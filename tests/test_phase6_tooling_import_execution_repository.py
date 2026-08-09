from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = (
    ROOT / "apps/npi_core/npi_core/tooling/import_execution_repository.py"
)
SOURCE = REPOSITORY_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"


def _function(name: str) -> ast.FunctionDef:
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def _source(name: str) -> str:
    return ast.unparse(_function(name))


class Phase6ToolingImportExecutionRepositoryTests(unittest.TestCase):
    def test_execution_is_fixture_scoped_and_never_contacts_erpnext(self) -> None:
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
            "Outbox",
            "ERPNext Endpoint",
            "ERPNext Credential",
            "ignore_" + "permissions",
            "frappe.db." + "sql",
        ):
            self.assertNotIn(forbidden, SOURCE)
        seed = _source("seed_synthetic_fixture_mapping_activation")
        for marker in (
            "require_tooling_import_routes_enabled()",
            "not self._is_internal_system_manager()",
            "_FIXTURE_SOURCES[source.file_name] != source.sha256",
            "source.customer_scope_id.casefold().startswith('synthetic')",
            "proposal.state is not MappingRevisionState.PROPOSAL",
            "proposal.mapping_version != 1",
            "ExecutionFieldBinding('Part Name English', 'engineering_part_revision', 'title')",
        ):
            self.assertIn(marker, seed)
        self.assertNotIn("@frappe.whitelist", SOURCE)

    def test_start_is_one_job_per_exact_preview_and_enqueues_after_commit(self) -> None:
        execute = _source("execute_tooling_import_preview")
        enqueue = _source("_enqueue_job")
        for marker in (
            "preview.preview_version != expected_version",
            "preview.snapshot_hash != expected_snapshot_hash",
            "_activation_for_preview(project, source, preview)",
            "not preview.execution_eligible",
            "_job_for_preview(project, source, preview) is not None",
            "ToolingVersionConflict",
        ):
            self.assertIn(marker, execute)
        self.assertIn("enqueue_after_commit=True", enqueue)
        self.assertIn("expected_snapshot_hash=expected_snapshot_hash", enqueue)
        self.assertIn(
            "npi_core.tooling.import_execution_repository.run_tooling_import_job",
            enqueue,
        )

    def test_worker_reauthorizes_and_commits_bounded_immutable_progress(self) -> None:
        worker = _source("run_tooling_import_job")
        row = _source("_execute_import_row")
        progress = _source("_update_processing_job_snapshot")
        for marker in (
            "require_tooling_import_routes_enabled()",
            "authenticated_principal(str(job.actor_user_id))",
            "'System Manager' not in principal.roles",
            "authorize_scope(project_id, administer=True)",
            "_validated_workbook(project, source)",
            "_require_customer_scope(project, source.customer_scope_id)",
            "_activation_for_preview(project, source, preview)",
            "mapping.snapshot_hash != activation.mapping_snapshot_hash",
            "_job_corrections(project, source, exact_job)",
            "selected[:_MAX_ROWS_PER_RUN]",
            "_enqueue_job(parsed_job_id, str(refreshed.snapshot_hash))",
        ):
            self.assertIn(marker, worker)
        self.assertLess(
            worker.index("_job_corrections(project, source, exact_job)"),
            worker.index("processing = ToolingImportJobSnapshot"),
        )
        self.assertEqual(_MAX_ROWS_PER_RUN_FROM_TREE(), 25)
        self.assertIn("frappe.db.commit()", row)
        self.assertIn("frappe.db.rollback()", row)
        self.assertIn("_insert_row_result", row)
        self.assertIn("_update_processing_job_snapshot", row)
        self.assertIn("row_results=history", progress)
        self.assertIn("int(job.optimistic_version) + 1", progress)

    def test_target_creation_diagnostics_are_closed_and_stage_specific(self) -> None:
        create = _source("_repository_create_part_target")
        for code in (
            "P607_IMPORT_TARGET_ROOT_INSERT",
            "P607_IMPORT_TARGET_REVISION_INSERT",
            "P607_IMPORT_TARGET_ROOT_ADVANCE",
            "P607_IMPORT_TARGET_ROW_RESULT_INSERT",
            "P607_IMPORT_TARGET_BINDING_INSERT",
        ):
            with self.subTest(code=code):
                self.assertEqual(create.count(code), 1)
        diagnostic = _source("_import_target_server_step")
        self.assertIn("code in _IMPORT_TARGET_DIAGNOSTIC_CODES", diagnostic)
        self.assertIn("exception_type.isidentifier()", diagnostic)
        self.assertNotIn("str(error)", diagnostic)

    def test_retry_selects_only_latest_retryable_rows_and_keeps_success_history(self) -> None:
        retry = _source("retry_tooling_import_job")
        selection = _source("_rows_for_attempt")
        for marker in (
            "latest_import_row_results(history)",
            "value.state is ImportRowResultState.FAILED_RETRYABLE",
            "row_results=history",
            "attempt=int(job.attempt) + 1",
            "correction_artifact_snapshot_hash",
            "artifact.job_snapshot_hash",
        ):
            self.assertIn(marker, retry)
        self.assertIn("item.attempt == attempt", selection)
        self.assertIn("ImportRowResultState.FAILED_RETRYABLE", selection)
        self.assertNotIn("ImportRowResultState.CREATED", selection)

    def test_correction_artifact_is_private_allowlisted_hashed_and_audited(self) -> None:
        create = _source("create_correction_artifact")
        save = _source("_save_correction_file")
        download = _source("correction_artifact_content")
        verify = _source("_verified_artifact_content")
        csv_builder = _source("_correction_csv")
        self.assertIn("is_private=1", save)
        self.assertIn(
            "['worksheet_name', 'source_row', 'source_header', 'corrected_value']",
            csv_builder,
        )
        self.assertIn("correctionHashes", create)
        self.assertIn("'fileName': str(file_document.file_name)", create)
        self.assertIn("'sizeBytes': int(file_document.file_size)", create)
        self.assertNotIn('"correctedValue": item.corrected_value', create)
        corrections = _source("_repository_job_corrections")
        self.assertIn("job.correction_artifact_snapshot_hash", corrections)
        self.assertIn("artifact.snapshot_hash", corrections)
        for marker in (
            "operation='tooling_import_correction.download'",
            "_verified_artifact_content",
            "_append_audit",
            "_seal_import_receipt",
        ):
            self.assertIn(marker, download)
        for marker in (
            "isinstance(raw_content, str)",
            "raw_content.encode('utf-8')",
            "int(file_document.is_private or 0) != 1",
            "len(content) != int(artifact.size_bytes)",
            "hashlib.sha256(content).hexdigest() != str(artifact.sha256)",
            "P607_CORRECTION_DOWNLOAD_CONTENT_VALIDATE",
            "P607_CORRECTION_DOWNLOAD_PRIVACY_VALIDATE",
            "P607_CORRECTION_DOWNLOAD_FILE_ID_VALIDATE",
            "P607_CORRECTION_DOWNLOAD_FILE_NAME_VALIDATE",
            "P607_CORRECTION_DOWNLOAD_SIZE_VALIDATE",
            "P607_CORRECTION_DOWNLOAD_DIGEST_VALIDATE",
        ):
            self.assertIn(marker, verify)

    def test_correction_diagnostics_are_closed_and_stage_specific(self) -> None:
        create = _source("create_correction_artifact")
        for code in (
            "P607_CORRECTION_RECEIPT_INSERT",
            "P607_CORRECTION_FILE_SAVE",
            "P607_CORRECTION_ARTIFACT_INSERT",
            "P607_CORRECTION_RESPONSE_BUILD",
            "P607_CORRECTION_AUDIT_APPEND",
            "P607_CORRECTION_RECEIPT_SEAL",
        ):
            with self.subTest(code=code):
                self.assertEqual(create.count(code), 1)
        diagnostic = _source("_correction_server_step")
        self.assertIn("code in _CORRECTION_DIAGNOSTIC_CODES", diagnostic)
        self.assertIn("exception_type.isidentifier()", diagnostic)
        self.assertNotIn("str(error)", diagnostic)

    def test_public_job_messages_are_localized_without_rewriting_snapshot_truth(
        self,
    ) -> None:
        public_job = _source("_public_job")
        detail = _source("_job_detail")
        localize = _source("_localized_job_payload")
        field_message = _source("_localized_field_result_message")
        failure_message = _source("_localized_job_failure_message")
        self.assertIn("_localized_job_payload(snapshot.snapshot_payload())", public_job)
        self.assertIn("_localized_job_payload(snapshot)", detail)
        self.assertIn("_localized_field_result_message", localize)
        self.assertIn("_localized_job_failure_message", localize)
        for marker in (
            "stored_message != source",
            "_('The field was imported.')",
            "_('The row could not be imported. Retry with the trace identifier.')",
        ):
            self.assertIn(marker, field_message)
        self.assertIn("worker_authorization_revoked", failure_message)
        self.assertIn("stored_message !=", failure_message)

    def test_rollback_is_all_or_nothing_and_uses_exact_delete_guards(self) -> None:
        rollback = _source("rollback_tooling_import_job")
        delete = _source("_delete_eligible_targets")
        observe = _source("_observe_binding")
        exact_targets = _source("_same_eligibility_targets")
        self.assertIn("bool(items)", rollback)
        self.assertIn("item.get('state') == 'matched'", rollback)
        self.assertIn("for item in items", rollback)
        self.assertIn("_build_reconciliation", rollback)
        self.assertIn("lock_targets=True", rollback)
        self.assertIn("_same_eligibility_targets(eligibility_items, items)", rollback)
        self.assertLess(
            rollback.index("if allowed:"),
            rollback.index("_insert_reconciliation"),
        )
        self.assertIn("frozen_identities == current_identities", exact_targets)
        self.assertIn("tooling_import_rollback_targets(targets)", delete)
        self.assertIn("len(bindings) != len(allowed_result_ids)", delete)
        self.assertIn("frappe.delete_doc('NPI Engineering Part Revision'", delete)
        self.assertIn("frappe.delete_doc('NPI Engineering Part'", delete)
        self.assertIn("frappe.db.count", observe)
        self.assertIn("_optional_locked_doc if for_update else _optional_doc", observe)
        self.assertIn("for_update=True", _source("_optional_locked_doc"))
        validation = (
            ROOT / "apps/npi_core/npi_core/tooling/frappe_validation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("TOOLING_COMMAND_WRITE_FLAG", validation)
        self.assertIn('"NPI Engineering Part Revision"', validation)
        self.assertIn('"NPI Engineering Part"', validation)
        self.assertIn("str(UUID(name)) == name", validation)
        dependency_values = {
            tuple(
                element.value
                for element in node.elts
                if isinstance(element, ast.Constant)
            )
            for node in ast.walk(TREE)
            if isinstance(node, ast.Tuple)
            and len(node.elts) == 2
            and all(isinstance(element, ast.Constant) for element in node.elts)
        }
        for dependency in (
            ("NPI Tooling Requirement", "target_part_revision_global_id"),
            ("NPI Tooling Applicability", "part_revision_global_id"),
            ("NPI Part Controlled Specification", "part_revision_global_id"),
        ):
            self.assertIn(dependency, dependency_values)

        for folder in ("npi_engineering_part", "npi_engineering_part_revision"):
            metadata = json.loads(
                (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
            )
            manager = next(
                item
                for item in metadata["permissions"]
                if item["role"] == "System Manager"
            )
            self.assertEqual(manager["delete"], 1)
            controller = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("tooling_import_rollback_delete_allowed(self)", controller)
            self.assertIn("deny_tooling_history_delete(self)", controller)

    def test_receipt_operations_and_target_types_match_doctype_contract(self) -> None:
        metadata = json.loads(
            (
                DOCTYPE_ROOT
                / "npi_tooling_import_command_idempotency"
                / "npi_tooling_import_command_idempotency.json"
            ).read_text(encoding="utf-8")
        )
        fields = {item["fieldname"]: item for item in metadata["fields"]}
        operations = set(fields["operation"]["options"].splitlines())
        target_types = set(fields["target_object_type"]["options"].splitlines())
        # Repository command operations are passed as explicit keyword literals.
        receipt_operations = {
            keyword.value.value
            for node in ast.walk(TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"_import_command_context", "_insert_import_receipt"}
            for keyword in node.keywords
            if keyword.arg == "operation"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        }
        self.assertTrue(receipt_operations)
        self.assertLessEqual(receipt_operations, operations)
        self.assertIn("tooling_import_reconciliation_revision", target_types)
        self.assertNotIn("tooling_import_rollback_result", target_types)


def _MAX_ROWS_PER_RUN_FROM_TREE() -> int:
    for node in TREE.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "_MAX_ROWS_PER_RUN"
            for target in node.targets
        ):
            if isinstance(node.value, ast.Constant) and type(node.value.value) is int:
                return node.value.value
    raise AssertionError("missing _MAX_ROWS_PER_RUN")


if __name__ == "__main__":
    unittest.main()
