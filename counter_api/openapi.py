from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse
from rest_framework import serializers

from counter_api.constants import REPORTS

EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
COUNTER_AUTH = [{"CounterAPIKey": []}]


class ExceptionSerializer(serializers.Serializer):
    Code = serializers.IntegerField()
    Message = serializers.CharField()
    Data = serializers.CharField(required=False)


class StatusSerializer(serializers.Serializer):
    Service_Active = serializers.BooleanField()
    Note = serializers.CharField()
    Alerts = serializers.ListField(child=serializers.DictField())
    Registry_URL = serializers.URLField(required=False)


class MemberSerializer(serializers.Serializer):
    Customer_ID = serializers.CharField()
    Institution_Name = serializers.CharField()
    Institution_ID = serializers.DictField()


class PlatformSerializer(serializers.Serializer):
    Platform_Parameter = serializers.CharField()
    Platform_Name = serializers.CharField()
    Platform_Description = serializers.CharField()


class ReportDescriptorSerializer(serializers.Serializer):
    Report_ID = serializers.CharField()
    Release = serializers.CharField()
    Report_Name = serializers.CharField()
    Report_Description = serializers.CharField()
    Path = serializers.CharField()
    First_Month_Available = serializers.CharField()
    Last_Month_Available = serializers.CharField()


class ReportHeaderSerializer(serializers.Serializer):
    Report_Name = serializers.CharField()
    Report_ID = serializers.CharField()
    Release = serializers.CharField()
    Institution_Name = serializers.CharField()
    Institution_ID = serializers.DictField()
    Report_Filters = serializers.DictField()
    Report_Attributes = serializers.DictField(required=False)
    Exceptions = ExceptionSerializer(many=True, required=False)
    Created = serializers.DateTimeField()
    Created_By = serializers.CharField()
    Registry_Record = serializers.URLField(required=False)


class ReportItemSerializer(serializers.Serializer):
    Platform = serializers.CharField()
    Title = serializers.CharField(required=False)
    Item = serializers.CharField(required=False)
    Publisher = serializers.CharField(required=False)
    Item_ID = serializers.DictField(required=False)
    Attribute_Performance = serializers.ListField(child=serializers.DictField())


class CounterReportSerializer(serializers.Serializer):
    Report_Header = ReportHeaderSerializer()
    Report_Items = ReportItemSerializer(many=True)


CUSTOMER_PARAMETER = OpenApiParameter(
    name="customer_id",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Institution identifier. Current public customer: "
        f"{settings.COUNTER_CUSTOMER_ID}."
    ),
)
PLATFORM_PARAMETER = OpenApiParameter(
    name="platform",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Platform parameter returned by /r51/platforms, for example scl.",
)
BEGIN_DATE_PARAMETER = OpenApiParameter(
    name="begin_date",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=True,
    description="First reporting month in YYYY-MM or first-day YYYY-MM-DD format.",
)
END_DATE_PARAMETER = OpenApiParameter(
    name="end_date",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Last reporting month in YYYY-MM or last-day YYYY-MM-DD format.",
)
REPORT_ID_PARAMETER = OpenApiParameter(
    name="report_id",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.PATH,
    required=True,
    enum=list(REPORTS),
    description="COUNTER report identifier.",
)
FORMAT_PARAMETER = OpenApiParameter(
    name="format",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=["json", "xlsx", "tsv"],
    description="Response format. Defaults to json.",
)
ATTRIBUTES_PARAMETER = OpenApiParameter(
    name="attributes_to_show",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Pipe-separated attributes: Data_Type, YOP, Access_Type, Access_Method."
    ),
)
DATA_TYPE_PARAMETER = OpenApiParameter(
    name="data_type",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Pipe-separated COUNTER data types.",
)
ACCESS_TYPE_PARAMETER = OpenApiParameter(
    name="access_type",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Pipe-separated access types.",
)
ACCESS_METHOD_PARAMETER = OpenApiParameter(
    name="access_method",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Pipe-separated access methods.",
)
METRIC_TYPE_PARAMETER = OpenApiParameter(
    name="metric_type",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Pipe-separated COUNTER metric types.",
)
YOP_PARAMETER = OpenApiParameter(
    name="yop",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Pipe-separated publication years or ranges.",
)
ITEM_ID_PARAMETER = OpenApiParameter(
    name="item_id",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description=(
        "Exact item identifier for TR or IR, such as DOI:10.1234/example, "
        "Print_ISSN:1234-5678 or Proprietary:identifier."
    ),
)
EXCLUDE_MONTHLY_PARAMETER = OpenApiParameter(
    name="exclude_monthly_details",
    type=OpenApiTypes.BOOL,
    location=OpenApiParameter.QUERY,
    required=False,
    description="For TSV and XLSX, omit monthly columns and retain the total.",
)
GRANULARITY_PARAMETER = OpenApiParameter(
    name="granularity",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=["Month", "Totals"],
    description="For JSON, return monthly counts or reporting-period totals.",
)
INCLUDE_PARENT_PARAMETER = OpenApiParameter(
    name="include_parent_details",
    type=OpenApiTypes.BOOL,
    location=OpenApiParameter.QUERY,
    required=False,
    description="For IR, group items under their journal or book parent.",
)

MEMBER_PARAMETERS = [CUSTOMER_PARAMETER]
REPORT_CATALOG_PARAMETERS = [
    CUSTOMER_PARAMETER,
    PLATFORM_PARAMETER,
]
REPORT_PARAMETERS = [
    CUSTOMER_PARAMETER,
    PLATFORM_PARAMETER,
    BEGIN_DATE_PARAMETER,
    END_DATE_PARAMETER,
    REPORT_ID_PARAMETER,
    FORMAT_PARAMETER,
    ATTRIBUTES_PARAMETER,
    DATA_TYPE_PARAMETER,
    ACCESS_TYPE_PARAMETER,
    ACCESS_METHOD_PARAMETER,
    METRIC_TYPE_PARAMETER,
    YOP_PARAMETER,
    ITEM_ID_PARAMETER,
    EXCLUDE_MONTHLY_PARAMETER,
    GRANULARITY_PARAMETER,
    INCLUDE_PARENT_PARAMETER,
]

REPORT_RESPONSES = {
    (200, "application/json"): CounterReportSerializer,
    (200, EXCEL_CONTENT_TYPE): OpenApiTypes.BINARY,
    (200, "text/tab-separated-values"): OpenApiTypes.BINARY,
    400: ExceptionSerializer,
    401: ExceptionSerializer,
    403: ExceptionSerializer,
    404: OpenApiResponse(description="Report unavailable for the platform."),
    503: ExceptionSerializer,
}
