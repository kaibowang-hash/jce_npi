from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
DOCTYPE_ROOT = APP / "npi_erpnext_connector/doctype"


class ERPNextConnectorToolAssetMetadataTest(unittest.TestCase):
    def test_support_records_are_read_only_non_exportable_and_asset_linked(
        self,
    ) -> None:
        for directory in (
            "npi_erp_tool_asset_mapping",
            "npi_erp_tool_asset_operation_receipt",
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
            asset_links = {
                field["fieldname"]
                for field in metadata["fields"]
                if field.get("fieldtype") == "Link" and field.get("options") == "Asset"
            }
            self.assertEqual(asset_links, {"formal_asset_id"})

    def test_asset_custom_fields_are_additive_fixed_and_owned_by_npi(self) -> None:
        patch = (APP / "patches/v0_4/sync_tool_asset_schema.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(patch)
        fields = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith("custom_npi_")
        }
        self.assertEqual(
            fields,
            {
                "custom_npi_source_section",
                "custom_npi_source_stream_key",
                "custom_npi_tooling_master_title",
                "custom_npi_physical_set_serial",
                "custom_npi_tooling_requirement_kind",
                "custom_npi_source_tooling_revision",
                "custom_npi_acceptance_evidence_reference",
            },
        )
        self.assertIn(
            'create_custom_fields({"Asset": list(_ASSET_FIELDS)}, update=False)', patch
        )
        self.assertNotIn("delete", patch.casefold())
        self.assertNotIn("drop", patch.casefold())
        self.assertNotIn("Property Setter", patch)

    def test_operation_is_asset_only_draft_only_and_has_no_generic_escape(self) -> None:
        production = "\n".join(
            (APP / name).read_text(encoding="utf-8")
            for name in (
                "tool_asset_api.py",
                "tool_asset_contract.py",
                "tool_asset_frappe.py",
                "tool_asset_config.py",
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
            'get_doc("Mold"',
            'get_doc("Asset Movement"',
            'get_doc("Asset Repair"',
        ):
            self.assertNotIn(forbidden, production)
        update = ast.unparse(
            next(
                node
                for node in ast.walk(
                    ast.parse(
                        (APP / "tool_asset_frappe.py").read_text(encoding="utf-8")
                    )
                )
                if isinstance(node, ast.FunctionDef) and node.name == "_update_asset"
            )
        )
        self.assertIn("int(asset.docstatus) != 0", update)
        for erp_owned_field in (
            "location",
            "company",
            "item_code",
            "asset_owner",
            "custodian",
            "gross_purchase_amount",
        ):
            self.assertNotIn(f"asset.{erp_owned_field} =", update)
        create = ast.unparse(
            next(
                node
                for node in ast.walk(
                    ast.parse(
                        (APP / "tool_asset_frappe.py").read_text(encoding="utf-8")
                    )
                )
                if isinstance(node, ast.FunctionDef) and node.name == "_create_asset"
            )
        )
        self.assertIn(
            "values['net_purchase_amount'] = profile.purchase_amount",
            create,
        )
        self.assertIn(
            "values['gross_purchase_amount'] = profile.purchase_amount",
            create,
        )
        self.assertIn("'owner': command.actor_user_id", create)
        self.assertIn("business_actor_is_enabled(command.actor_user_id", production)

    def test_service_identity_and_scopes_are_separate_and_default_closed(self) -> None:
        source = (APP / "tool_asset_api.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        service = ast.unparse(
            next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "_service_identity"
            )
        )
        self.assertIn("actor in {'Guest', 'Administrator'}", service)
        self.assertIn("SERVICE_ROLE not in frappe.get_roles(actor)", service)
        self.assertIn("user.get('user_type') != 'Website User'", service)
        config = (APP / "tool_asset_config.py").read_text(encoding="utf-8")
        self.assertIn("npi_erp_connector_tool_asset_create_disabled", config)
        self.assertIn("npi_erp_connector_tool_asset_update_disabled", config)
        self.assertIn("configuration.get(key) is False", config)

    def test_new_visible_sources_have_direct_symmetric_chinese_translations(
        self,
    ) -> None:
        sources: set[str] = set()
        for path in (
            APP / "tool_asset_api.py",
            APP / "frappe_validation.py",
            DOCTYPE_ROOT / "npi_erp_tool_asset_mapping/npi_erp_tool_asset_mapping.py",
            DOCTYPE_ROOT
            / "npi_erp_tool_asset_operation_receipt/npi_erp_tool_asset_operation_receipt.py",
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
            "npi_erp_tool_asset_mapping",
            "npi_erp_tool_asset_operation_receipt",
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
        patch_source = ast.parse(
            (APP / "patches/v0_4/sync_tool_asset_schema.py").read_text(encoding="utf-8")
        )
        for node in ast.walk(patch_source):
            if isinstance(node, ast.Dict) and any(
                isinstance(key, ast.Constant) and key.value == "label"
                for key in node.keys
            ):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "label"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        sources.add(value.value)
        sources.add("NPI ERP Tool Asset Integration Service")
        sources.update(
            {
                "new_tool",
                "customer_owned_intake",
                "copy_or_additional_set",
                "modification",
                "repair",
                "capacity_need",
            }
        )
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
                f"missing {language} Tool Asset translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
