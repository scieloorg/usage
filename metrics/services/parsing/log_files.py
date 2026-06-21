from datetime import timedelta

from django.utils import timezone

from log_manager import choices
from log_manager.models import LogFile
from tracker.models import LogFileDiscardedLine


def mark_logs_as_parsing(log_files):
    now = timezone.now()
    LogFile.objects.filter(pk__in=[log_file.pk for log_file in log_files]).update(
        status=choices.LOG_FILE_STATUS_PARSING,
        summary={},
        last_processed_line=0,
        parse_heartbeat_at=now,
        updated=now,
    )


def clear_discarded_lines(log_files):
    LogFileDiscardedLine.objects.filter(
        log_file_id__in=[log_file.pk for log_file in log_files]
    ).delete()


def mark_log_file_completed(log_file, log_parser, summary):
    log_file.summary = {
        "parsing_completed": True,
        "lines_parsed": summary["lines_parsed"],
        "valid_lines": summary["valid_lines"],
    }
    log_file.last_processed_line = log_parser.stats.lines_parsed
    log_file.parse_heartbeat_at = timezone.now()
    log_file.save(
        update_fields=[
            "summary",
            "last_processed_line",
            "parse_heartbeat_at",
            "updated",
        ]
    )


def touch_parse_heartbeat(log_file, last_processed_line=None):
    heartbeat_at = timezone.now()
    update_kwargs = {
        "parse_heartbeat_at": heartbeat_at,
        "updated": heartbeat_at,
    }
    if last_processed_line is not None:
        update_kwargs["last_processed_line"] = last_processed_line or 0
        log_file.last_processed_line = last_processed_line or 0

    LogFile.objects.filter(pk=log_file.pk).update(**update_kwargs)
    log_file.parse_heartbeat_at = heartbeat_at


def is_stale_parsing_log(log_file, stale_after_minutes=60):
    if log_file.status != choices.LOG_FILE_STATUS_PARSING:
        return False

    if not log_file.parse_heartbeat_at:
        return True

    cutoff = timezone.now() - timedelta(minutes=stale_after_minutes)
    return log_file.parse_heartbeat_at < cutoff


def requeue_stale_parsing_log(log_file):
    now = timezone.now()
    LogFile.objects.filter(pk=log_file.pk).update(
        status=choices.LOG_FILE_STATUS_ERROR,
        parse_heartbeat_at=None,
        updated=now,
    )
    log_file.status = choices.LOG_FILE_STATUS_ERROR
    log_file.parse_heartbeat_at = None
