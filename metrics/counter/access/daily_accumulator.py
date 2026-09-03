from struct import Struct

_ACCESS_KEY = Struct("!10I")
_SESSION_KEY = Struct("!5I")
_NONE_METADATA_ID = 0
_EMPTY_DOCUMENT_ID = 1


class _CompactAccessRecord:
    __slots__ = (
        "access_method",
        "access_date",
        "access_month",
        "access_year",
        "collection",
        "content_language",
        "content_type",
        "counter_access_type",
        "country_code",
        "document",
        "document_type",
        "first_second",
        "first_url",
        "media_format",
        "multiple_timestamps",
        "pid_generic",
        "pid_v2",
        "pid_v3",
        "publication_year",
        "session",
        "source",
        "source_key",
        "title_pid_generic",
    )

    def __init__(self, accumulator, data, session, url, second):
        self.collection = accumulator._intern(data.get("collection"))
        self.source_key = accumulator._intern(data.get("source_key"))
        self.document_type = accumulator._intern(data.get("document_type"))
        self.pid_v2 = accumulator._intern(data.get("pid_v2"))
        self.pid_v3 = accumulator._intern(data.get("pid_v3"))
        self.pid_generic = accumulator._intern(data.get("pid_generic"))
        self.title_pid_generic = accumulator._intern(data.get("title_pid_generic"))
        self.media_format = accumulator._intern(data.get("media_format"))
        self.content_language = accumulator._intern(data.get("content_language"))
        self.content_type = accumulator._intern(data.get("content_type"))
        self.country_code = accumulator._intern(data.get("access_country_code"))
        self.access_date = accumulator._intern(data.get("access_date"))
        self.access_year = accumulator._intern(data.get("access_year"))
        self.access_month = accumulator._intern(data.get("access_month"))
        self.publication_year = accumulator._intern(data.get("publication_year"))
        self.counter_access_type = accumulator._intern(data.get("counter_access_type"))
        self.access_method = accumulator._intern(data.get("access_method"))
        self.source = accumulator._intern_source(
            data.get("source_key"),
            data.get("source"),
        )
        self.document = accumulator._intern_document(data, share_empty=True)
        self.session = session
        self.first_url = accumulator._intern(url)
        self.first_second = second
        self.multiple_timestamps = None

    def add_timestamp(self, url, second):
        if self.multiple_timestamps is None:
            if url == self.first_url and second == self.first_second:
                return
            self.multiple_timestamps = {self.first_url: self.first_second}

        current = self.multiple_timestamps.get(url)
        if current is None:
            self.multiple_timestamps[url] = second
        elif isinstance(current, int):
            if current != second:
                self.multiple_timestamps[url] = {current, second}
        else:
            current.add(second)

    def as_dict(self, accumulator):
        return {
            "collection": accumulator._resolve(self.collection),
            "source_key": accumulator._resolve(self.source_key),
            "document_type": accumulator._resolve(self.document_type),
            "pid_v2": accumulator._resolve(self.pid_v2),
            "pid_v3": accumulator._resolve(self.pid_v3),
            "pid_generic": accumulator._resolve(self.pid_generic),
            "document": accumulator._documents[self.document],
            "title_pid_generic": accumulator._resolve(self.title_pid_generic),
            "user_session_id": self.session,
            "click_timestamps_by_url": self._timestamps_as_dict(accumulator),
            "media_format": accumulator._resolve(self.media_format),
            "content_language": accumulator._resolve(self.content_language),
            "content_type": accumulator._resolve(self.content_type),
            "access_country_code": accumulator._resolve(self.country_code),
            "access_date": accumulator._resolve(self.access_date),
            "access_year": accumulator._resolve(self.access_year),
            "access_month": accumulator._resolve(self.access_month),
            "publication_year": accumulator._resolve(self.publication_year),
            "counter_access_type": accumulator._resolve(self.counter_access_type),
            "access_method": accumulator._resolve(self.access_method),
            "source": accumulator._sources[self.source],
        }

    def _timestamps_as_dict(self, accumulator):
        if self.multiple_timestamps is None:
            return {
                accumulator._resolve(self.first_url): {self.first_second: 1},
            }

        timestamps = {}
        for url, seconds in self.multiple_timestamps.items():
            if isinstance(seconds, int):
                seconds = (seconds,)
            timestamps[accumulator._resolve(url)] = {
                second: 1 for second in sorted(seconds)
            }
        return timestamps


class DailyAccessAccumulator:
    """Store compact records and materialize them only for metric conversion."""

    def __init__(self):
        self._records = {}
        self._documents = [None, {}]
        self._document_ids = {}
        self._sources = [None]
        self._source_ids = {}
        self._sessions = {}
        self._strings = [None]
        self._string_ids = {}

    def __len__(self):
        return len(self._records)

    def accumulate_access(self, data, session_key, url, second):
        session = self._intern_session(session_key)
        key = _ACCESS_KEY.pack(
            self._intern(data.get("collection")),
            self._intern(data.get("source_key")),
            self._intern(data.get("pid_v2")),
            self._intern(data.get("pid_v3")),
            self._intern(data.get("pid_generic")),
            session,
            self._intern(data.get("access_country_code")),
            self._intern(data.get("content_language")),
            self._intern(data.get("media_format")),
            self._intern(data.get("content_type")),
        )
        record = self._records.get(key)
        if record is None:
            record = _CompactAccessRecord(self, data, session, url, second)
            self._records[key] = record
            return
        record.add_timestamp(self._intern(url), second)

    def iter_materialized_values(self, consume=False):
        if not consume:
            for value in self._records.values():
                yield value.as_dict(self)
            return

        keys = tuple(self._records)
        try:
            for key in keys:
                yield self._records.pop(key).as_dict(self)
        finally:
            self.clear()

    def clear(self):
        self._records.clear()
        self._documents.clear()
        self._document_ids.clear()
        self._sources.clear()
        self._source_ids.clear()
        self._sessions.clear()
        self._strings.clear()
        self._string_ids.clear()

    def _intern(self, value):
        if value is None:
            return 0
        value_id = self._string_ids.get(value)
        if value_id is None:
            value_id = len(self._strings)
            self._string_ids[value] = value_id
            self._strings.append(value)
        return value_id

    def _resolve(self, value_id):
        return self._strings[value_id]

    def _intern_session(self, session_key):
        compact_key = _SESSION_KEY.pack(
            self._intern(session_key[0]),
            self._intern(session_key[1]),
            self._intern(session_key[2]),
            session_key[3],
            session_key[4],
        )
        session_id = self._sessions.get(compact_key)
        if session_id is None:
            session_id = len(self._sessions) + 1
            self._sessions[compact_key] = session_id
        return session_id

    def _intern_source(self, source_key, source):
        if source is None:
            return _NONE_METADATA_ID
        if not source_key:
            self._sources.append(source)
            return len(self._sources) - 1
        source_id = self._source_ids.get(source_key)
        if source_id is None:
            source_id = len(self._sources)
            self._source_ids[source_key] = source_id
            self._sources.append(source)
        return source_id

    def _intern_document(self, data, share_empty=False):
        document_key = self._document_key(data)
        document = data.get("document")
        if document is None:
            return _NONE_METADATA_ID
        if share_empty and not document:
            return _EMPTY_DOCUMENT_ID
        if not any(document_key[1:]):
            self._documents.append(document)
            return len(self._documents) - 1
        document_id = self._document_ids.get(document_key)
        if document_id is None:
            document_id = len(self._documents)
            self._document_ids[document_key] = document_id
            self._documents.append(document)
        return document_id

    @staticmethod
    def _document_key(data):
        return (
            data.get("document_type"),
            data.get("pid_v2"),
            data.get("pid_v3"),
            data.get("pid_generic"),
            data.get("title_pid_generic"),
        )
