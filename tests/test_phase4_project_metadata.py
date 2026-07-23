from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"


class Phase4ProjectMetadataTest(unittest.TestCase):
    def load_doctype(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def fields(self, metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            field["fieldname"]: field
            for field in metadata["fields"]  # type: ignore[index]
        }

    def test_top_level_doctypes_are_additive_system_manager_only(self) -> None:
        top_level = (
            "npi_project_template",
            "npi_project_template_version",
            "npi_engineering_project",
            "npi_gate_shell",
            "npi_project_idempotency",
            "npi_project_business_code",
        )
        for folder in top_level:
            with self.subTest(folder=folder):
                metadata = self.load_doctype(folder)
                permissions = metadata["permissions"]  # type: ignore[index]
                self.assertEqual({item["role"] for item in permissions}, {"System Manager"})
                self.assertTrue(all(not item.get("delete") for item in permissions))
                self.assertEqual(metadata.get("custom"), 0)

    def test_template_version_has_deterministic_identity_and_immutable_snapshot_fields(self) -> None:
        root = self.fields(self.load_doctype("npi_project_template"))
        root_metadata = self.load_doctype("npi_project_template")
        version_metadata = self.load_doctype("npi_project_template_version")
        version = self.fields(version_metadata)
        self.assertEqual(root_metadata.get("autoname"), "field:global_id")
        self.assertEqual(root["global_id"].get("unique"), 1)
        self.assertEqual(root["template_code"].get("unique"), 1)
        self.assertEqual(version_metadata.get("autoname"), "field:version_key")
        self.assertEqual(version["global_id"].get("unique"), 1)
        self.assertEqual(version["version_key"].get("unique"), 1)
        self.assertEqual(version["snapshot_hash"].get("read_only"), 1)
        self.assertEqual(version["optimistic_version"].get("read_only"), 1)
        self.assertEqual(version["reference_rules"].get("options"), "NPI Template Reference Rule")
        self.assertEqual(version["gates"].get("options"), "NPI Template Gate Definition")
        root_source = (
            DOCTYPE_ROOT / "npi_project_template/npi_project_template.py"
        ).read_text(encoding="utf-8")
        self.assertIn('(\"global_id\", \"template_code\")', root_source)
        self.assertIn("validate_template_code(self.template_code)", root_source)

        version_source = (
            DOCTYPE_ROOT
            / "npi_project_template_version/npi_project_template_version.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ProjectTemplateVersion(", version_source)
        self.assertIn("domain_template.snapshot_hash", version_source)
        self.assertIn("throw_domain_validation(error)", version_source)

    def test_project_and_gate_persist_stable_identity_exact_template_and_versions(self) -> None:
        project_metadata = self.load_doctype("npi_engineering_project")
        project = self.fields(project_metadata)
        gate_metadata = self.load_doctype("npi_gate_shell")
        gate = self.fields(gate_metadata)

        self.assertEqual(project_metadata.get("autoname"), "field:global_id")
        self.assertEqual(gate_metadata.get("autoname"), "field:global_id")
        self.assertEqual(project["global_id"].get("unique"), 1)
        self.assertNotIn("unique", project["business_code"])
        self.assertEqual(project["source_system"].get("options"), "NPI_ONE")
        self.assertEqual(project["source_system"].get("default"), "NPI_ONE")
        self.assertEqual(project["template_snapshot"].get("read_only"), 1)
        self.assertEqual(project["template_snapshot_hash"].get("reqd"), 1)
        self.assertEqual(project["optimistic_version"].get("default"), "1")
        self.assertEqual(gate["global_id"].get("unique"), 1)
        self.assertEqual(gate["shell_key"].get("unique"), 1)
        self.assertEqual(gate["template_gate_snapshot"].get("read_only"), 1)
        self.assertEqual(gate["optimistic_version"].get("default"), "1")

        for field in project.values():
            self.assertEqual(field.get("read_only"), 1)
        for field in gate.values():
            self.assertEqual(field.get("read_only"), 1)

    def test_reference_schema_is_typed_and_does_not_claim_erp_ownership(self) -> None:
        reference = self.fields(self.load_doctype("npi_project_reference"))
        self.assertEqual(
            reference["reference_type"]["options"],
            "customer\nproduct\npart\ntooling\norder",
        )
        self.assertEqual(reference["source_system"]["options"], "NPI_ONE\nERPNEXT")
        self.assertIn("source_object_id", reference)
        self.assertNotIn("source_object_type", reference)

    def test_idempotency_and_business_code_reservations_are_unique_append_only_hashes(self) -> None:
        idempotency_metadata = self.load_doctype("npi_project_idempotency")
        idempotency = self.fields(idempotency_metadata)
        reservation_metadata = self.load_doctype("npi_project_business_code")
        reservation = self.fields(reservation_metadata)

        self.assertEqual(idempotency_metadata.get("read_only"), 1)
        self.assertEqual(idempotency_metadata.get("autoname"), "field:record_id")
        self.assertEqual(idempotency["actor_key_hash"].get("unique"), 1)
        self.assertNotIn("idempotency_key", idempotency)
        self.assertEqual(idempotency["payload_hash"].get("reqd"), 1)
        self.assertEqual(idempotency["project_global_id"].get("reqd"), 1)

        self.assertEqual(reservation_metadata.get("read_only"), 1)
        self.assertEqual(
            reservation_metadata.get("autoname"),
            "field:reservation_key_hash",
        )
        self.assertEqual(reservation["reservation_key_hash"].get("unique"), 1)
        self.assertEqual(reservation["tenant_id"].get("reqd"), 1)
        self.assertEqual(reservation["business_code"].get("reqd"), 1)
        self.assertEqual(reservation["project_global_id"].get("reqd"), 1)

        for metadata in (idempotency_metadata, reservation_metadata):
            permissions = metadata["permissions"]  # type: ignore[index]
            self.assertEqual(permissions, [
                {
                    "role": "System Manager",
                    "read": 1,
                    "create": 1,
                    "export": 0,
                    "print": 0,
                    "email": 0,
                }
            ])
            self.assertTrue(all(field.get("read_only") == 1 for field in self.fields(metadata).values()))

    def test_command_owned_controllers_require_the_internal_write_guard(self) -> None:
        guarded = (
            "npi_engineering_project",
            "npi_gate_shell",
            "npi_project_idempotency",
            "npi_project_business_code",
        )
        for folder in guarded:
            with self.subTest(folder=folder):
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                    encoding="utf-8"
                )
                self.assertIn("def before_insert(self)", source)
                self.assertIn("require_project_command_write()", source)
                if folder in {"npi_engineering_project", "npi_gate_shell"}:
                    self.assertIn("def before_save(self)", source)
                    self.assertGreaterEqual(
                        source.count("require_project_command_write()"),
                        2,
                    )
        helper = (
            ROOT / "apps/npi_core/npi_core/project/frappe_validation.py"
        ).read_text(encoding="utf-8")
        self.assertIn('getattr(frappe.flags, "npi_project_command_write", False)', helper)
        self.assertIn("frappe.PermissionError", helper)

    def test_child_tables_deny_standalone_resource_mutation(self) -> None:
        guarded = (
            "npi_project_reference",
            "npi_template_gate_definition",
            "npi_template_reference_rule",
        )
        for folder in guarded:
            with self.subTest(folder=folder):
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                    encoding="utf-8"
                )
                self.assertIn("def before_insert(self)", source)
                self.assertIn("def before_save(self)", source)
                self.assertIn("def on_trash(self)", source)
                self.assertEqual(source.count("deny_standalone_child_write()"), 3)

        helper = (
            ROOT / "apps/npi_core/npi_core/project/frappe_validation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def deny_standalone_child_write()", helper)
        self.assertIn("frappe.PermissionError", helper)

    def test_controlled_history_has_controller_level_delete_guards(self) -> None:
        guarded = (
            "npi_engineering_project",
            "npi_gate_shell",
            "npi_project_idempotency",
            "npi_project_business_code",
            "npi_project_template_version",
        )
        for folder in guarded:
            with self.subTest(folder=folder):
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                    encoding="utf-8"
                )
                self.assertIn("def on_trash(self)", source)
                self.assertIn("deny_controlled_history_delete()", source)

        audit = (
            DOCTYPE_ROOT / "npi_audit_event/npi_audit_event.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def before_save(self)", audit)
        self.assertIn("if not self.is_new()", audit)
        self.assertIn("def on_trash(self)", audit)
        self.assertIn("deny_controlled_history_delete()", audit)

    def test_published_controller_enforces_immutability_and_no_core_bypass(self) -> None:
        version_source = (
            DOCTYPE_ROOT
            / "npi_project_template_version/npi_project_template_version.py"
        ).read_text(encoding="utf-8")
        self.assertIn('previous.publication_state == "published"', version_source)
        self.assertIn("assert_immutable_fields", version_source)

        phase4_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "apps/npi_core/npi_core/project"
            ).rglob("*.py")
        )
        for prohibited in (
            "ignore_" + "permissions",
            "frappe.db." + "sql",
            "ERPNEXT_URL",
        ):
            self.assertNotIn(prohibited, phase4_source)

    def test_repository_installs_no_production_template_fixture(self) -> None:
        hooks = (ROOT / "apps/npi_core/npi_core/hooks.py").read_text(encoding="utf-8")
        self.assertNotIn("fixtures", hooks)
        self.assertFalse((ROOT / "apps/npi_core/npi_core/fixtures").exists())

    def test_composed_validation_messages_translate_field_labels(self) -> None:
        helper = (
            ROOT / "apps/npi_core/npi_core/project/frappe_validation.py"
        ).read_text(encoding="utf-8")
        idempotency = (
            DOCTYPE_ROOT
            / "npi_project_idempotency/npi_project_idempotency.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_(field_label)", helper)
        self.assertNotIn("meta.get_label", helper)
        self.assertNotIn("meta.get_label", idempotency)

        for language in ("zh", "zh-TW"):
            with self.subTest(language=language):
                catalog_path = (
                    ROOT
                    / "apps/npi_core/npi_core/translations"
                    / f"{language}.csv"
                )
                with catalog_path.open(encoding="utf-8", newline="") as file:
                    catalog = {row[0]: row[1] for row in csv.reader(file)}
                uuid_message = catalog[
                    "{field} must be a valid UUID."
                ].format(
                    field=catalog["Global ID"]
                )
                hash_message = catalog[
                    "A hash field must be a lowercase SHA-256 value."
                ]
                self.assertNotIn("Global ID", uuid_message)
                self.assertNotIn("Actor and Key Hash", hash_message)


if __name__ == "__main__":
    unittest.main()
