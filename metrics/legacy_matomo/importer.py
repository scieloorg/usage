import gzip
import json
from datetime import date
from functools import partial
from itertools import islice

from django.conf import settings
from opensearchpy import helpers

from log_manager_config.choices import OpenSearchPartitionStrategy
from metrics.legacy_matomo.manifest import build_migration_id
from metrics.legacy_matomo.opensearch_actions import (
    build_analytics_increment_action,
    build_counter_increment_action,
)
from metrics.legacy_matomo.routing import build_usage_index_target
from metrics.opensearch.month_status import mark_days_exported
from metrics.opensearch.names import generate_yearly_write_alias

DOCUMENT_INDEX_LOOKUP_BATCH_SIZE = 1000
DEFAULT_PROGRESS_INTERVAL = 100000


def iter_document_items(path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            yield row["_id"], row["_source"]


def _collection_config(collection):
    config = getattr(collection, "log_manager_config", None)
    if config is None:
        raise ValueError(
            "Collection %s has no log manager configuration." % collection.acron3
        )
    return config


def _dataset_target(collection, config, manifest, dataset):
    return build_usage_index_target(
        index_prefix=settings.OPENSEARCH_INDEX_NAME,
        collection=collection.acron3,
        dataset=dataset,
        partition_strategy=config.opensearch_partition_strategy,
        access_date=manifest["month"] + "-01",
    )


def _inspect_alias(search_client, alias_name):
    client = search_client.client
    if not client.indices.exists_alias(name=alias_name):
        return {
            "alias": alias_name,
            "exists": False,
            "indexes": [],
            "write_indexes": [],
        }

    indexes = client.indices.get_alias(name=alias_name)
    write_indexes = [
        index_name
        for index_name, index_data in indexes.items()
        if index_data.get("aliases", {}).get(alias_name, {}).get("is_write_index")
    ]
    return {
        "alias": alias_name,
        "exists": True,
        "indexes": sorted(indexes),
        "write_indexes": sorted(write_indexes),
    }


def _write_index(search_client, alias_name):
    alias = _inspect_alias(search_client, alias_name)
    if len(alias["write_indexes"]) == 1:
        return alias["write_indexes"][0]
    if len(alias["indexes"]) == 1:
        return alias["indexes"][0]
    raise RuntimeError("Alias %s has no unique write index." % alias_name)


def _existing_document_indexes(search_client, alias_name, doc_ids):
    response = search_client.client.search(
        index=alias_name,
        body={
            "size": len(doc_ids) * 2,
            "_source": False,
            "query": {"ids": {"values": doc_ids}},
        },
    )
    indexes = {}
    for hit in response.get("hits", {}).get("hits", []):
        doc_id = hit["_id"]
        if doc_id in indexes and indexes[doc_id] != hit["_index"]:
            raise RuntimeError(
                "Document %s exists in multiple indexes behind alias %s."
                % (doc_id, alias_name)
            )
        indexes[doc_id] = hit["_index"]
    return indexes


def _update_document_items(
    search_client,
    alias_name,
    document_items,
    action_builder,
    dataset=None,
    progress_callback=None,
    progress_interval=DEFAULT_PROGRESS_INTERVAL,
    stop_controller=None,
):
    if progress_interval <= 0:
        raise ValueError("Progress interval must be greater than zero.")

    write_index = _write_index(search_client, alias_name)
    succeeded = 0
    reported = 0
    next_progress = progress_interval
    batch_size = min(
        search_client.bulk_chunk_size,
        DOCUMENT_INDEX_LOOKUP_BATCH_SIZE,
    )

    while True:
        if stop_controller:
            stop_controller.raise_if_requested()
        batch = list(islice(document_items, batch_size))
        if not batch:
            if progress_callback and succeeded != reported:
                progress_callback(dataset, "import", succeeded)
            return succeeded

        existing_indexes = _existing_document_indexes(
            search_client,
            alias_name,
            [doc_id for doc_id, _document in batch],
        )
        batch_succeeded, _failed = helpers.bulk(
            search_client.client,
            (
                action_builder(
                    index_name=existing_indexes.get(doc_id, write_index),
                    doc_id=doc_id,
                    document=document,
                )
                for doc_id, document in batch
            ),
            chunk_size=search_client.bulk_chunk_size,
        )
        succeeded += batch_succeeded
        if succeeded >= next_progress:
            if progress_callback:
                progress_callback(dataset, "import", succeeded)
                reported = succeeded
            while next_progress <= succeeded:
                next_progress += progress_interval
        if stop_controller:
            stop_controller.raise_if_requested()


def _validate_alias_topology(search_client, target, access_date):
    read_alias = _inspect_alias(search_client, target["read_alias"])
    write_alias = _inspect_alias(search_client, target["write_alias"])

    if target["partition_strategy"] == OpenSearchPartitionStrategy.YEARLY:
        if read_alias["write_indexes"]:
            raise ValueError(
                "Yearly target has a writable continuous alias: %s."
                % target["read_alias"]
            )
    else:
        yearly_alias = generate_yearly_write_alias(target["read_alias"], access_date)
        yearly = _inspect_alias(search_client, yearly_alias)
        if yearly["exists"]:
            raise ValueError(
                "Rollover target conflicts with yearly alias: %s." % yearly_alias
            )

    if write_alias["exists"]:
        has_unique_writer = len(write_alias["write_indexes"]) == 1
        has_single_implicit_writer = (
            not write_alias["write_indexes"] and len(write_alias["indexes"]) == 1
        )
        if not has_unique_writer and not has_single_implicit_writer:
            raise ValueError(
                "Target alias has no unique write index: %s." % target["write_alias"]
            )

    return {
        "dataset": target["dataset"],
        "partition_strategy": target["partition_strategy"],
        "read_alias": read_alias,
        "write_alias": write_alias,
    }


def build_import_plan(search_client, collection, manifest):
    config = _collection_config(collection)
    access_date = manifest["month"] + "-01"
    datasets = []
    for dataset in ("counter", "analytics"):
        target = _dataset_target(collection, config, manifest, dataset)
        datasets.append(_validate_alias_topology(search_client, target, access_date))

    return {
        "collection": collection.acron3,
        "month": manifest["month"],
        "primary_shards": config.opensearch_primary_shards,
        "datasets": datasets,
    }


def import_dataset(
    search_client,
    collection,
    config,
    manifest,
    dataset,
    progress_callback=None,
    progress_interval=DEFAULT_PROGRESS_INTERVAL,
    stop_controller=None,
):
    target = _dataset_target(collection, config, manifest, dataset)
    write_alias = search_client.prepare_usage_index(
        alias_name=target["read_alias"],
        mappings=target["mappings"],
        partition_strategy=target["partition_strategy"],
        access_date=manifest["month"] + "-01",
        primary_shards=config.opensearch_primary_shards,
    )
    action_builder = partial(
        (
            build_analytics_increment_action
            if dataset == "analytics"
            else build_counter_increment_action
        ),
        migration_id=build_migration_id(manifest, dataset),
        source_days=manifest["source_days"],
    )
    imported = _update_document_items(
        search_client=search_client,
        alias_name=write_alias,
        document_items=iter_document_items(manifest[dataset]["path"]),
        action_builder=action_builder,
        dataset=dataset,
        progress_callback=progress_callback,
        progress_interval=progress_interval,
        stop_controller=stop_controller,
    )
    search_client.rollover_usage_index(
        alias_name=write_alias,
        mappings=target["mappings"],
        primary_shards=config.opensearch_primary_shards,
        read_alias=(
            target["read_alias"] if write_alias != target["read_alias"] else None
        ),
    )
    return imported


def import_manifest(
    search_client,
    collection,
    manifest,
    progress_callback=None,
    progress_interval=DEFAULT_PROGRESS_INTERVAL,
    stop_controller=None,
):
    config = _collection_config(collection)
    imported = {}

    for dataset in ("counter", "analytics"):
        imported[dataset] = import_dataset(
            search_client,
            collection,
            config,
            manifest,
            dataset,
            progress_callback=progress_callback,
            progress_interval=progress_interval,
            stop_controller=stop_controller,
        )

    targets = [
        _dataset_target(collection, config, manifest, dataset)
        for dataset in ("counter", "analytics")
    ]
    search_client.client.indices.refresh(
        index=",".join(target["read_alias"] for target in targets),
        ignore_unavailable=True,
    )

    month_date = date.fromisoformat(f"{manifest['month']}-01")
    days = manifest["source_days"] + manifest.get("empty_days", [])
    day_mask = 0
    for day in days:
        day_mask |= 1 << (date.fromisoformat(day).day - 1)

    mark_days_exported(
        search_client,
        collection.acron3,
        month_date,
        day_mask,
    )

    return imported
