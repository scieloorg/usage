import logging

from metrics.counter.access import accumulation, extraction, validation
from tracker.choices import (
    LOG_FILE_DISCARDED_LINE_REASON_MISSING_DOCUMENT,
    LOG_FILE_DISCARDED_LINE_REASON_MISSING_SOURCE,
)
from tracker.models import LogFileDiscardedLine

TRACKED_VALIDATION_ERROR_CODES = {
    "invalid_scielo_issn",
    "invalid_source_id",
    "invalid_pid_v3",
    "invalid_pid_v2",
    "invalid_pid_generic",
}


def process_line(results, line, utm, log_file, track_errors=False):
    try:
        translated_url = utm.translate(line.get("url"))
    except Exception as exc:
        logging.error("Error translating URL %s: %s", line.get("url"), exc)
        return False, None

    try:
        counter_access = extraction.extract(
            log_file.collection.acron3,
            translated_url,
        )
    except Exception as exc:
        logging.error(
            "Error extracting COUNTER access from URL %s: %s", line.get("url"), exc
        )
        return False, None

    ignore_utm_validation = not track_errors
    is_valid, check_result = validation.is_valid(
        counter_access,
        utm,
        ignore_utm_validation,
    )

    if not is_valid:
        return _build_discarded_line_error(
            track_errors=track_errors,
            check_result=check_result,
            log_file=log_file,
            line=line,
            counter_access=counter_access,
        )

    try:
        accumulation.accumulate(
            results,
            counter_access,
            line,
        )
    except Exception as exc:
        logging.error(
            "Error updating metrics results for URL %s: %s",
            line.get("url"),
            exc,
        )
        return False, None

    return True, None


def _build_discarded_line_error(
    track_errors,
    check_result,
    log_file,
    line,
    counter_access,
):
    if not track_errors:
        return False, None

    error_code = check_result.get("code")
    if error_code not in TRACKED_VALIDATION_ERROR_CODES:
        return False, None

    tracker_error_type = (
        LOG_FILE_DISCARDED_LINE_REASON_MISSING_DOCUMENT
        if "pid" in error_code
        else LOG_FILE_DISCARDED_LINE_REASON_MISSING_SOURCE
    )

    return False, LogFileDiscardedLine.create(
        log_file=log_file,
        error_type=tracker_error_type,
        message=check_result.get("message"),
        data={"line": line, "item_access_data": counter_access},
        save=False,
    )
