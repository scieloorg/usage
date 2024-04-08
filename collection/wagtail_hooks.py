from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _
from wagtail.contrib.modeladmin.options import ModelAdmin, modeladmin_register
from wagtail.contrib.modeladmin.views import CreateView

from .models import Collection


class CollectionCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class CollectionAdmin(ModelAdmin):
    model = Collection
    create_view_class = CollectionCreateView
    inspect_view_enabled = True
    menu_label = _("Collection")
    menu_icon = "folder-open-inverse"
    menu_order = 1
    add_to_settings_menu = False
    exclude_from_explorer = (
        False
    )
    list_display = (
        "main_name",
        "acron3",
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


modeladmin_register(CollectionAdmin)
