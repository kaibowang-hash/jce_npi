from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_ebom_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved_document_runtime = sys.modules.pop("verify_document_runtime", None)
    spec = importlib.util.spec_from_file_location(
        "verify_ebom_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("EBOM runtime verifier cannot be imported")
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
        sys.modules.pop(spec.name, None)
        sys.modules.pop("verify_document_runtime", None)
        if saved_document_runtime is not None:
            sys.modules["verify_document_runtime"] = saved_document_runtime
    return module


class Phase5EngineeringBomRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_is_bounded_and_synthetic(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertRegex(module.POLICY_ID, r"^[a-f0-9-]{36}$")
        self.assertEqual(module.POLICY_VERSION_KEY, f"{module.POLICY_ID}:1")
        self.assertTrue(module.ENGINEERING_BOM_KEY.startswith("synthetic_ebom_"))
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertNotEqual(module.ACTOR_USER, module.UNRELATED_USER)
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("ERP-", self.source)

    def test_payloads_are_closed_to_npi_owned_ebom_truth(self) -> None:
        module = self.module
        policy_hash = "a" * 64
        payload = module.create_payload(policy_hash)
        self.assertEqual(
            set(payload),
            {
                "policyGlobalId",
                "policyVersion",
                "policySnapshotHash",
                "engineeringBomKey",
                "title",
                "reason",
                "effectivityNote",
                "lines",
            },
        )
        self.assertEqual(
            set(payload["lines"][0]),
            {
                "lineKey",
                "engineeringItemId",
                "description",
                "quantity",
                "engineeringUom",
                "effectivityStart",
                "attributes",
            },
        )
        revision = module.revision_payload(
            policy_hash,
            predecessor_id="10000000-0000-4000-8000-000000000001",
            predecessor_hash="b" * 64,
        )
        self.assertEqual(revision["expectedEbomVersion"], 2)
        self.assertEqual(len(revision["lines"]), 2)
        serialized = json.dumps({"create": payload, "revision": revision})
        for forbidden in (
            "itemCode",
            "stockUom",
            "manufacturingRouting",
            "formalMbom",
            "erpnext",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.casefold(), serialized.casefold())

    def test_diagnostic_is_exact_allowlisted_and_sanitized(self) -> None:
        module = self.module
        trace_id = "trace-" + ("a" * 32)
        expected_codes = {
            "P504_RUNTIME_EMPTY_WORKSPACE",
            "P504_RUNTIME_GUEST_AUTHORIZATION",
            "P504_RUNTIME_UNRELATED_AUTHORIZATION",
            "P504_RUNTIME_CREATE",
            "P504_RUNTIME_CREATE_REPLAY",
            "P504_RUNTIME_IDEMPOTENCY_CONFLICT",
            "P504_RUNTIME_INVALID_REVISION_ROLLBACK",
            "P504_RUNTIME_SUCCESSOR_REVISION",
            "P504_RUNTIME_COMPARISON",
            "P504_RUNTIME_SUBMIT_REVIEW",
            "P504_RUNTIME_REVIEW",
            "P504_RUNTIME_RELEASE",
            "P504_RUNTIME_STALE_TRANSITION",
            "P504_RUNTIME_FINAL_WORKSPACE",
            "P504_RUNTIME_ROUTE_DISABLED",
            "P504_RUNTIME_ROUTE_RECOVERED",
            "P504_RUNTIME_PREDECESSOR_ROUTE_ISOLATION",
            "P504_RUNTIME_REPLAY_CREATE",
            "P504_RUNTIME_REPLAY_RELEASE",
        }
        self.assertEqual(set(module._RUNTIME_STAGE_CODES), expected_codes)
        error = module.RuntimeStageFailure(
            "P504_RUNTIME_CREATE",
            trace_id,
            exception_type="ValidationError",
        )
        self.assertEqual(
            module.runtime_stage_diagnostic(error),
            (
                "[diagnostic_code=P504_RUNTIME_CREATE; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for invalid_code, invalid_trace, invalid_type in (
            ("NOT_ALLOWED", trace_id, "ValidationError"),
            ("P504_RUNTIME_CREATE", "trace-secret", "ValidationError"),
            ("P504_RUNTIME_CREATE", trace_id, "bad type"),
        ):
            with self.subTest(
                code=invalid_code,
                trace=invalid_trace,
                exception_type=invalid_type,
            ), self.assertRaises(ValueError):
                module.RuntimeStageFailure(
                    invalid_code,
                    invalid_trace,
                    exception_type=invalid_type,
                )

    def test_http_failure_discards_unvalidated_body_and_type(self) -> None:
        module = self.module
        trace_id = "trace-" + ("b" * 32)
        result = module.HttpResult(
            status=500,
            headers={},
            body={
                "exc_type": "bad type /tmp/private",
                "exception": "sensitive server traceback",
                "message": "database secret",
            },
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id=trace_id,
        )
        with self.assertRaises(module.RuntimeStageFailure) as failure:
            module.require_stage_status(
                result,
                {201},
                "P504_RUNTIME_CREATE",
            )
        self.assertEqual(failure.exception.exception_type, "HttpStatusError")
        diagnostic = module.runtime_stage_diagnostic(failure.exception)
        self.assertNotIn("traceback", diagnostic)
        self.assertNotIn("database", diagnostic)
        self.assertNotIn("/tmp", diagnostic)
        invalid_trace = module.HttpResult(
            status=500,
            headers={},
            body={},
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id="not-a-trace",
        )
        with self.assertRaisesRegex(ValueError, "trace identity"):
            module.require_stage_status(
                invalid_trace,
                {201},
                "P504_RUNTIME_CREATE",
            )

    def test_comparison_fixture_covers_exact_change_categories(self) -> None:
        before = self.module.initial_lines()
        after = self.module.successor_lines()
        self.assertEqual([line["lineKey"] for line in before], ["10"])
        self.assertEqual([line["lineKey"] for line in after], ["10", "20"])
        self.assertNotEqual(before[0]["quantity"], after[0]["quantity"])
        self.assertNotEqual(before[0]["description"], after[0]["description"])
        self.assertNotEqual(before[0]["attributes"], after[0]["attributes"])

    def test_schema_fixture_is_metadata_only_and_fail_closed(self) -> None:
        required = (
            "NPI EBOM Policy",
            "NPI EBOM Policy Version",
            "NPI Engineering BOM",
            "NPI Engineering BOM Revision",
            "NPI Engineering BOM Line",
            "NPI EBOM Revision Lifecycle",
            "NPI EBOM Lifecycle Event",
            "NPI EBOM Command Idempotency",
        )
        self.assertEqual(self.module.EBOM_DOCTYPES, required)
        for doctype in required:
            with self.subTest(doctype=doctype):
                self.assertIn(f'"{doctype}"', self.source)
        self.assertIn("cached=False", self.source)
        self.assertIn('environment.pop(variable, None)', self.source)
        self.assertNotIn("frappe.db.set_value", self.source)
        self.assertNotIn("frappe.db." + "sql(", self.source)

    def test_runtime_shell_migrates_twice_and_restores_p504_switch(self) -> None:
        required_fragments = (
            'npi_p5_04_routes_disabled "${value}"',
            "for _migration_attempt in 1 2",
            "run_engineering_bom_runtime_verifier fresh",
            "run_engineering_bom_route_probe disabled",
            "run_engineering_bom_route_probe recovered",
            "run_engineering_bom_runtime_verifier replay-only",
            "restore_engineering_bom_route_switch",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)
        self.assertIn(
            'engineering_bom_route_disable_original_state}" != "absent"',
            self.shell,
        )
        self.assertLess(
            self.shell.index("run_document_runtime_verifier fresh"),
            self.shell.index("run_engineering_bom_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_engineering_bom_runtime_verifier replay-only"),
            self.shell.index("run_document_runtime_verifier replay-only"),
        )

    def test_manual_lane_records_exact_p504_scope_without_secrets(self) -> None:
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        required_fragments = (
            "P5 controlled document and EBOM runtime",
            "bash scripts/verify-frappe-runtime.sh --document-only",
            "scope=p5-01-through-p5-04",
            "p5-document-ebom-runtime-${{ github.run_id }}",
            "docker compose down --volumes",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core." + "whjichen.cn", runtime_job)

    def test_command_propagates_exact_idempotency_header(self) -> None:
        result = self.module.HttpResult(
            status=201,
            headers={"Idempotency-Replayed": "false"},
            body={},
            request_id="10000000-0000-4000-8000-000000000001",
            trace_id="trace-" + ("c" * 32),
        )
        with patch.object(self.module, "ebom_request", return_value=result) as call:
            actual = self.module.command(
                Mock(),
                "http://127.0.0.1:8003",
                "csrf-" + ("a" * 48),
                "/api/npi/v1/projects/project/eboms",
                {"value": True},
                self.module.CREATE_KEY,
                "P504_RUNTIME_CREATE",
            )
        self.assertIs(actual, result)
        self.assertEqual(call.call_args.kwargs["idempotency_key"], self.module.CREATE_KEY)
        self.assertEqual(call.call_args.kwargs["csrf_token"], "csrf-" + ("a" * 48))


if __name__ == "__main__":
    unittest.main()
