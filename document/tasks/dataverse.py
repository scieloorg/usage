import logging

from django.db import DataError
from django.utils.translation import gettext as _

from config import celery_app
from core.collectors import dataverse as dataverse_collector
from core.utils import date_utils
from core.utils.request_utils import _get_user
from document.services import dataset as dataset_service

from document.tasks.common import _get_collection


def load_dataset_metadata_from_dataverse(
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    force_update=True,
    user=None,
):
    from_date, until_date = date_utils.get_date_range_str(
        from_date,
        until_date,
        days_to_go_back,
    )
    logging.info(
        "Loading dataset metadata into documents. From: %s, Until: %s",
        from_date,
        until_date,
    )

    collection_obj = _get_collection("data")
    if not collection_obj:
        logging.error("Collection not found: data")
        return False

    for payload in dataverse_collector.iter_dataset_metadata(from_date, until_date):
        if not payload.get("dataset_doi"):
            logging.error("Dataset DOI not found in record: %s", payload)
            continue

        try:
            dataset_service.upsert_dataset_document(
                payload,
                collection=collection_obj,
                user=user,
                force_update=force_update,
            )
        except DataError as exc:
            logging.error(
                "Error saving Dataset Document. Collection: %s, PID: %s. Error: %s",
                collection_obj,
                payload.get("dataset_doi"),
                exc,
            )
            continue

    return True


@celery_app.task(
    bind=True,
    name=_("[Metadata] Sync Documents (Dataverse)"),
    timelimit=-1,
    queue="load",
)
def task_load_dataset_metadata_into_documents(
    self,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    force_update=True,
    user_id=None,
    username=None,
):
    user = _get_user(self.request, username=username, user_id=user_id)
    return load_dataset_metadata_from_dataverse(
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        force_update=force_update,
        user=user,
    )
