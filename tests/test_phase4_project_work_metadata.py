from __future__ import annotations

import json
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
WORK_DOCTYPES = (
    "npi_project_work_policy_version",
    "npi_project_member",
    "npi_project_role_assignment",
    "npi_project_substitution",
    "npi_project_raci_assignment",
    "npi_wbs_item",
    "npi_wbs_dependency",
    "npi_wbs_plan_baseline",
    "npi_domain_work_item",
    "npi_project_work_idempotency",
)
COMMAND_OWNED_DOCTYPES = tuple(
    folder
    for folder in WORK_DOCTYPES
    if folder != "npi_project_work_policy_version"
)


class Phase4ProjectWorkMetadataTest(unittest.TestCase):
    def load_doctype(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def fields(self, folder: str) -> dict[str, dict[str, object]]:
        metadata = self.load_doctype(folder)
        return {
            field["fieldname"]: field
            for field in metadata["fields"]  # type: ignore[index]
        }

    def test_project_work_doctypes_are_additive_and_system_manager_only(self) -> None:
        for folder in WORK_DOCTYPES:
            with self.subTest(folder=folder):
                metadata = self.load_doctype(folder)
                self.assertEqual(metadata.get("custom"), 0)
                self.assertEqual(metadata.get("allow_rename"), 0)
                permissions = metadata["permissions"]  # type: ignore[index]
                self.assertEqual(
                    {permission["role"] for permission in permissions},
                    {"System Manager"},
                )
                self.assertTrue(
                    all(not permission.get("delete") for permission in permissions)
                )

    def test_policy_is_versioned_and_published_content_has_a_hash(self) -> None:
        metadata = self.load_doctype("npi_project_work_policy_version")
        fields = self.fields("npi_project_work_policy_version")
        self.assertEqual(metadata.get("autoname"), "field:version_key")
        self.assertEqual(fields["global_id"].get("unique"), 1)
        self.assertEqual(fields["version_key"].get("unique"), 1)
        self.assertEqual(
            fields["publication_state"].get("options"),
            "draft\npublished",
        )
        self.assertEqual(fields["snapshot_hash"].get("read_only"), 1)
        self.assertIn("role_keys", fields)
        self.assertIn("wbs_states", fields)
        self.assertIn("work_item_lifecycles", fields)

    def test_kind_is_not_passed_into_strict_lifecycle_parsers(self) -> None:
        sources = (
            DOCTYPE_ROOT
            / "npi_project_work_policy_version"
            / "npi_project_work_policy_version.py",
            ROOT
            / "apps/npi_core/npi_core/project_work/frappe_repository.py",
        )
        parser_names = {"_lifecycle", "_domain_lifecycle"}
        for source in sources:
            with self.subTest(source=source.relative_to(ROOT)):
                tree = ast.parse(source.read_text(encoding="utf-8"))
                parser_calls = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in parser_names
                ]
                lifecycle_calls = [
                    node
                    for node in parser_calls
                    if node.args
                    and isinstance(node.args[0], ast.Dict)
                    and {
                        key.value
                        for key in node.args[0].keys
                        if isinstance(key, ast.Constant)
                    }
                    == {"initialStateKey", "states"}
                ]
                self.assertTrue(
                    lifecycle_calls,
                    "Kind lifecycle parsing must strip the sibling kind key.",
                )

    def test_team_raci_and_substitution_are_explicit_and_dated(self) -> None:
        member = self.fields("npi_project_member")
        role = self.fields("npi_project_role_assignment")
        substitution = self.fields("npi_project_substitution")
        raci = self.fields("npi_project_raci_assignment")
        self.assertEqual(member["user_id"].get("options"), "User")
        self.assertIn("role_key", role)
        self.assertIn("effective_from", role)
        self.assertIn("effective_to", role)
        self.assertIn("role_assignment_global_id", substitution)
        self.assertIn("substitute_member_global_id", substitution)
        self.assertEqual(substitution["effective_to"].get("reqd"), 1)
        self.assertEqual(
            raci["responsibility"].get("options"),
            "responsible\naccountable\nconsulted\ninformed",
        )
        self.assertNotIn("approval_access", raci)
        self.assertNotIn("can_approve", raci)

    def test_wbs_and_baseline_persist_required_planning_facts(self) -> None:
        item = self.fields("npi_wbs_item")
        dependency = self.fields("npi_wbs_dependency")
        baseline_metadata = self.load_doctype("npi_wbs_plan_baseline")
        baseline = self.fields("npi_wbs_plan_baseline")
        for fieldname in (
            "parent_global_id",
            "owner_role_assignment_global_id",
            "planned_start",
            "planned_end",
            "actual_start",
            "actual_end",
            "milestone",
            "status_key",
            "progress_percent",
            "critical_task",
            "plan_revision",
        ):
            self.assertIn(fieldname, item)
        self.assertEqual(item["title"].get("fieldtype"), "Small Text")
        self.assertIn("predecessor_global_id", dependency)
        self.assertIn("successor_global_id", dependency)
        self.assertNotIn("dependency_type", dependency)
        self.assertEqual(baseline_metadata.get("read_only"), 1)
        self.assertEqual(baseline["snapshot_hash"].get("reqd"), 1)
        self.assertEqual(baseline["snapshot"].get("fieldtype"), "JSON")

    def test_domain_work_item_kind_and_policy_state_are_not_conflated(self) -> None:
        work_item = self.fields("npi_domain_work_item")
        self.assertEqual(
            work_item["kind"].get("options"),
            "risk\nissue\naction\ndecision_request",
        )
        self.assertIn("state_key", work_item)
        self.assertIn("work_policy_global_id", work_item)
        self.assertIn("work_policy_version", work_item)
        self.assertIn("work_policy_snapshot_hash", work_item)
        self.assertIn("relations", work_item)
        self.assertIn("evidence_references", work_item)
        self.assertIn("stage_global_id", work_item)
        self.assertIn("wbs_item_global_id", work_item)
        self.assertNotIn("my_work_category", work_item)

    def test_domain_work_item_query_and_order_fields_are_indexed(self) -> None:
        work_item = self.fields("npi_domain_work_item")
        for fieldname in (
            "tenant_id",
            "project_global_id",
            "stage_global_id",
            "kind",
            "owner_user_id",
            "due_at",
            "state_terminal",
        ):
            with self.subTest(fieldname=fieldname):
                self.assertEqual(work_item[fieldname].get("search_index"), 1)
        self.assertEqual(work_item["global_id"].get("unique"), 1)

    def test_command_owned_records_have_write_and_history_guards(self) -> None:
        for folder in COMMAND_OWNED_DOCTYPES:
            with self.subTest(folder=folder):
                source = (
                    DOCTYPE_ROOT / folder / f"{folder}.py"
                ).read_text(encoding="utf-8")
                self.assertIn("def before_insert(self)", source)
                self.assertIn("require_project_work_command_write()", source)
                self.assertIn("def on_trash(self)", source)
                self.assertIn("deny_project_work_history_delete()", source)

    def test_engineering_project_tracks_plan_revision_without_mutable_baseline(self) -> None:
        project = self.fields("npi_engineering_project")
        self.assertEqual(project["work_plan_revision"].get("default"), "0")
        self.assertEqual(project["work_plan_revision"].get("read_only"), 1)
        self.assertEqual(
            project["active_plan_baseline_global_id"].get("read_only"),
            1,
        )

    def test_data_ownership_keeps_project_work_npi_owned(self) -> None:
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(
            encoding="utf-8"
        )
        for object_name in ("ProjectTeam", "ProjectWorkPlan", "DomainWorkItem"):
            self.assertIn(f"  {object_name}:\n    owner_system: NPI_ONE", ownership)
        self.assertIn(
            "approval_authority: {owner: VERSIONED_APPROVAL_POLICY",
            ownership,
        )

    def test_project_work_sources_do_not_use_core_bypasses(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "apps/npi_core/npi_core/project_work"
            ).rglob("*.py")
        )
        sources += "\n" + "\n".join(
            path.read_text(encoding="utf-8")
            for folder in WORK_DOCTYPES
            for path in (DOCTYPE_ROOT / folder).glob("*.py")
        )
        for prohibited in (
            "ignore_" + "permissions",
            "frappe.db." + "sql",
            "ERPNEXT_URL",
        ):
            self.assertNotIn(prohibited, sources)


if __name__ == "__main__":
    unittest.main()
