import hashlib

from metrics.counter.indexing.engines.article import ArticlePipeline
from metrics.counter.indexing.engines.base import DocumentPipeline
from metrics.counter.indexing.engines.book import BookPipeline
from metrics.counter.indexing.engines.dataset import DatasetPipeline
from metrics.counter.indexing.engines.preprint import PreprintPipeline

_PIPELINES = {
    "article": ArticlePipeline(),
    "preprint": PreprintPipeline(),
    "dataset": DatasetPipeline(),
    "book": BookPipeline(),
    "chapter": BookPipeline(),
}
_DEFAULT = DocumentPipeline()
_DEFAULT_PARTITION_COUNT = 64


def iter_partitioned_documents(
    accumulator,
    granularity,
    partition_count=_DEFAULT_PARTITION_COUNT,
):
    if partition_count <= 0:
        raise ValueError("Partition count must be greater than zero.")

    consume = granularity == "year"
    partitions = [[] for _ in range(partition_count)]
    for record_key, value in accumulator.iter_materialized_record_items():
        partition = _partition_for_value(value, granularity, partition_count)
        partitions[partition].append(record_key)

    try:
        for record_keys in partitions:
            values = accumulator.iter_materialized_record_keys(
                record_keys,
                consume=consume,
            )
            yield from _convert_partition(values, granularity)
            record_keys.clear()
    finally:
        for record_keys in partitions:
            record_keys.clear()
        partitions.clear()
        if consume:
            accumulator.clear()


def iter_partitioned_values(
    values,
    granularity,
    partition_count=_DEFAULT_PARTITION_COUNT,
):
    if partition_count <= 0:
        raise ValueError("Partition count must be greater than zero.")

    partitions = [[] for _ in range(partition_count)]
    for value in values:
        partition = _partition_for_value(value, granularity, partition_count)
        partitions[partition].append(value)

    try:
        for partition_values in partitions:
            yield from _convert_partition(partition_values, granularity)
            partition_values.clear()
    finally:
        for partition_values in partitions:
            partition_values.clear()
        partitions.clear()


def _partition_for_value(value, granularity, partition_count):
    pipeline = _get_pipeline(value)
    partition_key = pipeline.partition_key(value, granularity)
    digest = hashlib.blake2b(
        partition_key.encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big") % partition_count


def _convert_partition(values, granularity):
    converted_data = {}
    unique_state = _initialize_unique_state()

    try:
        for value in values:
            pipeline = _get_pipeline(value)
            pipeline.accumulate(
                data=converted_data,
                unique_state=unique_state,
                value=value,
                granularity=granularity,
            )

        for document_id in sorted(converted_data):
            yield document_id, converted_data[document_id]
    finally:
        converted_data.clear()
        for bucket in unique_state.values():
            bucket.clear()


def _get_pipeline(value):
    collection = value.get("collection")
    if collection == "books":
        return _PIPELINES["book"]

    return _PIPELINES.get(value.get("document_type"), _DEFAULT)


def _initialize_unique_state():
    return {
        "item_investigations": set(),
        "item_requests": set(),
        "title_investigations": set(),
        "title_requests": set(),
    }
