import base64
import hashlib
import json

KEY_PREFIX = "k1_"
UNKNOWN_VALUE = "_unknown"


def stable_key(*parts):
    payload = json.dumps(
        list(parts),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=16).digest()
    token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{KEY_PREFIX}{token}"


def source_key(collection, source_type, source_id):
    return stable_key(
        "source",
        collection or UNKNOWN_VALUE,
        source_type or UNKNOWN_VALUE,
        source_id or UNKNOWN_VALUE,
    )


def document_key(collection, document_type, document_id):
    return stable_key(
        "document",
        collection or UNKNOWN_VALUE,
        document_type or UNKNOWN_VALUE,
        document_id or UNKNOWN_VALUE,
    )


def metric_key(
    collection,
    source_identifier,
    document_identifier,
    period,
    metric_scope,
    data_type,
    parent_data_type,
    article_version,
    access_type,
    access_method,
    projection=None,
    country_code=None,
    content_language=None,
):
    return stable_key(
        "metric",
        collection or UNKNOWN_VALUE,
        source_identifier or UNKNOWN_VALUE,
        document_identifier or UNKNOWN_VALUE,
        period or UNKNOWN_VALUE,
        metric_scope or UNKNOWN_VALUE,
        data_type or UNKNOWN_VALUE,
        parent_data_type or UNKNOWN_VALUE,
        article_version or UNKNOWN_VALUE,
        access_type or UNKNOWN_VALUE,
        access_method or UNKNOWN_VALUE,
        projection or "counter",
        country_code or UNKNOWN_VALUE,
        content_language or UNKNOWN_VALUE,
    )
