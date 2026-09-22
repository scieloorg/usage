from django.urls import path

from counter_api import views

urlpatterns = [
    path("status", views.StatusView.as_view(), name="status"),
    path("members", views.MembersView.as_view(), name="members"),
    path("platforms", views.PlatformsView.as_view(), name="platforms"),
    path("reports", views.ReportsView.as_view(), name="reports"),
    path("reports/<str:report_id>", views.ReportView.as_view(), name="report"),
]
