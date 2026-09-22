from counter_api.availability import split_period
from counter_api.exceptions import CounterAPIError, service_unavailable
from counter_api.integrity import metric_invariant_errors
from counter_api.parameters import parse_parameters, report_parameters
from counter_api.query import ReportQuery
from counter_api.reports import build_report


def generate_report(report_id, platform, begin, end, query_params):
    months, pending, unavailable = split_period(platform, begin, end)
    params = parse_parameters(query_params, report_id)
    params["pending_months"] = pending
    params["unavailable_months"] = unavailable

    report_params = report_parameters(report_id, params)
    query = ReportQuery()

    if params.get("Item_ID"):
        try:
            item_field, item_key = query.resolve_item_filter(
                platform,
                report_id,
                params["Item_ID"],
            )
            report_params["Item_Key_Field"] = item_field
            report_params["Item_Key"] = item_key
        except CounterAPIError as error:
            if error.code not in {3060, 3061}:
                raise
            params["parameter_exceptions"].append(error.as_dict())

    records = query.fetch(
        platform,
        months,
        report_id,
        report_params,
    )

    payload = build_report(
        report_id,
        platform,
        begin,
        end,
        records,
        params,
        deadline=query.deadline,
    )

    if platform.collection_type == "books" and report_id in {"pr", "tr", "tr_b3"}:
        errors = metric_invariant_errors(payload)
        if errors:
            raise service_unavailable(f"Book metrics inconsistent: {errors[0]}")

    return payload, query.deadline
