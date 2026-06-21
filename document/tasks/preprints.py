import logging

from django.db import DataError
from django.utils.translation import gettext as _

from config import celery_app
from core.collectors import preprints as preprints_collector
from core.utils import date_utils
from core.utils.request_utils import _get_user
from document.services import preprint as preprint_service

from document.tasks.common import _get_collection


def load_preprints_from_preprints_api(
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
        "Loading preprints into documents. From: %s, Until: %s",
        from_date,
        until_date,
    )

    collection_obj = _get_collection("preprints")
    if not collection_obj:
        logging.error("Collection not found: preprints")
        return False

    for record in preprints_collector.iter_records(from_date, until_date):
        payload = preprints_collector.extract_record_data(record)

        if not payload.get("pid_generic"):
            logging.error("Preprint ID not found in record: %s", record)
            continue

        try:
            preprint_service.upsert_preprint_document(
                payload,
                collection=collection_obj,
                user=user,
                force_update=force_update,
            )
        except DataError as exc:
            logging.error(
                "Error saving Preprint Document. Collection: %s, PID: %s. Error: %s",
                collection_obj,
                payload.get("pid_generic"),
                exc,
            )
            continue

    return True


@celery_app.task(
    bind=True,
    name=_("[Metadata] Sync Documents (Preprints)"),
    timelimit=-1,
    queue="load",
)
def task_load_preprints_into_documents(
    self,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    force_update=True,
    user_id=None,
    username=None,
):
    user = _get_user(self.request, username=username, user_id=user_id)
    return load_preprints_from_preprints_api(
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        force_update=force_update,
        user=user,
    )
