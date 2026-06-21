from document.models import Document

from core.utils.metadata import compact_dict, normalize_langs, normalize_year


def upsert_article_document_from_articlemeta(
    payload,
    collection,
    source=None,
    user=None,
    force_update=True,
):
    pid_v2 = payload.get("code")
    document_id = _first_identifier(
        pid_v2, payload.get("pid_v3"), payload.get("pid_generic")
    )
    if not document_id:
        return None

    document = Document.find_by_identifiers(
        collection,
        Document.DOCUMENT_TYPE_ARTICLE,
        document_id,
        pid_v2,
    )
    created = document is None
    if created:
        document = Document(
            collection=collection,
            document_type=Document.DOCUMENT_TYPE_ARTICLE,
            document_id=document_id,
        )
        if user:
            document.creator = user

    if created or force_update:
        document.source = source
        document.parent_document = None
        document.scielo_issn = source.scielo_issn if source else None
        document.pid_v2 = pid_v2 or document.pid_v2
        document.pid_v3 = payload.get("pid_v3") or document.pid_v3
        document.pid_generic = payload.get("pid_generic") or document.pid_generic
        document.title = payload.get("title") or document.title
        document.identifiers = _merge_dicts(
            document.identifiers,
            _build_articlemeta_identifiers(payload, source),
        )
        document.files = payload.get("pdfs") or document.files or {}
        document.default_lang = payload.get("default_language") or document.default_lang
        document.text_langs = normalize_langs(payload.get("text_langs"))
        document.default_media_format = document.default_media_format
        document.processing_date = (
            payload.get("processing_date") or document.processing_date
        )
        document.publication_date = (
            payload.get("publication_date") or document.publication_date
        )
        document.publication_year = normalize_year(
            payload.get("publication_year"),
            fallback_date=document.publication_date,
        )
        document.extra_data = _merge_dicts(
            document.extra_data,
            compact_dict(
                {
                    "provider": "articlemeta",
                    "issn_codes": payload.get("code_title"),
                }
            ),
        )

    if user:
        document.updated_by = user

    document.save()
    return document


def upsert_article_document_from_opac(
    payload,
    collection,
    source=None,
    user=None,
    force_update=True,
):
    pid_v2 = payload.get("pid_v2")
    pid_v3 = payload.get("pid_v3")
    document_id = _first_identifier(
        pid_v2,
        pid_v3,
        payload.get("pid_generic"),
    )
    if not document_id:
        return None

    document = Document.find_by_identifiers(
        collection,
        Document.DOCUMENT_TYPE_ARTICLE,
        document_id,
        pid_v2,
        pid_v3,
        payload.get("pid_generic"),
    )
    created = document is None
    if created:
        document = Document(
            collection=collection,
            document_type=Document.DOCUMENT_TYPE_ARTICLE,
            document_id=document_id,
        )
        if user:
            document.creator = user

    if created or force_update:
        document.source = source
        document.parent_document = None
        document.scielo_issn = source.scielo_issn if source else None
        document.pid_v2 = pid_v2 or document.pid_v2
        document.pid_v3 = pid_v3 or document.pid_v3
        document.pid_generic = payload.get("pid_generic") or document.pid_generic
        document.title = payload.get("title") or document.title
        document.identifiers = _merge_dicts(
            document.identifiers,
            _build_opac_identifiers(payload, source),
        )
        document.files = document.files or {}
        document.default_lang = payload.get("default_language") or document.default_lang
        document.text_langs = (
            normalize_langs(payload.get("text_langs")) or document.text_langs or []
        )
        document.default_media_format = document.default_media_format
        document.processing_date = document.processing_date
        document.publication_date = (
            payload.get("publication_date") or document.publication_date
        )
        document.publication_year = normalize_year(
            payload.get("publication_year"),
            fallback_date=document.publication_date,
        )
        document.extra_data = _merge_dicts(
            document.extra_data,
            compact_dict(
                {
                    "provider": "opac",
                    "journal_acronym": payload.get("journal_acronym"),
                }
            ),
        )

    if user:
        document.updated_by = user

    document.save()
    return document


def _build_articlemeta_identifiers(payload, source):
    return compact_dict(
        {
            "pid_v2": payload.get("code"),
            "scielo_issn": source.scielo_issn if source else None,
        }
    )


def _build_opac_identifiers(payload, source):
    return compact_dict(
        {
            "pid_v2": payload.get("pid_v2"),
            "pid_v3": payload.get("pid_v3"),
            "scielo_issn": source.scielo_issn if source else None,
            "journal_acronym": payload.get("journal_acronym"),
        }
    )


def _merge_dicts(current, new_values):
    merged = dict(current or {})
    merged.update(new_values or {})
    return merged


def _first_identifier(*values):
    for value in values:
        if value not in (None, ""):
            return str(value)
    return None
