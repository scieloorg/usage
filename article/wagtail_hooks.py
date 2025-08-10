from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from .models import Article


class ArticleSnippetViewSet(SnippetViewSet):
    model = Article
    icon = "folder-open-inverse"
    menu_name = "article"
    menu_label = _("Article")
    menu_order = get_menu_order("article")
    add_to_admin_menu = True

    list_display = (
        "collection",
        "scielo_issn",
        "pid_v2",
        "pid_v3",
        "pid_generic",
        "files",
        "publication_year",
    )
    list_filter = (
        "collection",
        "scielo_issn",
        "publication_year",
    )
    search_fields = (
        "scielo_issn",
        "pid_v2",
        "pid_v3",
        "pid_generic",
    )

register_snippet(ArticleSnippetViewSet)
