from copy import deepcopy

from log_manager_config.choices import OpenSearchPartitionStrategy
from metrics.opensearch.mappings import get_index_mappings
from metrics.opensearch.names import (
    generate_analytics_index_name,
    generate_month_index_name,
    generate_yearly_write_alias,
)

MIGRATION_TRACKING_MAPPING = {
    "type": "keyword",
    "index": False,
    "doc_values": False,
}


def _migration_mappings(dataset):
    mappings = deepcopy(get_index_mappings(dataset))
    mappings["properties"]["applied_migrations"] = MIGRATION_TRACKING_MAPPING
    return mappings


def build_usage_index_target(
    index_prefix,
    collection,
    dataset,
    partition_strategy,
    access_date,
):
    if dataset == "counter":
        read_alias = generate_month_index_name(index_prefix, collection)
    elif dataset == "analytics":
        read_alias = generate_analytics_index_name(index_prefix, collection)
    else:
        raise ValueError("Unsupported usage dataset: %s." % dataset)

    if partition_strategy == OpenSearchPartitionStrategy.YEARLY:
        write_alias = generate_yearly_write_alias(read_alias, access_date)
    elif partition_strategy == OpenSearchPartitionStrategy.ROLLOVER:
        write_alias = read_alias
    else:
        raise ValueError(
            "Unsupported OpenSearch partition strategy: %s." % partition_strategy
        )

    return {
        "dataset": dataset,
        "mappings": _migration_mappings(dataset),
        "partition_strategy": partition_strategy,
        "read_alias": read_alias,
        "write_alias": write_alias,
    }
