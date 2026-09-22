import csv
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

    output = SpooledTemporaryFile(max_size=SPOOL_SIZE)
    if output_format == "csv":
        line = StringIO(newline="")
        writer = csv.writer(line, lineterminator="\n")
        writer.writerow(headings)
        output.write(line.getvalue().encode("utf-8"))
        line.seek(0)
        line.truncate(0)

        for row in rows:
            writer.writerow(row)
            output.write(line.getvalue().encode("utf-8"))
            line.seek(0)
            line.truncate(0)
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

        workbook.save(output)

    output.seek(0)
    return output
