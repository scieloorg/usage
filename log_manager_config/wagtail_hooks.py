from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from log_manager_config.models import LogManagerCollectionConfig


class LogManagerCollectionConfigSnippetViewSet(SnippetViewSet):
    model = LogManagerCollectionConfig
    menu_label = _("Log Manager Configurations")
    icon = "cogs"
    menu_order = 300

    list_display = (
        "collection",
        "sample_size",
        "buffer_size",
        "expected_logs_per_day",
        "updated",
    )
    list_filter = ("collection",)
    search_fields = ("collection__acron3",)
