import gzip
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from metrics.legacy_matomo.manifest import (
    MANIFEST_SCHEMA_VERSION,
    MIGRATION_NAME,
    validate_migration_scope,
)
from metrics.opensearch.keys import metric_key
from metrics.opensearch.painless import METRIC_FIELDS

ARTICLE_METRIC_DIMENSIONS = {
    "metric_scope": "item",
    "data_type": "Article",
    "parent_data_type": "Journal",
    "article_version": None,
    "access_type": "Open",
    "access_method": "Regular",
}
SQLITE_INSERT_BATCH_SIZE = 10000
DEFAULT_PROGRESS_INTERVAL = 100000


class UniqueIdStore:
    def __init__(self, temporary_directory=None):
        descriptor, self.path = tempfile.mkstemp(
            prefix="legacy-matomo-ids-",
            suffix=".sqlite3",
            dir=temporary_directory,
        )
        os.close(descriptor)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA journal_mode=OFF")
        self.connection.execute("PRAGMA synchronous=OFF")
        self.connection.execute(
            "CREATE TABLE ids (value TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        self.pending = []

    def add(self, value):
        self.pending.append((value,))
        if len(self.pending) >= SQLITE_INSERT_BATCH_SIZE:
            self.flush()

    def flush(self):
        if not self.pending:
            return
        try:
            self.connection.executemany("INSERT INTO ids VALUES (?)", self.pending)
        except sqlite3.IntegrityError as exc:
            raise ValueError("Migration payload contains a duplicate _id.") from exc
        self.pending = []

    def close(self):
        try:
            self.flush()
        finally:
            self.connection.close()
            os.unlink(self.path)


def _metric_values(document):
    values = []
    for field in METRIC_FIELDS:
        value = document.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("Invalid metric value for %s." % field)
        values.append(value)
    return values


def _add_metrics(target, values):
    for index, value in enumerate(values):
        target[index] += value


def _validate_dimensions(document):
    for field, expected in ARTICLE_METRIC_DIMENSIONS.items():
        if document.get(field) != expected:
            raise ValueError("Invalid counter dimension %s." % field)


def _expected_metric_id(collection, document, period, analytics):
    return metric_key(
        collection=collection,
        source_identifier=document["source_key"],
        document_identifier=document["document_key"],
        period=period,
        projection="country_language" if analytics else None,
        country_code=document.get("country_code"),
        content_language=document.get("content_language"),
        **ARTICLE_METRIC_DIMENSIONS,
    )


def validate_document_file(
    file_summary,
    collection,
    source_days,
    analytics=False,
    temporary_directory=None,
    progress_callback=None,
    progress_interval=DEFAULT_PROGRESS_INTERVAL,
    stop_controller=None,
):
    path = Path(file_summary["path"])
    expected_dataset = "analytics" if analytics else "counter"
    if file_summary.get("dataset") != expected_dataset:
        raise ValueError("Invalid dataset summary for %s." % path)

    expected_period = (
        file_summary["source_month"][:4] if analytics else file_summary["month"]
    )
    source_day_suffixes = {value[-2:] for value in source_days}
    totals = [0] * len(METRIC_FIELDS)
    payload_hash = hashlib.sha256()
    documents = 0
    unique_ids = UniqueIdStore(temporary_directory)

    try:
        with gzip.open(path, "rb") as source:
            for line_number, line in enumerate(source, 1):
                payload_hash.update(line)
                row = json.loads(line)
                document = row.get("_source")
                if not row.get("_id") or not isinstance(document, dict):
                    raise ValueError(
                        "Invalid JSONL row at %s:%d." % (path, line_number)
                    )
                unique_ids.add(row["_id"])
                _validate_dimensions(document)
                if row["_id"] != _expected_metric_id(
                    collection, document, expected_period, analytics
                ):
                    raise ValueError(
                        "Invalid metric key at %s:%d." % (path, line_number)
                    )

                if analytics:
                    _validate_analytics_document(
                        document, expected_period, path, line_number
                    )
                else:
                    _validate_counter_document(
                        document,
                        collection,
                        expected_period,
                        source_day_suffixes,
                        path,
                        line_number,
                    )

                _add_metrics(totals, _metric_values(document))
                documents += 1
                if documents % progress_interval == 0:
                    if progress_callback:
                        progress_callback(expected_dataset, "validation", documents)
                    if stop_controller:
                        stop_controller.raise_if_requested()
            if progress_callback and documents % progress_interval:
                progress_callback(expected_dataset, "validation", documents)
            if stop_controller:
                stop_controller.raise_if_requested()
    finally:
        unique_ids.close()

    actual_totals = dict(zip(METRIC_FIELDS, totals))
    if documents != file_summary["documents"]:
        raise ValueError("Document count mismatch for %s." % path)
    if actual_totals != file_summary["totals"]:
        raise ValueError("Metric totals mismatch for %s." % path)
    if payload_hash.hexdigest() != file_summary["uncompressed_sha256"]:
        raise ValueError("SHA-256 mismatch for %s." % path)

    return {
        "path": str(path),
        "documents": documents,
        "totals": actual_totals,
        "uncompressed_sha256": payload_hash.hexdigest(),
    }


def _validate_analytics_document(document, expected_year, path, line_number):
    if document.get("year") != expected_year:
        raise ValueError("Invalid analytics year at %s:%d." % (path, line_number))
    if not document.get("country_code") or not document.get("content_language"):
        raise ValueError(
            "Incomplete analytics projection at %s:%d." % (path, line_number)
        )


def _validate_counter_document(
    document,
    collection,
    expected_month,
    source_day_suffixes,
    path,
    line_number,
):
    if document.get("collection") != collection:
        raise ValueError("Invalid collection at %s:%d." % (path, line_number))
    if document.get("month") != expected_month:
        raise ValueError("Invalid counter month at %s:%d." % (path, line_number))
    daily_metrics = document.get("daily_metrics")
    if not isinstance(daily_metrics, dict) or not daily_metrics:
        raise ValueError(
            "Missing counter daily metrics at %s:%d." % (path, line_number)
        )
    if not set(daily_metrics).issubset(source_day_suffixes):
        raise ValueError("Unexpected daily metric at %s:%d." % (path, line_number))

    daily_totals = [0] * len(METRIC_FIELDS)
    for values in daily_metrics.values():
        _add_metrics(daily_totals, _metric_values(values))
    if daily_totals != _metric_values(document):
        raise ValueError(
            "Counter daily totals mismatch at %s:%d." % (path, line_number)
        )


def validate_manifest(
    manifest,
    temporary_directory=None,
    progress_callback=None,
    progress_interval=DEFAULT_PROGRESS_INTERVAL,
    stop_controller=None,
):
    if progress_interval <= 0:
        raise ValueError("Progress interval must be greater than zero.")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unsupported migration manifest schema version.")
    if manifest.get("migration") != MIGRATION_NAME:
        raise ValueError("Unsupported migration manifest.")
    validate_migration_scope(manifest)

    collection = manifest["target"]["collection"]
    month = manifest["month"]
    date.fromisoformat(month + "-01")
    source_days = manifest["source_days"]
    if not source_days:
        raise ValueError("Migration manifest has no source days.")
    if source_days != sorted(set(source_days)):
        raise ValueError("Migration source days must be unique and sorted.")
    for value in source_days:
        date.fromisoformat(value)
        if value[:7] != month:
            raise ValueError("Source day outside migration month: %s." % value)

    empty_days = manifest.get("empty_days", [])
    if set(source_days) & set(empty_days):
        raise ValueError("Source days and empty days overlap.")
    for value in empty_days:
        date.fromisoformat(value)
        if value[:7] != month:
            raise ValueError("Empty day outside migration month: %s." % value)

    if manifest["counter"].get("month") != month:
        raise ValueError("Counter summary month differs from manifest.")
    if manifest["analytics"].get("source_month") != month:
        raise ValueError("Analytics summary month differs from manifest.")

    counter = validate_document_file(
        manifest["counter"],
        collection,
        source_days,
        analytics=False,
        temporary_directory=temporary_directory,
        progress_callback=progress_callback,
        progress_interval=progress_interval,
        stop_controller=stop_controller,
    )
    analytics = validate_document_file(
        manifest["analytics"],
        collection,
        source_days,
        analytics=True,
        temporary_directory=temporary_directory,
        progress_callback=progress_callback,
        progress_interval=progress_interval,
        stop_controller=stop_controller,
    )
    if counter["totals"] != analytics["totals"]:
        raise ValueError("Counter and analytics totals do not reconcile.")

    return {
        "status": "valid",
        "collection": collection,
        "month": month,
        "source_days": len(source_days),
        "counter": counter,
        "analytics": analytics,
    }
