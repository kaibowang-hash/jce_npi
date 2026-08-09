from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
OBJECTS = (
    "npi_tooling_import_batch",
    "npi_tooling_import_inspection_revision",
    "npi_tooling_import_mapping_revision",
    "npi_tooling_import_preview_revision",
    "npi_tooling_import_command_idempotency",
    "npi_tooling_import_mapping_activation",
    "npi_tooling_import_job",
    "npi_tooling_import_row_result",
    "npi_tooling_import_target_binding",
    "npi_tooling_import_correction_artifact",
    "npi_tooling_import_reconciliation_revision",
)


def _load(folder: str) -> dict[str, object]:
    return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))


def _fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["fieldname"]: item for item in metadata["fields"]}  # type: ignore[index]


class Phase6ToolingImportMetadataTests(unittest.TestCase):
    def test_additive_objects_are_guarded_and_install_no_business_rows(self) -> None:
        for folder in OBJECTS:
            with self.subTest(folder=folder):
                metadata = _load(folder)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(all(item.get("read_only") == 1 for item in _fields(metadata).values()))
                controller = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
                self.assertIn("require_tooling_import_write()", controller)
                self.assertIn("deny_tooling_import_delete", controller)

    def test_source_and_revision_controllers_bind_exact_snapshots_and_parents(self) -> None:
        batch = (DOCTYPE_ROOT / "npi_tooling_import_batch/npi_tooling_import_batch.py").read_text(encoding="utf-8")
        inspection = (DOCTYPE_ROOT / "npi_tooling_import_inspection_revision/npi_tooling_import_inspection_revision.py").read_text(encoding="utf-8")
        mapping = (DOCTYPE_ROOT / "npi_tooling_import_mapping_revision/npi_tooling_import_mapping_revision.py").read_text(encoding="utf-8")
        preview = (DOCTYPE_ROOT / "npi_tooling_import_preview_revision/npi_tooling_import_preview_revision.py").read_text(encoding="utf-8")
        for marker in (
            '"NPI Engineering Project"', '"NPI File Revision"',
            '"is_private": 1', '"scan_state": "clean"',
            "file_optimistic_version", "frappe_content_hash", "sha256",
        ):
            self.assertIn(marker, batch)
        self.assertIn('"NPI Tooling Import Batch"', inspection)
        self.assertIn('"NPI Tooling Import Inspection Revision"', mapping)
        self.assertIn('"NPI Tooling Import Inspection Revision"', preview)
        self.assertIn('"NPI Tooling Import Mapping Revision"', preview)
        self.assertGreaterEqual(mapping.count('"source_snapshot_hash"'), 3)
        self.assertGreaterEqual(preview.count('"source_snapshot_hash"'), 3)
        self.assertIn("A mapping proposal cannot authorize import execution.", preview)

    def test_mapping_metadata_excludes_production_approval_and_receipts_are_separate(self) -> None:
        mapping = _fields(_load("npi_tooling_import_mapping_revision"))
        preview = _fields(_load("npi_tooling_import_preview_revision"))
        for options in (mapping["state"]["options"], preview["mapping_state"]["options"]):
            self.assertEqual(str(options).splitlines(), ["proposal", "approved_fixture"])
            self.assertNotIn("approved_production", str(options))
        receipt = _fields(_load("npi_tooling_import_command_idempotency"))
        operations = str(receipt["operation"]["options"]).splitlines()
        self.assertEqual(operations[0], "tooling_import_batch.create")
        self.assertEqual(operations[-1], "tooling_import_rollback.execute")
        self.assertNotIn("tooling_import", str(_fields(_load("npi_tooling_command_idempotency"))["operation"]["options"]))

    def test_contracts_activate_only_the_checkpoint_2_fail_closed_routes(self) -> None:
        openapi = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for schema in (
            "ToolingImportSource", "ToolingImportInspectionRevision",
            "ToolingImportMappingRevision", "ToolingImportPreviewRevision",
            "ToolingImportFieldResult", "ToolingImportRowResult",
            "ToolingImportJobSnapshot", "ToolingImportRollbackDecision",
        ):
            self.assertIn(f"    {schema}:\n", openapi)
        self.assertIn("Production approval is intentionally absent until DR-REC-007 is resolved.", openapi)
        self.assertEqual(openapi.count("x-transaction-boundary: project-tooling-import-history"), 5)
        for operation in (
            "tooling_import_batch.create",
            "tooling_import_inspection.create",
            "tooling_import_mapping.create",
            "tooling_import_preview.create",
            "tooling_import_confirmation.create",
        ):
            self.assertIn(f"x-audit-operation: {operation}", openapi)
        for route in (
            "/tooling-imports$",
            "/tooling-imports/",
            "/inspections$",
            "/mapping-proposals$",
            "/previews$",
            "/confirmations$",
        ):
            self.assertIn(route, bff)
        self.assertIn("ToolingImportRoutesDisabled", bff)
        self.assertIn("TOOLING_IMPORT_ROUTES_DISABLED", (ROOT / "apps/npi_core/npi_core/foundation/errors.py").read_text(encoding="utf-8"))
        self.assertIn("npi_p6_07_routes_disabled", (ROOT / "apps/npi_core/npi_core/request_security.py").read_text(encoding="utf-8"))
        for object_name in (
            "ToolingImportBatch", "ToolingImportInspectionRevision",
            "ToolingImportMappingRevision", "ToolingImportPreviewRevision",
        ):
            self.assertIn(f"  {object_name}:\n", ownership)
        self.assertIn("conflict: UNAVAILABLE", ownership)
        self.assertIn("conflict: HUMAN_CONFIRMATION_REQUIRED", ownership)

    def test_checkpoint_3_contracts_cover_execution_retry_reconciliation_and_rollback(self) -> None:
        openapi = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for operation in (
            "executeToolingImportPreview",
            "getToolingImportJobs",
            "getToolingImportJob",
            "retryToolingImportJob",
            "createToolingImportCorrectionArtifact",
            "downloadToolingImportCorrectionArtifact",
            "reconcileToolingImportJob",
            "evaluateToolingImportRollback",
            "rollbackToolingImportJob",
        ):
            self.assertIn(f"operationId: {operation}", openapi)
        for schema in (
            "ToolingImportJobVersionCommand",
            "ToolingImportJobCollection",
            "ToolingImportCorrectionArtifact",
            "ToolingImportReconciliationRevision",
            "ToolingImportRollbackCommand",
        ):
            self.assertIn(f"    {schema}:\n", openapi)
        for audit in (
            "tooling_import_execution.start",
            "tooling_import_execution.retry",
            "tooling_import_correction.export",
            "tooling_import_correction.download",
            "tooling_import_reconciliation.create",
            "tooling_import_rollback.evaluate",
            "tooling_import_rollback.execute",
        ):
            self.assertIn(f"x-audit-operation: {audit}", openapi)
        for route_marker in (
            "_PROJECT_TOOLING_IMPORT_EXECUTE_ROUTE",
            "_PROJECT_TOOLING_IMPORT_JOBS_ROUTE",
            "_PROJECT_TOOLING_IMPORT_JOB_RETRY_ROUTE",
            "_PROJECT_TOOLING_IMPORT_CORRECTION_CONTENT_ROUTE",
            "_PROJECT_TOOLING_IMPORT_RECONCILE_ROUTE",
            "_PROJECT_TOOLING_IMPORT_ROLLBACK_ROUTE",
        ):
            self.assertIn(route_marker, bff)
        for object_name in (
            "ToolingImportMappingActivation",
            "ToolingImportJob",
            "ToolingImportRowResult",
            "ToolingImportTargetBinding",
            "ToolingImportCorrectionArtifact",
            "ToolingImportReconciliationRevision",
        ):
            self.assertIn(f"  {object_name}:\n", ownership)
        self.assertIn("conflict: EXACT_FIXTURE_SCOPE", ownership)
        self.assertIn(
            "conflict: ALL_TARGETS_MUST_REMAIN_EXACT_AND_UNUSED",
            ownership,
        )

    def test_all_visible_sources_have_direct_symmetric_translations(self) -> None:
        sources: set[str] = set()
        python_paths = [
            ROOT / "apps/npi_core/npi_core/tooling/import_domain.py",
            ROOT / "apps/npi_core/npi_core/tooling/import_execution_domain.py",
            ROOT / "apps/npi_core/npi_core/tooling/import_execution_repository.py",
            ROOT / "apps/npi_core/npi_core/tooling/import_frappe_validation.py",
            ROOT / "apps/npi_core/npi_core/tooling/import_repository.py",
            ROOT / "apps/npi_core/npi_core/tooling_import_api.py",
        ]
        for folder in OBJECTS:
            metadata = _load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(item["label"]) for item in metadata["fields"])  # type: ignore[index]
            python_paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for path in python_paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    sources.add(node.args[0].value)
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} P6-07 translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
