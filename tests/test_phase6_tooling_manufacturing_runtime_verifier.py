from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_manufacturing_runtime.py"
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
            "verify_tooling_runtime",
            "verify_tooling_revision_runtime",
            "verify_tooling_manufacturing_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_manufacturing_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling manufacturing runtime verifier cannot be imported")
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


class Phase6ToolingManufacturingRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_and_scope_are_synthetic_and_bounded(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.TENANT_ID, "runtime-tenant")
        self.assertEqual(module.ADMINISTRATOR_USER, "Administrator")
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertEqual(
            module.MANUFACTURING_DOCTYPES,
            (
                "NPI Tooling Manufacturing Plan Revision",
                "NPI Tooling Manufacturing Milestone Observation",
            ),
        )
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("supplier command", self.source)
        self.assertNotIn("lifecycle transition", self.source)
        self.assertNotIn("editErpProjection\": True", self.source)
        self.assertIn(
            '"roleAssignments": [retained_role_payload]',
            self.source,
        )
        self.assertIn(
            '"raciAssignments": [',
            self.source,
        )
        self.assertNotIn('"roleAssignments": []', self.source)
        self.assertNotIn('"raciAssignments": []', self.source)

    def test_payloads_bind_release_milestone_dependency_and_file_evidence(self) -> None:
        module = self.module
        member = {
            "globalId": "10000000-0000-4000-8000-000000000001",
            "userId": "Administrator",
            "optimisticVersion": 1,
        }
        released = {
            "revisionGlobalId": "20000000-0000-4000-8000-000000000002",
            "revisionSnapshotHash": "a" * 64,
            "lifecycleGlobalId": "30000000-0000-4000-8000-000000000003",
            "lifecycleVersion": 5,
            "releaseEventGlobalId": "40000000-0000-4000-8000-000000000004",
            "releaseEventHash": "b" * 64,
            "releaseSnapshotHash": "c" * 64,
        }
        plan_one = module.plan_payload(
            "50000000-0000-4000-8000-000000000005",
            "d" * 64,
            member,
            released,
            version=1,
        )
        plan_two = module.plan_payload(
            "50000000-0000-4000-8000-000000000005",
            "d" * 64,
            member,
            released,
            version=2,
        )
        self.assertNotIn("expectedVersion", plan_one)
        self.assertEqual(plan_two["expectedVersion"], 1)
        self.assertEqual(plan_one["sourcingStrategy"], "hybrid")
        self.assertEqual(plan_one["designReleaseEvidence"], [released])
        self.assertEqual(plan_one["evidence"][0]["document"], released)
        internal, supplier = plan_one["milestones"]
        self.assertEqual(internal["responsibilityKind"], "internal")
        self.assertEqual(internal["responsibleMember"], member)
        self.assertEqual(supplier["responsibilityKind"], "supplier")
        self.assertIsNone(supplier["responsibleMember"])
        self.assertEqual(
            supplier["predecessorGlobalIds"],
            [module.INTERNAL_MILESTONE_ID],
        )
        plan_response = {
            **plan_one,
            "globalId": "60000000-0000-4000-8000-000000000006",
            "snapshotHash": "e" * 64,
            "milestones": [
                {**internal, "snapshotHash": "f" * 64},
                {**supplier, "snapshotHash": "1" * 64},
            ],
        }
        evidence = {
            "role": "progress_evidence",
            "fileRevisionGlobalId": "70000000-0000-4000-8000-000000000007",
            "fileOptimisticVersion": 2,
            "frappeContentHash": "2" * 32,
            "sha256": "3" * 64,
        }
        observation_one = module.observation_payload(
            plan_response,
            evidence,
            version=1,
        )
        observation_two = module.observation_payload(
            plan_response,
            evidence,
            version=2,
        )
        self.assertNotIn("expectedVersion", observation_one)
        self.assertEqual(observation_two["expectedVersion"], 1)
        self.assertEqual(observation_one["milestoneSnapshotHash"], "1" * 64)
        self.assertEqual(observation_one["evidence"], [evidence])

    def test_request_delegates_to_closed_predecessor_transport(self) -> None:
        module = self.module
        raw = SimpleNamespace(
            status=200,
            headers={"X-Request-ID": "request"},
            body={"items": []},
        )
        with patch.object(
            module.predecessor,
            "tooling_request",
            return_value=raw,
        ) as request:
            result = module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/tooling/master/manufacturing-plans",
                query_key="manufacturing-list",
            )
        self.assertIs(result, raw)
        self.assertEqual(request.call_args.kwargs["query_key"], "p604-manufacturing-list")

    def test_shell_orchestrates_independent_fail_closed_switch_and_cleanup(self) -> None:
        required = (
            "tooling_manufacturing_route_switch_state",
            "npi_p6_04_routes_disabled",
            "set_tooling_manufacturing_route_switch true true",
            "set_tooling_manufacturing_route_switch false false",
            "run_tooling_manufacturing_runtime_verifier fresh",
            "run_tooling_manufacturing_route_probe disabled",
            "run_tooling_manufacturing_route_probe recovered",
            "run_tooling_manufacturing_runtime_verifier replay-only",
            "restore_tooling_manufacturing_route_switch",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_revision_runtime_verifier replay-only"),
            self.shell.index("run_tooling_manufacturing_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_manufacturing_route_probe disabled"),
            self.shell.index("run_tooling_manufacturing_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_tooling_manufacturing_route_probe recovered"),
            self.shell.index("run_tooling_manufacturing_runtime_verifier replay-only"),
        )

    def test_verifier_covers_immutability_replay_idor_and_unavailable_truth(self) -> None:
        required = (
            "TOOLING_IDEMPOTENCY_CONFLICT",
            "TOOLING_VERSION_CONFLICT",
            "TOOLING_REFERENCE_UNAVAILABLE",
            "TOOLING_MANUFACTURING_ROUTES_DISABLED",
            "P6-04 unreleased Document selection drifted",
            "UNRELEASED_REFERENCE_KEY",
            "unauthorized and absent Projects are distinguishable",
            "cross-Project and absent Plans are distinguishable",
            "accepted generic mutation",
            "cross-process replay changed immutable cardinality",
            "tooling_lifecycle_policy_unavailable",
            "erp_projection_unavailable",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.source)

    def test_manual_controlled_workflow_records_exact_cumulative_scope(self) -> None:
        self.assertIn(
            "name: P5 controlled document runtime and P6 Tooling through export",
            self.workflow,
        )
        self.assertIn("Verify cumulative P5 and P6-08 controlled runtime", self.workflow)
        self.assertIn("scope=p5-01-through-p6-08", self.workflow)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            self.workflow,
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)


if __name__ == "__main__":
    unittest.main()
