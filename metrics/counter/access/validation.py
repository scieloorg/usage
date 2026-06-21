from scielo_usage_counter.values import (
    CONTENT_TYPE_UNDEFINED,
    DEFAULT_SCIELO_ISSN,
    MEDIA_FORMAT_UNDEFINED,
    MEDIA_LANGUAGE_UNDEFINED,
)


def is_valid(data, utm=None, ignore_utm_validation=False):
    if not isinstance(data, dict):
        return False, {
            "message": "Invalid data format. Expected a dictionary.",
            "code": "invalid_format",
        }

    scielo_issn = data.get("scielo_issn")
    source_id = data.get("source_id")
    source_type = data.get("source_type")
    document_type = data.get("document_type") or "article"
    media_format = data.get("media_format")
    media_language = data.get("media_language")
    content_type = data.get("content_type")
    pid_v2 = data.get("pid_v2")
    pid_v3 = data.get("pid_v3")
    pid_generic = data.get("pid_generic")
    has_source_identity = bool(source_id) or bool(
        scielo_issn and scielo_issn != DEFAULT_SCIELO_ISSN
    )
    has_media_language = bool(
        media_language and media_language != MEDIA_LANGUAGE_UNDEFINED
    )
    has_pid = bool(pid_v2 or pid_v3 or pid_generic)

    if not all(
        [
            media_format and media_format != MEDIA_FORMAT_UNDEFINED,
            content_type and content_type != CONTENT_TYPE_UNDEFINED,
            has_pid,
        ]
    ):
        return False, {
            "message": "Missing required fields in item access data.",
            "code": "missing_fields",
        }

    if document_type in {"article", "book", "chapter"} and not has_media_language:
        return False, {
            "message": "Missing media language in item access data.",
            "code": "missing_fields",
        }

    if document_type == "article" and not has_source_identity:
        return False, {
            "message": "Missing article source identity.",
            "code": "missing_fields",
        }

    if document_type in {"book", "chapter"} and not source_id:
        return False, {
            "message": "Missing book source identity.",
            "code": "missing_fields",
        }

    if document_type in {"preprint", "dataset"} and not pid_generic:
        return False, {
            "message": "Missing generic PID in item access data.",
            "code": "missing_fields",
        }

    if utm and not ignore_utm_validation:
        if (
            source_type == "journal"
            and scielo_issn
            and scielo_issn != DEFAULT_SCIELO_ISSN
            and not utm.is_valid_code(scielo_issn, utm.sources_metadata["issn_set"])
        ):
            return False, {
                "message": f"Invalid scielo_issn: {scielo_issn}",
                "code": "invalid_scielo_issn",
            }

        if (
            source_type
            and source_type != "journal"
            and source_id
            and source_id not in utm.sources_metadata.get("source_id_to_type", {})
        ):
            return False, {
                "message": f"Invalid source_id: {source_id}",
                "code": "invalid_source_id",
            }

        if pid_v2 and not utm.is_valid_code(pid_v2, utm.documents_metadata["pid_set"]):
            return False, {
                "message": f"Invalid pid_v2: {pid_v2}",
                "code": "invalid_pid_v2",
            }

        if pid_v3 and not utm.is_valid_code(pid_v3, utm.documents_metadata["pid_set"]):
            return False, {
                "message": f"Invalid pid_v3: {pid_v3}",
                "code": "invalid_pid_v3",
            }

        if pid_generic and not utm.is_valid_code(
            pid_generic, utm.documents_metadata["pid_set"]
        ):
            return False, {
                "message": f"Invalid pid_generic: {pid_generic}",
                "code": "invalid_pid_generic",
            }

    return True, {"message": "Item access data is valid.", "code": "valid"}
