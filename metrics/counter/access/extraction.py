from scielo_usage_counter.values import DEFAULT_SCIELO_ISSN

from core.utils.standardizer import (
    standardize_language_code,
    standardize_or_default,
    standardize_pid_generic,
    standardize_pid_generic_values,
    standardize_pid_v2,
    standardize_pid_v3,
    standardize_year_of_publication,
)


def extract(collection_acron3, translated_url):
    if not translated_url or not isinstance(translated_url, dict):
        return {}

    source_type = _resolve_source_type(collection_acron3, translated_url)
    source_id = _resolve_source_id(translated_url, source_type)
    scielo_issn = _resolve_scielo_issn(translated_url, source_type, source_id)
    document_type = _resolve_document_type(
        collection_acron3, translated_url, source_type
    )
    publication_year = standardize_or_default(
        standardize_year_of_publication,
        translated_url.get("year_of_publication"),
    )
    source_access_type = translated_url.get("source_access_type")

    return {
        "collection": collection_acron3,
        "source_type": source_type,
        "source_id": source_id,
        "scielo_issn": scielo_issn,
        "document_type": document_type,
        "document_title": _resolve_document_title(document_type, translated_url),
        "pid_v2": standardize_or_default(
            standardize_pid_v2,
            translated_url.get("pid_v2"),
        ),
        "pid_v3": standardize_or_default(
            standardize_pid_v3,
            translated_url.get("pid_v3"),
        ),
        "pid_generic": standardize_or_default(
            standardize_pid_generic,
            translated_url.get("pid_generic"),
        ),
        "title_pid_generic": standardize_or_default(
            standardize_pid_generic,
            translated_url.get("title_pid_generic"),
        ),
        "segment_pid_generics": standardize_pid_generic_values(
            translated_url.get("segment_pid_generics"),
        ),
        "media_language": standardize_or_default(
            standardize_language_code,
            translated_url.get("media_language"),
            default="un",
        ),
        "media_format": translated_url.get("media_format"),
        "content_type": translated_url.get("content_type"),
        "access_url": translated_url.get("access_url")
        or translated_url.get("normalized_url"),
        "publication_year": publication_year,
        "counter_access_type": _resolve_counter_access_type(source_access_type),
        "access_method": "Regular",
        "source_main_title": (
            translated_url.get("source_main_title")
            or translated_url.get("journal_main_title")
            or translated_url.get("book_title")
        ),
        "source_subject_area_capes": translated_url.get("source_subject_area_capes")
        or translated_url.get("journal_subject_area_capes"),
        "source_subject_area_wos": translated_url.get("source_subject_area_wos")
        or translated_url.get("journal_subject_area_wos"),
        "source_acronym": translated_url.get("source_acronym")
        or translated_url.get("journal_acronym"),
        "source_publisher_name": translated_url.get("source_publisher_name")
        or translated_url.get("journal_publisher_name"),
        "source_access_type": source_access_type,
        "source_identifiers": _resolve_source_identifiers(translated_url),
        "source_city": translated_url.get("source_city"),
        "source_country": translated_url.get("source_country"),
    }


def _resolve_document_title(document_type, translated_url):
    if document_type == "chapter":
        return translated_url.get("chapter_title")

    if document_type == "book":
        return translated_url.get("book_title")

    return (
        translated_url.get("document_title")
        or translated_url.get("article_title")
        or translated_url.get("title")
    )


def _resolve_counter_access_type(source_access_type):
    normalized_access_type = str(source_access_type or "").strip().lower()
    if normalized_access_type == "commercial":
        return "Controlled"

    if normalized_access_type in {"free_to_read", "free-to-read", "free"}:
        return "Free_To_Read"

    return "Open"


def _resolve_source_type(collection_acron3, translated_url):
    source_type = translated_url.get("source_type")
    if source_type:
        return source_type

    if collection_acron3 == "preprints":
        return "preprint_server"

    if collection_acron3 == "data":
        return "data_repository"

    if (
        translated_url.get("scielo_issn")
        and translated_url.get("scielo_issn") != DEFAULT_SCIELO_ISSN
    ):
        return "journal"

    if translated_url.get("journal_acronym") or translated_url.get(
        "journal_main_title"
    ):
        return "journal"

    return "other"


def _resolve_source_id(translated_url, source_type):
    source_id = translated_url.get("source_id")
    if source_id:
        return source_id

    if source_type == "preprint_server":
        return translated_url.get("preprint_server_id") or "scielo-preprints"

    if source_type == "data_repository":
        return translated_url.get("repository_id") or "scielo-data"

    if source_type == "journal":
        return translated_url.get("scielo_issn")

    return None


def _resolve_scielo_issn(translated_url, source_type, source_id):
    scielo_issn = translated_url.get("scielo_issn")
    if scielo_issn:
        return scielo_issn

    if source_type == "journal" and source_id:
        return source_id

    if source_type in {"book", "other"}:
        return DEFAULT_SCIELO_ISSN

    return None


def _resolve_document_type(collection_acron3, translated_url, source_type):
    document_type = translated_url.get("document_type")
    if document_type:
        return document_type

    if collection_acron3 == "preprints":
        return "preprint"

    if collection_acron3 == "data":
        return "dataset"

    if source_type == "journal":
        return "article"

    return "article"


def _resolve_source_identifiers(translated_url):
    identifiers = translated_url.get("source_identifiers")
    if isinstance(identifiers, dict):
        return _compact_identifiers(identifiers)
    return None


def _compact_identifiers(identifiers):
    compact = {
        key: value
        for key, value in identifiers.items()
        if value not in (None, "", [], {}, ())
    }
    return compact or None
