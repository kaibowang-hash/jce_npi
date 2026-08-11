from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRIAL_ROOT = ROOT / "apps/npi_core/npi_core/trial"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"

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


class Phase7TrialMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_trial_plan_revision": {
            "global_id",
            "plan_global_id",
            "version_key_hash",
            "tenant_id",
            "project_global_id",
            "tooling_master",
            "tooling_master_global_id",
            "plan_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "purpose",
            "objective",
            "planned_start_at",
            "planned_end_at",
            "resource_proposal_snapshot",
            "responsible_member_snapshot",
            "sample_quantity",
            "measurement_plan_snapshot",
            "reason",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
            "plan_snapshot",
            "snapshot_hash",
        },
        "npi_trial_round": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "trial_plan_global_id",
            "trial_plan_revision",
            "trial_plan_revision_global_id",
            "trial_plan_revision_snapshot_hash",
            "tooling_master",
            "tooling_master_global_id",
            "round_sequence",
            "display_label",
            "purpose",
            "planned_start_at",
            "planned_end_at",
            "current_state",
            "current_event_global_id",
            "optimistic_version",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
            "round_snapshot",
            "snapshot_hash",
        },
        "npi_trial_round_lifecycle_event": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "trial_round_global_id",
            "event_version",
            "event_type",
            "from_state",
            "to_state",
            "reason",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
            "event_snapshot",
            "snapshot_hash",
        },
        "npi_trial_plan_work_link": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "trial_plan_global_id",
            "trial_plan_revision",
            "trial_plan_revision_global_id",
            "trial_plan_revision_snapshot_hash",
            "trial_round",
            "trial_round_global_id",
            "domain_work_item",
            "domain_work_item_global_id",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
            "link_snapshot",
            "snapshot_hash",
        },
        "npi_trial_command_idempotency": {
            "global_id",
            "receipt_key",
            "tenant_id",
            "project_global_id",
            "actor_user_id",
            "operation",
            "idempotency_key_hash",
            "payload_hash",
            "target_object_type",
            "target_global_id",
            "response_payload",
            "response_hash",
            "sealed",
            "created_at",
            "updated_at",
        },
        "npi_trial_input_lock_revision": {
            "global_id",
            "input_lock_global_id",
            "version_key_hash",
            "tenant_id",
            "project_global_id",
            "trial_round",
            "trial_round_global_id",
            "trial_plan_revision",
            "trial_plan_revision_global_id",
            "trial_plan_revision_snapshot_hash",
            "lock_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "reference_snapshot",
            "material_snapshot",
            "parameter_definition_snapshot",
            "reason",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
            "lock_snapshot",
            "snapshot_hash",
        },
        "npi_trial_actual_revision": {
            "global_id",
            "actual_global_id",
            "version_key_hash",
            "tenant_id",
            "project_global_id",
            "trial_round",
            "trial_round_global_id",
            "input_lock_revision",
            "input_lock_revision_global_id",
            "input_lock_revision_snapshot_hash",
            "actual_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "acquisition_mode",
            "resource_snapshot",
            "material_snapshot",
            "environment_snapshot",
            "parameter_snapshot",
            "operator_user_id",
            "confirmed_by_user_id",
            "execution_started_at",
            "reason",
            "created_at",
            "request_id",
            "trace_id",
            "actual_snapshot",
            "snapshot_hash",
        },
        "npi_trial_sample_batch_revision": {
            "global_id",
            "sample_batch_global_id",
            "version_key_hash",
            "tenant_id",
            "project_global_id",
            "trial_round",
            "trial_round_global_id",
            "input_lock_revision",
            "input_lock_revision_global_id",
            "input_lock_revision_snapshot_hash",
            "sample_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "label",
            "cavity_snapshot",
            "material_snapshot_hash",
            "quantity",
            "unit",
            "packaging",
            "destination",
            "feedback_text",
            "feedback_source",
            "feedback_observed_at",
            "reason",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
            "sample_snapshot",
            "snapshot_hash",
        },
        "npi_trial_evidence_reference": {
            "global_id",
            "tenant_id",
            "project_global_id",
            "trial_round",
            "trial_round_global_id",
            "role",
            "sample_batch_revision",
            "sample_batch_revision_global_id",
            "sample_batch_revision_snapshot_hash",
            "file_revision",
            "file_revision_global_id",
            "file_sha256",
            "file_size_bytes",
            "file_mime_type",
            "created_by_user_id",
            "created_at",
            "request_id",
            "trace_id",
            "evidence_snapshot",
            "snapshot_hash",
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

    def test_exact_additive_objects_and_fields(self) -> None:
        for folder, expected in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), expected)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)

    def test_history_is_append_only_and_round_projection_is_command_guarded(self) -> None:
        for folder in (
            "npi_trial_plan_revision",
            "npi_trial_round_lifecycle_event",
            "npi_trial_plan_work_link",
            "npi_trial_input_lock_revision",
            "npi_trial_actual_revision",
            "npi_trial_sample_batch_revision",
            "npi_trial_evidence_reference",
        ):
            metadata = self.load(folder)
            self.assertEqual(metadata.get("read_only"), 1)
            self.assertEqual(metadata.get("permissions"), [SYSTEM_MANAGER_APPEND, API_APPEND])
            self.assertTrue(
                all(field.get("read_only") == 1 for field in self.fields(metadata).values())
            )
            controller = (
                DOCTYPE_ROOT / folder / f"{folder}.py"
            ).read_text(encoding="utf-8")
            self.assertIn("deny_trial_history_update()", controller)
        round_metadata = self.load("npi_trial_round")
        self.assertEqual(
            round_metadata.get("permissions"),
            [SYSTEM_MANAGER_ADMIN, {**API_APPEND, "write": 1}],
        )
        self.assertTrue(
            all(field.get("read_only") == 1 for field in self.fields(round_metadata).values())
        )

    def test_receipt_has_actor_bound_one_way_seal(self) -> None:
        receipt = self.load("npi_trial_command_idempotency")
        self.assertEqual(
            receipt.get("permissions"),
            [SYSTEM_MANAGER_ADMIN, {**API_APPEND, "write": 1}],
        )
        fields = self.fields(receipt)
        expected_operations = {
            "trial_plan.create": "trial_plan_revision",
            "trial_plan.revise": "trial_plan_revision",
            "trial_round.create": "trial_round",
            "trial_round.cancel": "trial_round",
            "trial_plan.generate_actions": "trial_plan_work_link_set",
            "trial_round.prepare": "trial_input_lock_revision",
            "trial_round.start": "trial_actual_revision",
            "trial_actual.append": "trial_actual_revision",
            "trial_sample.create": "trial_sample_batch_revision",
            "trial_sample.revise": "trial_sample_batch_revision",
            "trial_file.upload": "trial_pending_file_revision",
            "trial_evidence.bind": "trial_evidence_reference",
            "trial_cavity_result.create": "trial_cavity_result_revision",
            "trial_cavity_result.revise": "trial_cavity_result_revision",
            "trial_defect.create": "trial_defect_revision",
            "trial_defect.revise": "trial_defect_revision",
            "trial_defect.verify": "trial_defect_verification_revision",
            "trial_round.begin_analysis": "trial_round_lifecycle_event",
            "trial_comparison.create": "trial_round_comparison_snapshot",
            "trial_review_reference.create": "trial_review_reference_revision",
            "trial_review_reference.revise": "trial_review_reference_revision",
            "trial_conclusion.submit": "trial_conclusion_revision",
            "trial_conclusion.decide": "trial_conclusion_revision",
            "trial_conclusion.reopen": "trial_conclusion_revision",
        }
        self.assertEqual(
            str(fields["operation"].get("options", "")).splitlines(),
            list(expected_operations),
        )
        self.assertEqual(
            str(fields["target_object_type"].get("options", "")).splitlines(),
            ["", *dict.fromkeys(expected_operations.values())],
        )
        source = (
            DOCTYPE_ROOT
            / "npi_trial_command_idempotency"
            / "npi_trial_command_idempotency.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        controller_operations = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_OPERATIONS"
                for target in node.targets
            )
        )
        self.assertEqual(controller_operations, expected_operations)
        self.assertIn("assert_immutable_fields(self, previous, _IDENTITY_FIELDS)", source)
        self.assertIn("A Trial command response can only be sealed once.", source)
        self.assertIn('"actorUserId": self.actor_user_id.casefold()', source)

    def test_metadata_does_not_claim_resource_or_later_execution_truth(self) -> None:
        metadata = [self.load(folder) for folder in self.FIELDS]
        serialized = json.dumps(metadata, sort_keys=True).casefold()
        for forbidden in (
            "reservation_id",
            "booking_id",
            "availability_state",
            "erpnext_endpoint",
            "credential",
            "secret",
            "quality_result",
            "gate_status",
            "sample_result",
            "file_url",
            "machine_endpoint",
            "automatic_import_success",
            "approved_baseline_value",
        ):
            self.assertNotIn(forbidden, serialized)
        work_fields = self.fields(self.load("npi_trial_plan_work_link"))
        for duplicate_task_truth in ("status", "state", "owner", "due_at", "completed_at"):
            self.assertNotIn(duplicate_task_truth, work_fields)

    def test_all_controllers_fail_closed_behind_trial_command_flag(self) -> None:
        validation = (TRIAL_ROOT / "frappe_validation.py").read_text(encoding="utf-8")
        self.assertIn('TRIAL_COMMAND_WRITE_FLAG = "npi_trial_command_write"', validation)
        self.assertIn("deny_trial_history_delete", validation)
        for folder in self.FIELDS:
            source = (
                DOCTYPE_ROOT / folder / f"{folder}.py"
            ).read_text(encoding="utf-8")
            self.assertIn("require_trial_command_write()", source)
            self.assertIn("def on_trash", source)
            self.assertIn("deny_trial_history_delete", source)

    def test_exact_parent_validation_preserves_project_scope(self) -> None:
        source = (TRIAL_ROOT / "metadata_validation.py").read_text(encoding="utf-8")
        for parent in (
            "NPI Engineering Project",
            "NPI Tooling Master",
            "NPI Tooling Applicability",
            "NPI Project Member",
            "NPI Trial Plan Revision",
            "NPI Trial Round",
            "NPI Trial Round Lifecycle Event",
            "NPI Domain Work Item",
            "NPI Trial Input Lock Revision",
            "NPI Trial Actual Revision",
            "NPI Trial Sample Batch Revision",
            "NPI File Revision",
        ):
            self.assertIn(f'"{parent}"', source)
        self.assertIn("require_current_project_member(", source)
        self.assertIn(
            "int(document.optimistic_version) != member.optimistic_version",
            source,
        )
        self.assertIn("starts <= today and (ends is None or today <= ends)", source)
        self.assertIn('str(_record_value(user, "user_type")) != "System User"', source)
        self.assertIn('"snapshot_hash": value.trial_plan_revision_snapshot_hash', source)
        self.assertIn('"scan_state": "clean"', source)
        self.assertIn('"is_private": 1', source)

    def test_execution_metadata_keeps_manual_single_owner_truth(self) -> None:
        actual = self.fields(self.load("npi_trial_actual_revision"))
        self.assertEqual(actual["acquisition_mode"]["options"], "manual")
        evidence = self.fields(self.load("npi_trial_evidence_reference"))
        self.assertEqual(
            evidence["role"]["options"].splitlines(),
            [
                "photo",
                "video",
                "parameter_curve",
                "measurement_report",
                "customer_feedback",
            ],
        )
        for folder in (
            "npi_trial_input_lock_revision",
            "npi_trial_actual_revision",
            "npi_trial_sample_batch_revision",
            "npi_trial_evidence_reference",
        ):
            metadata = self.load(folder)
            self.assertEqual(metadata.get("read_only"), 1)
            self.assertEqual(metadata.get("permissions"), [SYSTEM_MANAGER_APPEND, API_APPEND])
            self.assertTrue(
                all(field.get("read_only") == 1 for field in self.fields(metadata).values())
            )

    def test_all_visible_sources_have_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        python_paths = list(TRIAL_ROOT.glob("*.py"))
        for folder in self.FIELDS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Select":
                    sources.update(
                        option
                        for option in str(field.get("options", "")).splitlines()
                        if option
                    )
            python_paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for path in python_paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    sources.add(node.args[0].value)
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(
                encoding="utf-8",
                newline="",
            ) as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} Trial translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
