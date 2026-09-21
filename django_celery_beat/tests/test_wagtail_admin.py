from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from django_celery_beat.models import IntervalSchedule, PeriodicTask
from django_celery_beat.wagtail_hooks import (
    DisableTasksBulkAction,
    EnableTasksBulkAction,
    ToggleTasksBulkAction,
)


class PeriodicTaskWagtailAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.org",
            password="password",
        )
        interval = IntervalSchedule.objects.create(
            every=1,
            period=IntervalSchedule.MINUTES,
        )
        self.task = PeriodicTask.objects.create(
            name="Test task",
            task="tests.task",
            enabled=False,
            interval=interval,
        )

    def test_snippet_listing_keeps_run_action(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("wagtailsnippets_django_celery_beat_periodictask:list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test task")
        self.assertContains(response, "Run")

    @patch("django_celery_beat.wagtail_hooks.PeriodicTasks.update_changed")
    def test_state_bulk_actions_signal_scheduler(self, update_changed):
        queryset = PeriodicTask.objects.filter(pk=self.task.pk)

        EnableTasksBulkAction.execute_action(queryset)
        self.task.refresh_from_db()
        self.assertTrue(self.task.enabled)

        ToggleTasksBulkAction.execute_action(queryset)
        self.task.refresh_from_db()
        self.assertFalse(self.task.enabled)

        DisableTasksBulkAction.execute_action(queryset)
        self.task.refresh_from_db()
        self.assertFalse(self.task.enabled)
        self.assertEqual(update_changed.call_count, 3)
