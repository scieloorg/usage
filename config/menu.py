WAGTAIL_MENU_APPS_ORDER = {
    "collection": 100,
    "metrics": 200,
    "log_manager": 300,
    "tasks": 400,
    "unexpected-error": 500,
}

def get_menu_order(app_name):
    try:
        return WAGTAIL_MENU_APPS_ORDER[app_name]
    except:
        return 900
