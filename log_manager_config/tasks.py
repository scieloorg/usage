import logging

from collection.models import Collection
from config import celery_app
from config.collections import COLLECTION_OPAC_URL_MAP, LOG_MANAGER_SEED_DATA
from core.utils.request_utils import _get_user
from log_manager_config import models

DEFAULT_VALIDATION_SAMPLE_SIZE = 1.0
DEFAULT_VALIDATION_BUFFER_SIZE = 2048


@celery_app.task(bind=True, name="[Log Pipeline] Load Log Manager Settings (Seed)")
def task_load_log_manager_collection_settings(
    self, data=None, user_id=None, username=None
):
    user = _get_user(self.request, username=username, user_id=user_id)

    using_default_data = not data
    data = [dict(item) for item in (data or LOG_MANAGER_SEED_DATA)]

    if using_default_data:
        for acronym, opac_url in COLLECTION_OPAC_URL_MAP.items():
            try:
                collection = Collection.objects.get(acron3=acronym)
            except Collection.DoesNotExist:
                logging.warning("Collection %s not found.", acronym)
                continue

            collection.opac_url = opac_url
            collection.updated_by = user
            collection.save(update_fields=["opac_url", "updated_by", "updated"])

    for item in data:
        item.setdefault("sample_size", DEFAULT_VALIDATION_SAMPLE_SIZE)
        item.setdefault("buffer_size", DEFAULT_VALIDATION_BUFFER_SIZE)

    models.LogManagerCollectionConfig.load(data, user)
    models.CollectionLogDirectory.load(data, user)
    models.CollectionEmail.load(data, user)
