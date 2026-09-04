from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"


class Phase9CollaborationMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_meeting_minute": {
            "global_id", "tenant_id", "project_global_id", "template_global_id",
            "template_version", "template_snapshot_hash", "title", "occurred_at",
            "attendee_user_ids", "sections", "content_hash", "created_by",
            "optimistic_version",
        },
        "npi_meeting_work_link": {
            "link_id", "tenant_id", "project_global_id", "meeting_global_id",
            "work_item_global_id", "item_key", "kind",
        },
        "npi_collaboration_idempotency": {
            "record_id", "actor", "tenant_id", "operation", "actor_key_hash",
            "payload_hash", "response_json", "response_sealed",
        },
        "npi_internal_notification": {
            "global_id", "delivery_key_hash", "tenant_id", "recipient_user_id",
            "project_global_id", "source_type", "source_global_id", "source_version",
            "notification_kind", "critical_audit", "title_source", "message_parameters",
            "target_route", "source_due_at", "email_delivery_state", "failure_code",
            "read_at", "optimistic_version",
        },
        "npi_notification_preference": {
            "global_id", "tenant_id", "user_id", "email_kinds",
            "critical_audit_email", "optimistic_version",
        },
    }

    def metadata(self, folder: str) -> dict[str, object]:
        return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))

    def test_collaboration_objects_are_closed_additive_and_non_deletable(self) -> None:
        for folder, expected_fields in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.metadata(folder)
                fields = {field["fieldname"] for field in metadata["fields"]}
                self.assertEqual(fields, expected_fields)
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["permissions"], [{
                    "role": "System Manager", "read": 1, "write": 1, "create": 1,
                    "delete": 0, "export": 0, "print": 0, "email": 0,
                }])
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
                self.assertIn("require_collaboration_write()", source)
                self.assertIn("deny_collaboration_delete()", source)
                ast.parse(source)

    def test_identity_hashes_and_links_have_database_uniqueness(self) -> None:
        for folder, fieldnames in {
            "npi_meeting_minute": {"global_id"},
            "npi_meeting_work_link": {"link_id", "work_item_global_id"},
            "npi_collaboration_idempotency": {"record_id", "actor_key_hash"},
            "npi_internal_notification": {"global_id", "delivery_key_hash"},
            "npi_notification_preference": {"global_id"},
        }.items():
            fields = {field["fieldname"]: field for field in self.metadata(folder)["fields"]}
            for fieldname in fieldnames:
                self.assertEqual(fields[fieldname].get("unique"), 1)

    def test_notification_preference_validation_keeps_translation_callable(self) -> None:
        source = (
            DOCTYPE_ROOT
            / "npi_notification_preference"
            / "npi_notification_preference.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        validate = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "validate"
        )
        assigned_names = {
            node.id
            for node in ast.walk(validate)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        self.assertNotIn("_", assigned_names)

    def test_scheduler_is_fixed_hourly_operation_without_dynamic_command(self) -> None:
        hooks = (ROOT / "apps/npi_core/npi_core/hooks.py").read_text(encoding="utf-8")
        self.assertIn('"hourly": ["npi_core.collaboration.frappe_repository.refresh_due_notifications"]', hooks)
        repository = (ROOT / "apps/npi_core/npi_core/collaboration/frappe_repository.py").read_text(encoding="utf-8")
        self.assertNotIn("frappe.enqueue", repository)
        self.assertNotIn("frappe.db." + "sql", repository)
        self.assertNotIn("ignore_permissions", repository)
        self.assertIn("MAX_NOTIFICATION_ROWS + 1", repository)
        self.assertIn("delivery_key_hash", repository)
        self.assertIn("EmailDeliveryState.FAILED", repository)
        self.assertNotIn('email_delivery_state": "sent"', repository)


if __name__ == "__main__":
    unittest.main()
