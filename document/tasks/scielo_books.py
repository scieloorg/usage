import logging

from django.conf import settings
from django.utils.translation import gettext as _

from collection.models import Collection
from config import celery_app
from core.collectors import scielo_books as scielo_books_collector
from core.utils.request_utils import _get_user
from document.models import Document
from document.services import book as document_books_service
from source.models import Source
from source.services import book as source_books_service

from document.tasks.common import get_latest_scielo_books_last_seq


def load_documents_from_scielo_books(
    collection="books",
    db_name=None,
    since=0,
    limit=None,
    force_update=True,
    headers=None,
    base_url=None,
    user=None,
):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    limit = limit or settings.SCIELO_BOOKS_LIMIT
    collection_obj = Collection.objects.get(acron3=collection)
    monograph_cache = {}

    logging.info(
        "Loading documents from SciELO Books. Collection: %s, DB: %s, Since: %s, Limit: %s",
        collection,
        db_name,
        since,
        limit,
    )

    for item in scielo_books_collector.iter_change_documents(
        base_url=base_url,
        db_name=db_name,
        since=since,
        limit=limit,
        headers=headers,
    ):
        change = item["change"]
        raw_id = change.get("id")

        if item["deleted"]:
            delete_source = Document.book_exists_for_raw_id(
                collection_obj,
                raw_id,
            )
            Document.delete_documents_by_raw_id(collection_obj, raw_id)
            if delete_source:
                Source.delete_book_source_by_id(collection_obj, raw_id)
            continue

        payload = item["payload"] or {}
        source_url = item.get("source_url")
        last_seq = change.get("seq")

        if payload.get("TYPE") == "Monograph":
            source = source_books_service.upsert_monograph_source(
                payload,
                collection=collection_obj,
                user=user,
                force_update=force_update,
                source_url=source_url,
                last_seq=last_seq,
            )
            document_books_service.upsert_monograph_document(
                payload,
                collection=collection_obj,
                source=source,
                user=user,
                force_update=force_update,
                source_url=source_url,
                last_seq=last_seq,
            )
            monograph_cache[str(payload.get("id"))] = payload
            continue

        if payload.get("TYPE") != "Part":
            continue

        monograph_payload = _get_monograph_payload(
            payload,
            monograph_cache=monograph_cache,
            base_url=base_url,
            db_name=db_name,
            headers=headers,
        )
        if not monograph_payload:
            logging.warning(
                "Skipping part %s because monograph %s could not be loaded.",
                payload.get("id"),
                payload.get("monograph"),
            )
            continue

        source = source_books_service.upsert_monograph_source(
            monograph_payload,
            collection=collection_obj,
            user=user,
            force_update=force_update,
            source_url=None,
            last_seq=last_seq,
        )
        parent_document = document_books_service.upsert_monograph_document(
            monograph_payload,
            collection=collection_obj,
            source=source,
            user=user,
            force_update=force_update,
            source_url=None,
            last_seq=last_seq,
        )
        enriched_payload = document_books_service.enrich_part_payload(
            payload,
            monograph_payload,
        )
        document_books_service.upsert_part_document(
            enriched_payload,
            collection=collection_obj,
            source=source,
            parent_document=parent_document,
            user=user,
            force_update=force_update,
            source_url=source_url,
            last_seq=last_seq,
        )

    return True


def sync_documents_from_scielo_books(
    collection="books",
    db_name=None,
    limit=None,
    force_update=True,
    headers=None,
    base_url=None,
    user=None,
):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    limit = limit or settings.SCIELO_BOOKS_LIMIT
    since = get_latest_scielo_books_last_seq(collection=collection)
    logging.info(
        "Syncing documents from SciELO Books incrementally. Collection: %s, Since: %s, Limit: %s",
        collection,
        since,
        limit,
    )
    return load_documents_from_scielo_books(
        collection=collection,
        db_name=db_name,
        since=since,
        limit=limit,
        force_update=force_update,
        headers=headers,
        base_url=base_url,
        user=user,
    )


@celery_app.task(
    bind=True, name=_("[Metadata] Sync Documents (SciELO Books - Manual)"), queue="load"
)
def task_load_documents_from_scielo_books(
    self,
    collection="books",
    db_name=None,
    since=0,
    limit=None,
    force_update=True,
    headers=None,
    base_url=None,
    user_id=None,
    username=None,
):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    limit = limit or settings.SCIELO_BOOKS_LIMIT
    user = _get_user(self.request, username=username, user_id=user_id)
    return load_documents_from_scielo_books(
        collection=collection,
        db_name=db_name,
        since=since,
        limit=limit,
        force_update=force_update,
        headers=headers,
        base_url=base_url,
        user=user,
    )


@celery_app.task(
    bind=True,
    name=_("[Metadata] Sync Documents (SciELO Books - Incremental)"),
    queue="load",
)
def task_sync_documents_from_scielo_books(
    self,
    collection="books",
    db_name=None,
    limit=None,
    force_update=True,
    headers=None,
    base_url=None,
    user_id=None,
    username=None,
):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    limit = limit or settings.SCIELO_BOOKS_LIMIT
    user = _get_user(self.request, username=username, user_id=user_id)
    return sync_documents_from_scielo_books(
        collection=collection,
        db_name=db_name,
        limit=limit,
        force_update=force_update,
        headers=headers,
        base_url=base_url,
        user=user,
    )


def _get_monograph_payload(
    payload, monograph_cache, base_url=None, db_name=None, headers=None
):
    monograph_id = payload.get("monograph")
    if not monograph_id:
        return None

    monograph_key = str(monograph_id)
    if monograph_key in monograph_cache:
        return monograph_cache[monograph_key]

    try:
        monograph_payload, _ = scielo_books_collector.fetch_document(
            doc_id=monograph_id,
            base_url=base_url,
            db_name=db_name or settings.SCIELO_BOOKS_DB_NAME,
            headers=headers,
        )
    except Exception as exc:
        logging.warning(
            "Failed to fetch monograph %s for part %s: %s",
            monograph_id,
            payload.get("id"),
            exc,
        )
        return None

    monograph_cache[monograph_key] = monograph_payload
    return monograph_payload
