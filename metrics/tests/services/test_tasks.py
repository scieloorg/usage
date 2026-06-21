from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from collection.models import Collection
from log_manager import choices
from log_manager.models import LogFile
from metrics.models import DailyMetricJob
from metrics.tasks.log_parsing import (
    task_enqueue_log_parsing_jobs,
    task_wait_log_parsing_wave,
)
from metrics.tasks.resume import task_resume_log_exports


class ParseLogsTaskTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")

    def _log_file(
        self, hash_value, probably_date, status=choices.LOG_FILE_STATUS_QUEUED
    ):
        return LogFile.objects.create(
            hash=hash_value,
            path=f"/tmp/{hash_value}.log.gz",
            stat_result={},
            status=status,
            collection=self.collection,
            date=date.fromisoformat(probably_date),
            validation={"probably_date": probably_date},
        )

    def test_task_enqueue_log_parsing_jobs_enqueues_one_daily_job_per_collection_date(
        self,
    ):
        first = self._log_file("1" * 32, "2012-03-10")
        second = self._log_file("2" * 32, "2012-03-10")
        third = self._log_file("3" * 32, "2012-03-15")

        with patch(
            "metrics.tasks.log_parsing.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_enqueue_log_parsing_jobs.run(
                collections=["books"],
                include_logs_with_error=False,
                from_date="2012-03-01",
                until_date="2012-03-31",
            )

        self.assertEqual(result["enqueued_jobs"], 2)
        self.assertEqual(result["enqueued_logs"], 3)
        self.assertEqual(mocked_apply_async.call_count, 2)
        jobs = list(DailyMetricJob.objects.order_by("access_date"))
        self.assertEqual(
            [job.access_date for job in jobs], [date(2012, 3, 10), date(2012, 3, 15)]
        )
        self.assertEqual(jobs[0].input_log_hashes, sorted([first.hash, second.hash]))
        self.assertEqual(jobs[1].input_log_hashes, [third.hash])

    def test_task_enqueue_log_parsing_jobs_allows_queue_override_and_robots_source(
        self,
    ):
        self._log_file("1" * 32, "2012-03-10")

        with patch(
            "metrics.tasks.log_parsing.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            task_enqueue_log_parsing_jobs.run(
                collections=["books"],
                include_logs_with_error=False,
                from_date="2012-03-01",
                until_date="2012-03-31",
                queue_name="parse_small_mult",
                robots_source="counter",
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(
            mocked_apply_async.call_args.kwargs["queue"], "parse_small_mult"
        )
        self.assertEqual(mocked_apply_async.call_args.kwargs["args"][-1], "counter")

    def test_task_enqueue_log_parsing_jobs_excludes_error_logs_when_not_requested(self):
        queued = self._log_file("1" * 32, "2012-03-10")
        error = self._log_file(
            "2" * 32, "2012-03-10", status=choices.LOG_FILE_STATUS_ERROR
        )

        with patch(
            "metrics.tasks.log_parsing.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_enqueue_log_parsing_jobs.run(
                collections=["books"],
                include_logs_with_error=False,
                from_date="2012-03-01",
                until_date="2012-03-31",
            )

        mocked_apply_async.assert_called_once()
        job = DailyMetricJob.objects.get()
        self.assertEqual(job.input_log_hashes, [queued.hash])
        self.assertNotIn(error.hash, job.input_log_hashes)
        self.assertEqual(result["enqueued_logs"], 1)
        self.assertEqual(result["enqueued_jobs"], 1)

    def test_task_enqueue_log_parsing_jobs_skip_log_hashes_prevents_reprocessing_same_auto_run(
        self,
    ):
        skipped = self._log_file(
            "1" * 32, "2012-03-10", status=choices.LOG_FILE_STATUS_ERROR
        )
        queued = self._log_file("2" * 32, "2012-03-10")

        with patch(
            "metrics.tasks.log_parsing.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_enqueue_log_parsing_jobs.run(
                collections=["books"],
                include_logs_with_error=True,
                from_date="2012-03-01",
                until_date="2012-03-31",
                skip_log_hashes=[skipped.hash],
            )

        mocked_apply_async.assert_called_once()
        job = DailyMetricJob.objects.get()
        self.assertEqual(job.input_log_hashes, [queued.hash])
        self.assertEqual(result["enqueued_jobs"], 1)
        self.assertEqual(result["enqueued_logs"], 1)

    def test_task_enqueue_log_parsing_jobs_max_log_files_counts_files_not_jobs(self):
        first = self._log_file("1" * 32, "2012-03-10")
        second = self._log_file("2" * 32, "2012-03-10")

        with patch(
            "metrics.tasks.log_parsing.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_enqueue_log_parsing_jobs.run(
                collections=["books"],
                include_logs_with_error=False,
                max_log_files=1,
                from_date="2012-03-01",
                until_date="2012-03-31",
            )

        mocked_apply_async.assert_called_once()
        job = DailyMetricJob.objects.get()
        self.assertEqual(job.input_log_hashes, [first.hash])
        self.assertNotIn(second.hash, job.input_log_hashes)
        self.assertEqual(result["enqueued_logs"], 1)
        self.assertEqual(result["enqueued_jobs"], 1)
        self.assertTrue(result["reached_max_log_files"])

    def test_wait_log_parsing_wave_rechecks_until_daily_jobs_complete(self):
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
        )

        with patch(
            "metrics.tasks.log_parsing.task_wait_log_parsing_wave.apply_async"
        ) as mocked_wait_apply_async:
            with patch(
                "metrics.tasks.log_parsing.task_enqueue_log_parsing_jobs.apply_async"
            ) as mocked_parse_logs_apply_async:
                result = task_wait_log_parsing_wave.run(
                    wave_log_hashes=[job.pk],
                    collections=["books"],
                    include_logs_with_error=False,
                    max_log_files=2,
                    auto_reexecute=True,
                )

        self.assertEqual(
            result, {"wave_completed": False, "reexecution_enqueued": False}
        )
        mocked_parse_logs_apply_async.assert_not_called()
        mocked_wait_apply_async.assert_called_once()

    def test_wait_log_parsing_wave_preserves_queue_name(self):
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
        )

        with patch(
            "metrics.tasks.log_parsing.task_wait_log_parsing_wave.apply_async"
        ) as mocked_wait_apply_async:
            result = task_wait_log_parsing_wave.run(
                wave_log_hashes=[job.pk],
                collections=["books"],
                queue_name="parse_small",
            )

        self.assertEqual(
            result, {"wave_completed": False, "reexecution_enqueued": False}
        )
        self.assertEqual(
            mocked_wait_apply_async.call_args.kwargs["queue"], "parse_small"
        )


class ResumeDailyMetricJobTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")

    def test_resume_log_exports_requeues_error_daily_jobs(self):
        log_file = LogFile.objects.create(
            hash="1" * 32,
            path="/tmp/1.log.gz",
            stat_result={},
            status=choices.LOG_FILE_STATUS_ERROR,
            collection=self.collection,
            date=date(2012, 3, 10),
        )
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_ERROR,
            input_log_hashes=[log_file.hash],
        )

        with patch(
            "metrics.tasks.resume.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_resume_log_exports.run(
                collections=["books"],
                from_date="2012-03-01",
                until_date="2012-03-31",
                queue_name="parse_small_mult",
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(mocked_apply_async.call_args.kwargs["args"][0], job.pk)
        self.assertEqual(
            mocked_apply_async.call_args.kwargs["queue"], "parse_small_mult"
        )
        self.assertEqual(result["resumed_logs"], 1)

    def test_resume_log_exports_clears_payload_when_current_logs_change(self):
        log_file = LogFile.objects.create(
            hash="2" * 32,
            path="/tmp/2.log.gz",
            stat_result={},
            status=choices.LOG_FILE_STATUS_QUEUED,
            collection=self.collection,
            date=date(2012, 3, 10),
        )
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_ERROR,
            input_log_hashes=["1" * 32],
            storage_path="books/2012/03/2012-03-10.json",
            payload_hash="abc",
            summary={"month_document_count": 1},
        )

        with patch(
            "metrics.tasks.resume.task_build_and_export_daily_metric_job.apply_async"
        ):
            task_resume_log_exports.run(
                collections=["books"],
                from_date="2012-03-01",
                until_date="2012-03-31",
            )

        job.refresh_from_db()
        self.assertEqual(job.input_log_hashes, [log_file.hash])
        self.assertEqual(job.storage_path, "")
        self.assertEqual(job.payload_hash, "")
        self.assertEqual(job.summary, {})

    def test_resume_log_exports_preserves_payload_when_current_logs_match(self):
        log_file = LogFile.objects.create(
            hash="1" * 32,
            path="/tmp/1.log.gz",
            stat_result={},
            status=choices.LOG_FILE_STATUS_ERROR,
            collection=self.collection,
            date=date(2012, 3, 10),
        )
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_ERROR,
            input_log_hashes=[log_file.hash],
            storage_path="books/2012/03/2012-03-10.json",
            payload_hash="abc",
            summary={"month_document_count": 1},
        )

        with patch(
            "metrics.tasks.resume.task_build_and_export_daily_metric_job.apply_async"
        ):
            task_resume_log_exports.run(
                collections=["books"],
                from_date="2012-03-01",
                until_date="2012-03-31",
            )

        job.refresh_from_db()
        self.assertEqual(job.storage_path, "books/2012/03/2012-03-10.json")
        self.assertEqual(job.payload_hash, "abc")
        self.assertEqual(job.summary, {"month_document_count": 1})

    def test_resume_log_exports_requeues_stored_payload_without_current_logs(self):
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_ERROR,
            input_log_hashes=["1" * 32],
            storage_path="books/2012/03/2012-03-10.json",
            payload_hash="abc",
        )

        with patch(
            "metrics.tasks.resume.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_resume_log_exports.run(
                collections=["books"],
                from_date="2012-03-01",
                until_date="2012-03-31",
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(mocked_apply_async.call_args.kwargs["args"][0], job.pk)
        self.assertEqual(result["resumed_jobs"], 1)

    def test_resume_log_exports_skips_jobs_without_logs_or_payload(self):
        DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_ERROR,
        )

        with patch(
            "metrics.tasks.resume.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_resume_log_exports.run(
                collections=["books"],
                from_date="2012-03-01",
                until_date="2012-03-31",
            )

        mocked_apply_async.assert_not_called()
        self.assertEqual(result["resumed_jobs"], 0)

    def test_resume_log_exports_releases_stale_exporting_jobs(self):
        log_file = LogFile.objects.create(
            hash="1" * 32,
            path="/tmp/1.log.gz",
            stat_result={},
            status=choices.LOG_FILE_STATUS_ERROR,
            collection=self.collection,
            date=date(2012, 3, 10),
        )
        job = DailyMetricJob.objects.create(
            collection=self.collection,
            access_date=date(2012, 3, 10),
            status=DailyMetricJob.STATUS_EXPORTING,
            input_log_hashes=[log_file.hash],
            export_started_at=timezone.now() - timedelta(minutes=120),
        )

        with patch(
            "metrics.tasks.resume.task_build_and_export_daily_metric_job.apply_async"
        ) as mocked_apply_async:
            result = task_resume_log_exports.run(
                collections=["books"],
                from_date="2012-03-01",
                until_date="2012-03-31",
                stale_after_minutes=60,
            )

        job.refresh_from_db()
        self.assertEqual(job.status, DailyMetricJob.STATUS_PENDING)
        mocked_apply_async.assert_called_once()
        self.assertEqual(result["released_stale_batches"], 1)
