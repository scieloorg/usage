import calendar
from datetime import date

from counter_api.exceptions import insufficient_information, invalid_dates


def parse_period(params):
    begin_value = params.get("begin_date")
    end_value = params.get("end_date")
    if not begin_value or not end_value:
        raise insufficient_information("begin_date and end_date are required")

    begin = _parse_date(begin_value, first=True)
    end = _parse_date(end_value, first=False)
    if begin > end:
        raise invalid_dates("end_date must not be earlier than begin_date")
    if begin.day != 1:
        raise invalid_dates("begin_date must be the first day of a month")
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        raise invalid_dates("end_date must be the last day of a month")
    if end >= date.today().replace(day=1):
        raise invalid_dates("end_date must be earlier than the current month")

    return begin, end


def iter_months(begin, end):
    current = begin.replace(day=1)
    final = end.replace(day=1)

    while current <= final:
        yield current
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)


def _parse_date(value, first):
    if len(value) == 7:
        try:
            year, month = (int(part) for part in value.split("-"))
            day = 1 if first else calendar.monthrange(year, month)[1]
            return date(year, month, day)
        except (TypeError, ValueError):
            raise invalid_dates("dates must use YYYY-MM or YYYY-MM-DD")

    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise invalid_dates("dates must use YYYY-MM or YYYY-MM-DD")
