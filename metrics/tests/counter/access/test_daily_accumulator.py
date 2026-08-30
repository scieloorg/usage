from metrics.counter.access.daily_accumulator import DailyAccessAccumulator


def _record(session_id, **overrides):
    record = {
        "collection": "scl",
        "source_key": "1234-5678",
        "document_type": "article",
        "pid_v2": "S123456782026000100001",
        "pid_v3": "abc123",
        "pid_generic": None,
        "title_pid_generic": None,
        "source": {"source_id": "1234-5678", "main_title": "Journal"},
        "document": {"title": "Article"},
        "user_session_id": session_id,
    }
    record.update(overrides)
    return record


def test_interns_repeated_metadata_and_sessions():
    accumulator = DailyAccessAccumulator()
    first_session = "|".join(["Firefox", "1", "127.0.0.1", "2026-08-25", "10"])
    second_session = "|".join(["Firefox", "1", "127.0.0.1", "2026-08-25", "10"])
    assert first_session is not second_session

    accumulator["first"] = _record(first_session)
    accumulator["second"] = _record(second_session)

    assert accumulator["first"]["source"] is accumulator["second"]["source"]
    assert accumulator["first"]["document"] is accumulator["second"]["document"]
    assert (
        accumulator["first"]["user_session_id"]
        is accumulator["second"]["user_session_id"]
    )


def test_interns_empty_document_metadata_for_the_same_document():
    accumulator = DailyAccessAccumulator()

    accumulator["first"] = _record("first", document={})
    accumulator["second"] = _record("second", document={})

    assert accumulator["first"]["document"] is accumulator["second"]["document"]


def test_does_not_share_metadata_between_distinct_documents():
    accumulator = DailyAccessAccumulator()

    accumulator["first"] = _record("first", pid_v3="first", document={})
    accumulator["second"] = _record("second", pid_v3="second", document={})

    assert accumulator["first"]["document"] is not accumulator["second"]["document"]


def test_does_not_share_documents_without_identifiers():
    accumulator = DailyAccessAccumulator()
    identifiers = {
        "pid_v2": None,
        "pid_v3": None,
        "pid_generic": None,
        "title_pid_generic": None,
    }

    accumulator["first"] = _record("first", document={}, **identifiers)
    accumulator["second"] = _record("second", document={}, **identifiers)

    assert accumulator["first"]["document"] is not accumulator["second"]["document"]
