from django.utils.translation import gettext as _

from config import celery_app
from metrics.services import log_parsing_jobs
from metrics.tasks.daily_metric_exports import task_build_and_export_daily_metric_job


@celery_app.task(
    bind=True, name=_("[Log Pipeline] 3. Parse Logs (Manual)"), timelimit=-1
)
def task_enqueue_log_parsing_jobs(
    self,
    collections=None,
    include_logs_with_error=True,
    batch_size=5000,
    max_log_files=None,
    auto_reexecute=False,
    replace=False,
    track_errors=False,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    queue_name=None,
    user_id=None,
    username=None,
    skip_log_hashes=None,
    robots_source=None,
):
    if replace:
        raise ValueError(
            "replace=True is not supported. Recompute requires deleting/recreating "
            "the affected day or period first."
        )

    return log_parsing_jobs.enqueue_log_parsing_jobs(
        daily_metric_export_task=task_build_and_export_daily_metric_job,
        wait_log_parsing_wave_task=task_wait_log_parsing_wave,
        collections=collections,
        include_logs_with_error=include_logs_with_error,
        batch_size=batch_size,
        max_log_files=max_log_files,
        auto_reexecute=auto_reexecute,
        replace=replace,
        track_errors=track_errors,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        skip_log_hashes=skip_log_hashes,
        robots_source=robots_source,
    )


@celery_app.task(bind=True, name=_("[Metrics] Wait Parse Logs Wave"), timelimit=-1)
def task_wait_log_parsing_wave(
    self,
    wave_job_ids=None,
    collections=None,
    include_logs_with_error=True,
    batch_size=5000,
    max_log_files=None,
    auto_reexecute=False,
    replace=False,
    track_errors=False,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    queue_name=None,
    user_id=None,
    username=None,
    skip_log_hashes=None,
    poll_interval_seconds=log_parsing_jobs.AUTO_REEXECUTE_POLL_INTERVAL_SECONDS,
    robots_source=None,
    wave_log_hashes=None,
):
    return log_parsing_jobs.wait_log_parsing_wave(
        log_parsing_task=task_enqueue_log_parsing_jobs,
        wait_log_parsing_wave_task=task_wait_log_parsing_wave,
        wave_job_ids=wave_job_ids,
        collections=collections,
        include_logs_with_error=include_logs_with_error,
        batch_size=batch_size,
        max_log_files=max_log_files,
        auto_reexecute=auto_reexecute,
        replace=replace,
        track_errors=track_errors,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        skip_log_hashes=skip_log_hashes,
        poll_interval_seconds=poll_interval_seconds,
        robots_source=robots_source,
        wave_log_hashes=wave_log_hashes,
    )
