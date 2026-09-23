import unittest
from datetime import datetime

from scielo_usage_counter.url_translator import URLTranslationManager
from scielo_usage_counter.values import (
    CONTENT_TYPE_ABSTRACT,
    CONTENT_TYPE_FULL_TEXT,
    MEDIA_FORMAT_HTML,
)

from metrics.counter.access import accumulation, extraction
from metrics.counter.access.daily_accumulator import DailyAccessAccumulator
from metrics.opensearch.keys import document_key
from metrics.tests.helpers import convert_accumulator


class TestPreprintPipeline(unittest.TestCase):
    def _build_preprint_access(self, **overrides):
        base = {
            "pid_generic": "10.1590/SciELOPreprints.1234",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_FULL_TEXT,
            "media_language": "en",
        }
        base.update(overrides)
        return extraction.extract("preprints", base)

    def test_extraction_sets_preprint_types(self):
        data = self._build_preprint_access()
        self.assertEqual(data["source_type"], "preprint_server")
        self.assertEqual(data["document_type"], "preprint")
        self.assertEqual(data["source_id"], "scielo-preprints")

    def test_full_pipeline_produces_preprint_article_version(self):
        counter_access = self._build_preprint_access()
        results = DailyAccessAccumulator()
        line = {
            "client_name": "browser",
            "client_version": "1.0",
            "ip_address": "200.1.2.3",
            "country_code": "BR",
            "local_datetime": datetime(2024, 6, 15, 14, 30, 10),
        }
        accumulation.accumulate(results, counter_access, line)
        metrics = convert_accumulator(results)

        counter_docs = list(metrics["counter"].values())
        self.assertEqual(len(counter_docs), 1)
        doc = counter_docs[0]
        self.assertEqual(doc["data_type"], "Article")
        self.assertEqual(doc["article_version"], "Preprint")
        self.assertEqual(doc["metric_scope"], "item")
        self.assertEqual(doc["total_requests"], 1)
        self.assertEqual(doc["unique_requests"], 1)


class TestDataversePipeline(unittest.TestCase):
    def _build_dataset_access(self, **overrides):
        base = {
            "pid_generic": "10.48331/scielodata.abc123",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_ABSTRACT,
        }
        base.update(overrides)
        return extraction.extract("data", base)

    def test_extraction_sets_dataset_types(self):
        data = self._build_dataset_access()
        self.assertEqual(data["source_type"], "data_repository")
        self.assertEqual(data["document_type"], "dataset")
        self.assertEqual(data["source_id"], "scielo-data")

    def test_full_pipeline_produces_dataset_metrics(self):
        counter_access = self._build_dataset_access()
        results = DailyAccessAccumulator()
        line = {
            "client_name": "browser",
            "client_version": "1.0",
            "ip_address": "200.1.2.3",
            "country_code": "BR",
            "local_datetime": datetime(2024, 6, 15, 14, 30, 10),
        }
        accumulation.accumulate(results, counter_access, line)
        metrics = convert_accumulator(results)

        counter_docs = list(metrics["counter"].values())
        self.assertEqual(len(counter_docs), 1)
        doc = counter_docs[0]
        self.assertEqual(doc["data_type"], "Dataset")
        self.assertNotIn("article_version", doc)
        self.assertEqual(doc["total_investigations"], 1)
        self.assertEqual(doc["total_requests"], 0)


class TestOPACPipeline(unittest.TestCase):
    def test_opac_article_produces_journal_article_metrics(self):
        counter_access = extraction.extract(
            "scl",
            {
                "scielo_issn": "1234-5678",
                "pid_v3": "S1234-56782024000100001",
                "article_title": "Test OPAC Article",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "media_language": "pt",
                "journal_main_title": "Test Journal",
                "journal_acronym": "testjou",
                "journal_publisher_name": ["SciELO"],
            },
        )

        results = DailyAccessAccumulator()
        line = {
            "client_name": "Chrome",
            "client_version": "120.0",
            "ip_address": "189.10.20.30",
            "country_code": "BR",
            "local_datetime": datetime(2024, 3, 20, 8, 15, 42),
        }
        accumulation.accumulate(results, counter_access, line)
        metrics = convert_accumulator(results)

        doc = list(metrics["counter"].values())[0]
        self.assertEqual(doc["data_type"], "Article")
        self.assertEqual(doc["parent_data_type"], "Journal")
        self.assertTrue(doc["source_key"].startswith("k1_"))
        self.assertTrue(doc["document_key"].startswith("k1_"))
        self.assertEqual(doc["total_requests"], 1)

    def test_classic_and_opac_urls_share_article_and_session(self):
        pid_v2 = "S0103-63512021000100001"
        pid_v3 = "dqLRqnpmnncSmnzMCB8bzPG"
        translator = URLTranslationManager(
            sources_metadata=[{"acronym": "neco", "scielo_issn": "0103-6351"}],
            documents_metadata=[
                {
                    "pid_v2": pid_v2,
                    "pid_v3": pid_v3,
                    "default_lang": "pt",
                    "text_langs": ["pt"],
                    "scielo_issn": "0103-6351",
                    "publication_year": "2021",
                }
            ],
        )
        results = DailyAccessAccumulator()
        urls = (
            f"/scielo.php?script=sci_arttext&pid={pid_v2}",
            f"/j/neco/a/{pid_v2}/?format=html",
            f"/j/neco/a/{pid_v3}/?format=html",
        )

        for minute, url in enumerate(urls):
            line = {
                "url": url,
                "client_name": "Chrome",
                "client_version": "120.0",
                "ip_address": "189.10.20.30",
                "country_code": "BR",
                "local_datetime": datetime(2026, 7, 15, 8, 15 + minute, 0),
            }
            access = extraction.extract("scl", translator.translate(url))
            accumulation.accumulate(results, access, line)

        metrics = convert_accumulator(results)
        self.assertEqual(len(metrics["counter"]), 1)
        self.assertEqual(len(metrics["analytics"]), 1)

        article = next(iter(metrics["counter"].values()))
        self.assertEqual(
            article["document_key"],
            document_key("scl", "article", pid_v3),
        )
        self.assertEqual(article["total_requests"], 3)
        self.assertEqual(article["unique_requests"], 1)
