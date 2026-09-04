import hashlib
import json
import logging
import os
from datetime import timedelta
from pathlib import Path

import ijson
from django.conf import settings
from django.utils import timezone

from metrics.models import DailyMetricJob


def get_daily_payload_root():
    return Path(settings.MEDIA_ROOT) / "metrics" / "daily_payloads"


def build_daily_storage_path(collection, access_date):
    return (
        Path(collection.acron3)
        / access_date.strftime("%Y")
        / access_date.strftime("%m")
        / f"{access_date.isoformat()}.json"
    )


def resolve_storage_path(storage_path):
    return get_daily_payload_root() / storage_path


class DailyPayloadWriter:
    def __init__(self, storage_path, collection, access_date):
        self.collection = collection
        self.access_date = access_date
        self.resolved_path = resolve_storage_path(storage_path)
        self.tmp_path = self.resolved_path.with_suffix(
            f"{self.resolved_path.suffix}.tmp"
        )
        self.encoder = json.JSONEncoder(
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.payload_hash = hashlib.sha256()
        self.output = None
        self.next_granularity = "month"
        self.completed = False

    def __enter__(self):
        self.resolved_path.parent.mkdir(parents=True, exist_ok=True)
        self.output = self.tmp_path.open("wb")
        self._write_text('{"access_date":')
        self._write_json(self.access_date)
        self._write_text(',"collection":')
        self._write_json(self.collection)
        self._write_text(',"documents":{"month":')
        return self

    def write_document_items(self, granularity, document_items):
        if granularity != self.next_granularity:
            raise RuntimeError(
                f"Expected {self.next_granularity} documents, got {granularity}."
            )

        document_count = 0
        self._write_text("{")
        for document_id, document in document_items:
            if document_count:
                self._write_text(",")
            self._write_json(document_id)
            self._write_text(":")
            self._write_json(document)
            document_count += 1
        self._write_text("}")
        if granularity == "month":
            self._write_text(',"year":')
            self.next_granularity = "year"
        else:
            self.next_granularity = None
        return document_count

    def finalize(self, input_log_hashes, summary):
        if self.next_granularity is not None:
            raise RuntimeError("Month and year documents must be written first.")

        self._write_text('},"input_log_hashes":')
        self._write_json(input_log_hashes)
        self._write_text(',"summary":')
        self._write_json(summary)
        self._write_text("}")
        self.output.close()
        self.output = None
        self.tmp_path.replace(self.resolved_path)
        self.completed = True
        return self.payload_hash.hexdigest()

    def __exit__(self, exc_type, exc_value, traceback):
        if self.output is not None:
            self.output.close()
            self.output = None
        if not self.completed:
            try:
                self.tmp_path.unlink()
            except FileNotFoundError:
                pass

    def _write_json(self, value):
        for chunk in self.encoder.iterencode(value):
            self._write_text(chunk)

    def _write_text(self, value):
        encoded_value = value.encode("utf-8")
        self.payload_hash.update(encoded_value)
        self.output.write(encoded_value)


def iter_document_items(storage_path, granularity):
    resolved_path = resolve_storage_path(storage_path)
    with resolved_path.open("rb") as payload_file:
        yield from ijson.kvitems(payload_file, f"documents.{granularity}")


def cleanup_exported_payloads(collections=None, older_than_days=7):
    root = get_daily_payload_root()
    if not root.exists():
        return 0

    cutoff = (
        timezone.now() - timedelta(days=older_than_days)
        if older_than_days and older_than_days > 0
        else None
    )

    storage_path_to_job = {}
    db_queryset = DailyMetricJob.objects.exclude(storage_path="")
    if collections:
        db_queryset = db_queryset.filter(collection__acron3__in=collections)
    for job in db_queryset.iterator(chunk_size=500):
        storage_path_to_job[job.storage_path] = job

    json_files = root.rglob("*.json")
    if collections:
        json_files = [
            p for p in json_files if p.relative_to(root).parts[0] in collections
        ]

    deleted_count = 0
    for file_path in json_files:
        if cutoff and file_path.stat().st_mtime >= cutoff.timestamp():
            continue

        storage_path = file_path.relative_to(root).as_posix()
        job = storage_path_to_job.get(storage_path)

        if job is not None and job.status != DailyMetricJob.STATUS_EXPORTED:
            continue

        try:
            file_path.unlink()
        except FileNotFoundError:
            pass
        deleted_count += 1

        if job is not None:
            job.storage_path = ""
            job.payload_hash = ""
            job.save(update_fields=["storage_path", "payload_hash", "updated"])

    _cleanup_empty_dirs(root)

    logging.info(
        "Cleaned up %s daily payload files (collections=%s, older_than_days=%s).",
        deleted_count,
        collections or "all",
        older_than_days,
    )
    return deleted_count


def _cleanup_empty_dirs(root):
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if dirpath == str(root):
            continue
        try:
            os.rmdir(dirpath)
        except OSError:
            pass
