from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
EBOM_DOMAIN = ROOT / "apps/npi_core/npi_core/ebom/domain.py"
EBOM_VALIDATION = ROOT / "apps/npi_core/npi_core/ebom/frappe_validation.py"

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


class Phase5EngineeringBomMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_ebom_policy": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "policy_key",
            "policy_key_hash",
            "title",
            "enabled",
            "optimistic_version",
        },
        "npi_ebom_policy_version": {
            "global_id",
            "ebom_policy",
            "tenant_id",
            "project_global_id",
            "policy_global_id",
            "policy_key",
            "policy_version",
            "version_key",
            "title",
            "publication_state",
            "synthetic_namespace",
            "line_identity_mode",
            "quantity_scale",
            "maximum_nodes",
            "engineering_uoms",
            "attribute_keys",
            "creator_user_ids",
            "review_submitter_user_ids",
            "reviewer_user_ids",
            "release_authority_user_ids",
            "require_acyclic_graph",
            "require_closed_alternates",
            "require_effectivity_order",
            "policy_snapshot",
            "snapshot_hash",
            "published_at",
            "optimistic_version",
        },
        "npi_engineering_bom": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "engineering_bom_key",
            "engineering_bom_key_hash",
            "title",
            "policy_global_id",
            "policy_version",
            "policy_snapshot_hash",
            "latest_revision_global_id",
            "latest_revision_number",
            "latest_revision_snapshot_hash",
            "optimistic_version",
        },
        "npi_engineering_bom_revision": {
            "global_id",
            "engineering_bom",
            "ebom_global_id",
            "tenant_id",
            "project_global_id",
            "engineering_bom_key",
            "revision_number",
            "revision_key",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "reason",
            "effectivity_note",
            "policy_global_id",
            "policy_version",
            "policy_snapshot_hash",
            "quantity_scale",
            "line_count",
            "revision_snapshot",
            "snapshot_hash",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
        },
        "npi_engineering_bom_line": {
            "global_id",
            "line_identity_key",
            "engineering_bom",
            "ebom_global_id",
            "engineering_bom_revision",
            "revision_global_id",
            "revision_snapshot_hash",
            "tenant_id",
            "project_global_id",
            "line_key",
            "parent_line_key",
            "engineering_item_id",
            "description",
            "quantity",
            "engineering_uom",
            "alternate_for_line_key",
            "alternate_group_key",
            "effectivity_start",
            "effectivity_end",
            "attributes",
            "line_snapshot",
            "line_hash",
            "created_at",
        },
        "npi_ebom_revision_lifecycle": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "engineering_bom",
            "ebom_global_id",
            "engineering_bom_revision",
            "revision_global_id",
            "revision_snapshot_hash",
            "current_state",
            "lifecycle_version",
            "last_event_global_id",
            "updated_by_user_id",
            "updated_at",
            "request_id",
            "trace_id",
        },
        "npi_ebom_lifecycle_event": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "engineering_bom",
            "ebom_global_id",
            "engineering_bom_revision",
            "revision_global_id",
            "revision_snapshot_hash",
            "policy_global_id",
            "policy_version",
            "policy_snapshot_hash",
            "event_type",
            "from_state",
            "to_state",
            "from_version",
            "to_version",
            "actor_user_id",
            "authority_action",
            "decision",
            "reason",
            "confirmation_intent",
            "occurred_at",
            "request_id",
            "trace_id",
            "event_snapshot",
            "event_hash",
        },
        "npi_ebom_command_idempotency": {
            "global_id",
            "receipt_key",
            "tenant_id",
            "project_global_id",
            "actor_user_id",
            "operation",
            "idempotency_key_hash",
            "payload_hash",
            "ebom_global_id",
            "revision_global_id",
            "response_payload",
            "response_hash",
            "sealed",
            "created_at",
            "updated_at",
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

    def test_foundation_contains_exact_separated_objects_and_fields(self) -> None:
        for folder, expected in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), expected)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)

    def test_policy_is_admin_only_and_no_production_record_is_installed(self) -> None:
        for folder in ("npi_ebom_policy", "npi_ebom_policy_version"):
            self.assertEqual(self.load(folder).get("permissions"), [SYSTEM_MANAGER])
        for folder in self.FIELDS:
            metadata = self.load(folder)
            self.assertNotIn("fixtures", metadata)
            serialized = json.dumps(metadata, sort_keys=True)
            self.assertNotIn("PROD-", serialized)
            self.assertNotIn("item_code", serialized)
            self.assertNotIn("mbom", serialized.casefold())

    def test_history_and_projection_permissions_are_closed(self) -> None:
        for folder in (
            "npi_engineering_bom_revision",
            "npi_engineering_bom_line",
            "npi_ebom_lifecycle_event",
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
        for folder in (
            "npi_engineering_bom",
            "npi_ebom_revision_lifecycle",
            "npi_ebom_command_idempotency",
        ):
            self.assertEqual(
                self.load(folder).get("permissions"),
                [SYSTEM_MANAGER, API_TRANSITION],
            )

    def test_enums_and_fail_closed_policy_rules_are_exact(self) -> None:
        policy = self.fields(self.load("npi_ebom_policy_version"))
        lifecycle = self.fields(self.load("npi_ebom_revision_lifecycle"))
        event = self.fields(self.load("npi_ebom_lifecycle_event"))
        receipt = self.fields(self.load("npi_ebom_command_idempotency"))
        self.assertEqual(policy["publication_state"].get("options"), "draft\npublished")
        self.assertEqual(
            policy["line_identity_mode"].get("options"),
            "caller_supplied_stable_key",
        )
        for fieldname in (
            "require_acyclic_graph",
            "require_closed_alternates",
            "require_effectivity_order",
        ):
            self.assertEqual(policy[fieldname].get("default"), "1")
        self.assertEqual(
            lifecycle["current_state"].get("options"),
            "draft\nin_review\napproved\nreleased",
        )
        self.assertEqual(
            event["event_type"].get("options"),
            "review_submitted\nreview_approved\nreview_rejected\nreleased",
        )
        self.assertEqual(
            receipt["operation"].get("options"),
            "ebom.create\nebom.revise\nebom.submit_review\nebom.review\nebom.release",
        )

    def test_controllers_use_closed_write_flags_and_history_guards(self) -> None:
        helper = EBOM_VALIDATION.read_text(encoding="utf-8")
        for value in (
            "npi_ebom_policy_write",
            "npi_ebom_command_write",
            "npi_ebom_lifecycle_command_write",
        ):
            self.assertIn(value, helper)
        for folder, guard in (
            ("npi_ebom_policy", "require_ebom_policy_write"),
            ("npi_ebom_policy_version", "require_ebom_policy_write"),
            ("npi_engineering_bom", "require_ebom_command_write"),
            ("npi_engineering_bom_revision", "require_ebom_command_write"),
            ("npi_engineering_bom_line", "require_ebom_command_write"),
            ("npi_ebom_revision_lifecycle", "require_ebom_lifecycle_write"),
            ("npi_ebom_lifecycle_event", "require_ebom_lifecycle_write"),
            ("npi_ebom_command_idempotency", "require_ebom_"),
        ):
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            with self.subTest(folder=folder):
                ast.parse(source)
                self.assertIn(guard, source)
                self.assertIn("deny_ebom_history_delete", source)
                self.assertNotIn("ignore_" "permissions", source)
                self.assertNotIn("frappe.db.sql", source)

    def test_domain_is_pure_and_comparison_uses_exact_line_keys(self) -> None:
        source = EBOM_DOMAIN.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("compare_engineering_bom_revisions", source)
        self.assertIn("line.line_key", source)
        self.assertNotIn("item_code", source)
        self.assertNotIn("manufacturing_routing", source)
        self.assertNotIn("frappe.db", source)

    def test_ownership_keeps_formal_item_mbom_and_stock_uom_in_erpnext(self) -> None:
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(
            encoding="utf-8"
        )
        for object_name in (
            "EngineeringBOMPolicy:",
            "EngineeringBOMPolicyVersion:",
            "EngineeringBOM:",
            "EngineeringBOMRevision:",
            "EngineeringBOMLine:",
            "EngineeringBOMRevisionLifecycle:",
            "EngineeringBOMLifecycleEvent:",
            "EngineeringBOMCommandIdempotency:",
        ):
            self.assertIn(object_name, ownership)
        self.assertIn("formal_item_code_mbom_and_routing", ownership)
        self.assertIn("formal_item_mapping_and_stock_uom", ownership)
        self.assertIn("FUTURE_APPROVED_PRODUCT_POLICY", ownership)


if __name__ == "__main__":
    unittest.main()
