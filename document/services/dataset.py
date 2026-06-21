from document.models import Document

from core.utils.metadata import compact_dict, normalize_year


def upsert_dataset_document(
    payload,
    collection,
    user=None,
    force_update=True,
):
    dataset_doi = payload.get("dataset_doi")
    if not dataset_doi:
        return None

    document, created = Document.objects.get_or_create(
        collection=collection,
        document_type=Document.DOCUMENT_TYPE_DATASET,
        document_id=dataset_doi,
    )

    if created and user:
        document.creator = user

    if created or force_update:
        files = dict(document.files or {})
        file_id = payload.get("file_id")
        if file_id:
            files[str(file_id)] = compact_dict(
                {
                    "name": payload.get("file_name"),
                    "url": payload.get("file_url"),
                    "file_persistent_id": payload.get("file_persistent_id"),
                }
            )

        document.source = None
        document.parent_document = None
        document.scielo_issn = None
        document.pid_v2 = None
        document.pid_v3 = None
        document.pid_generic = dataset_doi
        document.title = payload.get("title") or document.title
        document.identifiers = compact_dict(
            {
                "dataset_doi": dataset_doi,
            }
        )
        document.files = files
        document.default_lang = document.default_lang
        document.text_langs = document.text_langs or []
        document.default_media_format = document.default_media_format
        document.processing_date = document.processing_date
        document.publication_date = (
            payload.get("dataset_published") or document.publication_date
        )
        document.publication_year = normalize_year(
            None,
            fallback_date=document.publication_date,
        )
        document.extra_data = compact_dict(
            {
                "provider": "dataverse",
            }
        )

    if user:
        document.updated_by = user

    document.save()
    return document
