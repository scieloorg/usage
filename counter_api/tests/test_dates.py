from datetime import date
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase

from counter_api.dates import parse_period
from counter_api.exceptions import CounterAPIError


class ReportPeriodTests(SimpleTestCase):
    def test_expands_months_to_complete_period(self):
        begin, end = parse_period({"begin_date": "2024-02", "end_date": "2024-03"})

        self.assertEqual(begin, date(2024, 2, 1))
        self.assertEqual(end, date(2024, 3, 31))

    def test_rejects_current_month(self):
        current_month = date.today().strftime("%Y-%m")

        with self.assertRaises(CounterAPIError) as raised:
            parse_period({"begin_date": "2024-01", "end_date": current_month})

        self.assertEqual(raised.exception.code, 3020)


@pytest.mark.parametrize(
    "begin,end",
    [
        ("2024-02-02", "2024-02-29"),
        ("2024-02-01", "2024-02-28"),
    ],
)
def test_official_report_still_requires_whole_past_months(begin, end):
    with patch("counter_api.dates.date", wraps=date) as clock:
        clock.today.return_value = date(2024, 3, 15)
        with pytest.raises(CounterAPIError) as raised:
            parse_period({"begin_date": begin, "end_date": end})
    assert raised.value.code == 3020
