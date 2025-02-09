import logging
import os

from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from core.utils import date_utils
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


@celery_app.task(bind=True, name=_('Search for log files'))
def task_search_log_files(self, collections=[], from_date=None, until_date=None, days_to_go_back=None, user_id=None, username=None):
    """
    Task to search for log files in the directories defined in the CollectionLogDirectory model.

    Parameters:
        collections (list, optional): List of collection acronyms. Defaults to [].
        from_date (str, optional): The start date for log discovery in YYYY-MM-DD format. Defaults to None.
        until_date (str, optional): The end date for log discovery in YYYY-MM-DD format. Defaults to None.
        days_to_go_back (int, optional): The number of days to go back from today for log discovery. Defaults to None.
        user_id (int, optional): The ID of the user initiating the task. Defaults to None.
        username (str, optional): The username of the user initiating the task. Defaults to None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)
    
    for col in collections or Collection.acron3_list():
        collection = Collection.objects.get(acron3=col)

        col_configs_dirs = lmc_models.CollectionLogDirectory.objects.filter(collection__acron3=col, active=True)
        if len(col_configs_dirs) == 0:
            raise lmc_exceptions.UndefinedCollectionLogDirectoryError(_(f'Error. Please, add a CollectionLogDirectory for the collection {col}.'))

        supported_logfile_extensions = lmc_models.SupportedLogFile.objects.values_list('file_extension', flat=True)
        if len(supported_logfile_extensions) == 0:
            raise lmc_exceptions.UndefinedSupportedLogFile(_('Error. Please, add a SupportedLogFile for each of the supported log file formats.'))

        for cd in col_configs_dirs:
            for root, _sub_dirs, files in os.walk(cd.path):
                for name in files:
                    _name, extension = os.path.splitext(name)
                    if extension.lower() not in supported_logfile_extensions:
                        continue

                    visible_dates = _get_visible_dates(from_date, until_date, days_to_go_back)
                    logging.debug(f'Visible dates: {visible_dates}')

                    _add_log_file(user, collection, root, name, visible_dates)


def _get_visible_dates(from_date, until_date, days_to_go_back):
    from_date_str, until_date_str = date_utils.get_date_range_str(from_date, until_date, days_to_go_back)
    return date_utils.get_date_objs_from_date_range(from_date_str, until_date_str)


def _add_log_file(user, collection, root, name, visible_dates):
    file_path = os.path.join(root, name)
    file_ctime = date_utils.get_date_obj_from_timestamp(os.stat(file_path).st_ctime)

    logging.debug(f'Checking file {file_path} with ctime {file_ctime}.')
    if file_ctime in visible_dates:
        models.LogFile.create_or_update(
            user=user,
            collection=collection,
            path=file_path,
            stat_result=os.stat(file_path),
            hash=utils.hash_file(file_path),
        )


@celery_app.task(bind=True, name=_('Validate log files'), timelimit=-1)
def task_validate_log_files(self, collections=[], user_id=None, username=None):
    """
    Task to validate log files in the database.

    Parameters:
        collections (list, optional): List of collection acronyms. Defaults to [].
        user_id (int, optional): The ID of the user initiating the task. Defaults to None.
        username (str, optional): The username of the user initiating the task. Defaults to None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    for col in collections or Collection.acron3_list():
        for log_file in models.LogFile.objects.filter(status=choices.LOG_FILE_STATUS_CREATED, collection__acron3=col):
            logging.info(f'Validating log file {log_file.path} for collection {log_file.collection.acron3}.')
            
            val_results = utils.validate_file(path=log_file.path)
            if val_results.get('is_valid', {}).get('all', False):
                models.LogFileDate.create_or_update(
                    user=user,
                    log_file=log_file,
                    date=val_results.get('probably_date', ''),
                )
                log_file.status = choices.LOG_FILE_STATUS_QUEUED

            else:
                log_file.status = choices.LOG_FILE_STATUS_INVALIDATED

            logging.info(f'Log file {log_file.path} ({log_file.collection.acron3}) has status {log_file.status}.')
            log_file.save()


@celery_app.task(bind=True, name=_('Check missing log files'))
def task_check_missing_logs_for_date_range(self, collections=[], from_date=None, until_date=None, user_id=None, username=None):
    """
    Task to check for missing log files in the defined date range.

    Parameters:
        collections (list, optional): List of collection acronyms. Defaults to [].
        from_date (str, optional): The start date for log discovery in YYYY-MM-DD format. Defaults to None.
        until_date (str, optional): The end date for log discovery in YYYY-MM-DD format. Defaults to None.
        user_id (int, optional): The ID of the user initiating the task. Defaults to None.
        username (str, optional): The username of the user initiating the task. Defaults to None.

    Raises:
        exceptions.UndefinedCollectionFilesPerDayError: Raised when there are no expected log files for the collection.
        exceptions.MultipleFilesPerDayForTheSameDateError: Raised when there are multiple expected log files for the same date.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    for col in collections or Collection.acron3_list():
        collection = Collection.objects.get(acron3=col)
        for date in date_utils.get_date_objs_from_date_range(from_date, until_date):
            logging.info(f'Checking missings logs for collection {col} and date {date}')
            _check_missing_logs_for_date(user, collection, date)


def _check_missing_logs_for_date(user, collection, date):
    try:
        n_expected_files = lmc_models.CollectionLogFilesPerDay.get_number_of_expected_files_by_day(collection=collection.acron3, date=date)
    except lmc_exceptions.UndefinedCollectionFilesPerDayError:
        return
    except lmc_exceptions.MultipleFilesPerDayForTheSameDateError:
        return
        
    n_found_logs = models.LogFileDate.get_number_of_found_files_for_date(collection=collection.acron3, date=date)
    
    obj = models.CollectionLogFileDateCount.create_or_update(
        user=user,
        collection=collection,
        date=date,
        expected_log_files=n_expected_files,
        found_log_files=n_found_logs,
    )
    logging.info(f'Created CollectionLogFileDateCount object {obj}.')


@celery_app.task(bind=True, name=_('Generate log files count report'))
def task_log_files_count_status_report(self, collection, user_id=None, username=None):
    col = models.Collection.objects.get(acron3=collection)
    subject = _(f'Log Files Report for {col.main_name}')
    
    message = _(f'Dear collection {col.main_name},\n\nThis message is to inform you of the results of the Usage Log Validation service. Here are the results:\n\n')
    
    missing = models.CollectionLogFileDateCount.objects.filter(collection__acron3=collection, status=choices.COLLECTION_LOG_FILE_DATE_COUNT_MISSING_FILES)
    extra = models.CollectionLogFileDateCount.objects.filter(collection__acron3=collection, status=choices.COLLECTION_LOG_FILE_DATE_COUNT_EXTRA_FILES)
    ok = models.CollectionLogFileDateCount.objects.filter(collection__acron3=collection, status=choices.COLLECTION_LOG_FILE_DATE_COUNT_OK)

    if missing.count() > 0:
        message += _(f'There are {missing.count()} missing log files.\n')
    if extra.count() > 0:
        message += _(f'There are {extra.count()} extra log files.\n')
    if ok.count() > 0:
        message += _(f'There are {ok.count()} dates with correct log files.\n')

    if missing.count() > 0 or extra.count() > 0:
        message += _(f'\nPlease check the script that shares the logs.\n')
        
    message += _(f'\nYou can view the complete report results at {settings.WAGTAILADMIN_BASE_URL}/admin/snippets/log_manager/collectionlogfiledatecount/?collection={col.pk}>.')

    logging.info(f'Sending email to collection {col.main_name}. Subject: {subject}. Message: {message}')
    _send_message(subject, message, collection)


def _send_message(subject, message, collection):
    collection_emails = lmc_models.CollectionEmail.objects.filter(collection__acron3=collection, active=True).values_list('email', flat=True)
    if len(collection_emails) == 0:
        raise exceptions.UndefinedCollectionConfigError(_("Error. Please, add an E-mail Configuration for the collection."))
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=collection_emails
    )
