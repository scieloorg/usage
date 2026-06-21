import logging

from django.db import DataError
from django.utils.translation import gettext as _

from config import celery_app
from core.collectors import articlemeta as articlemeta_collector
from core.utils import date_utils
from core.utils.request_utils import _get_user
from document.services import article as article_service
from source.models import Source

from document.tasks.common import _get_collection


def load_documents_from_article_meta(
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    collection=None,
    issn=None,
    force_update=True,
    user=None,
):
    from_date, until_date = date_utils.get_date_range_str(
        from_date,
        until_date,
        days_to_go_back,
    )
    logging.info(
        "Loading documents from Article Meta. From: %s, Until: %s, Collection: %s, ISSN: %s",
        from_date,
        until_date,
        collection,
        issn,
    )

    offset = 0
    limit = 1000
    while True:
        response = articlemeta_collector.fetch_article_counter_dict(
            from_date,
            until_date,
            offset=offset,
            limit=limit,
            collection=collection,
            issn=issn,
        )
        objects = response.get("objects") or []
        if not objects:
            break

        for payload in objects:
            collection_obj = _get_collection(payload.get("collection") or collection)
            if not collection_obj:
                logging.info(
                    "Collection not found for payload %s",
                    payload.get("code"),
                )
                continue

            source = Source.find_journal_by_issns(
                collection_obj,
                payload.get("code_title"),
            )
            if not source:
                logging.info(
                    "Source not found for collection %s and ISSNs %s",
                    collection_obj.acron3,
                    payload.get("code_title"),
                )
                continue

            try:
                article_service.upsert_article_document_from_articlemeta(
                    payload,
                    collection=collection_obj,
                    source=source,
                    user=user,
                    force_update=force_update,
                )
            except DataError as exc:
                logging.error(
                    "Error saving Document from Article Meta. "
                    "Collection: %s, Source: %s, PIDv2: %s. Error: %s",
                    collection_obj,
                    source.source_id,
                    payload.get("code"),
                    exc,
                )
                continue

        offset += limit

    return True


@celery_app.task(
    bind=True,
    name=_("[Metadata] Sync Documents (Article Meta)"),
    timelimit=-1,
    queue="load",
)
def task_load_documents_from_article_meta(
    self,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    collection=None,
    issn=None,
    force_update=True,
    user_id=None,
    username=None,
):
    user = _get_user(self.request, username=username, user_id=user_id)
    return load_documents_from_article_meta(
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        collection=collection,
        issn=issn,
        force_update=force_update,
        user=user,
    )
