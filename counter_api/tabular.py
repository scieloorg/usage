import csv
from codecs import BOM_UTF8
from datetime import date
from io import StringIO
from tempfile import SpooledTemporaryFile
from time import monotonic

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

from counter_api.constants import EXCEL_MAX_ROWS, SPOOL_SIZE, STANDARD_VIEWS
from counter_api.dates import iter_months
from counter_api.exceptions import insufficient_information, service_unavailable
from counter_api.report_items import iter_report_items

MONTH_LABELS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
TABULAR_FILTER_EXCLUSIONS = {"Begin_Date", "End_Date", "Metric_Type"}


def build_workbook(report, deadline=None):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet()
    sheet.title = report["Report_Header"]["Report_ID"]
    for column in (1, 2, 4):
        sheet.column_dimensions[chr(64 + column)].width = 28

    for row_number, row in enumerate(_report_rows(report), start=1):
        if deadline and monotonic() >= deadline:
            workbook.close()
            raise service_unavailable()

        if row_number > EXCEL_MAX_ROWS:
            workbook.close()
            raise insufficient_information()

        if row_number == 15:
            heading = []
            for value in row:
                cell = WriteOnlyCell(sheet, value=value)
                cell.font = Font(bold=True)
                heading.append(cell)
            row = heading

        sheet.append(row)

    output = SpooledTemporaryFile(max_size=SPOOL_SIZE)
    if deadline and monotonic() >= deadline:
        workbook.close()
        output.close()
        raise service_unavailable()

    workbook.save(output)
    output.seek(0)

    return output


def build_tsv(report, deadline=None):
    output = SpooledTemporaryFile(max_size=SPOOL_SIZE)
    output.write(BOM_UTF8)
    line = StringIO(newline="")
    writer = csv.writer(line, delimiter="\t", lineterminator="\n")

    for row in _report_rows(report):
        if deadline and monotonic() >= deadline:
            output.close()
            raise service_unavailable()

        writer.writerow(row)
        output.write(line.getvalue().encode("utf-8"))
        line.seek(0)
        line.truncate(0)

    output.seek(0)

    return output


def _report_rows(report):
    header = report["Report_Header"]
    yield from (
        ("Report_Name", header["Report_Name"]),
        ("Report_ID", header["Report_ID"]),
        ("Release", header["Release"]),
        ("Institution_Name", header["Institution_Name"]),
        ("Institution_ID", _header_identifiers(header["Institution_ID"])),
        ("Metric_Types", "; ".join(_metric_types(report))),
        (
            "Report_Filters",
            _pairs(
                {
                    key: value
                    for key, value in header["Report_Filters"].items()
                    if key not in TABULAR_FILTER_EXCLUSIONS
                }
            ),
        ),
        ("Report_Attributes", _pairs(header.get("Report_Attributes") or {})),
        ("Exceptions", _exceptions(header.get("Exceptions") or [])),
        (
            "Reporting_Period",
            f"Begin_Date={header['Report_Filters']['Begin_Date']}; "
            f"End_Date={header['Report_Filters']['End_Date']}",
        ),
        ("Created", header["Created"]),
        ("Created_By", header["Created_By"]),
        ("Registry_Record", header.get("Registry_Record", "")),
        ("", ""),
    )

    months = _months(header["Report_Filters"])
    if (header.get("Report_Attributes") or {}).get("Exclude_Monthly_Details"):
        months = []

    columns = _columns(header, months)
    yield [
        f"{MONTH_LABELS[int(column[5:]) - 1]}-{column[:4]}"
        if column in months
        else column
        for column in columns
    ]

    for values in _item_values(report["Report_Items"]):
        yield [values.get(column, "") for column in columns]


def _item_values(items):
    for parent, item in iter_report_items(items):
        identifiers = item.get("Item_ID") or {}
        parent_ids = parent.get("Item_ID") or {}
        common = {
            "Platform": item.get("Platform", ""),
            "Title": item.get("Title", ""),
            "Item": item.get("Item", ""),
            "Publisher": item.get("Publisher", ""),
            "Publisher_ID": "",
            "DOI": identifiers.get("DOI", ""),
            "Proprietary_ID": identifiers.get("Proprietary", ""),
            "ISBN": identifiers.get("ISBN", ""),
            "Print_ISSN": identifiers.get("Print_ISSN", ""),
            "Online_ISSN": identifiers.get("Online_ISSN", ""),
            "URI": identifiers.get("URI", ""),
            "Parent_Title": parent.get("Title", ""),
            "Parent_Authors": "",
            "Parent_Publication_Date": "",
            "Parent_Article_Version": "",
            "Parent_Data_Type": parent.get("Data_Type", ""),
            "Parent_DOI": parent_ids.get("DOI", ""),
            "Parent_Proprietary_ID": parent_ids.get("Proprietary", ""),
            "Parent_ISBN": parent_ids.get("ISBN", ""),
            "Parent_Print_ISSN": parent_ids.get("Print_ISSN", ""),
            "Parent_Online_ISSN": parent_ids.get("Online_ISSN", ""),
            "Parent_URI": parent_ids.get("URI", ""),
        }

        for attributes in item.get("Attribute_Performance", []):
            for metric_type, counts in attributes.get("Performance", {}).items():
                values = dict(common)
                values.update(
                    {
                        "Data_Type": attributes.get("Data_Type", ""),
                        "YOP": attributes.get("YOP", ""),
                        "Access_Type": attributes.get("Access_Type", ""),
                        "Access_Method": attributes.get("Access_Method", ""),
                        "Metric_Type": metric_type,
                        "Reporting_Period_Total": sum(counts.values()),
                        **counts,
                    }
                )
                yield values


def _months(filters):
    begin = date.fromisoformat(filters["Begin_Date"]).replace(day=1)
    end = date.fromisoformat(filters["End_Date"]).replace(day=1)

    return [month.strftime("%Y-%m") for month in iter_months(begin, end)]


def _header_identifiers(values):
    identifiers = []
    for namespace, namespace_values in values.items():
        if namespace == "Proprietary":
            identifiers.extend(namespace_values)
        else:
            identifiers.extend(f"{namespace}:{value}" for value in namespace_values)
    return "; ".join(identifiers)


def _metric_types(report):
    metrics = set()
    for _, item in iter_report_items(report["Report_Items"]):
        for attributes in item.get("Attribute_Performance", []):
            metrics.update(attributes.get("Performance", {}))
    return sorted(metrics)


def _columns(header, months):
    report_id = header["Report_ID"]
    standard_view = STANDARD_VIEWS.get(report_id.lower()) or {}
    attributes = list(
        standard_view.get("attributes")
        or (header.get("Report_Attributes") or {}).get("Attributes_To_Show", [])
    )
    if report_id in {"PR", "TR", "IR"} and "Data_Type" not in attributes:
        attributes.insert(0, "Data_Type")
    metric_columns = [
        *attributes,
        "Metric_Type",
        "Reporting_Period_Total",
        *months,
    ]
    if report_id == "PR":
        return ["Platform", *metric_columns]
    if report_id == "IR":
        parent_columns = []
        if (header.get("Report_Attributes") or {}).get("Include_Parent_Details"):
            parent_columns = [
                "Parent_Title",
                "Parent_Authors",
                "Parent_Publication_Date",
                "Parent_Article_Version",
                "Parent_Data_Type",
                "Parent_DOI",
                "Parent_Proprietary_ID",
                "Parent_ISBN",
                "Parent_Print_ISSN",
                "Parent_Online_ISSN",
                "Parent_URI",
            ]
        return [
            "Item",
            "Publisher",
            "Publisher_ID",
            "Platform",
            "DOI",
            "Proprietary_ID",
            "ISBN",
            "Print_ISSN",
            "Online_ISSN",
            "URI",
            *parent_columns,
            *metric_columns,
        ]
    if report_id == "TR_J3":
        return [
            "Title",
            "Publisher",
            "Publisher_ID",
            "Platform",
            "DOI",
            "Proprietary_ID",
            "Print_ISSN",
            "Online_ISSN",
            "URI",
            *metric_columns,
        ]
    return [
        "Title",
        "Publisher",
        "Publisher_ID",
        "Platform",
        "DOI",
        "Proprietary_ID",
        "ISBN",
        "Print_ISSN",
        "Online_ISSN",
        "URI",
        *metric_columns,
    ]


def _pairs(values):
    pairs = []
    for key, value in values.items():
        if isinstance(value, list):
            value = "|".join(value)
        pairs.append(f"{key}={value}")
    return "; ".join(pairs)


def _exceptions(values):
    result = []
    for value in values:
        exception = f"{value['Code']}: {value['Message']}"
        if value.get("Data"):
            exception += f" ({value['Data']})"
        result.append(exception)
    return "; ".join(result)
