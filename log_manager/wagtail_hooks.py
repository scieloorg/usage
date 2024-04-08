from django.utils.translation import gettext_lazy as _

from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from log_manager.models import (
    ApplicationConfig,
    CollectionConfig,
    LogFile,
    LogFileDate,
    LogProcessedRow,
)


class ApplicationConfigSnippetViewSet(SnippetViewSet):
    model = ApplicationConfig
    menu_label = _("Application Configuration")
    icon = "folder"
    menu_order = 100

    list_display = (
        "config_type",
        "value",
        "created",
        "is_enabled",
        "version_number",
    )
    list_filter = (
        "config_type",
        "is_enabled",
    )
    search_fields = (
        "value",
    )
