import unittest
from unittest.mock import patch

from core.collectors import scielo_books


class SciELOBooksCollectorTests(unittest.TestCase):
    def test_build_url_appends_query_params(self):
        url = scielo_books.build_url(
            "https://books.example/_changes",
            {"since": 10, "limit": 100},
        )

        self.assertEqual(url, "https://books.example/_changes?since=10&limit=100")

    def test_sanitize_raw_data_renames__id(self):
        payload = {"_id": "abc123", "TYPE": "Monograph"}

        sanitized = scielo_books.sanitize_raw_data(payload)

        self.assertEqual(sanitized["id"], "abc123")
        self.assertNotIn("_id", sanitized)
        self.assertEqual(sanitized["TYPE"], "Monograph")

    def test_extract_last_seq_accepts_both_couch_formats(self):
        self.assertEqual(scielo_books.extract_last_seq({"last_seq": 123}), 123)
        self.assertEqual(scielo_books.extract_last_seq({"seq": 456}), 456)

    @patch("core.collectors.scielo_books.fetch_document")
    @patch("core.collectors.scielo_books.fetch_changes_page")
    def test_iter_change_documents_uses_docs_from_changes_payload(
        self, mock_fetch_changes_page, mock_fetch_document
    ):
        mock_fetch_changes_page.side_effect = [
            {
                "results": [
                    {
                        "seq": 10,
                        "id": "book1",
                        "doc": {
                            "_id": "book1",
                            "TYPE": "Monograph",
                            "title": "Book One",
                        },
                    }
                ],
                "last_seq": 10,
            },
            {"results": [], "last_seq": 10},
        ]

        results = list(
            scielo_books.iter_change_documents(
                base_url="https://books.example", db_name="scielobooks_1a"
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["payload"]["id"], "book1")
        self.assertEqual(results[0]["payload"]["TYPE"], "Monograph")
        mock_fetch_document.assert_not_called()


if __name__ == "__main__":
    unittest.main()
