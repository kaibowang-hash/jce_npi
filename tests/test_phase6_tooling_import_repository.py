from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = ROOT / "apps/npi_core/npi_core/tooling/import_repository.py"
SOURCE = REPOSITORY_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _method(name: str) -> ast.FunctionDef:
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing method {name}")


def _call_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for candidate in ast.walk(node):
        if not isinstance(candidate, ast.Call):
            continue
        function = candidate.func
        if isinstance(function, ast.Attribute):
            names.append(function.attr)
        elif isinstance(function, ast.Name):
            names.append(function.id)
    return names


class Phase6ToolingImportRepositoryTests(unittest.TestCase):
    COMMANDS = {
        "create_tooling_import_batch": "_insert_source",
        "create_tooling_import_inspection": "_insert_inspection",
        "create_tooling_import_mapping_proposal": "_insert_mapping",
        "create_tooling_import_preview": "_insert_preview",
        "create_tooling_import_confirmation": "_insert_preview",
    }

    def test_project_authorization_precedes_import_object_resolution(self) -> None:
        for method_name in (
            "tooling_import_batches",
            "tooling_import_batch_detail",
            *self.COMMANDS,
        ):
            with self.subTest(method=method_name):
                method = _method(method_name)
                statements = [ast.unparse(item) for item in method.body]
                authorization = next(
                    index
                    for index, statement in enumerate(statements)
                    if "_authorized_project(" in statement
                    or "_locked_authorized_project(" in statement
                )
                object_lookup = next(
                    (
                        index
                        for index, statement in enumerate(statements)
                        if "_source_for_project(" in statement
                        or "_bounded_documents(" in statement
                    ),
                    len(statements),
                )
                self.assertLess(authorization, object_lookup)

    def test_source_registration_binds_exact_customer_and_file_revision_identity(self) -> None:
        method = ast.unparse(_method("create_tooling_import_batch"))
        for marker in (
            "_require_customer_scope(project, customer_scope_id)",
            "_file_revision_for_project(project, file_revision_id)",
            "file_revision.optimistic_version",
            "file_revision.frappe_content_hash",
            "file_revision.sha256",
            "file_revision.file_name",
            "file_revision.mime_type",
            "file_revision.size_bytes",
        ):
            self.assertIn(marker, method)

    def test_workbook_is_read_from_exact_server_file_bytes_and_rehashed(self) -> None:
        method = ast.unparse(_method("_validated_workbook"))
        for marker in (
            "frappe.get_doc('File'",
            "file_document.get_content()",
            "isinstance(content, bytes)",
            "len(content) != source.size_bytes",
            "hashlib.sha256(content).hexdigest() != source.sha256",
            "read_validated_workbook_bytes(content",
        ):
            self.assertIn(marker, method)
        for forbidden in ("get_full_path", "NamedTemporaryFile", "mkstemp", "open("):
            self.assertNotIn(forbidden, method)

    def test_each_command_orders_receipt_record_audit_and_seal_in_one_guard(self) -> None:
        for method_name, insert_name in self.COMMANDS.items():
            with self.subTest(method=method_name):
                method = _method(method_name)
                guards = [
                    node
                    for node in ast.walk(method)
                    if isinstance(node, ast.With)
                    and any(
                        isinstance(item.context_expr, ast.Call)
                        and isinstance(item.context_expr.func, ast.Name)
                        and item.context_expr.func.id == "tooling_import_write"
                        for item in node.items
                    )
                ]
                self.assertEqual(len(guards), 1)
                ordered = []
                for statement in guards[0].body:
                    ordered.extend(_call_names(statement))
                positions = [
                    ordered.index(name)
                    for name in (
                        "_insert_import_receipt",
                        insert_name,
                        "_append_audit",
                        "_seal_import_receipt",
                    )
                ]
                self.assertEqual(positions, sorted(positions))

    def test_receipts_are_actor_bound_separate_and_integrity_checked(self) -> None:
        context = ast.unparse(_method("_import_command_context"))
        replay = ast.unparse(_method("_import_receipt_replay"))
        insert = ast.unparse(_method("_insert_import_receipt"))
        for marker in (
            "actorUserId",
            "operation",
            "projectGlobalId",
            "tenantId",
            "idempotencyKeyHash",
        ):
            self.assertIn(marker, context)
        self.assertIn("NPI Tooling Import Command Idempotency", replay)
        self.assertIn("NPI Tooling Import Command Idempotency", insert)
        self.assertIn("ToolingIdempotencyConflict", replay)
        self.assertIn("sha256_json(response)", replay)
        self.assertIn("for_update=True", replay)

    def test_audits_are_hash_count_summaries_without_raw_workbook_data(self) -> None:
        forbidden_keys = {
            "fileName",
            "worksheetName",
            "reason",
            "rows",
            "columns",
            "cells",
            "values",
            "confirmations",
        }
        audit_calls = [
            node
            for node in ast.walk(TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_append_audit"
        ]
        self.assertEqual(len(audit_calls), len(self.COMMANDS))
        for call in audit_calls:
            summary = next(
                keyword.value for keyword in call.keywords if keyword.arg == "summary"
            )
            self.assertIsInstance(summary, ast.Dict)
            keys = {
                key.value
                for key in summary.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            self.assertFalse(keys & forbidden_keys)

    def test_checkpoint_2_has_no_execution_outbox_network_or_target_mutation(self) -> None:
        imports = {
            alias.name
            for node in TREE.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(
            imports
            & {
                "requests",
                "httpx",
                "urllib",
                "urllib.request",
                "socket",
            }
        )
        for forbidden in (
            "urlopen(",
            "requests.",
            "httpx.",
            "Outbox",
            "ERPNext Endpoint",
            "ERPNext Credential",
            ".commit(",
            ".rollback(",
        ):
            self.assertNotIn(forbidden, SOURCE)
        doctypes = {
            node.args[0].value
            for node in ast.walk(TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_doc"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        self.assertEqual(doctypes, {"File"})
        inserted_doctypes = set()
        for node in ast.walk(TREE):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_doc"
                and node.args
                and isinstance(node.args[0], ast.Dict)
            ):
                continue
            definition = node.args[0]
            for key, value in zip(definition.keys, definition.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "doctype"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    inserted_doctypes.add(value.value)
        self.assertEqual(
            inserted_doctypes,
            {
                "NPI Tooling Import Batch",
                "NPI Tooling Import Command Idempotency",
                "NPI Tooling Import Inspection Revision",
                "NPI Tooling Import Mapping Revision",
                "NPI Tooling Import Preview Revision",
            },
        )
        self.assertIn('"activateProductionMapping": False', SOURCE)
        self.assertIn('"execute": False', SOURCE)

    def test_confirmation_resolves_exact_contained_target_and_image_anchor(self) -> None:
        method = ast.unparse(_method("_confirmation_value"))
        for marker in (
            "_part_revision_for_project(project, target_id, require_current=True)",
            "_master_for_project(project, target_id)",
            "target.snapshot_hash",
            "_inspection_for_project(project, predecessor.source",
            "anchor.anchor_key == anchor_key",
            "anchor.candidate_source_row == source_row",
            "anchor.requires_confirmation",
        ):
            self.assertIn(marker, method)

    def test_production_mapping_authority_is_unavailable_by_default(self) -> None:
        constructor = ast.unparse(_method("__init__"))
        authority = ast.unparse(_method("_unavailable_mapping_authority"))
        self.assertIn("mapping_authority or self._unavailable_mapping_authority", constructor)
        self.assertIn("'state': 'unavailable'", authority)
        self.assertIn("'reasonCode': 'production_mapping_unavailable'", authority)


if __name__ == "__main__":
    unittest.main()
