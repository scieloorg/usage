"""File: core/wagtail_hooks.py."""

from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks


HIDDEN_MAIN_MENU_ITEMS = {
    "documents",
    "explorer",
    "images",
    "reports",
    "snippets",
}


@hooks.register("insert_global_admin_css", order=100)
def global_admin_css():
    """Add /static/css/custom.css to the admin."""
    """Add /static/admin/css/custom.css to the admin."""
    return format_html(
        '<link rel="stylesheet" href="{}">', static("admin/css/custom.css")
    )


@hooks.register("insert_global_admin_js", order=100)
def global_admin_js():
    """Add /static/css/custom.js to the admin."""
    """Add /static/admin/css/custom.js to the admin."""
    return format_html('<script src="{}"></script>', static("admin/js/custom.js"))


@hooks.register("construct_homepage_summary_items", order=1)
def remove_all_summary_items(request, items):
    items.clear()


@hooks.register("construct_main_menu")
def hide_generic_main_menu_items(request, menu_items):
    menu_items[:] = [
        item for item in menu_items if item.name not in HIDDEN_MAIN_MENU_ITEMS
    ]
