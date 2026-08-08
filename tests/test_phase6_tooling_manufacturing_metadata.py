from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
DOMAIN = ROOT / "apps/npi_core/npi_core/tooling/manufacturing_domain.py"
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


class Phase6ToolingManufacturingMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_tooling_manufacturing_plan_revision": {
            "global_id", "plan_global_id", "version_key_hash", "tenant_id",
            "project_global_id", "tooling_master", "tooling_master_global_id",
            "tooling_revision", "tooling_revision_global_id",
            "tooling_revision_snapshot_hash", "plan_version",
            "predecessor_global_id", "predecessor_snapshot_hash",
            "sourcing_strategy", "responsible_member",
            "responsible_member_global_id", "responsibility_snapshot",
            "cost_snapshot", "document_evidence_snapshot",
            "design_release_snapshot", "milestone_snapshot", "reason",
            "created_by_user_id", "created_at", "request_id", "trace_id",
            "plan_snapshot", "snapshot_hash",
        },
        "npi_tooling_manufacturing_milestone_observation": {
            "global_id", "observation_key_hash", "tenant_id",
            "project_global_id", "tooling_master_global_id",
            "manufacturing_plan_revision", "plan_revision_global_id",
            "plan_revision_snapshot_hash", "milestone_global_id",
            "milestone_snapshot_hash", "observation_version",
            "predecessor_global_id", "predecessor_snapshot_hash",
            "progress_percentage", "actual_start", "actual_finish", "risk",
            "note", "evidence_snapshot", "reported_by_member",
            "reported_by_member_global_id", "reporter_snapshot", "created_at",
            "request_id", "trace_id", "observation_snapshot", "snapshot_hash",
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

    def test_two_exact_additive_append_only_objects(self) -> None:
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

    def test_metadata_preserves_internal_plan_and_observation_boundaries(self) -> None:
        plan = self.fields(self.load("npi_tooling_manufacturing_plan_revision"))
        observation = self.fields(
            self.load("npi_tooling_manufacturing_milestone_observation")
        )
        self.assertEqual(plan["tooling_revision"].get("options"), "NPI Tooling Revision")
        self.assertEqual(plan["responsible_member"].get("options"), "NPI Project Member")
        self.assertEqual(
            str(plan["sourcing_strategy"].get("options", "")).splitlines(),
            ["internal", "supplier", "hybrid"],
        )
        self.assertEqual(
            observation["manufacturing_plan_revision"].get("options"),
            "NPI Tooling Manufacturing Plan Revision",
        )
        for fields in (plan, observation):
            for forbidden in (
                "status", "lifecycle_state", "supplier_id", "purchase_order_id",
                "invoice_id", "actual_cost", "erpnext_endpoint", "credential",
                "approved", "manufacturing_authorized", "file_url",
            ):
                self.assertNotIn(forbidden, fields)

    def test_receipt_has_only_the_two_closed_new_pairs(self) -> None:
        metadata = self.load("npi_tooling_command_idempotency")
        fields = self.fields(metadata)
        operations = str(fields["operation"].get("options", "")).splitlines()
        targets = str(fields["target_object_type"].get("options", "")).splitlines()
        self.assertEqual(
            operations[-2:],
            [
                "tooling_manufacturing_plan.create",
                "tooling_manufacturing_milestone.observe",
            ],
        )
        self.assertEqual(
            targets[-2:],
            [
                "tooling_manufacturing_plan_revision",
                "tooling_manufacturing_milestone_observation",
            ],
        )
        source = (
            DOCTYPE_ROOT
            / "npi_tooling_command_idempotency"
            / "npi_tooling_command_idempotency.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"tooling_manufacturing_plan.create": "tooling_manufacturing_plan_revision"',
            source,
        )
        self.assertIn(
            '"tooling_manufacturing_milestone.observe": "tooling_manufacturing_milestone_observation"',
            source,
        )

    def test_controllers_require_closed_write_and_exact_dependencies(self) -> None:
        plan_source = (
            DOCTYPE_ROOT
            / "npi_tooling_manufacturing_plan_revision"
            / "npi_tooling_manufacturing_plan_revision.py"
        ).read_text(encoding="utf-8")
        observation_source = (
            DOCTYPE_ROOT
            / "npi_tooling_manufacturing_milestone_observation"
            / "npi_tooling_manufacturing_milestone_observation.py"
        ).read_text(encoding="utf-8")
        for source in (plan_source, observation_source):
            self.assertIn("require_tooling_command_write()", source)
            self.assertIn("deny_tooling_history_update()", source)
            self.assertIn("def on_trash", source)
            self.assertIn("deny_tooling_history_delete", source)
            self.assertIn("frappe_utc_datetime_text", source)
        for marker in (
            '"NPI Tooling Revision"', '"NPI Project Member"',
            '"NPI Document Revision Lifecycle"', '"current_state": "released"',
            '"NPI Document Lifecycle Event"', '"event_hash": evidence.release_event_hash',
            'extra_fields=("design_document_revision_snapshot",)',
            '"effective_to": None',
        ):
            self.assertIn(marker, plan_source)
        for marker in (
            '"NPI Tooling Manufacturing Plan Revision"',
            'extra_fields=("plan_snapshot",)', '"NPI File Revision"',
            '"scan_state": "clean"', '"is_private": 1',
            '"effective_to": None',
        ):
            self.assertIn(marker, observation_source)

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
                f"missing {language} P6-04 translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
