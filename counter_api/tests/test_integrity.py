from unittest import TestCase

from counter_api.integrity import metric_invariant_errors


class ReportIntegrityTests(TestCase):
    def test_book_reports_require_title_metrics_alongside_item_metrics(self):
        payload = {
            "Report_Header": {
                "Report_ID": "TR_B3",
                "Report_Filters": {
                    "Metric_Type": [
                        "Total_Item_Investigations",
                        "Unique_Title_Investigations",
                    ]
                },
            },
            "Report_Items": [
                {
                    "Title": "Book",
                    "Attribute_Performance": [
                        {
                            "Data_Type": "Book",
                            "Performance": {
                                "Total_Item_Investigations": {"2024-01": 2},
                            },
                        }
                    ],
                }
            ],
        }

        self.assertEqual(
            metric_invariant_errors(payload),
            ["Book 2024-01: Unique_Title_Investigations is missing"],
        )
