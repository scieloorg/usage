import logging

from django.db import DataError
from django.utils.translation import gettext as _

from config import celery_app
from core.collectors import opac as opac_collector
from core.utils import date_utils
from core.utils.request_utils import _get_user
from document.services import article as article_service
from source.models import Source

from document.tasks.common import _get_collection


def load_documents_from_opac(
    collection="scl",
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    page=1,
    force_update=True,
    user=None,
):
    from_date, until_date = date_utils.get_date_range_str(
        from_date,
        until_date,
        days_to_go_back,
    )
    logging.info(
        "Loading documents from OPAC. From: %s, Until: %s, Collection: %s",
        from_date,
        until_date,
        collection,
    )

    collection_obj = _get_collection(collection)
    if not collection_obj:
        logging.error("Collection not found: %s", collection)
        return False

    if not collection_obj.opac_url:
        logging.error(
            "OPAC endpoint not configured for collection: %s",
            collection_obj.acron3,
        )
        return False

    while True:
        response = opac_collector.fetch_counter_dict(
            from_date,
            until_date,
            page=page,
            endpoint=collection_obj.opac_url,
        )
        response_collection = response.get("collection")
        if response_collection and response_collection != collection_obj.acron3:
            logging.error(
                "OPAC response collection %s differs from requested collection %s",
                response_collection,
                collection_obj.acron3,
            )
            return False

        documents = response.get("documents") or {}

        for payload in documents.values():
            source = Source.find_journal_by_acronym(
                collection_obj,
                payload.get("journal_acronym"),
            )
            if not source:
                logging.info(
                    "Source not found for collection %s and acronym %s",
                    collection_obj.acron3,
                    payload.get("journal_acronym"),
                )
                continue

            try:
                article_service.upsert_article_document_from_opac(
                    payload,
                    collection=collection_obj,
                    source=source,
                    user=user,
                    force_update=force_update,
                )
            except DataError as exc:
                logging.error(
                    "Error saving Document from OPAC. "
                    "Collection: %s, Source: %s, PIDv2: %s. Error: %s",
                    collection_obj,
                    source.source_id,
                    payload.get("pid_v2"),
                    exc,
                )
                continue

        page += 1
        if page > int(response.get("pages", 0)):
            break

    return True


@celery_app.task(
    bind=True, name=_("[Metadata] Sync Documents (OPAC)"), timelimit=-1, queue="load"
)
def task_load_documents_from_opac(
    self,
    collection="scl",
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    page=1,
    force_update=True,
    user_id=None,
    username=None,
):
    user = _get_user(self.request, username=username, user_id=user_id)
    return load_documents_from_opac(
        collection=collection,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        page=page,
        force_update=force_update,
        user=user,
    )
