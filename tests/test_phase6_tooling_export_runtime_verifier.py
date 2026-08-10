from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_export_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    module_names = (
        "verify_document_runtime",
        "verify_tooling_runtime",
        "verify_tooling_revision_runtime",
        "verify_tooling_manufacturing_runtime",
        "verify_tooling_engineering_controls_runtime",
        "verify_tooling_acceptance_runtime",
        "verify_tooling_import_runtime",
        "verify_tooling_export_runtime_contract",
    )
    saved = {name: sys.modules.pop(name, None) for name in module_names}
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_export_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling export runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": FIXTURE_RUN_ID},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        for name in module_names:
            sys.modules.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                sys.modules[name] = value
    return module


class Phase6ToolingExportRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_routes_and_closed_vocabulary_are_exact(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.TENANT_ID, "runtime-tenant")
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertEqual(len(module.VIEW_IDS), 10)
        self.assertEqual(
            module.PACKAGE_MEMBERS,
            ("manifest.json", "tooling-objects.csv", "README.txt"),
        )
        project_id = "10000000-0000-4000-8000-000000000001"
        package_id = "20000000-0000-4000-8000-000000000002"
        self.assertEqual(
            module.preference_path(project_id, "shared_parts"),
            f"/api/npi/v1/projects/{project_id}/tooling-list/preferences/shared_parts",
        )
        self.assertEqual(
            module.package_content_path(project_id, package_id),
            f"/api/npi/v1/projects/{project_id}/tooling-exports/{package_id}:content",
        )
        identity = module.deterministic_uuid("controlled-fixture")
        self.assertEqual(UUID(identity).version, 4)
        self.assertEqual(identity, module.deterministic_uuid("controlled-fixture"))

    def test_view_predicates_cover_all_ten_server_views(self) -> None:
        row = {
            "applicabilityCount": 0,
            "distinctPartRevisionCount": 1,
            "physicalSetCount": 2,
            "designRevisionCount": 1,
            "customerOwnedSet": True,
        }
        expected = {
            "all": True,
            "missing_applicability": True,
            "single_part": True,
            "shared_parts": False,
            "missing_physical_set": False,
            "single_physical_set": False,
            "multiple_physical_sets": True,
            "missing_design_revision": False,
            "has_design_revision": True,
            "customer_owned_set": True,
        }
        self.assertEqual(
            {view: self.module.matches_view(row, view) for view in self.module.VIEW_IDS},
            expected,
        )

    def test_verifier_covers_views_preferences_and_stable_paging(self) -> None:
        required = (
            "for view_id in VIEW_IDS:",
            "actual == expected and value[\"totalCount\"] == len(expected)",
            "second[\"querySnapshotHash\"] == first[\"querySnapshotHash\"]",
            'validate_problem(stale_cursor, 422, "VALIDATION_FAILED")',
            '"stored") is False',
            'saved.body.get("optimisticVersion") == 1',
            'validate_problem(conflict, 409, "TOOLING_VERSION_CONFLICT")',
            '"hiddenColumns": ["origin"]',
            '"columnId": "tooling", "width": 272',
            '"manual" in observed_sources',
            'observed_sources <= {"manual", "controlled_xlsx_import"}',
            'f"P6-08 Tooling List returned HTTP {result.status} "',
            "problem_code if isinstance(problem_code, str) else 'unavailable'",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_preference_diagnostic_is_response_neutral_and_structural(self) -> None:
        result = self.module.HttpResult(
            500,
            {},
            {"code": "INTERNAL_ERROR", "message": "must not be emitted"},
        )
        with patch.object(
            self.module.document_runtime,
            "sanitized_http_failure",
            return_value=(
                " [diagnostic_code=UNEXPECTED_BFF_EXCEPTION; "
                "exc_type=ValidationError; "
                "trace_id=trace-0123456789abcdef0123456789abcdef]"
            ),
        ):
            diagnostic = self.module.preference_save_diagnostic(
                result,
                {"viewId": "all"},
            )
        self.assertEqual(
            diagnostic,
            "P6-08 saved preference truth drifted: HTTP 500; "
            "code=INTERNAL_ERROR; storedTrue=False; versionOne=False; "
            "snapshotHashValid=False; preferenceMatches=False "
            "[diagnostic_code=UNEXPECTED_BFF_EXCEPTION; "
            "exc_type=ValidationError; "
            "trace_id=trace-0123456789abcdef0123456789abcdef]",
        )
        self.assertNotIn("message", diagnostic)
        self.assertNotIn("must not be emitted", diagnostic)

    def test_verifier_covers_selection_filter_package_and_localized_bytes(self) -> None:
        required = (
            'PACKAGE_CASES = (\n    ("en", "selection"),',
            '("zh-TW", "filtered")',
            'tuple(archive.namelist()) == PACKAGE_MEMBERS',
            'hashlib.sha256(downloaded.content).hexdigest() == package_hash',
            'hashlib.sha256(members["manifest.json"]).hexdigest() == manifest_hash',
            'tuple(manifest.get("omittedFieldClasses", [])) == OMITTED_FIELD_CLASSES',
            'csv_rows[1][2] == "\'" + FORMULA_MASTER_TITLE',
            'readme.splitlines()[0] == expected_readme',
            '"/private/files/" not in repr(members)',
            'expires_at - generated_at == timedelta(hours=1)',
            'downloaded.headers.get("Content-Security-Policy")',
            '== "sandbox; default-src \'none\'"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_stale_replay_expiry_idor_and_mutation_boundaries_are_closed(self) -> None:
        required = (
            'validate_problem(stale, 422, "VALIDATION_FAILED")',
            'validate_problem(conflict, 409, "TOOLING_IDEMPOTENCY_CONFLICT")',
            'result.headers.get("Idempotency-Replayed") == replayed',
            'downloaded.headers.get("Idempotency-Replayed") == "true"',
            '"P6-08 cross-process replay changed package, receipt, audit or integration truth"',
            'expired_download.status == 410',
            'expired_download.problem.get("code") == "TOOLING_EXPORT_EXPIRED"',
            'validate_problem(denied_export, 403, "PERMISSION_DENIED")',
            'creator_denied.problem.get("code") == "TOOLING_UNAVAILABLE"',
            'cross_project.problem.get("code") == "TOOLING_UNAVAILABLE"',
            'rejected_update.status == 403',
            'rejected_delete.status == 403',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_bench_fixtures_are_fixed_site_schema_and_expiry_only(self) -> None:
        required = (
            "document_runtime._validated_runtime_site()",
            '"verify_tooling_export_runtime_schema"',
            '"seed_expired_tooling_export_package"',
            'generated_at = datetime.now(UTC) - timedelta(hours=1)',
            "FrappeToolingExportRepository(",
            "ToolingExportMode.SELECTION",
            "BENCH_PATH.resolve() == BENCH_PATH",
            "completed.stderr[-2000:]",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("requests.post", self.source)
        self.assertNotIn("erpnext_url", self.source.casefold())
        self.assertNotIn("Outbox", self.source.split("def seed_expired", 1)[1])

    def test_persistence_cardinality_proves_no_erp_integration_traffic(self) -> None:
        required = (
            'final["NPI Tooling List Preference"] == 1',
            'final["NPI Tooling Export Package"] == 4',
            'final["NPI Tooling Export Command Idempotency"] == 7',
            'final["createAudit"] == 4',
            'final["downloadAudit"] == 3',
            'final["preferenceAudit"] == 1',
            '(final["outbox"], final["inbox"]) == integration_before',
            '"integrationTrafficCreated": False',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_shell_orchestrates_independent_switch_replay_redaction_and_cleanup(self) -> None:
        required = (
            "tooling_export_route_switch_state",
            "npi_p6_08_routes_disabled",
            "set_tooling_export_route_switch true true",
            "set_tooling_export_route_switch false false",
            "run_tooling_export_runtime_verifier fresh",
            "run_tooling_export_route_probe disabled",
            "run_tooling_export_route_probe recovered",
            "run_tooling_export_runtime_verifier replay-only",
            "verify_tooling_export_runtime_log_redaction",
            "restore_tooling_export_route_switch",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_import_runtime_verifier replay-only"),
            self.shell.index("run_tooling_export_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_export_route_probe disabled"),
            self.shell.index("run_tooling_export_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_tooling_export_route_probe recovered"),
            self.shell.index("run_tooling_export_runtime_verifier replay-only"),
        )

    def test_manual_workflow_records_exact_cumulative_scope(self) -> None:
        self.assertIn(
            "name: P5 controlled document runtime and P6 Tooling through export",
            self.workflow,
        )
        self.assertIn("Verify cumulative P5 and P6-08 controlled runtime", self.workflow)
        self.assertIn("scope=p5-01-through-p6-08", self.workflow)
        self.assertIn("predecessor_scope=p5-01-through-p6-07", self.workflow)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            self.workflow,
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)


if __name__ == "__main__":
    unittest.main()
