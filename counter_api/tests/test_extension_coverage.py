import csv
import json
from datetime import date
from io import StringIO
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openpyxl import load_workbook

from counter_api.exceptions import CounterAPIError
from counter_api.extensions.coverage import resolve_coverage
from counter_api.extensions.distribution import DistributionQuery
from counter_api.extensions.exports import build_export
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


def test_strict_skips_markers_and_invalid_policy_fails():
    client = Mock()

    assert resolve_coverage(client, PLATFORM, BEGIN, END, "strict", False, 0) is None

    with pytest.raises(CounterAPIError):
        resolve_coverage(client, PLATFORM, BEGIN, END, "other", False, 0)
    client.search.assert_not_called()


@pytest.mark.parametrize("kind", ["ranking", "distribution"])
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
            DistributionQuery,
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
        assert script["source"].strip().splitlines()[0] == (
            "String month = doc['month'].value.toString().substring(0,7);"
        )


@pytest.mark.parametrize("response", [markers(), markers(**{"01": 1})])
def test_annual_totals_do_not_depend_on_confirmed_days(response):
    client = Mock()
    client.search.side_effect = [
        response,
        {
            "aggregations": {
                "rows": {
                    "buckets": [{"key": {"country": "BR"}, "count": {"value": 15}}]
                }
            }
        },
    ]

    payload = DistributionQuery(Mock(client=client)).run(
        PLATFORM,
        BEGIN,
        END,
        {"entity_type": "collection", "entity_id": "scl", "dimension": "country"},
    )

    assert payload["total"] == 15
    assert payload["coverage"]["status"] == "partial"
    assert payload["coverage"]["basis"] == "available_annual_totals"
    assert payload["coverage"]["included_months"] is None
    assert "informative" in payload["warnings"][0]

    body = client.search.call_args.kwargs["body"]
    assert {"terms": {"year": ["2023"]}} in body["query"]["bool"]["filter"]
    assert body["aggs"]["rows"]["aggs"]["count"]["sum"] == {"field": "total_requests"}


@pytest.mark.parametrize("output_format", ["csv", "xlsx"])
def test_empty_export_preserves_coverage_metadata(output_format):
    payload = {
        "dimension": "yop",
        "buckets": [],
        "total": 0,
        "coverage": {"status": "partial", "included_months": ["2023-03"]},
        "warnings": ["Only confirmed days are included."],
    }

    with build_export(payload, "distribution", output_format) as output:
        if output_format == "csv":
            rows = list(csv.DictReader(StringIO(output.read().decode())))
            assert len(rows) == 1
            metadata = rows[0]
            assert metadata["Yop"] == metadata["Count"] == ""
        else:
            workbook = load_workbook(output, read_only=True)
            assert list(workbook["Distribution"].values) == [("Yop", "Count")]
            headings, values = list(workbook["Coverage"].values)
            metadata = dict(zip(headings, values))
            workbook.close()

    assert json.loads(metadata["Coverage"]) == payload["coverage"]
    assert json.loads(metadata["Warnings"]) == payload["warnings"]
    assert int(metadata["Total"]) == 0
