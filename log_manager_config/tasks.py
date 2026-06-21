from config import celery_app
from config.collections import (
    COLLECTION_SIZE_SAMPLE_MAP,
    LOG_MANAGER_SEED_DATA,
    get_collection_size,
)
from core.utils.request_utils import _get_user

from log_manager_config import models


@celery_app.task(bind=True, name="[Log Pipeline] Load Log Manager Settings (Seed)")
def task_load_log_manager_collection_settings(
    self, data=None, user_id=None, username=None
):
    user = _get_user(self.request, username=username, user_id=user_id)

    if not data:
        data = LOG_MANAGER_SEED_DATA

        for i in data:
            size = get_collection_size(i["acronym"])
            i["sample_size"] = COLLECTION_SIZE_SAMPLE_MAP.get(size, 1.0)
            i["buffer_size"] = 2048

    models.LogManagerCollectionConfig.load(data, user)
    models.CollectionLogDirectory.load(data, user)
    models.CollectionEmail.load(data, user)
