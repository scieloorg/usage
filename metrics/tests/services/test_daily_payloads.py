import hashlib
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from metrics.services import daily_payloads


class DailyPayloadTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temporary_directory.name
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_directory.cleanup()

    def test_incremental_writer_preserves_canonical_bytes_and_hash(self):
        storage_path = Path("scl/2026/08/2026-08-25.json")
        payload = {
            "access_date": "2026-08-25",
            "collection": "scl",
            "documents": {
                "counter": {"á": {"total_requests": 2}},
                "analytics": {"z": {"total_requests": 3}},
            },
            "input_log_hashes": ["abc"],
            "summary": {"valid_lines": 1},
        }
        expected = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=False,
            separators=(",", ":"),
        ).encode("utf-8")

        with daily_payloads.DailyPayloadWriter(
            storage_path,
            payload["collection"],
            payload["access_date"],
        ) as writer:
            writer.write_document_items(
                "counter", sorted(payload["documents"]["counter"].items())
            )
            writer.write_document_items(
                "analytics", sorted(payload["documents"]["analytics"].items())
            )
            payload_hash = writer.finalize(
                payload["input_log_hashes"],
                payload["summary"],
            )

        resolved_path = daily_payloads.resolve_storage_path(storage_path)
        self.assertEqual(resolved_path.read_bytes(), expected)
        self.assertEqual(payload_hash, hashlib.sha256(expected).hexdigest())

    def test_iter_document_items_reads_each_granularity_incrementally(self):
        storage_path = Path("scl/2026/08/2026-08-25.json")
        payload = {
            "collection": "scl",
            "access_date": "2026-08-25",
            "input_log_hashes": ["abc"],
            "documents": {
                "counter": {"month-1": {"total_requests": 2}},
                "analytics": {"analytics-1": {"total_requests": 3}},
            },
            "summary": {},
        }
        with daily_payloads.DailyPayloadWriter(
            storage_path,
            payload["collection"],
            payload["access_date"],
        ) as writer:
            writer.write_document_items(
                "counter", payload["documents"]["counter"].items()
            )
            writer.write_document_items(
                "analytics", payload["documents"]["analytics"].items()
            )
            writer.finalize(payload["input_log_hashes"], payload["summary"])

        self.assertEqual(
            list(daily_payloads.iter_document_items(storage_path, "counter")),
            [("month-1", {"total_requests": 2})],
        )
        self.assertEqual(
            list(daily_payloads.iter_document_items(storage_path, "analytics")),
            [("analytics-1", {"total_requests": 3})],
        )

    def test_incremental_writer_removes_temporary_file_after_error(self):
        storage_path = Path("scl/2026/08/2026-08-25.json")
        resolved_path = daily_payloads.resolve_storage_path(storage_path)
        resolved_path.parent.mkdir(parents=True)
        resolved_path.write_bytes(b"previous canonical payload")

        with self.assertRaises(TypeError):
            with daily_payloads.DailyPayloadWriter(
                storage_path,
                "scl",
                "2026-08-25",
            ) as writer:
                writer.write_document_items("counter", iter(()))
                writer.write_document_items("analytics", [("invalid", object())])

        self.assertEqual(resolved_path.read_bytes(), b"previous canonical payload")
        self.assertFalse(resolved_path.with_suffix(".json.tmp").exists())

    def test_document_item_order_produces_deterministic_payload(self):
        hashes = []
        contents = []

        for filename in ("first.json", "second.json"):
            storage_path = Path("scl/2026/08") / filename
            with daily_payloads.DailyPayloadWriter(
                storage_path,
                "scl",
                "2026-08-25",
            ) as writer:
                writer.write_document_items(
                    "counter",
                    [("b", {"total": 2}), ("a", {"total": 1})],
                )
                writer.write_document_items("analytics", [("c", {"total": 3})])
                hashes.append(writer.finalize(["abc"], {"valid_lines": 1}))
            contents.append(
                daily_payloads.resolve_storage_path(storage_path).read_bytes()
            )

        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(contents[0], contents[1])
