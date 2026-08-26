from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps"
ITEM_ROOT = APP_ROOT / "npi_integration/npi_integration/item_publish"
MBOM_ROOT = APP_ROOT / "npi_integration/npi_integration/mbom_publish"
TOOL_ASSET_ROOT = APP_ROOT / "npi_integration/npi_integration/tool_asset_request"
PROJECTION_ROOT = APP_ROOT / "npi_integration/npi_integration/projections"
EXPECTED_PERMISSION_CALLS = Counter(
    {
        (
            str(ITEM_ROOT / "frappe_validation.py"),
            "insert_item_support_document",
            "document",
            "insert",
        ): 1,
        (
            str(ITEM_ROOT / "frappe_validation.py"),
            "save_item_support_document",
            "document",
            "save",
        ): 1,
        (
            str(MBOM_ROOT / "frappe_validation.py"),
            "insert_mbom_support_document",
            "document",
            "insert",
        ): 1,
        (
            str(MBOM_ROOT / "frappe_validation.py"),
            "save_mbom_support_document",
            "document",
            "save",
        ): 1,
        (
            str(TOOL_ASSET_ROOT / "execution_frappe_validation.py"),
            "insert_tool_asset_support_document",
            "document",
            "insert",
        ): 1,
        (
            str(TOOL_ASSET_ROOT / "execution_frappe_validation.py"),
            "save_tool_asset_support_document",
            "document",
            "save",
        ): 1,
        (
            str(TOOL_ASSET_ROOT / "execution_frappe_validation.py"),
            "insert_tool_asset_audit_document",
            "document",
            "insert",
        ): 1,
        (
            str(PROJECTION_ROOT / "frappe_validation.py"),
            "insert_projection_support_document",
            "document",
            "insert",
        ): 1,
        (
            str(PROJECTION_ROOT / "frappe_validation.py"),
            "save_projection_support_document",
            "document",
            "save",
        ): 1,
    }
)


def _function_for(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = parents.get(current)
    return None


def _scan_permission_paths(paths: list[Path] | tuple[Path, ...]):
    calls: list[tuple[str, str, str, str]] = []
    violations: list[str] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            violations.append(f"{path}: syntax error: {error}")
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "ignore_permissions":
                violations.append(f"{path}:{node.lineno}: attribute bypass")
            if isinstance(node, ast.Name) and node.id == "ignore_permissions":
                violations.append(f"{path}:{node.lineno}: name bypass")
            if isinstance(node, ast.arg) and node.arg == "ignore_permissions":
                violations.append(f"{path}:{node.lineno}: parameter bypass")
            if isinstance(node, ast.Constant) and node.value == "ignore_permissions":
                violations.append(f"{path}:{node.lineno}: string or dict-key bypass")
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"insert", "save"}:
                if any(keyword.arg is None for keyword in node.keywords):
                    violations.append(f"{path}:{node.lineno}: dynamic insert/save forwarding")
            permission_keywords = [
                keyword
                for keyword in node.keywords
                if keyword.arg == "ignore_permissions"
            ]
            if not permission_keywords:
                continue
            function = _function_for(node, parents)
            function_name = (
                function.name
                if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
                else ""
            )
            receiver = (
                node.func.value.id
                if isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                else ""
            )
            method = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            calls.append((str(path), function_name, receiver, method))
            if len(permission_keywords) != 1:
                violations.append(f"{path}:{node.lineno}: duplicate bypass keyword")
            value = permission_keywords[0].value
            if not isinstance(value, ast.Constant) or value.value is not True:
                violations.append(f"{path}:{node.lineno}: non-literal true bypass")
            if (str(path), function_name, receiver, method) not in EXPECTED_PERMISSION_CALLS:
                violations.append(f"{path}:{node.lineno}: unapproved bypass call")
    return calls, violations


class Phase8ItemPublishSecurityTest(unittest.TestCase):
    def test_ignore_permissions_is_exactly_nine_controlled_calls(self) -> None:
        calls, violations = _scan_permission_paths(tuple(APP_ROOT.rglob("*.py")))
        self.assertEqual(violations, [])
        self.assertEqual(Counter(calls), EXPECTED_PERMISSION_CALLS)

    def test_permission_ast_rejects_unsafe_temporary_variants(self) -> None:
        variants = {
            "wrong_path": "def insert_item_support_document(document):\n    return document.insert(ignore_permissions=True)\n",
            "wrong_function": "def other(document):\n    return document.insert(ignore_permissions=True)\n",
            "wrong_receiver": "def insert_item_support_document(document):\n    return row.insert(ignore_permissions=True)\n",
            "non_literal": "def insert_item_support_document(document, flag):\n    return document.insert(ignore_permissions=flag)\n",
            "duplicate": "def insert_item_support_document(document):\n    document.insert(ignore_permissions=True)\n    document.insert(ignore_permissions=True)\n",
            "attribute": "def write(document):\n    return flags.ignore_permissions\n",
            "string": "value = 'ignore_permissions'\n",
            "dict_key": "value = {'ignore_permissions': True}\n",
            "parameter": "def write(ignore_permissions):\n    return None\n",
            "dynamic_insert": "def write(document, kwargs):\n    return document.insert(**kwargs)\n",
            "dynamic_save": "def write(document, kwargs):\n    return document.save(**kwargs)\n",
        }
        with tempfile.TemporaryDirectory() as temporary:
            for name, source in variants.items():
                path = Path(temporary) / f"{name}.py"
                path.write_text(source, encoding="utf-8")
                calls, violations = _scan_permission_paths((path,))
                with self.subTest(name=name):
                    self.assertTrue(
                        violations or Counter(calls) != EXPECTED_PERMISSION_CALLS,
                        f"unsafe permission bypass variant was accepted: {name}",
                    )

    def test_support_doctype_writes_have_no_dynamic_insert_or_save_forwarding(self) -> None:
        for path in APP_ROOT.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"insert", "save"}
                ):
                    continue
                self.assertFalse(
                    any(keyword.arg is None for keyword in node.keywords),
                    f"dynamic insert/save forwarding is forbidden in {path}:{node.lineno}",
                )

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
