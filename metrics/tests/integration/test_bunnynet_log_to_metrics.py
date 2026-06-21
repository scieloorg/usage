import unittest
from pathlib import Path

from scielo_usage_counter import log_handler

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
