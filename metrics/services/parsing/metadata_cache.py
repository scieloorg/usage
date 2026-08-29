import logging
from copy import copy
from threading import Lock
from time import monotonic

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count, Max

from config.collections import get_collection_size
from document.models import Document
from source.models import Source

_CACHE_ENTRY = None
_CACHE_LOCK = Lock()


def is_enabled(collection):
    enabled_collections = {
        value.lower()
        for value in getattr(settings, "PARSING_METADATA_CACHE_COLLECTIONS", [])
    }
    return collection.acron3.lower() in enabled_collections


def get_url_translation_manager(collection, translator_class, build_manager):
    global _CACHE_ENTRY

    acronym = collection.acron3
    size = get_collection_size(acronym)
    translator_name = translator_class.__name__

    with _CACHE_LOCK:
        entry = _CACHE_ENTRY
        reason = _get_rebuild_reason(entry, collection, translator_name)

        if reason is None:
            signature = _read_signature(collection)
            if signature == entry["signature"]:
                logging.info(
                    "Parsing metadata cache hit for %s (size=%s, signature=%s).",
                    acronym,
                    size,
                    signature,
                )
                return _fresh_manager(entry)
            reason = "signature_changed"

        started = monotonic()
        new_entry = _build_cache_entry(
            collection,
            translator_class,
            build_manager,
        )
        elapsed = monotonic() - started
        _CACHE_ENTRY = new_entry

        logging.info(
            "Parsing metadata cache %s for %s "
            "(size=%s, reason=%s, signature=%s, build_seconds=%.3f).",
            "miss" if entry is None else "rebuild",
            acronym,
            size,
            reason,
            new_entry["signature"],
            elapsed,
        )
        return _fresh_manager(new_entry)


def clear():
    global _CACHE_ENTRY

    with _CACHE_LOCK:
        _CACHE_ENTRY = None


def _get_rebuild_reason(entry, collection, translator_name):
    if entry is None:
        return "empty"
    if entry["collection_id"] != collection.pk:
        return "collection_changed"
    if entry["translator_name"] != translator_name:
        return "translator_changed"
    return None


def _build_cache_entry(collection, translator_class, build_manager):
    if connection.in_atomic_block:
        return _load_cache_entry(collection, translator_class, build_manager)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return _load_cache_entry(collection, translator_class, build_manager)


def _load_cache_entry(collection, translator_class, build_manager):
    signature = _get_collection_signature(collection)
    manager, _ = build_manager(collection, translator_class)
    return {
        "collection_id": collection.pk,
        "translator_class": translator_class,
        "translator_name": translator_class.__name__,
        "signature": signature,
        "manager": manager,
    }


def _read_signature(collection):
    if connection.in_atomic_block:
        return _get_collection_signature(collection)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return _get_collection_signature(collection)


def _get_collection_signature(collection):
    document_signature = Document.objects.filter(collection=collection).aggregate(
        count=Count("pk"),
        max_updated=Max("updated"),
    )
    source_signature = Source.objects.filter(collection=collection).aggregate(
        count=Count("pk"),
        max_updated=Max("updated"),
    )
    return (
        document_signature["count"],
        document_signature["max_updated"],
        source_signature["count"],
        source_signature["max_updated"],
    )


def _fresh_manager(entry):
    manager = copy(entry["manager"])
    manager.translator = entry["translator_class"](
        manager.sources_metadata,
        manager.documents_metadata,
    )
    manager.is_translator_forced = True
    return manager
