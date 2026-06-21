WAGTAIL_MENU_APPS_ORDER = {
    "metadata": 100,
    "resources": 200,
    "log_manager": 300,
    "tracker": 400,
    "metrics": 500,
    "tasks": 600,
}


def get_menu_order(app_name):
    try:
        return WAGTAIL_MENU_APPS_ORDER[app_name]
    except KeyError:
        return 950
