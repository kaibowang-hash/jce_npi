from __future__ import annotations

import ast
import csv
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "apps/npi_integration/npi_integration/integration_operations"
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase8IntegrationOperationsMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_integration_action_receipt",
        "npi_integration_reconciliation_observation",
    )

    @staticmethod
    def load(folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def test_two_additive_support_doctypes_are_read_only_and_install_no_rows(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata["autoname"], "field:global_id")
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["track_changes"], 0)
                self.assertEqual(metadata["read_only"], 1)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(
                    all(field.get("read_only") == 1 for field in metadata["fields"])
                )
                for permission in metadata["permissions"]:
                    for action in (
                        "write",
                        "create",
                        "delete",
                        "export",
                        "print",
                        "email",
                    ):
                        self.assertFalse(permission.get(action, 0))

    def test_links_resolve_and_reconciliation_links_only_the_exact_action_receipt(self) -> None:
        names = {
            json.loads(path.read_text(encoding="utf-8"))["name"]
            for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT)
            for path in root.glob("*/*.json")
        }
        for folder in self.FOLDERS:
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field["options"], names)
        observation = self.load("npi_integration_reconciliation_observation")
        action = next(
            field
            for field in observation["fields"]
            if field["fieldname"] == "action_receipt_global_id"
        )
        self.assertEqual(action["options"], "NPI Integration Action Receipt")
        source = (
            DOCTYPE_ROOT
            / "npi_integration_reconciliation_observation"
            / "npi_integration_reconciliation_observation.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "require_exact_parent(",
            '"action_kind": "request_reconciliation"',
            '"outcome_state": "reconciliation_requested"',
        ):
            self.assertIn(marker, source)

    def test_controllers_are_append_only_hash_validated_with_one_exact_writer(self) -> None:
        base = (PACKAGE / "doctype_base.py").read_text(encoding="utf-8")
        guard = (PACKAGE / "frappe_validation.py").read_text(encoding="utf-8")
        for marker in (
            'require_integration_operations_write(self.doctype, "insert")',
            "deny_integration_operations_history_update()",
            "assert_immutable_fields",
            "deny_integration_operations_history_delete()",
        ):
            self.assertIn(marker, base)
        for marker in (
            "IntegrationOperationsWriteCapability",
            "_CURRENT.reset(token)",
            "INTEGRATION_OPERATIONS_SUPPORT_WRITES",
            "NPI API User",
            'service_actor_user_id.casefold() in {"guest", "administrator"}',
        ):
            self.assertIn(marker, guard)
        bypasses: list[tuple[str, str, str]] = []
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and any(
                        keyword.arg == "ignore_permissions"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                        for keyword in node.keywords
                    )
                ):
                    continue
                function = next(
                    (
                        parent
                        for parent in ast.walk(tree)
                        if isinstance(parent, ast.FunctionDef)
                        and node in tuple(ast.walk(parent))
                    ),
                    None,
                )
                bypasses.append(
                    (
                        path.name,
                        function.name if isinstance(function, ast.FunctionDef) else "",
                        node.func.attr,
                    )
                )
        self.assertEqual(
            bypasses,
            [
                (
                    "frappe_validation.py",
                    "insert_integration_operations_support_document",
                    "insert",
                )
            ],
        )
        action_metadata = self.load("npi_integration_action_receipt")
        action_key = next(
            field
            for field in action_metadata["fields"]
            if field["fieldname"] == "action_idempotency_key_hash"
        )
        self.assertEqual(action_key.get("unique"), 1)
        for folder in self.FOLDERS:
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            ast.parse(source)
            self.assertIn("IntegrationOperationsSupportDocument", source)
            self.assertIn("Snapshot", source)
            self.assertIn("hash does not match its fields", source)

    def test_support_base_executes_insert_guard_and_rejects_later_save(self) -> None:
        core = types.ModuleType("npi_core.documents.frappe_validation")
        for name in (
            "actor_text",
            "canonical_uuid",
            "lowercase_sha256",
            "positive_integer",
            "required_text",
            "tenant_text",
        ):
            setattr(core, name, lambda value, *_args: value)
        core.assert_immutable_fields = lambda *_args: None
        frappe_model = types.ModuleType("frappe.model")
        frappe_document = types.ModuleType("frappe.model.document")
        frappe_document.Document = object
        validation = types.ModuleType(
            "npi_integration.integration_operations.frappe_validation"
        )
        calls: list[object] = []
        validation.require_integration_operations_write = (
            lambda doctype, action: calls.append((doctype, action))
        )
        validation.deny_integration_operations_history_update = lambda: calls.append(
            "update"
        )
        validation.deny_integration_operations_history_delete = lambda: calls.append(
            "delete"
        )
        modules = {
            "frappe.model": frappe_model,
            "frappe.model.document": frappe_document,
            "npi_core.documents.frappe_validation": core,
            "npi_integration.integration_operations.frappe_validation": validation,
        }
        spec = importlib.util.spec_from_file_location(
            "npi_integration.integration_operations.p807_doctype_base",
            PACKAGE / "doctype_base.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        loaded = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(loaded)
        document = loaded.IntegrationOperationsSupportDocument()
        document.doctype = "NPI Integration Action Receipt"
        document.flags = types.SimpleNamespace(in_insert=True)
        document.get_doc_before_save = lambda: None
        document.before_insert()
        document.before_save()
        self.assertEqual(
            calls,
            [
                (document.doctype, "insert"),
                (document.doctype, "insert"),
            ],
        )
        calls.clear()
        document.flags.in_insert = False
        document.get_doc_before_save = lambda: object()
        document.before_save()
        self.assertEqual(calls, [(document.doctype, "save"), "update"])
        document.on_trash()
        self.assertEqual(calls[-1], "delete")

    def test_every_new_metadata_label_and_controller_message_has_direct_translations(self) -> None:
        sources: set[str] = set()
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            tree = ast.parse(
                (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                    encoding="utf-8"
                )
            )
            sources.update(_translation_literals(tree))
        sources.update(
            _translation_literals(
                ast.parse((PACKAGE / "frappe_validation.py").read_text(encoding="utf-8"))
            )
        )
        for path in (PACKAGE / "api.py", PACKAGE / "problems.py"):
            sources.update(
                _translation_literals(ast.parse(path.read_text(encoding="utf-8")))
            )
        for locale in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{locale}.csv").open(
                encoding="utf-8",
                newline="",
            ) as stream:
                catalog = {row[0]: row[1] for row in csv.reader(stream) if row}
            missing = sorted(source for source in sources if not catalog.get(source))
            self.assertEqual(missing, [], f"{locale} missing: {missing}")


def _translation_literals(tree: ast.AST) -> set[str]:
    return {
        str(node.args[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }


if __name__ == "__main__":
    unittest.main()
