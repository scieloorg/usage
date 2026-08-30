import unittest
from datetime import datetime

from scielo_usage_counter.values import (
    CONTENT_TYPE_FULL_TEXT,
    DEFAULT_SCIELO_ISSN,
    MEDIA_FORMAT_HTML,
    MEDIA_FORMAT_PDF,
)

from metrics.counter.access import accumulation


class TestAccumulation(unittest.TestCase):
    def _book_counter_access(self, **overrides):
        base = {
            "collection": "books",
            "source_type": "book",
            "source_id": "q7gtd",
            "scielo_issn": DEFAULT_SCIELO_ISSN,
            "pid_v2": None,
            "pid_v3": None,
            "pid_generic": "BOOK:Q7GTD",
            "title_pid_generic": "BOOK:Q7GTD",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_FULL_TEXT,
            "publication_year": "2023",
            "document_title": "Book Title",
            "source_main_title": "Book Title",
            "source_subject_area_capes": [],
            "source_subject_area_wos": [],
            "source_acronym": None,
            "source_publisher_name": ["SciELO Books"],
        }
        base.update(overrides)
        return base

    def _line(self, **overrides):
        base = {
            "client_name": "browser",
            "client_version": "1.0",
            "ip_address": "127.0.0.1",
            "country_code": "BR",
            "local_datetime": datetime(2024, 1, 15, 10, 0, 5),
        }
        base.update(overrides)
        return base

    def test_stores_source_and_periods(self):
        results = {}
        accumulation.accumulate(results, self._book_counter_access(), self._line())

        self.assertEqual(len(results), 1)
        result = next(iter(results.values()))
        self.assertEqual(result["source"]["source_type"], "book")
        self.assertEqual(result["source"]["source_id"], "q7gtd")
        self.assertEqual(result["source"]["main_title"], "Book Title")
        self.assertEqual(result["access_date"], "2024-01-15")
        self.assertEqual(result["access_month"], "202401")
        self.assertEqual(result["access_year"], "2024")
        self.assertEqual(result["access_country_code"], "BR")
        self.assertEqual(result["content_language"], "en")
        self.assertEqual(result["title_pid_generic"], "BOOK:Q7GTD")
        self.assertEqual(result["document"], {"title": "Book Title"})
        self.assertIn("user_session_id", result)

    def test_rejects_invalid_local_datetime(self):
        results = {}
        with self.assertRaises(ValueError):
            accumulation.accumulate(
                results,
                self._book_counter_access(),
                self._line(local_datetime=None),
            )
        self.assertEqual(results, {})

    def test_does_not_expand_book_into_segments(self):
        results = {}
        counter_access = self._book_counter_access(
            source_id="c2248",
            pid_generic="BOOK:C2248",
            title_pid_generic="BOOK:C2248",
            segment_pid_generics=[
                "BOOK:C2248/CHAPTER:00",
                "BOOK:C2248/CHAPTER:01",
                "BOOK:C2248/CHAPTER:02",
            ],
            media_format=MEDIA_FORMAT_PDF,
            media_language="pt",
            publication_year="2018",
            source_main_title="C2248 Book",
        )
        accumulation.accumulate(results, counter_access, self._line())
        self.assertEqual(len(results), 1)
        result = list(results.values())[0]
        self.assertEqual(result["pid_generic"], "BOOK:C2248")

    def test_double_click_filter_uses_url_bucket_for_same_item(self):
        results = {}
        counter_access = self._book_counter_access(
            source_id="c2248",
            pid_generic="BOOK:C2248/CHAPTER:03",
            title_pid_generic="BOOK:C2248",
            media_language="pt",
            publication_year="2018",
            source_main_title="C2248 Book",
        )

        accumulation.accumulate(
            results,
            counter_access,
            self._line(
                local_datetime=datetime(2024, 1, 15, 10, 0, 5),
                url="/id/c2248/03",
            ),
        )
        accumulation.accumulate(
            results,
            counter_access,
            self._line(
                local_datetime=datetime(2024, 1, 15, 10, 0, 20),
                url="https://books.scielo.org/id/c2248/epub/03.html?x=1",
            ),
        )

        raw = next(iter(results.values()))
        self.assertEqual(
            set(raw["click_timestamps_by_url"]),
            {"/id/c2248/03", "/id/c2248/epub/03.html"},
        )

    def test_same_url_within_window_produces_single_url_bucket(self):
        results = {}
        counter_access = self._book_counter_access(
            source_id="c2248",
            pid_generic="BOOK:C2248/CHAPTER:03",
            title_pid_generic="BOOK:C2248",
            media_language="pt",
            publication_year="2018",
            source_main_title="C2248 Book",
        )

        accumulation.accumulate(
            results,
            counter_access,
            self._line(
                local_datetime=datetime(2024, 1, 15, 10, 0, 5),
                url="/id/c2248/03?from=search",
            ),
        )
        accumulation.accumulate(
            results,
            counter_access,
            self._line(
                local_datetime=datetime(2024, 1, 15, 10, 0, 20),
                url="/id/c2248/03?from=search",
            ),
        )

        raw = next(iter(results.values()))
        self.assertEqual(
            raw["click_timestamps_by_url"],
            {"/id/c2248/03": {5: 1, 20: 1}},
        )

    def test_parses_datetime_string_and_stores_integer_seconds(self):
        results = {}

        accumulation.accumulate(
            results,
            self._book_counter_access(),
            self._line(local_datetime="2024-01-15 10:01:05"),
        )

        raw = next(iter(results.values()))
        self.assertEqual(raw["click_timestamps"], {65: 1})

    def test_generates_session_id_from_client_ip_datetime(self):
        results = {}
        accumulation.accumulate(results, self._book_counter_access(), self._line())
        result = next(iter(results.values()))
        self.assertEqual(
            result["user_session_id"], "browser|1.0|127.0.0.1|2024-01-15|10"
        )

    def test_ipv6_address_is_accepted(self):
        results = {}
        accumulation.accumulate(
            results,
            self._book_counter_access(),
            self._line(ip_address="2001:4860:7:1103::"),
        )
        result = next(iter(results.values()))
        self.assertIn("2001:4860:7:1103::", result["user_session_id"])
