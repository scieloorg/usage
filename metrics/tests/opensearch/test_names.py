from metrics.opensearch.names import (
    generate_analytics_index_name,
    generate_metadata_alias,
    generate_month_index_name,
    generate_physical_index_name,
)


def test_metric_aliases_are_partitioned_by_collection_and_year():
    assert generate_month_index_name("usage", "scl", "2026-08-20") == (
        "usage_monthly_scl_2026"
    )
    assert generate_analytics_index_name("usage", "scl", "2026-08-20") == (
        "usage_yearly_analytics_scl_2026"
    )


def test_physical_index_and_metadata_alias_names_are_explicit():
    assert generate_physical_index_name("usage_monthly_scl_2026") == (
        "usage_monthly_scl_2026_000001"
    )
    assert generate_metadata_alias("documents") == "usage_documents"
    assert generate_metadata_alias("sources") == "usage_sources"
