import json
import os
import shutil
import tempfile
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from collection.models import Collection
from metrics.models import DailyMetricJob
from metrics.services import daily_payloads


class CleanupExportedPayloadsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._patched_root = patch.object(
            daily_payloads,
            "get_daily_payload_root",
            return_value=Path(cls._tmpdir.name),
        )
        cls._patched_root.start()

    @classmethod
    def tearDownClass(cls):
        cls._patched_root.stop()
        cls._tmpdir.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")
        self.other_collection = Collection.objects.create(acron3="scl", acron2="sc")

        self.payload_root = daily_payloads.get_daily_payload_root()
        self._clean_temp_dir()

    def _clean_temp_dir(self):
        root = self.payload_root
        if root.exists():
            for item in root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    def _create_job(self, collection, access_date, status, storage_path, payload_hash):
        return DailyMetricJob.objects.create(
            collection=collection,
            access_date=access_date,
            status=status,
            storage_path=storage_path,
            payload_hash=payload_hash,
        )

    def _write_payload_file(self, storage_path):
        resolved = daily_payloads.resolve_storage_path(storage_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps({"test": True}), encoding="utf-8")
        return resolved

    def _set_file_age(self, file_path, days_old):
        old_time = time.time() - days_old * 86400
        os.utime(file_path, (old_time, old_time))

    def test_cleanup_deletes_old_exported_payloads(self):
        path = daily_payloads.build_daily_storage_path(
            self.collection, date(2012, 3, 10)
        )
        resolved = self._write_payload_file(path)
        self._set_file_age(resolved, 30)

        self._create_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTED,
            storage_path=path.as_posix(),
            payload_hash="abc",
        )

        result = daily_payloads.cleanup_exported_payloads(older_than_days=7)

        self.assertEqual(result, 1)
        self.assertFalse(resolved.exists())

    def test_cleanup_skips_recent_files(self):
        path = daily_payloads.build_daily_storage_path(
            self.collection, date(2012, 3, 10)
        )
        resolved = self._write_payload_file(path)

        self._create_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTED,
            storage_path=path.as_posix(),
            payload_hash="abc",
        )

        result = daily_payloads.cleanup_exported_payloads(older_than_days=7)

        self.assertEqual(result, 0)
        self.assertTrue(resolved.exists())

    def test_cleanup_skips_non_exported_jobs(self):
        statuses = [
            DailyMetricJob.STATUS_PENDING,
            DailyMetricJob.STATUS_ERROR,
            DailyMetricJob.STATUS_EXPORTING,
        ]
        paths = []
        for i, status in enumerate(statuses):
            access_date = date(2012, 3, 10 + i)
            path = daily_payloads.build_daily_storage_path(self.collection, access_date)
            resolved = self._write_payload_file(path)
            self._set_file_age(resolved, 30)
            paths.append(resolved)

            self._create_job(
                collection=self.collection,
                access_date=access_date,
                status=status,
                storage_path=path.as_posix(),
                payload_hash="abc",
            )

        result = daily_payloads.cleanup_exported_payloads(older_than_days=7)

        self.assertEqual(result, 0)
        for p in paths:
            self.assertTrue(p.exists())

    def test_cleanup_filters_by_collection(self):
        path_books = daily_payloads.build_daily_storage_path(
            self.collection, date(2012, 3, 10)
        )
        path_scl = daily_payloads.build_daily_storage_path(
            self.other_collection, date(2012, 3, 10)
        )
        resolved_books = self._write_payload_file(path_books)
        resolved_scl = self._write_payload_file(path_scl)
        self._set_file_age(resolved_books, 30)
        self._set_file_age(resolved_scl, 30)

        self._create_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTED,
            storage_path=path_books.as_posix(),
            payload_hash="abc",
        )
        self._create_job(
            collection=self.other_collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTED,
            storage_path=path_scl.as_posix(),
            payload_hash="def",
        )

        result = daily_payloads.cleanup_exported_payloads(
            collections=["books"],
            older_than_days=7,
        )

        self.assertEqual(result, 1)
        self.assertFalse(resolved_books.exists())
        self.assertTrue(resolved_scl.exists())

    def test_cleanup_deletes_orphan_files(self):
        path = daily_payloads.build_daily_storage_path(
            self.collection, date(2012, 3, 10)
        )
        resolved = self._write_payload_file(path)
        self._set_file_age(resolved, 30)

        result = daily_payloads.cleanup_exported_payloads(older_than_days=7)

        self.assertEqual(result, 1)
        self.assertFalse(resolved.exists())

    def test_cleanup_skips_orphan_file_with_old_db_job_not_exported(self):
        path = daily_payloads.build_daily_storage_path(
            self.collection, date(2012, 3, 10)
        )
        resolved = self._write_payload_file(path)
        self._set_file_age(resolved, 30)

        self._create_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_PENDING,
            storage_path=path.as_posix(),
            payload_hash="abc",
        )

        result = daily_payloads.cleanup_exported_payloads(older_than_days=7)

        self.assertEqual(result, 0)
        self.assertTrue(resolved.exists())

    def test_cleanup_clears_db_fields_for_exported_jobs(self):
        path = daily_payloads.build_daily_storage_path(
            self.collection, date(2012, 3, 10)
        )
        resolved = self._write_payload_file(path)
        self._set_file_age(resolved, 30)

        job = self._create_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTED,
            storage_path=path.as_posix(),
            payload_hash="abc",
        )

        daily_payloads.cleanup_exported_payloads(older_than_days=7)

        job.refresh_from_db()
        self.assertEqual(job.storage_path, "")
        self.assertEqual(job.payload_hash, "")

    def test_cleanup_with_no_matching_files(self):
        result = daily_payloads.cleanup_exported_payloads(older_than_days=7)
        self.assertEqual(result, 0)

    def test_cleanup_without_older_than_days_deletes_all(self):
        path = daily_payloads.build_daily_storage_path(
            self.collection, date(2012, 3, 10)
        )
        resolved = self._write_payload_file(path)

        self._create_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTED,
            storage_path=path.as_posix(),
            payload_hash="abc",
        )

        result = daily_payloads.cleanup_exported_payloads(older_than_days=0)

        self.assertEqual(result, 1)
        self.assertFalse(resolved.exists())


class CleanupTaskTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")

    def test_task_cleanup_daily_payloads_calls_service(self):
        with patch(
            "metrics.services.daily_payloads.cleanup_exported_payloads"
        ) as mock_cleanup:
            mock_cleanup.return_value = 5
            from metrics.tasks.cleanup import task_cleanup_daily_payloads

            result = task_cleanup_daily_payloads.run(
                collections=["books"],
                older_than_days=7,
            )

        mock_cleanup.assert_called_once_with(
            collections=["books"],
            older_than_days=7,
        )
        self.assertEqual(result, {"deleted_payloads": 5})

    def test_task_cleanup_with_defaults(self):
        with patch(
            "metrics.services.daily_payloads.cleanup_exported_payloads"
        ) as mock_cleanup:
            mock_cleanup.return_value = 0
            from metrics.tasks.cleanup import task_cleanup_daily_payloads

            result = task_cleanup_daily_payloads.run()

        mock_cleanup.assert_called_once_with(
            collections=[],
            older_than_days=7,
        )
        self.assertEqual(result, {"deleted_payloads": 0})
