from calendar import monthrange
from datetime import date

from counter_api.dates import parse_period_inputs
from counter_api.exceptions import insufficient_information, invalid_dates
from counter_api.extensions.contracts import SEGMENT_DIMENSIONS
from counter_api.extensions.query import validate_segmented_period


def parse_provisional_period(params):
    if params.get("coverage_policy", "allow_partial") != "allow_partial":
        raise insufficient_information("Provisional reports only support allow_partial")

    begin, end = parse_period_inputs(params)
    if begin.day != 1 or end.day != monthrange(end.year, end.month)[1]:
        raise invalid_dates("Provisional reports require full calendar months")

    today = date.today()
    if begin > today or end.year > today.year:
        raise invalid_dates("Period must start by today and end by the current year")

    return begin, end


def parse_analytics_period(params):
    begin, end = parse_period_inputs(params)
    today = date.today()

    dimensions = {
        part.strip()
        for name in ("group_by", "dimension")
        for part in params.get(name, "").split(",")
    }
    dimensions.update(key for key in SEGMENT_DIMENSIONS if params.get(key))

    segmented = validate_segmented_period(
        begin, end, dimensions, params.get("metric_type", "Total_Item_Requests")
    )

    if segmented:
        if begin.day != 1 or end.day != monthrange(end.year, end.month)[1]:
            raise invalid_dates("Segmented periods must cover full calendar years")
        if end.year > today.year:
            raise invalid_dates("end_date must not be later than the current year")
    else:
        if (
            len(params["end_date"]) == 7
            and end.year == today.year
            and end.month == today.month
        ):
            end = today

        if end > today:
            raise invalid_dates("end_date must not be later than today")
        if begin > end:
            raise invalid_dates("end_date must not be earlier than begin_date")

    return begin, end
