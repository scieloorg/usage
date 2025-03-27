from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from log_manager_config.models import (
    CollectionLogDirectory,
    CollectionLogFilesPerDay,
    CollectionEmail,
    CollectionValidationParameters,
    SupportedLogFile,
)


class CollectionLogDirectorySnippetViewSet(SnippetViewSet):
    model = CollectionLogDirectory
    menu_label = _("Collection Log Directory")
    icon = "folder"
    menu_order = 300

    list_display = (
        "collection",
        "directory_name",
        "path",
        "active",
    )
    list_filter = (
        "collection",
        "active",
    )
    search_fields = (
        "path",
    )


class CollectionLogFilesPerDaySnippetViewSet(SnippetViewSet):
    model = CollectionLogFilesPerDay
    menu_label = _("Collection Log Files Per Day")
    icon = "folder"
    menu_order = 400

    list_display = (
        "collection",
        "start_date",
        "end_date",
        "quantity",
    )
    list_filter = (
        "collection",
    )


class CollectionEmailSnippetViewSet(SnippetViewSet):
    model = CollectionEmail
    menu_label = _("Collection Email")
    icon = "folder"
    menu_order = 500

    list_display = (
        "collection",
        "name",
        "position",
        "email",
        "active",
    )
    list_filter = (
        "collection",
        "active",
    )
    search_fields = (
        "name", 
        "email"
    )

class CollectionValidationParametersSnippetViewSet(SnippetViewSet):
    model = CollectionValidationParameters
    menu_label = _("Collection Validation Parameters")
    icon = "folder"
    menu_order = 550

    list_display = (
        "collection",
        "sample_size",
        "buffer_size",
    )
    list_filter = (
        "collection",
    )

class SupportedLogFileSnippetViewSet(SnippetViewSet):
    model = SupportedLogFile
    menu_label = _("Supported Log File Formats")
    icon = "folder"
    menu_order = 600

    list_display = (
        "file_extension",
        "description",
    )


class LogManagerConfigSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = 'log_manager_config'
    menu_label = _("Log Manager Config")
    menu_icon = "folder-open-inverse"
    menu_order = get_menu_order("log_manager_config")
    items = (
        CollectionLogDirectorySnippetViewSet,
        CollectionLogFilesPerDaySnippetViewSet,
        CollectionEmailSnippetViewSet,
        CollectionValidationParametersSnippetViewSet,
        SupportedLogFileSnippetViewSet,
    )


register_snippet(LogManagerConfigSnippetViewSetGroup)
