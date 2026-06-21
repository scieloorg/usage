from metrics.counter.indexing.engines.base import DocumentPipeline


class ArticlePipeline(DocumentPipeline):
    data_type = "Article"

    def _resolve_parent_data_type(self, value):
        source_type = (value.get("source") or {}).get("source_type")
        if source_type == "journal":
            return "Journal"
        return None
