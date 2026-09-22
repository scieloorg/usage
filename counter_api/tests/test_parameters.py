from django.test import SimpleTestCase

from counter_api.parameters import parse_parameters


class ReportParameterTests(SimpleTestCase):
    def test_invalid_filter_values_are_ignored_without_discarding_valid_values(self):
        params = parse_parameters(
            {
                "metric_type": "Total_Item_Requests|Inexistente",
                "access_method": "Inválido",
                "yop": "2024|2025-2023",
            },
            "tr",
        )

        self.assertEqual(params["Metric_Type"], ["Total_Item_Requests"])
        self.assertEqual(params["YOP"], ["2024"])
        self.assertNotIn("Access_Method", params)
        self.assertEqual(
            params["parameter_exceptions"],
            [
                {
                    "Code": 3060,
                    "Message": "Invalid ReportFilter Value",
                    "Data": "Inválido|Inexistente|2025-2023",
                }
            ],
        )

    def test_filters_outside_report_context_are_ignored(self):
        params = parse_parameters(
            {"access_type": "Open", "metric_type": "Total_Item_Requests"},
            "pr",
        )

        self.assertEqual(params["Metric_Type"], ["Total_Item_Requests"])
        self.assertNotIn("Access_Type", params)
        self.assertEqual(params["parameter_exceptions"][0]["Code"], 3050)
        self.assertEqual(params["parameter_exceptions"][0]["Data"], "access_type")

    def test_standard_view_keeps_fixed_filters(self):
        params = parse_parameters(
            {
                "data_type": "Book",
                "item_id": "Print_ISSN:1234-5678",
                "attributes_to_show": "YOP",
                "exclude_monthly_details": "true",
            },
            "tr_j3",
        )

        self.assertNotIn("Data_Type", params)
        self.assertNotIn("Item_ID", params)
        self.assertNotIn("Attributes_To_Show", params)
        self.assertNotIn("Exclude_Monthly_Details", params)
        self.assertEqual(params["parameter_exceptions"][0]["Code"], 3050)
        self.assertEqual(
            params["parameter_exceptions"][0]["Data"],
            "attributes_to_show|data_type|exclude_monthly_details|item_id",
        )

    def test_yop_uses_counter_special_values_as_limits(self):
        params = parse_parameters(
            {"yop": "0000|0001|2020-2024|9999|9999-9999|9999-0001"},
            "tr",
        )

        self.assertEqual(
            params["YOP"],
            ["0001", "2020-2024", "9999", "9999-9999"],
        )
        self.assertEqual(
            params["parameter_exceptions"][0]["Data"],
            "0000|9999-0001",
        )

    def test_granularity_and_tabular_month_exclusion_use_their_own_formats(self):
        json_params = parse_parameters({"granularity": "Totals"}, "tr")
        tabular_params = parse_parameters(
            {"format": "tsv", "exclude_monthly_details": "true"},
            "tr",
        )
        invalid_params = parse_parameters({"granularity": "Year"}, "tr")

        self.assertEqual(json_params["Granularity"], "Totals")
        self.assertEqual(tabular_params["Exclude_Monthly_Details"], True)
        self.assertNotIn("Exclude_Monthly_Details", json_params)
        self.assertNotIn("Granularity", tabular_params)
        self.assertEqual(invalid_params["parameter_exceptions"][0]["Code"], 3062)
