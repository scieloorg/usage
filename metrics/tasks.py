from collections import defaultdict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext as _

from scielo_usage_counter import log_handler
from scielo_usage_counter import url_translator
from scielo_usage_counter.counter import compute_r5_metrics

from core.utils.utils import _get_user
from core.utils.date_utils import (
    get_date_obj,
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
import time


User = get_user_model()


@celery_app.task(bind=True, name=_('Parse logs'), timelimit=-1)
def task_parse_logs(self, collections=[], from_date=None, until_date=None, days_to_go_back=None, user_id=None, username=None):
    """
    Parses log files associated with a given collection.

    Args:
        collections (list, optional): List of collection acronyms to parse logs for. Defaults to all collections.
        from_date (str, optional): Start date for log parsing in 'YYYY-MM-DD' format. Defaults to None.
        until_date (str, optional): End date for log parsing in 'YYYY-MM-DD' format. Defaults to None.
        days_to_go_back (int, optional): Number of days to go back from the current date to parse logs. Defaults to None.
        user_id
        username

    Returns:
        None.
    """
    from_date, until_date = get_date_range_str(from_date, until_date, days_to_go_back)
    
    from_date_obj = get_date_obj(from_date)
    until_date_obj = get_date_obj(until_date)

    for collection in collections or Collection.acron3_list():
        for lf in LogFile.objects.filter(status=choices.LOG_FILE_STATUS_QUEUED, collection__acron3=collection):
            probably_date = _extract_date_from_validation(lf.validation)
            if not probably_date:
                logging.debug(f'Log file {lf.path} does not have a valid probably date.')
                continue

            if probably_date <= from_date_obj or probably_date >= until_date_obj:
                continue

            logging.info(f'PARSING file {lf.path}')
            task_parse_log.apply_async(args=(lf.hash, user_id, username))


def _extract_date_from_validation(validation):
    """
    Extracts the date from the validation dict of a log file.

    Args:
        validation (dict): The validation dict of the log file.

    Returns:
        datetime.date: The extracted date.
    """
    try:
        date_str = validation.get('probably_date')
        return get_date_obj(date_str, '%Y-%m-%d')
    except Exception as e:
        logging.error(f"Failed to extract date from validation: {e}")
        return None


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
    success = _process_lines(log_parser, url_translator_manager, log_file)

    if not success:
        logging.error(f'Failed to parse log file {log_file.path}.')
        return
    
    log_file.status = choices.LOG_FILE_STATUS_PROCESSED
    log_file.save()
    logging.info(f'Log file {log_file.path} has been successfully parsed.')


def _initialize_log_file(log_file_hash):
    """
    Initializes the log file for parsing by setting its status to 'parsing'.
    
    Args:
        log_file_hash (str): The hash of the log file to be initialized.
    
    Returns:
        LogFile: The initialized log file object, or None if it does not exist.
    """
    try:
        log_file = LogFile.get(hash=log_file_hash)
        log_file.status = choices.LOG_FILE_STATUS_PARSING
        log_file.save()
        return log_file
    except LogFile.DoesNotExist:
        logging.error(f'Log file with hash {log_file_hash} does not exist.')
        return None


def _fetch_required_resources():
    """
    Fetches the necessary resources for parsing logs, including robot user agents and MMDB files.
    
    Returns:
        tuple: A tuple containing the list of robot user agents and the latest MMDB object.
    """
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
    """
    Sets up the environment for parsing the log file, including initializing the log parser and URL translator manager.
    
    Args:
        log_file (LogFile): The log file to be parsed.
        robots_list (list): List of robot user agents.
        mmdb (MMDB): The MMDB object containing geolocation data.
    
    Returns:
        tuple: A tuple containing the LogParser instance and URLTranslationManager instance.
    """
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


def _load_metrics_objs_cache(log_file):
    """
    Loads the necessary objects into a cache for efficient access during log processing.
    
    Args:
        log_file (LogFile): The log file being processed.
    
    Returns:
        dict: A cache containing items and user agents.
    """
    logging.info(f'Loading metrics objects cache for {log_file.collection}')
    cache = {
        'items': {},
        'user_agents': {},
        'user_sessions': {},
        'item_accesses': {},
    }

    items_qs = Item.objects.filter(collection=log_file.collection).select_related('journal', 'article', 'collection')
    for it in items_qs:
        key = (it.collection.acron3, it.journal_id, it.article_id)
        cache['items'][key] = it
    logging.info(f'Loaded {len(cache["items"])} items for {log_file.collection}')

    user_agents_qs = UserAgent.objects.all()
    for ua in user_agents_qs:
        key = (ua.name, ua.version)
        cache['user_agents'][key] = ua
    logging.info(f'Loaded {len(cache["user_agents"])} user agents')

    return cache


def _fetch_art_jou_ids(utm, item_access_data):
    """
    Fetches the journal and article IDs based on the item access data.
    
    Args:
        utm (URLTranslationManager): The URL translation manager instance.
        item_access_data (dict): A dictionary containing item access data, including ISSN and PIDs.
    
    Returns:
        tuple: A tuple containing the journal ID and article ID, or (None, None) if not found.
    """
    issn = item_access_data.get('scielo_issn')
    if not issn:
        return (None, None)
    
    pid_v2 = item_access_data.get('pid_v2')
    pid_v3 = item_access_data.get('pid_v3')
    pid_generic = item_access_data.get('pid_generic')
    if not issn or not pid_v2 and not pid_v3 and not pid_generic:
        return (None, None)
    
    jou_db_id = utm.journals_metadata['issn_to_db_id'].get(issn)
    art_db_id = utm.articles_metadata['pid_v2_to_db_id'].get(pid_v2) or utm.articles_metadata['pid_v3_to_db_id'].get(pid_v3) or utm.articles_metadata['pid_generic_to_db_id'].get(pid_generic)

    return (jou_db_id, art_db_id)


def _process_lines(lp, utm, log_file):
    """
    Processes each line of the log file, translating URLs and registering item accesses.
    
    Args:
        lp (LogParser): The log parser instance.
        utm (URLTranslationManager): The URL translation manager instance.
        log_file (LogFile): The log file being processed.
    
    Returns:
        None.
    """
    logging.info(f'Loading metadata cache for {log_file.collection}')
    cache = _load_metrics_objs_cache(log_file)

    logging.info(f'Processing {lp.logfile}')
    for line in lp.parse():
        if not _process_line(line, utm, log_file, cache):
            continue

    return True


def _process_line(line, utm, log_file, cache):
    """
    Processes a single line from the log file, translating the URL and registering item access if valid.
    
    Args:
        line (dict): A dictionary representing a single log line.
        utm (URLTranslationManager): The URL translation manager instance.
        log_file (LogFile): The log file being processed.
        cache (dict): A cache containing pre-fetched objects to avoid redundant database queries.
    
    Returns:
        bool: True if the line was processed successfully, False otherwise.
    """
    try:
        translated_url = utm.translate(line.get('url'))
    except Exception as e:
        _log_discarded_line(log_file, line, tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_URL_TRANSLATION, str(e))
        return False
    
    item_access_data = {
        'collection': log_file.collection.acron3,
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
    
    jou_id, art_id = _fetch_art_jou_ids(utm, item_access_data)

    if not jou_id:
        _log_discarded_line(
            log_file, line,
            tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_JOURNAL,
            _('There is no journal registered for the given ISSN')
        )
        return False
    
    if not art_id:
        _log_discarded_line(
            log_file, line,
            tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_MISSING_ARTICLE,
            _('There is no article registered for the given PID')
        )
        return False
    
    try:
        _register_item_access(item_access_data, line, jou_id, art_id, cache)
    except Exception as e:
        _log_discarded_line(log_file, line, tracker_choices.LOG_FILE_DISCARDED_LINE_REASON_DATABASE_ERROR, str(e))
        return False

    return True


def _register_item_access(item_access_data, line, jou_id, art_id, cache):
    """
    Registers an item access in the database, creating necessary objects if they do not exist.
    Handles potential deadlocks by retrying on database errors.
    """
    col_acron3 = item_access_data.get('collection')
    media_format = item_access_data.get('media_format')
    media_language = item_access_data.get('media_language')
    content_type = item_access_data.get('content_type')

    client_name = line.get('client_name')
    client_version = line.get('client_version')
    local_datetime = line.get('local_datetime')
    country_code = line.get('country_code')
    ip_address = line.get('ip_address')

    truncated_datetime = truncate_datetime_to_hour(local_datetime)
    if timezone.is_naive(truncated_datetime):
        truncated_datetime = timezone.make_aware(truncated_datetime)
    ms_key = extract_minute_second_key(local_datetime)

    it = _get_or_create_item(col_acron3, jou_id, art_id, cache)
    ua = _get_or_create_user_agent(client_name, client_version, cache)
    us = _get_or_create_user_session(truncated_datetime, ua, ip_address, cache)
    ita = _get_or_create_item_access(it, us, media_format, media_language, country_code, content_type, ms_key, cache)

    ita.click_timestamps[ms_key] = ita.click_timestamps.get(ms_key, 0) + 1
    ita.save()


def _get_or_create_item(col_acron3, jou_id, art_id, cache, max_retries=3):
    item_key = (col_acron3, jou_id, art_id)
    for attempt in range(max_retries):
        try:
            if item_key not in cache['items']:
                collection_obj = Collection.objects.get(acron3=col_acron3)
                journal_obj = Journal.objects.get(id=jou_id)
                article_obj = Article.objects.get(id=art_id)
                it, _ = Item.objects.get_or_create(
                    collection=collection_obj,
                    journal=journal_obj,
                    article=article_obj,
                )
                cache['items'][item_key] = it
            else:
                it = cache['items'][item_key]
            return it
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1)
    return None


def _get_or_create_user_agent(client_name, client_version, cache, max_retries=3):
    user_agent_key = (client_name, client_version)
    for attempt in range(max_retries):
        try:
            if user_agent_key not in cache['user_agents']:
                ua, _ = UserAgent.objects.get_or_create(
                    name=client_name,
                    version=client_version
                )
                cache['user_agents'][user_agent_key] = ua
            else:
                ua = cache['user_agents'][user_agent_key]
            return ua
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1)
    return None


def _get_or_create_user_session(truncated_datetime, ua, ip_address, cache, max_retries=3):
    us_key = (truncated_datetime, ua.id, ip_address)
    for attempt in range(max_retries):
        try:
            if us_key not in cache['user_sessions']:
                us, _ = UserSession.objects.get_or_create(
                    datetime=truncated_datetime,
                    user_agent=ua,
                    user_ip=ip_address
                )
                cache['user_sessions'][us_key] = us
            else:
                us = cache['user_sessions'][us_key]
            return us
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1)
    return None


def _get_or_create_item_access(it, us, media_format, media_language, country_code, content_type, ms_key, cache, max_retries=3):
    item_access_key = (it.id, us.id, media_format, media_language, country_code, content_type)
    for attempt in range(max_retries):
        try:
            if item_access_key not in cache['item_accesses']:
                ita, _ = ItemAccess.objects.get_or_create(
                    item=it,
                    user_session=us,
                    media_format=media_format,
                    media_language=media_language,
                    country_code=country_code,
                    content_type=content_type,
                    defaults={'click_timestamps': {ms_key: 1}}
                )
                cache['item_accesses'][item_access_key] = ita
            else:
                ita = cache['item_accesses'][item_access_key]
            return ita
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1)
    return None


def _log_discarded_line(log_file, line, error_type, message):
    """
    Logs a discarded line from the log file and creates a record in the database.

    Args:
        log_file (LogFile): The log file being processed.
        line (dict): The log line that was discarded.
        error_type (str): The type of error that caused the line to be discarded.
        message (str): A message describing the reason for discarding the line.
    """
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


@celery_app.task(bind=True, name=_('Index metrics'), timelimit=-1)
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

        clfdc_to_update = []

        bulk_data = []
        metrics_result = compute_metrics_for_collection(collection, dates, replace, clfdc_to_update)

        for key, metric_data in metrics_result.items():
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
                    clfdc_to_update = []

        if bulk_data:
            try:
                index_documents(
                    index_name=settings.ES_INDEX_NAME,
                    documents={doc["_id"]: doc["_source"] for doc in bulk_data},
                    client=es_client,
                )
            except Exception as e:
                logging.error(f"Failed to send remaining bulk metrics to Elasticsearch: {e}")
                clfdc_to_update = []

        for clfdc in clfdc_to_update:
            clfdc.is_usage_metric_computed = True
            clfdc.save()


def compute_metrics_for_collection(collection, dates, replace=False, clfdc_to_update=None):
    """
    Computes usage metrics for a given collection over a range of dates.

    Args:
        collection (str): The acronym of the collection for which metrics 
            are to be computed.
        dates (list[datetime.date]): A list of dates for which metrics 
            should be computed.
        replace (bool, optional): A flag indicating whether to replace 
            existing metrics. Defaults to False.
        clfdc_to_update (list, optional): List to append clfdc objects that should be marked as computed after successful export.

    Returns:
        dict: A dictionary containing computed metrics, keyed by a 
        generated usage key.
    """
    data = {}

    if clfdc_to_update is None:
        clfdc_to_update = []

    for date in dates:
        date_str = get_date_str(date)

        if not _is_valid_log_file_status(collection, date_str):
            continue

        is_valid, clfdc = _is_valid_collection_log_file_date(collection, date_str, replace)
        if not is_valid:
            continue

        logging.info(f"Computing metrics for {date_str}")
        _process_user_sessions(collection, date, date_str, data)
        clfdc_to_update.append(clfdc)

    return data


def _is_valid_collection_log_file_date(collection, date_str, replace):
    """
    Checks if the CollectionLogFileDateCount exists and is valid for the given date.

    Args:
        collection (str): The acronym of the collection.
        date_str (str): The date string in 'YYYY-MM-DD' format.
        replace (bool): Whether to replace existing metrics.
    
    Returns:
        tuple: A tuple containing a boolean indicating if the date is valid and the CollectionLogFileDateCount object if it exists.
    """
    try:
        clfdc = CollectionLogFileDateCount.objects.get(date=date_str, collection__acron3=collection)

        if clfdc.status != choices.COLLECTION_LOG_FILE_DATE_COUNT_OK:
            logging.info(f'CollectionLogFileDateCount status is not OK for {date_str}')
            return False, None

        if not replace and clfdc.is_usage_metric_computed:
            logging.info(f'Usage metric already computed for {date_str}')
            return False, None

        return True, clfdc

    except CollectionLogFileDateCount.DoesNotExist:
        logging.info(f'CollectionLogFileDateCount does not exist for {date_str}')
        return False, None


def _is_valid_log_file_status(collection, date_str):
    """
    Checks if all LogFileDate objects for the given date and collection have a valid status.
    
    Args:
        collection (str): The acronym of the collection.
        date_str (str): The date string in 'YYYY-MM-DD' format.
    
    Returns:
        bool: True if all LogFileDate objects have a valid status, False otherwise.
    """
    for lfd in LogFileDate.objects.filter(date=date_str, log_file__collection__acron3=collection):
        if lfd.log_file.status not in (choices.LOG_FILE_STATUS_INVALIDATED, choices.LOG_FILE_STATUS_PROCESSED):
            logging.info(f'LogFile status is not PROCESSED for {date_str}')
            return False
    return True


def _process_user_sessions(collection, date, date_str, data):
    """
    Processes user sessions for a given collection and date, computing metrics for each item access.

    Args:
        collection (str): The acronym of the collection.
        date (datetime.date): The date for which to compute metrics.
        date_str (str): The date string in 'YYYY-MM-DD' format.
        data (dict): A dictionary to store computed metrics.
    """
    all_item_accesses = ItemAccess.objects.filter(
        item__collection__acron3=collection,
        user_session__datetime__date=date_str
    ).select_related(
        'item__journal',
        'item__article',
        'item__collection',
        'user_session'
    ).only(
        'item__journal__scielo_issn',
        'item__article__pid_v2',
        'item__article__pid_v3',
        'item__article__pid_generic',
        'item__collection__acron3',
        'media_language',
        'country_code',
        'click_timestamps',
        'content_type',
        'user_session__datetime',
        'user_session__user_agent__name',
        'user_session__user_agent__version',
        'user_session__user_ip',
    ).iterator()

    user_sessions_data = defaultdict(list)
    for item_access in all_item_accesses:
        if item_access.item.collection.acron3 != collection:
            continue
        user_sessions_data[item_access.user_session].append(item_access)

    for user_session, item_accesses_list in user_sessions_data.items():
        for item_access in item_accesses_list:
            key = _generate_usage_key(
                collection,
                item_access.item.journal.scielo_issn,
                item_access.item.article.pid_v2 or '',
                item_access.item.article.pid_v3 or '',
                item_access.item.article.pid_generic or '',
                item_access.media_language,
                item_access.country_code,
                date_str,
            )

            compute_r5_metrics(
                key,
                data,
                collection,
                item_access.item.journal.scielo_issn,
                item_access.item.article.pid_v2 or '',
                item_access.item.article.pid_v3 or '',
                item_access.item.article.pid_generic or '',
                item_access.media_language,
                item_access.country_code,
                date_str,
                date.year,
                date.month,
                date.day,
                item_access.click_timestamps,
                item_access.content_type,
            )

    return True


def _generate_usage_key(collection, journal, pid_v2, pid_v3, pid_generic, media_language, country_code, date_str):
    """"
    Generates a unique key for the given parameters.

    :param collection: collection acrononym with 3 characters
    :param journal: journal ISSN (e.g., scielo_issn)
    :param pid_v2: PID v2
    :param pid_v3: PID v3
    :param pid_generic: generic PID
    :param media_language: media language
    :param country_code: country code
    :param date_str: date string in the format YYYY-MM-DD

    :return: a string that uniquely identifies the combination of parameters
    """
    return '|'.join([
        collection,
        journal,
        pid_v2 or '',
        pid_v3 or '',
        pid_generic or '',
        media_language,
        country_code,
        date_str
    ])
