from metrics.opensearch.keys import document_key, source_key


def build_source_document(source, active=True):
    key = source_key(
        source.collection.acron3,
        source.source_type,
        source.source_id,
    )
    return key, {
        "key": key,
        "collection": source.collection.acron3,
        "source_id": source.source_id,
        "source_type": source.source_type,
        "title": source.title,
        "scielo_issn": source.scielo_issn,
        "acronym": source.acronym,
        "publisher_name": source.publisher_name or [],
        "access_type": source.access_type,
        "country": (source.extra_data or {}).get("country"),
        "subject_areas": source.subject_areas or [],
        "wos_subject_areas": source.wos_subject_areas or [],
        "identifiers": source.identifiers or {},
        "active": active,
        "updated": source.updated.isoformat(),
    }


def build_document_document(document, active=True):
    collection = document.collection.acron3
    canonical_id = (
        document.pid_v3
        or document.pid_v2
        or document.pid_generic
        or document.document_id
    )
    key = document_key(
        collection,
        document.document_type,
        canonical_id,
    )
    source_identifier = None
    if document.source_id:
        source_identifier = source_key(
            collection,
            document.source.source_type,
            document.source.source_id,
        )
    parent_identifier = None
    if document.parent_document_id:
        parent = document.parent_document
        parent_id = (
            parent.pid_v3 or parent.pid_v2 or parent.pid_generic or parent.document_id
        )
        parent_identifier = document_key(
            collection,
            parent.document_type,
            parent_id,
        )
    return key, {
        "key": key,
        "collection": collection,
        "document_id": document.document_id,
        "document_type": document.document_type,
        "source_key": source_identifier,
        "parent_document_key": parent_identifier,
        "title": document.title,
        "publication_year": _integer_or_none(document.publication_year),
        "default_lang": document.default_lang,
        "text_langs": document.text_langs or [],
        "identifiers": _document_identifiers(document),
        "active": active,
        "updated": document.updated.isoformat(),
    }


def build_source_tombstone(source):
    key, payload = build_source_document(source, active=False)
    return key, {
        "key": key,
        "collection": payload["collection"],
        "source_id": payload["source_id"],
        "source_type": payload["source_type"],
        "active": False,
        "updated": payload["updated"],
    }


def build_document_tombstone(document):
    key, payload = build_document_document(document, active=False)
    return key, {
        "key": key,
        "collection": payload["collection"],
        "document_id": payload["document_id"],
        "document_type": payload["document_type"],
        "active": False,
        "updated": payload["updated"],
    }


def _document_identifiers(document):
    identifiers = dict(document.identifiers or {})
    for name in ("pid_v2", "pid_v3", "pid_generic", "scielo_issn"):
        value = getattr(document, name)
        if value:
            identifiers[name] = value
    return identifiers


def _integer_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
