from django.conf import settings

from counter_api.constants import METRICS, STANDARD_VIEWS, TITLE_METRICS
from counter_api.exceptions import CounterAPIError
from counter_api.yop import valid_yop

FILTERS = {
    "data_type": "Data_Type",
    "access_type": "Access_Type",
    "access_method": "Access_Method",
    "metric_type": "Metric_Type",
    "yop": "YOP",
}
ATTRIBUTES = {
    "exclude_monthly_details": "Exclude_Monthly_Details",
    "include_parent_details": "Include_Parent_Details",
}
ATTRIBUTE_NAMES = {"Data_Type", "YOP", "Access_Type", "Access_Method"}
DATA_TYPES = {
    "Article",
    "Book",
    "Book_Segment",
    "Dataset",
    "Journal",
    "Reference_Work",
    "Unspecified",
}
FILTER_VALUES = {
    "Data_Type": DATA_TYPES,
    "Access_Type": {"Controlled", "Free_To_Read", "Open"},
    "Access_Method": {"Regular", "TDM"},
    "Metric_Type": {*METRICS, *TITLE_METRICS},
}
REPORT_FILTERS = {
    "pr": {"Data_Type", "Access_Method", "Metric_Type"},
    "tr": set(FILTERS.values()),
    "ir": set(FILTERS.values()),
    "tr_j3": set(),
    "tr_b3": set(),
}


def parse_parameters(query_params, report_id=None):
    params = {}
    exceptions = []
    unsupported = []
    standard_view = report_id in STANDARD_VIEWS

    attributes_to_show = query_params.get("attributes_to_show")
    if attributes_to_show and standard_view:
        unsupported.append("attributes_to_show")
    elif attributes_to_show:
        requested = [item for item in attributes_to_show.split("|") if item]
        invalid = [item for item in requested if item not in ATTRIBUTE_NAMES]
        if invalid:
            exceptions.append(
                {
                    "Code": 3062,
                    "Message": "Invalid ReportAttribute Value",
                    "Data": "|".join(invalid),
                }
            )

        params["Attributes_To_Show"] = [
            item for item in requested if item in ATTRIBUTE_NAMES
        ]

    invalid_filters = []
    allowed_filters = REPORT_FILTERS.get(report_id, set(FILTERS.values()))

    for external, internal in FILTERS.items():
        value = query_params.get(external)
        if not value:
            continue
        if internal not in allowed_filters:
            unsupported.append(external)
            continue

        requested = [item for item in value.split("|") if item]
        if internal == "YOP":
            valid = [item for item in requested if valid_yop(item)]
        else:
            valid = [item for item in requested if item in FILTER_VALUES[internal]]

        invalid_filters.extend(item for item in requested if item not in valid)
        if valid:
            params[internal] = valid

    if invalid_filters:
        exceptions.append(
            {
                "Code": 3060,
                "Message": "Invalid ReportFilter Value",
                "Data": "|".join(invalid_filters),
            }
        )

    item_id = query_params.get("item_id")
    if item_id and report_id in {"tr", "ir"}:
        params["Item_ID"] = item_id
    elif item_id:
        unsupported.append("item_id")

    for external, internal in ATTRIBUTES.items():
        value = query_params.get(external)
        if value is None:
            continue
        if standard_view:
            unsupported.append(external)
            continue
        if value.lower() not in {"true", "false"}:
            exceptions.append(
                {
                    "Code": 3062,
                    "Message": "Invalid ReportAttribute Value",
                    "Data": external,
                }
            )
            continue

        enabled = value.lower() == "true"
        if internal == "Include_Parent_Details" and enabled and report_id != "ir":
            exceptions.append(
                {
                    "Code": 3062,
                    "Message": "Invalid ReportAttribute Value",
                    "Data": external,
                }
            )
            continue

        params[internal] = enabled

    output_format = query_params.get("format")
    if output_format and output_format not in {"json", "xlsx", "tsv"}:
        exceptions.append(
            {
                "Code": 3060,
                "Message": "Invalid ReportFilter Value",
                "Data": "format",
            }
        )

    recognized = {
        "api_key",
        "customer_id",
        "platform",
        "begin_date",
        "end_date",
        "format",
        "item_id",
        "attributes_to_show",
        *FILTERS,
        *ATTRIBUTES,
    }
    unsupported = sorted(set(unsupported) | (set(query_params) - recognized))
    if unsupported:
        exceptions.append(
            {
                "Code": 3050,
                "Message": "Parameter Not Recognized in this Context",
                "Data": "|".join(unsupported),
            }
        )

    params["parameter_exceptions"] = exceptions

    return params


def validate_customer(query_params):
    customer_id = query_params.get("customer_id")
    if customer_id and customer_id != settings.COUNTER_CUSTOMER_ID:
        raise CounterAPIError(
            2010,
            "Requestor is Not Authorized to Access Usage for Institution",
            403,
            customer_id,
        )


def report_parameters(report_id, params):
    result = dict(params)
    result.update(STANDARD_VIEWS.get(report_id, {}).get("filters") or {})

    return result
