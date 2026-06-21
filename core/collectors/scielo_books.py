import logging
from urllib.parse import urlencode

import requests
from django.conf import settings


def build_url(base_url, params=None):
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params, doseq=True)}"


def sanitize_raw_data(payload):
    if not isinstance(payload, dict):
        return payload

    if "_id" not in payload:
        return payload

    sanitized = dict(payload)
    sanitized["id"] = sanitized.pop("_id")
    return sanitized


def fetch_document(doc_id, base_url=None, db_name=None, headers=None):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    resolved_base_url = base_url or settings.SCIELO_BOOKS_BASE_URL
    if not resolved_base_url:
        logging.error("Sem base url definida para coleta de books")
        raise ValueError("SCIELO_BOOKS_BASE_URL is not configured")

    url = f"{resolved_base_url}/{db_name}/{doc_id}"
    response = requests.get(
        url, headers=headers, timeout=settings.SCIELO_BOOKS_TIMEOUT, verify=False
    )
    response.raise_for_status()
    payload = response.json()
    return sanitize_raw_data(payload), url


def fetch_changes_page(
    base_url=None,
    db_name=None,
    since=0,
    limit=None,
    include_docs=False,
    headers=None,
):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    limit = limit or settings.SCIELO_BOOKS_LIMIT
    resolved_base_url = base_url or settings.SCIELO_BOOKS_BASE_URL
    if not resolved_base_url:
        logging.error("Sem base url definida para coleta de books")
        raise ValueError("SCIELO_BOOKS_BASE_URL is not configured")

    params = {
        "since": since,
        "limit": limit,
    }
    if include_docs:
        params["include_docs"] = "true"

    url = build_url(f"{resolved_base_url}/{db_name}/_changes", params)
    response = requests.get(
        url, headers=headers, timeout=settings.SCIELO_BOOKS_TIMEOUT, verify=False
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def extract_changes(payload):
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return payload.get("results")
    return []


def extract_last_seq(payload):
    if isinstance(payload, dict):
        return payload.get("last_seq") or payload.get("seq")
    return None


def iter_changes(
    base_url=None,
    db_name=None,
    since=0,
    limit=None,
    headers=None,
):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    limit = limit or settings.SCIELO_BOOKS_LIMIT
    current_since = since or 0

    while True:
        payload = fetch_changes_page(
            base_url=base_url,
            db_name=db_name,
            since=current_since,
            limit=limit,
            include_docs=False,
            headers=headers,
        )
        changes = extract_changes(payload)
        if not changes:
            break

        for change in changes:
            yield change

        last_seq = extract_last_seq(payload)
        if last_seq is None or last_seq == current_since:
            break
        current_since = last_seq


def iter_change_documents(
    base_url=None,
    db_name=None,
    since=0,
    limit=None,
    headers=None,
):
    db_name = db_name or settings.SCIELO_BOOKS_DB_NAME
    limit = limit or settings.SCIELO_BOOKS_LIMIT
    current_since = since or 0

    while True:
        payload = fetch_changes_page(
            base_url=base_url,
            db_name=db_name,
            since=current_since,
            limit=limit,
            include_docs=True,
            headers=headers,
        )
        changes = extract_changes(payload)
        if not changes:
            break

        for change in changes:
            doc_id = change.get("id")
            if not doc_id:
                continue

            deleted = bool(change.get("deleted"))
            raw_doc = change.get("doc") or {}
            if deleted:
                yield {
                    "change": change,
                    "deleted": True,
                    "payload": None,
                    "source_url": None,
                }
                continue

            if raw_doc:
                sanitized = sanitize_raw_data(raw_doc)
                yield {
                    "change": change,
                    "deleted": False,
                    "payload": sanitized,
                    "source_url": f"{(base_url or settings.SCIELO_BOOKS_BASE_URL)}/{db_name}/{doc_id}",
                }
                continue

            document_payload, source_url = fetch_document(
                doc_id=doc_id,
                base_url=base_url,
                db_name=db_name,
                headers=headers,
            )
            yield {
                "change": change,
                "deleted": False,
                "payload": document_payload,
                "source_url": source_url,
            }

        last_seq = extract_last_seq(payload)
        if last_seq is None or last_seq == current_since:
            break
        current_since = last_seq
