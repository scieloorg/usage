import logging
import os

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from core.utils.utils import _get_user
from config import celery_app
from collection.models import Collection

from . import (
    exceptions, 
    choices, 
    models, 
    utils,
)


User = get_user_model()


@celery_app.task(bind=True, name=_('Discover Logs'))
def task_discover(self, collection_acron2, is_enabled=True, temporal_reference=None, from_date=None, user_id=None, username=None):
    """
    Task to discover logs.

    Parameters:
        collection_acron2 (str): Acronym of the collection.
        is_enabled (boolean)
        temporal_reference (str, optional): Temporal reference for filtering logs (e.g., 'yesterday', 'last week', 'last month').
        from_date (str, optional): Specific date from which logs should be considered (format: 'YYYY-MM-DD').
        user_id
        username

    Raises:
        UndefinedCollectionConfigError: If there is no configuration for the logs directory.
        InvalidTemporaReferenceError: If the provided temporal reference is invalid.
        InvalidDateFormatError: If the provided date format is invalid.
    
    Returns:
        None.
    """
    col = Collection.objects.get(acron2=collection_acron2)

    col_configs_dirs = models.CollectionConfig.filter_by_collection_and_config_type(
        collection_acron2=collection_acron2, 
        config_type=choices.COLLECTION_CONFIG_TYPE_DIRECTORY_LOGS,
        is_enabled=is_enabled,
    )

    if len(col_configs_dirs) == 0:
        raise exceptions.UndefinedCollectionConfigError('ERROR. Please, add a Collection Config for the Logs Directory.')

    app_config_log_file_formats = models.ApplicationConfig.get_field_values(config_type=choices.APPLICATION_CONFIG_TYPE_LOG_FILE_FORMAT)

    if len(app_config_log_file_formats) == 0:
        raise exceptions.UndefinedApplicationConfigError('ERROR. Please, add a Application Config for each of the supported log file formats.')

    if temporal_reference:
        try:
            obj_from_date = utils.temporal_reference_to_datetime(temporal_reference)
        except ValueError:
            raise exceptions.InvalidTemporaReferenceError('ERROR. The supported temporal references are: yesterday, last week, and last month.')
    elif from_date:
        try:
            obj_from_date = utils.formatted_text_to_datetime(from_date)
        except ValueError:
            raise exceptions.InvalidDateFormatError('ERROR. Please, use a valid date format (YYYY-MM-DD).')
    
    for cd in col_configs_dirs:
        for root, _, files in os.walk(cd.value):
            for name in files:
                _, extension = os.path.splitext(name)
                if extension.lower() not in app_config_log_file_formats:
                    continue

                file_path = os.path.join(root, name)
                file_ctime = utils.timestamp_to_datetime(os.stat(file_path).st_ctime)

                if not (temporal_reference or from_date) or file_ctime > obj_from_date:
                    task_create_log_file(col, file_path, user_id, username)


@celery_app.task(bind=True, name=_('Create Log File'))
def task_create_log_file(self, collection_acron2, path, user_id=None, username=None):
    """
    Task to create a log file record in the database.

    Args:
        collection_acron2 (str): Acronym of the collection.
        path (str): File path of the log file.
        user_id
        username

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)
    col = Collection.objects.get(acron2=collection_acron2)

    models.LogFile.create(
        user=user,
        collection=col,
        path=path,
        stat_result=os.stat(path),
        hash=utils.hash_file(path),
    )


@celery_app.task(bind=True, name=_('Validate Logs'), timelimit=-1)
def task_validate_logs(self, collection_acron2, user_id=None, username=None):
    for lf in models.LogFile.objects.filter(status=choices.LOG_FILE_STATUS_CREATED, collection__acron2=collection_acron2):
        logging.info(f'VALIDATING file {lf.path}')
        task_validate_log.apply_async(args=(lf.hash, user_id, username))


@celery_app.task(bind=True, name=_('Validate Log'), timelimit=-1)
def task_validate_log(self, log_file_hash, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    log_file = models.LogFile.get(hash=log_file_hash)

    val_results = utils.validate_file(path=log_file.path)

    if val_results.get('is_valid', {}).get('all', False):
        probably_date = val_results.get('probably_date', '')

        models.LogFileDate.create(
            user=user,
            log_file=log_file,
            date=probably_date,
        )
        log_file.status = choices.LOG_FILE_STATUS_QUEUED
    else:
        log_file.status = choices.LOG_FILE_STATUS_INVALIDATED

    log_file.save()

# TODO: 
#   Create a method that get all log files related to a collection and a period of time (start and end dates)
#   In detail:
#       Look at the LogFileDate table to get all the log_file,date pairs about that collection and dates
#       Look at the CollectionConfig table to get the number of valid log files expected per day
#       Generate a report informing the dates that there are missing files

@celery_app.task(bind=True, name=_('Parse Logs'), timelimit=-1)
def task_parse_logs(self, collection_acron2, user_id=None, username=None):
    """
    Parses log files associated with a given collection. 
    It retrieves necessary configuration details such as paths for Counter Robots and Geolocation MMDB files,
    checks their existence, and iterates through queued log files for parsing.

    Args:
        collection_acron2 (str): Acronym associated with the collection for which logs are being parsed.
        user_id
        username

    Raises:
        UndefinedCollectionConfigError: If necessary configuration details are missing for Counter Robots or Geolocation MMDB files.

    Returns:
        None.
    """
    ac_robots = models.ApplicationConfig.filter_by_config_type(choices.APPLICATION_CONFIG_TYPE_PATH_SUPPLY_ROBOTS)
    if not ac_robots or not os.path.exists(ac_robots.value) or not os.path.isfile(ac_robots.value):
        raise exceptions.UndefinedApplicationConfigError("ERROR. Please, add an Application Configuration for the Counter Robots text file path.")
    
    ac_mmdb = models.ApplicationConfig.filter_by_config_type(choices.APPLICATION_CONFIG_TYPE_PATH_SUPPLY_MMDB)
    if not ac_mmdb or not os.path.exists(ac_mmdb.value) or not os.path.isfile(ac_mmdb.value):
        raise exceptions.UndefinedApplicationConfigError("ERROR. Please, add an Application Configuration fot the Geolocation MMDB file path.")
    
    for lf in models.LogFile.objects.filter(status=choices.LOG_FILE_STATUS_QUEUED, collection__acron2=collection_acron2):
        logging.info(f'PARSING file {lf.path}')
        task_parse_log.apply_async(args=(
                lf.hash,
                ac_robots.value, 
                ac_mmdb.value,
                user_id,
                username,
            )
        )
        

@celery_app.task(bind=True, name=_('Parse Log'), timelimit=-1)
def task_parse_log(self, log_file_hash, path_robots, path_mmdb, user_id=None, username=None):
    """
    Parses a log file, extracts relevant information, and creates processed log records in the database.

    Args:
        log_file_hash (str): Hash representing the log file to be parsed.
        path_robots (str): File path to the Counter Robots text file.
        path_mmdb (str): File path to the Geolocation MMDB file.
        user_id
        username

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    log_file = models.LogFile.get(hash=log_file_hash)
    log_file.status = choices.LOG_FILE_STATUS_PARSING
    log_file.save()

    try:
        for row in utils.parse_file(
            path_mmdb,
            path_robots,
            log_file.path,
        ):
            '''
            hit.local_datetime
            hit.client_name
            hit.client_version
            hit.ip
            hit.geolocation
            hit.action
            '''
            st, bn, bv, ip, latlong, action = row

            # FIXME: It depends on the counter-access library to become more flexible.
            lat, long = latlong.split('\t')

            models.LogProcessedRow.create(
                user=user,
                log_file=log_file,
                server_time=st,
                browser_name=bn,
                browser_version=bv,
                ip=ip,
                latitude=float(lat),
                longitude=float(long),
                action_name=action,
            )
    except:
        log_file.status = choices.LOG_FILE_STATUS_QUEUED
    else:
        log_file.status = choices.LOG_FILE_STATUS_PROCESSED
        
    log_file.save()


@celery_app.task(bind=True, name=_('Download Supplies'))
def task_download_supplies(self, url_robots, url_mmdb, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    supplies_directory = models.ApplicationConfig.filter_by_config_type(choices.APPLICATION_CONFIG_TYPE_DIRECTORY_SUPPLIES).value

    robots_path, mmdb_path = utils.download_supplies(supplies_directory, url_robots, url_mmdb)

    models.ApplicationConfig.create(
        user,
        choices.APPLICATION_CONFIG_TYPE_PATH_SUPPLY_ROBOTS,
        robots_path,
    )

    models.ApplicationConfig.create(
        user,
        choices.APPLICATION_CONFIG_TYPE_PATH_SUPPLY_MMDB,
        mmdb_path,
    )
   