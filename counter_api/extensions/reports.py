from functools import partial

from drf_spectacular.utils import extend_schema, extend_schema_view

from counter_api.extensions.dates import parse_provisional_period
from counter_api.extensions.openapi import ProvisionalReportSerializer
from counter_api.generation import generate_report
from counter_api.openapi import REPORT_PARAMETERS, REPORT_RESPONSES
from counter_api.views import ReportView


@extend_schema_view(
    get=extend_schema(
        tags=["SciELO extensions"],
        operation_id="extension_provisional_report",
        summary="Generate a provisional Usage report with monthly coverage",
        description=(
            "Not a COUNTER-compliant report. Reuses PR, TR, TR_J3, TR_B3 and IR "
            "filters and formats. Always includes confirmed daily contributions "
            "in incomplete months, including the current month. No coverage_policy "
            "parameter is needed; strict and invalid values are rejected. Periods must span "
            "full calendar months; future months through December of the current "
            "year are coverage-only, never zero usage. Coverage describes collection "
            "processing, not completeness of the source. JSON, XLSX and TSV retain "
            "coverage and warnings. Standard COUNTER routes are unchanged."
        ),
        parameters=REPORT_PARAMETERS,
        responses={
            **REPORT_RESPONSES,
            (200, "application/json"): ProvisionalReportSerializer,
        },
    )
)
class ProvisionalReportView(ReportView):
    period_parser = staticmethod(parse_provisional_period)
    report_generator = staticmethod(partial(generate_report, provisional=True))
    filename_prefix = "provisional_"
