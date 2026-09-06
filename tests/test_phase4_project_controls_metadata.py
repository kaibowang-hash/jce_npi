from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
CONTROL_DOCTYPES = (
    "npi_project_control_policy",
    "npi_project_control_policy_version",
    "npi_project_control_binding",
    "npi_project_health_assessment",
    "npi_project_activity_event",
    "npi_project_follower",
    "npi_project_learning",
    "npi_project_control_idempotency",
    "npi_my_work_assignment",
)
COMMAND_OWNED = CONTROL_DOCTYPES[2:]


class Phase4ProjectControlsMetadataTest(unittest.TestCase):
    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def fields(self, folder: str) -> dict[str, dict[str, object]]:
        return {
            field["fieldname"]: field
            for field in self.load(folder)["fields"]  # type: ignore[index]
        }

    def test_control_doctypes_are_additive_and_not_deletable(self) -> None:
        for folder in CONTROL_DOCTYPES:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata.get("custom"), 0)
                self.assertEqual(metadata.get("allow_rename"), 0)
                permissions = metadata["permissions"]  # type: ignore[index]
                self.assertTrue(
                    all(
                        not permission.get(operation)
                        for permission in permissions
                        for operation in ("delete", "export", "print", "email")
                    )
                )
                self.assertIn(
                    "System Manager",
                    {permission["role"] for permission in permissions},
                )

    def test_policy_is_reusable_versioned_and_contains_no_users(self) -> None:
        root = self.fields("npi_project_control_policy")
        version = self.fields("npi_project_control_policy_version")
        self.assertEqual(root["global_id"].get("unique"), 1)
        self.assertEqual(root["policy_code"].get("unique"), 1)
        self.assertEqual(version["version_key"].get("unique"), 1)
        self.assertEqual(
            version["publication_state"].get("options"),
            "draft\npublished",
        )
        for fieldname in (
            "authority_slots",
            "health_assessment_slot",
            "health_rules",
            "require_all_dimensions",
            "lifecycle_transitions",
            "snapshot",
            "snapshot_hash",
        ):
            self.assertIn(fieldname, version)
        self.assertNotIn("authority_users", version)
        self.assertNotIn("approver_user_ids", version)

    def test_binding_freezes_exact_policy_and_member_assignments(self) -> None:
        fields = self.fields("npi_project_control_binding")
        for fieldname in (
            "tenant_id",
            "project_global_id",
            "binding_version",
            "policy_global_id",
            "policy_version",
            "policy_snapshot_hash",
            "policy_snapshot",
            "authority_bindings",
            "project_version",
            "request_id",
            "trace_id",
            "binding_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(fieldname, fields)
        for fieldname in ("tenant_id", "project_global_id"):
            self.assertEqual(fields[fieldname].get("search_index"), 1)

    def test_activity_learning_and_follow_state_are_distinct(self) -> None:
        activity = self.fields("npi_project_activity_event")
        follower = self.fields("npi_project_follower")
        learning = self.fields("npi_project_learning")
        self.assertEqual(
            activity["event_type"].get("options"),
            "comment_added\nfollowed\nunfollowed\nhealth_assessed\n"
            "lifecycle_transition\nlearning_created",
        )
        self.assertIn("payload", activity)
        self.assertIn("payload_hash", activity)
        self.assertEqual(follower["follower_key"].get("unique"), 1)
        self.assertIn("active", follower)
        self.assertEqual(
            learning["kind"].get("options"),
            "retrospective\nlesson\ntemplate_improvement",
        )
        for fieldname in (
            "template_global_id",
            "template_version",
            "template_snapshot_hash",
            "record_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(fieldname, learning)

    def test_health_assessment_is_append_only_and_retains_exact_context(self) -> None:
        fields = self.fields("npi_project_health_assessment")
        for fieldname in (
            "tenant_id",
            "project_global_id",
            "binding_global_id",
            "policy_global_id",
            "policy_version",
            "policy_snapshot_hash",
            "actor_authority_slot",
            "actor_member_global_id",
            "actor_user_id",
            "actor_display_name",
            "assessed_at",
            "project_version",
            "request_id",
            "trace_id",
            "assessment_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(fieldname, fields)

    def test_my_work_index_is_a_typed_rebuildable_projection(self) -> None:
        metadata = self.load("npi_my_work_assignment")
        fields = self.fields("npi_my_work_assignment")
        self.assertEqual(metadata.get("read_only"), 1)
        self.assertEqual(fields["assignment_key"].get("unique"), 1)
        self.assertEqual(
            fields["source_type"].get("options"),
            "domain_work_item\ngate_review_assignment\n" "gate_review_invalidation",
        )
        self.assertEqual(
            fields["category"].get("options"),
            "task\napproval\nblocker\nrisk\nissue\ndecision",
        )
        for fieldname in (
            "actor_user_id",
            "project_global_id",
            "source_type",
            "source_global_id",
            "category",
            "due_at",
            "priority_scheme",
            "priority_value",
            "active",
        ):
            self.assertEqual(fields[fieldname].get("search_index"), 1)
        self.assertNotIn("domain_status", fields)
        self.assertNotIn("approval_authority", fields)

    def test_project_tracks_nullable_control_and_honest_health_refs(self) -> None:
        metadata = self.load("npi_engineering_project")
        fields = self.fields("npi_engineering_project")
        for fieldname in (
            "control_binding_global_id",
            "control_policy_global_id",
            "control_policy_version",
            "control_policy_snapshot_hash",
            "control_binding_version",
            "current_health_assessment_global_id",
            "current_health_status",
            "current_health_snapshot",
            "current_health_at",
        ):
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname].get("read_only"), 1)
        self.assertEqual(
            fields["current_health_status"].get("options"),
            "unassessed\nunavailable\ngreen\nyellow\nred",
        )
        self.assertEqual(
            fields["lifecycle_state"].get("options"),
            "draft\nproposed\nactive\non_hold\ncompleted\ncancelled",
        )
        transport = next(
            permission
            for permission in metadata["permissions"]  # type: ignore[index]
            if permission["role"] == "NPI API User"
        )
        self.assertEqual(
            transport,
            {
                "role": "NPI API User",
                "read": 0,
                "write": 1,
                "create": 0,
                "delete": 0,
                "export": 0,
                "print": 0,
                "email": 0,
            },
        )

    def test_command_owned_controllers_deny_generic_writes_and_deletes(self) -> None:
        for folder in COMMAND_OWNED:
            with self.subTest(folder=folder):
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                    encoding="utf-8"
                )
                self.assertIn("def before_insert(self)", source)
                self.assertIn("def before_save(self)", source)
                self.assertIn("def on_trash(self)", source)

    def test_no_policy_or_business_data_fixture_is_installed(self) -> None:
        hooks = (ROOT / "apps/npi_core/npi_core/hooks.py").read_text(encoding="utf-8")
        for doctype in (
            "NPI Project Control Policy",
            "NPI Project Control Policy Version",
            "NPI Project Control Binding",
            "NPI Project Health Assessment",
            "NPI Project Activity Event",
            "NPI Project Learning",
        ):
            self.assertNotIn(f'"doctype": "{doctype}"', hooks)

    def test_control_sources_do_not_use_core_or_database_bypasses(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "apps/npi_core/npi_core/project_controls").rglob("*.py")
        )
        sources += "\n" + "\n".join(
            path.read_text(encoding="utf-8")
            for folder in CONTROL_DOCTYPES
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
