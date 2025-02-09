from django.contrib.auth import get_user_model

from config import celery_app

User = get_user_model()


@celery_app.task(bind=True, name='Get users count')
def get_users_count():
    """A pointless Celery task to demonstrate usage."""
    return User.objects.count()
