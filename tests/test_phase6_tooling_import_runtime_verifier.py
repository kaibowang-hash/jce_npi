from __future__ import annotations

import importlib.util
import hashlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_import_runtime.py"
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
        "verify_tooling_import_runtime_contract",
    )
    saved = {name: sys.modules.pop(name, None) for name in module_names}
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_import_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling import runtime verifier cannot be imported")
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


class Phase6ToolingImportRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_and_sources_are_synthetic_and_exact(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.TENANT_ID, "runtime-tenant")
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertEqual(
            [item["fileName"] for item in module.FIXTURES],
            [
                "p6-07-synthetic-title-row-deleted.xlsx",
                "p6-07-synthetic-title-rows-inserted.xlsx",
            ],
        )
        self.assertEqual(
            [item["sha256"] for item in module.FIXTURES],
            [
                "b807aca4ef6776a0ad6e8eada1c8291b3a13dbe32724828d33661d67bc8e684f",
                "f1c67a991bb59cffbee208fcc786ee44de342d3a2cf56da31d3422c9026459b4",
            ],
        )
        self.assertEqual(
            [(item["headerRow"], item["rollbackMode"]) for item in module.FIXTURES],
            [(2, "allowed"), (4, "denied")],
        )
        fixture_id = module.deterministic_uuid("controlled-fixture")
        self.assertEqual(UUID(fixture_id).version, 4)
        self.assertEqual(fixture_id, module.deterministic_uuid("controlled-fixture"))
        self.assertNotEqual(
            fixture_id,
            module.deterministic_uuid("different-controlled-fixture"),
        )
        self.assertIn(
            'validate_local_fixture_inputs(\n        arguments.base_url,\n        "Administrator",',
            self.source,
        )
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("requests.post", self.source)
        self.assertNotIn("erpnext_url", self.source.casefold())

    def test_route_contract_is_project_and_batch_scoped(self) -> None:
        module = self.module
        project_id = "10000000-0000-4000-8000-000000000001"
        batch_id = "20000000-0000-4000-8000-000000000002"
        preview_id = "30000000-0000-4000-8000-000000000003"
        job_id = "40000000-0000-4000-8000-000000000004"
        base = f"/api/npi/v1/projects/{project_id}/tooling-imports/{batch_id}"
        self.assertEqual(module.batch_path(project_id, batch_id), base)
        self.assertEqual(module.inspection_path(project_id, batch_id), f"{base}/inspections")
        self.assertEqual(
            module.confirmation_path(project_id, batch_id, preview_id),
            f"{base}/previews/{preview_id}/confirmations",
        )
        self.assertEqual(
            module.execute_path(project_id, batch_id, preview_id),
            f"{base}/previews/{preview_id}:execute",
        )
        self.assertEqual(
            module.retry_path(project_id, batch_id, job_id),
            f"{base}/jobs/{job_id}:retry",
        )
        self.assertEqual(
            module.rollback_path(project_id, batch_id, job_id),
            f"{base}/jobs/{job_id}:rollback",
        )

    def test_request_delegates_to_closed_predecessor_transport(self) -> None:
        raw = SimpleNamespace(status=200, headers={}, body={})
        with patch.object(
            self.module.predecessor,
            "tooling_request",
            return_value=raw,
        ) as request:
            result = self.module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/tooling-imports",
                query_key="imports",
            )
        self.assertIs(result, raw)
        self.assertEqual(request.call_args.kwargs["query_key"], "p607-imports")

    def test_command_request_identity_is_stable_uuid4(self) -> None:
        raw = SimpleNamespace(status=201, headers={}, body={})
        with patch.object(
            self.module.predecessor,
            "tooling_request",
            return_value=raw,
        ) as request:
            result = self.module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/tooling-imports",
                method="POST",
                payload={},
                csrf_token="csrf",
                idempotency_key="p6-07-command",
            )
        self.assertIs(result, raw)
        request_id = request.call_args.kwargs["request_id"]
        self.assertEqual(UUID(request_id).version, 4)
        self.assertEqual(
            request_id,
            self.module.deterministic_uuid("request:p6-07-command"),
        )
        self.assertIn(
            'headers["X-Request-ID"] = deterministic_uuid(f"request:{idempotency_key}")',
            self.source,
        )

    def test_verifier_covers_complete_controlled_import_lifecycle(self) -> None:
        required = (
            "build_sanitized_tooling_workbook",
            'len(columns) == 43',
            'len(preview_rows) == 3',
            'expected_state="partially_succeeded"',
            'item.get("state") == "failed_retryable"',
            'sum(item.get("state") == "created" for item in partial_latest) == 1',
            '("total daily output", "formula_error")',
            'artifact.get("entryCount") == 2',
            'b"\\xef\\xbb\\xbfworksheet_name,source_row,source_header,corrected_value\\n"',
            "hashlib.sha256(content).hexdigest() == artifact_content_hash",
            'len(succeeded["rowResults"]) == 5',
            'counts["NPI Tooling Import Row Result"] == 10',
            'expected_attempt=2',
            "failed-row-only retry or successful-row non-duplication drifted",
            'item.get("state") == "matched"',
            '"rolled_back" if fixture["rollbackMode"] == "allowed"',
            'else "rollback_denied"',
            "seed_tooling_import_downstream_reference",
            "p6-07.synthetic-execution-mapping.v1",
            "partial_row_diagnostic(partial_latest)",
            "IMPORT_TARGET_DIAGNOSTIC_CODES",
            'key.endswith("-correction")',
            "CORRECTION_DIAGNOSTIC_CODES",
            "CORRECTION_VALIDATION_DIAGNOSTIC_CODES",
            "CORRECTION_DOWNLOAD_DIAGNOSTIC_CODES",
            'key.endswith("-reconcile")',
            "RECONCILIATION_DIAGNOSTIC_CODES",
            "RECONCILIATION_VALIDATION_DIAGNOSTIC_CODES",
            "RECONCILIATION_DOMAIN_PATHS",
            '"productionMappingActive": False',
            '"integrationTrafficCreated": False',
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.source)

    def test_correction_entries_cover_both_fixture_validation_failures(self) -> None:
        job = {
            "rowResults": [
                {
                    "worksheetName": "Synthetic Tooling List",
                    "sourceRow": 3,
                    "attempt": 1,
                    "state": "failed_retryable",
                    "fieldResults": [
                        {
                            "sourceHeader": "total daily output",
                            "resultCode": "formula_error",
                        }
                    ],
                },
                {
                    "worksheetName": "Synthetic Tooling List",
                    "sourceRow": 4,
                    "attempt": 1,
                    "state": "failed_retryable",
                    "fieldResults": [
                        {
                            "sourceHeader": "Part Name English",
                            "resultCode": "required_value_missing",
                        }
                    ],
                },
                {
                    "worksheetName": "Synthetic Tooling List",
                    "sourceRow": 6,
                    "attempt": 1,
                    "state": "created",
                    "fieldResults": [],
                },
            ]
        }

        corrections = self.module.correction_entries(
            job,
            "Synthetic corrected part",
            "2001",
        )

        self.assertEqual(len(corrections), 2)
        self.assertEqual(
            {
                (item["sourceHeader"], item["correctedValue"])
                for item in corrections
            },
            {
                ("Part Name English", "Synthetic corrected part"),
                ("total daily output", "2001"),
            },
        )
    def test_correction_download_diagnostic_is_closed_and_exact(self) -> None:
        content = (
            b"\xef\xbb\xbfworksheet_name,source_row,source_header,corrected_value\n"
            b"Synthetic Tooling List,4,Part Name English,Synthetic corrected part\n"
            b"Synthetic Tooling List,3,total daily output,2001\n"
        )
        checks = self.module.correction_download_checks(
            SimpleNamespace(
                status=200,
                content=content,
                headers={"Idempotency-Replayed": "false"},
            ),
            corrected_value="Synthetic corrected part",
            corrected_formula_value="2001",
            artifact_content_hash=hashlib.sha256(content).hexdigest(),
        )

        self.assertTrue(all(checks.values()))
        self.assertEqual(
            set(checks),
            {
                "statusOk",
                "csvPreambleOk",
                "digestOk",
                "partCorrectionPresent",
                "formulaCorrectionPresent",
                "freshReceipt",
            },
        )
        diagnostic = self.module.correction_download_diagnostic(
            SimpleNamespace(
                status=404,
                problem={"code": "TOOLING_REFERENCE_UNAVAILABLE"},
            ),
            {key: False for key in checks},
        )
        self.assertEqual(diagnostic["httpStatus"], 404)
        self.assertEqual(
            diagnostic["problemCode"],
            "TOOLING_REFERENCE_UNAVAILABLE",
        )
        self.assertNotIn("problem", diagnostic)

    def test_reconciliation_domain_diagnostic_only_accepts_one_allowlisted_path(
        self,
    ) -> None:
        self.assertEqual(
            self.module.reconciliation_domain_path(
                {
                    "fieldErrors": [
                        {
                            "path": "rowResultGlobalId",
                            "message": "must not be copied",
                            "value": "must not be copied",
                        }
                    ]
                }
            ),
            "rowResultGlobalId",
        )
        self.assertIsNone(
            self.module.reconciliation_domain_path(
                {"fieldErrors": [{"path": "secretValue", "message": "secret"}]}
            )
        )
        self.assertIsNone(
            self.module.reconciliation_domain_path(
                {
                    "fieldErrors": [
                        {"path": "state"},
                        {"path": "targetGlobalId"},
                    ]
                }
            )
        )

    def test_failure_boundaries_are_fail_closed_and_cardinality_checked(self) -> None:
        required = (
            "TOOLING_IDEMPOTENCY_CONFLICT",
            "TOOLING_REFERENCE_UNAVAILABLE",
            "TOOLING_IMPORT_ROUTES_DISABLED",
            "unauthorized and absent import scopes are distinguishable",
            "unauthorized and absent command scopes are distinguishable",
            "failed commands changed business, receipt, audit, or integration truth",
            'conflicting_scenario=scenarios[1]',
            "conflicting source fixture is not a valid alternate reference",
            "cross-process replay changed immutable or integration cardinality",
            "controlled import created ERP integration traffic",
            "production mapping state was persisted",
            "accepted generic mutation",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.source)

    def test_idor_fixture_has_transport_access_without_system_manager_bypass(self) -> None:
        idor_source = self.source.split("def verify_idor(", 1)[1].split(
            "def verify_conflict_rollback(",
            1,
        )[0]
        self.assertIn("document_runtime.create_internal_fixture_user(", idor_source)
        self.assertNotIn("create_resource(", idor_source)
        self.assertNotIn('"System Manager"', idor_source)
        self.assertEqual(
            idor_source.count(
                'validate_problem(denied_command, 403, "PERMISSION_DENIED")'
            ),
            1,
        )
        self.assertEqual(
            idor_source.count(
                'validate_problem(absent_command, 403, "PERMISSION_DENIED")'
            ),
            1,
        )

    def test_bench_mutations_are_fixed_site_synthetic_fixtures(self) -> None:
        required = (
            "document_runtime._validated_runtime_site()",
            "P6-07 fresh synthetic File Revision already exists",
            "containsCustomerData",
            "temporary_directory / file_name",
            '"fileName": file_name',
            "approved_fixture",
            "run_tooling_import_job(job_id, expected_snapshot_hash)",
            "with tooling_command_write():",
            "FrappeToolingRepository._insert_requirement(value)",
            "BENCH_PATH.resolve() == BENCH_PATH",
            "completed.stderr[-2000:]",
            '"live-private-file": has_live_private_file_identity(revision)',
            '"P6-07 synthetic live private File identity drifted: "',
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.source)
        source_fixture = self.source.split(
            "def seed_tooling_import_fixture(",
            1,
        )[1].split("def seed_tooling_import_mapping_activation(", 1)[0]
        self.assertIn('"doctype": "File"', source_fixture)
        self.assertIn('"content": content', source_fixture)
        bypass_keyword = "ignore_" + "permissions"
        self.assertIn(f".insert({bypass_keyword}=True)", source_fixture)
        self.assertNotIn("save_file(", source_fixture)
        self.assertNotIn("production_mapping", self.source.split("BENCH_FIXTURES =", 1)[1])

    def test_shell_orchestrates_independent_fail_closed_switch_and_cleanup(self) -> None:
        required = (
            "tooling_import_route_switch_state",
            "npi_p6_07_routes_disabled",
            "set_tooling_import_route_switch true true",
            "set_tooling_import_route_switch false false",
            "run_tooling_import_runtime_verifier fresh",
            "run_tooling_import_route_probe disabled",
            "run_tooling_import_route_probe recovered",
            "run_tooling_import_runtime_verifier replay-only",
            "verify_tooling_import_runtime_log_redaction",
            "restore_tooling_import_route_switch",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_acceptance_runtime_verifier replay-only"),
            self.shell.index("run_tooling_import_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_import_route_probe disabled"),
            self.shell.index("run_tooling_import_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_tooling_import_route_probe recovered"),
            self.shell.index("run_tooling_import_runtime_verifier replay-only"),
        )

    def test_manual_controlled_workflow_records_exact_cumulative_scope(self) -> None:
        self.assertIn(
            "name: P5 controlled document runtime and P6 Tooling through import",
            self.workflow,
        )
        self.assertIn("Verify cumulative P5 and P6-07 controlled runtime", self.workflow)
        self.assertIn("scope=p5-01-through-p6-07", self.workflow)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            self.workflow,
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)


if __name__ == "__main__":
    unittest.main()
