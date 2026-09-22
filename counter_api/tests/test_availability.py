from datetime import date
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from counter_api.availability import available_months, split_period


class AvailabilityTests(SimpleTestCase):
    @patch("counter_api.availability.OpenSearchUsageClient")
    def test_reads_only_complete_months_from_status_index(self, client_class):
        client = client_class.return_value.client
        client.search.return_value = {
            "aggregations": {
                "months": {
                    "buckets": [
                        {"key": {"month": "2024-01"}},
                        {"key": {"month": "2024-03"}},
                    ]
                }
            }
        }

        months = available_months(Mock(acron3="scl"))

        self.assertEqual(months, [date(2024, 1, 1), date(2024, 3, 1)])
        filters = client.search.call_args.kwargs["body"]["query"]["bool"]["filter"]
        self.assertIn({"term": {"collection": "scl"}}, filters)
        self.assertIn({"term": {"complete": True}}, filters)

    @patch("counter_api.availability.available_months")
    def test_splits_missing_months_without_treating_gaps_as_no_usage(self, months):
        months.return_value = [date(2024, 1, 1), date(2024, 3, 1)]

        result = split_period(Mock(), date(2023, 12, 1), date(2024, 3, 31))

        self.assertEqual(result[0], [date(2024, 1, 1), date(2024, 3, 1)])
        self.assertEqual(result[1], [date(2024, 2, 1)])
        self.assertEqual(result[2], [date(2023, 12, 1)])
