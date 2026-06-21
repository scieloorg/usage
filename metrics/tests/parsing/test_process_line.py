from datetime import date
from unittest.mock import Mock

from django.test import TestCase
from scielo_usage_counter.values import CONTENT_TYPE_FULL_TEXT, MEDIA_FORMAT_HTML

from collection.models import Collection
from log_manager import choices
from log_manager.models import LogFile
from metrics.services.parsing.lines import process_line


class ProcessLineTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")
        self.log_file = LogFile.objects.create(
            hash="1" * 32,
            path="/tmp/111.log.gz",
            stat_result={},
            status=choices.LOG_FILE_STATUS_QUEUED,
            collection=self.collection,
            date=date(2012, 3, 10),
            validation={"probably_date": "2012-03-10"},
        )

    def _fake_utm(self, translate_return=None, translate_error=None):
        utm = Mock()
        if translate_error:
            utm.translate.side_effect = translate_error
        else:
            utm.translate.return_value = translate_return or {
                "source_type": "book",
                "source_id": "q7gtd",
                "book_id": "q7gtd",
                "pid_generic": "book:q7gtd",
                "media_language": "en",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
            }
        return utm

    def _line(self, **overrides):
        base = {
            "url": "/id/q7gtd",
            "client_name": "browser",
            "client_version": "1.0",
            "ip_address": "127.0.0.1",
            "country_code": "BR",
            "local_datetime": None,
        }
        base.update(overrides)
        return base

    def test_discards_invalid_local_datetime_without_raising(self):
        results = {}
        is_valid, error = process_line(
            results=results,
            line=self._line(),
            utm=self._fake_utm(),
            log_file=self.log_file,
        )
        self.assertFalse(is_valid)
        self.assertIsNone(error)
        self.assertEqual(results, {})

    def test_url_translation_error_returns_false_none(self):
        results = {}
        is_valid, error = process_line(
            results=results,
            line=self._line(),
            utm=self._fake_utm(translate_error=ValueError("bad URL")),
            log_file=self.log_file,
        )
        self.assertFalse(is_valid)
        self.assertIsNone(error)

    def test_valid_line_accumulates_result(self):
        from datetime import datetime

        results = {}
        is_valid, error = process_line(
            results=results,
            line=self._line(local_datetime=datetime(2024, 1, 15, 10, 0, 5)),
            utm=self._fake_utm(),
            log_file=self.log_file,
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(len(results), 1)

    def test_validation_failure_without_track_errors_returns_no_discarded_line(self):
        results = {}
        utm = self._fake_utm(
            translate_return={
                "pid_generic": "",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
            }
        )
        is_valid, error = process_line(
            results=results,
            line=self._line(),
            utm=utm,
            log_file=self.log_file,
            track_errors=False,
        )
        self.assertFalse(is_valid)
        self.assertIsNone(error)

    def test_extraction_error_returns_false_none(self):
        results = {}
        utm = self._fake_utm(translate_return="not-a-dict")
        is_valid, error = process_line(
            results=results,
            line=self._line(),
            utm=utm,
            log_file=self.log_file,
        )
        self.assertFalse(is_valid)
        self.assertIsNone(error)
