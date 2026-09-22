from metrics.opensearch.names import (
    generate_analytics_index_name,
    generate_initial_index_name,
    generate_metadata_alias,
    generate_month_index_name,
    generate_month_status_index_name,
    generate_rollover_index_name,
    generate_yearly_write_alias,
)


def test_metric_aliases_are_stable_per_collection():
    assert generate_month_index_name("usage", "scl") == "usage_monthly_scl"
    assert generate_month_status_index_name("usage") == "usage_month_status"
    assert generate_analytics_index_name("usage", "scl") == (
        "usage_yearly_analytics_scl"
    )


def test_physical_index_names_express_the_partition_strategy():
    assert generate_rollover_index_name("usage_monthly_books") == (
        "usage_monthly_books-000001"
    )
    assert generate_yearly_write_alias("usage_monthly_scl", "2026-08-20") == (
        "usage_monthly_scl_2026"
    )


def test_non_rollover_alias_uses_a_neutral_physical_name():
    assert generate_initial_index_name("usage_documents") == ("usage_documents_000001")


def test_metadata_alias_names_are_explicit():
    assert generate_metadata_alias("usage", "documents") == "usage_documents"
    assert generate_metadata_alias("custom", "sources") == "custom_sources"
