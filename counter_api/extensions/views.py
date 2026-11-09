import logging

from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response

from counter_api.access import CounterAPIView
from counter_api.availability import available_months
from counter_api.constants import METRICS
from counter_api.exceptions import (
    CounterAPIError,
    insufficient_information,
    service_unavailable,
)
from counter_api.extensions.contracts import (
    DISTRIBUTION_CAPABILITIES,
    DOWNLOAD_FORMATS,
    RANKING_ENTITIES,
)
from counter_api.extensions.dates import parse_analytics_period
from counter_api.extensions.distribution import DistributionQuery
from counter_api.extensions.exports import build_export
from counter_api.extensions.openapi import (
    CapabilitiesSerializer,
    DistributionSerializer,
    RankingSerializer,
)
from counter_api.extensions.ranking import DEFAULT_GROUP_LIMIT, RankingQuery
from counter_api.openapi import (
    EXCEL_CONTENT_TYPE,
    PLATFORM_PARAMETER,
    ExceptionSerializer,
)
from counter_api.platforms import get_platform

BEGIN_DATE_PARAMETER = OpenApiParameter(
    "begin_date",
    OpenApiTypes.STR,
    required=True,
    description="First day (YYYY-MM-DD) or month (YYYY-MM). Country/language must start in January.",
)
END_DATE_PARAMETER = OpenApiParameter(
    "end_date",
    OpenApiTypes.STR,
    required=True,
    description=(
        "Last day (YYYY-MM-DD) or month (YYYY-MM). The current month ends today; "
        "explicit future days are rejected. Country/language must end in December "
        "and may select the current year for provisional annual totals."
    ),
)

COVERAGE_PARAMETER = OpenApiParameter(
    "coverage_policy",
    OpenApiTypes.STR,
    enum=["strict", "allow_partial"],
    default="allow_partial",
    description=(
        "Use confirmed days for monthly counts and available annual totals for "
        "country/language. Use strict to require complete coverage."
    ),
)


def _download_response(payload, kind, platform, output_format):
    content = build_export(payload, kind, output_format)
    content_type = "text/csv" if output_format == "csv" else EXCEL_CONTENT_TYPE
    response = FileResponse(content, content_type=content_type)
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{kind}_{platform.acron3}.{output_format}"'

    return response


class RankingView(CounterAPIView):
    @extend_schema(
        tags=["SciELO extensions"],
        auth=[],
        operation_id="extension_ranking",
        summary="Rank descendants of a collection, journal or book",
        parameters=[
            PLATFORM_PARAMETER,
            BEGIN_DATE_PARAMETER,
            END_DATE_PARAMETER,
            OpenApiParameter("parent_type", OpenApiTypes.STR, required=True),
            OpenApiParameter("parent_id", OpenApiTypes.STR, required=True),
            OpenApiParameter("entity_type", OpenApiTypes.STR, required=True),
            OpenApiParameter("metric_type", OpenApiTypes.STR, required=False),
            COVERAGE_PARAMETER,
            OpenApiParameter("group_by", OpenApiTypes.STR, required=False),
            OpenApiParameter("country", OpenApiTypes.STR, required=False),
            OpenApiParameter("language", OpenApiTypes.STR, required=False),
            OpenApiParameter("yop", OpenApiTypes.STR, required=False),
            OpenApiParameter("subject_area", OpenApiTypes.STR, required=False),
            OpenApiParameter(
                "limit",
                OpenApiTypes.INT,
                required=False,
                default=100,
                description="Items per group (1–1000), ranked after aggregating the full period.",
            ),
            OpenApiParameter(
                "group_limit",
                OpenApiTypes.INT,
                required=False,
                default=DEFAULT_GROUP_LIMIT,
                description="Groups per page (1–20), only with group_by. group_limit × limit must not exceed 10000.",
            ),
            OpenApiParameter(
                "cursor",
                OpenApiTypes.STR,
                required=False,
                description=(
                    "Opaque next_cursor from a grouped ranking, with the same filters and period. "
                    "Follow it even if a page has no visible groups. Limits and output format may change."
                ),
            ),
            OpenApiParameter("format", OpenApiTypes.STR, required=False),
        ],
        responses={
            200: RankingSerializer,
            (200, "text/csv"): OpenApiTypes.BINARY,
            (200, EXCEL_CONTENT_TYPE): OpenApiTypes.BINARY,
            400: ExceptionSerializer,
            503: ExceptionSerializer,
        },
    )
    def get(self, request):
        try:
            output_format = request.query_params.get("format", "json")
            if output_format not in DOWNLOAD_FORMATS:
                raise insufficient_information()

            platform = get_platform(request.query_params.get("platform"))
            begin, end = parse_analytics_period(request.query_params)
            payload = RankingQuery().run(platform, begin, end, request.query_params)

            if output_format != "json":
                return _download_response(
                    payload,
                    "ranking",
                    platform,
                    output_format,
                )
        except CounterAPIError as error:
            return Response(error.as_dict(), status=error.status_code)
        except Exception:
            logging.exception("COUNTER extension ranking failed")
            error = service_unavailable()
            return Response(error.as_dict(), status=error.status_code)

        return Response(payload)


class CapabilitiesView(CounterAPIView):
    @extend_schema(
        tags=["SciELO extensions"],
        auth=[],
        operation_id="extension_capabilities",
        summary="Discover SciELO extension capabilities for a platform",
        parameters=[PLATFORM_PARAMETER],
        responses={200: CapabilitiesSerializer, 400: ExceptionSerializer},
    )
    def get(self, request):
        try:
            platform = get_platform(request.query_params.get("platform"))
            months = available_months(platform, complete_only=False)
        except CounterAPIError as error:
            return Response(error.as_dict(), status=error.status_code)

        relations = [
            {"entity_type": entity, "parent_type": relation["parent_type"]}
            for entity, relation in RANKING_ENTITIES.items()
            if relation["collection_type"] == platform.collection_type
        ]
        return Response(
            {
                "platform": platform.acron3,
                "ranking_relations": relations,
                "ranking_metrics": list(METRICS),
                "ranking_dimensions": ["country", "language"],
                "download_formats": list(DOWNLOAD_FORMATS),
                "distribution_dimensions": list(DISTRIBUTION_CAPABILITIES),
                "country_language_granularity": "year",
                "other_granularity": "day",
                "first_month_available": (
                    months[0].strftime("%Y-%m") if months else None
                ),
                "last_month_available": (
                    months[-1].strftime("%Y-%m") if months else None
                ),
            }
        )


class DistributionView(CounterAPIView):
    @extend_schema(
        tags=["SciELO extensions"],
        auth=[],
        operation_id="extension_distribution",
        summary="Distribute accesses by one dimension or a supported pair",
        parameters=[
            PLATFORM_PARAMETER,
            BEGIN_DATE_PARAMETER,
            END_DATE_PARAMETER,
            OpenApiParameter("entity_type", OpenApiTypes.STR, required=True),
            OpenApiParameter("entity_id", OpenApiTypes.STR, required=True),
            OpenApiParameter("dimension", OpenApiTypes.STR, required=True),
            COVERAGE_PARAMETER,
            OpenApiParameter("metric_type", OpenApiTypes.STR, required=False),
            OpenApiParameter("format", OpenApiTypes.STR, required=False),
        ],
        responses={
            200: DistributionSerializer,
            (200, "text/csv"): OpenApiTypes.BINARY,
            (200, EXCEL_CONTENT_TYPE): OpenApiTypes.BINARY,
            400: ExceptionSerializer,
            503: ExceptionSerializer,
        },
    )
    def get(self, request):
        try:
            output_format = request.query_params.get("format", "json")
            if output_format not in DOWNLOAD_FORMATS:
                raise insufficient_information()

            platform = get_platform(request.query_params.get("platform"))
            begin, end = parse_analytics_period(request.query_params)
            payload = DistributionQuery().run(
                platform, begin, end, request.query_params
            )

            if output_format != "json":
                return _download_response(
                    payload,
                    "distribution",
                    platform,
                    output_format,
                )
        except CounterAPIError as error:
            return Response(error.as_dict(), status=error.status_code)
        except Exception:
            logging.exception("COUNTER extension distribution failed")
            error = service_unavailable()
            return Response(error.as_dict(), status=error.status_code)

        return Response(payload)
