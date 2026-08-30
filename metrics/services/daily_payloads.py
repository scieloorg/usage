import hashlib
import json
import logging
import os
from datetime import timedelta
from pathlib import Path

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


def write_payload(storage_path, payload):
    resolved_path = resolve_storage_path(storage_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    encoder = json.JSONEncoder(
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload_hash = hashlib.sha256()
    tmp_path = resolved_path.with_suffix(f"{resolved_path.suffix}.tmp")

    try:
        with tmp_path.open("wb") as output:
            for chunk in encoder.iterencode(payload):
                encoded_chunk = chunk.encode("utf-8")
                payload_hash.update(encoded_chunk)
                output.write(encoded_chunk)
        tmp_path.replace(resolved_path)
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise

    return payload_hash.hexdigest()


def read_payload(storage_path):
    resolved_path = resolve_storage_path(storage_path)
    return json.loads(resolved_path.read_text(encoding="utf-8"))


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
