import json
from datetime import datetime, timezone
from time import monotonic

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from collection.models import Collection
from metrics.legacy_matomo.importer import build_import_plan, import_manifest
from metrics.legacy_matomo.manifest import load_manifest
from metrics.legacy_matomo.operations import (
    MigrationInterrupted,
    StopController,
    validate_report_destination,
    write_json_atomic,
)
from metrics.legacy_matomo.validation import validate_manifest
from metrics.opensearch.client import OpenSearchUsageClient


class Command(BaseCommand):
    help = "Validate or import a legacy Matomo migration manifest."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--preflight", action="store_true")
        mode.add_argument("--execute", action="store_true")
        parser.add_argument("--report")
        parser.add_argument("--temporary-directory")
        parser.add_argument("--progress-every", type=int, default=100000)
        parser.add_argument("--allow-partial", action="store_true")

    def _progress(self, dataset, stage, documents):
        self.stdout.write("[%s] %s: %d documents" % (stage, dataset, documents))
        self.stdout.flush()

    def _finish_report(self, report, path, status, started, error=None):
        report["status"] = status
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["duration_seconds"] = round(monotonic() - started, 3)
        if error:
            report["error"] = str(error)
        if path:
            write_json_atomic(path, report)

    def handle(self, *args, **options):
        started = monotonic()
        report = {
            "manifest": options["manifest"],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        report_path = None
        stop_controller = StopController()
        stop_controller.install()

        try:
            manifest = load_manifest(options["manifest"])
            validate_report_destination(
                options["report"],
                [
                    options["manifest"],
                    manifest["counter"]["path"],
                    manifest["analytics"]["path"],
                ],
            )
            report_path = options["report"]
            report["collection"] = manifest.get("target", {}).get("collection")
            report["month"] = manifest.get("month")
            validation = validate_manifest(
                manifest,
                temporary_directory=options["temporary_directory"],
                progress_callback=self._progress,
                progress_interval=options["progress_every"],
                stop_controller=stop_controller,
                allow_partial=options["allow_partial"],
            )
            report["validation"] = validation

            if not options["preflight"] and not options["execute"]:
                self.stdout.write(json.dumps(validation, indent=2, sort_keys=True))
                self.stdout.write(
                    self.style.SUCCESS(
                        "Dry-run validation completed; nothing imported."
                    )
                )
                self._finish_report(
                    report,
                    report_path,
                    "validated",
                    started,
                )
                return

            collection = Collection.objects.get(acron3=manifest["target"]["collection"])
            search_client = OpenSearchUsageClient()
            if not search_client.ping():
                raise ValueError("OpenSearch preflight ping failed.")
            plan = build_import_plan(search_client, collection, manifest)
            report["plan"] = plan
            if not options["execute"]:
                self.stdout.write(
                    json.dumps(
                        {"validation": validation, "plan": plan},
                        indent=2,
                        sort_keys=True,
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        "Read-only preflight completed; nothing imported."
                    )
                )
                self._finish_report(
                    report,
                    report_path,
                    "preflight-completed",
                    started,
                )
                return
            imported = import_manifest(
                search_client,
                collection,
                manifest,
                progress_callback=self._progress,
                progress_interval=options["progress_every"],
                stop_controller=stop_controller,
            )
            report["imported"] = imported
            self._finish_report(
                report,
                report_path,
                "completed",
                started,
            )
        except MigrationInterrupted as exc:
            self._finish_report(
                report,
                report_path,
                "stopped",
                started,
                error=exc,
            )
            raise CommandError(str(exc)) from exc
        except (
            OSError,
            Collection.DoesNotExist,
            ObjectDoesNotExist,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            self._finish_report(
                report,
                report_path,
                "failed",
                started,
                error=exc,
            )
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            self._finish_report(
                report,
                report_path,
                "failed",
                started,
                error=exc,
            )
            raise
        finally:
            stop_controller.restore()

        self.stdout.write(json.dumps(imported, indent=2, sort_keys=True))
        self.stdout.write(self.style.SUCCESS("Historical Matomo import completed."))
