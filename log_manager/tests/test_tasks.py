from unittest.mock import patch

from django.test import TestCase

from log_manager import tasks


class ValidateLogFilesTaskTests(TestCase):
    def test_returns_none_for_empty_date_range(self):
        with patch("log_manager.tasks.task_validate_log_file.s") as mocked_signature:
            result = tasks.task_validate_log_files.run(
                collections=["books"],
                from_date="2024-02-02",
                until_date="2024-02-01",
            )

        self.assertIsNone(result)
        mocked_signature.assert_not_called()

    def test_routes_parse_callback_to_collection_queue(self):
        with patch(
            "log_manager.tasks.task_enqueue_log_parsing_jobs.apply_async"
        ) as mocked_apply_async:
            tasks.task_validate_log_files.run(
                collections=["books"],
                from_date="2024-02-01",
                until_date="2024-02-02",
                trigger_parse=True,
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(mocked_apply_async.call_args.kwargs["queue"], "parse_small")
        self.assertEqual(
            mocked_apply_async.call_args.kwargs["kwargs"]["queue_name"],
            "parse_small",
        )

    def test_routes_each_collection_to_its_queue(self):
        with patch(
            "log_manager.tasks.task_enqueue_log_parsing_jobs.apply_async"
        ) as mocked_apply_async:
            tasks.task_validate_log_files.run(
                collections=["books", "scl"],
                from_date="2024-02-01",
                until_date="2024-02-02",
                trigger_parse=True,
            )

        calls = {
            call.kwargs["kwargs"]["collections"][0]: call.kwargs["queue"]
            for call in mocked_apply_async.call_args_list
        }
        self.assertEqual(calls, {"books": "parse_small", "scl": "parse_xlarge"})
