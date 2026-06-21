from document.models import Document

from core.utils.metadata import compact_dict, normalize_langs, normalize_year


def upsert_preprint_document(
    payload,
    collection,
    user=None,
    force_update=True,
):
    pid_generic = payload.get("pid_generic")
    if not pid_generic:
        return None

    document, created = Document.objects.get_or_create(
        collection=collection,
        document_type=Document.DOCUMENT_TYPE_PREPRINT,
        document_id=pid_generic,
    )

    if created and user:
        document.creator = user

    if created or force_update:
        document.source = None
        document.parent_document = None
        document.scielo_issn = None
        document.pid_v2 = None
        document.pid_v3 = None
        document.pid_generic = pid_generic
        document.title = payload.get("title") or document.title
        document.identifiers = compact_dict(
            {
                "pid_generic": pid_generic,
            }
        )
        document.files = document.files or {}
        document.default_lang = payload.get("default_language") or document.default_lang
        document.text_langs = normalize_langs(payload.get("text_langs"))
        document.default_media_format = document.default_media_format
        document.processing_date = document.processing_date
        document.publication_date = (
            payload.get("publication_date") or document.publication_date
        )
        document.publication_year = normalize_year(
            payload.get("publication_year"),
            fallback_date=document.publication_date,
        )
        document.extra_data = compact_dict(
            {
                "provider": "preprints",
            }
        )

    if user:
        document.updated_by = user

    document.save()
    return document
