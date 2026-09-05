import gzip
import tempfile
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from collection.models import Collection
from log_manager import choices, utils
from log_manager.models import LogFile
from log_manager.services import validation


class ValidationServiceTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="scl", acron2="sc")

    def test_validation_settings_defaults_match_validator_arguments(self):
        buffer_size, sample_size = validation._get_collection_validation_settings(
            self.collection.acron3
        )

        self.assertEqual(buffer_size, 2048)
        self.assertEqual(sample_size, 0.1)

    @patch("log_manager.utils.validator.pipeline_validate")
    @patch("log_manager.utils.validator.get_total_lines", return_value=10)
    def test_validate_file_clamps_sample_size_to_avoid_zero_range_step(
        self, mock_get_total_lines, mock_pipeline_validate
    ):
        utils.validate_file("/tmp/access.log", sample_size=2048, buffer_size=2048)

        mock_get_total_lines.assert_called_once_with(
            path="/tmp/access.log",
            buffer_size=2048,
        )
        self.assertEqual(mock_pipeline_validate.call_args.kwargs["sample_size"], 1.0)

    @patch("log_manager.utils.validator.validate_path_name", return_value={"all": True})
    def test_validate_file_returns_invalid_result_for_empty_log(
        self, mock_validate_path_name
    ):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as tmp_file:
            path = tmp_file.name

            result = utils.validate_file(path, sample_size=1.0, buffer_size=2048)

        self.assertFalse(result["is_valid"]["all"])
        self.assertEqual(
            result["content"]["summary"]["total_lines"]["error"],
            "File is empty",
        )
        self.assertIsNone(result["probably_date"])

    def test_validate_file_returns_structured_error_for_corrupted_gzip(self):
        with tempfile.NamedTemporaryFile(suffix=".log.gz") as tmp_file:
            compressed = bytearray(gzip.compress(b"valid line\n"))
            compressed[-1] ^= 0xFF
            tmp_file.write(compressed)
            tmp_file.flush()

            result = utils.validate_file(
                tmp_file.name,
                sample_size=1.0,
                buffer_size=2048,
            )

        self.assertEqual(result["content"]["error"]["code"], "file_read_error")
        self.assertEqual(result["content"]["error"]["kind"], "corrupted")

    @patch("log_manager.services.validation.utils.validate_file")
    def test_validate_log_file_updates_status_and_normalizes_result(
        self, mock_validate_file
    ):
        log_file = LogFile.objects.create(
            collection=self.collection,
            path="/tmp/access.log",
            stat_result={"size": 10},
            hash="2" * 32,
            status=choices.LOG_FILE_STATUS_CREATED,
        )
        mock_validate_file.return_value = {
            "probably_date": date(2026, 5, 10),
            "is_valid": {"all": True},
            "content": {
                "summary": {
                    "datetimes": ["2026-05-10T00:00:00"],
                },
            },
        }

        validation.validate_log_file_and_update_status(log_file.hash)

        log_file.refresh_from_db()
        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_QUEUED)
        self.assertEqual(log_file.date, date(2026, 5, 10))
        self.assertNotIn("datetimes", log_file.validation["content"]["summary"])
        self.assertEqual(log_file.validation["probably_date"], "2026-05-10")

    @patch("log_manager.services.validation.utils.validate_file")
    def test_validate_log_file_marks_read_failure_as_error(self, mock_validate_file):
        log_file = LogFile.objects.create(
            collection=self.collection,
            path="/tmp/2026-05-10_access.log.gz",
            stat_result={"size": 10},
            hash="3" * 32,
            status=choices.LOG_FILE_STATUS_QUEUED,
            date=date(2026, 5, 10),
        )
        mock_validate_file.return_value = {
            "probably_date": None,
            "is_valid": {"all": False},
            "content": {
                "summary": {"total_lines": {"error": "File is corrupted"}},
                "error": {
                    "code": "file_read_error",
                    "kind": "corrupted",
                    "message": "File is corrupted",
                },
            },
        }

        validation.validate_log_file_and_update_status(log_file.hash)

        log_file.refresh_from_db()
        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_ERROR)
        self.assertIsNone(log_file.date)
        self.assertEqual(log_file.validation["file_error"]["stage"], "validation")

    @patch("log_manager.services.validation.utils.validate_file")
    def test_validate_log_file_keeps_readable_invalid_file_invalidated(
        self, mock_validate_file
    ):
        log_file = LogFile.objects.create(
            collection=self.collection,
            path="/tmp/2026-05-10-error_access.log.gz",
            stat_result={"size": 10},
            hash="4" * 32,
            status=choices.LOG_FILE_STATUS_CREATED,
        )
        mock_validate_file.return_value = {
            "probably_date": date(2026, 5, 10),
            "is_valid": {"all": False},
            "content": {"summary": {"total_lines": 10}},
        }

        validation.validate_log_file_and_update_status(log_file.hash)

        log_file.refresh_from_db()
        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_INVALIDATED)
