import logging
from collections import defaultdict

from log_manager import choices
from log_manager.models import LogFile
from reports.models import MonthlyLogReport, WeeklyLogReport, YearlyLogReport
from reports.services.dates import get_report_date_from_log_file

VALIDATED_FILE_STATUSES = {
    choices.LOG_FILE_STATUS_QUEUED,
    choices.LOG_FILE_STATUS_PARSING,
    choices.LOG_FILE_STATUS_PROCESSED,
}


def populate_log_report_tables(year=None, collection_acron=None):
    totals_by_period = _build_log_report_totals_by_period(
        year=year,
        collection_acron=collection_acron,
    )

    weekly_count = _upsert_log_report_records(
        WeeklyLogReport,
        totals_by_period["weekly"],
    )
    monthly_count = _upsert_log_report_records(
        MonthlyLogReport,
        totals_by_period["monthly"],
    )
    yearly_count = _upsert_log_report_records(
        YearlyLogReport,
        totals_by_period["yearly"],
    )

    logging.info(
        "Reports populated: %s weekly, %s monthly, %s yearly.",
        weekly_count,
        monthly_count,
        yearly_count,
    )

    return f"Weekly: {weekly_count}, Monthly: {monthly_count}, Yearly: {yearly_count}"


def _build_log_report_totals_by_period(year=None, collection_acron=None):
    totals_by_period = {
        "weekly": defaultdict(lambda: defaultdict(int)),
        "monthly": defaultdict(lambda: defaultdict(int)),
        "yearly": defaultdict(lambda: defaultdict(int)),
    }

    for log_file in _iter_reportable_log_files(collection_acron=collection_acron):
        report_date = get_report_date_from_log_file(log_file)
        if not report_date:
            continue

        if year and report_date.year != int(year):
            continue

        _add_log_file_to_period_totals(totals_by_period, log_file, report_date)

    return totals_by_period


def _iter_reportable_log_files(collection_acron=None):
    queryset = LogFile.objects.select_related("collection")

    if collection_acron:
        queryset = queryset.filter(collection__acron3=collection_acron)

    queryset = queryset.only(
        "id",
        "collection_id",
        "date",
        "path",
        "status",
        "summary",
        "validation",
    )

    return queryset.iterator(chunk_size=2000)


def _add_log_file_to_period_totals(totals_by_period, log_file, report_date):
    iso_year, iso_week, _ = report_date.isocalendar()

    period_keys = {
        "weekly": (log_file.collection_id, iso_year, iso_week),
        "monthly": (log_file.collection_id, report_date.year, report_date.month),
        "yearly": (log_file.collection_id, report_date.year),
    }

    for period_name, period_key in period_keys.items():
        totals = totals_by_period[period_name][period_key]
        _add_log_file_metrics_to_totals(totals, log_file)


def _add_log_file_metrics_to_totals(totals, log_file):
    totals["total_files"] += 1

    _add_log_file_status_to_totals(totals, log_file.status)
    _add_log_file_line_counts_to_totals(totals, log_file.summary or {})
    _add_log_file_ip_counts_to_totals(totals, log_file.validation or {})


def _add_log_file_status_to_totals(totals, status):
    if status == choices.LOG_FILE_STATUS_CREATED:
        totals["created_files"] += 1
        return

    if status in VALIDATED_FILE_STATUSES:
        totals["validated_files"] += 1
        return

    if status == choices.LOG_FILE_STATUS_INVALIDATED:
        totals["invalidated_files"] += 1
        return

    if status == choices.LOG_FILE_STATUS_ERROR:
        totals["errored_files"] += 1


def _add_log_file_line_counts_to_totals(totals, summary):
    lines_parsed = summary.get("lines_parsed", 0) or 0
    valid_lines = summary.get("valid_lines", 0) or 0

    totals["lines_parsed"] += lines_parsed
    totals["valid_lines"] += valid_lines
    totals["discarded_lines"] += max(lines_parsed - valid_lines, 0)


def _add_log_file_ip_counts_to_totals(totals, validation):
    ip_counts = validation.get("content", {}).get("summary", {}).get("ips", {})

    totals["ip_local_count"] += ip_counts.get("local", 0) or 0
    totals["ip_remote_count"] += ip_counts.get("remote", 0) or 0
    totals["ip_unknown_count"] += ip_counts.get("unknown", 0) or 0


def _upsert_log_report_records(model_class, totals_by_key):
    count = 0
    period_fields = _get_report_model_period_fields(model_class)

    for period_key, totals in totals_by_key.items():
        lookup = _build_log_report_record_lookup(period_fields, period_key)
        model_class.objects.update_or_create(defaults=totals, **lookup)
        count += 1

    return count


def _get_report_model_period_fields(model_class):
    unique_fields = list(model_class._meta.unique_together[0])
    return unique_fields[1:]


def _build_log_report_record_lookup(period_fields, period_key):
    lookup = {"collection_id": period_key[0]}
    period_values = period_key[1:]

    for idx, field_name in enumerate(period_fields):
        lookup[field_name] = period_values[idx]

    return lookup
