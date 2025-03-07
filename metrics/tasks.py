from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext as _

from scielo_usage_counter import log_handler
from scielo_usage_counter import url_translator

from core.utils.utils import _get_user
from config import celery_app

from article.models import Article
from journal.models import Journal
from log_manager import choices
from log_manager.models import LogFile
from resources.models import MMDB, RobotUserAgent
from tracker.models import LogFileDiscardedLine
from tracker import choices as tracker_choices

from .models import UserAgent, UserSession, Item, ItemAccess

import logging


User = get_user_model()

@celery_app.task(bind=True, name=_('Compute access'), timelimit=-1)
def task_parse_logs(self, collection, user_id=None, username=None):
    """
    Parses log files associated with a given collection.

    Args:
        collection (str): Acronym associated with the collection for which logs are being parsed.
        user_id
        username

    Returns:
        None.
    """    
    for lf in LogFile.objects.filter(status=choices.LOG_FILE_STATUS_QUEUED, collection__acron3=collection):
        logging.info(f'PARSING file {lf.path}')
        task_parse_log.apply_async(args=(lf.hash, user_id, username))
        

@celery_app.task(bind=True, name=_('Parse one log'), timelimit=-1)
def task_parse_log(self, log_file_hash, user_id=None, username=None):
    """
    Parses a log file, extracts relevant information, and creates processed log records in the database.

    Args:
        log_file_hash (str): Hash representing the log file to be parsed.
        user_id
        username

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    log_file = LogFile.get(hash=log_file_hash)
    log_file.status = choices.LOG_FILE_STATUS_PARSING
    log_file.save()

    robots_list = RobotUserAgent.get_all_patterns()
    if not robots_list:
        logging.error('There are no robots available in the database.')
        log_file.status = choices.LOG_FILE_STATUS_QUEUED
        log_file.save()
        return

    mmdb = MMDB.objects.latest('created')
    if not mmdb:
        logging.error('There are no MMDB files available in the database.')
        log_file.status = choices.LOG_FILE_STATUS_QUEUED
        log_file.save()
        return
    
    lp = log_handler.LogParser(mmdb_data=mmdb.data, robots_list=robots_list, output_mode='dict')
    lp.logfile = log_file.path

    logging.info(f'Creating URL translation manager for {log_file.collection}')
    utm = url_translator.URLTranslationManager(
        articles_metadata=Article.metadata(collection=log_file.collection),
        journals_metadata=Journal.metadata(collection=log_file.collection),
    )
    
    logging.info(f'Processing {lp.logfile}')
    for line in lp.parse():
        translated_url = utm.translate(line.get('url'))

        collection = log_file.collection

        scielo_issn = translated_url.get('scielo_issn')
        pid_v2 = translated_url.get('pid_v2')

        # TODO: Ensure that the PID v3 is a valid PID v3.
        pid_v3 = translated_url.get('pid_v3') or ''

        # TODO: Ensure that the media_language is a valid language code formed by two characters.
        media_language = translated_url.get('media_language')

        media_format = translated_url.get('media_format')

        if not scielo_issn or not pid_v2 and not pid_v3 or not media_language or not media_format:
            logging.info(f'It was not possible to identify the necessary information for the URL {line.get("url")}')
            LogFileDiscardedLine.create(
                log_file=log_file,
                data=line,
                error_type=tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_METADATA,
                message=_(f'It was not possible to identify the necessary information for the URL {line.get("url")}'),
            )
            continue

        client_name = line.get('client_name')
        client_version = line.get('client_version')
        local_datetime = line.get('local_datetime')
        country_code = line.get('country_code')
        ip_address = line.get('ip_address')

        try:
            art_obj = Article.objects.get(Q(collection=collection) & (Q(pid_v2=pid_v2) | Q(pid_v3=pid_v3)))
        except Article.DoesNotExist:
            logging.info(f'There is no article registered for Collection {collection} and PID v2 {pid_v2} or v3 {pid_v3}')
            LogFileDiscardedLine.create(
                log_file=log_file,
                data=line,
                error_type=tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_ARTICLE,
                message=_('There is no article registered for the given PID'),
            )
            continue

        try:
            jou_obj = Journal.objects.get(Q(collection=collection) & Q(scielo_issn=scielo_issn))
        except Journal.DoesNotExist:
            logging.info(f'There is no journal registered for the Collection {collection} and ISSN {scielo_issn}')
            LogFileDiscardedLine.create(
                log_file=log_file,
                data=line,
                error_type=tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_JOURNAL,
                message=_('There is no journal registered for the given collection and ISSN'),
            )
            continue

        logging.info(f'INFO. Article {art_obj} from Journal {jou_obj} has been identified. Country code: {line["country_code"]},  Language: {media_language}, Media format: {media_format}')
        it, created = Item.objects.get_or_create(
            collection=collection,
            journal=jou_obj,
            article=art_obj,
        )
        if created:
            it.save()

        ua, created = UserAgent.objects.get_or_create(
            name=client_name,
            version=client_version,
        )
        if created:
            ua.save()

        us, created = UserSession.objects.get_or_create(
            datetime=local_datetime,
            user_agent=ua,
            user_ip=ip_address,
        )
        if created:
            us.save()

        ita, created = ItemAccess.objects.get_or_create(
            item=it,
            user_session=us,
            media_format=media_format,
            media_language=media_language,
            country_code=country_code,
        )
        if created:
            ita.save()

    logging.info(f'File {log_file.path} has been parsed.')
    log_file.status = choices.LOG_FILE_STATUS_PROCESSED        
    log_file.save()
