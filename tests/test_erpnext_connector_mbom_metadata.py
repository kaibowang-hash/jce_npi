from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
DOCTYPE_ROOT = APP / "npi_erpnext_connector/doctype"


class ERPNextConnectorMbomMetadataTest(unittest.TestCase):
    def test_mbom_support_records_are_read_only_and_non_exportable(self) -> None:
        for directory in (
            "npi_erp_mbom_mapping",
            "npi_erp_mbom_operation_receipt",
        ):
            metadata = json.loads(
                (DOCTYPE_ROOT / directory / f"{directory}.json").read_text(
                    encoding="utf-8"
                )
            )
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
            self.assertNotIn(
                "NPI ERP MBOM Integration Service",
                {permission["role"] for permission in metadata["permissions"]},
            )

    def test_mbom_operation_has_no_generic_writer_submit_or_core_patch(self) -> None:
        production = "\n".join(
            (APP / name).read_text(encoding="utf-8")
            for name in (
                "mbom_api.py",
                "mbom_contract.py",
                "mbom_frappe.py",
                "mbom_config.py",
                "frappe_validation.py",
            )
        )
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.client." + "insert",
            "frappe.client." + "save",
            ".submit(",
            ".cancel(",
            "doctype = command",
            "getattr(frappe, command",
            "verify=False",
            "http://",
        ):
            self.assertNotIn(forbidden, production)
        update_source = ast.unparse(
            next(
                node
                for node in ast.walk(
                    ast.parse((APP / "mbom_frappe.py").read_text(encoding="utf-8"))
                )
                if isinstance(node, ast.FunctionDef) and node.name == "_execute_node"
            )
        )
        self.assertIn("int(bom.docstatus) != 0", update_source)
        self.assertIn("bom.set('items', [])", update_source)
        self.assertNotIn("bom.docstatus =", update_source)
        self.assertIn("CUSTOM_TEMPORARY_BOM_FIELD", production)
        self.assertNotIn("customFieldValues", production)
        self.assertIn('"owner": command.actor_user_id', production)
        self.assertIn("business_actor_is_enabled(command.actor_user_id", production)

    def test_mbom_service_identity_is_non_admin_website_user(self) -> None:
        tree = ast.parse((APP / "mbom_api.py").read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_service_identity"
        )
        source = ast.unparse(function)
        self.assertIn("actor in {'Guest', 'Administrator'}", source)
        self.assertIn("SERVICE_ROLE not in frappe.get_roles(actor)", source)
        self.assertIn("user.get('user_type') != 'Website User'", source)

    def test_mbom_migration_is_additive_and_bounded(self) -> None:
        patch_path = APP / "patches/v0_3/sync_mbom_doctypes.py"
        source = patch_path.read_text(encoding="utf-8")
        self.assertEqual(source.count('"npi_erp_mbom_'), 2)
        self.assertIn("for doctype in _MBOM_DOCTYPES", source)
        self.assertNotIn("delete", source.casefold())
        self.assertNotIn("drop", source.casefold())
        patches = (APP / "patches.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            patches,
            [
                "npi_erpnext_connector.patches.v0_3.sync_mbom_doctypes",
                "npi_erpnext_connector.patches.v0_4.sync_tool_asset_schema",
            ],
        )

    def test_new_visible_sources_have_direct_symmetric_chinese_translations(
        self,
    ) -> None:
        sources: set[str] = set()
        for path in (
            APP / "mbom_api.py",
            APP / "frappe_validation.py",
            DOCTYPE_ROOT / "npi_erp_mbom_mapping/npi_erp_mbom_mapping.py",
            DOCTYPE_ROOT
            / "npi_erp_mbom_operation_receipt/npi_erp_mbom_operation_receipt.py",
        ):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            sources.update(
                str(node.args[0].value)
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            )
        for directory in (
            "npi_erp_mbom_mapping",
            "npi_erp_mbom_operation_receipt",
        ):
            metadata = json.loads(
                (DOCTYPE_ROOT / directory / f"{directory}.json").read_text(
                    encoding="utf-8"
                )
            )
            sources.add(metadata["name"])
            for field in metadata["fields"]:
                sources.add(field["label"])
                if field["fieldtype"] == "Select":
                    sources.update(field["options"].splitlines())
        sources.add("NPI ERP MBOM Integration Service")
        catalogs = {}
        for language in ("zh", "zh-TW"):
            with (APP / f"translations/{language}.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(value for value in sources if not catalogs[language].get(value)),
                f"missing {language} connector translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
