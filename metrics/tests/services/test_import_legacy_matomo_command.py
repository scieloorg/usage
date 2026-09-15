import json
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command

from metrics.legacy_matomo.operations import (
    validate_report_destination,
    write_json_atomic,
)
from metrics.tests.services.legacy_matomo import LegacyManifestTestCase


class ImportLegacyMatomoCommandTests(LegacyManifestTestCase):
    def test_writes_report_atomically(self):
        report_path = Path(self.temporary_directory.name) / "reports" / "result.json"

        write_json_atomic(report_path, {"status": "completed"})

        with open(report_path, encoding="utf-8") as source:
            self.assertEqual(json.load(source), {"status": "completed"})
        self.assertEqual(list(report_path.parent.glob("*.tmp")), [])

    def test_rejects_report_that_would_overwrite_an_input(self):
        input_path = Path(self.manifest["counter"]["path"])

        with self.assertRaisesMessage(ValueError, "overwrite"):
            validate_report_destination(input_path, [input_path])

    def test_management_command_writes_validation_report(self):
        root = Path(self.temporary_directory.name)
        manifest_path = root / "manifest.json"
        report_path = root / "report.json"
        work_path = root / "work"
        work_path.mkdir()
        with open(manifest_path, "w", encoding="utf-8") as output:
            json.dump(self.manifest, output)

        call_command(
            "import_legacy_matomo",
            manifest=str(manifest_path),
            report=str(report_path),
            temporary_directory=str(work_path),
            progress_every=1,
            stdout=StringIO(),
        )

        with open(report_path, encoding="utf-8") as source:
            report = json.load(source)
        self.assertEqual(report["status"], "validated")
        self.assertEqual(report["collection"], "scl")

    def test_management_command_does_not_overwrite_manifest_with_report(self):
        manifest_path = Path(self.temporary_directory.name) / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as output:
            json.dump(self.manifest, output)
        original = manifest_path.read_bytes()

        with self.assertRaisesMessage(CommandError, "overwrite"):
            call_command(
                "import_legacy_matomo",
                manifest=str(manifest_path),
                report=str(manifest_path),
                stdout=StringIO(),
            )

        self.assertEqual(manifest_path.read_bytes(), original)
