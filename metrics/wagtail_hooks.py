from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from metrics.models import (
    Top100Articles,
)


class Top100Articles(SnippetViewSet):
    model = Top100Articles
    menu_label = _("Top 100 Articles")
    icon = "folder"
    menu_order = 100

    list_display = (
        'collection',
        'key_issn',
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
        "key_issn",
        'yop',
        'year_month_day',
    )
    search_fields = (
        "pid",
    )


class MetricsViewSetGroup(SnippetViewSetGroup):
    menu_name = 'metrics'
    menu_label = _("Usage Metrics")
    menu_icon = "folder-open-inverse"
    menu_order = get_menu_order("metrics")
    items = (
        Top100Articles, 
    )


register_snippet(MetricsViewSetGroup)
