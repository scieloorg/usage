import logging
import os

from django.db.models import Count
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from core.utils.utils import _get_user
from config import celery_app
from collection.models import Collection
from log_manager_config import exceptions as lmc_exceptions, models as lmc_models

from . import (
    exceptions, 
    choices, 
    models, 
    utils,
)


User = get_user_model()


@celery_app.task(bind=True, name=_('Discover logs for a list of collections'))
def task_discover_logs_bulk(self, collections=[], days_to_go_back=None, from_date=None, user_id=None, username=None):
    for col in collections or Collection.acron2_list():
        logging.info(f'Discovering logs for collection {col}.')
        task_discover_logs.apply_async(args=(col, days_to_go_back, from_date, user_id, username))


@celery_app.task(bind=True, name=_('Discover logs for one collection'))
def task_discover_logs(self, collection_acron2, days_to_go_back=None, from_date=None, user_id=None, username=None):
    """
    Task to discover logs.

    Parameters:
        collection_acron2 (str): Acronym of the collection.
        days_to_go_back (int, optional): Number of days to count backward from the current date (e.g., 1 for yesterday, 7 for a week ago).
        from_date (str, optional): Specific date from which logs should be considered (format: 'YYYY-MM-DD').
        user_id
        username

    Raises:
        CollectionLogDirectoryError: If the CollectionLogDirectory is missing for the collection.
        InvalidDateFormatError: If the provided date format is invalid.
    
    Returns:
        None.
    """
    col_configs_dirs = lmc_models.CollectionLogDirectory.objects.filter(collection__acron2=collection_acron2, active=True)
    if len(col_configs_dirs) == 0:
        raise lmc_exceptions.UndefinedCollectionLogDirectoryError(_('ERROR. Please, add a CollectionLogDirectory for the collection.'))

    supported_logfile_extensions = lmc_models.SupportedLogFile.objects.values_list('file_extension', flat=True)
    if len(supported_logfile_extensions) == 0:
        raise lmc_exceptions.UndefinedSupportedLogFile(_('ERROR. Please, add a SupportedLogFile for each of the supported log file formats.'))

    if days_to_go_back:
        obj_from_date = utils.get_date_offset_from_today(days=days_to_go_back)
    elif from_date:
        try:
            obj_from_date = utils.formatted_text_to_date(from_date)
        except ValueError:
            raise exceptions.InvalidDateFormatError(_('ERROR. Please, use a valid date format (YYYY-MM-DD).'))
    
    for cd in col_configs_dirs:
        for root, _sub_dirs, files in os.walk(cd.path):
            for name in files:
                _name, extension = os.path.splitext(name)
                if extension.lower() not in supported_logfile_extensions:
                    continue

                file_path = os.path.join(root, name)
                file_ctime = utils.timestamp_to_date(os.stat(file_path).st_ctime)

                if not (days_to_go_back or from_date) or file_ctime > obj_from_date:
                    task_add_log_file.apply_async(args=(collection_acron2, file_path, user_id, username))


@celery_app.task(bind=True, name=_('Add log file'))
def task_add_log_file(self, collection_acron2, path, user_id=None, username=None):
    """
    Task to add a log file record in the database.

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


@celery_app.task(bind=True, name=_('Validate a list of logs'), timelimit=-1)
def task_validate_log_bulk(self, collection_acron2, user_id=None, username=None):
    for lf in models.LogFile.objects.filter(status=choices.LOG_FILE_STATUS_CREATED, collection__acron2=collection_acron2):
        logging.info(f'VALIDATING file {lf.path}')
        task_validate_log.apply_async(args=(lf.hash, user_id, username))


@celery_app.task(bind=True, name=_('Validate one log'), timelimit=-1)
def task_validate_log(self, log_file_hash, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    log_file = models.LogFile.get(hash=log_file_hash)

    val_results = utils.validate_file(path=log_file.path)

    if val_results.get('is_valid', {}).get('all', False):
        probably_date = val_results.get('probably_date', '')

        models.LogFileDate.create_or_update(
            user=user,
            log_file=log_file,
            date=probably_date,
        )
        log_file.status = choices.LOG_FILE_STATUS_QUEUED
    else:
        log_file.status = choices.LOG_FILE_STATUS_INVALIDATED

    log_file.save()


@celery_app.task(bind=True, name=_('Check missing logs for a date'))
def task_check_missing_logs_for_date(self, collection_acron2, date, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)
    collection = models.Collection.objects.get(acron2=collection_acron2)
    
    try:
        n_expected_files = lmc_models.CollectionLogFilesPerDay.get_number_of_expected_files_by_day(collection_acron2=collection_acron2, date=date)
    except lmc_exceptions.UndefinedCollectionFilesPerDayError:
        return
    except lmc_exceptions.MultipleFilesPerDayForTheSameDateError:
        return
        
    n_found_logs = models.LogFileDate.get_number_of_found_files_for_date(collection_acron2=collection_acron2, date=date)
        
    models.CollectionLogFileDateCount.create_or_update(
        user=user,
        collection=collection,
        date=date,
        expected_log_files=n_expected_files,
        found_log_files=n_found_logs,
    )


@celery_app.task(bind=True, name=_('Check missing logs for a date range'))
def task_check_missing_logs_for_date_range(self, start_date, end_date, collection_acron2_list=[], user_id=None, username=None):
    for acron2 in collection_acron2_list or Collection.acron2_list():
        for date in utils.date_range(start_date, end_date):
            logging.info(f'CHECKING missings logs for collection {acron2} and date {date}')
            task_check_missing_logs_for_date.apply_async(args=(acron2, date, user_id, username))


@celery_app.task(bind=True, name=_('Generate a log files countage report'))
def task_log_files_count_status_report(self, collection_acron2, user_id=None, username=None):
    col = models.Collection.objects.get(acron2=collection_acron2)
    subject = _(f'Log Files Report for {col.main_name}')
    
    message = _(f'Dear collection {col.main_name},\n\nThis message is to inform you of the results of the Usage Log Validation service.\n\nHere are the results:\n\n')
    
    missing = models.CollectionLogFileDateCount.objects.filter(status=choices.COLLECTION_LOG_FILE_DATE_COUNT_MISSING_FILES)
    extra = models.CollectionLogFileDateCount.objects.filter(status=choices.COLLECTION_LOG_FILE_DATE_COUNT_EXTRA_FILES)
    ok = models.CollectionLogFileDateCount.objects.filter(status=choices.COLLECTION_LOG_FILE_DATE_COUNT_OK)

    items = models.CollectionLogFileDateCount.objects.values('status', 'collection').annotate(total=Count('id'))

    for i in items:
        if i['status'] == choices.COLLECTION_LOG_FILE_DATE_COUNT_OK:
            message += _(f'There are {ok.count()} dates with correct log files.\n')
        
        if i['status'] == choices.COLLECTION_LOG_FILE_DATE_COUNT_MISSING_FILES:
            message += _(f'There are {missing.count()} missing log files.\n')
        
        if i['status'] == choices.COLLECTION_LOG_FILE_DATE_COUNT_EXTRA_FILES:
            message += _(f'There are {extra.count()} extra log files.\n')
        
    if any(i['status'] in [choices.COLLECTION_LOG_FILE_DATE_COUNT_EXTRA_FILES, choices.COLLECTION_LOG_FILE_DATE_COUNT_MISSING_FILES] for i in items):
        message += _(f'Please check the script that shares the logs.\n')
        
    message += _(f'You can view the complete report results at {settings.WAGTAILADMIN_BASE_URL}/admin/snippets/log_manager/collectionlogfiledatecount/?collection={col.pk}>.')
        
    task_send_message.apply_async(args=(subject, message, collection_acron2, user_id, username))


@celery_app.task(bind=True, name=_('Send a message'))
def task_send_message(self, subject, message, collection_acron2, user_id=None, username=None):
    collection_emails = lmc_models.CollectionEmail.objects.filter(collection_acron2=collection_acron2, active=True).values_list('email', flat=True)
    if len(collection_emails) == 0:
        raise exceptions.UndefinedCollectionConfigError(_("ERROR. Please, add an Email Configuration for the collection."))
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=collection_emails
    )
