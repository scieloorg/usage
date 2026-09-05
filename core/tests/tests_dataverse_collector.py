from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.collectors import dataverse


@override_settings(
    DATAVERSE_ENDPOINT="https://data.example/api",
    DATAVERSE_ROOT_COLLECTION="root",
)
class DataverseCollectorTests(SimpleTestCase):
    @patch("core.collectors.dataverse._get_files")
    @patch("core.collectors.dataverse._get_dataverse_contents")
    def test_iter_dataset_metadata_includes_root_and_nested_datasets(
        self,
        mock_get_contents,
        mock_get_files,
    ):
        root_dataset = {
            "id": 1,
            "type": "dataset",
            "persistentUrl": "https://doi.org/10.1234/root",
            "publicationDate": "2026-09-01",
        }
        child_dataset = {
            "id": 2,
            "type": "dataset",
            "persistentUrl": "https://doi.org/10.1234/child",
            "publicationDate": "2026-09-02",
        }
        nested_dataset = {
            "id": 3,
            "type": "dataset",
            "persistentUrl": "https://doi.org/10.1234/nested",
            "publicationDate": "2026-09-03",
        }
        mock_get_contents.side_effect = {
            "root": [
                root_dataset,
                {"id": 10, "type": "dataverse", "title": "Child"},
            ],
            10: [
                child_dataset,
                {"id": 20, "type": "dataverse", "title": "Nested"},
            ],
            20: [nested_dataset],
        }.get
        mock_get_files.side_effect = lambda dataset_id: [
            {
                "label": f"file-{dataset_id}.csv",
                "dataFile": {
                    "id": dataset_id * 100,
                    "persistentId": f"doi:10.1234/file-{dataset_id}",
                },
            }
        ]

        payloads = list(dataverse.iter_dataset_metadata("2026-08-29", "2026-09-05"))

        self.assertEqual(
            [(payload["dataset_doi"], payload["title"]) for payload in payloads],
            [
                ("10.1234/root", "root"),
                ("10.1234/child", "Child"),
                ("10.1234/nested", "Nested"),
            ],
        )
        self.assertEqual(mock_get_files.call_count, 3)

    @patch("core.collectors.dataverse._get_files")
    @patch("core.collectors.dataverse._get_dataverse_contents")
    def test_iter_dataset_metadata_filters_root_dataset_by_date(
        self,
        mock_get_contents,
        mock_get_files,
    ):
        mock_get_contents.return_value = [
            {
                "id": 1,
                "type": "dataset",
                "persistentUrl": "https://doi.org/10.1234/old",
                "publicationDate": "2026-08-28",
            }
        ]

        payloads = list(dataverse.iter_dataset_metadata("2026-08-29", "2026-09-05"))

        self.assertEqual(payloads, [])
        mock_get_files.assert_not_called()
