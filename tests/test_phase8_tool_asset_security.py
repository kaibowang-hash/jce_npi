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
    def test_checkpoint_one_adds_no_route_worker_adapter_or_network_import(self) -> None:
        self.assertNotIn("ToolAssetExecutionRequestV2", API.read_text(encoding="utf-8"))
        self.assertNotIn("tool_asset_execution", HOOKS.read_text(encoding="utf-8"))
        prohibited_probe = ast.parse(".".join(("frappe", "db", "sql")) + "('select 1')")
        self.assertTrue(any(_is_direct_frappe_sql_call(node) for node in ast.walk(prohibited_probe)))
        for path in (MODULE / "execution_domain.py", MODULE / "config.py", MODULE / "execution_frappe_validation.py", MODULE / "doctype_base.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names}
            self.assertFalse({"requests", "httpx", "socket", "urllib.request"} & imports)
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("ignore_permissions", source)
            self.assertFalse(any(_is_direct_frappe_sql_call(node) for node in ast.walk(tree)))

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
