from django.urls import path

from counter_api.extensions.views import CapabilitiesView, DistributionView, RankingView

urlpatterns = [
    path("capabilities", CapabilitiesView.as_view(), name="extension-capabilities"),
    path("distribution", DistributionView.as_view(), name="extension-distribution"),
    path("ranking", RankingView.as_view(), name="extension-ranking"),
]
