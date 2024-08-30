from django.utils.translation import gettext as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from .models import (
    UnexpectedEvent, 
    Top100ArticlesFileEvent
)


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


class Top100ArticlesFileEventSnippetViewSet(SnippetViewSet):
    model = Top100ArticlesFileEvent
    menu_label = _("Top100 Articles File Events")
    icon = 'warning'
    menu_order = get_menu_order("tracker")
    add_to_admin_menu = False

    list_display = (
        "file",
        "status",
        "lines",
        "message",
        "created",
    )
    list_filter = (
        "status",
        "lines",
    )
    search_fields = (
        "file",
        "created",
    )


class TrackerViewSetGroup(SnippetViewSetGroup):
    menu_name = 'tracker'
    menu_label = _("Tracker")
    icon = "folder-open-inverse"
    menu_order = get_menu_order("tracker")
    
    items = (
        UnexpectedEventSnippetViewSet, 
        Top100ArticlesFileEventSnippetViewSet,
    )


register_snippet(TrackerViewSetGroup)