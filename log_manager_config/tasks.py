import logging

from config import celery_app
from config.collections import (
    COLLECTION_OPAC_URL_MAP,
    COLLECTION_SIZE_SAMPLE_MAP,
    LOG_MANAGER_SEED_DATA,
    get_collection_size,
)
from collection.models import Collection
from core.utils.request_utils import _get_user

from log_manager_config import models


@celery_app.task(bind=True, name="[Log Pipeline] Load Log Manager Settings (Seed)")
def task_load_log_manager_collection_settings(
    self, data=None, user_id=None, username=None
):
    user = _get_user(self.request, username=username, user_id=user_id)

    if not data:
        data = LOG_MANAGER_SEED_DATA

        for acronym, opac_url in COLLECTION_OPAC_URL_MAP.items():
            try:
                collection = Collection.objects.get(acron3=acronym)
            except Collection.DoesNotExist:
                logging.warning("Collection %s not found.", acronym)
                continue

            collection.opac_url = opac_url
            collection.updated_by = user
            collection.save(update_fields=["opac_url", "updated_by", "updated"])

        for i in data:
            size = get_collection_size(i["acronym"])
            i["sample_size"] = COLLECTION_SIZE_SAMPLE_MAP.get(size, 1.0)
            i["buffer_size"] = 2048

    models.LogManagerCollectionConfig.load(data, user)
    models.CollectionLogDirectory.load(data, user)
    models.CollectionEmail.load(data, user)
