from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
DOCTYPE_ROOT = APP / "npi_erpnext_connector/doctype"


class ERPNextConnectorItemMetadataTest(unittest.TestCase):
    def test_item_support_records_are_read_only_and_non_exportable(self) -> None:
        for directory in (
            "npi_erp_item_mapping",
            "npi_erp_item_operation_receipt",
        ):
            path = DOCTYPE_ROOT / directory / f"{directory}.json"
            metadata = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["read_only"], 1)
            self.assertEqual(
                metadata["permissions"],
                [
                    {
                        "role": "System Manager",
                        "read": 1,
                        "write": 0,
                        "create": 0,
                        "delete": 0,
                        "export": 0,
                        "print": 0,
                        "email": 0,
                        "share": 0,
                    }
                ],
            )
            self.assertTrue(
                all(field.get("read_only") == 1 for field in metadata["fields"])
            )

    def test_service_role_has_no_desk_or_doctype_permissions(self) -> None:
        roles = json.loads((APP / "fixtures/role.json").read_text(encoding="utf-8"))
        by_name = {role["name"]: role for role in roles}
        self.assertEqual(
            set(by_name),
            {
                "NPI ERP Integration Service",
                "NPI ERP MBOM Integration Service",
                "NPI ERP Tool Asset Integration Service",
                "NPI ERP Trial Summary Integration Service",
                "NPI ERP Trial Summary Viewer",
                "NPI ERP Engineering Change Integration Service",
                "NPI ERP Engineering Change Summary Viewer",
            },
        )
        for name, role in by_name.items():
            self.assertEqual(role["role_name"], name)
            self.assertEqual(
                role["desk_access"],
                1 if name.endswith("Viewer") else 0,
            )
            self.assertEqual(role["disabled"], 0)
            self.assertEqual(role["is_custom"], 0)
        for path in DOCTYPE_ROOT.glob("npi_erp_item_*/*.json"):
            permissions = json.loads(path.read_text(encoding="utf-8"))["permissions"]
            self.assertNotIn(
                "NPI ERP Integration Service", {row["role"] for row in permissions}
            )

    def test_operation_has_no_generic_target_or_database_escape(self) -> None:
        sources = "\n".join(
            (APP / name).read_text(encoding="utf-8")
            for name in (
                "item_api.py",
                "item_frappe.py",
                "frappe_validation.py",
            )
        )
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.client." + "insert",
            "frappe.client." + "save",
            "doctype = command",
            "getattr(frappe, command",
            "verify=False",
            "http://",
        ):
            self.assertNotIn(forbidden, sources)
        tree = ast.parse((APP / "item_api.py").read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        service_source = ast.unparse(functions["_service_identity"])
        self.assertIn("actor in {'Guest', 'Administrator'}", service_source)
        self.assertIn("SERVICE_ROLE not in frappe.get_roles(actor)", service_source)
        self.assertIn("user.get('user_type') != 'Website User'", service_source)

    def test_connector_source_is_python_310_compatible(self) -> None:
        pyproject = (APP.parent / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('requires-python = ">=3.10"', pyproject)
        sources = "\n".join(
            path.read_text(encoding="utf-8") for path in APP.rglob("*.py")
        )
        self.assertNotIn("from datetime import UTC", sources)
        self.assertNotIn("from enum import StrEnum", sources)

    def test_capability_versions_follow_the_installed_app_version(self) -> None:
        package = (APP / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.9.0"', package)
        for module in ("item_api.py", "mbom_api.py", "tool_asset_api.py"):
            source = (APP / module).read_text(encoding="utf-8")
            self.assertIn("from npi_erpnext_connector import __version__", source)
            self.assertIn('"appVersion": __version__', source)
            self.assertNotIn('"appVersion": "0.5.0"', source)

    def test_engineering_update_does_not_overwrite_erp_owned_item_fields(self) -> None:
        tree = ast.parse((APP / "item_frappe.py").read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        update_source = ast.unparse(functions["_engineering_update_values"])
        self.assertIn("description", update_source)
        for erp_owned_field in ("stock_uom", "item_group", "item_name", "item_code"):
            self.assertNotIn(erp_owned_field, update_source)

    def test_formal_identity_and_version_come_from_the_inserted_erpnext_item(
        self,
    ) -> None:
        source = (APP / "item_frappe.py").read_text(encoding="utf-8")
        self.assertNotIn("item_code_prefix", source)
        self.assertNotIn("command.engineering_item_id}", source)
        self.assertIn('"naming_series": profile.erp_naming_series', source)
        self.assertIn("if item_code == pending_item_code", source)
        self.assertIn(
            'item = frappe.get_doc("Item", item_code, for_update=True)', source
        )
        self.assertIn("item.item_code = item_code", source)
        self.assertIn("item_code = _formal_item_code(item)", source)
        self.assertIn(
            'frappe.db.get_value("Item", item_code, "modified")',
            source,
        )
        self.assertIn('"owner": command.actor_user_id', source)
        api = (APP / "item_api.py").read_text(encoding="utf-8")
        self.assertIn("business_actor_is_enabled(command.actor_user_id", api)

    def test_install_hook_reloads_only_connector_doctypes(self) -> None:
        hooks = (APP / "hooks.py").read_text(encoding="utf-8")
        self.assertIn(
            'after_install = "npi_erpnext_connector.install.after_install"',
            hooks,
        )
        install = (APP / "install.py").read_text(encoding="utf-8")
        tree = ast.parse(install)
        reload_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "reload_doc"
        ]
        self.assertEqual(len(reload_calls), 1)
        self.assertIn("for doctype in _CONNECTOR_DOCTYPES", install)
        self.assertEqual(install.count('"npi_erp_'), 13)
        self.assertIn('"npi_erpnext_connector"', install)


if __name__ == "__main__":
    unittest.main()
