from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.snippets.models import register_snippet

from config.menu import get_menu_order

from .models import Journal


class JournalSnippetViewSet(SnippetViewSet):
    model = Journal
    icon = "folder-open-inverse"
    menu_name = "journal"
    menu_label = _("Journal")
    menu_order = get_menu_order('journal')
    add_to_admin_menu = True

    list_display = (
        "collection",
        "scielo_issn",
        "acronym",
        "title",
        "issns",
        "subject_areas",
        "wos_subject_areas",
    )
    list_filter = (
        "collection",
    )
    search_fields = (
        "issns",
        "acronym",
        "subject_areas",
        "wos_subject_areas",
    )


register_snippet(JournalSnippetViewSet)
