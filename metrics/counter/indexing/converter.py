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


def convert(data):
    if not isinstance(data, dict):
        return {"month": {}, "year": {}}

    month_data = _convert_granularity(data, "month")
    year_data = _convert_granularity(data, "year")

    return {"month": month_data, "year": year_data}


def _convert_granularity(data, granularity):
    converted_data = {}
    unique_state = _initialize_unique_state()
    values = getattr(data, "iter_materialized_values", data.values)

    for value in values():
        pipeline = _get_pipeline(value)
        pipeline.accumulate(
            data=converted_data,
            unique_state=unique_state,
            value=value,
            granularity=granularity,
        )

    return converted_data


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
