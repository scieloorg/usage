from django.utils.translation import gettext as _
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from config.menu import get_menu_order
from document.wagtail_hooks import DocumentSnippetViewSet
from source.wagtail_hooks import SourceSnippetViewSet
from .models import Collection


class CollectionSnippetViewSet(SnippetViewSet):
    model = Collection
    icon = "folder-open-inverse"
    menu_label = _("Collection")
    menu_order = 100

    list_display = (
        "main_name",
        "acron3",
        "acron2",
        "code",
        "status",
        "collection_type",
        "is_active",
        "updated",
        "created",
    )
    list_filter = (
        "status",
        "collection_type",
        "is_active",
        "has_analytics",
    )
    search_fields = (
        "acron3",
        "acron2",
        "code",
        "domain",
        "name__text",
        "main_name",
    )
    list_export = (
        "acron3",
        "acron2",
        "code",
        "domain",
        "main_name",
        "status",
        "has_analytics",
        "collection_type",
        "is_active",
        "foundation_date",
        "creator",
        "updated",
        "created",
        "updated_by",
    )
    export_filename = "collections"


class MetadataSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = "metadata"
    menu_label = _("Metadata")
    menu_icon = "folder-open-inverse"
    menu_order = get_menu_order("metadata")
    items = (
        CollectionSnippetViewSet,
        SourceSnippetViewSet,
        DocumentSnippetViewSet,
    )


register_snippet(MetadataSnippetViewSetGroup)
