import gzip
import hashlib
from pathlib import Path
from unittest.mock import Mock

from metrics.legacy_matomo import validation
from metrics.legacy_matomo.manifest import build_migration_id, validate_migration_scope
from metrics.tests.services.legacy_matomo import METRICS, LegacyManifestTestCase


class LegacyMatomoValidationTests(LegacyManifestTestCase):
    def test_validates_reconciled_manifest(self):
        result = validation.validate_manifest(self.manifest)

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["counter"]["totals"], METRICS)
        self.assertEqual(result["analytics"]["totals"], METRICS)

    def test_scl_scope_accepts_nbr_alias_through_june_2026(self):
        self.manifest["source_days"] = ["2026-06-30"]

        validate_migration_scope(self.manifest)

    def test_scl_scope_rejects_days_after_historical_cutoff(self):
        self.manifest["source_days"] = ["2026-07-01"]

        with self.assertRaisesMessage(ValueError, "limited to 2026-06-30"):
            validate_migration_scope(self.manifest)

    def test_other_article_collection_is_limited_to_2025(self):
        self.manifest["source"]["collection"] = "spa"
        self.manifest["target"]["collection"] = "spa"
        self.manifest["source_days"] = ["2026-01-01"]

        with self.assertRaisesMessage(ValueError, "limited to 2025-12-31"):
            validate_migration_scope(self.manifest)

    def test_rejects_non_article_collection(self):
        self.manifest["source"]["collection"] = "books"
        self.manifest["target"]["collection"] = "books"

        with self.assertRaisesMessage(ValueError, "not supported"):
            validate_migration_scope(self.manifest)

    def test_rejects_undeclared_collection_alias(self):
        self.manifest["source"]["collection"] = "old-spa"
        self.manifest["target"]["collection"] = "spa"

        with self.assertRaisesMessage(ValueError, "old-spa -> spa"):
            validate_migration_scope(self.manifest)

    def test_rejects_unknown_metric_profile(self):
        self.manifest["metric_profile"] = "books"

        with self.assertRaisesMessage(ValueError, "metric profile"):
            validate_migration_scope(self.manifest)

    def test_migration_identity_includes_payload_hash(self):
        migration_id = build_migration_id(self.manifest, "counter")

        self.assertIn(self.manifest["counter"]["uncompressed_sha256"], migration_id)

    def test_rejects_manifest_without_source_days(self):
        self.manifest["source_days"] = []

        with self.assertRaisesMessage(ValueError, "no source days"):
            validation.validate_manifest(self.manifest)

    def test_rejects_duplicate_empty_days(self):
        self.manifest["empty_days"] = ["2025-08-02", "2025-08-02"]

        with self.assertRaisesMessage(ValueError, "empty days must be unique"):
            validation.validate_manifest(self.manifest)

    def test_rejects_duplicate_payload_ids(self):
        path = Path(self.manifest["counter"]["path"])
        with gzip.open(path, "rb") as source:
            line = source.read()
        with gzip.GzipFile(filename=path, mode="wb", mtime=0) as output:
            output.write(line)
            output.write(line)
        self.manifest["counter"]["documents"] = 2
        self.manifest["counter"]["totals"] = {
            key: value * 2 for key, value in METRICS.items()
        }
        self.manifest["counter"]["uncompressed_sha256"] = hashlib.sha256(
            line + line
        ).hexdigest()

        with self.assertRaisesMessage(ValueError, "duplicate _id"):
            validation.validate_manifest(self.manifest)

    def test_validation_reports_progress_and_uses_requested_temporary_directory(self):
        temporary_directory = Path(self.temporary_directory.name) / "work"
        temporary_directory.mkdir()
        progress = []

        validation.validate_manifest(
            self.manifest,
            temporary_directory=temporary_directory,
            progress_callback=lambda dataset, stage, documents: progress.append(
                (dataset, stage, documents)
            ),
            progress_interval=1,
        )

        self.assertEqual(
            progress,
            [
                ("counter", "validation", 1),
                ("analytics", "validation", 1),
            ],
        )
        self.assertEqual(list(temporary_directory.iterdir()), [])

    def test_validation_honors_stop_request(self):
        stop_controller = Mock()
        stop_controller.raise_if_requested.side_effect = RuntimeError(
            "interruption requested"
        )

        with self.assertRaisesMessage(RuntimeError, "interruption requested"):
            validation.validate_manifest(
                self.manifest,
                progress_interval=1,
                stop_controller=stop_controller,
            )
