# tasks.py
from datetime import datetime

from django.contrib.auth import get_user_model

from config import celery_app
from core.utils.utils import _get_user

from .models import UnexpectedEvent


User = get_user_model()


@celery_app.task(bind=True, name="cleanup_unexpected_events")
def delete_unexpected_events(self, exception_type, start_date=None, end_date=None, user_id=None, username=None):
    """
    Delete UnexpectedEvent records based on exception type and optional date range.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    if exception_type == '__all__':
        UnexpectedEvent.objects.all().delete()
        return

    filters = {'exception_type__icontains': exception_type}
    if start_date:
        start_date = datetime.fromisoformat(start_date)
        filters['created__gte'] = start_date
    if end_date:
        end_date = datetime.fromisoformat(end_date)
        filters['created__lte'] = end_date

    UnexpectedEvent.objects.filter(**filters).delete()
