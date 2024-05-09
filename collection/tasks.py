from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from core.utils.utils import _get_user
from collection.models import Collection
from config import celery_app

User = get_user_model()


@celery_app.task(bind=True)
def task_load_collections(self, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)
    Collection.load(user)
