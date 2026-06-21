import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from log_manager import choices
from log_manager.models import LogFile
from metrics.models import DailyMetricJob


def create_or_update_daily_metric_job(collection, access_date, log_files):
    input_log_hashes = sorted(log_file.hash for log_file in log_files if log_file.hash)
    with transaction.atomic():
        job, _ = DailyMetricJob.objects.select_for_update().get_or_create(
            collection=collection,
            access_date=access_date,
        )

        if job.status == DailyMetricJob.STATUS_EXPORTED:
            if job.input_log_hashes != input_log_hashes:
                raise RuntimeError(
                    f"Daily metric job already exported for {collection.acron3} {access_date}. "
                    "Recompute requires deleting/recreating the affected day or period first."
                )
            LogFile.objects.filter(hash__in=input_log_hashes).update(
                status=choices.LOG_FILE_STATUS_PROCESSED,
                parse_heartbeat_at=None,
                updated=timezone.now(),
            )
            return job

        keep_payload = (
            job.status == DailyMetricJob.STATUS_ERROR
            and job.input_log_hashes == input_log_hashes
            and job.storage_path
            and job.payload_hash
        )

        job.input_log_hashes = input_log_hashes
        job.status = DailyMetricJob.STATUS_PENDING
        job.error_message = ""
        job.export_started_at = None
        job.exported_at = None
        if not keep_payload:
            job.storage_path = ""
            job.payload_hash = ""
            job.summary = {}
        job.save(
            update_fields=[
                "input_log_hashes",
                "status",
                "error_message",
                "export_started_at",
                "exported_at",
                "storage_path",
                "payload_hash",
                "summary",
                "updated",
            ]
        )
    return job


def acquire_daily_metric_job(job_id):
    with transaction.atomic():
        job = (
            DailyMetricJob.objects.select_for_update()
            .select_related("collection")
            .get(pk=job_id)
        )
        if job.status in {
            DailyMetricJob.STATUS_EXPORTING,
            DailyMetricJob.STATUS_EXPORTED,
        }:
            logging.info(
                "Daily metric job %s is already in final/active state.", job_id
            )
            return None

        job.status = DailyMetricJob.STATUS_EXPORTING
        job.attempts += 1
        job.error_message = ""
        job.export_started_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "attempts",
                "error_message",
                "export_started_at",
                "updated",
            ]
        )
    return job


def mark_daily_metric_job_failed(job, error_message):
    DailyMetricJob.objects.filter(pk=job.pk).update(
        status=DailyMetricJob.STATUS_ERROR,
        error_message=str(error_message),
        updated=timezone.now(),
    )
    LogFile.objects.filter(hash__in=job.input_log_hashes).update(
        status=choices.LOG_FILE_STATUS_ERROR,
        parse_heartbeat_at=None,
        updated=timezone.now(),
    )


def mark_daily_metric_job_exported(job):
    DailyMetricJob.objects.filter(pk=job.pk).update(
        status=DailyMetricJob.STATUS_EXPORTED,
        error_message="",
        exported_at=timezone.now(),
        updated=timezone.now(),
    )
    LogFile.objects.filter(hash__in=job.input_log_hashes).update(
        status=choices.LOG_FILE_STATUS_PROCESSED,
        parse_heartbeat_at=None,
        updated=timezone.now(),
    )


def release_stale_daily_metric_jobs(
    collections=None,
    from_date=None,
    until_date=None,
    stale_after_minutes=60,
):
    cutoff = timezone.now() - timedelta(minutes=stale_after_minutes)
    queryset = DailyMetricJob.objects.filter(
        status=DailyMetricJob.STATUS_EXPORTING,
        export_started_at__lt=cutoff,
    )
    if collections:
        queryset = queryset.filter(collection__acron3__in=collections)
    if from_date:
        queryset = queryset.filter(access_date__gte=from_date)
    if until_date:
        queryset = queryset.filter(access_date__lte=until_date)

    stale_jobs = list(queryset.only("pk", "input_log_hashes"))
    released = queryset.update(
        status=DailyMetricJob.STATUS_ERROR,
        error_message="Job marked for retry after stale exporting state.",
        updated=timezone.now(),
    )
    stale_hashes = {
        log_hash for job in stale_jobs for log_hash in (job.input_log_hashes or [])
    }
    if stale_hashes:
        LogFile.objects.filter(hash__in=stale_hashes).update(
            status=choices.LOG_FILE_STATUS_ERROR,
            parse_heartbeat_at=None,
            updated=timezone.now(),
        )
    return released
