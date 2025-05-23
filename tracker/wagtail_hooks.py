from django.utils.translation import gettext as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from .models import UnexpectedEvent, LogFileDiscardedLine, ArticleEvent


class UnexpectedEventSnippetViewSet(SnippetViewSet):
    model = UnexpectedEvent
    menu_label = _("Unexpected Events")
    icon = 'warning'
    menu_order = get_menu_order("tracker")
    add_to_admin_menu = False

    list_display = (
        "exception_type",
        "exception_msg",
        "traceback",
        "created",
    )
    list_filter = ("exception_type",)
    search_fields = (
        "exception_msg",
        "detail",
    )
    inspect_view_fields = (
        "exception_type",
        "exception_msg",
        "traceback",
        "detail",
        "created",
    )

class LogFileDiscardedLineSnippetViewSet(SnippetViewSet):
    model = LogFileDiscardedLine
    menu_label = _("Discarded Lines")
    icon = 'warning'
    menu_order = get_menu_order("tracker")
    add_to_admin_menu = False

    list_display = (
        "log_file",
        "data",
        "message",
        "handled",
    )
    list_filter = (
        "log_file__collection",
        "log_file", 
        "handled",
        "error_type"
    )
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

class ArticleEventSnippetViewSet(SnippetViewSet):
    model = ArticleEvent
    menu_label = _("Article Events")
    icon = 'warning'
    menu_order = get_menu_order("tracker")
    add_to_admin_menu = False

    list_display = (
        "event_type",
        "message",
        "data",
        "handled",
    )

    list_filter = (
        "event_type",
        "handled",
    )

    search_fields = (
        "message",
    )
    inspect_view_fields = (
        "event_type",
        "message",
        "data",
        "handled",
    )


class TrackerSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = 'tracker'
    menu_label = _("Tracker")
    icon = "folder-open-inverse"
    menu_order = get_menu_order("tracker")
    
    items = (
        UnexpectedEventSnippetViewSet,
        LogFileDiscardedLineSnippetViewSet,
        ArticleEventSnippetViewSet,
    )


register_snippet(TrackerSnippetViewSetGroup)
