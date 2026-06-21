from django.contrib.auth import get_user_model

from collection.models import Collection
from config import celery_app
from core.utils.request_utils import _get_user

User = get_user_model()


@celery_app.task(bind=True, name="[Collection] Load Collection Data")
def task_load_collections(self, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)
    Collection.load(user)
