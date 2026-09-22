from scielo_usage_counter.counter import is_request

from metrics.counter.indexing.engines.base import DocumentPipeline, _strip_empty_values


class BookPipeline(DocumentPipeline):
    def partition_key(self, value, projection=None):
        title_pid_generic = _extract_title_pid_generic(value)
        if title_pid_generic:
            return self._generate_document_id(
                value,
                projection=projection,
                metric_scope="title",
                pid_generic=title_pid_generic,
            )

        return self._generate_document_id(value, projection=projection)

    def accumulate(self, data, unique_state, value, projection=None):
        if not isinstance(value, dict):
            return

        segment_pid_generics = value.get("segment_pid_generics") or []
        if (
            value.get("document_type") == "book"
            and is_request(value.get("content_type"))
            and segment_pid_generics
        ):
            for pid_generic in segment_pid_generics:
                segment = {
                    **value,
                    "pid_generic": pid_generic,
                    "document_type": "chapter",
                }
                self._accumulate_item(data, unique_state, segment, projection)
        elif value.get("pid_generic"):
            self._accumulate_item(data, unique_state, value, projection)

        title_pid_generic = _extract_title_pid_generic(value)
        if not title_pid_generic:
            return

        self._accumulate_title(data, unique_state, value, projection, title_pid_generic)

    def _accumulate_item(self, data, unique_state, value, projection):
        item_document_id = self._generate_document_id(
            value,
            projection=projection,
            metric_scope="item",
        )
        item_document = data.setdefault(
            item_document_id,
            self._build_document(
                value=value,
                projection=projection,
                metric_scope="item",
            ),
        )

        self._apply_totals(
            document=item_document,
            click_timestamps=value.get("click_timestamps"),
            click_timestamps_by_url=value.get("click_timestamps_by_url"),
            content_type=value.get("content_type"),
        )

        self._apply_uniques(
            document=item_document,
            unique_state=unique_state,
            scope="item",
            document_id=item_document_id,
            user_session_id=value.get("user_session_id"),
            is_request_event=is_request(value.get("content_type")),
        )

    def _accumulate_title(
        self, data, unique_state, value, projection, title_pid_generic
    ):
        title_document_id = self._generate_document_id(
            value,
            projection=projection,
            metric_scope="title",
            pid_generic=title_pid_generic,
        )
        title_document = data.setdefault(
            title_document_id,
            self._build_document(
                value=value,
                projection=projection,
                metric_scope="title",
                pid_generic=title_pid_generic,
            ),
        )

        self._apply_totals(
            document=title_document,
            click_timestamps=value.get("click_timestamps"),
            click_timestamps_by_url=value.get("click_timestamps_by_url"),
            content_type=value.get("content_type"),
        )

        self._apply_uniques(
            document=title_document,
            unique_state=unique_state,
            scope="title",
            document_id=title_document_id,
            user_session_id=value.get("user_session_id"),
            is_request_event=is_request(value.get("content_type")),
        )

    def _build_document(self, value, projection=None, **kwargs):
        metric_scope = kwargs.get("metric_scope") or "item"
        pid_generic = kwargs.get("pid_generic")
        document_id = pid_generic or value.get("pid_generic")
        counter = _strip_empty_values(
            {
                "metric_scope": metric_scope,
                "data_type": "Book" if metric_scope == "title" else "Book_Segment",
                "parent_data_type": "Book" if metric_scope != "title" else None,
                "access_type": value.get("counter_access_type") or "Open",
                "access_method": value.get("access_method") or "Regular",
            }
        )

        if projection:
            country_code, content_language = self._projection_values(
                value,
                projection,
            )
            analytics_document = {
                "year": self._access_year(value),
                "source_key": self._source_key(value),
                "document_key": self._document_key(
                    value,
                    pid_generic=document_id,
                    metric_scope=metric_scope,
                ),
                **counter,
                "country_code": country_code,
                "content_language": content_language,
                "total_requests": 0,
                "total_investigations": 0,
                "unique_requests": 0,
                "unique_investigations": 0,
            }
            return _strip_empty_values(analytics_document)

        base_document = {
            "collection": value.get("collection"),
            "source_key": self._source_key(value),
            "document_key": self._document_key(
                value,
                pid_generic=document_id,
                metric_scope=metric_scope,
            ),
            "month": self._access_month(value),
            "publication_year": self._publication_year(value),
            **counter,
            "total_requests": 0,
            "total_investigations": 0,
            "unique_requests": 0,
            "unique_investigations": 0,
        }

        base_document["daily_metrics"] = self._build_daily_metrics(value)

        return _strip_empty_values(base_document)


def _extract_title_pid_generic(value):
    title_pid_generic = value.get("title_pid_generic")
    if title_pid_generic:
        return title_pid_generic

    pid_generic = value.get("pid_generic")
    if "/CHAPTER:" in (pid_generic or "").upper():
        return pid_generic.upper().split("/CHAPTER:")[0]

    source = value.get("source") or {}
    source_id = source.get("source_id")
    if source_id:
        return f"BOOK:{str(source_id).upper()}"

    return None
