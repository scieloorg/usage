from datetime import date
from unittest.mock import patch

import pytest

from counter_api.exceptions import CounterAPIError
from counter_api.extensions.dates import parse_analytics_period


@pytest.fixture(autouse=True)
def today():
    with patch("counter_api.extensions.dates.date", wraps=date) as clock:
        clock.today.return_value = date(2024, 3, 15)
        yield


@pytest.mark.parametrize(
    "begin,end,expected",
    [
        ("2024-02-29", "2024-03-02", (date(2024, 2, 29), date(2024, 3, 2))),
        ("2024-03-12", "2024-03", (date(2024, 3, 12), date(2024, 3, 15))),
    ],
)
def test_monthly_analytics_dates(begin, end, expected):
    assert parse_analytics_period({"begin_date": begin, "end_date": end}) == expected


@pytest.mark.parametrize(
    "begin,end",
    [
        ("2024-03-01", "2024-03-16"),
        ("2024-04", "2024-04"),
        ("2024-03-16", "2024-03"),
    ],
)
def test_invalid_monthly_dates(begin, end):
    with pytest.raises(CounterAPIError):
        parse_analytics_period({"begin_date": begin, "end_date": end})


@pytest.mark.parametrize(
    "segmentation",
    [
        {"group_by": "country,language"},
        {"dimension": "language,yop"},
        {"country": "BR"},
    ],
)
def test_current_year_annual_dates(segmentation):
    params = {"begin_date": "2024-01", "end_date": "2024-12", **segmentation}

    assert parse_analytics_period(params) == (date(2024, 1, 1), date(2024, 12, 31))


@pytest.mark.parametrize(
    "begin,end",
    [
        ("2024-01-02", "2024-12-31"),
        ("2024-01-01", "2024-12-30"),
        ("2024-02", "2024-12"),
        ("2024-01", "2025-12"),
    ],
)
def test_annual_requires_whole_calendar_years(begin, end):
    with pytest.raises(CounterAPIError):
        parse_analytics_period({"begin_date": begin, "end_date": end, "country": "BR"})


def test_whitespace_does_not_bypass_annual_boundaries():
    with pytest.raises(CounterAPIError):
        parse_analytics_period(
            {
                "begin_date": "2023-01-02",
                "end_date": "2023-12-30",
                "dimension": " country , language ",
            }
        )


def test_annual_preserves_unique_metric_restriction():
    with pytest.raises(CounterAPIError):
        parse_analytics_period(
            {
                "begin_date": "2023-01",
                "end_date": "2024-12",
                "dimension": "country",
                "metric_type": "Unique_Item_Requests",
            }
        )
