from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps/npi_core/npi_core"
DOCTYPE_ROOT = APP_ROOT / "npi_core/doctype"
CHANGE_ROOT = APP_ROOT / "change_control"
FOLDERS = (
    "npi_engineering_change",
    "npi_engineering_change_revision",
    "npi_engineering_change_event",
    "npi_engineering_change_idempotency",
)


class Phase9ChangeControlMetadataTest(unittest.TestCase):
    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["fieldname"]: item for item in metadata["fields"]}

    def test_four_additive_doctypes_are_guarded_and_create_no_business_defaults(self) -> None:
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata["custom"], 0)
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertNotIn("fixtures", metadata)
                self.assertTrue((DOCTYPE_ROOT / folder / "__init__.py").is_file())
                self.assertEqual(metadata["permissions"][0]["role"], "System Manager")
                self.assertEqual(metadata["permissions"][1]["role"], "NPI API User")
                self.assertTrue(
                    all(permission.get("delete", 0) == 0 for permission in metadata["permissions"])
                )
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
                self.assertIn("require_change_command_write()", source)
                self.assertIn("deny_change_history_delete(self)", source)
                ast.parse(source)

        patch_source = (APP_ROOT / "patches/v1_2/add_change_control.py").read_text(encoding="utf-8")
        self.assertIn("no defaults, fixtures", patch_source)
        self.assertNotIn("frappe.db", patch_source)
        self.assertNotIn("insert(", patch_source)
        self.assertIn("npi_core.patches.v1_2.add_change_control", (APP_ROOT / "patches.txt").read_text(encoding="utf-8"))

    def test_current_shell_is_project_scoped_versioned_and_erp_observation_owned(self) -> None:
        metadata = self.load("npi_engineering_change")
        fields = self.fields(metadata)
        self.assertEqual(fields["project_global_id"]["options"], "NPI Engineering Project")
        self.assertEqual(fields["current_revision"]["options"], "NPI Engineering Change Revision")
        self.assertEqual(
            fields["formal_change_doctype"]["options"],
            "\nEngineering Change Request",
        )
        for name in (
            "global_id", "tenant_id", "project_global_id", "internal_state",
            "optimistic_version", "current_revision_global_id",
            "current_revision_number", "current_revision_snapshot_hash",
            "formal_change_document_id", "formal_change_raw_status",
            "formal_change_source_version", "formal_change_source_hash",
            "formal_change_observed_at",
        ):
            self.assertEqual(fields[name].get("read_only"), 1)
        source = (DOCTYPE_ROOT / "npi_engineering_change/npi_engineering_change.py").read_text(encoding="utf-8")
        self.assertIn("require_change_observation_write()", source)
        self.assertIn("FORMAL_CHANGE_DOCTYPE", source)
        self.assertIn("must advance by exactly one", source)

    def test_revision_stores_exact_canonical_snapshots_without_copying_source_objects(self) -> None:
        metadata = self.load("npi_engineering_change_revision")
        fields = self.fields(metadata)
        for name in (
            "predecessor_global_id", "predecessor_snapshot_hash",
            "formal_change_snapshot", "impact_assessment_snapshot",
            "affected_object_snapshot", "implementation_task_snapshot",
            "effectivity_snapshot", "disposition_snapshot",
            "revalidation_snapshot", "cost_summary_snapshot",
            "closure_evidence_snapshot", "revision_snapshot", "snapshot_hash",
        ):
            self.assertIn(name, fields)
            self.assertEqual(fields[name].get("read_only"), 1)
        for forbidden in (
            "document_content", "ebom_lines", "tooling_payload", "trial_result_payload",
            "gate_decision_payload", "work_item_state", "erp_effectivity_transaction",
            "change",
        ):
            self.assertNotIn(forbidden, fields)
        self.assertTrue(all(permission.get("write", 0) == 0 for permission in metadata["permissions"]))
        source = (DOCTYPE_ROOT / "npi_engineering_change_revision/npi_engineering_change_revision.py").read_text(encoding="utf-8")
        self.assertIn("deny_change_history_update()", source)
        self.assertIn("sha256_json(snapshot)", source)
        self.assertIn("expected_version_key = sha256_json", source)

    def test_event_and_idempotency_are_append_only_or_one_way_sealed(self) -> None:
        event = self.load("npi_engineering_change_event")
        event_fields = self.fields(event)
        self.assertEqual(
            event_fields["project_global_id"]["options"],
            "NPI Engineering Project",
        )
        self.assertEqual(event_fields["tenant_id"].get("search_index"), 1)
        self.assertEqual(event_fields["event_type"]["options"].splitlines(), [
            "created", "revised", "formal_observation_linked", "ready_to_close", "closed", "cancelled",
        ])
        event_source = (DOCTYPE_ROOT / "npi_engineering_change_event/npi_engineering_change_event.py").read_text(encoding="utf-8")
        self.assertIn("deny_change_history_update()", event_source)
        self.assertIn("sha256_json(snapshot)", event_source)

        receipt = self.load("npi_engineering_change_idempotency")
        receipt_fields = self.fields(receipt)
        self.assertEqual(receipt_fields["actor_key_hash"].get("unique"), 1)
        self.assertEqual(receipt_fields["response_sealed"].get("default"), "0")
        receipt_source = (DOCTYPE_ROOT / "npi_engineering_change_idempotency/npi_engineering_change_idempotency.py").read_text(encoding="utf-8")
        self.assertIn("An idempotency response can only be sealed once", receipt_source)
        self.assertNotIn("ignore_permissions", receipt_source)

    def test_permissions_do_not_create_desk_or_generic_writer_access(self) -> None:
        for folder in FOLDERS:
            metadata = self.load(folder)
            for permission in metadata["permissions"]:
                self.assertEqual(permission.get("delete", 0), 0)
                self.assertEqual(permission.get("export", 0), 0)
                self.assertEqual(permission.get("print", 0), 0)
                self.assertEqual(permission.get("email", 0), 0)
            api_permission = metadata["permissions"][1]
            self.assertEqual(api_permission.get("read", 0), 0)
        for path in CHANGE_ROOT.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("ignore_permissions", source)
            self.assertNotIn("frappe.db." + "sql", source)

    def test_write_flags_restore_prior_state_and_observation_requires_command_scope(self) -> None:
        module, flags, error_type = self._load_guard_module()
        with self.assertRaises(error_type):
            module.require_change_command_write()
        with self.assertRaises(error_type):
            module.require_change_observation_write()
        with module.change_command_write():
            self.assertTrue(flags.npi_change_control_command_write)
            with self.assertRaises(error_type):
                module.require_change_observation_write()
        self.assertFalse(hasattr(flags, "npi_change_control_command_write"))
        with module.change_observation_write():
            module.require_change_observation_write()
            self.assertTrue(flags.npi_change_control_command_write)
            self.assertTrue(flags.npi_change_control_observation_write)
            self.assertTrue(flags.npi_audit_append)
        self.assertEqual(vars(flags), {})

    def test_data_ownership_keeps_formal_truth_in_erp_and_npi_impact_in_launchflow(self) -> None:
        source = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
        engineering_change = source.split("  EngineeringChange:\n", 1)[1].split(
            "  EngineeringChangeRevision:\n", 1
        )[0]
        revision = source.split("  EngineeringChangeRevision:\n", 1)[1].split(
            "  EngineeringChangeEvent:\n", 1
        )[0]
        self.assertIn("owner_system: NPI_ONE_CHANGE_CONTROL_SERVICE", engineering_change)
        self.assertIn(
            "formal_change_identifier_raw_status_source_version_and_effectivity_transaction_truth: {owner: ERPNEXT",
            engineering_change,
        )
        self.assertIn(
            "impact_assessment_affected_versions_tasks_and_revalidation: {owner: NPI_ONE_CHANGE_CONTROL_SERVICE",
            engineering_change,
        )
        self.assertIn("erp_view: none", revision)

    def test_json_and_python_sources_are_parseable_and_labels_are_english(self) -> None:
        for folder in FOLDERS:
            metadata = self.load(folder)
            for field in metadata["fields"]:
                self.assertIsInstance(field["label"], str)
                self.assertNotRegex(field["label"], r"[\u4e00-\u9fff]")
            ast.parse((DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8"))
        ast.parse((CHANGE_ROOT / "domain.py").read_text(encoding="utf-8"))
        ast.parse((CHANGE_ROOT / "frappe_validation.py").read_text(encoding="utf-8"))

    @staticmethod
    def _load_guard_module():
        class PermissionErrorForTest(Exception):
            pass

        class ValidationErrorForTest(Exception):
            pass

        flags = types.SimpleNamespace()
        frappe = types.ModuleType("frappe")
        frappe.flags = flags
        frappe.PermissionError = PermissionErrorForTest
        frappe.ValidationError = ValidationErrorForTest

        def throw(message, error_type):
            raise error_type(str(message))

        frappe.throw = throw
        frappe._ = lambda source: source
        previous = {name: sys.modules.get(name) for name in ("frappe",)}
        sys.modules["frappe"] = frappe
        try:
            path = CHANGE_ROOT / "frappe_validation.py"
            spec = importlib.util.spec_from_file_location("phase9_change_guard", path)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            if previous["frappe"] is None:
                sys.modules.pop("frappe", None)
            else:
                sys.modules["frappe"] = previous["frappe"]
        return module, flags, PermissionErrorForTest


if __name__ == "__main__":
    unittest.main()
