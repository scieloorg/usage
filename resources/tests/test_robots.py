from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from resources import models, tasks, utils


class RobotUserAgentModelTests(TestCase):
    def test_manual_robot_defaults_to_scielo_source(self):
        robot = models.RobotUserAgent.objects.create(pattern="CustomBot")

        robot.refresh_from_db()

        self.assertFalse(robot.source_counter)
        self.assertTrue(robot.source_scielo)
        self.assertTrue(robot.is_active)
        self.assertEqual(robot.source_labels, "SciELO")

    def test_get_all_patterns_only_returns_active_patterns(self):
        active = models.RobotUserAgent.objects.create(
            pattern="ActiveBot",
            source_scielo=True,
            is_active=True,
        )
        models.RobotUserAgent.objects.create(
            pattern="InactiveBot",
            source_scielo=True,
            is_active=False,
        )

        self.assertListEqual(
            list(models.RobotUserAgent.get_all_patterns()), [active.pattern]
        )

    def test_get_patterns_can_filter_by_source(self):
        counter_only = models.RobotUserAgent.objects.create(
            pattern="CounterOnlyBot",
            source_counter=True,
            source_scielo=False,
            is_active=True,
        )
        shared = models.RobotUserAgent.objects.create(
            pattern="SharedBot",
            source_counter=True,
            source_scielo=True,
            is_active=True,
        )
        scielo_only = models.RobotUserAgent.objects.create(
            pattern="ScieloOnlyBot",
            source_counter=False,
            source_scielo=True,
            is_active=True,
        )

        self.assertCountEqual(
            list(models.RobotUserAgent.get_patterns(source="counter")),
            [counter_only.pattern, shared.pattern],
        )
        self.assertCountEqual(
            list(models.RobotUserAgent.get_patterns(source="scielo")),
            [shared.pattern, scielo_only.pattern],
        )

    def test_get_patterns_rejects_invalid_source(self):
        with self.assertRaises(ValueError):
            list(models.RobotUserAgent.get_patterns(source="invalid"))


class LoadRobotsTaskTests(TestCase):
    @patch("resources.services.utils.fetch_data")
    @override_settings(COUNTER_ROBOTS_URL="https://settings.example.org/robots.json")
    def test_task_load_robots_uses_settings_url_when_not_provided(
        self,
        mock_fetch_data,
    ):
        mock_fetch_data.return_value = [
            {"pattern": "CounterBot", "last_changed": "2025-01-15"},
        ]

        result = tasks.task_load_robots.run()

        self.assertTrue(result)
        mock_fetch_data.assert_called_once_with(
            "https://settings.example.org/robots.json",
            data_type="json",
        )

        counter_bot = models.RobotUserAgent.objects.get(pattern="CounterBot")
        self.assertEqual(
            counter_bot.source_url,
            "https://settings.example.org/robots.json",
        )

    @patch("resources.services.utils.fetch_data")
    def test_task_load_robots_marks_counter_source_and_deactivates_stale_counter_entries(
        self,
        mock_fetch_data,
    ):
        mock_fetch_data.return_value = [
            {"pattern": "CounterBot", "last_changed": "2025-01-15"},
            {"pattern": "SharedBot", "last_changed": "2025-01-20"},
        ]

        stale_counter = models.RobotUserAgent.objects.create(
            pattern="OldCounterBot",
            source_counter=True,
            is_active=True,
            last_changed="2024-12-01",
            source_url="https://old.example.org/robots.json",
        )
        shared_bot = models.RobotUserAgent.objects.create(
            pattern="SharedBot",
            source_scielo=True,
            is_active=True,
        )

        result = tasks.task_load_robots.run(
            url_robots="https://counter.example.org/robots.json",
        )

        self.assertTrue(result)

        counter_bot = models.RobotUserAgent.objects.get(pattern="CounterBot")
        self.assertTrue(counter_bot.source_counter)
        self.assertFalse(counter_bot.source_scielo)
        self.assertTrue(counter_bot.is_active)
        self.assertEqual(
            counter_bot.source_url, "https://counter.example.org/robots.json"
        )

        shared_bot.refresh_from_db()
        self.assertTrue(shared_bot.source_counter)
        self.assertTrue(shared_bot.source_scielo)
        self.assertTrue(shared_bot.is_active)

        stale_counter.refresh_from_db()
        self.assertFalse(stale_counter.source_counter)
        self.assertFalse(stale_counter.is_active)
        self.assertIsNone(stale_counter.source_url)
        self.assertIsNone(stale_counter.last_changed)


class GeoIPUtilsTests(TestCase):
    @override_settings(
        MMDB_URL_TEMPLATE="https://example.org/dbip-{year}-{month:02d}.mmdb.gz"
    )
    @patch("resources.utils.date")
    def test_resolve_mmdb_url_returns_current_and_previous_month_from_settings(
        self,
        mock_date,
    ):
        mock_date.today.return_value = date(2026, 5, 5)

        self.assertEqual(
            utils.resolve_mmdb_url(),
            [
                "https://example.org/dbip-2026-05.mmdb.gz",
                "https://example.org/dbip-2026-04.mmdb.gz",
            ],
        )
