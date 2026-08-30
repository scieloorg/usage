class DailyAccessAccumulator(dict):
    def __init__(self):
        super().__init__()
        self._documents = {}
        self._sources = {}
        self._sessions = {}

    def __setitem__(self, key, value):
        source_key = value.get("source_key")
        source = value.get("source")
        if source_key and source:
            value["source"] = self._sources.setdefault(source_key, source)

        document_key = (
            value.get("document_type"),
            value.get("pid_v2"),
            value.get("pid_v3"),
            value.get("pid_generic"),
            value.get("title_pid_generic"),
        )
        document = value.get("document")
        if document and any(document_key):
            value["document"] = self._documents.setdefault(document_key, document)

        user_session_id = value.get("user_session_id")
        if user_session_id:
            value["user_session_id"] = self._sessions.setdefault(
                user_session_id,
                user_session_id,
            )

        super().__setitem__(key, value)
