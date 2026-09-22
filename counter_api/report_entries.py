from collections import defaultdict
from time import monotonic

from django.conf import settings

from counter_api.constants import METRICS, STANDARD_VIEWS, TITLE_METRICS
from counter_api.exceptions import service_unavailable
from counter_api.identifiers import counter_identifiers

ATTRIBUTE_FIELDS = {
    "Data_Type": "data_type",
    "YOP": "yop",
    "Access_Type": "access_type",
    "Access_Method": "access_method",
}
PARENT_DATA_TYPES = {"journals": "Journal", "books": "Book"}


def build_entries(report_id, platform, records, params, deadline):
    entries = defaultdict(lambda: defaultdict(int))
    shown_attributes = _shown_attributes(report_id, params)
    missing_sources = set()
    missing_documents = set()

    for bucket, source, document in records:
        if deadline and monotonic() >= deadline:
            raise service_unavailable()

        key = bucket["key"]
        if report_id.startswith("tr") and not source:
            missing_sources.add(key.get("source_key"))
            continue
        if report_id == "ir" and not document:
            missing_documents.add(key.get("document_key"))
            continue

        for metric_type, field in _metrics_for_bucket(
            report_id,
            platform,
            key,
            params,
        ):
            count = int(bucket.get(field, {}).get("value", 0))
            if count <= 0:
                continue

            entry = _entry(report_id, platform, key, source, document, metric_type)
            if (
                params.get("Data_Type")
                and entry["data_type"] not in params["Data_Type"]
            ):
                continue

            entry = _hide_attributes(entry, shown_attributes)
            identity = _identity(report_id, entry)
            month = _month_value(key.get("month"))
            entries[identity][month] += count

            if len(entries) > settings.COUNTER_MAX_REPORT_ENTRIES:
                raise service_unavailable("report size")

    result = []
    for identity, performance in entries.items():
        entry = dict(identity)
        entry["performance"] = dict(performance)
        result.append(entry)

    exceptions = []
    if missing_sources:
        exceptions.append(
            {
                "Code": 3040,
                "Message": "Partial Data Returned",
                "Data": f"Metadata missing for {len(missing_sources)} title(s)",
            }
        )
    if missing_documents:
        exceptions.append(
            {
                "Code": 3040,
                "Message": "Partial Data Returned",
                "Data": f"Metadata missing for {len(missing_documents)} item(s)",
            }
        )

    return result, exceptions


def _metrics_for_bucket(report_id, platform, key, params):
    scope = key.get("metric_scope") or "item"
    if platform.collection_type == "books":
        if report_id == "ir":
            metrics = METRICS if scope == "item" else {}
        elif scope == "title":
            metrics = TITLE_METRICS
        else:
            metrics = METRICS
    elif scope == "item":
        metrics = METRICS
    else:
        metrics = {}

    selected = params.get("Metric_Type")
    return (
        (metric_type, field)
        for metric_type, field in metrics.items()
        if not selected or metric_type in selected
    )


def _entry(report_id, platform, key, source, document, metric_type):
    data_type = _data_type(report_id, platform, key)
    source_ids = ()
    item_ids = ()
    yop = ""

    if report_id.startswith("tr"):
        source_ids = counter_identifiers(source)
        yop = f"{key.get('publication_year') or 1:04d}"
    if report_id == "ir":
        item_ids = counter_identifiers(document)
        yop = f"{key.get('publication_year') or 1:04d}"

    parent_data_type = ""
    parent_title = ""
    parent_ids = ()

    if report_id == "ir" and source:
        parent_data_type = key.get("parent_data_type") or PARENT_DATA_TYPES.get(
            platform.collection_type,
            "",
        )
        if parent_data_type:
            parent_title = source.get("title") or ""
            parent_ids = counter_identifiers(source)

    return {
        "name": _item_name(report_id, platform, source, document),
        "publisher": "" if report_id == "pr" else _publisher(source),
        "platform": platform.acron3,
        "data_type": data_type,
        "access_type": key.get("access_type") or "Open",
        "access_method": key.get("access_method") or "Regular",
        "metric_type": metric_type,
        "yop": yop,
        "source_ids": source_ids,
        "item_ids": item_ids,
        "source_key": key.get("source_key") or "",
        "document_key": key.get("document_key") or "",
        "parent_data_type": parent_data_type,
        "parent_title": parent_title,
        "parent_ids": parent_ids,
    }


def _data_type(report_id, platform, key):
    if report_id.startswith("tr"):
        if platform.collection_type == "journals":
            return "Journal"
        return "Book"
    if report_id == "pr":
        if platform.collection_type == "journals":
            return "Journal"
        if platform.collection_type == "books":
            return "Book"

    return key.get("data_type") or "Unspecified"


def _item_name(report_id, platform, source, document):
    if report_id == "pr":
        return platform.acron3
    if report_id.startswith("tr"):
        return source.get("title") or source.get("source_id") or "Unknown"

    return document.get("title") or document.get("document_id") or "Unknown"


def _publisher(source):
    value = source.get("publisher_name") or []
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)

    return str(value)


def _hide_attributes(entry, shown_attributes):
    entry = dict(entry)

    for attribute, field in ATTRIBUTE_FIELDS.items():
        if attribute not in shown_attributes:
            entry[field] = ""

    return entry


def _identity(report_id, entry):
    excluded = {"source_key", "document_key"}
    if report_id.startswith("tr"):
        excluded.remove("source_key")
    if report_id == "ir":
        excluded.remove("source_key")
        excluded.remove("document_key")

    return tuple((key, value) for key, value in entry.items() if key not in excluded)


def _month_value(value):
    if isinstance(value, str):
        return value[:7]

    return value.strftime("%Y-%m")


def _shown_attributes(report_id, params):
    standard_view = STANDARD_VIEWS.get(report_id) or {}
    attributes = set(
        standard_view.get("attributes") or params.get("Attributes_To_Show") or []
    )
    if report_id in {"pr", "tr", "ir"}:
        attributes.add("Data_Type")

    return attributes
