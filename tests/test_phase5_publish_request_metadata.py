from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = (
    ROOT
    / "apps/npi_integration/npi_integration/npi_integration/doctype"
)
VALIDATION = (
    ROOT
    / "apps/npi_integration/npi_integration/publish_request/frappe_validation.py"
)

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


class Phase5PublishRequestMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_ebom_publish_policy": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "policy_key",
            "policy_key_hash",
            "title",
            "enabled",
            "optimistic_version",
        },
        "npi_ebom_publish_policy_version": {
            "global_id",
            "publish_policy",
            "tenant_id",
            "project_global_id",
            "policy_global_id",
            "policy_key",
            "policy_version",
            "version_key",
            "title",
            "publication_state",
            "target_mode",
            "api_version",
            "operation",
            "requester_user_ids",
            "policy_snapshot",
            "snapshot_hash",
            "published_at",
            "optimistic_version",
        },
        "npi_ebom_publish_request": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "engineering_bom",
            "ebom_global_id",
            "engineering_bom_revision",
            "revision_global_id",
            "publish_policy_global_id",
            "publish_policy_version",
            "publish_policy_snapshot_hash",
            "target_mode",
            "api_version",
            "operation",
            "state",
            "dispatch_allowed",
            "evidence_snapshot",
            "payload_hash",
            "node_count",
            "actor_user_id",
            "request_id",
            "trace_id",
            "idempotency_key_hash",
            "created_at",
        },
        "npi_ebom_publish_node": {
            "global_id",
            "publish_request",
            "request_global_id",
            "tenant_id",
            "project_global_id",
            "ebom_global_id",
            "revision_global_id",
            "line_global_id",
            "line_key",
            "engineering_item_id",
            "line_snapshot",
            "line_hash",
            "mapping_observation",
            "mapping_state",
            "mapping_version",
            "operations",
            "result_state",
            "input_hash",
            "created_at",
        },
        "npi_ebom_publish_mapping_observation": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "line_global_id",
            "engineering_item_id",
            "mapping_state",
            "mapping_version",
            "formal_item_code",
            "formal_mbom_id",
            "target_version",
            "observed_at",
            "source_system",
            "observation_snapshot",
            "observation_hash",
            "created_at",
        },
        "npi_ebom_publish_node_result": {
            "global_id",
            "publish_request",
            "request_global_id",
            "publish_node",
            "node_global_id",
            "tenant_id",
            "project_global_id",
            "attempt_number",
            "state",
            "fault_kind",
            "future_retry_directive",
            "future_retryable",
            "reconciliation_required",
            "retry_after_required",
            "phase5_dispatch_allowed",
            "formal_item_code",
            "formal_mbom_id",
            "target_version",
            "occurred_at",
            "result_snapshot",
            "result_hash",
        },
        "npi_ebom_publish_command_idempotency": {
            "global_id",
            "receipt_key",
            "tenant_id",
            "project_global_id",
            "actor_user_id",
            "operation",
            "idempotency_key_hash",
            "payload_hash",
            "request_global_id",
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

    def test_additive_foundation_contains_exact_objects_and_fields(self) -> None:
        for folder, expected in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), expected)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)

    def test_policies_are_admin_only_mock_only_and_install_no_defaults(self) -> None:
        for folder in (
            "npi_ebom_publish_policy",
            "npi_ebom_publish_policy_version",
        ):
            metadata = self.load(folder)
            self.assertEqual(metadata.get("permissions"), [SYSTEM_MANAGER_ADMIN])
            self.assertNotIn("fixtures", metadata)
        version = self.fields(self.load("npi_ebom_publish_policy_version"))
        self.assertEqual(version["target_mode"].get("options"), "mock")
        self.assertEqual(version["target_mode"].get("default"), "mock")
        self.assertEqual(version["api_version"].get("default"), "npi.erp-publish.v1")
        self.assertEqual(
            version["operation"].get("default"),
            "publish_released_ebom_item_mbom",
        )
        serialized = json.dumps(
            [self.load(folder) for folder in self.FIELDS], sort_keys=True
        ).casefold()
        for forbidden in ("https://", "http://", "password", "credential", "secret"):
            self.assertNotIn(forbidden, serialized)

    def test_request_and_history_permissions_are_closed(self) -> None:
        for folder in (
            "npi_ebom_publish_request",
            "npi_ebom_publish_node",
            "npi_ebom_publish_mapping_observation",
            "npi_ebom_publish_node_result",
        ):
            metadata = self.load(folder)
            self.assertEqual(
                metadata.get("permissions"),
                [SYSTEM_MANAGER_APPEND, API_APPEND],
            )
            self.assertEqual(metadata.get("read_only"), 1)
            self.assertTrue(
                all(
                    field.get("read_only") == 1
                    for field in self.fields(metadata).values()
                )
            )
        receipt = self.load("npi_ebom_publish_command_idempotency")
        self.assertEqual(
            receipt.get("permissions"),
            [SYSTEM_MANAGER_ADMIN, {**API_APPEND, "write": 1}],
        )

    def test_mock_metadata_never_defaults_to_execution_success(self) -> None:
        request = self.fields(self.load("npi_ebom_publish_request"))
        node = self.fields(self.load("npi_ebom_publish_node"))
        result = self.fields(self.load("npi_ebom_publish_node_result"))
        self.assertEqual(request["target_mode"].get("options"), "mock")
        self.assertEqual(request["state"].get("options"), "validated\nmanual_intervention")
        self.assertEqual(request["dispatch_allowed"].get("default"), "0")
        self.assertEqual(node["result_state"].get("options"), "validated\nblocked_mapping")
        self.assertEqual(result["state"].get("options"), "validated\nblocked_mapping")
        self.assertEqual(result["phase5_dispatch_allowed"].get("default"), "0")
        for fieldname in ("formal_item_code", "formal_mbom_id", "target_version"):
            self.assertEqual(result[fieldname].get("read_only"), 1)

    def test_controllers_use_closed_write_flags_and_delete_audit_guards(self) -> None:
        helper = VALIDATION.read_text(encoding="utf-8")
        ast.parse(helper)
        for value in (
            "npi_ebom_publish_policy_write",
            "npi_ebom_publish_request_write",
            "npi_audit_append",
            "ebom.publish_request.history.delete_attempt",
        ):
            self.assertIn(value, helper)
        for folder in self.FIELDS:
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            with self.subTest(folder=folder):
                ast.parse(source)
                self.assertIn("deny_publish_history_delete", source)
                self.assertIn("require_publish_", source)
                self.assertNotIn("ignore_" "permissions", source)
                self.assertNotIn("frappe.db." "sql", source)

    def test_formal_identifiers_remain_server_read_only_observations(self) -> None:
        for folder in (
            "npi_ebom_publish_mapping_observation",
            "npi_ebom_publish_node_result",
        ):
            fields = self.fields(self.load(folder))
            for fieldname in ("formal_item_code", "formal_mbom_id", "target_version"):
                self.assertEqual(fields[fieldname].get("read_only"), 1)
        mapping_source = (
            DOCTYPE_ROOT
            / "npi_ebom_publish_mapping_observation"
            / "npi_ebom_publish_mapping_observation.py"
        ).read_text(encoding="utf-8")
        self.assertIn('self.source_system != "NPI_ONE"', mapping_source)
        self.assertIn('self.mapping_state != "unmapped"', mapping_source)
        self.assertIn("without ERP identifiers", mapping_source)


if __name__ == "__main__":
    unittest.main()
