WAGTAIL_MENU_APPS_ORDER = {
}


def get_menu_order(app_name):
    try:
        return WAGTAIL_MENU_APPS_ORDER[app_name]
    except:
        return 900
