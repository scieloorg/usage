from datetime import date
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from counter_api.exceptions import CounterAPIError
from counter_api.extensions.coverage import resolve_coverage
from counter_api.extensions.ranking import RankingQuery

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


@pytest.mark.parametrize("kind", ["ranking"])
def test_default_queries_share_confirmed_sum_across_pages(kind):
    client = Mock()
    key = "source_key" if kind == "ranking" else "yop"
    client.search.side_effect = [
        markers(**{"01": 1, "03": (1 << 31) - 1}),
        {
            "aggregations": {
                "rows": {
                    "buckets": [{"key": {key: None}, "count": {"value": 5}}],
                    "after_key": {key: None},
                }
            }
        },
        {"aggregations": {"rows": {"buckets": []}}},
    ]
    query, params = (
        (
            RankingQuery,
            {
                "parent_type": "collection",
                "parent_id": "scl",
                "entity_type": "journals",
            },
        )
        if kind == "ranking"
        else (
            None,
            {"entity_type": "collection", "entity_id": "scl", "dimension": "yop"},
        )
    )

    payload = query(Mock(client=client)).run(PLATFORM, BEGIN, END, params)

    assert payload["coverage"]["status"] == "partial"
    if kind == "distribution":
        assert payload["total"] == sum(b["count"] for b in payload["buckets"]) == 5
    bodies = [call.kwargs["body"] for call in client.search.call_args_list[1:]]
    assert len(bodies) == 2

    for body in bodies:
        assert {"terms": {"month": ["2023-01", "2023-03"]}} in body["query"]["bool"][
            "filter"
        ]
        script = body["aggs"]["rows"]["aggs"]["count"]["sum"]["script"]
        assert script["params"] == {
            "metric": "total_requests",
            "complete": ["2023-03"],
            "days": {"2023-01": ["01"]},
        }
        assert "Missing daily_metrics" in script["source"]
