from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrappeMetadataTest(unittest.TestCase):
    def load(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_apps_are_independent_and_in_dependency_order(self) -> None:
        core_hooks = (ROOT / "apps/npi_core/npi_core/hooks.py").read_text(encoding="utf-8")
        integration_hooks = (ROOT / "apps/npi_integration/npi_integration/hooks.py").read_text(encoding="utf-8")
        self.assertIn('app_name = "npi_core"', core_hooks)
        self.assertIn('app_name = "npi_integration"', integration_hooks)
        self.assertIn('required_apps = ["npi_core"]', integration_hooks)

    def test_audit_is_append_only_for_business_roles(self) -> None:
        audit = self.load("apps/npi_core/npi_core/npi_core/doctype/npi_audit_event/npi_audit_event.json")
        self.assertEqual(audit["read_only"], 1)
        expected = [{"role": "System Manager", "read": 1, "create": 1, "export": 0, "print": 0, "email": 0}]
        self.assertEqual(audit["permissions"], expected)
        fields = {field["fieldname"]: field for field in audit["fields"]}
        self.assertEqual(fields["event_id"]["unique"], 1)
        self.assertEqual(fields["trace_id"]["reqd"], 1)
        controller = (ROOT / "apps/npi_core/npi_core/npi_core/doctype/npi_audit_event/npi_audit_event.py").read_text(encoding="utf-8")
        self.assertIn('getattr(frappe.flags, "npi_audit_append", False)', controller)

    def test_message_ids_are_unique_and_never_default_to_success(self) -> None:
        paths = (
            "apps/npi_integration/npi_integration/npi_integration/doctype/npi_outbox_message/npi_outbox_message.json",
            "apps/npi_integration/npi_integration/npi_integration/doctype/npi_inbox_message/npi_inbox_message.json",
        )
        for relative in paths:
            metadata = self.load(relative)
            fields = {field["fieldname"]: field for field in metadata["fields"]}
            self.assertEqual(fields["event_id"]["unique"], 1)
            self.assertEqual(fields["state"]["reqd"], 1)
            self.assertNotEqual(fields["state"].get("default"), "succeeded")
            self.assertEqual(metadata["permissions"], [{"role": "System Manager", "read": 1}])

    def test_file_integrity_fields_are_server_read_only(self) -> None:
        metadata = self.load("apps/npi_core/npi_core/npi_core/doctype/npi_file_revision/npi_file_revision.json")
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        self.assertEqual(fields["sha256"]["read_only"], 1)
        self.assertEqual(fields["scan_state"]["read_only"], 1)
        self.assertEqual(fields["released"]["read_only"], 1)
