from counter_api.report_items import iter_report_items

METRIC_INVARIANTS = (
    ("Total_Item_Investigations", "Unique_Item_Investigations"),
    ("Total_Item_Requests", "Unique_Item_Requests"),
    ("Total_Item_Investigations", "Total_Item_Requests"),
    ("Unique_Item_Investigations", "Unique_Item_Requests"),
    ("Total_Item_Investigations", "Unique_Title_Investigations"),
    ("Unique_Item_Investigations", "Unique_Title_Investigations"),
    ("Total_Item_Requests", "Unique_Title_Requests"),
    ("Unique_Item_Requests", "Unique_Title_Requests"),
    ("Unique_Title_Investigations", "Unique_Title_Requests"),
)
BOOK_TITLE_REQUIREMENTS = (
    (
        "Unique_Title_Investigations",
        ("Total_Item_Investigations", "Unique_Item_Investigations"),
    ),
    (
        "Unique_Title_Requests",
        ("Total_Item_Requests", "Unique_Item_Requests"),
    ),
)


def metric_invariant_errors(payload):
    errors = []
    header = payload["Report_Header"]
    report_id = header["Report_ID"]
    selected_metrics = header["Report_Filters"].get("Metric_Type")

    for _, item in iter_report_items(payload["Report_Items"]):
        name = item.get("Title") or item.get("Item") or item.get("Platform") or ""

        for attributes in item.get("Attribute_Performance", []):
            performance = attributes.get("Performance", {})

            for greater_metric, lesser_metric in METRIC_INVARIANTS:
                greater = performance.get(greater_metric, {})
                lesser = performance.get(lesser_metric, {})

                for month in set(greater) | set(lesser):
                    if lesser.get(month, 0) > greater.get(month, 0):
                        errors.append(
                            f"{name} {month}: {lesser_metric} exceeds {greater_metric}"
                        )

            if report_id == "IR" or attributes.get("Data_Type") not in {
                "Book",
                "Reference_Work",
            }:
                continue

            for title_metric, item_metrics in BOOK_TITLE_REQUIREMENTS:
                if selected_metrics and title_metric not in selected_metrics:
                    continue

                months = {
                    month
                    for metric in item_metrics
                    for month in performance.get(metric, {})
                }

                for month in months:
                    if performance.get(title_metric, {}).get(month, 0):
                        continue

                    errors.append(f"{name} {month}: {title_metric} is missing")

    return errors
