import tempfile
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from collection.models import Collection
from log_manager import choices
from log_manager.models import LogFile
from metrics.counter.access.daily_accumulator import DailyAccessAccumulator
from metrics.models import DailyMetricJob
from metrics.services.jobs import (
    create_or_update_daily_metric_job,
    mark_daily_metric_job_exported,
    release_stale_daily_metric_jobs,
)
from metrics.services.parsing.job_payloads import (
    _write_job_payload,
    build_daily_metric_job_payload,
)


class DailyMetricJobServiceTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")

    def _log_file(self, hash_value, status=choices.LOG_FILE_STATUS_QUEUED):
        return LogFile.objects.create(
            hash=hash_value,
            path=f"/tmp/{hash_value}.log.gz",
            stat_result={},
            status=status,
            collection=self.collection,
            date=date(2012, 3, 10),
            validation={"probably_date": "2012-03-10"},
        )

    def test_create_or_update_blocks_implicit_recompute_after_export(self):
        first = self._log_file("1" * 32)
        second = self._log_file("2" * 32)
        DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTED,
            input_log_hashes=[first.hash],
            storage_path="books/2012/03/2012-03-10.json",
            payload_hash="abc",
        )

        with self.assertRaises(RuntimeError):
            create_or_update_daily_metric_job(
                collection=self.collection,
                access_date=date(2012, 3, 10),
                log_files=[first, second],
            )

    def test_create_or_update_keeps_payload_for_export_retry(self):
        log_file = self._log_file("1" * 32, status=choices.LOG_FILE_STATUS_ERROR)
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_ERROR,
            input_log_hashes=[log_file.hash],
            storage_path="books/2012/03/2012-03-10.json",
            payload_hash="abc",
            summary={"month_document_count": 1},
        )

        create_or_update_daily_metric_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            log_files=[log_file],
        )

        job.refresh_from_db()
        self.assertEqual(job.status, DailyMetricJob.STATUS_PENDING)
        self.assertEqual(job.storage_path, "books/2012/03/2012-03-10.json")
        self.assertEqual(job.payload_hash, "abc")
        self.assertEqual(job.summary, {"month_document_count": 1})

    def test_create_or_update_clears_stale_payload_when_inputs_change_before_success(
        self,
    ):
        first = self._log_file("1" * 32)
        second = self._log_file("2" * 32)
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_ERROR,
            input_log_hashes=[first.hash],
            storage_path="books/2012/03/2012-03-10.json",
            payload_hash="abc",
            summary={"month_document_count": 1},
        )

        create_or_update_daily_metric_job(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            log_files=[first, second],
        )

        job.refresh_from_db()
        self.assertEqual(job.input_log_hashes, sorted([first.hash, second.hash]))
        self.assertEqual(job.storage_path, "")
        self.assertEqual(job.payload_hash, "")
        self.assertEqual(job.summary, {})

    def test_release_stale_daily_metric_jobs_marks_logs_for_retry(self):
        log_file = self._log_file("1" * 32, status=choices.LOG_FILE_STATUS_PARSING)
        DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
            input_log_hashes=[log_file.hash],
            export_started_at=timezone.now() - timedelta(minutes=120),
        )

        released = release_stale_daily_metric_jobs(stale_after_minutes=60)

        log_file.refresh_from_db()
        self.assertEqual(released, 1)
        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_ERROR)
        self.assertIsNone(log_file.parse_heartbeat_at)

    def test_mark_daily_metric_job_exported_sets_status_and_timestamp(self):
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
        )

        mark_daily_metric_job_exported(job)

        job.refresh_from_db()
        self.assertEqual(job.status, DailyMetricJob.STATUS_EXPORTED)
        self.assertIsNotNone(job.exported_at)

    @patch(
        "metrics.services.parsing.job_payloads.process_line", return_value=(True, None)
    )
    @patch("metrics.services.parsing.job_payloads.setup_parsing_environment")
    def test_build_daily_metric_job_payload_uses_only_input_log_hashes(
        self,
        mock_setup_parsing_environment,
        mock_process_line,
    ):
        selected = self._log_file("1" * 32)
        extra = self._log_file("2" * 32)
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
            input_log_hashes=[selected.hash],
        )

        parser = Mock()
        parser.stats = SimpleNamespace(lines_parsed=1)
        parser.parse.return_value = [{"url": "/selected"}]
        mock_setup_parsing_environment.return_value = (parser, Mock())

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                storage_path, payload_hash = build_daily_metric_job_payload(
                    job, robots_list=["robot"], mmdb=Mock(data={})
                )

        selected.refresh_from_db()
        extra.refresh_from_db()
        job.refresh_from_db()

        self.assertEqual(storage_path, "books/2012/03/2012-03-10.json")
        self.assertTrue(payload_hash)
        self.assertEqual(job.input_log_hashes, [selected.hash])
        self.assertEqual(selected.status, choices.LOG_FILE_STATUS_PARSING)
        self.assertEqual(extra.status, choices.LOG_FILE_STATUS_QUEUED)
        mock_setup_parsing_environment.assert_called_once()
        self.assertEqual(
            mock_setup_parsing_environment.call_args.kwargs["log_file"].hash,
            selected.hash,
        )

    def test_build_daily_metric_job_payload_rejects_empty_input_hashes(self):
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
            input_log_hashes=[],
        )

        with self.assertRaisesMessage(RuntimeError, "has no input log hashes"):
            build_daily_metric_job_payload(
                job, robots_list=["robot"], mmdb=Mock(data={})
            )

    def test_build_daily_metric_job_payload_rejects_missing_input_hashes(self):
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
            input_log_hashes=["9" * 32],
        )

        with self.assertRaisesMessage(RuntimeError, "is missing log files"):
            build_daily_metric_job_payload(
                job, robots_list=["robot"], mmdb=Mock(data={})
            )

    def test_payload_generation_releases_accumulator(self):
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
            input_log_hashes=["1" * 32],
        )
        accumulator = DailyAccessAccumulator()
        accumulator.accumulate_access(
            data={"collection": "books"},
            session_key=("browser", "1", "127.0.0.1", 734572, 10),
            url="/book",
            second=5,
        )
        summary = {
            "log_files": 1,
            "input_log_hashes": ["1" * 32],
            "lines_parsed": 1,
            "valid_lines": 1,
            "discarded_lines": 0,
        }

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                _write_job_payload(job, accumulator, summary)

        self.assertEqual(len(accumulator), 0)
        self.assertEqual(accumulator._documents, [])
