from django.urls import path

from counter_api.extensions.reports import ProvisionalReportView
from counter_api.extensions.views import CapabilitiesView, DistributionView, RankingView

urlpatterns = [
    path(
        "reports/<str:report_id>",
        ProvisionalReportView.as_view(),
        name="extension-provisional-report",
    ),
    path("capabilities", CapabilitiesView.as_view(), name="extension-capabilities"),
    path("distribution", DistributionView.as_view(), name="extension-distribution"),
    path("ranking", RankingView.as_view(), name="extension-ranking"),
]
