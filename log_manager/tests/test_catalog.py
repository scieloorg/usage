import gzip
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from collection.models import Collection
from log_manager import choices, file_errors, utils
from log_manager.models import LogFile
from log_manager.services import catalog


class CatalogLogFilesTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="per", acron2="pe")

    def _catalog_directory(self, directory, visible_dates=None):
        catalog._catalog_log_files_in_directory(
            collection=self.collection,
            directory_path=directory,
            visible_dates=visible_dates
            if visible_dates is not None
            else [date.today()],
            supported_extensions=[".gz"],
        )

    def test_corrupted_gzip_is_recorded_once_as_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-09-04_scielo.pe.log.gz"
            path.write_bytes(b"\x1f\x8bcorrupted")

            self._catalog_directory(directory)
            self._catalog_directory(directory)

            log_file = LogFile.objects.get()
            expected_hash = file_errors.build_catalog_error_hash("per", str(path))

        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_ERROR)
        self.assertIsNone(log_file.date)
        self.assertEqual(log_file.hash, expected_hash)
        self.assertEqual(
            log_file.validation["file_error"]["code"],
            file_errors.FILE_READ_ERROR_CODE,
        )
        self.assertEqual(log_file.validation["file_error"]["stage"], "catalog")

    def test_file_metadata_io_error_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-09-04_scielo.pe.log.gz"
            path.touch()

            with patch.object(
                catalog.os, "stat", side_effect=PermissionError("denied")
            ):
                self._catalog_directory(directory)

            log_file = LogFile.objects.get()

        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_ERROR)
        self.assertEqual(log_file.stat_result, {})
        self.assertEqual(log_file.validation["file_error"]["kind"], "io")

    def test_valid_replacement_recovers_the_error_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-09-04_scielo.pe.log.gz"
            path.write_bytes(b"\x1f\x8bcorrupted")
            self._catalog_directory(directory)
            log_file_id = LogFile.objects.get().pk

            with gzip.open(path, "wt") as output:
                output.write(
                    "127.0.0.1 - - [04/Sep/2026:10:00:00 +0000] "
                    '"GET / HTTP/1.1" 200 1\n'
                )
            expected_hash = utils.hash_file(path)
            self._catalog_directory(directory)

            log_file = LogFile.objects.get()

        self.assertEqual(log_file.pk, log_file_id)
        self.assertEqual(log_file.hash, expected_hash)
        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_CREATED)
        self.assertEqual(log_file.validation, {})

    def test_read_error_is_retried_outside_the_visible_date_range(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-09-04_scielo.pe.log.gz"
            path.write_bytes(b"\x1f\x8bcorrupted")
            self._catalog_directory(directory)
            log_file_id = LogFile.objects.get().pk

            with gzip.open(path, "wb") as output:
                output.write(b"repaired content\n")
            self._catalog_directory(directory, visible_dates=[])

            log_file = LogFile.objects.get()

        self.assertEqual(log_file.pk, log_file_id)
        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_CREATED)

    def test_valid_duplicate_removes_the_error_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            valid_path = Path(directory) / "2026-09-03_scielo.pe.log.gz"
            repaired_path = Path(directory) / "2026-09-04_scielo.pe.log.gz"
            content = b"same content\n"
            with gzip.open(valid_path, "wb") as output:
                output.write(content)
            repaired_path.write_bytes(b"\x1f\x8bcorrupted")
            self._catalog_directory(directory)

            with gzip.open(repaired_path, "wb") as output:
                output.write(content)
            self._catalog_directory(directory)

            expected_hash = utils.hash_file(valid_path)

        self.assertEqual(LogFile.objects.count(), 1)
        self.assertEqual(LogFile.objects.get().hash, expected_hash)
