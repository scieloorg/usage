import logging
import os

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from collection.models import Collection
from core.utils import date_utils
from log_manager import choices, file_errors, models, utils
from log_manager_config import models as lmc_models


def catalog_log_files_from_configured_directories(
    collections=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
):
    from_date_str, until_date_str = date_utils.get_date_range_str(
        from_date, until_date, days_to_go_back
    )
    visible_dates = date_utils.get_date_objs_from_date_range(
        from_date_str, until_date_str
    )
    supported_extensions = settings.SUPPORTED_LOGFILE_EXTENSIONS
    if not supported_extensions:
        logging.error("No supported log file extensions configured.")

    for collection_code in collections or Collection.acron3_list():
        collection = Collection.objects.get(acron3=collection_code)
        directories = lmc_models.CollectionLogDirectory.objects.filter(
            config__collection__acron3=collection_code,
            active=True,
        )
        if not directories:
            logging.error(
                "No CollectionLogDirectory found for collection %s.", collection_code
            )

        for directory in directories:
            _catalog_log_files_in_directory(
                collection=collection,
                directory_path=directory.path,
                visible_dates=visible_dates,
                supported_extensions=supported_extensions,
            )


def _catalog_log_files_in_directory(
    collection,
    directory_path,
    visible_dates,
    supported_extensions,
):
    retry_paths = _get_file_read_error_paths(collection, directory_path)

    for root, _sub_dirs, files in os.walk(directory_path):
        for name in files:
            _name, extension = os.path.splitext(name)
            if extension.lower() not in supported_extensions:
                continue

            file_path = os.path.join(root, name)
            try:
                file_stat = os.stat(file_path)
            except file_errors.FILE_READ_EXCEPTIONS as exc:
                logging.error(
                    "Error reading file metadata %s. Error: %s",
                    file_path,
                    exc,
                )
                _record_file_read_error(
                    collection=collection,
                    path=file_path,
                    stat_result={},
                    exc=exc,
                )
                continue

            file_ctime = date_utils.get_date_obj_from_timestamp(file_stat.st_ctime)

            logging.debug("Checking file %s with ctime %s.", file_path, file_ctime)
            if file_ctime not in visible_dates and file_path not in retry_paths:
                continue

            try:
                file_hash = utils.hash_file(file_path)
            except file_errors.FILE_READ_EXCEPTIONS as exc:
                logging.error(
                    "Error cataloging file %s. Error: %s",
                    file_path,
                    exc,
                )
                _record_file_read_error(
                    collection=collection,
                    path=file_path,
                    stat_result=file_stat,
                    exc=exc,
                )
                continue

            _catalog_readable_file(
                collection=collection,
                path=file_path,
                stat_result=file_stat,
                file_hash=file_hash,
            )


def _get_file_read_error_paths(collection, directory_path):
    return set(
        models.LogFile.objects.filter(
            collection=collection,
            path__startswith=directory_path,
            status=choices.LOG_FILE_STATUS_ERROR,
            validation__file_error__code=file_errors.FILE_READ_ERROR_CODE,
        ).values_list("path", flat=True)
    )


def _record_file_read_error(collection, path, stat_result, exc):
    error_hash = file_errors.build_catalog_error_hash(collection.acron3, path)
    with transaction.atomic():
        log_file = (
            models.LogFile.objects.select_for_update()
            .filter(
                collection=collection,
                path=path,
                status=choices.LOG_FILE_STATUS_ERROR,
                validation__file_error__code=file_errors.FILE_READ_ERROR_CODE,
            )
            .first()
        )
        if log_file is None:
            log_file = models.LogFile.create_or_update(
                collection=collection,
                path=path,
                stat_result=stat_result,
                hash=error_hash,
                status=choices.LOG_FILE_STATUS_ERROR,
            )

        log_file.path = path
        log_file.stat_result = stat_result
        log_file.status = choices.LOG_FILE_STATUS_ERROR
        log_file.date = None
        log_file.validation = {
            "file_error": file_errors.build_file_read_error(exc, stage="catalog")
        }
        log_file.summary = {}
        log_file.last_processed_line = 0
        log_file.parse_heartbeat_at = None
        log_file.save()


def _catalog_readable_file(collection, path, stat_result, file_hash):
    with transaction.atomic():
        path_error = (
            models.LogFile.objects.select_for_update()
            .filter(
                collection=collection,
                path=path,
                status=choices.LOG_FILE_STATUS_ERROR,
                validation__file_error__code=file_errors.FILE_READ_ERROR_CODE,
            )
            .first()
        )
        canonical = (
            models.LogFile.objects.select_for_update().filter(hash=file_hash).first()
        )

        if canonical and path_error and canonical.pk != path_error.pk:
            path_error.delete()
            canonical.updated = timezone.now()
            canonical.save(update_fields=["updated"])
            return canonical

        log_file = canonical or path_error
        if log_file:
            if file_errors.get_file_read_error(log_file.validation):
                _recover_readable_log_file(log_file, file_hash, path, stat_result)
            else:
                log_file.updated = timezone.now()
                log_file.save(update_fields=["updated"])
            return log_file

        return models.LogFile.create_or_update(
            collection=collection,
            path=path,
            stat_result=stat_result,
            hash=file_hash,
        )


def _recover_readable_log_file(log_file, file_hash, path, stat_result):
    log_file.hash = file_hash
    log_file.path = path
    log_file.stat_result = stat_result
    log_file.status = choices.LOG_FILE_STATUS_CREATED
    log_file.date = None
    log_file.validation = {}
    log_file.summary = {}
    log_file.last_processed_line = 0
    log_file.parse_heartbeat_at = None
    log_file.save()
