from django.utils.translation import gettext as _
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from config.menu import get_menu_order

from tracker.models import LogFileDiscardedLine


class LogFileDiscardedLineSnippetViewSet(SnippetViewSet):
    model = LogFileDiscardedLine
    menu_label = _("Discarded Lines")
    icon = "warning"
    menu_order = get_menu_order("tracker")
    add_to_admin_menu = False

    list_display = (
        "log_file",
        "data",
        "message",
        "handled",
    )
    list_filter = ("log_file__collection", "log_file", "handled", "error_type")
    search_fields = (
        "data",
        "message",
    )
    inspect_view_fields = (
        "log_file",
        "error_type",
        "data",
        "message",
        "handled",
    )


class TrackerSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = "tracker"
    menu_label = _("Tracker")
    icon = "folder-open-inverse"
    menu_order = get_menu_order("tracker")

    items = (LogFileDiscardedLineSnippetViewSet,)


register_snippet(TrackerSnippetViewSetGroup)
