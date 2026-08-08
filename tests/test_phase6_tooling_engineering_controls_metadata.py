from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
DOMAIN = ROOT / "apps/npi_core/npi_core/tooling/engineering_controls_domain.py"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"

SYSTEM_MANAGER_APPEND = {
    "role": "System Manager",
    "read": 1,
    "write": 0,
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


class Phase6ToolingEngineeringControlsMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_tooling_defect_revision": {
            "global_id", "defect_global_id", "version_key_hash", "tenant_id",
            "project_global_id", "tooling_master", "tooling_master_global_id",
            "tooling_revision", "tooling_revision_global_id",
            "tooling_revision_snapshot_hash", "cavity_global_id",
            "cavity_identifier", "defect_version", "predecessor_global_id",
            "predecessor_snapshot_hash", "business_code", "title",
            "description", "category_key", "severity", "blocking", "state",
            "responsible_member", "responsible_member_global_id",
            "detection_context_snapshot", "root_cause_state", "root_cause",
            "target_round_label", "action_snapshot", "evidence_snapshot",
            "reason", "created_by_user_id", "created_at", "request_id",
            "trace_id", "defect_snapshot", "snapshot_hash",
        },
        "npi_tooling_process_profile_revision": {
            "global_id", "profile_global_id", "version_key_hash", "tenant_id",
            "project_global_id", "tooling_master", "tooling_master_global_id",
            "tooling_revision", "tooling_revision_global_id",
            "tooling_revision_snapshot_hash", "layer", "profile_version",
            "predecessor_global_id", "predecessor_snapshot_hash",
            "effective_from", "context_snapshot", "metric_snapshot", "reason",
            "created_by_user_id", "created_at", "request_id", "trace_id",
            "profile_snapshot", "snapshot_hash",
        },
        "npi_tooling_capacity_scenario_revision": {
            "global_id", "scenario_global_id", "version_key_hash", "tenant_id",
            "project_global_id", "tooling_master", "tooling_master_global_id",
            "scenario_version", "predecessor_global_id",
            "predecessor_snapshot_hash", "title", "effective_from",
            "target_monthly_assembly_units", "formula_version", "rounding_rule",
            "input_snapshot", "result_snapshot", "reason", "created_by_user_id",
            "created_at", "request_id", "trace_id", "scenario_snapshot",
            "snapshot_hash",
        },
    }

    @staticmethod
    def load(folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            value["fieldname"]: value
            for value in metadata["fields"]  # type: ignore[index]
        }

    def test_three_exact_additive_append_only_objects(self) -> None:
        for folder, expected in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), expected)
                self.assertEqual(metadata.get("permissions"), [SYSTEM_MANAGER_APPEND, API_APPEND])
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertEqual(metadata.get("read_only"), 1)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(
                    all(field.get("read_only") == 1 for field in self.fields(metadata).values())
                )

    def test_metadata_keeps_defect_process_and_capacity_truth_separate(self) -> None:
        defect = self.fields(self.load("npi_tooling_defect_revision"))
        profile = self.fields(self.load("npi_tooling_process_profile_revision"))
        capacity = self.fields(self.load("npi_tooling_capacity_scenario_revision"))
        self.assertEqual(defect["tooling_revision"].get("options"), "NPI Tooling Revision")
        self.assertEqual(defect["responsible_member"].get("options"), "NPI Project Member")
        self.assertEqual(
            str(defect["state"].get("options", "")).splitlines(),
            ["open", "assigned", "in_progress", "ready_for_verification", "closed", "reopened"],
        )
        self.assertEqual(
            str(profile["layer"].get("options", "")).splitlines(),
            ["customer_standard", "trial_actual", "approved_baseline"],
        )
        self.assertEqual(capacity["formula_version"].get("options"), "capacity.v1")
        self.assertEqual(capacity["rounding_rule"].get("options"), "decimal-6-half-even")
        combined = set(defect) | set(profile) | set(capacity)
        for forbidden in (
            "gate_id", "gate_state", "trial_round_id", "trial_result",
            "approved", "shot_count", "health_score", "maintenance_advice",
            "erpnext_endpoint", "credential", "file_url",
        ):
            self.assertNotIn(forbidden, combined)

    def test_receipt_has_only_the_three_closed_new_pairs(self) -> None:
        metadata = self.load("npi_tooling_command_idempotency")
        fields = self.fields(metadata)
        operations = str(fields["operation"].get("options", "")).splitlines()
        targets = str(fields["target_object_type"].get("options", "")).splitlines()
        self.assertEqual(
            operations[-3:],
            [
                "tooling_defect.revise",
                "tooling_process_profile.create",
                "tooling_capacity_scenario.create",
            ],
        )
        self.assertEqual(
            targets[-3:],
            [
                "tooling_defect_revision",
                "tooling_process_profile_revision",
                "tooling_capacity_scenario_revision",
            ],
        )
        source = (
            DOCTYPE_ROOT
            / "npi_tooling_command_idempotency"
            / "npi_tooling_command_idempotency.py"
        ).read_text(encoding="utf-8")
        for operation, target in zip(operations[-3:], targets[-3:], strict=True):
            self.assertIn(f'"{operation}": "{target}"', source)

    def test_controllers_require_closed_write_and_exact_dependencies(self) -> None:
        sources = {
            folder: (
                DOCTYPE_ROOT / folder / f"{folder}.py"
            ).read_text(encoding="utf-8")
            for folder in self.FIELDS
        }
        for source in sources.values():
            self.assertIn("require_tooling_command_write()", source)
            self.assertIn("deny_tooling_history_update()", source)
            self.assertIn("def on_trash", source)
            self.assertIn("deny_tooling_history_delete", source)
            self.assertIn("frappe_utc_datetime_text", source)
        for marker in (
            '"NPI Tooling Revision"', '"NPI Project Member"',
            '"NPI File Revision"', '"scan_state": "clean"', '"is_private": 1',
            "validate_tooling_defect_successor", "_require_detection_context(value)",
        ):
            self.assertIn(marker, sources["npi_tooling_defect_revision"])
        for marker in (
            '"NPI Tooling Revision"', '"NPI Document Revision"',
            '"NPI Document Revision Lifecycle"', '"current_state": "released"',
            '"NPI Document Lifecycle Event"', "validate_process_profile_successor",
            'frappe.db.exists("DocType", "NPI Trial Round")',
        ):
            self.assertIn(marker, sources["npi_tooling_process_profile_revision"])
        for marker in (
            '"NPI Engineering Part Revision"', '"NPI Tooling Applicability"',
            '"NPI Tooling Set"', "CapacityProvenanceKind.SCENARIO_ASSUMPTION",
            "validate_capacity_scenario_successor", "value.result_payload()",
        ):
            self.assertIn(marker, sources["npi_tooling_capacity_scenario_revision"])

    def test_all_new_visible_sources_have_direct_symmetric_translations(self) -> None:
        sources: set[str] = set()
        python_paths = [DOMAIN]
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
                encoding="utf-8", newline=""
            ) as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} P6-05 translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
