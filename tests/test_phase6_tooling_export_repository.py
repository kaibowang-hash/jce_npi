from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = ROOT / "apps/npi_core/npi_core/tooling/export_repository.py"
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


class Phase6ToolingExportRepositoryTests(unittest.TestCase):
    def test_project_authorization_precedes_every_secondary_export_lookup(self) -> None:
        lookup_markers = {
            "tooling_list": "_tooling_list_rows(",
            "tooling_list_preference": "_preference_for_key(",
            "save_tooling_list_preference": "_locked_preference_for_key(",
            "create_tooling_export_package": "_export_command_context(",
            "tooling_export_package_content": "_package_for_project(",
        }
        for method_name, lookup_marker in lookup_markers.items():
            with self.subTest(method=method_name):
                statements = [ast.unparse(item) for item in _method(method_name).body]
                authorization = next(
                    index
                    for index, statement in enumerate(statements)
                    if "_authorized_project(" in statement
                    or "_locked_authorized_project(" in statement
                    or "_locked_view_project(" in statement
                )
                lookup = next(
                    index
                    for index, statement in enumerate(statements)
                    if lookup_marker in statement
                )
                self.assertLess(authorization, lookup)

    def test_list_is_complete_before_stable_bounded_cursor_paging(self) -> None:
        method = ast.unparse(_method("tooling_list"))
        for marker in (
            "query_tooling_list_rows(rows, filter_spec)",
            "tooling_list_query_snapshot_hash(filter_spec, rows)",
            "_decode_cursor(cursor, expected_query_hash=query_hash)",
            "page = selected[start:start + page_size]",
            "_encode_cursor(str(page[-1].tooling_master_global_id), query_hash=query_hash)",
            "'totalCount': len(selected)",
        ):
            self.assertIn(marker, method)
        self.assertNotIn("MAX_TOOLING_EXPORT_OBJECTS", method)

    def test_shared_master_projection_uses_only_exact_project_aggregates(self) -> None:
        method = ast.unparse(_method("_tooling_list_rows"))
        for doctype in (
            "NPI Tooling Set",
            "NPI Tooling Revision",
            "NPI Tooling Import Target Binding",
        ):
            self.assertIn(doctype, method)
        self.assertGreaterEqual(method.count("'project_global_id': str(project.global_id)"), 3)
        self.assertIn("'tenant_id': str(project.tenant_id)", method)
        self.assertIn("'target_object_type': 'tooling_master'", method)
        for snapshot_set in (
            "applicabilitySnapshots",
            "setSnapshots",
            "revisionSnapshots",
            "source",
        ):
            self.assertIn(snapshot_set, method)
        self.assertNotIn("customer_scope_id", method)
        self.assertNotIn("supplier", method.casefold())

    def test_preference_is_actor_project_view_scoped_and_optimistically_locked(self) -> None:
        save = ast.unparse(_method("save_tooling_list_preference"))
        match = ast.unparse(_method("_preference_matches"))
        for marker in (
            "tenant_id=str(project.tenant_id)",
            "project_global_id=project_id",
            "actor_user_id=self.actor",
            "view_id=view_id",
            "expected_version != 0",
            "int(row.optimistic_version) != expected_version",
            "str(row.snapshot_hash) != str(expected_snapshot_hash)",
            "version = int(row.optimistic_version) + 1",
        ):
            self.assertIn(marker, save)
        for field in (
            "preference_key_hash",
            "tenant_id",
            "project_global_id",
            "actor_user_id",
            "view_id",
            "grid_id",
            "table_schema_version",
        ):
            self.assertIn(field, match)
        self.assertIn("for_update=True", ast.unparse(_method("_locked_preference_for_key")))
        self.assertIn(
            "The Tooling List preference scope drifted.",
            ast.unparse(_method("_preference_for_key")),
        )
        self.assertIn("frappe.DuplicateEntryError", save)
        self.assertIn("ToolingVersionConflict", save)
        validate = ast.unparse(_method("_validated_preference_snapshot"))
        self.assertIn("_preference_from_stored_payload", validate)
        self.assertIn("preference.snapshot_payload() != snapshot['preference']", validate)
        stored = ast.unparse(_method("_preference_from_stored_payload"))
        self.assertIn("ToolingListPreferenceSnapshot", stored)
        self.assertIn("set(payload) != expected_fields", stored)

    def test_export_clock_uses_the_canonical_snapshot_precision(self) -> None:
        clock = ast.unparse(_method("_now_export"))
        self.assertIn("astimezone(UTC).replace(microsecond=0)", clock)

    def test_create_orders_receipt_file_package_audit_and_seal_in_one_guard(self) -> None:
        method = _method("create_tooling_export_package")
        guards = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.With)
            and any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "tooling_export_write"
                for item in node.items
            )
        ]
        self.assertEqual(len(guards), 1)
        ordered: list[str] = []
        for statement in guards[0].body:
            ordered.extend(_call_names(statement))
        positions = [
            ordered.index(name)
            for name in (
                "_insert_export_receipt",
                "_save_private_package",
                "_register_orphan_cleanup",
                "_insert_package",
                "_append_audit",
                "_seal_export_receipt",
            )
        ]
        self.assertEqual(positions, sorted(positions))

    def test_selection_and_filtered_exports_revalidate_current_exact_truth(self) -> None:
        method = ast.unparse(_method("create_tooling_export_package"))
        for marker in (
            "rows = self._tooling_list_rows(project)",
            "resolve_exact_selection(rows, ToolingExportSelection(tuple(selection)))",
            "query_tooling_list_rows(rows, filter_spec)",
            "1 <= len(selected) <= MAX_TOOLING_EXPORT_OBJECTS",
            "filtered_query_snapshot_hash(filter_spec, rows)",
            "exact_query_hash != query_snapshot_hash",
            "The filtered Tooling List is stale.",
        ):
            self.assertIn(marker, method)
        self.assertLess(
            method.index("_export_command_context"),
            method.index("_tooling_list_rows"),
        )

    def test_download_reauthorizes_creator_project_expiry_hash_and_private_file(self) -> None:
        download = ast.unparse(_method("tooling_export_package_content"))
        verify = ast.unparse(_method("_verified_package_content"))
        for marker in (
            "_locked_authorized_project(project_id)",
            "self._is_internal_system_manager()",
            "package.created_by_user_id",
            "package.snapshot_hash",
            "now >= _datetime(package.expires_at)",
            "ToolingExportExpired()",
            "frappe.get_doc('File'",
            "_verified_package_content(package, file_document)",
        ):
            self.assertIn(marker, download)
        for marker in (
            "file_document.is_private",
            "file_document.name",
            "file_document.file_name",
            "file_document.file_size",
            "hashlib.sha256(content).hexdigest()",
            "package.sha256",
        ):
            self.assertIn(marker, verify)

    def test_receipts_are_actor_project_operation_payload_and_key_bound(self) -> None:
        context = ast.unparse(_method("_export_command_context"))
        replay = ast.unparse(_method("_export_receipt_replay"))
        insert = ast.unparse(_method("_insert_export_receipt"))
        for marker in (
            "tenantId",
            "projectGlobalId",
            "actorUserId",
            "operation",
            "payload",
        ):
            self.assertIn(marker, context)
        for marker in (
            "actor_user_id",
            "operation",
            "idempotency_key_hash",
            "payload_hash",
            "ToolingIdempotencyConflict",
            "sha256_json(response)",
            "for_update=True",
        ):
            self.assertIn(marker, replay)
        self.assertIn("NPI Tooling Export Command Idempotency", insert)
        self.assertIn("frappe.DuplicateEntryError", insert)
        self.assertIn("ToolingIdempotencyConflict", insert)
        for marker in (
            "target_id = UUID",
            "_package_for_project(project, target_id)",
            "package.created_by_user_id",
            "response != expected_response",
        ):
            self.assertIn(marker, replay)

    def test_private_file_orphan_cleanup_is_bounded_and_rollback_only(self) -> None:
        method = ast.unparse(_method("_register_orphan_cleanup"))
        for marker in (
            "file_url.startswith('/private/files/')",
            "parsed.parts[:3] != ('/', 'private', 'files')",
            "file_path.parent != private_directory",
            "frappe.db.after_rollback.add(cleanup_after_rollback)",
            "file_path.unlink(missing_ok=True)",
        ):
            self.assertIn(marker, method)
        self.assertNotIn("rmtree", method)
        self.assertNotIn("glob(", method)

    def test_public_contract_and_audits_are_url_and_raw_value_free(self) -> None:
        public = ast.unparse(_method("_public_package"))
        self.assertIn("_validated_package_snapshot(row)", public)
        self.assertNotIn("frappe_file_id", public)
        self.assertNotIn("file_url", public)
        validation = ast.unparse(_method("_validated_package_snapshot"))
        for marker in (
            "snapshot != expected",
            "sha256_json(snapshot)",
            "frappeFileId",
            "objectRefs",
            "generatedAt",
            "expiresAt",
        ):
            self.assertIn(marker, validation)
        forbidden_keys = {
            "title",
            "fileName",
            "actorUserId",
            "objectRefs",
            "selection",
            "rows",
            "values",
            "content",
        }
        audit_calls = [
            node
            for node in ast.walk(TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_append_audit"
        ]
        self.assertEqual(len(audit_calls), 3)
        for call in audit_calls:
            summary = next(keyword.value for keyword in call.keywords if keyword.arg == "summary")
            self.assertIsInstance(summary, ast.Dict)
            keys = {
                key.value
                for key in summary.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            self.assertFalse(keys & forbidden_keys)

    def test_adapter_has_no_erp_network_outbox_or_manual_transaction_escape(self) -> None:
        imports = {
            alias.name
            for node in TREE.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(imports & {"requests", "httpx", "urllib", "urllib.request", "socket"})
        for forbidden in (
            "urlopen(",
            "requests.",
            "httpx.",
            "Outbox",
            "ERPNext Endpoint",
            "ERPNext Credential",
            ".commit(",
            ".rollback(",
            "frappe.db." "sql(",
        ):
            self.assertNotIn(forbidden, SOURCE)
        inserted_doctypes: set[str] = set()
        for node in ast.walk(TREE):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_doc"
                and node.args
                and isinstance(node.args[0], ast.Dict)
            ):
                continue
            for key, value in zip(node.args[0].keys, node.args[0].values, strict=True):
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
                "NPI Tooling List Preference",
                "NPI Tooling Export Package",
                "NPI Tooling Export Command Idempotency",
            },
        )


if __name__ == "__main__":
    unittest.main()
