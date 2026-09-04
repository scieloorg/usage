from scielo_usage_counter.counter import is_request

from metrics.counter.indexing.engines.base import (
    DocumentPipeline,
    _strip_empty_identifiers,
    _strip_empty_values,
)


class BookPipeline(DocumentPipeline):
    def partition_key(self, value, granularity):
        title_pid_generic = _extract_title_pid_generic(value)
        if title_pid_generic:
            return self._generate_document_id(
                value,
                granularity,
                metric_scope="title",
                pid_generic=title_pid_generic,
            )
        return self._generate_document_id(value, granularity)

    def accumulate(self, data, unique_state, value, granularity):
        if not isinstance(value, dict):
            return

        if _should_create_item_document(value):
            self._accumulate_item(data, unique_state, value, granularity)

        title_pid_generic = _extract_title_pid_generic(value)
        if not title_pid_generic:
            return

        self._accumulate_title(
            data, unique_state, value, granularity, title_pid_generic
        )

    def _accumulate_item(self, data, unique_state, value, granularity):
        item_document_id = self._generate_document_id(
            value,
            granularity,
            metric_scope="item",
        )
        item_document = data.setdefault(
            item_document_id,
            self._build_document(
                value=value,
                granularity=granularity,
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
        self, data, unique_state, value, granularity, title_pid_generic
    ):
        title_document_id = self._generate_document_id(
            value,
            granularity,
            metric_scope="title",
            pid_generic=title_pid_generic,
        )
        title_document = data.setdefault(
            title_document_id,
            self._build_document(
                value=value,
                granularity=granularity,
                metric_scope="title",
                pid_generic=title_pid_generic,
                document_type="book",
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

    def _build_document(self, value, granularity, **kwargs):
        metric_scope = kwargs.get("metric_scope") or "item"
        pid_generic = kwargs.get("pid_generic")
        document_type = kwargs.get("document_type")

        document_id = pid_generic or value.get("pid_generic")
        parent_id = _extract_title_pid_generic(value, fallback=document_id)
        if parent_id == document_id or metric_scope == "title":
            parent_id = None
        raw_source = value.get("source") or {}
        source = self._build_source(raw_source)

        base_document = {
            "collection": value.get("collection"),
            "source": source,
            "document": self._build_document_section(
                value=value,
                document_id=document_id,
                document_type=document_type or value.get("document_type"),
                parent_id=parent_id,
                source_identifiers=raw_source.get("identifiers"),
                metric_scope=metric_scope,
            ),
            "counter": _strip_empty_values(
                {
                    "metric_scope": metric_scope,
                    "data_type": "Book" if metric_scope == "title" else "Book_Segment",
                    "parent_data_type": "Book" if metric_scope != "title" else None,
                    "access_type": value.get("counter_access_type") or "Open",
                    "access_method": value.get("access_method") or "Regular",
                }
            ),
            "total_requests": 0,
            "total_investigations": 0,
            "unique_requests": 0,
            "unique_investigations": 0,
        }

        base_document["access"] = self._build_access(value, granularity)
        if granularity == "month":
            base_document["daily_metrics"] = self._build_daily_metrics(value)
        return base_document

    def _document_identifiers(
        self, value, document_id, source_identifiers=None, metric_scope="item"
    ):
        if metric_scope == "title":
            identifiers = _book_identifiers_from_pid(document_id)
            identifiers.update(source_identifiers or {})
            return _strip_empty_identifiers(identifiers, canonical_id=document_id)

        document_identifiers = (value.get("document") or {}).get("identifiers") or {}
        identifiers = {
            "pid_v2": value.get("pid_v2"),
            "pid_v3": value.get("pid_v3"),
            "pid_generic": value.get("pid_generic"),
        }
        identifiers.update(document_identifiers)
        identifiers.update(_book_identifiers_from_pid(value.get("pid_generic")))
        identifiers.update(source_identifiers or {})
        return _strip_empty_identifiers(identifiers, canonical_id=document_id)


def _should_create_item_document(value):
    if not value.get("pid_generic"):
        return False
    if value.get("document_type") == "book" and not is_request(
        value.get("content_type")
    ):
        return False
    return True


def _extract_title_pid_generic(value, fallback=None):
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

    return fallback


def _book_identifiers_from_pid(pid_generic):
    value = str(pid_generic or "")
    if not value.upper().startswith("BOOK:"):
        return {}

    identifiers = {}
    parts = value.split("/", 1)
    book_id = parts[0].split(":", 1)[1] if ":" in parts[0] else ""
    if book_id:
        identifiers["book_id"] = book_id

    if len(parts) > 1 and parts[1].upper().startswith("CHAPTER:"):
        chapter_id = parts[1].split(":", 1)[1] if ":" in parts[1] else ""
        if chapter_id:
            identifiers["chapter_id"] = chapter_id

    return identifiers
