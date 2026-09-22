import logging

from django.conf import settings
from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from counter_api.access import CounterAPIView, get_authentication_error
from counter_api.availability import available_months
from counter_api.constants import PROPRIETARY_NAMESPACE, RELEASE, REPORTS
from counter_api.dates import parse_period
from counter_api.exceptions import CounterAPIError, service_unavailable
from counter_api.generation import generate_report
from counter_api.openapi import (
    COUNTER_AUTH,
    EXCEL_CONTENT_TYPE,
    MEMBER_PARAMETERS,
    REPORT_CATALOG_PARAMETERS,
    REPORT_PARAMETERS,
    REPORT_RESPONSES,
    ExceptionSerializer,
    MemberSerializer,
    PlatformSerializer,
    ReportDescriptorSerializer,
    StatusSerializer,
)
from counter_api.parameters import validate_customer
from counter_api.platforms import get_platform, list_platforms
from counter_api.tabular import build_tsv, build_workbook


class StatusView(CounterAPIView):
    @extend_schema(
        tags=["Service"],
        auth=[],
        operation_id="counter_status",
        summary="Check COUNTER service status",
        responses={200: StatusSerializer},
    )
    def get(self, request):
        payload = {
            "Service_Active": True,
            "Note": "SciELO COUNTER API",
            "Alerts": [],
        }
        registry_url = getattr(settings, "COUNTER_REGISTRY_URL", "")
        if registry_url:
            payload["Registry_URL"] = registry_url

        return Response(payload)


class MembersView(CounterAPIView):
    @extend_schema(
        tags=["Discovery"],
        auth=COUNTER_AUTH,
        operation_id="counter_members",
        summary="List COUNTER customers",
        parameters=MEMBER_PARAMETERS,
        responses={
            200: MemberSerializer(many=True),
            401: ExceptionSerializer,
            403: ExceptionSerializer,
        },
    )
    def get(self, request):
        authentication_error = get_authentication_error(request)
        if authentication_error:
            return authentication_error

        try:
            validate_customer(request.query_params)
        except CounterAPIError as error:
            return Response(error.as_dict(), status=error.status_code)

        payload = [
            {
                "Customer_ID": settings.COUNTER_CUSTOMER_ID,
                "Institution_Name": settings.COUNTER_INSTITUTION_NAME,
                "Institution_ID": {
                    "Proprietary": [
                        f"{PROPRIETARY_NAMESPACE}:{settings.COUNTER_CUSTOMER_ID}"
                    ]
                },
            }
        ]

        return Response(payload)


class PlatformsView(CounterAPIView):
    @extend_schema(
        tags=["Discovery"],
        auth=COUNTER_AUTH,
        operation_id="counter_platforms",
        summary="List SciELO COUNTER platforms",
        responses={
            200: PlatformSerializer(many=True),
            401: ExceptionSerializer,
        },
    )
    def get(self, request):
        authentication_error = get_authentication_error(request)
        if authentication_error:
            return authentication_error

        return Response(list_platforms())


class ReportsView(CounterAPIView):
    @extend_schema(
        tags=["Discovery"],
        auth=COUNTER_AUTH,
        operation_id="counter_reports",
        summary="List reports available for a platform",
        parameters=REPORT_CATALOG_PARAMETERS,
        responses={
            200: ReportDescriptorSerializer(many=True),
            400: ExceptionSerializer,
            401: ExceptionSerializer,
            403: ExceptionSerializer,
            503: ExceptionSerializer,
        },
    )
    def get(self, request):
        authentication_error = get_authentication_error(request)
        if authentication_error:
            return authentication_error

        try:
            validate_customer(request.query_params)
            platform = get_platform(request.query_params.get("platform"))
        except CounterAPIError as error:
            return Response(error.as_dict(), status=error.status_code)

        try:
            months = available_months(platform)
        except CounterAPIError as error:
            return Response(error.as_dict(), status=error.status_code)
        if not months:
            return Response([])

        first_month = months[0].strftime("%Y-%m")
        last_month = months[-1].strftime("%Y-%m")
        payload = []

        for report_id, definition in REPORTS.items():
            if platform.collection_type not in definition["collections"]:
                continue
            payload.append(
                {
                    "Report_ID": report_id.upper(),
                    "Release": RELEASE,
                    "Report_Name": definition["name"],
                    "Report_Description": definition["name"],
                    "Path": f"/r51/reports/{report_id}",
                    "First_Month_Available": first_month,
                    "Last_Month_Available": last_month,
                }
            )

        return Response(payload)


class ReportView(CounterAPIView):
    @extend_schema(
        tags=["Reports"],
        auth=COUNTER_AUTH,
        operation_id="counter_report",
        summary="Generate a COUNTER R5.1 report",
        description=(
            "Returns COUNTER JSON by default. Set format=xlsx or format=tsv "
            "for a tabular download. PR omits Searches_Platform and "
            "reports COUNTER exception 3040."
        ),
        parameters=REPORT_PARAMETERS,
        responses=REPORT_RESPONSES,
    )
    def get(self, request, report_id):
        authentication_error = get_authentication_error(request)
        if authentication_error:
            return authentication_error

        try:
            validate_customer(request.query_params)
            platform = get_platform(request.query_params.get("platform"))
            definition = REPORTS.get(report_id)
            if (
                not definition
                or platform.collection_type not in definition["collections"]
            ):
                return Response({}, status=404)

            begin, end = parse_period(request.query_params)
            payload, deadline = generate_report(
                report_id,
                platform,
                begin,
                end,
                request.query_params,
            )

            output_format = request.query_params.get("format")
            if output_format in {"xlsx", "tsv"}:
                if output_format == "xlsx":
                    content = build_workbook(payload, deadline=deadline)
                    content_type = EXCEL_CONTENT_TYPE
                else:
                    content = build_tsv(payload, deadline=deadline)
                    content_type = "text/tab-separated-values"

                response = FileResponse(content, content_type=content_type)
                filename = (
                    f"{report_id}_{platform.acron3}_{begin:%Y%m}_{end:%Y%m}."
                    f"{output_format}"
                )
                response["Content-Disposition"] = f'attachment; filename="{filename}"'

                return response
        except CounterAPIError as error:
            return Response(error.as_dict(), status=error.status_code)
        except Exception:
            logging.exception("COUNTER report generation failed")
            exception = service_unavailable()

            return Response(exception.as_dict(), status=exception.status_code)

        return Response(payload)
