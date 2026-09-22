import inspect
import json

from celery import current_app
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from wagtail.admin import messages

from django_celery_beat import models


def execute_task(periodic_task, user=None):
    current_app.loader.import_default_modules()
    task = current_app.tasks.get(periodic_task.task)
    if task is None:
        return False

    kwargs = json.loads(periodic_task.kwargs)
    signature = inspect.signature(task.run)
    if user and "user_id" in signature.parameters:
        kwargs["user_id"] = user.id

    task.apply_async(
        args=json.loads(periodic_task.args),
        kwargs=kwargs,
        queue=periodic_task.queue,
        periodic_task_name=periodic_task.name,
    )

    return True


@permission_required("django_celery_beat.change_periodictask", raise_exception=True)
def task_run(request):
    """
    View funciton to run the task by PeriodicTask id.
    """

    task_id = int(request.GET.get("task_id", None))

    p_task = get_object_or_404(models.PeriodicTask, pk=task_id)

    if not execute_task(p_task, request.user):
        messages.error(
            request,
            _("Task '{0}' not found in the Celery registry.").format(p_task.task),
        )
        return redirect(
            request.META.get("HTTP_REFERER") or reverse("wagtailadmin_home")
        )

    messages.success(request, _("Task {0} was successfully run").format(p_task.name))

    return redirect(request.META.get("HTTP_REFERER") or reverse("wagtailadmin_home"))
