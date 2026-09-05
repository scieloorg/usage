from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from wagtail.permission_policies.base import BasePermissionPolicy
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from reports.models import MonthlyLogReport, WeeklyLogReport, YearlyLogReport


class ReadOnlyPermissionPolicy(BasePermissionPolicy):
    def user_has_permission(self, user, action):
        if action in ("add", "change", "delete"):
            return False
        return True

    def users_with_any_permission(self, actions):
        return get_user_model().objects.filter(is_active=True)


COMMON_LIST_DISPLAY = (
    "total_files",
    "created_files",
    "validated_files",
    "invalidated_files",
    "errored_files",
    "pct_validated",
    "lines_parsed",
    "pct_valid_lines",
    "pct_remote_ip",
    "generated_at",
)


class WeeklyLogReportSnippetViewSet(SnippetViewSet):
    model = WeeklyLogReport
    menu_label = _("Weekly")
    icon = "info-circle"
    menu_order = 100
    list_display = ("collection", "year", "week") + COMMON_LIST_DISPLAY
    list_filter = ("collection", "year", "week")
    search_fields = ("collection__acron3",)
    permission_policy = ReadOnlyPermissionPolicy(WeeklyLogReport)


class MonthlyLogReportSnippetViewSet(SnippetViewSet):
    model = MonthlyLogReport
    menu_label = _("Monthly")
    icon = "info-circle"
    menu_order = 200
    list_display = ("collection", "year", "month") + COMMON_LIST_DISPLAY
    list_filter = ("collection", "year", "month")
    search_fields = ("collection__acron3",)
    permission_policy = ReadOnlyPermissionPolicy(MonthlyLogReport)


class YearlyLogReportSnippetViewSet(SnippetViewSet):
    model = YearlyLogReport
    menu_label = _("Yearly")
    icon = "info-circle"
    menu_order = 300
    list_display = ("collection", "year") + COMMON_LIST_DISPLAY
    list_filter = ("collection", "year")
    search_fields = ("collection__acron3",)
    permission_policy = ReadOnlyPermissionPolicy(YearlyLogReport)


class ReportsSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = "usage_reports"
    menu_label = _("Reports")
    menu_icon = "info-circle"
    menu_order = 350
    items = (
        WeeklyLogReportSnippetViewSet,
        MonthlyLogReportSnippetViewSet,
        YearlyLogReportSnippetViewSet,
    )


register_snippet(ReportsSnippetViewSetGroup)
