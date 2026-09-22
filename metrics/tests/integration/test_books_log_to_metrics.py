import unittest
from datetime import datetime
from pathlib import Path

from scielo_usage_counter import log_handler
from scielo_usage_counter.translator.books import URLTranslatorBooksSite
from scielo_usage_counter.url_translator import URLTranslationManager

from metrics.counter.access import accumulation, extraction, validation
from metrics.counter.access.daily_accumulator import DailyAccessAccumulator
from metrics.tests.helpers import convert_accumulator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestBooksLogToMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.robots_list = (FIXTURES_DIR / "counter-robots.txt").read_text().splitlines()
        cls.mmdb_data = (FIXTURES_DIR / "map.mmdb").read_bytes()
        cls.log_path = str(FIXTURES_DIR / "usage.books.log")
        cls.utm = URLTranslationManager(
            documents_metadata=iter([]),
            sources_metadata=iter([]),
            translator=URLTranslatorBooksSite,
        )

    def _parse_log(self):
        parser = log_handler.LogParser(
            mmdb_data=self.mmdb_data,
            robots_list=self.robots_list,
            output_mode="dict",
        )
        parser.logfile = self.log_path
        return list(parser.parse())

    def _extract_all(self, lines):
        extracted = []
        for line in lines:
            url = line.get("url")
            if not url:
                continue
            translated = self.utm.translate(url)
            if translated and isinstance(translated, dict):
                counter_access = extraction.extract("books", translated)
                extracted.append((counter_access, line))
        return extracted

    def test_parser_yields_lines_from_mixed_formats(self):
        lines = self._parse_log()
        self.assertGreater(len(lines), 0)

    def test_translation_extracts_book_ids(self):
        lines = self._parse_log()
        extracted = self._extract_all(lines)
        self.assertGreater(len(extracted), 0)

        source_ids = {ca.get("source_id") for ca, _ in extracted}
        self.assertGreater(len(source_ids), 0)
        for ca, _ in extracted:
            self.assertEqual(ca["source_type"], "book")
            self.assertIsNotNone(ca.get("pid_generic"))

    def test_extraction_produces_book_and_chapter_types(self):
        lines = self._parse_log()
        extracted = self._extract_all(lines)
        doc_types = {ca.get("document_type") for ca, _ in extracted}
        self.assertTrue(doc_types & {"book", "chapter"})

    def test_resolves_country_codes_via_geoip(self):
        lines = self._parse_log()
        countries = {line.get("country_code") for line in lines}
        countries.discard(None)
        self.assertGreater(len(countries), 0)

    def test_ipv6_address_is_parsed(self):
        lines = self._parse_log()
        has_ipv6 = any("::" in (line.get("ip_address") or "") for line in lines)
        self.assertTrue(has_ipv6)

    def test_pdf_and_epub_formats_detected(self):
        lines = self._parse_log()
        extracted = self._extract_all(lines)
        formats = {ca.get("media_format") for ca, _ in extracted}
        self.assertTrue(len(formats) > 0)

    def test_full_pipeline_with_synthetic_metadata(self):
        results = DailyAccessAccumulator()
        counter_access = extraction.extract(
            "books",
            {
                "source_type": "book",
                "source_id": "xjcw9",
                "document_type": "book",
                "book_id": "xjcw9",
                "book_title": "Test Book",
                "pid_generic": "book:xjcw9",
                "title_pid_generic": "book:xjcw9",
                "media_language": "pt",
                "media_format": "html",
                "content_type": "full_text",
            },
        )

        valid, _ = validation.is_valid(counter_access)
        self.assertTrue(valid)

        accumulation.accumulate(
            results,
            counter_access,
            {
                "client_name": "browser",
                "client_version": "1.0",
                "ip_address": "186.215.90.179",
                "country_code": "BR",
                "local_datetime": datetime(2012, 4, 1, 0, 0, 29),
            },
        )

        metrics = convert_accumulator(results)
        self.assertGreater(len(metrics["counter"]), 0)
        self.assertGreater(len(metrics["analytics"]), 0)

        has_item = False
        has_title = False
        for doc in metrics["counter"].values():
            scope = doc["metric_scope"]
            if scope == "item":
                has_item = True
                self.assertEqual(doc["data_type"], "Book_Segment")
            elif scope == "title":
                has_title = True
                self.assertEqual(doc["data_type"], "Book")

        self.assertTrue(has_item)
        self.assertTrue(has_title)

    def test_whole_book_pdf_counts_chapters_from_metadata(self):
        book_id = "xjcw9"
        manager = URLTranslationManager(
            documents_metadata=iter(
                [
                    {
                        "document_id": f"book:{book_id}/chapter:{chapter_id}",
                        "document_type": "chapter",
                        "pid_generic": f"book:{book_id}/chapter:{chapter_id}",
                        "source_id": book_id,
                        "source_type": "book",
                        "title": f"Chapter {chapter_id}",
                    }
                    for chapter_id in ("01", "02")
                ]
            ),
            sources_metadata=iter(
                [{"source_id": book_id, "source_type": "book", "title": "Test Book"}]
            ),
            translator=URLTranslatorBooksSite,
        )
        translated = manager.translate(f"/id/{book_id}/pdf/test-book.pdf")
        counter_access = extraction.extract("books", translated)

        self.assertEqual(len(counter_access["segment_pid_generics"]), 2)

        results = DailyAccessAccumulator()
        accumulation.accumulate(
            results,
            counter_access,
            {
                "client_name": "browser",
                "client_version": "1.0",
                "ip_address": "186.215.90.179",
                "country_code": "BR",
                "local_datetime": datetime(2025, 8, 1, 10, 0, 29),
            },
        )

        metrics = convert_accumulator(results)
        for dataset in ("counter", "analytics"):
            documents = metrics[dataset].values()
            items = [item for item in documents if item["metric_scope"] == "item"]
            titles = [item for item in documents if item["metric_scope"] == "title"]

            self.assertEqual(len(items), 2)
            self.assertEqual(len(titles), 1)
            self.assertEqual(sum(item["unique_requests"] for item in items), 2)
            self.assertEqual(titles[0]["unique_requests"], 1)

    def test_all_metric_fields_present_in_converted_document(self):
        results = DailyAccessAccumulator()
        counter_access = extraction.extract(
            "books",
            {
                "source_type": "book",
                "source_id": "h8pyf",
                "document_type": "chapter",
                "book_id": "h8pyf",
                "chapter_id": "08",
                "pid_generic": "book:h8pyf/chapter:08",
                "title_pid_generic": "book:h8pyf",
                "media_language": "pt",
                "media_format": "html",
                "content_type": "full_text",
                "book_title": "Book H8PYF",
                "chapter_title": "Chapter 08",
            },
        )
        accumulation.accumulate(
            results,
            counter_access,
            {
                "client_name": "MSIE",
                "client_version": "9.0",
                "ip_address": "189.97.101.205",
                "country_code": "BR",
                "local_datetime": datetime(2012, 4, 1, 0, 30, 27),
            },
        )

        metrics = convert_accumulator(results)
        for doc in metrics["counter"].values():
            self.assertIn("total_requests", doc)
            self.assertIn("total_investigations", doc)
            self.assertIn("unique_requests", doc)
            self.assertIn("unique_investigations", doc)
            self.assertIn("collection", doc)
            self.assertIn("source_key", doc)
            self.assertIn("document_key", doc)
            self.assertIn("data_type", doc)
            self.assertIn("month", doc)
            self.assertIn("daily_metrics", doc)

        for doc in metrics["analytics"].values():
            self.assertEqual(doc["year"], "2012")
            self.assertNotIn("daily_metrics", doc)
