from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from log_manager.models import (
    ApplicationConfig,
    CollectionConfig,
    CollectionLogFileDateCount,
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


class CollectionLogFileDateCountSet(SnippetViewSet):
    model = CollectionLogFileDateCount
    menu_label = _("Collection Log File Date Count")
    icon = "folder"
    menu_order = 400

    list_display = (
        "collection",
        "date",
        "year",
        "month",
        "existing_log_files",
        "required_log_files",
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
    menu_label = _("Log File")
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


class LogProcessedRowSnippetViewSet(SnippetViewSet):
    model = LogProcessedRow
    menu_label = _("Log Processed Row")
    icon = "folder"
    menu_order = 600

    list_display = (
        "action_name",
        "server_time",
        "created", 
        "log_file",
    )
    list_filter = ("log_file__collection", "browser_name")
    search_fields = ("action_name",)


class LogSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = 'log_manager'
    menu_label = _("Log Manager")
    menu_icon = "folder-open-inverse"
    menu_order = get_menu_order("log_manager")
    items = (
        ApplicationConfigSnippetViewSet, 
        CollectionConfigSnippetViewSet,
        LogFileDateSet,
        CollectionLogFileDateCountSet,
        LogFileSnippetViewSet, 
        LogProcessedRowSnippetViewSet, 
    )


register_snippet(LogSnippetViewSetGroup)
