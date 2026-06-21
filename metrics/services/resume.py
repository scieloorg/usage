import logging

from django.utils import timezone

from config.collections import get_collection_parse_queue
from core.utils.date_utils import get_date_obj, get_date_range_str
from log_manager import choices
from log_manager.models import LogFile
from metrics.models import DailyMetricJob
from metrics.services.jobs import (
    create_or_update_daily_metric_job,
    release_stale_daily_metric_jobs,
)
from metrics.services.parsing.log_files import (
    is_stale_parsing_log,
    requeue_stale_parsing_log,
)


def resume_daily_metric_jobs(
    daily_metric_export_task,
    collections=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    stale_after_minutes=60,
    queue_name=None,
    user_id=None,
    username=None,
    robots_source=None,
):
    from_date, until_date = get_date_range_str(from_date, until_date, days_to_go_back)
    from_date_obj = get_date_obj(from_date)
    until_date_obj = get_date_obj(until_date)

    released_stale_jobs = release_stale_daily_metric_jobs(
        collections=collections,
        from_date=from_date_obj,
        until_date=until_date_obj,
        stale_after_minutes=stale_after_minutes,
    )
    resumed_jobs = _enqueue_resumable_daily_metric_jobs(
        daily_metric_export_task=daily_metric_export_task,
        collections=collections,
        from_date_obj=from_date_obj,
        until_date_obj=until_date_obj,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        robots_source=robots_source,
    )

    logging.info(
        "Resumed daily metric jobs for %s day(s); released %s stale job(s) at %s.",
        resumed_jobs,
        released_stale_jobs,
        timezone.now(),
    )
    return {
        "resumed_logs": resumed_jobs,
        "resumed_jobs": resumed_jobs,
        "released_stale_batches": released_stale_jobs,
        "released_stale_jobs": released_stale_jobs,
    }


def resume_stale_parsing_logs(
    log_parsing_task,
    collections=None,
    batch_size=5000,
    track_errors=False,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    stale_after_minutes=60,
    max_log_files=None,
    queue_name=None,
    user_id=None,
    username=None,
    robots_source=None,
):
    from_date, until_date = get_date_range_str(from_date, until_date, days_to_go_back)
    from_date_obj = get_date_obj(from_date)
    until_date_obj = get_date_obj(until_date)

    resumed_logs = _requeue_matching_stale_logs(
        collections=collections,
        from_date_obj=from_date_obj,
        until_date_obj=until_date_obj,
        stale_after_minutes=stale_after_minutes,
        max_log_files=max_log_files,
    )
    _enqueue_log_parsing_retry(
        log_parsing_task=log_parsing_task,
        collections=collections,
        batch_size=batch_size,
        track_errors=track_errors,
        from_date=from_date,
        until_date=until_date,
        max_log_files=max_log_files,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        robots_source=robots_source,
    )
    return {
        "stale_logs_marked_for_retry": resumed_logs,
        "parse_logs_enqueued": True,
    }


def _enqueue_resumable_daily_metric_jobs(
    daily_metric_export_task,
    collections,
    from_date_obj,
    until_date_obj,
    queue_name,
    user_id,
    username,
    robots_source,
):
    resumed_jobs = 0
    for job in _get_resumable_daily_metric_jobs(
        collections, from_date_obj, until_date_obj
    ):
        job = _refresh_job_inputs_from_retryable_logs(job)
        if job is None or job.status == DailyMetricJob.STATUS_EXPORTED:
            continue

        daily_metric_export_task.apply_async(
            args=(job.pk, False, user_id, username, robots_source),
            queue=queue_name or get_collection_parse_queue(job.collection.acron3),
        )
        resumed_jobs += 1
    return resumed_jobs


def _get_resumable_daily_metric_jobs(collections, from_date_obj, until_date_obj):
    queryset = (
        DailyMetricJob.objects.filter(
            status__in=[DailyMetricJob.STATUS_PENDING, DailyMetricJob.STATUS_ERROR],
            access_date__gte=from_date_obj,
            access_date__lte=until_date_obj,
        )
        .select_related("collection")
        .order_by("access_date", "collection__acron3")
    )
    if collections:
        queryset = queryset.filter(collection__acron3__in=collections)
    return queryset


def _refresh_job_inputs_from_retryable_logs(job):
    log_files = LogFile.for_collection_date(
        collection=job.collection,
        access_date=job.access_date,
        status_filters=[
            choices.LOG_FILE_STATUS_QUEUED,
            choices.LOG_FILE_STATUS_ERROR,
        ],
    )
    if log_files:
        return create_or_update_daily_metric_job(
            collection=job.collection,
            access_date=job.access_date,
            log_files=log_files,
        )

    if job.storage_path and job.payload_hash:
        return job

    logging.warning(
        "Skipping daily metric job %s: no queued/error logs or stored payload.",
        job.pk,
    )
    return None


def _requeue_matching_stale_logs(
    collections,
    from_date_obj,
    until_date_obj,
    stale_after_minutes,
    max_log_files,
):
    resumed_logs = 0
    for log_file in _get_parsing_logs(collections):
        probably_date = _extract_date_from_validation_dict(log_file.validation)
        if not _is_log_date_inside_range(probably_date, from_date_obj, until_date_obj):
            continue
        if not is_stale_parsing_log(log_file, stale_after_minutes=stale_after_minutes):
            continue

        requeue_stale_parsing_log(log_file)
        resumed_logs += 1
        if max_log_files and resumed_logs >= max_log_files:
            break
    return resumed_logs


def _get_parsing_logs(collections):
    queryset = (
        LogFile.objects.filter(status=choices.LOG_FILE_STATUS_PARSING)
        .select_related("collection")
        .order_by("validation__probably_date", "path", "hash")
    )
    if collections:
        queryset = queryset.filter(collection__acron3__in=collections)
    return queryset


def _is_log_date_inside_range(probably_date, from_date_obj, until_date_obj):
    return probably_date and from_date_obj <= probably_date <= until_date_obj


def _enqueue_log_parsing_retry(
    log_parsing_task,
    collections,
    batch_size,
    track_errors,
    from_date,
    until_date,
    max_log_files,
    queue_name,
    user_id,
    username,
    robots_source,
):
    apply_kwargs = {
        "kwargs": {
            "collections": collections,
            "include_logs_with_error": True,
            "batch_size": batch_size,
            "max_log_files": max_log_files,
            "auto_reexecute": False,
            "replace": False,
            "track_errors": track_errors,
            "from_date": from_date,
            "until_date": until_date,
            "days_to_go_back": None,
            "queue_name": queue_name,
            "user_id": user_id,
            "username": username,
            "robots_source": robots_source,
        }
    }
    if queue_name:
        apply_kwargs["queue"] = queue_name
    log_parsing_task.apply_async(**apply_kwargs)


def _extract_date_from_validation_dict(validation):
    try:
        date_str = validation.get("probably_date")
        return get_date_obj(date_str, "%Y-%m-%d")
    except Exception as e:
        logging.error(f"Failed to extract date from validation: {e}")
        return None
