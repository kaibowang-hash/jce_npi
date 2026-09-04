from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apps/npi_integration/npi_integration/tool_asset_request"
API = ROOT / "apps/npi_integration/npi_integration/tool_asset_request_api.py"
HOOKS = ROOT / "apps/npi_integration/npi_integration/hooks.py"


def _is_direct_frappe_sql_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sql"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "db"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "frappe"
    )


class Phase8ToolAssetSecurityTest(unittest.TestCase):
    def test_checkpoint_three_worker_is_closed_default_off_network_free_and_direct_sql_free(self) -> None:
        api_source = API.read_text(encoding="utf-8")
        self.assertIn("create_tool_asset_execution_request", api_source)
        self.assertIn("update_tool_asset_execution_request", api_source)
        api_tree = ast.parse(api_source, filename=str(API))
        api_imports = {
            node.names[0].name
            for node in ast.walk(api_tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
        }
        self.assertFalse({"requests", "httpx", "socket", "urllib.request"} & api_imports)
        hooks = HOOKS.read_text(encoding="utf-8")
        self.assertIn("recover_tool_asset_outbox_messages", hooks)
        self.assertIn("npi_tool_asset_execution_profile_resolver", hooks)
        self.assertIn("npi_tool_asset_adapter_registry", hooks)
        prohibited_probe = ast.parse(".".join(("frappe", "db", "sql")) + "('select 1')")
        self.assertTrue(any(_is_direct_frappe_sql_call(node) for node in ast.walk(prohibited_probe)))
        for path in (MODULE / "execution_domain.py", MODULE / "config.py", MODULE / "execution_frappe_validation.py", MODULE / "doctype_base.py", MODULE / "diagnostics.py", MODULE / "frappe_repository.py", MODULE / "adapters.py", MODULE / "worker.py", MODULE / "worker_repository.py", MODULE / "runtime_fixture.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names}
            self.assertFalse({"requests", "httpx", "socket", "urllib.request"} & imports)
            self.assertFalse(any(_is_direct_frappe_sql_call(node) for node in ast.walk(tree)))

    def test_predecessor_diagnostic_is_response_neutral_and_value_closed(self) -> None:
        source = (MODULE / "diagnostics.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        records = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "record_safe_diagnostic"
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(
            {keyword.arg for keyword in records[0].keywords},
            {"code", "title", "exception_type", "trace_id"},
        )
        for forbidden in (
            "str(error)",
            "repr(error)",
            "traceback",
            "request_fields",
            "payload_hash",
            "asset_id",
        ):
            self.assertNotIn(forbidden, source)

    def test_ignore_permissions_is_capability_bound_and_cannot_reach_product_repository(self) -> None:
        validation = MODULE / "execution_frappe_validation.py"
        tree = ast.parse(validation.read_text(encoding="utf-8"), filename=str(validation))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and any(
                keyword.arg == "ignore_permissions"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
        ]
        self.assertEqual(len(calls), 3)
        allowed = {
            "insert_tool_asset_support_document",
            "save_tool_asset_support_document",
            "insert_tool_asset_audit_document",
        }
        for call in calls:
            current: ast.AST | None = call
            while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                current = parents.get(current)
            self.assertIsInstance(current, ast.FunctionDef)
            self.assertIn(current.name, allowed)
        repository = (MODULE / "frappe_repository.py").read_text(encoding="utf-8")
        self.assertNotIn("ignore_permissions", repository)

    def test_no_metadata_grants_business_crud_or_installs_target_values(self) -> None:
        root = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
        for folder in root.glob("npi_tool_asset_*"):
            metadata = json.loads((folder / f"{folder.name}.json").read_text(encoding="utf-8"))
            self.assertNotIn("fixtures", metadata)
            self.assertNotIn("records", metadata)
        payload = "\n".join((MODULE / name).read_text(encoding="utf-8") for name in ("execution_domain.py", "config.py"))
        for forbidden in ("company=", "asset_category=", "location=", "depreciation", "production.erpnext", "password=", "api_key="):
            self.assertNotIn(forbidden, payload.casefold())

    def test_default_configuration_is_empty_and_production_contact_has_no_seam(self) -> None:
        source = (MODULE / "config.py").read_text(encoding="utf-8")
        self.assertIn("def default_tool_asset_execution_profiles()", source)
        self.assertIn("return ()", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("frappe.conf", source)


if __name__ == "__main__":
    unittest.main()
