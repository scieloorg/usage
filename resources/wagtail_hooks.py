from django.utils.translation import gettext_lazy as _
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from config.menu import get_menu_order

from resources.models import MMDB, RobotUserAgent


class RobotUserAgentSnippetViewSet(SnippetViewSet):
    model = RobotUserAgent
    icon = "folder"
    menu_label = _("Robot User Agent")
    menu_order = 300

    list_display = (
        "pattern",
        "source_labels",
        "is_active",
        "last_changed",
    )
    search_fields = (
        "pattern",
        "source_url",
    )
    list_filter = (
        "source_counter",
        "source_scielo",
        "is_active",
    )
    list_export = (
        "pattern",
        "source_counter",
        "source_scielo",
        "is_active",
        "source_url",
        "last_changed",
    )
    export_filename = "robots"


class MMDBSnippetViewSet(SnippetViewSet):
    model = MMDB
    icon = "folder"
    menu_label = _("MMDB")
    menu_order = 400

    list_display = (
        "id",
        "url",
    )


class ResourcesSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = "resources"
    menu_label = _("Resources")
    menu_icon = "folder-open-inverse"
    menu_order = get_menu_order("resources")
    items = (
        RobotUserAgentSnippetViewSet,
        MMDBSnippetViewSet,
    )


register_snippet(ResourcesSnippetViewSetGroup)
