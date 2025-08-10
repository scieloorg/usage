import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from scielo_usage_counter import log_handler
from scielo_usage_counter import url_translator

from config import celery_app
from core.utils.utils import _get_user
from core.utils.date_utils import get_date_obj, get_date_range_str
from article.models import Article
from collection.models import Collection
from journal.models import Journal
from log_manager import choices
from log_manager_config.models import CollectionURLTranslatorClass, CollectionLogFilesPerDay, CollectionLogDirectory
from log_manager.models import LogFile, CollectionLogFileDateCount, LogFileDate
from resources.models import MMDB, RobotUserAgent
from tracker.models import LogFileDiscardedLine
from tracker.choices import LOG_FILE_DISCARDED_LINE_REASON_MISSING_ARTICLE, LOG_FILE_DISCARDED_LINE_REASON_MISSING_JOURNAL

from . import es
from .utils import parser_utils, index_utils


User = get_user_model()


@celery_app.task(bind=True, name=_('Parse logs'), timelimit=-1)
def task_parse_logs(self, collections=[], include_logs_with_error=True, batch_size=5000, replace=False, track_errors=False, from_date=None, until_date=None, days_to_go_back=None, user_id=None, username=None):
    """
    Parses log files associated with a given collection.

    Args:
        collections (list, optional): List of collection acronyms to parse logs for. Defaults to all collections.
        include_logs_with_error (bool, optional): Whether to include logs with errors. Defaults to True.
        batch_size (int, optional): Number of records to process in a single batch. Defaults to 5000.
        replace (bool, optional): Whether to replace existing records. Defaults to False.
        track_errors (bool, optional): Whether to track errors in log parsing. Defaults to False.
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

    # Set status filters based on the include_logs_with_error and replace flags
    status_filters = [choices.LOG_FILE_STATUS_QUEUED]
    if include_logs_with_error:
        status_filters.append(choices.LOG_FILE_STATUS_ERROR)
    if replace:
        status_filters.append(choices.LOG_FILE_STATUS_PROCESSED)

    for collection in collections or Collection.acron3_list():
        for lf in LogFile.objects.filter(status__in=status_filters, collection__acron3=collection):
            probably_date = parser_utils.extract_date_from_validation_dict(lf.validation)
            if not probably_date:
                logging.debug(f'Log file {lf.path} does not have a valid probably date.')
                continue

            if probably_date < from_date_obj or probably_date > until_date_obj:
                continue

            logging.info(f'PARSING file {lf.path}')
            task_parse_log.apply_async(args=(lf.hash, batch_size, replace, track_errors, user_id, username))


@celery_app.task(bind=True, name=_('Parse one log'), timelimit=-1)
def task_parse_log(self, log_file_hash, batch_size=5000, replace=False, track_errors=False, user_id=None, username=None):
    """
    Parses a log file, extracts relevant information, and creates processed log records in the database.

    Args:
        log_file_hash (str): Hash representing the log file to be parsed.
        batch_size (int, optional): Number of records to process in a single batch. Defaults to 5000.
        replace (bool, optional): Whether to replace existing records. Defaults to False.
        track_errors (bool, optional): Whether to track errors in log parsing. Defaults to False.
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
    
    clfdc = create_or_update_collection_log_file_date_count(
        user=user,
        collection=log_file.collection,
        date=get_date_obj(log_file.validation.get('probably_date'))
    )

    if not replace and clfdc.is_usage_metric_computed:
        logging.info(f'Usage metric already computed for {log_file.validation.get("probably_date")}')
        return
    
    if replace:
        clfdc.exported_files_count = 0
        clfdc.is_usage_metric_computed = False
        clfdc.save()

    log_parser, url_translator_manager = _setup_parsing_environment(log_file, robots_list, mmdb)
    success = _process_lines(lp=log_parser, utm=url_translator_manager, log_file=log_file, batch_size=batch_size, replace=replace, track_errors=track_errors)

    if not success:
        logging.error(f'Failed to parse log file {log_file.path}.')
        log_file.status = choices.LOG_FILE_STATUS_ERROR
        log_file.save()
        return
    
    log_file.status = choices.LOG_FILE_STATUS_PROCESSED
    log_file.save()

    _update_exported_files_count(clfdc)

    logging.info(f'Log file {log_file.path} has been successfully parsed.')


def create_or_update_collection_log_file_date_count(user, collection, date):
    n_expected_files = CollectionLogFilesPerDay.get_number_of_expected_files_by_day(collection=collection.acron3, date=date)
    n_found_logs = LogFileDate.get_number_of_found_files_for_date(collection=collection.acron3, date=date)
    
    return CollectionLogFileDateCount.create_or_update(
        user=user,
        collection=collection,
        date=date,
        expected_log_files=n_expected_files,
        found_log_files=n_found_logs,
    )


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
                translator_class = parser_utils.translator_class_name_to_obj(translator_class_name)
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


def _process_lines(lp, utm, log_file, batch_size=5000, replace=False, track_errors=False):
    """
    Processes each line of the log file, translating URLs and registering item accesses.
    
    Args:
        lp (LogParser): The log parser instance.
        utm (URLTranslationManager): The URL translation manager instance.
        log_file (LogFile): The log file being processed.
        batch_size (int, optional): Number of records to process in a single batch. Defaults to 5000.
        replace (bool, optional): Whether to replace existing records. Defaults to False.
        track_errors (bool, optional): Whether to track errors in log parsing. Defaults to False.
    
    Returns:
        None.
    """
    logging.info(f'Processing {lp.logfile}')
    results = {}
    errors = []

    jump = log_file.last_processed_line if not replace else 0

    es_manager = es.ElasticSearchUsageWrapper(
        settings.ES_URL, 
        settings.ES_BASIC_AUTH, 
        settings.ES_API_KEY,
        settings.ES_VERIFY_CERTS
    )

    if not es_manager.ping():
        logging.error('Elasticsearch client is not available.')
        return False
    
    index_name = index_utils.generate_index_name(
        index_prefix=settings.ES_INDEX_NAME, 
        collection=log_file.collection.acron3, 
        date=log_file.validation.get('probably_date')
    )

    es_manager.create_index_if_not_exists(index_name=index_name)

    if replace:
        logging.info(f'Removing existing documents for collection {log_file.collection.acron3} and date {log_file.validation.get("probably_date")}')
        delete_success = es_manager.delete_documents_by_key(
            index_name=index_name,
            data={'collection': log_file.collection.acron3, 'date': log_file.validation.get('probably_date')},
        )
        if not delete_success:
            logging.error(f'Failed to delete existing documents for collection {log_file.collection.acron3} and date {log_file.validation.get("probably_date")}')
            return False

    for line in lp.parse():
        if lp.stats.lines_parsed < jump:
            continue

        if lp.stats.lines_parsed % batch_size == 0:
            logging.info(f'Processing line {lp.stats.lines_parsed} of {lp.logfile}')

        is_valid_line, error_obj = _process_line(results, line, utm, log_file, track_errors)
        if not is_valid_line:
            if error_obj:
                errors.append(error_obj)

            if len(errors) >= batch_size:
                LogFileDiscardedLine.objects.bulk_create(errors)
                errors = []
            continue

        if len(results) >= batch_size:
            logging.info(f'Indexing data for log file {log_file.path}')
            es_manager.export_to_index(
                index_name=index_name, 
                data=results, 
                batch_size=batch_size
            )
            results = {}

            _update_log_file_summary(log_file, lp.stats.get_stats())

    logging.info(f'Indexing data for log file {log_file.path}')
    es_manager.export_to_index(
        index_name=index_name,
        data=results,
        batch_size=batch_size
    )
    results = {}

    LogFileDiscardedLine.objects.bulk_create(errors) if errors else None
    errors = []

    _update_log_file_summary(log_file, lp.stats.get_stats())

    return True


def _update_log_file_summary(log_file, stats):
    if not stats:
        logging.warning(f'No stats available for log file {log_file.path}. Skipping summary update.')
        return
    
    summary_k, summary_v = stats
    log_file.summary = dict(zip(summary_k, summary_v))
    log_file.last_processed_line = log_file.summary.get('lines_parsed', 0)
    log_file.save()


def _update_exported_files_count(collection_log_file_date: CollectionLogFileDateCount):
    collection_log_file_date.exported_files_count += 1
    collection_log_file_date.set_is_usage_metric_computed()
    collection_log_file_date.save()
   

def _process_line(results, line, utm, log_file, track_errors=False):
    """
    Process a single log line to extract and validate item access data.
    This function translates a URL from the log line, extracts item access data,
    validates the data, and updates the results if the data is valid.
    
    Args:
        results: Dictionary or data structure to store processed results
        line (dict): Log line containing URL and other access information
        utm: URL translation manager for converting URLs
        log_file: Log file object containing collection information (must have collection.acron3)
        track_errors (bool): Whether to track errors in log parsing.
    
    Returns:
        tuple: A tuple containing a boolean indicating success or failure, and an optional LogFileDiscardedLine object.
    
    Raises:
        Logs errors for URL translation failures and item access data extraction failures.
        Logs debug messages for invalid item access data.
    """
    try:
        translated_url = utm.translate(line.get('url'))
    except Exception as e:
        logging.error(f'Error translating URL {line.get("url")}: {e}')
        return False, None
   
    try:
        item_access_data = index_utils.extract_item_access_data(log_file.collection.acron3, translated_url)
    except Exception as e:
        logging.error(f'Error extracting item access data from URL {line.get("url")}: {e}')
        return False, None
    
    ignore_utm_validation = not track_errors
    is_valid, check_result = index_utils.is_valid_item_access_data(item_access_data, utm, ignore_utm_validation)

    if not is_valid:
        if track_errors:
            error_code = check_result.get('code')

            if error_code in {
                'invalid_scielo_issn', 
                'invalid_pid_v3',
                'invalid_pid_v2', 
                'invalid_pid_generic'
            }:
                if 'pid' in error_code:
                    tracker_error_type = LOG_FILE_DISCARDED_LINE_REASON_MISSING_ARTICLE
                else:
                    tracker_error_type = LOG_FILE_DISCARDED_LINE_REASON_MISSING_JOURNAL

                lfdl = LogFileDiscardedLine.create(
                    log_file=log_file,
                    error_type=tracker_error_type,
                    message=check_result.get('message'),
                    data={'line': line, 'item_access_data': item_access_data},
                    save=False,
                )
                logging.debug(f'Invalid item access data: {check_result.get("message")}. Line: {line}. Item Access Data: {item_access_data}')
                return False, lfdl
        
        return False, None
    
    index_utils.update_results_with_item_access_data(
        results, 
        item_access_data, 
        line
    )

    return True, None


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
    es_manager = es.ElasticSearchUsageWrapper(
        settings.ES_URL, 
        settings.ES_BASIC_AUTH, 
        settings.ES_API_KEY,
        settings.ES_VERIFY_CERTS
    )

    try:
        if es_manager.client.indices.exists(index=index_name):
            logging.info(f"Index {index_name} already exists.")
            return

        es_manager.create_index(index_name=index_name, mappings=mappings)
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
    es_manager = es.ElasticSearchUsageWrapper(
        settings.ES_URL, 
        settings.ES_BASIC_AUTH, 
        settings.ES_API_KEY,
        settings.ES_VERIFY_CERTS
    )

    try:
        if not es_manager.client.indices.exists(index=index_name):
            logging.info(f"Index {index_name} does not exist.")
            return

        es_manager.client.indices.delete(index=index_name)
        logging.info(f"Index {index_name} deleted successfully.")
    except Exception as e:
        logging.error(f"Failed to delete index {index_name}: {e}")


@celery_app.task(bind=True, name=_('Delete documents by key'), timelimit=-1)
def task_delete_documents_by_key(self, index_name, data, user_id=None, username=None):
    """
    Deletes documents from Elasticsearch based on the provided keys and values.

    Args:
        index_name (str): The name of the Elasticsearch index. Defaults to settings.ES_INDEX_NAME.
        data (dict): A dictionary where keys are field names and values are the corresponding values to match for deletion.
        user_id (int, optional): The ID of the user initiating the task. Defaults to None.
        username (str, optional): The username of the user initiating the task. Defaults to None.

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)
    es_manager = es.ElasticSearchUsageWrapper(
        settings.ES_URL, 
        settings.ES_BASIC_AUTH, 
        settings.ES_API_KEY,
        settings.ES_VERIFY_CERTS
    )

    try:
        es_manager.delete_documents_by_key(
            index_name=index_name, 
            data=data,
        )
        logging.info(f"Successfully deleted documents with data: {data} from index {index_name}.")
    except Exception as e:
        logging.error(f"Failed to delete documents with data {data} from index {index_name}: {e}")
