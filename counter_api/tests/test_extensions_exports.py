from io import BytesIO
from unittest import TestCase

from openpyxl import load_workbook

from counter_api.extensions.exports import build_export


class ExtensionExportTests(TestCase):
    def test_ranking_csv_and_xlsx_keep_group_and_rank(self):
        payload = {
            "groups": [
                {
                    "dimensions": {"country": "BR", "language": "pt"},
                    "items": [{"id": "article-1", "title": "Artigo", "count": 12}],
                }
            ]
        }

        csv_file = build_export(payload, "ranking", "csv")
        lines = csv_file.read().decode("utf-8").splitlines()
        xlsx_file = build_export(payload, "ranking", "xlsx")
        sheet = load_workbook(BytesIO(xlsx_file.read()), read_only=True).active

        self.assertEqual(lines[0], "Country,Language,Rank,ID,Title,Count")
        self.assertEqual(lines[1], "BR,pt,1,article-1,Artigo,12")
        self.assertEqual(sheet["D2"].value, "article-1")
        self.assertEqual(sheet["F2"].value, 12)
