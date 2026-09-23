import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from collection.models import Collection
from counter_api.dates import iter_months
from metrics.legacy_matomo.manifest import load_manifest
from metrics.models import DailyMetricJob
from metrics.opensearch.client import OpenSearchUsageClient
from metrics.opensearch.month_status import replace_month_status


class Command(BaseCommand):
    help = "Rebuild monthly COUNTER availability from jobs or migration reports."

    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--collection")
        source.add_argument("--report", nargs="+")
        parser.add_argument("--start-month")
        parser.add_argument("--end-month")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        client = OpenSearchUsageClient() if options["apply"] else None

        try:
            if options["report"]:
                if options["start_month"] or options["end_month"]:
                    raise CommandError("month arguments cannot be used with reports")

                self._from_reports(options["report"], client)
                return

            if not options["start_month"] or not options["end_month"]:
                raise CommandError("start-month and end-month are required")

            self._from_jobs(
                options["collection"],
                options["start_month"],
                options["end_month"],
                client,
            )
        except CommandError:
            raise
        except (
            OSError,
            Collection.DoesNotExist,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise CommandError(str(exc)) from exc

    def _from_jobs(self, acronym, start_value, end_value, client):
        try:
            start = date.fromisoformat(f"{start_value}-01")
            end = date.fromisoformat(f"{end_value}-01")
        except ValueError as exc:
            raise CommandError("months must use YYYY-MM") from exc

        if start > end:
            raise CommandError("start-month must not be later than end-month")

        if end.month == 12:
            following_month = date(end.year + 1, 1, 1)
        else:
            following_month = date(end.year, end.month + 1, 1)

        collection = Collection.objects.get(acron3=acronym)
        exported_days = DailyMetricJob.objects.filter(
            collection=collection,
            status=DailyMetricJob.STATUS_EXPORTED,
            access_date__gte=start,
            access_date__lt=following_month,
        ).values_list("access_date", flat=True)
        masks = {}

        for access_date in exported_days:
            month = access_date.replace(day=1)
            masks[month] = masks.get(month, 0) | (1 << (access_date.day - 1))

        for month in iter_months(start, end):
            self._write_status(
                client,
                collection.acron3,
                month,
                masks.get(month, 0),
            )

    def _from_reports(self, paths, client):
        for path in paths:
            with open(path, encoding="utf-8") as source:
                report = json.load(source)

            if report.get("status") != "completed":
                raise CommandError(f"migration report is not completed: {path}")
            if report.get("validation", {}).get("status") not in {"valid", "partial"}:
                raise CommandError(f"migration report is not valid: {path}")

            for dataset in ("counter", "analytics"):
                expected = report["validation"][dataset]["documents"]
                if report["imported"][dataset] != expected:
                    raise CommandError(f"migration report is incomplete: {path}")

            manifest = load_manifest(report["manifest"])
            collection = manifest["target"]["collection"]
            month = date.fromisoformat(f"{manifest['month']}-01")
            if report.get("collection") != collection:
                raise CommandError(f"collection differs from manifest: {path}")
            if report.get("month") != manifest["month"]:
                raise CommandError(f"month differs from manifest: {path}")

            days = manifest["source_days"] + manifest.get("empty_days", [])
            day_mask = 0
            for value in days:
                access_date = date.fromisoformat(value)
                if access_date.replace(day=1) != month:
                    raise CommandError(f"day outside manifest month: {path}")
                day_mask |= 1 << (access_date.day - 1)

            self._write_status(client, collection, month, day_mask)

    def _write_status(self, client, collection, month, day_mask):
        if client:
            replace_month_status(client, collection, month, day_mask)

        self.stdout.write(f"{collection} {month:%Y-%m} days={day_mask.bit_count()}")
