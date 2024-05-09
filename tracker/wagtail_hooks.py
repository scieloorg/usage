from django.utils.translation import gettext as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from .models import UnexpectedEvent, Hello


class UnexpectedEventSnippetViewSet(SnippetViewSet):
    model = UnexpectedEvent
    inspect_view_enabled = True
    menu_label = _("Unexpected Events")
    menu_icon = 100
    menu_order = get_menu_order("tracker")
    add_to_settings_menu = False
    exclude_from_explorer = False

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


class HelloSnippetViewSet(SnippetViewSet):
    model = Hello
    inspect_view_enabled = True
    menu_label = _("Hello Events")
    menu_icon = "folder"
    menu_order = 200
    add_to_settings_menu = False
    exclude_from_explorer = False

    list_display = (
        "status",
        "exception_type",
        "exception_msg",
        "traceback",
        "created",
    )
    list_filter = ("status", "exception_type",)
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


class UnexpectedEventSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = 'unexpected errors'
    menu_label = _("Unexpected Errors")
    menu_icon = "folder-open-inverse"
    menu_order = get_menu_order("unexpected-error")
    items = (UnexpectedEventSnippetViewSet, HelloSnippetViewSet)

register_snippet(UnexpectedEventSnippetViewSetGroup)
