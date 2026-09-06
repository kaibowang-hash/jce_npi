from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
NPI_APP = ROOT / "apps/npi_integration/npi_integration"
DOCTYPE = (
    ERP_APP
    / "npi_erpnext_connector/doctype/npi_erp_change_implementation_summary"
)


class ERPNextConnectorEngineeringChangeMetadataTest(unittest.TestCase):
    def test_projection_is_immutable_read_only_and_actor_visible(self) -> None:
        metadata = json.loads(
            (DOCTYPE / "npi_erp_change_implementation_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(metadata["read_only"], 1)
        permissions = {row["role"]: row for row in metadata["permissions"]}
        self.assertEqual(
            set(permissions),
            {"System Manager", "NPI ERP Engineering Change Summary Viewer"},
        )
        self.assertTrue(all(row["read"] == 1 for row in permissions.values()))
        self.assertTrue(all(row["write"] == 0 for row in permissions.values()))
        self.assertTrue(all(row["create"] == 0 for row in permissions.values()))
        self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))
        fields = {field["fieldname"] for field in metadata["fields"]}
        self.assertIn("source_actor_user_id", fields)
        source = (ERP_APP / "engineering_change_frappe.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"owner": command.actor_user_id', source)
        self.assertIn("business_actor_context(command.actor_user_id)", source)

    def test_transport_and_receiver_are_operation_specific_and_default_closed(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ERP_APP / "engineering_change_api.py",
                ERP_APP / "engineering_change_frappe.py",
                ERP_APP / "engineering_change_contract.py",
                NPI_APP / "engineering_change/connector_runtime.py",
            )
        )
        self.assertIn("record_change_implementation_summary", sources)
        self.assertIn("receiver_is_disabled(frappe.conf)", sources)
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.client." + "insert",
            "frappe.client." + "save",
            "doctype = command",
            ".submit(",
            ".cancel(",
            "verify=False",
            "http://",
        ):
            self.assertNotIn(forbidden, sources)
        api = (ERP_APP / "engineering_change_api.py").read_text(encoding="utf-8")
        self.assertNotIn("allow_guest=True", api)
        self.assertIn(
            'SERVICE_ROLE = "NPI ERP Engineering Change Integration Service"',
            api,
        )
        connector = (NPI_APP / "engineering_change/connector_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(connector.count("session.post("), 1)
        self.assertIn("allow_redirects=False", connector)

    def test_schema_patch_hooks_roles_and_python_310_compatibility_are_exact(self) -> None:
        hooks = (NPI_APP / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("engineering_change.connector_runtime.resolve_profile", hooks)
        self.assertIn("engineering_change.connector_runtime.resolve_secret", hooks)
        self.assertIn(
            "engineering_change.connector_runtime.resolve_adapter_registry", hooks
        )
        patches = (ERP_APP / "patches.txt").read_text(encoding="utf-8")
        self.assertIn(
            "npi_erpnext_connector.patches.v0_9.sync_engineering_change_schema",
            patches,
        )
        roles = json.loads((ERP_APP / "fixtures/role.json").read_text(encoding="utf-8"))
        by_name = {role["name"]: role for role in roles}
        self.assertEqual(
            by_name["NPI ERP Engineering Change Integration Service"]["desk_access"],
            0,
        )
        self.assertEqual(
            by_name["NPI ERP Engineering Change Summary Viewer"]["desk_access"],
            1,
        )
        sources = "\n".join(path.read_text(encoding="utf-8") for path in ERP_APP.rglob("*.py"))
        self.assertNotIn("from datetime import UTC", sources)
        self.assertNotIn("from enum import StrEnum", sources)
        for path in ERP_APP.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_visible_sources_have_symmetric_chinese_translations(self) -> None:
        python_files = [
            ERP_APP / "engineering_change_api.py",
            ERP_APP / "engineering_change_frappe.py",
            ERP_APP / "frappe_validation.py",
            DOCTYPE / "npi_erp_change_implementation_summary.py",
        ]
        metadata = json.loads(
            (DOCTYPE / "npi_erp_change_implementation_summary.json").read_text(
                encoding="utf-8"
            )
        )
        sources = {metadata["name"]}
        for field in metadata["fields"]:
            if field.get("label"):
                sources.add(field["label"])
        for path in python_files:
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
        sources.update(
            {
                "NPI ERP Engineering Change Integration Service",
                "NPI ERP Engineering Change Summary Viewer",
            }
        )
        translated: dict[str, set[str]] = {}
        for locale in ("zh", "zh-TW"):
            with (ERP_APP / f"translations/{locale}.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.reader(handle))
            keys = [row[0] for row in rows if row]
            self.assertEqual(len(keys), len(set(keys)))
            translated[locale] = set(keys)
            self.assertFalse(sources - translated[locale])
        self.assertEqual(sources - translated["zh"], sources - translated["zh-TW"])


if __name__ == "__main__":
    unittest.main()
