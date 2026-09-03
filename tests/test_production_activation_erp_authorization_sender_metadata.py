from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
DOCTYPE = (
    APP
    / "npi_erpnext_connector/doctype/npi_erp_authorization_delivery"
)


class ProductionActivationERPAuthorizationSenderMetadataTest(unittest.TestCase):
    def test_app_is_independent_default_disabled_and_operation_specific(self) -> None:
        hooks = (APP / "hooks.py").read_text(encoding="utf-8")
        config = (APP / "config.py").read_text(encoding="utf-8")
        transport = (APP / "transport.py").read_text(encoding="utf-8")
        pyproject = (APP.parent / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('app_name = "npi_erpnext_connector"', hooks)
        self.assertIn("required_apps = []", hooks)
        self.assertNotIn("npi_core", "\n".join((hooks, config, transport, pyproject)))
        self.assertIn('DISABLED_KEY = "npi_erp_authorization_sender_disabled"', config)
        self.assertIn("configuration.get(DISABLED_KEY) is False", config)
        self.assertIn(
            'ENDPOINT_PATH = "/api/npi/v1/integration/erpnext/user-authorization"',
            config,
        )
        self.assertIn('TOKEN_ENV = "NPI_ERP_AUTHORIZATION_TOKEN"', config)
        self.assertIn("allow_redirects=False", transport)
        self.assertIn("timeout=(3.05, 10.0)", transport)
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.client." + "insert",
            "frappe.client." + "save",
            "verify=False",
            "http://",
            "site_config.json",
            "new_password",
            "password=",
        ):
            self.assertNotIn(forbidden, "\n".join((hooks, config, transport, pyproject)))

    def test_hooks_cover_user_changes_recovery_and_reconciliation(self) -> None:
        hooks = (APP / "hooks.py").read_text(encoding="utf-8")
        self.assertIn('"User": {', hooks)
        self.assertIn('"User Permission": {', hooks)
        self.assertEqual(hooks.count('"on_trash":'), 2)
        self.assertIn('"*/5 * * * *"', hooks)
        self.assertIn("recover_pending_deliveries", hooks)
        self.assertIn("reconcile_all_users", hooks)

        repository = (APP / "frappe_repository.py").read_text(encoding="utf-8")
        self.assertIn('["not in", ["Administrator", "Guest"]]', repository)
        self.assertIn('group_by="target_user_id"', repository)

    def test_delivery_metadata_is_read_only_non_exportable_and_immutable(self) -> None:
        metadata = json.loads(
            (DOCTYPE / "npi_erp_authorization_delivery.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(metadata["name"], "NPI ERP Authorization Delivery")
        self.assertEqual(metadata["autoname"], "field:event_id")
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
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        self.assertTrue(fields["event_id"]["unique"])
        self.assertTrue(fields["stream_key"]["unique"])
        self.assertTrue(fields["event_json"]["hidden"])
        self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
        controller = (DOCTYPE / "npi_erp_authorization_delivery.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("require_delivery_write()", controller)
        self.assertIn("deny_delivery_delete()", controller)
        self.assertIn("canonical_hash(event) != self.event_hash", controller)

    def test_only_two_permission_bypasses_are_capability_wrapped(self) -> None:
        validation = (APP / "frappe_validation.py").read_text(encoding="utf-8")
        repository = (APP / "frappe_repository.py").read_text(encoding="utf-8")
        worker = (APP / "worker.py").read_text(encoding="utf-8")
        self.assertEqual(validation.count("ignore_permissions=True"), 2)
        self.assertNotIn("ignore_permissions", repository)
        self.assertNotIn("ignore_permissions", worker)
        tree = ast.parse(validation)
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("_authorize", ast.unparse(functions["insert_delivery_document"]))
        self.assertIn("_authorize", ast.unparse(functions["save_delivery_document"]))

    def test_visible_strings_have_symmetric_direct_chinese_translations(self) -> None:
        metadata = json.loads(
            (DOCTYPE / "npi_erp_authorization_delivery.json").read_text(
                encoding="utf-8"
            )
        )
        sources = {metadata["name"]}
        sources.update(field["label"] for field in metadata["fields"])
        sources.update(
            option
            for field in metadata["fields"]
            if field.get("fieldtype") == "Select"
            for option in str(field.get("options", "")).splitlines()
            if option
        )
        for path in (DOCTYPE / "npi_erp_authorization_delivery.py", APP / "worker.py", APP / "frappe_validation.py"):
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
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (APP / f"translations/{language}.csv").open(
                encoding="utf-8",
                newline="",
            ) as stream:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(stream)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source))
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
