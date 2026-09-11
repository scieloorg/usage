from unittest.mock import patch

import pytest

from collection.models import Collection
from config.collections import COLLECTION_OPAC_URL_MAP, LOG_MANAGER_SEED_DATA
from log_manager_config import tasks

EXPECTED_LOG_DIRECTORIES = {
    ("arg", "/app/logs/bkp-ratchet/scielo.ar", "classic", True),
    ("bol", "/app/logs/bkp-ratchet/scielo.bo", "classic", True),
    ("books", "/app/logs/bkp-bunnynet/books", "books", True),
    ("chl", "/app/logs/bkp-ratchet/scielo.cl", "classic", True),
    ("col", "/app/logs/bkp-ratchet/scielo.co", "classic", True),
    ("cri", "/app/logs/bkp-ratchet/scielo.cr", "classic", True),
    ("cub", "/app/logs/bkp-ratchet/scielo.cu", "classic", True),
    ("data", "/app/logs/bkp-dataverse", "dataverse", False),
    ("data", "/app/logs/bkp-bunnynet/data", "dataverse", True),
    ("ecu", "/app/logs/bkp-ratchet/scielo.ec", "classic", True),
    ("esp", "/app/logs/bkp-ratchet/scielo.es", "classic", True),
    ("mex", "/app/logs/bkp-ratchet/scielo.mx", "classic", True),
    ("per", "/app/logs/bkp-ratchet/scielo.pe", "classic", True),
    ("preprints", "/app/logs/bkp-bunnynet/preprints", "preprints", True),
    ("prt", "/app/logs/bkp-ratchet/scielo.pt", "classic", True),
    ("pry", "/app/logs/bkp-ratchet/scielo.py", "classic", True),
    ("psi", "/app/logs/bkp-ratchet/scielo.pepsic", "classic", True),
    ("rve", "/app/logs/bkp-ratchet/scielo.revenf", "classic", True),
    ("scl", "/app/logs/bkp-bunnynet/scielo-br", "opac", True),
    ("scl", "/app/logs/bkp-bunnynet/scielo-br-2", "opac", True),
    ("sza", "/app/logs/bkp-ratchet/scielo.za", "classic", True),
    ("ury", "/app/logs/bkp-ratchet/scielo.uy", "classic", True),
    ("ven", "/app/logs/bkp-venezuela", "classic", False),
    ("ven", "/app/logs/bkp-ratchet/scielo.ve", "classic", False),
    ("ven", "/app/logs/bkp-bunnynet/venezuela", "classic", True),
    ("wid", "/app/logs/bkp-ratchet/scielo.wi", "classic", False),
    ("wid", "/app/logs/bkp-bunnynet/caribbean", "classic", False),
    ("wid", "/app/logs/bkp-bunnynet/westindies", "classic", True),
}


def test_default_seed_matches_log_directories():
    configured_directories = {
        (
            item["acronym"],
            item["path"],
            item["translator_class"],
            item.get("directory_active", True),
        )
        for item in LOG_MANAGER_SEED_DATA
    }

    assert configured_directories == EXPECTED_LOG_DIRECTORIES
    assert {
        item["quantity"] for item in LOG_MANAGER_SEED_DATA if item["acronym"] == "scl"
    } == {2}
    assert {
        item.get("opensearch_primary_shards", 1)
        for item in LOG_MANAGER_SEED_DATA
        if item["acronym"] == "scl"
    } == {1}
    assert {
        item["acronym"]
        for item in LOG_MANAGER_SEED_DATA
        if item.get("opensearch_partition_strategy", "rollover") == "yearly"
    } == {"chl", "col", "mex", "scl"}
    assert not {
        "dom",
        "rvt",
        "spa",
        "sss",
    } & {item["acronym"] for item in LOG_MANAGER_SEED_DATA}


def test_default_seed_preserves_validation_sample_policy():
    sample_sizes = {
        item["acronym"]: item.get(
            "sample_size",
            tasks.DEFAULT_VALIDATION_SAMPLE_SIZE,
        )
        for item in LOG_MANAGER_SEED_DATA
    }

    assert {
        acronym for acronym, sample_size in sample_sizes.items() if sample_size == 0.1
    } == {"chl", "col", "mex", "scl"}
    assert {
        acronym for acronym, sample_size in sample_sizes.items() if sample_size == 0.5
    } == {"cri", "esp", "prt", "psi", "ven"}


def test_custom_seed_gets_defaults_without_mutating_input():
    data = [{"acronym": "custom"}]

    with (
        patch.object(tasks, "_get_user", return_value=None),
        patch.object(tasks.models.LogManagerCollectionConfig, "load") as load_config,
        patch.object(tasks.models.CollectionLogDirectory, "load"),
        patch.object(tasks.models.CollectionEmail, "load"),
    ):
        tasks.task_load_log_manager_collection_settings.run(data=data)

    loaded_data = load_config.call_args.args[0]
    assert loaded_data == [
        {
            "acronym": "custom",
            "sample_size": tasks.DEFAULT_VALIDATION_SAMPLE_SIZE,
            "buffer_size": tasks.DEFAULT_VALIDATION_BUFFER_SIZE,
        }
    ]
    assert data == [{"acronym": "custom"}]


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
