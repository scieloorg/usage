from datetime import date
from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from metrics.opensearch.month_status import mark_days_exported, replace_month_status


@override_settings(OPENSEARCH_INDEX_NAME="usage")
class MonthStatusTests(SimpleTestCase):
    def test_marks_month_complete_only_with_every_day(self):
        search_client = Mock()
        all_days = (1 << 31) - 1

        mark_days_exported(search_client, "scl", date(2024, 1, 1), all_days)

        search_client.create_alias_if_not_exists.assert_called_once()
        call = search_client.client.update.call_args
        self.assertEqual(call.kwargs["index"], "usage_month_status")
        self.assertEqual(call.kwargs["id"], "scl:2024-01")
        self.assertEqual(call.kwargs["body"]["script"]["params"]["day_mask"], all_days)
        self.assertEqual(
            call.kwargs["body"]["script"]["params"]["complete_mask"], all_days
        )
        self.assertEqual(call.kwargs["refresh"], "wait_for")

    def test_replaces_status_when_rebuilding_month(self):
        search_client = Mock()

        replace_month_status(search_client, "books", date(2024, 2, 1), (1 << 29) - 1)

        body = search_client.client.index.call_args.kwargs["body"]
        self.assertEqual(body["month"], "2024-02")
        self.assertTrue(body["complete"])
