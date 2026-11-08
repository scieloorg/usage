from datetime import date
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from counter_api.exceptions import CounterAPIError
from counter_api.extensions.coverage import resolve_coverage

PLATFORM = SimpleNamespace(acron3="scl", collection_type="journals")
BEGIN, END = date(2023, 1, 1), date(2023, 12, 31)


def markers(**masks):
    return {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "collection": "scl",
                        "month": f"2023-{month}",
                        "day_mask": mask,
                        "complete": mask == (1 << 31) - 1,
                    }
                }
                for month, mask in masks.items()
            ]
        }
    }


def resolve(client, segmented=False):
    return resolve_coverage(
        client, PLATFORM, BEGIN, END, "allow_partial", segmented, monotonic() + 30
    )


def test_mixed_coverage():
    client = Mock()
    client.search.return_value = markers(**{"01": 1, "03": (1 << 31) - 1, "05": 0})

    coverage = resolve(client)

    assert coverage["included_months"] == ["2023-01", "2023-03"]
    assert [m["status"] for m in coverage["months"][:5]] == [
        "partial",
        "unknown",
        "complete",
        "unknown",
        "unavailable",
    ]
    assert coverage["months"][0]["confirmed_days"] == [1]
    assert coverage["months"][0]["missing_days"] == list(range(2, 32))
    assert coverage["months"][1]["missing_days"] is None
    client.search.assert_called_once()


@pytest.mark.parametrize(
    "response", [markers(), markers(**{"01": 0}), markers(**{"01": -1})]
)
def test_unusable_or_inconsistent_coverage_fails(response):
    client = Mock()
    client.search.return_value = response

    with pytest.raises(CounterAPIError):
        resolve(client)


def test_annual_partial_rejected_and_strict_skips_markers():
    client = Mock()
    client.search.return_value = markers(**{"01": 1})

    with pytest.raises(CounterAPIError) as error:
        resolve(client, segmented=True)

    assert "country/language" in error.value.data

    client.reset_mock()

    assert resolve_coverage(client, PLATFORM, BEGIN, END, "strict", False, 0) is None

    with pytest.raises(CounterAPIError):
        resolve_coverage(client, PLATFORM, BEGIN, END, "other", False, 0)
    client.search.assert_not_called()
