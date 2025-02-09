from datetime import datetime, timedelta

from django.test import TestCase

from core.utils.date_utils import get_date_range_str


class DateUtilsTests(TestCase):

    def test_get_date_range_with_valid_dates(self):
        from_date = "2023-01-01"
        until_date = "2023-01-31"
        result = get_date_range_str(from_date_str=from_date, until_date_str=until_date)

        expected = (
           '2023-01-01',
           '2023-01-31'
        )
        self.assertEqual(result, expected)

    def test_get_date_range_with_invalid_from_date(self):
        from_date = "invalid-date"
        until_date = "2023-01-10"
        result = get_date_range_str(from_date_str=from_date, until_date_str=until_date)
        
        expected = (
            '2023-01-03',
            '2023-01-10'
        )
        self.assertEqual(result, expected)

    def test_get_date_range_with_invalid_until_date(self):
        from_date = "2024-05-20"
        until_date = "invalid-date"
        result = get_date_range_str(from_date_str=from_date, until_date_str=until_date)

        expected = (
            '2024-05-20',
            '2024-05-27'
        )
        self.assertEqual(result, expected)

    def test_get_date_range_with_days_to_go_back(self):
        days_to_go_back = 10
        today = datetime.now().date()
        result = get_date_range_str(days_to_go_back=days_to_go_back)

        expected = (
            (today - timedelta(days=days_to_go_back)).strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d")
        )
        self.assertEqual(result, expected)

    def test_get_date_range_with_no_params(self):
        result = get_date_range_str()
        expected = (
            (datetime.now().date() - timedelta(days=7)).strftime("%Y-%m-%d"),
            datetime.now().date().strftime("%Y-%m-%d")
        )
        self.assertEqual(result, expected)

    def test_get_date_range_with_only_from_date(self):
        from_date = "2025-02-01"
        result = get_date_range_str(from_date_str=from_date)
        expected = (
            '2025-02-01',
            '2025-02-08',
        )
        self.assertEqual(result, expected)

    def test_get_date_range_with_only_until_date(self):
        until_date = "2025-02-08"
        result = get_date_range_str(until_date_str=until_date)
        expected = (
            '2025-02-01',
            '2025-02-08',
        )
        self.assertEqual(result, expected)
