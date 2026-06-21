from metrics.counter.indexing.engines.base import DocumentPipeline, _strip_empty_values


class PreprintPipeline(DocumentPipeline):
    data_type = "Article"

    def _build_counter_section(self, value):
        return _strip_empty_values(
            {
                "metric_scope": "item",
                "data_type": self.data_type,
                "parent_data_type": self._resolve_parent_data_type(value),
                "article_version": "Preprint",
                "access_type": value.get("counter_access_type") or "Open",
                "access_method": value.get("access_method") or "Regular",
            }
        )
