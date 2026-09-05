from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from requests.exceptions import HTTPError

from core.collectors import preprints


@override_settings(
    OAI_PMH_PREPRINT_ENDPOINT="https://preprints.example/oai",
    OAI_PMH_MAX_RETRIES=2,
    OAI_METADATA_PREFIX="oai_dc",
)
class PreprintsCollectorTests(SimpleTestCase):
    @patch("core.collectors.preprints.Sickle")
    def test_iter_records_uses_remote_date_filter_and_ignores_deleted(
        self, mock_sickle
    ):
        record = SimpleNamespace(
            header=SimpleNamespace(
                identifier="oai:preprints:1",
                datestamp="2026-09-01T12:00:00Z",
            )
        )
        mock_sickle.return_value.ListRecords.return_value = [record]

        records = list(preprints.iter_records("2026-08-29", "2026-09-05"))

        self.assertEqual(records, [record])
        mock_sickle.return_value.ListRecords.assert_called_once_with(
            ignore_deleted=True,
            metadataPrefix="oai_dc",
            **{"from": "2026-08-29", "until": "2026-09-05"},
        )

    @patch("core.collectors.preprints.Sickle")
    def test_iter_records_filters_full_feed_after_date_filter_http_500(
        self, mock_sickle
    ):
        response = Mock(status_code=500)
        error = HTTPError(response=response)
        old_record = SimpleNamespace(
            header=SimpleNamespace(
                identifier="oai:preprints:old",
                datestamp="2026-08-28T23:59:59Z",
            )
        )
        recent_record = SimpleNamespace(
            header=SimpleNamespace(
                identifier="oai:preprints:recent",
                datestamp="2026-09-01T12:00:00Z",
            )
        )
        future_record = SimpleNamespace(
            header=SimpleNamespace(
                identifier="oai:preprints:future",
                datestamp="2026-09-06T00:00:00Z",
            )
        )
        mock_sickle.return_value.ListRecords.side_effect = [
            error,
            [old_record, recent_record, future_record],
        ]

        records = list(preprints.iter_records("2026-08-29", "2026-09-05"))

        self.assertEqual(records, [recent_record])
        self.assertEqual(mock_sickle.return_value.ListRecords.call_count, 2)
        mock_sickle.return_value.ListRecords.assert_called_with(
            ignore_deleted=True,
            metadataPrefix="oai_dc",
        )

    @patch("core.collectors.preprints.Sickle")
    def test_iter_records_does_not_fallback_for_other_http_errors(self, mock_sickle):
        response = Mock(status_code=503)
        mock_sickle.return_value.ListRecords.side_effect = HTTPError(response=response)

        with self.assertRaises(HTTPError):
            list(preprints.iter_records("2026-08-29", "2026-09-05"))

        self.assertEqual(mock_sickle.return_value.ListRecords.call_count, 1)
