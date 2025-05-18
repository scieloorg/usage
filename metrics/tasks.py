from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext as _

from scielo_usage_counter import log_handler
from scielo_usage_counter import url_translator
from scielo_usage_counter.counter import compute_r5_metrics

from core.utils.utils import _get_user
from core.utils.date_utils import (
    get_date_str,
    get_date_range_str,
    get_date_objs_from_date_range,
    extract_minute_second_key,
    truncate_datetime_to_hour,
)
from config import celery_app

from article.models import Article
from core.utils import standardizer
from collection.models import Collection
from journal.models import Journal
from log_manager import choices
from log_manager_config.models import (
    CollectionURLTranslatorClass,
    CollectionLogDirectory,
)
from log_manager.models import LogFile, CollectionLogFileDateCount, LogFileDate
from resources.models import MMDB, RobotUserAgent
from tracker.models import LogFileDiscardedLine
from tracker import choices as tracker_choices

from .es import create_index, delete_documents_by_key, index_documents, get_elasticsearch_client

from .utils import (
    is_valid_item_access_data,
    translator_class_name_to_obj,
)
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
    robots_list, mmdb = _fetch_required_resources()
    if not robots_list or not mmdb:
        return
    
    log_file = _initialize_log_file(log_file_hash)
    if not log_file:
        return

    log_parser, url_translator_manager = _setup_parsing_environment(log_file, robots_list, mmdb)
    _process_lines(log_parser, url_translator_manager, log_file)


def _initialize_log_file(log_file_hash):
    try:
        log_file = LogFile.get(hash=log_file_hash)
        log_file.status = choices.LOG_FILE_STATUS_PARSING
        log_file.save()
        return log_file
    except LogFile.DoesNotExist:
        logging.error(f'Log file with hash {log_file_hash} does not exist.')
        return None


def _fetch_required_resources():
    robots_list = RobotUserAgent.get_all_patterns()
    if not robots_list:
        logging.error('There are no robots available in the database.')
        return None, None

    mmdb = MMDB.objects.latest('created')
    if not mmdb:
        logging.error('There are no MMDB files available in the database.')
        return None, None

    return robots_list, mmdb


def _setup_parsing_environment(log_file, robots_list, mmdb):
    lp = log_handler.LogParser(mmdb_data=mmdb.data, robots_list=robots_list, output_mode='dict')
    lp.logfile = log_file.path

    translator_class = None
    for cld in CollectionLogDirectory.objects.filter(collection=log_file.collection):
        if cld.path in log_file.path:
            try:
                translator_class_name = CollectionURLTranslatorClass.objects.get(collection=log_file.collection, directory=cld).translator_class
                translator_class = translator_class_name_to_obj(translator_class_name)
                break
            except CollectionURLTranslatorClass.DoesNotExist:
                continue

    if not translator_class:
        raise Exception(f'No URL translator class found for collection {log_file.collection}.')

    logging.info(f'Creating URL translation manager for {log_file.collection}')
    utm = url_translator.URLTranslationManager(
        articles_metadata=Article.metadata(collection=log_file.collection),
        journals_metadata=Journal.metadata(collection=log_file.collection),
        translator=translator_class,
    )
    return lp, utm


def _process_lines(lp, utm, log_file):
    logging.info(f'Processing {lp.logfile}')
    for line in lp.parse():
        if not _process_line(line, utm, log_file):
            continue

    logging.info(f'File {log_file.path} has been parsed.')
    log_file.status = choices.LOG_FILE_STATUS_PROCESSED
    log_file.save()


def _process_line(line, utm, log_file):
    try:
        translated_url = utm.translate(line.get('url'))
    except Exception as e:
        _log_discarded_line(log_file, line, tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_URL_TRANSLATION, str(e))
        return False
    
    item_access_data = {
        'collection': log_file.collection,
        'scielo_issn': translated_url.get('scielo_issn'),
        'pid_v2': standardizer.standardize_pid_v2(translated_url.get('pid_v2')),
        'pid_v3': standardizer.standardize_pid_v3(translated_url.get('pid_v3')),
        'pid_generic': standardizer.standardize_pid_generic(translated_url.get('pid_generic')),
        'media_language': standardizer.standardize_language_code(translated_url.get('media_language')),
        'media_format': translated_url.get('media_format'),
        'content_type': translated_url.get('content_type'),
    }

    if not is_valid_item_access_data(item_access_data):
        _log_discarded_line(
            log_file, line,
            tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_METADATA,
            _(f'It was not possible to identify the necessary information for the URL {line.get("url")}')
        )
        return False

    _register_item_access(item_access_data, line, log_file)
    return True


def _register_item_access(item_access_data, line, log_file):
    # ItemAccess data
    collection = item_access_data.get('collection')
    scielo_issn = item_access_data.get('scielo_issn')
    pid_v2 = item_access_data.get('pid_v2')
    pid_v3 = item_access_data.get('pid_v3')
    pid_generic = item_access_data.get('pid_generic')
    media_format = item_access_data.get('media_format')
    media_language = item_access_data.get('media_language')
    content_type = item_access_data.get('content_type')

    # UserAgent and UserSession data
    client_name = line.get('client_name')
    client_version = line.get('client_version')
    local_datetime = line.get('local_datetime')
    country_code = line.get('country_code')
    ip_address = line.get('ip_address')

    art_obj = _fetch_article(collection, pid_v2, pid_v3, pid_generic, log_file, line)
    if not art_obj:
        return

    jou_obj = _fetch_journal(collection, scielo_issn, log_file, line)
    if not jou_obj:
        return
    
    truncated_datetime = truncate_datetime_to_hour(local_datetime)
    ms_key = extract_minute_second_key(local_datetime)

    it, _it = Item.objects.get_or_create(collection=collection, journal=jou_obj, article=art_obj)
    ua, _ua = UserAgent.objects.get_or_create(name=client_name, version=client_version)
    us, _us = UserSession.objects.get_or_create(datetime=truncated_datetime, user_agent=ua, user_ip=ip_address)
    ita, _ita = ItemAccess.objects.get_or_create(
        item=it, user_session=us, media_format=media_format,
        media_language=media_language, country_code=country_code, content_type=content_type
    )

    # Update the access count
    ita.click_timestamps[ms_key] = ita.click_timestamps.get(ms_key, 0) + 1

    ita.save()


def _fetch_article(collection, pid_v2, pid_v3, pid_generic, log_file, line):
    try:
        if pid_generic:
            return Article.objects.get(Q(collection=collection) & Q(pid_generic=pid_generic))
        return Article.objects.get(Q(collection=collection) & (Q(pid_v2=pid_v2) | Q(pid_v3=pid_v3)))
    except Article.DoesNotExist:
        _log_discarded_line(
            log_file, line,
            tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_ARTICLE,
            _('There is no article registered for the given PID')
        )
        return None


def _fetch_journal(collection, scielo_issn, log_file, line):
    try:
        return Journal.objects.get(Q(collection=collection) & Q(scielo_issn=scielo_issn))
    except Journal.DoesNotExist:
        _log_discarded_line(
            log_file, line,
            tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_JOURNAL,
            _('There is no journal registered for the given collection and ISSN')
        )
        return None


def _log_discarded_line(log_file, line, error_type, message):
    LogFileDiscardedLine.create(log_file=log_file, data=line, error_type=error_type, message=message)


@celery_app.task(bind=True, name=_('Create index'), timelimit=-1)
def task_create_index(self, index_name, mappings=None, user_id=None, username=None):
    """
    Creates an Elasticsearch index with the specified settings and mappings.

    Args:
        index_name (str): The name of the index to be created.
        mappings (dict, optional): The mappings for the index. Defaults to None.
        user_id (int, optional): The ID of the user initiating the task. Defaults to None.
        username (str, optional): The username of the user initiating the task. Defaults to None.

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)
    es_client = get_elasticsearch_client(settings.ES_URL, settings.ES_BASIC_AUTH, settings.ES_API_KEY)

    try:
        if es_client.indices.exists(index=index_name):
            logging.info(f"Index {index_name} already exists.")
            return

        create_index(client=es_client, index_name=index_name, mappings=mappings)
        logging.info(f"Index {index_name} created successfully.")
    except Exception as e:
        logging.error(f"Failed to create index {index_name}: {e}")


@celery_app.task(bind=True, name=_('Delete index'), timelimit=-1)
def task_delete_index(self, index_name, user_id=None, username=None):
    """
    Deletes an Elasticsearch index.

    Args:
        index_name (str): The name of the index to be deleted.
        user_id (int, optional): The ID of the user initiating the task. Defaults to None.
        username (str, optional): The username of the user initiating the task. Defaults to None.

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)
    es_client = get_elasticsearch_client(settings.ES_URL, settings.ES_BASIC_AUTH, settings.ES_API_KEY)

    try:
        if not es_client.indices.exists(index=index_name):
            logging.info(f"Index {index_name} does not exist.")
            return

        es_client.indices.delete(index=index_name)
        logging.info(f"Index {index_name} deleted successfully.")
    except Exception as e:
        logging.error(f"Failed to delete index {index_name}: {e}")


@celery_app.task(bind=True, name=_('Delete documents by key'), timelimit=-1)
def task_delete_documents_by_key(self, keys, values, index_name=None, user_id=None, username=None):
    """
    Deletes documents from Elasticsearch based on the provided keys and values.

    Args:
        keys (list): List of document keys to delete.
        values (dict): Additional values to filter documents for deletion. This is required.
        index_name (str, optional): The name of the Elasticsearch index. Defaults to settings.ES_INDEX_NAME.
        user_id (int, optional): The ID of the user initiating the task. Defaults to None.
        username (str, optional): The username of the user initiating the task. Defaults to None.

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)
    es_client = get_elasticsearch_client(settings.ES_URL, settings.ES_BASIC_AUTH, settings.ES_API_KEY)

    if not index_name:
        index_name = settings.ES_INDEX_NAME

    try:
        delete_documents_by_key(client=es_client, index_name=index_name, keys=keys, values=values)
        logging.info(f"Successfully deleted documents with keys: {keys} and values: {values} from index {index_name}.")
    except Exception as e:
        logging.error(f"Failed to delete documents with keys {keys} and values {values} from index {index_name}: {e}")


@celery_app.task(bind=True, name=_('Compute metrics'), timelimit=-1)
def task_index_documents(self, collections=[], from_date=None, until_date=None, days_to_go_back=None, user_id=None, username=None, bulk_size=5000, replace=False):
    """
    Task to compute and index metrics for specified collections within a given date range.

    This task retrieves metrics for the specified collections and indexes them into an Elasticsearch
    index. The metrics are computed for the provided date range or a range derived from the given
    parameters.

    Args:
        collections (list, optional): List of collection identifiers to compute metrics for. Defaults to an empty list.
        from_date (str, optional): Start date for the metrics computation in 'YYYY-MM-DD' format. Defaults to None.
        until_date (str, optional): End date for the metrics computation in 'YYYY-MM-DD' format. Defaults to None.
        days_to_go_back (int, optional): Number of days to go back from the current date to compute metrics. Defaults to None.
        user_id (int, optional): ID of the user initiating the task. Defaults to None.
        username (str, optional): Username of the user initiating the task. Defaults to None.
        bulk_size (int, optional): Number of documents to send in each bulk request to Elasticsearch. Defaults to 5000.
        replace (bool, optional): If True, replaces existing documents in Elasticsearch. Defaults to False.

    Raises:
        Exception: Logs errors if bulk indexing to Elasticsearch fails.

    Notes:
        - If no collections are provided, the task will compute metrics for all collections.
        - The date range is determined by the combination of `from_date`, `until_date`, and `days_to_go_back`.
        - Metrics are computed and indexed in bulk to optimize performance.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    if not collections:
        collections = Collection.acron3_list()

    from_date_str, until_date_str = get_date_range_str(from_date, until_date, days_to_go_back)
    dates = get_date_objs_from_date_range(from_date_str, until_date_str)

    es_client = get_elasticsearch_client(settings.ES_URL, settings.ES_BASIC_AUTH, settings.ES_API_KEY)

    for collection in collections:
        logging.info(f'Computing metrics for collection {collection} from {from_date_str} to {until_date_str}')

        bulk_data = []

        for key, metric_data in compute_metrics_for_collection(collection, dates, replace).items():
            bulk_data.append({
                "_id": key,
                "_source": metric_data,
            })

            if len(bulk_data) >= bulk_size:
                try:
                    index_documents(
                        index_name=settings.ES_INDEX_NAME,
                        documents={doc["_id"]: doc["_source"] for doc in bulk_data},
                        client=es_client,
                    )
                    bulk_data = []
                except Exception as e:
                    logging.error(f"Failed to send bulk metrics to Elasticsearch: {e}")

        if bulk_data:
            try:
                index_documents(
                    index_name=settings.ES_INDEX_NAME,
                    documents={doc["_id"]: doc["_source"] for doc in bulk_data},
                    client=es_client,
                )
            except Exception as e:
                logging.error(f"Failed to send remaining bulk metrics to Elasticsearch: {e}")


def compute_metrics_for_collection(collection, dates, replace=False):
    """
    Computes usage metrics for a given collection over a range of dates.

    Args:
        collection (str): The acronym of the collection for which metrics 
            are to be computed.
        dates (list[datetime.date]): A list of dates for which metrics 
            should be computed.
        replace (bool, optional): A flag indicating whether to replace 
            existing metrics. Defaults to False.

    Returns:
        dict: A dictionary containing computed metrics, keyed by a 
        generated usage key.
    """
    data = {}

    for date in dates:
        date_str = get_date_str(date)

        if not _is_valid_log_file_status(collection, date_str):
            continue

        is_valid, clfdc = _is_valid_collection_log_file_date(collection, date_str, replace)
        if not is_valid:
            continue

        _process_user_sessions(collection, date, date_str, data)
        clfdc.is_usage_metric_computed = True
        clfdc.save()

    return data


def _is_valid_collection_log_file_date(collection, date_str, replace):
    try:
        clfdc = CollectionLogFileDateCount.objects.get(date=date_str, collection__acron3=collection)

        if clfdc.status != choices.COLLECTION_LOG_FILE_DATE_COUNT_OK:
            print(f'CollectionLogFileDateCount status is not OK for {date_str}')
            return False, None

        if not replace and clfdc.is_usage_metric_computed:
            print(f'Usage metric already computed for {date_str}')
            return False, None

        return True, clfdc

    except CollectionLogFileDateCount.DoesNotExist:
        print(f'CollectionLogFileDateCount does not exist for {date_str}')
        return False, None


def _is_valid_log_file_status(collection, date_str):
    for lfd in LogFileDate.objects.filter(date=date_str, log_file__collection__acron3=collection):
        if lfd.log_file.status not in (choices.LOG_FILE_STATUS_INVALIDATED, choices.LOG_FILE_STATUS_PROCESSED):
            print(f'LogFile status is not PROCESSED for {date_str}')
            return False
    return True


def _process_user_sessions(collection, date, date_str, data):
    for user_session in UserSession.objects.filter(itemaccess__item__collection__acron3=collection, datetime__date=date_str):
        _process_item_accesses(collection, date, date_str, user_session, data)

