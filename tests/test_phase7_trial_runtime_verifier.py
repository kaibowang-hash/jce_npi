from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_trial_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved = {
        name: sys.modules.pop(name, None)
        for name in ("verify_document_runtime", "verify_trial_runtime_contract")
    }
    spec = importlib.util.spec_from_file_location(
        "verify_trial_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Trial runtime verifier cannot be imported")
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
        for name in tuple(saved):
            sys.modules.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                sys.modules[name] = value
    return module


class Phase7TrialRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_failure_diagnostic_exposes_only_bounded_contract_keys(self) -> None:
        result = self.module.HttpResult(
            status=422,
            headers=Mock(),
            body={
                "code": "VALIDATION_FAILED",
                "fieldErrors": [
                    {
                        "path": "resources[0].sourceObjectId",
                        "message": "Synthetic raw value must never reach the log.",
                    },
                    {"path": "invalid path", "message": "ignored"},
                ],
                "request": {"objective": "Synthetic secret objective"},
            },
        )
        detail = self.module.sanitized_trial_failure(result)
        self.assertEqual(
            detail,
            (
                " [problem_code=VALIDATION_FAILED; "
                "field_paths=resources[0].sourceObjectId]"
            ),
        )
        self.assertNotIn("raw value", detail)
        self.assertNotIn("secret objective", detail)

    def test_verifier_uses_only_the_fixed_disposable_runtime(self) -> None:
        required = (
            'SITE_NAME = document_runtime.SITE_NAME',
            'RUNTIME_MARKER = document_runtime.RUNTIME_MARKER',
            'BENCH_PATH = ROOT / "tmp" / "frappe-bench"',
            "BENCH_PATH.resolve() == BENCH_PATH",
            "validate_local_fixture_inputs",
            "document_runtime._validated_runtime_site()",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("requests.post", self.source)
        self.assertNotIn("erpnext_url", self.source.casefold())

    def test_runtime_proves_exact_plan_round_action_and_unavailable_resources(self) -> None:
        required = (
            '"NPI Trial Plan Revision"',
            '"NPI Trial Round"',
            '"NPI Trial Round Lifecycle Event"',
            '"NPI Trial Plan Work Link"',
            '"NPI Trial Command Idempotency"',
            '"resource_reservation"',
            '"approved_booking_policy_not_configured"',
            '"bookingState") == "unavailable"',
            '"planning_intent_only"',
            'round_id not in {plan_id, initial_id, successor_id}',
            '"currentState") == "planned"',
            '"domainWorkItemGlobalId"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_revision_fixture_does_not_resubmit_server_owned_plan_identity(self) -> None:
        payload = self.module.revise_payload(
            {
                "toolingMasterGlobalId": "0878087f-6192-4e40-862d-05e0a5927638",
                "globalId": "4a02b83c-e069-4da2-835c-c9b42cc1246e",
                "snapshotHash": "a" * 64,
                "planVersion": 1,
            }
        )
        self.assertNotIn("toolingMasterGlobalId", payload)
        self.assertEqual(
            set(payload),
            {
                "expectedRevisionGlobalId",
                "expectedRevisionSnapshotHash",
                "expectedPlanVersion",
                "purpose",
                "objective",
                "plannedStartAt",
                "plannedEndAt",
                "resources",
                "responsibleMemberGlobalIds",
                "sampleQuantity",
                "measurementPlan",
                "reason",
            },
        )

    def test_runtime_proves_replay_conflict_rollback_and_idor(self) -> None:
        required = (
            'validate_problem(create_conflict, 409, "TRIAL_IDEMPOTENCY_CONFLICT")',
            'validate_problem(stale, 409, "TRIAL_VERSION_CONFLICT")',
            'validate_problem(duplicate_label, 409, "TRIAL_LABEL_CONFLICT")',
            'validate_problem(denied, 404, "TRIAL_UNAVAILABLE")',
            'validate_problem(cross_project, 404, "TRIAL_UNAVAILABLE")',
            '"P7-02 cross-process replay changed immutable cardinality or integration truth"',
            '"P7-01 same-process action replay changed sealed response truth"',
            '"rollbackVerified": True',
            'validate_problem(stale_prepare, 409, "TRIAL_EXECUTION_CONFLICT")',
            'validate_problem(stale_actual, 409, "TRIAL_EXECUTION_CONFLICT")',
            '"P7-02 same-process evidence replay changed sealed response truth"',
            '"P7-02 cross-process execution command was not replayed"',
            '"TRIAL_EXECUTION_UNAVAILABLE"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_runtime_proves_guarded_metadata_and_no_integration_traffic(self) -> None:
        required = (
            "verify_trial_runtime_schema",
            "frappe.db.table_exists(doctype)",
            "verify_generic_mutation_denial",
            "rejected_update.status in {403, 417}",
            "rejected_delete.status in {403, 417}",
            '"NPI Outbox Message"',
            '"NPI Inbox Message"',
            '"P7-01 controlled Trial planning created ERP integration traffic"',
            '"integrationTrafficCreated": False',
            '"NPI Trial Input Lock Revision"',
            '"NPI Trial Actual Revision"',
            '"NPI Trial Sample Batch Revision"',
            '"NPI Trial Evidence Reference"',
            '"trial_evidence.content.read"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_shell_orchestrates_switch_replay_redaction_and_cleanup(self) -> None:
        required = (
            "--trial-only",
            "trial_route_switch_state",
            "npi_p7_01_routes_disabled",
            "trial_execution_route_switch_state",
            "npi_p7_02_routes_disabled",
            "set_trial_route_switch false false",
            "set_trial_route_switch true true",
            "set_trial_execution_route_switch false false",
            "set_trial_execution_route_switch true true",
            "run_trial_runtime_verifier fresh",
            "run_trial_route_probe planning-disabled",
            "run_trial_route_probe planning-recovered",
            "run_trial_route_probe execution-disabled",
            "run_trial_route_probe execution-recovered",
            "run_trial_runtime_verifier replay-only",
            "verify_trial_runtime_log_redaction",
            "restore_trial_route_switch",
            "restore_trial_execution_route_switch",
            "Failed to restore the P7-01 route-disable switch to absent.",
            "Failed to restore the P7-02 route-disable switch to absent.",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_export_runtime_verifier replay-only"),
            self.shell.index("run_trial_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_trial_route_probe planning-disabled"),
            self.shell.index("run_trial_route_probe planning-recovered"),
        )
        self.assertLess(
            self.shell.index("run_trial_route_probe execution-recovered"),
            self.shell.index("run_trial_runtime_verifier replay-only"),
        )

    def test_shell_runs_two_migrations_and_keeps_predecessor_modes(self) -> None:
        self.assertIn('"${verification_mode}" == "--trial-only"', self.shell)
        self.assertIn("for _migration_attempt in 1 2", self.shell)
        self.assertIn("bench --site \"${site_name}\" migrate", self.shell)
        self.assertIn("run_document_runtime_verifier fresh", self.shell)
        self.assertIn("run_tooling_export_runtime_verifier fresh", self.shell)

    def test_workflow_records_exact_cumulative_scope(self) -> None:
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        required = (
            "P7-02 Trial execution",
            "Verify cumulative P5 and P6-08 controlled runtime plus P7-01 planning and P7-02 execution",
            "bash scripts/verify-frappe-runtime.sh --trial-only",
            "scope=p5-01-through-p7-02",
            "predecessor_scope=p5-01-through-p7-01",
            "p6_scope=p5-01-through-p6-08",
            "p7-trial-runtime-${{ github.run_id }}",
            "site=npi.localhost",
            "database=npi_one_runtime",
            "runtime_marker=npi-one-local-runtime-disposable-v1",
            "docker compose down --volumes",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core." + "whjichen.cn", runtime_job)

    def test_raw_trial_values_are_fail_closed_in_runtime_log(self) -> None:
        for marker in (
            "Synthetic controlled Trial planning objective",
            "Synthetic successor Trial planning objective",
            "SYN-MATERIAL-",
            "Verify synthetic dimensional evidence",
            "Controlled PA66 material observation",
            "P702-MATERIAL-",
            "Controlled dimensional laboratory",
            "p7-02-controlled-parameters.csv",
            "melt_temperature,287,degC",
            "P7-02 raw Trial execution value leaked into the runtime log.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)

    def test_runtime_proves_exact_execution_sample_and_private_evidence(self) -> None:
        required = (
            "prepare_execution_payload",
            "actual_context_payload",
            "sample_payload",
            'state="prepared"',
            'state="running"',
            'actual_successor.get("actualVersion") == 2',
            'sample_successor.get("sampleVersion") == 2',
            '"TRIAL_EXECUTION_REFERENCE_UNAVAILABLE"',
            "observe_trial_file_scan",
            'pending_file.get("scanState") == "pending"',
            'clean_body["pendingFiles"][0].get("scanState") == "clean"',
            "binary_evidence_request",
            '"machineImport": "unavailable"',
            '"erpQuality": "unavailable"',
            '"gateEffect": "unavailable"',
            '"approvedBaseline": "unavailable"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
