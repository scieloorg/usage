from django.utils.translation import gettext as _

from config import celery_app
from core.utils.request_utils import _get_user
from metrics.services import resume
from metrics.tasks.daily_metric_exports import task_build_and_export_daily_metric_job
from metrics.tasks.log_parsing import task_enqueue_log_parsing_jobs


@celery_app.task(bind=True, name=_("[Metrics] Resume Log Exports"), timelimit=-1)
def task_resume_log_exports(
    self,
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
    _get_user(self.request, username=username, user_id=user_id)
    return resume.resume_daily_metric_jobs(
        daily_metric_export_task=task_build_and_export_daily_metric_job,
        collections=collections,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        stale_after_minutes=stale_after_minutes,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        robots_source=robots_source,
    )


@celery_app.task(bind=True, name=_("[Metrics] Resume Stale Parsing Logs"), timelimit=-1)
def task_resume_stale_parsing_logs(
    self,
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
    return resume.resume_stale_parsing_logs(
        log_parsing_task=task_enqueue_log_parsing_jobs,
        collections=collections,
        batch_size=batch_size,
        track_errors=track_errors,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        stale_after_minutes=stale_after_minutes,
        max_log_files=max_log_files,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        robots_source=robots_source,
    )
