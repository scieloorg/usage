from django.utils.translation import gettext as _
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from .models import UnexpectedEvent


class UnexpectedEventSnippetViewSet(SnippetViewSet):
    model = UnexpectedEvent
    menu_label = _("Unexpected Events")
    icon = 'warning'
    menu_order = get_menu_order("tracker")
    add_to_admin_menu = True

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


register_snippet(UnexpectedEventSnippetViewSet)
