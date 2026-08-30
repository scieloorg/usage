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

    def test_write_payload_preserves_canonical_bytes_and_hash(self):
        payload = {
            "collection": "scl",
            "documents": {"á": {"total_requests": 2}},
            "summary": {"valid_lines": 1},
        }
        expected = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        payload_hash = daily_payloads.write_payload(
            Path("scl/2026/08/2026-08-25.json"),
            payload,
        )

        resolved_path = daily_payloads.resolve_storage_path(
            Path("scl/2026/08/2026-08-25.json")
        )
        self.assertEqual(resolved_path.read_bytes(), expected)
        self.assertEqual(payload_hash, hashlib.sha256(expected).hexdigest())

    def test_write_payload_removes_temporary_file_after_serialization_error(self):
        storage_path = Path("scl/2026/08/2026-08-25.json")

        with self.assertRaises(TypeError):
            daily_payloads.write_payload(storage_path, {"invalid": object()})

        resolved_path = daily_payloads.resolve_storage_path(storage_path)
        self.assertFalse(resolved_path.exists())
        self.assertFalse(resolved_path.with_suffix(".json.tmp").exists())
