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
            "collection": "scl",
            "access_date": "2026-08-25",
            "input_log_hashes": ["abc"],
            "documents": {
                "month": {"á": {"total_requests": 2}},
                "year": {"z": {"total_requests": 3}},
            },
            "summary": {"valid_lines": 1},
        }
        expected = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        with daily_payloads.DailyPayloadWriter(
            storage_path,
            payload["collection"],
            payload["access_date"],
        ) as writer:
            writer.write_document_items(
                "month", sorted(payload["documents"]["month"].items())
            )
            writer.write_document_items(
                "year", sorted(payload["documents"]["year"].items())
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
                "month": {"month-1": {"total_requests": 2}},
                "year": {"year-1": {"total_requests": 3}},
            },
            "summary": {},
        }
        with daily_payloads.DailyPayloadWriter(
            storage_path,
            payload["collection"],
            payload["access_date"],
        ) as writer:
            writer.write_document_items("month", payload["documents"]["month"].items())
            writer.write_document_items("year", payload["documents"]["year"].items())
            writer.finalize(payload["input_log_hashes"], payload["summary"])

        self.assertEqual(
            list(daily_payloads.iter_document_items(storage_path, "month")),
            [("month-1", {"total_requests": 2})],
        )
        self.assertEqual(
            list(daily_payloads.iter_document_items(storage_path, "year")),
            [("year-1", {"total_requests": 3})],
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
                writer.write_document_items("month", iter(()))
                writer.write_document_items("year", [("invalid", object())])

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
                    "month",
                    [("b", {"total": 2}), ("a", {"total": 1})],
                )
                writer.write_document_items("year", [("c", {"total": 3})])
                hashes.append(writer.finalize(["abc"], {"valid_lines": 1}))
            contents.append(
                daily_payloads.resolve_storage_path(storage_path).read_bytes()
            )

        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(contents[0], contents[1])
