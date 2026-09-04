from scielo_usage_counter.counter import get_valid_clicks, is_request


class DocumentPipeline:
    data_type = "Other"

    def accumulate(self, data, unique_state, value, granularity):
        if not isinstance(value, dict):
            return

        document_id = self._generate_document_id(value, granularity)
        document = data.setdefault(
            document_id,
            self._build_document(value=value, granularity=granularity),
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

    def partition_key(self, value, granularity):
        return self._generate_document_id(value, granularity)

    def _generate_document_id(
        self, value, granularity, metric_scope=None, pid_generic=None
    ):
        pid_generic = pid_generic or value.get("pid_generic")
        publication_year = str(value.get("publication_year") or "0001")
        if granularity == "month":
            access_month = (
                value.get("access_date", "")[:7] if value.get("access_date") else ""
            )
            return _generate_month_document_id(
                collection=value.get("collection"),
                source_key=value.get("source_key"),
                pid_v2=value.get("pid_v2"),
                pid_v3=value.get("pid_v3"),
                pid_generic=pid_generic,
                access_month=access_month,
                counter_access_type=value.get("counter_access_type") or "Open",
                access_method=value.get("access_method") or "Regular",
                publication_year=publication_year,
                metric_scope="title" if metric_scope == "title" else None,
            )

        return _generate_year_document_id(
            collection=value.get("collection"),
            source_key=value.get("source_key"),
            pid_v2=value.get("pid_v2"),
            pid_v3=value.get("pid_v3"),
            pid_generic=pid_generic,
            content_language=value.get("content_language"),
            access_country_code=value.get("access_country_code"),
            access_year=value.get("access_year"),
            counter_access_type=value.get("counter_access_type") or "Open",
            access_method=value.get("access_method") or "Regular",
            publication_year=publication_year,
            metric_scope="title" if metric_scope == "title" else None,
        )

    def _build_document(self, value, granularity, **kwargs):
        document_type = value.get("document_type")
        document_id = self._resolve_document_id(value)

        base_document = {
            "collection": value.get("collection"),
            "source": self._build_source(value.get("source")),
            "document": self._build_document_section(
                value=value,
                document_id=document_id,
                document_type=document_type,
            ),
            "counter": self._build_counter_section(value),
            "total_requests": 0,
            "total_investigations": 0,
            "unique_requests": 0,
            "unique_investigations": 0,
        }

        base_document["access"] = self._build_access(value, granularity)
        if granularity == "month":
            base_document["daily_metrics"] = self._build_daily_metrics(value)
        return base_document

    def _resolve_document_id(self, value):
        return value.get("pid_v3") or value.get("pid_v2") or value.get("pid_generic")

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

    def _build_document_section(
        self,
        value,
        document_id,
        document_type,
        parent_id=None,
        source_identifiers=None,
        metric_scope="item",
    ):
        document = value.get("document") or {}
        title = document.get("title")
        if metric_scope == "title":
            title = (value.get("source") or {}).get("main_title") or title

        identifiers = self._document_identifiers(
            value=value,
            document_id=document_id,
            source_identifiers=source_identifiers,
            metric_scope=metric_scope,
        )

        return _strip_empty_values(
            {
                "id": document_id,
                "type": document_type,
                "title": title,
                "parent_id": parent_id,
                "publication_year": value.get("publication_year"),
                "identifiers": identifiers,
            }
        )

    def _document_identifiers(
        self, value, document_id, source_identifiers=None, metric_scope="item"
    ):
        document_identifiers = (value.get("document") or {}).get("identifiers") or {}
        identifiers = {
            "pid_v2": value.get("pid_v2"),
            "pid_v3": value.get("pid_v3"),
            "pid_generic": value.get("pid_generic"),
        }
        identifiers.update(document_identifiers)
        return _strip_empty_identifiers(identifiers, canonical_id=document_id)

    @staticmethod
    def _build_source(source):
        source = source or {}
        source_id = source.get("source_id")
        source_type = source.get("source_type")
        identifiers = _strip_empty_identifiers(
            source.get("identifiers") or {}, canonical_id=source_id
        )

        return _strip_empty_values(
            {
                "id": source_id,
                "type": source_type,
                "title": source.get("main_title"),
                "scielo_issn": None
                if source_type == "book"
                else source.get("scielo_issn"),
                "acronym": source.get("acronym"),
                "publisher_name": source.get("publisher_name"),
                "subject_area_capes": source.get("subject_area_capes"),
                "subject_area_wos": source.get("subject_area_wos"),
                "access_type": source.get("access_type"),
                "city": source.get("city"),
                "country": source.get("country"),
                "identifiers": identifiers,
            }
        )

    @staticmethod
    def _build_access(value, granularity):
        if granularity == "month":
            return {
                "month": value.get("access_date", "")[:7]
                if value.get("access_date")
                else ""
            }

        return _strip_empty_values(
            {
                "year": value.get("access_year"),
                "country_code": value.get("access_country_code"),
                "content_language": value.get("content_language"),
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


def _strip_empty_identifiers(identifiers, canonical_id=None):
    compact = {}
    canonical_value = str(canonical_id or "").strip().upper()
    for key, value in (identifiers or {}).items():
        if value in (None, "", [], {}, ()):
            continue
        if canonical_value and str(value).strip().upper() == canonical_value:
            continue
        compact[key] = value
    return compact


def _strip_empty_values(data):
    return {
        key: value for key, value in data.items() if value not in (None, "", [], {}, ())
    }


def _generate_month_document_id(
    collection,
    source_key,
    pid_v2,
    pid_v3,
    pid_generic,
    access_month,
    counter_access_type,
    access_method,
    publication_year,
    metric_scope=None,
):
    parts = []
    if metric_scope:
        parts.append(metric_scope)

    parts.extend(
        [
            str(collection or ""),
            str(source_key or ""),
            pid_v2 or "",
            pid_v3 or "",
            pid_generic or "",
            str(access_month or ""),
            str(counter_access_type or ""),
            str(access_method or ""),
            str(publication_year or ""),
        ]
    )
    return "|".join(parts)


def _generate_year_document_id(
    collection,
    source_key,
    pid_v2,
    pid_v3,
    pid_generic,
    content_language,
    access_country_code,
    access_year,
    counter_access_type,
    access_method,
    publication_year,
    metric_scope=None,
):
    parts = []
    if metric_scope:
        parts.append(metric_scope)

    parts.extend(
        [
            str(collection or ""),
            str(source_key or ""),
            pid_v2 or "",
            pid_v3 or "",
            pid_generic or "",
            content_language or "",
            access_country_code or "",
            str(access_year or ""),
            str(counter_access_type or ""),
            str(access_method or ""),
            str(publication_year or ""),
        ]
    )
    return "|".join(parts)
