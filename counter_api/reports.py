from datetime import datetime, timezone

from django.conf import settings

from counter_api.constants import PROPRIETARY_NAMESPACE, RELEASE, REPORTS
from counter_api.parameters import report_parameters
from counter_api.report_items import build_report_items


def build_report(report_id, platform, begin, end, records, params, deadline=None):
    definition = REPORTS[report_id]
    params = report_parameters(report_id, params)
    report_items, metadata_exceptions = build_report_items(
        report_id,
        platform,
        begin,
        records,
        params,
        deadline,
    )

    exceptions = list(params.get("parameter_exceptions") or [])
    exceptions.extend(metadata_exceptions)
    exceptions.extend(
        _availability_exceptions(
            params.get("pending_months"),
            params.get("unavailable_months"),
            report_items,
            exceptions,
        )
    )

    if report_id == "pr":
        exceptions.append(
            {
                "Code": 3040,
                "Message": "Partial Data Returned",
                "Data": "Searches_Platform is not measured",
            }
        )

    header = _report_header(
        report_id,
        definition,
        platform,
        begin,
        end,
        params,
        exceptions,
    )

    return {
        "Report_Header": header,
        "Report_Items": report_items,
    }


def _report_header(report_id, definition, platform, begin, end, params, exceptions):
    attributes = _report_attributes(params)
    header = {
        "Report_Name": definition["name"],
        "Report_ID": report_id.upper(),
        "Release": RELEASE,
        "Institution_Name": settings.COUNTER_INSTITUTION_NAME,
        "Institution_ID": {
            "Proprietary": [f"{PROPRIETARY_NAMESPACE}:{settings.COUNTER_CUSTOMER_ID}"]
        },
        "Report_Filters": _report_filters(platform, begin, end, params),
        "Created": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "Created_By": settings.COUNTER_CREATED_BY,
        "Registry_Record": settings.COUNTER_REGISTRY_URL,
    }

    if attributes:
        header["Report_Attributes"] = attributes
    if exceptions:
        header["Exceptions"] = exceptions

    return header


def _report_filters(platform, begin, end, params):
    filters = {
        "Begin_Date": begin.isoformat(),
        "End_Date": end.isoformat(),
        "Platform": platform.acron3,
    }

    for name in ("Data_Type", "Access_Type", "Access_Method", "Metric_Type", "YOP"):
        if params.get(name):
            filters[name] = params[name]

    if params.get("Item_ID"):
        filters["Item_ID"] = params["Item_ID"]

    return filters


def _report_attributes(params):
    attributes = {}

    if params.get("Attributes_To_Show"):
        attributes["Attributes_To_Show"] = params["Attributes_To_Show"]
    if params.get("Exclude_Monthly_Details"):
        attributes["Granularity"] = "Totals"
    if params.get("Include_Parent_Details"):
        attributes["Include_Parent_Details"] = "True"

    return attributes


def _availability_exceptions(pending_months, unavailable_months, items, existing):
    exceptions = []

    if pending_months:
        months = "|".join(month.strftime("%Y-%m") for month in pending_months)
        exceptions.append(
            {
                "Code": 3031,
                "Message": "Usage Not Ready for Requested Dates",
                "Data": months,
            }
        )

    if unavailable_months:
        months = "|".join(month.strftime("%Y-%m") for month in unavailable_months)
        exceptions.append(
            {
                "Code": 3032,
                "Message": "Usage No Longer Available for Requested Dates",
                "Data": months,
            }
        )

    if not items and not exceptions and not existing:
        exceptions.append(
            {
                "Code": 3030,
                "Message": "No Usage Available for Requested Dates",
            }
        )

    return exceptions
