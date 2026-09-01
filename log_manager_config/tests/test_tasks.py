from unittest.mock import patch

import pytest

from collection.models import Collection
from config.collections import COLLECTION_OPAC_URL_MAP, LOG_MANAGER_SEED_DATA
from log_manager_config import tasks


EXPECTED_LOG_DIRECTORIES = {
    ("arg", "/app/logs/bkp-ratchet/scielo.ar", "classic"),
    ("bol", "/app/logs/bkp-ratchet/scielo.bo", "classic"),
    ("books", "/app/logs/bkp-bunnynet/books", "books"),
    ("chl", "/app/logs/bkp-ratchet/scielo.cl", "classic"),
    ("col", "/app/logs/bkp-ratchet/scielo.co", "classic"),
    ("cri", "/app/logs/bkp-ratchet/scielo.cr", "classic"),
    ("cub", "/app/logs/bkp-ratchet/scielo.cu", "classic"),
    ("ecu", "/app/logs/bkp-ratchet/scielo.ec", "classic"),
    ("esp", "/app/logs/bkp-ratchet/scielo.es", "classic"),
    ("mex", "/app/logs/bkp-ratchet/scielo.mx", "classic"),
    ("per", "/app/logs/bkp-ratchet/scielo.pe", "classic"),
    ("prt", "/app/logs/bkp-ratchet/scielo.pt", "classic"),
    ("pry", "/app/logs/bkp-ratchet/scielo.py", "classic"),
    ("psi", "/app/logs/bkp-ratchet/scielo.pepsic", "classic"),
    ("rve", "/app/logs/bkp-ratchet/scielo.revenf", "classic"),
    ("scl", "/app/logs/bkp-bunnynet/scielo-br", "opac"),
    ("scl", "/app/logs/bkp-bunnynet/scielo-br-2", "opac"),
    ("sza", "/app/logs/bkp-ratchet/scielo.za", "classic"),
    ("ury", "/app/logs/bkp-ratchet/scielo.uy", "classic"),
    ("ven", "/app/logs/bkp-ratchet/scielo.ve", "classic"),
    ("wid", "/app/logs/bkp-bunnynet/caribbean", "classic"),
}


def test_default_seed_matches_active_log_directories():
    configured_directories = {
        (item["acronym"], item["path"], item["translator_class"])
        for item in LOG_MANAGER_SEED_DATA
    }

    assert configured_directories == EXPECTED_LOG_DIRECTORIES
    assert {
        item["quantity"]
        for item in LOG_MANAGER_SEED_DATA
        if item["acronym"] == "scl"
    } == {2}
    assert not {
        "data",
        "dom",
        "preprints",
        "rvt",
        "spa",
        "sss",
    } & {item["acronym"] for item in LOG_MANAGER_SEED_DATA}


@pytest.mark.django_db
def test_default_seed_configures_collection_opac_urls():
    scl = Collection.objects.create(acron3="scl")
    dom = Collection.objects.create(acron3="dom")

    with (
        patch.object(tasks, "LOG_MANAGER_SEED_DATA", []),
        patch.object(tasks, "_get_user", return_value=None),
    ):
        tasks.task_load_log_manager_collection_settings.run()

    scl.refresh_from_db()
    dom.refresh_from_db()

    assert scl.opac_url == COLLECTION_OPAC_URL_MAP["scl"]
    assert dom.opac_url == COLLECTION_OPAC_URL_MAP["dom"]
