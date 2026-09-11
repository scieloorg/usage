from scielo_usage_counter.counter import get_valid_clicks, is_request

from metrics.opensearch.keys import UNKNOWN_VALUE, document_key, metric_key, source_key


class DocumentPipeline:
    data_type = "Other"

    def accumulate(self, data, unique_state, value, projection=None):
        if not isinstance(value, dict):
            return

        document_id = self._generate_document_id(value, projection=projection)
        document = data.setdefault(
            document_id,
            self._build_document(value=value, projection=projection),
        )

        self._apply_totals(
            document=document,
            click_timestamps=value.get("click_timestamps"),
            click_timestamps_by_url=value.get("click_timestamps_by_url"),
            content_type=value.get("content_type"),
        )
        self._apply_uniques(
            document=document,
            unique_state=unique_state,
            scope="item",
            document_id=document_id,
            user_session_id=value.get("user_session_id"),
            is_request_event=is_request(value.get("content_type")),
        )

    def partition_key(self, value, projection=None):
        return self._generate_document_id(value, projection=projection)

    def _generate_document_id(
        self, value, projection=None, metric_scope=None, pid_generic=None
    ):
        pid_generic = pid_generic or value.get("pid_generic")
        counter = self._build_counter_section(value)
        if metric_scope == "title":
            counter["metric_scope"] = "title"
            counter["data_type"] = "Book"
            counter.pop("parent_data_type", None)
        source_identifier = self._source_key(value)
        document_identifier = self._document_key(
            value,
            pid_generic=pid_generic,
            metric_scope=metric_scope,
        )
        country_code, content_language = self._projection_values(value, projection)
        return metric_key(
            collection=value.get("collection"),
            source_identifier=source_identifier,
            document_identifier=document_identifier,
            period=(
                self._access_year(value) if projection else self._access_month(value)
            ),
            metric_scope=counter.get("metric_scope"),
            data_type=counter.get("data_type"),
            parent_data_type=counter.get("parent_data_type"),
            article_version=counter.get("article_version"),
            access_type=counter.get("access_type"),
            access_method=counter.get("access_method"),
            projection=projection,
            country_code=country_code,
            content_language=content_language,
        )

    def _build_document(self, value, projection=None, **kwargs):
        counter = self._build_counter_section(value)
        source_identifier = self._source_key(value)
        document_identifier = self._document_key(value)

        if projection:
            country_code, content_language = self._projection_values(
                value,
                projection,
            )
            analytics_document = {
                "year": self._access_year(value),
                "source_key": source_identifier,
                "document_key": document_identifier,
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
            "source_key": source_identifier,
            "document_key": document_identifier,
            "month": self._access_month(value),
            **counter,
            "total_requests": 0,
            "total_investigations": 0,
            "unique_requests": 0,
            "unique_investigations": 0,
        }
        base_document["daily_metrics"] = self._build_daily_metrics(value)
        return _strip_empty_values(base_document)

    def _resolve_document_id(self, value):
        return value.get("pid_v3") or value.get("pid_v2") or value.get("pid_generic")

    def _source_key(self, value):
        source = value.get("source") or {}
        raw_source_id = source.get("source_id") or value.get("source_key")
        return source_key(
            value.get("collection"),
            source.get("source_type"),
            raw_source_id,
        )

    def _document_key(self, value, pid_generic=None, metric_scope=None):
        raw_document_id = pid_generic or self._resolve_document_id(value)
        document_type = (
            "book" if metric_scope == "title" else value.get("document_type")
        )
        return document_key(
            value.get("collection"),
            document_type,
            raw_document_id,
        )

    @staticmethod
    def _access_month(value):
        access_date = value.get("access_date") or ""
        return access_date[:7]

    @staticmethod
    def _access_year(value):
        access_date = value.get("access_date") or ""
        return access_date[:4]

    @staticmethod
    def _projection_values(value, projection):
        if projection == "country_language":
            return (
                value.get("access_country_code") or UNKNOWN_VALUE,
                value.get("content_language") or UNKNOWN_VALUE,
            )
        return None, None

    def _resolve_parent_data_type(self, value):
        return None

    def _build_counter_section(self, value):
        return _strip_empty_values(
            {
                "metric_scope": "item",
                "data_type": self.data_type,
                "parent_data_type": self._resolve_parent_data_type(value),
                "access_type": value.get("counter_access_type") or "Open",
                "access_method": value.get("access_method") or "Regular",
            }
        )

    @staticmethod
    def _build_daily_metrics(value):
        day = value.get("access_date", "")[-2:] if value.get("access_date") else "01"
        return {
            day: {
                "total_requests": 0,
                "total_investigations": 0,
                "unique_requests": 0,
                "unique_investigations": 0,
            }
        }

    @staticmethod
    def _apply_totals(
        document, click_timestamps, content_type, click_timestamps_by_url=None
    ):
        number_of_clicks = _count_valid_clicks(
            click_timestamps=click_timestamps,
            click_timestamps_by_url=click_timestamps_by_url,
        )

        document["total_investigations"] += number_of_clicks
        if is_request(content_type):
            document["total_requests"] += number_of_clicks

        if "daily_metrics" in document:
            day_key = list(document["daily_metrics"].keys())[0]
            document["daily_metrics"][day_key][
                "total_investigations"
            ] += number_of_clicks
            if is_request(content_type):
                document["daily_metrics"][day_key]["total_requests"] += number_of_clicks

    @staticmethod
    def _apply_uniques(
        document,
        unique_state,
        scope,
        document_id,
        user_session_id,
        is_request_event,
    ):
        if not user_session_id:
            return

        inv_bucket = unique_state[f"{scope}_investigations"]
        inv_key = (document_id, user_session_id)
        add_investigation = inv_key not in inv_bucket
        if add_investigation:
            inv_bucket.add(inv_key)

        add_request = False
        if is_request_event:
            req_bucket = unique_state[f"{scope}_requests"]
            req_key = (document_id, user_session_id)
            add_request = req_key not in req_bucket
            if add_request:
                req_bucket.add(req_key)

        _increment_document_uniques(
            document=document,
            add_investigation=add_investigation,
            add_request=add_request,
        )


def _increment_document_uniques(document, add_investigation=False, add_request=False):
    if add_investigation:
        document["unique_investigations"] += 1
    if add_request:
        document["unique_requests"] += 1

    if "daily_metrics" in document:
        day_key = list(document["daily_metrics"].keys())[0]
        if add_investigation:
            document["daily_metrics"][day_key]["unique_investigations"] += 1
        if add_request:
            document["daily_metrics"][day_key]["unique_requests"] += 1


def _count_valid_clicks(click_timestamps, click_timestamps_by_url=None):
    if isinstance(click_timestamps_by_url, dict) and click_timestamps_by_url:
        return sum(
            get_valid_clicks(timestamps or {})
            for timestamps in click_timestamps_by_url.values()
        )
    return get_valid_clicks(click_timestamps or {})


def _strip_empty_values(data):
    return {
        key: value for key, value in data.items() if value not in (None, "", [], {}, ())
    }
