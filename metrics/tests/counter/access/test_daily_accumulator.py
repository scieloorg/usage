from metrics.counter.access.daily_accumulator import DailyAccessAccumulator


def _record(pid_v3):
    return {
        "collection": "scl",
        "source_key": "1234-5678",
        "document_type": "article",
        "pid_v2": "S123456782026000100001",
        "pid_v3": pid_v3,
        "pid_generic": None,
        "title_pid_generic": None,
        "source": {"source_id": "1234-5678", "main_title": "Journal"},
        "document": {"title": f"Article {pid_v3}"},
    }


def _accumulate(accumulator, pid_v3, session_ip):
    accumulator.accumulate_access(
        data=_record(pid_v3),
        session_key=("Firefox", "1", session_ip, 739491, 10),
        url=f"/{pid_v3}",
        second=5,
    )


def test_materialization_preserves_insertion_order():
    accumulator = DailyAccessAccumulator()
    _accumulate(accumulator, "first", "127.0.0.1")
    _accumulate(accumulator, "second", "127.0.0.2")

    values = list(accumulator.iter_materialized_values())

    assert [value["pid_v3"] for value in values] == ["first", "second"]


def test_consuming_materialization_releases_all_internal_structures():
    accumulator = DailyAccessAccumulator()
    _accumulate(accumulator, "first", "127.0.0.1")
    _accumulate(accumulator, "second", "127.0.0.2")

    values = list(accumulator.iter_materialized_values(consume=True))

    assert [value["pid_v3"] for value in values] == ["first", "second"]
    assert len(accumulator) == 0
    assert accumulator._documents == []
    assert accumulator._document_ids == {}
    assert accumulator._sources == []
    assert accumulator._source_ids == {}
    assert accumulator._sessions == {}
    assert accumulator._strings == []
    assert accumulator._string_ids == {}


def test_consuming_materialization_releases_structures_after_consumer_error():
    accumulator = DailyAccessAccumulator()
    _accumulate(accumulator, "first", "127.0.0.1")
    values = accumulator.iter_materialized_values(consume=True)

    next(values)
    values.close()

    assert len(accumulator) == 0
    assert accumulator._documents == []


def test_partitioned_year_conversion_releases_accumulator_after_consumer_error():
    from metrics.counter.indexing import converter

    accumulator = DailyAccessAccumulator()
    _accumulate(accumulator, "first", "127.0.0.1")
    _accumulate(accumulator, "second", "127.0.0.2")
    documents = converter.iter_partitioned_documents(
        accumulator,
        "year",
        partition_count=2,
    )

    next(documents)
    documents.close()

    assert len(accumulator) == 0
    assert accumulator._documents == []
