from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from log_manager.models import (
    CollectionLogFileDateCount,
    LogFile,
    LogFileDate,
)


class LogFileDateViewSet(SnippetViewSet):
    model = LogFileDate
    menu_label = _("Log Files per Day")
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


class CollectionLogFileDateCountViewSet(SnippetViewSet):
    model = CollectionLogFileDateCount
    menu_label = _("Expected and Found Log Files")
    icon = "folder"
    menu_order = 400

    list_display = (
        "collection",
        "date",
        "year",
        "month",
        "found_log_files",
        "expected_log_files",
        "status",
    )
    list_filter = (
        "collection",
        "status",
        "year",
        "month"
    )


class LogFileSnippetViewSet(SnippetViewSet):
    model = LogFile
    menu_label = _("Log File Status")
    icon = "folder"
    menu_order = 500
    list_display = (
        "path",
        "stat_result",
        "collection", 
        "status", 
        "hash"
    )
    list_filter = ("status", "collection")
    search_fields = ("file",)


class LogSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = 'log_manager'
    menu_label = _("Log Manager")
    menu_icon = "folder-open-inverse"
    menu_order = get_menu_order("log_manager")
    items = (
        LogFileDateViewSet,
        CollectionLogFileDateCountViewSet,
        LogFileSnippetViewSet, 
    )


register_snippet(LogSnippetViewSetGroup)
