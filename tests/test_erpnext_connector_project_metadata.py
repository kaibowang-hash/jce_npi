from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
DOCTYPE_ROOT = APP / "npi_erpnext_connector/doctype"


class ERPNextConnectorProjectMetadataTest(unittest.TestCase):
    def test_project_support_records_are_immutable_read_only_and_non_exportable(self) -> None:
        for directory in (
            "npi_erp_project_delivery",
            "npi_erp_project_mapping",
        ):
            metadata = json.loads(
                (DOCTYPE_ROOT / directory / f"{directory}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(metadata["read_only"], 1)
            self.assertTrue(
                all(field.get("read_only") == 1 for field in metadata["fields"])
            )
            permission = metadata["permissions"][0]
            self.assertEqual(permission["role"], "System Manager")
            for operation in (
                "write",
                "create",
                "delete",
                "export",
                "print",
                "email",
                "share",
            ):
                self.assertEqual(permission[operation], 0)

    def test_project_hook_and_reconciliation_are_default_disabled_and_bounded(self) -> None:
        hooks = (APP / "hooks.py").read_text(encoding="utf-8")
        config = (APP / "project_config.py").read_text(encoding="utf-8")
        repository = (APP / "project_repository.py").read_text(encoding="utf-8")
        module = ast.parse(hooks)
        doc_events = next(
            node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "doc_events"
                for target in node.targets
            )
        )
        project_hook = ast.literal_eval(doc_events)["Project"]
        self.assertEqual(
            project_hook,
            {
                "after_insert": (
                    "npi_erpnext_connector.hooks_runtime.queue_project_create"
                )
            },
        )
        self.assertIn('"*/15 * * * *"', hooks)
        self.assertIn("reconcile_projects", hooks)
        self.assertIn('DISABLED_KEY = "npi_erp_project_sender_disabled"', config)
        self.assertIn("configuration.get(DISABLED_KEY) is False", config)
        self.assertIn("MAX_RECONCILIATION_PROJECTS = 1_000", repository)
        self.assertIn('filters={"status": "Open"}', repository)

    def test_project_transport_is_operation_specific_and_secrets_are_runtime_only(self) -> None:
        sources = "\n".join(
            (APP / name).read_text(encoding="utf-8")
            for name in (
                "project_config.py",
                "project_domain.py",
                "project_transport.py",
                "project_repository.py",
                "project_worker.py",
            )
        )
        self.assertIn(
            'EVENT_PATH = "/api/npi/v1/integration/erpnext/project-source-events"',
            sources,
        )
        self.assertIn('SIGNING_SECRET_ENV = "NPI_ERP_PROJECT_SIGNING_SECRET"', sources)
        self.assertIn('STATUS_TOKEN_ENV = "NPI_ERP_AUTHORIZATION_TOKEN"', sources)
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.client." + "insert",
            "frappe.client." + "save",
            "verify=False",
            "http://",
            "site_config.json",
            "password=",
        ):
            self.assertNotIn(forbidden, sources)
        validation = ast.parse(
            (APP / "frappe_validation.py").read_text(encoding="utf-8")
        )
        functions = {
            node.name: node
            for node in ast.walk(validation)
            if isinstance(node, ast.FunctionDef)
        }
        for function in (
            "insert_project_delivery_document",
            "save_project_delivery_document",
        ):
            self.assertIn(
                "_authorize_project_support",
                ast.unparse(functions[function]),
            )

    def test_project_schema_has_install_and_forward_patch_paths(self) -> None:
        install = (APP / "install.py").read_text(encoding="utf-8")
        patches = (APP / "patches.txt").read_text(encoding="utf-8")
        for doctype in (
            "npi_erp_project_delivery",
            "npi_erp_project_mapping",
        ):
            self.assertIn(f'"{doctype}"', install)
        self.assertIn(
            "npi_erpnext_connector.patches.v0_5.sync_project_schema",
            patches,
        )


if __name__ == "__main__":
    unittest.main()
