from django.conf import settings
from django.utils.translation import gettext as _

from config import celery_app
from core.utils.request_utils import _get_user
from metrics.services.daily_metric_exports import build_and_export_daily_metric_job


@celery_app.task(
    bind=True,
    name=_("[Metrics] Process Daily Job"),
    soft_time_limit=settings.CELERY_DAILY_JOB_SOFT_TIME_LIMIT_SECONDS,
    time_limit=settings.CELERY_DAILY_JOB_TIME_LIMIT_SECONDS,
)
def task_build_and_export_daily_metric_job(
    self,
    job_id,
    track_errors=False,
    user_id=None,
    username=None,
    robots_source=None,
):
    _get_user(self.request, username=username, user_id=user_id)
    return build_and_export_daily_metric_job(
        job_id=job_id,
        track_errors=track_errors,
        robots_source=robots_source,
    )
