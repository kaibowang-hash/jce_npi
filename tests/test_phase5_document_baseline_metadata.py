from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
BASELINE_FRAPPE = ROOT / "apps/npi_core/npi_core/documents/baseline_frappe.py"

SYSTEM_MANAGER = {
    "role": "System Manager",
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "export": 0,
    "print": 0,
    "email": 0,
}
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
API_TRANSITION = {**API_APPEND, "write": 1}


class Phase5DocumentBaselineMetadataTest(unittest.TestCase):
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

    def test_baseline_foundation_contains_exact_separated_objects(self) -> None:
        expected = {
            "npi_document_baseline_policy": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "policy_key",
                "policy_key_hash",
                "title",
                "enabled",
                "optimistic_version",
            },
            "npi_document_baseline_policy_version": {
                "global_id",
                "document_baseline_policy",
                "tenant_id",
                "project_global_id",
                "policy_global_id",
                "policy_key",
                "policy_version",
                "version_key",
                "title",
                "publication_state",
                "baseline_authority_user_ids",
                "policy_snapshot",
                "snapshot_hash",
                "published_at",
                "optimistic_version",
            },
            "npi_document_baseline": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "label",
                "baseline_version",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "member_count",
                "baseline_snapshot",
                "snapshot_hash",
                "created_by_user_id",
                "created_at",
                "request_id",
                "trace_id",
            },
            "npi_document_baseline_member": {
                "global_id",
                "member_key",
                "document_baseline",
                "baseline_global_id",
                "baseline_snapshot_hash",
                "tenant_id",
                "project_global_id",
                "member_sequence",
                "controlled_document",
                "document_global_id",
                "document_revision",
                "revision_global_id",
                "major",
                "minor",
                "revision_snapshot_hash",
                "lifecycle_version",
                "release_event_global_id",
                "release_snapshot_hash",
                "release_evidence",
                "member_snapshot",
                "member_hash",
                "created_at",
            },
            "npi_baseline_command_idempotency": {
                "global_id",
                "receipt_key",
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "baseline_global_id",
                "response_payload",
                "response_hash",
                "sealed",
                "created_at",
                "updated_at",
            },
            "npi_baseline_gate_dependency": {
                "global_id",
                "dependency_key",
                "tenant_id",
                "project_global_id",
                "document_baseline",
                "baseline_global_id",
                "baseline_snapshot_hash",
                "input_document_global_id",
                "input_revision_global_id",
                "input_revision_snapshot_hash",
                "gate_global_id",
                "requirement_global_id",
                "requirement_key",
                "evidence_reference_global_id",
                "registered_by_user_id",
                "registered_at",
                "request_id",
                "trace_id",
                "dependency_snapshot",
                "snapshot_hash",
            },
            "npi_baseline_impact_event": {
                "global_id",
                "impact_key",
                "event_type",
                "tenant_id",
                "project_global_id",
                "dependency_global_id",
                "baseline_global_id",
                "baseline_snapshot_hash",
                "old_revision_global_id",
                "old_revision_snapshot_hash",
                "new_revision_global_id",
                "new_revision_snapshot_hash",
                "gate_global_id",
                "requirement_global_id",
                "evidence_reference_global_id",
                "initiated_by_user_id",
                "occurred_at",
                "request_id",
                "trace_id",
                "event_snapshot",
                "event_hash",
            },
        }
        for folder, fields in expected.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), fields)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)

    def test_policy_is_admin_only_and_command_history_is_guarded(self) -> None:
        for folder in (
            "npi_document_baseline_policy",
            "npi_document_baseline_policy_version",
        ):
            self.assertEqual(self.load(folder).get("permissions"), [SYSTEM_MANAGER])
        for folder in (
            "npi_document_baseline",
            "npi_document_baseline_member",
            "npi_baseline_gate_dependency",
            "npi_baseline_impact_event",
        ):
            metadata = self.load(folder)
            self.assertEqual(
                metadata.get("permissions"),
                [{**SYSTEM_MANAGER, "write": 0}, API_APPEND],
            )
            self.assertTrue(
                all(
                    field.get("read_only") == 1
                    for field in self.fields(metadata).values()
                )
            )
        self.assertEqual(
            self.load("npi_baseline_command_idempotency").get("permissions"),
            [SYSTEM_MANAGER, API_TRANSITION],
        )

    def test_enums_defaults_and_exact_links_are_closed(self) -> None:
        policy = self.fields(self.load("npi_document_baseline_policy_version"))
        receipt = self.fields(self.load("npi_baseline_command_idempotency"))
        impact = self.fields(self.load("npi_baseline_impact_event"))
        self.assertEqual(
            policy["publication_state"].get("options"),
            "draft\npublished",
        )
        self.assertEqual(receipt["operation"].get("options"), "baseline.create")
        self.assertEqual(impact["event_type"].get("options"), "invalidated")
        self.assertEqual(
            self.fields(self.load("npi_document_baseline"))["baseline_version"].get(
                "default"
            ),
            "1",
        )
        member = self.fields(self.load("npi_document_baseline_member"))
        self.assertEqual(member["document_baseline"].get("options"), "NPI Document Baseline")
        self.assertEqual(member["document_revision"].get("options"), "NPI Document Revision")

    def test_controllers_use_closed_write_flags_and_delete_guards(self) -> None:
        helper = BASELINE_FRAPPE.read_text(encoding="utf-8")
        self.assertIn("npi_document_baseline_command_write", helper)
        self.assertIn("npi_baseline_dependency_system_write", helper)
        for folder, guard in (
            ("npi_document_baseline", "require_document_baseline_command_write"),
            (
                "npi_document_baseline_member",
                "require_document_baseline_command_write",
            ),
            (
                "npi_baseline_command_idempotency",
                "require_document_baseline_command_write",
            ),
            (
                "npi_baseline_gate_dependency",
                "require_baseline_dependency_system_write",
            ),
            (
                "npi_baseline_impact_event",
                "require_baseline_dependency_system_write",
            ),
        ):
            with self.subTest(folder=folder):
                source = (
                    DOCTYPE_ROOT / folder / f"{folder}.py"
                ).read_text(encoding="utf-8")
                ast.parse(source)
                self.assertIn(guard, source)
                self.assertIn("deny_document_history_delete", source)
                self.assertNotIn("ignore_" "permissions", source)

    def test_ownership_declares_exact_future_held_boundaries(self) -> None:
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(
            encoding="utf-8"
        )
        for object_name in (
            "DocumentBaselinePolicy:",
            "DocumentBaselinePolicyVersion:",
            "DocumentBaseline:",
            "DocumentBaselineMember:",
            "BaselineCommandIdempotency:",
            "BaselineGateDependency:",
            "BaselineImpactEvent:",
        ):
            self.assertIn(object_name, ownership)
        self.assertIn("FUTURE_APPROVED_PRODUCT_POLICY", ownership)
        self.assertIn("EXPLICIT_REGISTRATION_ONLY", ownership)
        self.assertIn("EXISTING_GATE_REVIEW_CYCLE", ownership)


if __name__ == "__main__":
    unittest.main()
