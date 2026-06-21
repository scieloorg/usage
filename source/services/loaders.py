import logging

from django.conf import settings

from collection.models import Collection
from core.collectors import articlemeta as articlemeta_collector
from core.collectors import scielo_books as scielo_books_collector
from source.models import Source
from source.services import book as books_service
from source.services import journal as journal_service


def load_sources_from_article_meta(
    collections=None,
    force_update=True,
    user=None,
    mode="thrift",
):
    collection_codes = collections or Collection.acron3_list()

    for collection_code in collection_codes:
        logging.info(
            "Loading sources from Article Meta. Collection: %s, Mode: %s",
            collection_code,
            mode,
        )

        for journal in articlemeta_collector.iter_journals(
            collection=collection_code,
            mode=mode,
        ):
            collection = Collection.objects.filter(
                acron3=journal.collection_acronym
            ).first()
            if not collection:
                logging.error(
                    "Collection %s does not exist",
                    journal.collection_acronym,
                )
                continue

            source = journal_service.upsert_journal_source(
                journal,
                collection=collection,
                user=user,
                force_update=force_update,
                load_mode=mode,
            )
            logging.info(
                "Source %s upserted for collection %s",
                source.source_id if source else None,
                collection.acron3,
            )

    return True


def load_sources_from_scielo_books(
    collection="books",
    db_name=settings.SCIELO_BOOKS_DB_NAME,
    since=0,
    limit=settings.SCIELO_BOOKS_LIMIT,
    force_update=True,
    headers=None,
    base_url=None,
    user=None,
):
    collection_obj = Collection.objects.get(acron3=collection)

    logging.info(
        "Loading sources from SciELO Books. Collection: %s, DB: %s, Since: %s, Limit: %s",
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

        if item["deleted"]:
            Source.delete_book_source_by_id(collection_obj, change.get("id"))
            continue

        payload = item["payload"] or {}
        if payload.get("TYPE") != "Monograph":
            continue

        books_service.upsert_monograph_source(
            payload,
            collection=collection_obj,
            user=user,
            force_update=force_update,
            source_url=item.get("source_url"),
            last_seq=change.get("seq"),
        )

    return True
