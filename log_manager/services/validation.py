import logging

from collection.models import Collection
from core.utils import date_utils
from log_manager import choices, models, utils
from log_manager_config import models as lmc_models

LOGFILE_STAT_RESULT_CTIME_INDEX = 9


def get_validation_candidate_hashes_by_collection(
    collections=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    ignore_date=False,
    revalidate=False,
    status_list=None,
):
    collection_codes = collections or Collection.acron3_list()
    logging.info("Validating log files for collections: %s.", collection_codes)

    visible_dates = _get_validation_visible_dates(
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        ignore_date=ignore_date,
    )
    if visible_dates is None:
        return None

    status_filter = _get_validation_status_filter(
        revalidate=revalidate,
        status_list=status_list,
    )

    log_hashes_by_collection = {}
    for collection_code in collection_codes:
        log_hashes_by_collection[collection_code] = _get_validation_candidate_hashes(
            collection_code=collection_code,
            status_filter=status_filter,
            visible_dates=visible_dates,
            ignore_date=ignore_date,
        )

    return log_hashes_by_collection


def _get_validation_visible_dates(
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    ignore_date=False,
):
    from_date_str, until_date_str = date_utils.get_date_range_str(
        from_date,
        until_date,
        days_to_go_back,
    )
    visible_dates = date_utils.get_date_objs_from_date_range(
        from_date_str,
        until_date_str,
    )

    if ignore_date:
        return visible_dates

    if not visible_dates:
        logging.warning("No visible dates found for log validation.")
        return None

    logging.info("Interval: %s to %s.", visible_dates[0], visible_dates[-1])
    return visible_dates


def _get_validation_status_filter(revalidate=False, status_list=None):
    status_filter = [choices.LOG_FILE_STATUS_CREATED]

    if revalidate:
        status_filter += status_list or [
            choices.LOG_FILE_STATUS_QUEUED,
            choices.LOG_FILE_STATUS_INVALIDATED,
            choices.LOG_FILE_STATUS_ERROR,
        ]

    return status_filter


def _get_validation_candidate_hashes(
    collection_code,
    status_filter,
    visible_dates,
    ignore_date=False,
):
    log_hashes = []
    log_files = models.LogFile.objects.filter(
        status__in=status_filter,
        collection__acron3=collection_code,
    )

    for log_file in log_files:
        if not ignore_date and not _log_file_ctime_is_in_date_range(
            log_file,
            visible_dates,
        ):
            continue

        log_hashes.append(log_file.hash)

    return log_hashes


def _log_file_ctime_is_in_date_range(log_file, visible_dates):
    file_ctime = date_utils.get_date_obj_from_timestamp(
        log_file.stat_result[LOGFILE_STAT_RESULT_CTIME_INDEX]
    )
    return file_ctime in visible_dates


def validate_log_file_and_update_status(log_file_hash):
    log_file = models.LogFile.objects.get(hash=log_file_hash)
    collection = log_file.collection.acron3
    buffer_size, sample_size = _get_collection_validation_settings(collection)

    logging.info("Validating log file %s.", log_file.path)
    validation_result = utils.validate_file(
        path=log_file.path,
        buffer_size=buffer_size,
        sample_size=sample_size,
    )
    _normalize_validation_result_for_storage(validation_result)

    _update_log_file_with_validation_result(
        log_file=log_file,
        validation_result=validation_result,
        buffer_size=buffer_size,
        sample_size=sample_size,
    )


def _get_collection_validation_settings(
    collection, default_buffer_size=2048, default_sample_size=0.1
):
    col_configs = lmc_models.LogManagerCollectionConfig.objects.filter(
        collection__acron3=collection
    ).first()

    if not col_configs:
        logging.warning(
            "No LogManagerCollectionConfig found for collection %s. Using default values.",
            collection,
        )
        return default_buffer_size, default_sample_size

    return col_configs.buffer_size, col_configs.sample_size


def _normalize_validation_result_for_storage(validation_result):
    if "datetimes" in validation_result.get("content", {}).get("summary", {}):
        del validation_result["content"]["summary"]["datetimes"]

    if "probably_date" not in validation_result:
        return

    probably_date = validation_result["probably_date"]
    if isinstance(probably_date, dict):
        logging.error("Error determining probably_date: %s", probably_date.get("error"))
        validation_result["probably_date"] = None
        return

    try:
        validation_result["probably_date"] = date_utils.get_date_str(probably_date)
    except (ValueError, AttributeError) as exc:
        logging.error("Error serializing probably_date: %s", exc)
        validation_result["probably_date"] = None


def _update_log_file_with_validation_result(
    log_file,
    validation_result,
    buffer_size,
    sample_size,
):
    log_file.validation = validation_result
    log_file.validation.update({"buffer_size": buffer_size, "sample_size": sample_size})

    if validation_result.get("is_valid", {}).get("all", False):
        log_file.date = validation_result.get("probably_date") or None
        log_file.status = choices.LOG_FILE_STATUS_QUEUED
    else:
        log_file.status = choices.LOG_FILE_STATUS_INVALIDATED

    logging.info(
        "Log file %s (%s) has status %s.",
        log_file.path,
        log_file.collection.acron3,
        log_file.status,
    )
    log_file.save()
