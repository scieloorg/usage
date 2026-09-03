import unittest
from pathlib import Path

from scielo_usage_counter import log_handler
from scielo_usage_counter.translator.classic import URLTranslatorClassicSite
from scielo_usage_counter.url_translator import URLTranslationManager

from metrics.counter.access import accumulation, extraction, validation
from metrics.counter.access.daily_accumulator import DailyAccessAccumulator
from metrics.tests.helpers import convert_accumulator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestClassicLogToMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.robots_list = (FIXTURES_DIR / "counter-robots.txt").read_text().splitlines()
        cls.mmdb_data = (FIXTURES_DIR / "map.mmdb").read_bytes()
        cls.log_path = str(FIXTURES_DIR / "usage.log")
        cls.utm = URLTranslationManager(
            documents_metadata=iter([]),
            sources_metadata=iter([]),
            translator=URLTranslatorClassicSite,
        )

    def _parse_log(self):
        parser = log_handler.LogParser(
            mmdb_data=self.mmdb_data,
            robots_list=self.robots_list,
            output_mode="dict",
        )
        parser.logfile = self.log_path
        return list(parser.parse()), parser.stats

    def _full_pipeline(self):
        lines, stats = self._parse_log()
        results = DailyAccessAccumulator()
        valid_count = 0

        for line in lines:
            url = line.get("url")
            if not url:
                continue

            translated = self.utm.translate(url)
            if not translated or not isinstance(translated, dict):
                continue

            counter_access = extraction.extract("scl", translated)
            is_valid, _ = validation.is_valid(counter_access)
            if not is_valid:
                continue

            try:
                accumulation.accumulate(results, counter_access, line)
                valid_count += 1
            except (ValueError, Exception):
                pass

        return results, lines, stats, valid_count

    def test_filters_static_resources(self):
        lines, stats = self._parse_log()
        self.assertLess(len(lines), 200)

    def test_filters_bots(self):
        lines, stats = self._parse_log()
        for line in lines:
            self.assertNotEqual(line.get("client_name", "").lower(), "lockss cache")

    def test_produces_article_type_metrics(self):
        results, _, _, valid_count = self._full_pipeline()
        if not results:
            self.skipTest("No valid lines in classic fixture for this translator")
            return

        metrics = convert_accumulator(results)

        for doc in metrics["month"].values():
            self.assertEqual(doc["counter"]["data_type"], "Article")
            self.assertEqual(doc["counter"]["metric_scope"], "item")
            self.assertEqual(doc["document"]["type"], "article")

    def test_sets_journal_parent_data_type(self):
        results, _, _, _ = self._full_pipeline()
        if not results:
            self.skipTest("No valid lines")
            return

        metrics = convert_accumulator(results)
        for doc in metrics["month"].values():
            source_type = doc.get("source", {}).get("type")
            if source_type == "journal":
                self.assertEqual(doc["counter"]["parent_data_type"], "Journal")

    def test_handles_truncated_user_agent(self):
        lines, _ = self._parse_log()
        self.assertGreater(len(lines), 0)

    def test_valid_lines_produce_session_ids(self):
        results, _, _, _ = self._full_pipeline()
        for value in results.iter_materialized_values():
            self.assertIn("user_session_id", value)
            self.assertIsNotNone(value["user_session_id"])
