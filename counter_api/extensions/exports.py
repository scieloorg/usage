import csv
import json
from io import StringIO
from tempfile import SpooledTemporaryFile

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

from counter_api.constants import EXCEL_MAX_ROWS, SPOOL_SIZE
from counter_api.exceptions import insufficient_information


def build_export(payload, kind, output_format):
    if kind == "ranking":
        headings = ["Country", "Language", "Rank", "ID", "Title", "Count"]
        rows = (
            [
                group["dimensions"].get("country", ""),
                group["dimensions"].get("language", ""),
                rank,
                item["id"],
                item["title"],
                item["count"],
            ]
            for group in payload["groups"]
            for rank, item in enumerate(group["items"], start=1)
        )
    else:
        dimensions = payload.get("dimensions") or [payload["dimension"]]
        headings = [dimension.replace("_", " ").title() for dimension in dimensions]
        headings.append("Count")
        rows = (
            [
                bucket.get("dimensions", {}).get(dimension, "")
                for dimension in dimensions
            ]
            + [bucket["count"]]
            for bucket in payload["buckets"]
        )

    metadata = None
    if "coverage" in payload:
        metadata = [
            json.dumps(payload["coverage"], separators=(",", ":")),
            json.dumps(payload["warnings"]),
            payload.get("total", ""),
        ]
        if output_format == "csv":
            headings.extend(["Coverage", "Warnings", "Total"])
            rows = (row + metadata for row in rows)

    output = SpooledTemporaryFile(max_size=SPOOL_SIZE)
    if output_format == "csv":
        line = StringIO(newline="")
        writer = csv.writer(line, lineterminator="\n")
        writer.writerow(headings)
        output.write(line.getvalue().encode("utf-8"))
        line.seek(0)
        line.truncate(0)

        has_rows = False
        for row in rows:
            has_rows = True
            writer.writerow(row)
            output.write(line.getvalue().encode("utf-8"))
            line.seek(0)
            line.truncate(0)

        if metadata is not None and not has_rows:
            writer.writerow([""] * (len(headings) - len(metadata)) + metadata)
            output.write(line.getvalue().encode("utf-8"))
    else:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title=kind.capitalize())
        heading = []
        for label in headings:
            cell = WriteOnlyCell(sheet, value=label)
            cell.font = Font(bold=True)
            heading.append(cell)
        sheet.append(heading)

        for row_number, row in enumerate(rows, start=2):
            if row_number > EXCEL_MAX_ROWS:
                workbook.close()
                output.close()
                raise insufficient_information()
            sheet.append(row)

        if metadata is not None:
            coverage_sheet = workbook.create_sheet(title="Coverage")
            coverage_sheet.append(["Coverage", "Warnings", "Total"])
            coverage_sheet.append(metadata)

        workbook.save(output)

    output.seek(0)
    return output
