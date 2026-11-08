from calendar import monthrange

from django.conf import settings
from opensearchpy import NotFoundError

from counter_api.dates import iter_months
from counter_api.exceptions import insufficient_information, service_unavailable
from counter_api.painless import CONFIRMED_DAYS_SUM_SCRIPT
from counter_api.search import search
from metrics.opensearch.names import generate_month_status_index_name


def resolve_coverage(client, platform, begin, end, policy, segmented, deadline):
    if policy not in {"strict", "allow_partial"}:
        raise insufficient_information()

    if policy == "strict":
        return None

    months = {
        month.strftime("%Y-%m"): monthrange(month.year, month.month)[1]
        for month in iter_months(begin, end)
    }
    body = {
        "size": len(months),
        "query": {
            "ids": {"values": [f"{platform.acron3}:{month}" for month in months]}
        },
    }

    try:
        response = search(
            client,
            generate_month_status_index_name(settings.OPENSEARCH_INDEX_NAME),
            body,
            deadline,
        )
        markers = {
            hit["_source"]["month"]: hit["_source"] for hit in response["hits"]["hits"]
        }
    except NotFoundError:
        markers = {}

    details = []

    for month, day_count in months.items():
        days = range(1, day_count + 1)
        marker = markers.get(month)
        confirmed = []
        missing = None
        status = "unknown"

        if marker is not None:
            mask = marker.get("day_mask")
            full = (1 << day_count) - 1
            if (
                marker.get("collection") != platform.acron3
                or type(mask) is not int
                or not 0 <= mask <= full
                or type(marker.get("complete")) is not bool
                or marker["complete"] != (mask == full)
            ):
                raise service_unavailable(f"Invalid coverage marker for {month}")

            confirmed = [day for day in days if mask & (1 << (day - 1))]
            missing = [day for day in days if day not in confirmed]
            status = (
                "complete" if not missing else "partial" if confirmed else "unavailable"
            )

        details.append(
            {
                "month": month,
                "status": status,
                "confirmed_days": confirmed,
                "missing_days": missing,
            }
        )

    included = [item["month"] for item in details if item["confirmed_days"]]
    complete = all(item["status"] == "complete" for item in details)

    if not segmented and not included:
        raise service_unavailable("No confirmed usage days in requested period")

    return {
        "policy": policy,
        "status": "complete" if complete else "partial",
        "basis": "available_annual_totals" if segmented else "confirmed_days",
        "included_months": None if segmented else included,
        "months": details,
    }


def coverage_fields(coverage):
    if coverage is None:
        return {}

    warnings = []

    if coverage["basis"] == "available_annual_totals":
        warnings.append(
            "Available annual totals may change as data arrives or processing completes. "
            "Coverage is informative and does not restrict the days included in these totals."
        )
    elif coverage["status"] != "complete":
        warnings.append(
            "Partial coverage: counts include only confirmed days; missing or unknown days are not zero usage."
        )

    return {"coverage": coverage, "warnings": warnings}


def metric_sum(metric, coverage):
    partial = (
        {
            item["month"]: [f"{day:02d}" for day in item["confirmed_days"]]
            for item in coverage["months"]
            if item["status"] == "partial"
        }
        if coverage
        else {}
    )
    if not partial:
        return {"field": metric}

    return {
        "script": {
            "source": CONFIRMED_DAYS_SUM_SCRIPT,
            "params": {
                "metric": metric,
                "complete": [
                    item["month"]
                    for item in coverage["months"]
                    if item["status"] == "complete"
                ],
                "days": partial,
            },
        }
    }
