from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from document.models import Document


class DocumentSnippetViewSet(SnippetViewSet):
    model = Document
    icon = "folder-open-inverse"
    menu_label = _("Document")
    menu_order = 300

    list_display = (
        "collection",
        "document_type",
        "document_id",
        "source",
        "title",
        "pid_v2",
        "pid_v3",
        "pid_generic",
        "publication_year",
    )
    list_filter = (
        "collection",
        "document_type",
        "publication_year",
    )
    search_fields = (
        "document_id",
        "title",
        "pid_v2",
        "pid_v3",
        "pid_generic",
    )
