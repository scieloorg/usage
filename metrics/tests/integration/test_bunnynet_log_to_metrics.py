import unittest
from pathlib import Path

from scielo_usage_counter import log_handler
from scielo_usage_counter.values import CONTENT_TYPE_FULL_TEXT, MEDIA_FORMAT_HTML

from metrics.counter.access import accumulation, extraction
from metrics.counter.indexing import converter as index_docs

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestBunnynetLogToMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.robots_list = (FIXTURES_DIR / "counter-robots.txt").read_text().splitlines()
        cls.mmdb_data = (FIXTURES_DIR / "map.mmdb").read_bytes()
        cls.log_path = str(FIXTURES_DIR / "usage.scl.bunnynet.log")

    def _parse_log(self):
        parser = log_handler.LogParser(
            mmdb_data=self.mmdb_data,
            robots_list=self.robots_list,
            output_mode="dict",
        )
        parser.logfile = self.log_path
        return list(parser.parse()), parser.stats

    def test_parses_bunnynet_pipe_separated_format(self):
        lines, stats = self._parse_log()
        self.assertGreater(len(lines), 0)

    def test_extracts_urls_from_bunnynet_format(self):
        lines, _ = self._parse_log()
        urls = [line.get("url") for line in lines if line.get("url")]
        self.assertGreater(len(urls), 0)

    def test_resolves_country_codes(self):
        lines, _ = self._parse_log()
        countries = {line.get("country_code") for line in lines}
        countries.discard(None)
        self.assertGreater(len(countries), 0)

    def test_extracts_client_info(self):
        lines, _ = self._parse_log()
        for line in lines[:3]:
            self.assertIn("client_name", line)
            self.assertIn("ip_address", line)

    def test_uses_client_country_and_millisecond_timestamp_in_year_metrics(self):
        parser = log_handler.LogParser(
            mmdb_data=self.mmdb_data,
            robots_list=self.robots_list,
            output_mode="dict",
        )
        line = parser.parse_line(
            "HIT|200|1785887999998|5432|4339610|186.225.0.1|-|"
            "https://www.scielo.br/j/neco/a/test/|LA|"
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36|"
            "8dbbeef65a64c5235f863868a7c94d70|US"
        )
        counter_access = extraction.extract(
            "scl",
            {
                "scielo_issn": "1234-5678",
                "pid_v3": "S1234-56782024000100001",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "media_language": "en",
            },
        )
        results = {}

        accumulation.accumulate(results, counter_access, line)
        metrics = index_docs.convert(results)

        self.assertEqual(line["country_code"], "US")
        self.assertEqual(line["local_datetime"], "2026-08-04 23:59:59")
        year_document = next(iter(metrics["year"].values()))
        self.assertEqual(year_document["access"]["country_code"], "US")
        month_document = next(iter(metrics["month"].values()))
        self.assertNotIn("country_code", month_document["access"])
