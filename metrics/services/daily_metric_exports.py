import logging
import resource
from time import monotonic

from metrics.models import DailyMetricJob
from metrics.opensearch.client import OpenSearchUsageClient
from metrics.services.export import (
    daily_metric_payload_exists,
    export_daily_metric_payload,
)
from metrics.services.jobs import (
    acquire_daily_metric_job,
    mark_daily_metric_job_exported,
    mark_daily_metric_job_failed,
)
from metrics.services.parsing.job_payloads import build_daily_metric_job_payload
from metrics.services.resources import fetch_required_resources


def build_and_export_daily_metric_job(job_id, track_errors=False, robots_source=None):
    try:
        job = acquire_daily_metric_job(job_id)
    except DailyMetricJob.DoesNotExist:
        logging.error("Daily metric job %s does not exist.", job_id)
        return

    if not job:
        return

    try:
        _ensure_payload(
            job=job,
            track_errors=track_errors,
            robots_source=robots_source,
        )
        _export_payload(job=job)
    except Exception as exc:
        logging.error("Failed to process daily metric job %s: %s", job_id, exc)
        mark_daily_metric_job_failed(job, exc)
        return

    mark_daily_metric_job_exported(job)


def _ensure_payload(job, track_errors, robots_source):
    if job.payload_hash and daily_metric_payload_exists(job):
        logging.info(
            "Daily metric job %s is resuming from persisted payload %s.",
            job.pk,
            job.storage_path,
        )
        return

    robots_list, mmdb = fetch_required_resources(robot_source=robots_source)
    if not robots_list or not mmdb:
        raise RuntimeError("Required parsing resources are not available.")

    build_daily_metric_job_payload(
        job=job,
        robots_list=robots_list,
        mmdb=mmdb,
        track_errors=track_errors,
    )
    job.refresh_from_db()


def _export_payload(job):
    opensearch_started = monotonic()
    search_client = OpenSearchUsageClient()
    if not search_client.ping():
        raise RuntimeError("OpenSearch client is not available.")

    export_daily_metric_payload(
        search_client=search_client,
        job=job,
    )
    logging.info(
        "Daily metric job %s OpenSearch export completed in %.3f seconds; "
        "peak RSS %.1f MiB.",
        job.pk,
        monotonic() - opensearch_started,
        _peak_rss_mib(),
    )


def _peak_rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
