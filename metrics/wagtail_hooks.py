from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order
from .models import Item, ItemAccess, UserSession, UserAgent


class ItemSnippetViewSet(SnippetViewSet):
    model = Item
    menu_label = _("Item")
    icon = "list-ol"
    menu_order = 100

    list_display = (
        'collection',
        'journal',
        'article',
    )
    list_filter = (
        "collection",
        "journal",
    )
    search_fields = (
        "journal",
        "article",
    )


class ItemAccessSnippetViewSet(SnippetViewSet):
    model = ItemAccess
    menu_label = _("Item Access")
    icon = "list-ol"
    menu_order = 200

    list_display = (
        'item',
        'user_session',
        'country_code',
        'media_language',
        'media_format',
        'content_type',
        'click_timestamps',
    )
    list_filter = (
        "item",
        "item__collection",
        "item__journal",       
        "country_code",
        "media_language",
        "media_format",
        "content_type",
    )
    search_fields = (
        "item",
    )


class UserSessionSnippetViewSet(SnippetViewSet):
    model = UserSession
    menu_label = _("User Session")
    icon = "list-ol"
    menu_order = 300

    list_display = (
        'datetime',
        'user_agent',
        'user_ip',
    )
    list_filter = (
        "datetime",
    )
    search_fields = (
        "user_agent",
        "user_ip",
    )


class UserAgentSnippetViewSet(SnippetViewSet):
    model = UserAgent
    menu_label = _("User Agent")
    icon = "list-ol"
    menu_order = 400

    list_display = (
        'name',
        'version',
    )
    search_fields = (
        "name",
    )


class MetricsViewSetGroup(SnippetViewSetGroup):
    menu_name = 'metrics'
    menu_label = _("Metrics")
    icon = "folder-open-inverse"
    menu_order = get_menu_order("metrics")
    
    items = (
        ItemAccessSnippetViewSet,
        ItemSnippetViewSet,
        UserSessionSnippetViewSet,
        UserAgentSnippetViewSet,
    )


register_snippet(MetricsViewSetGroup)
