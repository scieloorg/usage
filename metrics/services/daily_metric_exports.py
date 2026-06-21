import logging

from metrics.models import DailyMetricJob
from metrics.opensearch.client import OpenSearchUsageClient
from metrics.services.export import (
    export_daily_metric_payload,
    load_daily_metric_payload,
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
        payload = _load_or_build_payload(
            job=job,
            track_errors=track_errors,
            robots_source=robots_source,
        )
        _export_payload(job=job, payload=payload)
    except Exception as exc:
        logging.error("Failed to process daily metric job %s: %s", job_id, exc)
        mark_daily_metric_job_failed(job, exc)
        return

    mark_daily_metric_job_exported(job)


def _load_or_build_payload(job, track_errors, robots_source):
    payload = load_daily_metric_payload(job)
    if payload is not None and job.payload_hash:
        return payload

    robots_list, mmdb = fetch_required_resources(robot_source=robots_source)
    if not robots_list or not mmdb:
        raise RuntimeError("Required parsing resources are not available.")

    payload = build_daily_metric_job_payload(
        job=job,
        robots_list=robots_list,
        mmdb=mmdb,
        track_errors=track_errors,
    )
    job.refresh_from_db()
    return payload


def _export_payload(job, payload):
    search_client = OpenSearchUsageClient()
    if not search_client.ping():
        raise RuntimeError("OpenSearch client is not available.")

    export_daily_metric_payload(
        search_client=search_client,
        job=job,
        payload=payload,
    )
