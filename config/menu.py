WAGTAIL_MENU_APPS_ORDER = {
    "collection": 100,
    "article": 200,
    "journal": 300,
    "resources": 400,
    "log_manager": 500,
    "log_manager_config": 600,
    "metrics": 700,
    "tasks": 800,
    "unexpected-error": 900,
}

def get_menu_order(app_name):
    try:
        return WAGTAIL_MENU_APPS_ORDER[app_name]
    except:
        return 950
