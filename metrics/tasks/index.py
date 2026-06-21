import logging

from django.utils.translation import gettext as _

from config import celery_app
from core.utils.request_utils import _get_user
from metrics.opensearch.client import OpenSearchUsageClient


@celery_app.task(bind=True, name=_("[Metrics] Create Index"), timelimit=-1)
def task_create_index(self, index_name, mappings=None, user_id=None, username=None):
    _get_user(self.request, username=username, user_id=user_id)
    search_client = OpenSearchUsageClient()

    try:
        if search_client.client.indices.exists(index=index_name):
            logging.info("Index %s already exists.", index_name)
            return

        search_client.create_index(index_name=index_name, mappings=mappings or {})
        logging.info("Index %s created successfully.", index_name)
    except Exception as exc:
        logging.error("Failed to create index %s: %s", index_name, exc)


@celery_app.task(bind=True, name=_("[Metrics] Delete Documents by Key"), timelimit=-1)
def task_delete_documents_by_key(self, index_name, data, user_id=None, username=None):
    _get_user(self.request, username=username, user_id=user_id)
    search_client = OpenSearchUsageClient()

    try:
        search_client.delete_documents_by_key(index_name=index_name, data=data)
        logging.info(
            "Successfully deleted documents with data: %s from index %s.",
            data,
            index_name,
        )
    except Exception as exc:
        logging.error(
            "Failed to delete documents with data %s from index %s: %s",
            data,
            index_name,
            exc,
        )
