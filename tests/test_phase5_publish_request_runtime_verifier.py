from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_publish_request_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved = {
        name: sys.modules.pop(name, None)
        for name in (
            "verify_document_runtime",
            "verify_ebom_runtime",
            "verify_publish_request_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_publish_request_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Publish-request runtime verifier cannot be imported")
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


class Phase5PublishRequestRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_is_bounded_synthetic_and_separate(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertRegex(module.PUBLISH_POLICY_ID, r"^[a-f0-9-]{36}$")
        self.assertRegex(module.PUBLISH_POLICY_VERSION_ID, r"^[a-f0-9-]{36}$")
        self.assertNotEqual(
            module.PUBLISH_POLICY_ID,
            module.PUBLISH_POLICY_VERSION_ID,
        )
        self.assertEqual(
            module.PUBLISH_POLICY_VERSION_KEY,
            f"{module.PUBLISH_POLICY_ID}:1",
        )
        self.assertTrue(module.PUBLISH_POLICY_KEY.startswith("p5_05_runtime_"))
        self.assertEqual(
            module.PREDECESSOR_ROUTE_QUERY,
            "p505-predecessor-route-isolation",
        )
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("ERP-", self.source)

    def test_create_payload_is_closed_mock_exact_revision_only(self) -> None:
        context = {
            "projectId": "10000000-0000-4000-8000-000000000001",
            "ebomId": "10000000-0000-4000-8000-000000000002",
            "ebomVersion": 3,
            "revisionId": "10000000-0000-4000-8000-000000000003",
            "revisionHash": "a" * 64,
            "lifecycleVersion": 4,
        }
        payload = self.module.create_payload(context, "b" * 64)
        self.assertEqual(
            set(payload),
            {
                "expectedEbomVersion",
                "expectedRevisionSnapshotHash",
                "expectedLifecycleVersion",
                "publishPolicyGlobalId",
                "publishPolicyVersion",
                "publishPolicySnapshotHash",
                "targetMode",
                "confirmed",
                "confirmationIntent",
                "reason",
            },
        )
        self.assertEqual(payload["targetMode"], "mock")
        self.assertEqual(payload["expectedEbomVersion"], 3)
        self.assertEqual(payload["expectedLifecycleVersion"], 4)
        self.assertNotIn("operation", payload)
        self.assertNotIn("payload", payload)
        serialized = str(payload).casefold()
        for forbidden in (
            "itemcode",
            "stockuom",
            "formalmbom",
            "endpoint",
            "credential",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_diagnostic_is_allowlisted_and_response_neutral(self) -> None:
        module = self.module
        trace_id = "trace-" + ("a" * 32)
        error = module.RuntimeStageFailure(
            "P505_RUNTIME_CREATE",
            trace_id,
            exception_type="ValidationError",
        )
        self.assertEqual(
            module.runtime_stage_diagnostic(error),
            (
                "[diagnostic_code=P505_RUNTIME_CREATE; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        with self.assertRaises(ValueError):
            module.RuntimeStageFailure(
                "P505_NOT_ALLOWED",
                trace_id,
                exception_type="ValidationError",
            )
        with self.assertRaises(ValueError):
            module.RuntimeStageFailure(
                "P505_RUNTIME_CREATE",
                "trace-secret",
                exception_type="ValidationError",
            )
        self.assertNotIn("message", module.runtime_stage_diagnostic(error))
        self.assertNotIn("traceback", module.runtime_stage_diagnostic(error))

        fixture_error = module.FixtureStageFailure(
            "P505_RUNTIME_POLICY_VERSION_INSERT",
            exception_type="ValidationError",
        )
        self.assertEqual(
            module.fixture_stage_diagnostic(fixture_error),
            (
                "[fixture_diagnostic_code=P505_RUNTIME_POLICY_VERSION_INSERT; "
                "exc_type=ValidationError]"
            ),
        )
        diagnostic = module.fixture_stage_diagnostic(fixture_error)
        self.assertNotIn("message", diagnostic)
        self.assertNotIn("traceback", diagnostic)
        with self.assertRaises(ValueError):
            module.FixtureStageFailure(
                "P505_RUNTIME_CREATE",
                exception_type="ValidationError",
            )

    def test_bench_fixture_translates_only_allowlisted_safe_marker(self) -> None:
        module = self.module
        completed = module.subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr=(
                "[fixture_diagnostic_code=P505_RUNTIME_POLICY_ROOT_INSERT; "
                "exc_type=ValidationError]\n"
            ),
        )
        path_type = type(module.BENCH_PATH)
        with patch.object(path_type, "is_dir", return_value=True), patch.object(
            path_type, "is_symlink", return_value=False
        ), patch.object(
            path_type, "resolve", return_value=module.BENCH_PATH
        ), patch.object(
            module.subprocess, "run", return_value=completed
        ), self.assertRaises(module.RuntimeStageFailure) as raised:
            module.run_bench_fixture("provision_publish_policy", {})
        self.assertEqual(raised.exception.code, "P505_RUNTIME_POLICY_ROOT_INSERT")
        self.assertEqual(raised.exception.exception_type, "ValidationError")

    def test_policy_fixture_uses_guarded_admin_boundary(self) -> None:
        self.assertIn("with publish_policy_write():", self.source)
        self.assertIn('"publication_state": "published"', self.source)
        self.assertIn('"target_mode": "mock"', self.source)
        self.assertIn('"requester_user_ids": [actor_user_id]', self.source)
        self.assertIn("frappe.db.commit()", self.source)
        self.assertIn("frappe.db.rollback()", self.source)
        self.assertNotIn("create_resource(", self.source)
        self.assertNotIn("update_resource(", self.source)
        self.assertNotIn("ignore_" + "permissions", self.source)
        self.assertNotIn("frappe.db." + "sql(", self.source)

    def test_policy_fixture_result_is_exact_and_actor_bound(self) -> None:
        module = self.module
        project_id = "10000000-0000-4000-8000-000000000001"
        result = {
            "fixtureRunId": module.FIXTURE_RUN_ID,
            "policyGlobalId": module.PUBLISH_POLICY_ID,
            "policyVersionGlobalId": module.PUBLISH_POLICY_VERSION_ID,
            "publicationState": "published",
            "snapshotHash": "a" * 64,
        }
        with patch.object(module, "run_bench_fixture", return_value=result) as call:
            policy_hash = module.ensure_policy(project_id)
        self.assertEqual(policy_hash, "a" * 64)
        call.assert_called_once_with(
            "provision_publish_policy",
            {
                "fixture_run_id": module.FIXTURE_RUN_ID,
                "project_id": project_id,
                "actor_user_id": module.ACTOR_USER,
            },
        )

    def test_runtime_shell_orders_publish_after_released_ebom(self) -> None:
        required = (
            'npi_p5_05_routes_disabled "${value}"',
            "run_publish_request_runtime_verifier fresh",
            "run_publish_request_route_probe disabled",
            "run_publish_request_route_probe recovered",
            "run_publish_request_runtime_verifier replay-only",
            "restore_publish_request_route_switch",
        )
        for fragment in required:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)
        self.assertIn(
            'publish_request_route_disable_original_state}" != "absent"',
            self.shell,
        )
        self.assertLess(
            self.shell.index("run_engineering_bom_runtime_verifier replay-only"),
            self.shell.index("run_publish_request_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_publish_request_runtime_verifier replay-only"),
            self.shell.index("run_document_runtime_verifier replay-only"),
        )

    def test_controlled_lane_records_cumulative_scope_without_secrets(self) -> None:
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        for fragment in (
            "P5 controlled document, EBOM, and publish runtime",
            "bash scripts/verify-frappe-runtime.sh --document-only",
            "scope=p5-01-through-p5-05",
            "docker compose down --volumes",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core." + "whjichen.cn", runtime_job)

    def test_no_dispatch_outbox_or_target_identifiers_are_required(self) -> None:
        self.assertIn('"NPI Outbox Message"', self.source)
        self.assertIn('"outboxMessages": 0', self.source)
        self.assertIn('"dispatchAllowed": False', self.source)
        self.assertIn('"formalTargetIdentifiers": 0', self.source)
        self.assertIn('results[0].get("formalItemCode") is None', self.source)
        self.assertIn('results[0].get("formalMbomId") is None', self.source)
        self.assertNotIn("requests.", self.source)
        self.assertNotIn("urllib.request.urlopen", self.source)


if __name__ == "__main__":
    unittest.main()
