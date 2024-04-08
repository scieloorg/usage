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


class CollectionConfigSnippetViewSet(SnippetViewSet):
    model = CollectionConfig
    menu_label = _("Collection Configuration")
    icon = "folder"
    menu_order = 200

    list_display = (
        "collection",
        "config_type",
        "value",
        "start_date",
        "end_date",
        "is_enabled",
    )
    list_filter = (
        "collection", 
        "config_type",
        "is_enabled",
    )
    search_fields = (
        "value",
    )


class LogFileDateSet(SnippetViewSet):
    model = LogFileDate
    menu_label = _("Log File Dates")
    icon = "folder"
    menu_order = 300

    list_display = (
        "date",
        "log_file",
    )
    list_filter = (
        "date",
        "log_file__collection",
    )
    search_fields = ()

