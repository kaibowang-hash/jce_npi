from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = (
    ROOT
    / "apps/npi_integration/npi_integration/npi_integration/doctype"
    / "npi_item_publish_stream_guard"
)


class Phase8ItemPublishStreamGuardTest(unittest.TestCase):
    def test_guard_is_a_permanent_read_only_source_stream_anchor(self) -> None:
        metadata = json.loads(
            (GUARD / "npi_item_publish_stream_guard.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["autoname"], "field:source_stream_key_hash")
        self.assertEqual(metadata["allow_rename"], 0)
        self.assertEqual(metadata["read_only"], 1)
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        self.assertTrue(fields["source_stream_key_hash"]["unique"])
        for fieldname in (
            "tenant_id",
            "project_global_id",
            "engineering_item_id",
            "active_request_global_id",
            "active_target_idempotency_key_hash",
            "active_state",
            "last_request_global_id",
            "last_target_idempotency_key_hash",
            "last_state",
            "blocked_reason_code",
            "optimistic_version",
            "updated_at",
        ):
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname].get("read_only"), 1)
        for permission in metadata["permissions"]:
            self.assertFalse(permission.get("write", 0))
            self.assertFalse(permission.get("create", 0))
            self.assertFalse(permission.get("delete", 0))

    def test_guard_controller_recomputes_identity_and_rejects_unscoped_mutation(self) -> None:
        source = (GUARD / "npi_item_publish_stream_guard.py").read_text(encoding="utf-8")
        ast.parse(source)
        for marker in (
            "require_item_stream_guard_write()",
            "deny_item_history_delete()",
            "assert_immutable_fields(",
            "expected_hash = canonical_hash(",
            "_validate_binding(",
            "optimistic_version",
            "source_stream_key_hash",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
