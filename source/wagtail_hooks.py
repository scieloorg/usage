from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from source.models import Source


class SourceSnippetViewSet(SnippetViewSet):
    model = Source
    icon = "folder-open-inverse"
    menu_label = _("Source")
    menu_order = 200

    list_display = (
        "collection",
        "source_type",
        "source_id",
        "scielo_issn",
        "acronym",
        "title",
        "publication_year",
    )
    list_filter = (
        "collection",
        "source_type",
        "publication_year",
    )
    search_fields = (
        "source_id",
        "scielo_issn",
        "acronym",
        "title",
    )
