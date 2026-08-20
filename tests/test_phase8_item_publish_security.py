from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ITEM_ROOT = ROOT / "apps/npi_integration/npi_integration/item_publish"


class Phase8ItemPublishSecurityTest(unittest.TestCase):
    def test_ignore_permissions_is_confined_to_the_two_support_write_seams(self) -> None:
        allowed = {
            (
                ITEM_ROOT / "frappe_validation.py",
                "insert_item_support_document",
            ),
            (
                ITEM_ROOT / "frappe_validation.py",
                "save_item_support_document",
            ),
        }
        for path in ITEM_ROOT.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            parents: dict[ast.AST, ast.AST] = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                keyword = next(
                    (
                        value
                        for value in node.keywords
                        if value.arg == "ignore_permissions"
                    ),
                    None,
                )
                if keyword is None:
                    continue
                function: ast.FunctionDef | ast.AsyncFunctionDef | None = None
                current: ast.AST | None = node
                while current is not None:
                    if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        function = current
                        break
                    current = parents.get(current)
                self.assertIsNotNone(function)
                self.assertEqual(
                    keyword.value.__class__, ast.Constant,
                    f"ignore_permissions must be a literal in {path}",
                )
                self.assertIs(
                    keyword.value.value,
                    True,
                    f"support seam may only use ignore_permissions=True in {path}",
                )
                self.assertIn((path, function.name), allowed)

    def test_support_doctype_writes_have_no_unbounded_raw_insert_or_save(self) -> None:
        allowed = {
            (ITEM_ROOT / "frappe_validation.py", "insert_item_support_document"),
            (ITEM_ROOT / "frappe_validation.py", "save_item_support_document"),
            (ITEM_ROOT / "worker_repository.py", "_append_audit"),
        }
        for path in ITEM_ROOT.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            parents: dict[ast.AST, ast.AST] = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"insert", "save"}
                ):
                    continue
                function: ast.FunctionDef | ast.AsyncFunctionDef | None = None
                current: ast.AST | None = node
                while current is not None:
                    if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        function = current
                        break
                    current = parents.get(current)
                self.assertIsNotNone(function)
                self.assertIn((path, function.name), allowed)

    def test_execution_has_no_administrator_or_fallback_worker_identity(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in ITEM_ROOT.glob("*.py")
        )
        self.assertNotIn("SYSTEM_SERVICE_USER", source)
        self.assertNotIn('"Administrator"', source)
        self.assertNotIn("'Administrator'", source)
        self.assertNotIn("npi-item-publish-worker", source)


if __name__ == "__main__":
    unittest.main()
