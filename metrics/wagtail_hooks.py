from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order
from .models import Top100Articles, Top100ArticlesFile


class Top100ArticlesSnippetViewSet(SnippetViewSet):
    model = Top100Articles
    menu_label = _("Top 100 Articles")
    icon = "list-ol"
    menu_order = 100

    list_display = (
        'collection',
        'pid_issn',
        'pid',
        'yop',
        'year_month_day',
        'total_item_requests',
        'total_item_investigations',
        'unique_item_requests',
        'unique_item_investigations',
    )
    list_filter = (
        "collection",
        "pid_issn",
        'yop',
        'year_month_day',
    )
    search_fields = (
        "pid",
    )


class Top100ArticlesFileSnippetViewSet(SnippetViewSet):
    model = Top100ArticlesFile
    menu_label = _("Top 100 Articles File")
    icon = "list-ol"
    menu_order = 100

    list_display = (
        'attachment',
        'get_status_display',
        'creator',
        'created',
        'updated',
    )
    list_filter = (
        "status",
    )


class MetricsViewSetGroup(SnippetViewSetGroup):
    menu_name = 'metrics'
    menu_label = _("Usage Metrics")
    icon = "folder-open-inverse"
    menu_order = get_menu_order("metrics")
    
    items = (
        Top100ArticlesSnippetViewSet, 
        Top100ArticlesFileSnippetViewSet,
    )


register_snippet(MetricsViewSetGroup)
