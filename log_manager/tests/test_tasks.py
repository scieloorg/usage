from unittest.mock import patch

from django.test import TestCase, override_settings

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

    def test_routes_parse_callback_to_configured_queue(self):
        with patch(
            "log_manager.tasks.task_enqueue_log_parsing_jobs.apply_async"
        ) as mocked_apply_async:
            tasks.task_validate_log_files.run(
                collections=["books"],
                from_date="2024-02-01",
                until_date="2024-02-02",
                trigger_parse=True,
                parse_queue_name="parse_tiny",
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(mocked_apply_async.call_args.kwargs["queue"], "parse_tiny")
        self.assertEqual(
            mocked_apply_async.call_args.kwargs["kwargs"]["queue_name"],
            "parse_tiny",
        )

    def test_routes_all_configured_collections_to_same_queue(self):
        with patch(
            "log_manager.tasks.task_enqueue_log_parsing_jobs.apply_async"
        ) as mocked_apply_async:
            tasks.task_validate_log_files.run(
                collections=["books", "scl"],
                from_date="2024-02-01",
                until_date="2024-02-02",
                trigger_parse=True,
                parse_queue_name="parse_tiny",
            )

        calls = {
            call.kwargs["kwargs"]["collections"][0]: call.kwargs["queue"]
            for call in mocked_apply_async.call_args_list
        }
        self.assertEqual(calls, {"books": "parse_tiny", "scl": "parse_tiny"})

    @patch(
        "log_manager.tasks.validation.get_validation_candidate_hashes_by_collection",
        return_value={"books": ["a" * 32]},
    )
    @patch("log_manager.tasks.chord")
    def test_routes_parse_callback_after_validation_to_configured_queue(
        self, mocked_chord, mocked_candidates
    ):
        tasks.task_validate_log_files.run(
            collections=["books"],
            trigger_parse=True,
            parse_queue_name="parse_tiny",
        )

        callback = mocked_chord.return_value.call_args.args[0]
        self.assertEqual(callback.options["queue"], "parse_tiny")
        self.assertEqual(callback.kwargs["queue_name"], "parse_tiny")

    @override_settings(DEFAULT_PARSE_QUEUE="parse_default")
    def test_trigger_parse_uses_default_queue(self):
        with patch(
            "log_manager.tasks.task_enqueue_log_parsing_jobs.apply_async"
        ) as mocked_apply_async:
            tasks.task_validate_log_files.run(
                collections=["books"],
                from_date="2024-02-01",
                until_date="2024-02-02",
                trigger_parse=True,
            )

        self.assertEqual(mocked_apply_async.call_args.kwargs["queue"], "parse_default")


class SearchLogFilesTaskTests(TestCase):
    @patch("log_manager.tasks.catalog.catalog_log_files_from_configured_directories")
    @patch("log_manager.tasks.task_validate_log_files.apply_async")
    def test_propagates_configured_queue_to_validation(
        self, mocked_validation_apply_async, mocked_catalog
    ):
        tasks.task_search_log_files.run(
            collections=["data"],
            days_to_go_back=7,
            trigger_validation=True,
            parse_queue_name="parse_tiny",
        )

        mocked_catalog.assert_called_once()
        self.assertEqual(
            mocked_validation_apply_async.call_args.kwargs["kwargs"][
                "parse_queue_name"
            ],
            "parse_tiny",
        )

    @override_settings(DEFAULT_PARSE_QUEUE="parse_default")
    @patch("log_manager.tasks.catalog.catalog_log_files_from_configured_directories")
    @patch("log_manager.tasks.task_validate_log_files.apply_async")
    def test_trigger_validation_uses_default_queue(
        self, mocked_validation_apply_async, mocked_catalog
    ):
        tasks.task_search_log_files.run(
            collections=["data"],
            days_to_go_back=7,
            trigger_validation=True,
        )

        mocked_catalog.assert_called_once()
        self.assertEqual(
            mocked_validation_apply_async.call_args.kwargs["kwargs"][
                "parse_queue_name"
            ],
            "parse_default",
        )
