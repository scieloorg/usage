WAGTAIL_MENU_APPS_ORDER = {
    "collection": 100,
    "log_manager": 200,
    "tasks": 300,
    "unexpected-error": 400,
}

def get_menu_order(app_name):
    try:
        return WAGTAIL_MENU_APPS_ORDER[app_name]
    except:
        return 900
