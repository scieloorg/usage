import gc
import logging
from time import monotonic

from django.conf import settings

from config.collections import get_collection_size
from log_manager.models import LogFile
from metrics.counter.access.daily_accumulator import DailyAccessAccumulator
from metrics.counter.indexing import converter as index_docs
from metrics.services import daily_payloads, memory
from metrics.services.parsing import metadata_cache
from metrics.services.parsing.environment import setup_parsing_environment
from metrics.services.parsing.lines import process_line
from metrics.services.parsing.log_files import (
    clear_discarded_lines,
    mark_log_file_completed,
    mark_logs_as_parsing,
    touch_parse_heartbeat,
)
from tracker.models import LogFileDiscardedLine


def build_daily_metric_job_payload(job, robots_list, mmdb, track_errors=False):
    input_log_hashes = sorted(job.input_log_hashes or [])
    log_files = _get_job_log_files(job, input_log_hashes)
    results = DailyAccessAccumulator()
    summary = _initial_summary(log_files, input_log_hashes)

    mark_logs_as_parsing(log_files)
    clear_discarded_lines(log_files)

    parsing_started = monotonic()
    for log_file in log_files:
        log_summary = _parse_log_file_into_results(
            log_file=log_file,
            results=results,
            robots_list=robots_list,
            mmdb=mmdb,
            track_errors=track_errors,
        )
        _merge_log_summary(summary, log_summary)
    logging.info(
        "Daily metric job %s parsing completed in %.3f seconds; "
        "%s compact records; %s.",
        job.pk,
        monotonic() - parsing_started,
        len(results),
        memory.format_snapshot(),
    )

    if get_collection_size(job.collection.acron3) == "xlarge":
        metadata_cache.clear()
        gc.collect()
        logging.info(
            "Daily metric job %s released parsing metadata cache; %s.",
            job.pk,
            memory.format_snapshot(),
        )

    return _write_job_payload(job, results, summary)


def _get_job_log_files(job, input_log_hashes):
    if not input_log_hashes:
        raise RuntimeError(f"Daily metric job {job.pk} has no input log hashes.")

    log_files = LogFile.for_collection_date_hashes(
        collection=job.collection,
        access_date=job.access_date,
        log_hashes=input_log_hashes,
    )
    found_hashes = {log_file.hash for log_file in log_files if log_file.hash}
    missing_hashes = sorted(set(input_log_hashes) - found_hashes)
    if missing_hashes:
        raise RuntimeError(
            f"Daily metric job {job.pk} is missing log files for "
            f"{job.collection.acron3} {job.access_date}: "
            f"{', '.join(missing_hashes)}."
        )
    return log_files


def _initial_summary(log_files, input_log_hashes):
    return {
        "log_files": len(log_files),
        "input_log_hashes": input_log_hashes,
        "lines_parsed": 0,
        "valid_lines": 0,
        "discarded_lines": 0,
    }


def _parse_log_file_into_results(
    log_file, results, robots_list, mmdb, track_errors=False
):
    log_parser, url_translator_manager = setup_parsing_environment(
        log_file=log_file,
        robots_list=robots_list,
        mmdb=mmdb,
    )
    heartbeat_interval_seconds = getattr(
        settings,
        "METRICS_PARSE_HEARTBEAT_INTERVAL_SECONDS",
        30,
    )
    summary = {
        "lines_parsed": 0,
        "valid_lines": 0,
        "discarded_lines": 0,
    }
    errors = []
    last_heartbeat_monotonic = monotonic()

    for line in log_parser.parse():
        summary["lines_parsed"] += 1
        if monotonic() - last_heartbeat_monotonic >= heartbeat_interval_seconds:
            touch_parse_heartbeat(log_file, log_parser.stats.lines_parsed)
            last_heartbeat_monotonic = monotonic()

        is_valid_line, error_obj = process_line(
            results=results,
            line=line,
            utm=url_translator_manager,
            log_file=log_file,
            track_errors=track_errors,
        )
        if is_valid_line:
            summary["valid_lines"] += 1
        else:
            summary["discarded_lines"] += 1
            if error_obj:
                errors.append(error_obj)

    if errors:
        LogFileDiscardedLine.objects.bulk_create(errors)

    mark_log_file_completed(log_file, log_parser, summary)
    return summary


def _merge_log_summary(summary, log_summary):
    summary["lines_parsed"] += log_summary["lines_parsed"]
    summary["valid_lines"] += log_summary["valid_lines"]
    summary["discarded_lines"] += log_summary["discarded_lines"]


def _write_job_payload(job, results, summary):
    storage_path = daily_payloads.build_daily_storage_path(
        job.collection,
        job.access_date,
    )
    month_document_count = 0
    year_document_count = 0
    payload_started = monotonic()

    with daily_payloads.DailyPayloadWriter(
        storage_path=storage_path,
        collection=job.collection.acron3,
        access_date=job.access_date.isoformat(),
    ) as writer:
        month_started = monotonic()
        month_documents = index_docs.iter_partitioned_documents(
            results,
            "month",
        )
        month_document_count = writer.write_document_items("month", month_documents)
        month_conversion_seconds = monotonic() - month_started
        gc.collect()
        logging.info(
            "Daily metric job %s monthly conversion and serialization completed "
            "in %.3f seconds; %s documents; %s.",
            job.pk,
            month_conversion_seconds,
            month_document_count,
            memory.format_snapshot(),
        )

        year_started = monotonic()
        year_documents = index_docs.iter_partitioned_documents(
            results,
            "year",
        )
        year_document_count = writer.write_document_items("year", year_documents)
        del results
        payload_hash = writer.finalize(summary["input_log_hashes"], summary)
        year_conversion_seconds = monotonic() - year_started
        gc.collect()
        logging.info(
            "Daily metric job %s yearly conversion and serialization completed "
            "in %.3f seconds; %s documents; %s.",
            job.pk,
            year_conversion_seconds,
            year_document_count,
            memory.format_snapshot(),
        )

    logging.info(
        "Daily metric job %s payload generation completed in %.3f seconds; " "%s.",
        job.pk,
        monotonic() - payload_started,
        memory.format_snapshot(),
    )

    job.input_log_hashes = summary["input_log_hashes"]
    job.storage_path = storage_path.as_posix()
    job.payload_hash = payload_hash
    job.summary = {
        **summary,
        "month_document_count": month_document_count,
        "year_document_count": year_document_count,
    }
    job.save(
        update_fields=[
            "input_log_hashes",
            "storage_path",
            "payload_hash",
            "summary",
            "updated",
        ]
    )
    return storage_path.as_posix(), payload_hash
