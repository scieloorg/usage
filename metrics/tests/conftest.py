from datetime import date
from pathlib import Path

import pytest

from collection.models import Collection
from log_manager import choices
from log_manager.models import LogFile

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def books_collection(db):
    return Collection.objects.create(acron3="books", acron2="bk")


@pytest.fixture
def scl_collection(db):
    return Collection.objects.create(acron3="scl", acron2="sc")


@pytest.fixture
def preprints_collection(db):
    return Collection.objects.create(acron3="preprints", acron2="pp")


@pytest.fixture
def data_collection(db):
    return Collection.objects.create(acron3="data", acron2="dt")


@pytest.fixture
def robots_list():
    path = FIXTURES_DIR / "counter-robots.txt"
    return path.read_text().splitlines()


@pytest.fixture
def mmdb_data():
    path = FIXTURES_DIR / "map.mmdb"
    return path.read_bytes()


@pytest.fixture
def log_file_factory(db):
    def _create(collection, hash_value, **kwargs):
        defaults = {
            "path": f"/tmp/{hash_value}.log.gz",
            "stat_result": {},
            "status": choices.LOG_FILE_STATUS_QUEUED,
            "date": date(2024, 1, 15),
            "validation": {"probably_date": "2024-01-15"},
        }
        defaults.update(kwargs)
        return LogFile.objects.create(
            collection=collection, hash=hash_value, **defaults
        )

    return _create
