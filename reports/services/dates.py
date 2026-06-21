import re

from core.utils import date_utils


def get_report_date_from_log_file(log_file):
    if log_file.date:
        return log_file.date

    validation_date = (log_file.validation or {}).get("probably_date")
    if isinstance(validation_date, str) and validation_date:
        return date_utils.get_date_obj(validation_date)

    return _get_report_date_from_log_file_path(log_file.path)


def _get_report_date_from_log_file_path(path):
    try:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path)
    except TypeError:
        return None

    if not match:
        return None

    return date_utils.get_date_obj(match.group(1))
