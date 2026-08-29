from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from metrics.services.parsing.environment import setup_parsing_environment


class ParsingEnvironmentTests(TestCase):
    @patch("metrics.services.parsing.environment.build_url_translation_manager")
    @patch("metrics.services.parsing.environment.log_handler.LogParser")
    def test_setup_builds_parser_and_delegates_metadata_preparation(
        self,
        log_parser_class,
        build_url_translation_manager,
    ):
        log_file = SimpleNamespace(path="/app/logs/books/2026-08-01.log.gz")
        mmdb = SimpleNamespace(data=b"mmdb")
        log_parser = log_parser_class.return_value
        translation_manager = build_url_translation_manager.return_value

        result = setup_parsing_environment(
            log_file=log_file,
            robots_list=["robot"],
            mmdb=mmdb,
        )

        log_parser_class.assert_called_once_with(
            mmdb_data=b"mmdb",
            robots_list=["robot"],
            output_mode="dict",
        )
        self.assertEqual(log_parser.logfile, log_file.path)
        build_url_translation_manager.assert_called_once_with(log_file)
        self.assertEqual(result, (log_parser, translation_manager))
