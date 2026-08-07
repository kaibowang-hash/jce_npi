from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
VALIDATION = ROOT / "apps/npi_core/npi_core/controlled_print/frappe_validation.py"

SYSTEM_MANAGER_ADMIN = {
    "role": "System Manager",
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "export": 0,
    "print": 0,
    "email": 0,
}
SYSTEM_MANAGER_APPEND = {**SYSTEM_MANAGER_ADMIN, "write": 0}
API_APPEND = {
    "role": "NPI API User",
    "read": 0,
    "write": 0,
    "create": 1,
    "delete": 0,
    "export": 0,
    "print": 0,
    "email": 0,
}


class Phase5ControlledPrintMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_controlled_print_registry": {
            "global_id", "tenant_id", "registry_key", "registry_key_hash",
            "title", "enabled", "optimistic_version",
        },
        "npi_controlled_print_registry_version": {
            "global_id", "print_registry", "tenant_id", "registry_global_id",
            "mapping_key", "mapping_version", "version_key", "title",
            "publication_state", "source_object_type", "project_type_key",
            "gate_key", "source_state", "language", "delivery_mode",
            "copy_state", "print_format_name", "template_content",
            "template_sha256", "watermark_source", "printer_user_ids",
            "effective_from", "effective_to", "mapping_snapshot",
            "snapshot_hash", "published_at", "optimistic_version",
        },
        "npi_controlled_print_snapshot": {
            "global_id", "tenant_id", "project_global_id", "project_type_key",
            "gate_key", "source_object_type", "source_global_id",
            "source_version", "source_state", "source_snapshot",
            "source_snapshot_hash", "mapping_global_id", "registry_global_id",
            "mapping_version", "mapping_snapshot_hash", "template_sha256",
            "language", "delivery_mode", "copy_state", "watermark_source",
            "actor_user_id", "printed_at", "request_id", "trace_id",
            "snapshot_version", "snapshot", "snapshot_hash",
            "verification_payload",
        },
        "npi_controlled_print_output": {
            "global_id", "tenant_id", "project_global_id",
            "controlled_print_snapshot", "snapshot_global_id",
            "frappe_file_id", "file_name", "mime_type", "size_bytes",
            "frappe_content_hash", "sha256", "created_by_user_id",
            "created_at", "output_snapshot", "record_hash",
        },
        "npi_controlled_print_access_event": {
            "global_id", "tenant_id", "project_global_id",
            "controlled_print_snapshot", "snapshot_global_id",
            "controlled_print_output", "output_global_id", "event_type",
            "actor_user_id", "occurred_at", "trace_id", "event_snapshot",
            "event_hash",
        },
        "npi_controlled_print_command_idempotency": {
            "global_id", "receipt_key", "tenant_id", "project_global_id",
            "actor_user_id", "operation", "idempotency_key_hash",
            "payload_hash", "snapshot_global_id", "response_payload",
            "response_hash", "sealed", "created_at", "updated_at",
        },
    }

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            field["fieldname"]: field
            for field in metadata["fields"]  # type: ignore[index]
        }

    def test_additive_foundation_contains_only_exact_objects_and_fields(self) -> None:
        for folder, expected in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), expected)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)

    def test_no_mapping_or_format_is_enabled_or_seeded(self) -> None:
        registry = self.fields(self.load("npi_controlled_print_registry"))
        self.assertEqual(registry["enabled"].get("default"), "0")
        version = self.fields(self.load("npi_controlled_print_registry_version"))
        self.assertEqual(version["publication_state"].get("default"), "draft")
        self.assertNotIn("default", version["print_format_name"])
        self.assertNotIn("default", version["template_content"])
        self.assertNotIn("default", version["watermark_source"])
        self.assertEqual(version["delivery_mode"].get("options"), "controlled_pdf")
        self.assertEqual(version["copy_state"].get("options"), "not_numbered")
        serialized = json.dumps(
            [self.load(folder) for folder in self.FIELDS], sort_keys=True
        ).casefold()
        for forbidden in (
            "https://", "http://", "browser_print", "copy_1", "credential",
            "secret", "signature", "wet signature",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_registry_is_admin_only_and_history_is_append_only(self) -> None:
        for folder in (
            "npi_controlled_print_registry",
            "npi_controlled_print_registry_version",
        ):
            self.assertEqual(self.load(folder).get("permissions"), [SYSTEM_MANAGER_ADMIN])
        for folder in (
            "npi_controlled_print_snapshot",
            "npi_controlled_print_output",
            "npi_controlled_print_access_event",
        ):
            metadata = self.load(folder)
            self.assertEqual(metadata.get("permissions"), [SYSTEM_MANAGER_APPEND, API_APPEND])
            self.assertEqual(metadata.get("read_only"), 1)
            self.assertTrue(
                all(field.get("read_only") == 1 for field in self.fields(metadata).values())
            )
        receipt = self.load("npi_controlled_print_command_idempotency")
        self.assertEqual(
            receipt.get("permissions"),
            [SYSTEM_MANAGER_ADMIN, {**API_APPEND, "write": 1}],
        )

    def test_private_output_identity_is_server_owned_and_url_free(self) -> None:
        output = self.fields(self.load("npi_controlled_print_output"))
        for fieldname in (
            "frappe_file_id", "file_name", "mime_type", "size_bytes",
            "frappe_content_hash", "sha256", "output_snapshot", "record_hash",
        ):
            self.assertEqual(output[fieldname].get("read_only"), 1)
        all_fields = {field for fields in self.FIELDS.values() for field in fields}
        self.assertNotIn("file_url", all_fields)
        self.assertNotIn("template_url", all_fields)
        self.assertNotIn("raw_idempotency_key", all_fields)

    def test_controllers_use_closed_write_flags_and_delete_guards(self) -> None:
        helper = VALIDATION.read_text(encoding="utf-8")
        ast.parse(helper)
        for marker in (
            "npi_controlled_print_registry_write",
            "npi_controlled_print_command_write",
            "deny_document_history_delete",
            "require_immutable_or_receipt_seal",
            "require_exact_parent",
        ):
            self.assertIn(marker, helper)
        for exact_parent in (
            '"NPI Engineering Project"',
            '"NPI Controlled Print Registry"',
            '"NPI Controlled Print Registry Version"',
            '"NPI Controlled Print Snapshot"',
            '"NPI Controlled Print Output"',
            '"File"',
        ):
            self.assertIn(exact_parent, helper)
        for private_file_field in (
            '"is_private": 1',
            '"content_hash": document.frappe_content_hash',
            '"file_size": document.size_bytes',
            '"/private/files/"',
        ):
            self.assertIn(private_file_field, helper)
        self.assertNotIn('"is_remote_file": 0', helper)
        for folder in self.FIELDS:
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            with self.subTest(folder=folder):
                ast.parse(source)
                self.assertIn("deny_controlled_print_history_delete", source)
                self.assertIn("require_controlled_print_", source)
                self.assertNotIn("ignore_" "permissions", source)
                self.assertNotIn("frappe.db." "sql", source)
                self.assertNotIn("tuple(self.as_dict())", source)
        for folder in (
            "npi_controlled_print_snapshot",
            "npi_controlled_print_output",
            "npi_controlled_print_access_event",
        ):
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("_IMMUTABLE_FIELDS", source)

    def test_snapshot_validation_serializes_only_thawed_source_payload(self) -> None:
        helper = VALIDATION.read_text(encoding="utf-8")

        self.assertIn(
            'value.snapshot_payload()["sourceSnapshot"]',
            helper,
        )
        self.assertNotIn("canonical_json(value.source_snapshot)", helper)


if __name__ == "__main__":
    unittest.main()
