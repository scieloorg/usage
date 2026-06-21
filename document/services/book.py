from document.models import Document

from core.utils.metadata import compact_dict, normalize_langs, normalize_year


def enrich_part_payload(payload, monograph_payload):
    if not monograph_payload:
        return payload

    enriched = dict(payload)
    enriched["monograph_title"] = monograph_payload.get("title")
    enriched["monograph_language"] = monograph_payload.get("language")
    enriched["monograph_publication_date"] = monograph_payload.get("publication_date")
    enriched["monograph_year"] = monograph_payload.get("year")
    enriched["monograph_publisher"] = monograph_payload.get("publisher")
    enriched["monograph_isbn"] = monograph_payload.get("isbn")
    enriched["monograph_eisbn"] = monograph_payload.get("eisbn")
    enriched["monograph_doi_number"] = monograph_payload.get("doi_number")
    enriched["monograph_creators"] = monograph_payload.get("creators")
    return enriched


def upsert_monograph_document(
    payload,
    collection,
    source=None,
    user=None,
    force_update=True,
    source_url=None,
    last_seq=None,
):
    if payload.get("TYPE") != "Monograph":
        return None

    book_id = str(payload.get("id"))
    pid_generic = Document.build_book_pid_generic(book_id)
    document, created = Document.objects.get_or_create(
        collection=collection,
        document_type=Document.DOCUMENT_TYPE_BOOK,
        document_id=pid_generic,
    )

    if created and user:
        document.creator = user

    if created or force_update:
        document.source = source
        document.parent_document = None
        document.scielo_issn = None
        document.pid_v2 = None
        document.pid_v3 = None
        document.pid_generic = pid_generic
        document.title = payload.get("title") or book_id
        document.identifiers = _build_monograph_identifiers(payload)
        document.files = {}
        document.default_lang = payload.get("language") or None
        document.text_langs = normalize_langs(payload.get("language"))
        document.default_media_format = None
        document.processing_date = None
        document.publication_date = payload.get("publication_date") or None
        document.publication_year = normalize_year(payload.get("year"))
        document.extra_data = _build_monograph_extra_data(
            payload,
            source_url=source_url,
            last_seq=last_seq,
        )

    if user:
        document.updated_by = user

    document.save()
    return document


def upsert_part_document(
    payload,
    collection,
    source=None,
    parent_document=None,
    user=None,
    force_update=True,
    source_url=None,
    last_seq=None,
):
    if payload.get("TYPE") != "Part":
        return None

    book_id = payload.get("monograph")
    chapter_id = payload.get("id")
    pid_generic = Document.build_chapter_pid_generic(book_id, chapter_id)
    document, created = Document.objects.get_or_create(
        collection=collection,
        document_type=Document.DOCUMENT_TYPE_CHAPTER,
        document_id=pid_generic,
    )

    if created and user:
        document.creator = user

    if created or force_update:
        document.source = source
        document.parent_document = parent_document
        document.scielo_issn = None
        document.pid_v2 = None
        document.pid_v3 = None
        document.pid_generic = pid_generic
        document.title = payload.get("title") or str(chapter_id)
        document.identifiers = _build_part_identifiers(payload)
        document.files = {}
        document.default_lang = (
            payload.get("text_language") or payload.get("monograph_language") or None
        )
        document.text_langs = normalize_langs(
            payload.get("text_language") or payload.get("monograph_language")
        )
        document.default_media_format = None
        document.processing_date = None
        document.publication_date = payload.get("monograph_publication_date") or None
        document.publication_year = normalize_year(payload.get("monograph_year"))
        document.extra_data = _build_part_extra_data(
            payload,
            source_url=source_url,
            last_seq=last_seq,
        )

    if user:
        document.updated_by = user

    document.save()
    return document


def _build_monograph_identifiers(payload):
    identifiers = {
        "book_id": str(payload.get("id")) if payload.get("id") is not None else None,
        "isbn": payload.get("isbn"),
        "eisbn": payload.get("eisbn"),
        "doi": payload.get("doi_number"),
    }
    return compact_dict(identifiers)


def _build_part_identifiers(payload):
    identifiers = {
        "book_id": str(payload.get("monograph"))
        if payload.get("monograph") is not None
        else None,
        "chapter_id": str(payload.get("id")) if payload.get("id") is not None else None,
        "isbn": payload.get("monograph_isbn"),
        "eisbn": payload.get("monograph_eisbn"),
        "doi": payload.get("doi_number"),
        "book_doi": payload.get("monograph_doi_number"),
    }
    return compact_dict(identifiers)


def _build_monograph_extra_data(payload, source_url=None, last_seq=None):
    extra_data = {
        "raw_id": str(payload.get("id")) if payload.get("id") is not None else None,
        "raw_type": payload.get("TYPE"),
        "source_url": source_url,
        "last_seq": last_seq,
        "visible": payload.get("visible"),
        "city": payload.get("city"),
        "country": payload.get("country"),
        "pages": payload.get("pages"),
        "publisher": payload.get("publisher"),
        "creators": payload.get("creators"),
        "translated_titles": payload.get("translated_titles"),
        "translated_synopses": payload.get("translated_synopses"),
        "synopsis": payload.get("synopsis"),
    }
    return compact_dict(extra_data)


def _build_part_extra_data(payload, source_url=None, last_seq=None):
    extra_data = {
        "raw_id": str(payload.get("id")) if payload.get("id") is not None else None,
        "raw_type": payload.get("TYPE"),
        "source_url": source_url,
        "last_seq": last_seq,
        "visible": payload.get("visible"),
        "order": payload.get("order"),
        "pages": payload.get("pages"),
        "creators": payload.get("creators"),
        "translated_titles": payload.get("translated_titles"),
        "monograph_id": str(payload.get("monograph"))
        if payload.get("monograph") is not None
        else None,
        "monograph_title": payload.get("monograph_title"),
        "monograph_language": payload.get("monograph_language"),
        "monograph_publication_date": payload.get("monograph_publication_date"),
        "monograph_year": payload.get("monograph_year"),
        "monograph_publisher": payload.get("monograph_publisher"),
        "monograph_creators": payload.get("monograph_creators"),
    }
    return compact_dict(extra_data)
