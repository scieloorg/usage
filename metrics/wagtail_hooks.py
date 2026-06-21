from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from metrics.models import DailyMetricJob


class DailyMetricJobSnippetViewSet(SnippetViewSet):
    model = DailyMetricJob
    menu_label = _("Daily Metric Jobs")
    icon = "history"
    menu_order = 600
    list_display = (
        "collection",
        "access_date",
        "status",
        "input_log_count",
        "attempts",
        "export_started_at",
        "exported_at",
        "updated",
    )
    list_filter = ("status", "collection", "access_date")
    search_fields = ("collection__acron3", "error_message")
