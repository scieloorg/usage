from django.conf import settings
from django.db.models import Case, Value, When
from django.template.defaultfilters import pluralize
from django.urls import include, path, reverse
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.widgets import Button
from wagtail.snippets.bulk_actions.snippet_bulk_action import SnippetBulkAction
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import (
    IndexView,
    SnippetViewSet,
    SnippetViewSetGroup,
)

from config.menu import get_menu_order
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    PeriodicTasks,
    SolarSchedule,
)
from django_celery_beat.schedulers import is_database_scheduler
from django_celery_beat.views import execute_task


class PeriodicTaskIndexView(IndexView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scheduler = getattr(settings, "CELERY_BEAT_SCHEDULER", None)
        context["wrong_scheduler"] = not is_database_scheduler(scheduler)

        return context


class PeriodicTaskSnippetViewSet(SnippetViewSet):
    model = PeriodicTask
    icon = "cog"
    menu_label = _("Periodic tasks")
    menu_order = 100
    index_view_class = PeriodicTaskIndexView
    index_template_name = "django_celery_beat/periodic_task_index.html"
    list_display = (
        "__str__",
        "enabled",
        "interval",
        "start_time",
        "last_run_at",
        "one_off",
    )
    list_filter = ("enabled", "one_off", "task")
    search_fields = ("name",)

    def get_queryset(self, request):
        return self.model.objects.select_related(
            "interval", "crontab", "solar", "clocked"
        )


class CrontabScheduleSnippetViewSet(SnippetViewSet):
    model = CrontabSchedule
    icon = "date"
    menu_label = _("Crontab schedules")
    menu_order = 200


class IntervalScheduleSnippetViewSet(SnippetViewSet):
    model = IntervalSchedule
    icon = "date"
    menu_label = _("Interval schedules")
    menu_order = 300


class ClockedScheduleSnippetViewSet(SnippetViewSet):
    model = ClockedSchedule
    icon = "time"
    menu_label = _("Clocked schedules")
    menu_order = 400
    list_display = ("clocked_time",)
    form_fields = ("clocked_time",)


class SolarScheduleSnippetViewSet(SnippetViewSet):
    model = SolarSchedule
    icon = "date"
    menu_label = _("Solar schedules")
    menu_order = 500


class TasksSnippetViewSetGroup(SnippetViewSetGroup):
    menu_name = "tasks"
    menu_label = _("Tasks")
    menu_icon = "cogs"
    menu_order = get_menu_order("tasks")
    items = (
        PeriodicTaskSnippetViewSet,
        CrontabScheduleSnippetViewSet,
        IntervalScheduleSnippetViewSet,
        ClockedScheduleSnippetViewSet,
        SolarScheduleSnippetViewSet,
    )


register_snippet(TasksSnippetViewSetGroup)


class PeriodicTaskBulkAction(SnippetBulkAction):
    template_name = "wagtailadmin/bulk_actions/confirmation/base.html"
    models = [PeriodicTask]

    def check_perm(self, obj):
        return self.request.user.has_perm("django_celery_beat.change_periodictask")

    def get_success_message(self, num_parent_objects, num_child_objects):
        return _("{0} task{1} {2} successfully {3}").format(
            num_parent_objects,
            pluralize(num_parent_objects),
            pluralize(num_parent_objects, _("was,were")),
            self.success_verb,
        )


@hooks.register("register_bulk_action")
class EnableTasksBulkAction(PeriodicTaskBulkAction):
    display_name = _("Enable")
    aria_label = _("Enable selected tasks")
    action_type = "enable_periodic_tasks"
    success_verb = _("enabled")

    @classmethod
    def execute_action(cls, objects, **kwargs):
        rows_updated = objects.update(enabled=True)
        PeriodicTasks.update_changed()

        return rows_updated, 0


@hooks.register("register_bulk_action")
class DisableTasksBulkAction(PeriodicTaskBulkAction):
    display_name = _("Disable")
    aria_label = _("Disable selected tasks")
    action_type = "disable_periodic_tasks"
    success_verb = _("disabled")

    @classmethod
    def execute_action(cls, objects, **kwargs):
        rows_updated = objects.update(enabled=False, last_run_at=None)
        PeriodicTasks.update_changed()

        return rows_updated, 0


@hooks.register("register_bulk_action")
class ToggleTasksBulkAction(PeriodicTaskBulkAction):
    display_name = _("Toggle")
    aria_label = _("Toggle selected tasks")
    action_type = "toggle_periodic_tasks"
    success_verb = _("toggled")

    @classmethod
    def execute_action(cls, objects, **kwargs):
        rows_updated = objects.update(
            enabled=Case(
                When(enabled=True, then=Value(False)),
                default=Value(True),
            )
        )
        PeriodicTasks.update_changed()

        return rows_updated, 0


@hooks.register("register_bulk_action")
class RunTasksBulkAction(PeriodicTaskBulkAction):
    display_name = _("Run")
    aria_label = _("Run selected tasks")
    action_type = "run_periodic_tasks"
    success_verb = _("run")

    @classmethod
    def execute_action(cls, objects, **kwargs):
        action = kwargs["self"]
        tasks_run = 0
        for task in objects:
            if execute_task(task, action.request.user):
                tasks_run += 1

        return tasks_run, 0


@hooks.register("register_snippet_listing_buttons")
def register_periodic_task_run_button(snippet, user, next_url=None):
    if not isinstance(snippet, PeriodicTask) or not user.has_perm(
        "django_celery_beat.change_periodictask"
    ):
        return

    yield Button(
        label=_("Run"),
        url=reverse("django_celery_beat:task_run") + f"?task_id={snippet.pk}",
        icon_name="play",
        priority=10,
    )


@hooks.register("register_admin_urls")
def register_task_url():
    return [
        path(
            "django_celery_beat/tasks/",
            include("django_celery_beat.urls", namespace="django_celery_beat"),
        ),
    ]
