from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_engineering_controls_runtime.py"
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
            "verify_tooling_manufacturing_runtime",
            "verify_tooling_engineering_controls_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_engineering_controls_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling engineering-controls runtime verifier cannot be imported")
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


class Phase6ToolingEngineeringControlsRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def context(self) -> dict[str, object]:
        module = self.module
        return {
            "projectId": "10000000-0000-4000-8000-000000000001",
            "masterId": "20000000-0000-4000-8000-000000000002",
            "member": {
                "globalId": "30000000-0000-4000-8000-000000000003",
                "userId": module.ACTOR_USER,
                "optimisticVersion": 1,
            },
            "fileEvidence": {
                "role": "progress_evidence",
                "fileRevisionGlobalId": "40000000-0000-4000-8000-000000000004",
                "fileOptimisticVersion": 2,
                "frappeContentHash": "a" * 32,
                "sha256": "b" * 64,
            },
            "revisionId": "50000000-0000-4000-8000-000000000005",
            "revisionSnapshotHash": "c" * 64,
            "toolingSetId": "60000000-0000-4000-8000-000000000006",
            "toolingSetSnapshotHash": "d" * 64,
            "applicability": [
                {
                    "globalId": "70000000-0000-4000-8000-000000000007",
                    "snapshotHash": "e" * 64,
                    "partRevisionGlobalId": "80000000-0000-4000-8000-000000000008",
                    "partRevisionSnapshotHash": "f" * 64,
                }
            ],
        }

    def test_fixture_namespace_and_scope_are_synthetic_and_bounded(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.TENANT_ID, "runtime-tenant")
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertIn(
            'validate_local_fixture_inputs(\n        arguments.base_url,\n        "Administrator",',
            self.source,
        )
        self.assertEqual(
            module.ENGINEERING_CONTROL_DOCTYPES,
            (
                "NPI Tooling Defect Revision",
                "NPI Tooling Process Profile Revision",
                "NPI Tooling Capacity Scenario Revision",
            ),
        )
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("transitionGate\": True", self.source)
        self.assertNotIn("transitionToolingLifecycle\": True", self.source)
        self.assertNotIn("createTrialActual\": True", self.source)

    def test_payloads_bind_successors_evidence_layers_and_provenance(self) -> None:
        module = self.module
        context = self.context()
        defect_one = module.defect_payload(context, version=1)
        self.assertNotIn("defectGlobalId", defect_one)
        self.assertEqual(defect_one["state"], "open")
        self.assertTrue(defect_one["blocking"])
        self.assertEqual(defect_one["evidence"][0]["role"], "detection")
        predecessor_defect = {
            "defectGlobalId": "90000000-0000-4000-8000-000000000009",
            "actions": [{"globalId": "a0000000-0000-4000-8000-00000000000a"}],
        }
        defect_two = module.defect_payload(
            context,
            version=2,
            predecessor_value=predecessor_defect,
        )
        self.assertEqual(defect_two["expectedVersion"], 1)
        self.assertEqual(defect_two["actions"][0]["state"], "completed")
        self.assertEqual(defect_two["actions"][0]["evidence"][0]["role"], "action")

        profile_one = module.profile_payload(context, version=1)
        self.assertNotIn("profileGlobalId", profile_one)
        self.assertEqual(profile_one["context"]["kind"], "tooling_revision_specification")
        profile_response = {
            "globalId": "c0000000-0000-4000-8000-00000000000c",
            "profileGlobalId": "b0000000-0000-4000-8000-00000000000b",
            "snapshotHash": "1" * 64,
        }
        profile_two = module.profile_payload(
            context,
            version=2,
            predecessor_value=profile_response,
        )
        self.assertEqual(profile_two["expectedVersion"], 1)
        self.assertEqual(profile_two["metrics"][0]["numericValue"], "36.0")

        capacity_one = module.capacity_payload(
            context,
            profile_response,
            version=1,
        )
        line = capacity_one["lines"][0]
        self.assertEqual(line["cycleProvenance"]["kind"], "customer_standard")
        self.assertEqual(line["cycleProvenance"]["globalId"], profile_response["globalId"])
        self.assertEqual(line["cavityProvenance"]["kind"], "tooling_revision")
        self.assertEqual(line["usageProvenance"]["kind"], "tooling_applicability")
        self.assertEqual(line["setProvenance"]["kind"], "tooling_set_selection")

    def test_request_delegates_to_closed_predecessor_transport(self) -> None:
        module = self.module
        raw = SimpleNamespace(
            status=200,
            headers={"X-Request-ID": "request"},
            body={"defectRevisions": []},
        )
        with patch.object(
            module.predecessor,
            "tooling_request",
            return_value=raw,
        ) as request:
            result = module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/tooling/master/engineering-controls",
                query_key="controls",
            )
        self.assertIs(result, raw)
        self.assertEqual(request.call_args.kwargs["query_key"], "p605-controls")

    def test_project_context_scopes_shared_master_applicability_to_project(self) -> None:
        module = self.module
        context = self.context()
        replay = (
            context["projectId"],
            context["masterId"],
            context["applicability"][0]["globalId"],
            {},
            context["member"],
            {},
            context["fileEvidence"],
            {
                "globalId": context["revisionId"],
                "snapshotHash": context["revisionSnapshotHash"],
            },
            {},
            {},
        )
        predecessor_context = (
            context["projectId"],
            context["masterId"],
            "90000000-0000-4000-8000-000000000009",
            (),
            context["toolingSetId"],
            {},
        )

        def fixture_rows(_administrator, _base_url, doctype, filters, fields=None):
            if doctype == "NPI Tooling Set":
                return [
                    {
                        "global_id": context["toolingSetId"],
                        "snapshot_hash": context["toolingSetSnapshotHash"],
                    }
                ]
            if doctype == "NPI Tooling Applicability":
                self.assertIn(
                    ["project_global_id", "=", context["projectId"]],
                    filters,
                )
                return [
                    {
                        "global_id": context["applicability"][0]["globalId"],
                        "part_revision_global_id": context["applicability"][0][
                            "partRevisionGlobalId"
                        ],
                        "snapshot_hash": context["applicability"][0]["snapshotHash"],
                        "effective_to": None,
                    }
                ]
            if doctype == "NPI Engineering Part Revision":
                return [
                    {
                        "global_id": context["applicability"][0][
                            "partRevisionGlobalId"
                        ],
                        "snapshot_hash": context["applicability"][0][
                            "partRevisionSnapshotHash"
                        ],
                    }
                ]
            raise AssertionError(f"Unexpected fixture doctype: {doctype}")

        with (
            patch.object(module.predecessor, "replay_context", return_value=replay),
            patch.object(
                module.predecessor.predecessor,
                "project_context",
                return_value=predecessor_context,
            ),
            patch.object(module, "rows", side_effect=fixture_rows),
        ):
            resolved = module.project_context(object(), "http://127.0.0.1:8003")

        self.assertEqual(resolved["projectId"], context["projectId"])
        self.assertEqual(resolved["applicability"], context["applicability"])

    def test_shell_orchestrates_independent_fail_closed_switch_and_cleanup(self) -> None:
        required = (
            "tooling_engineering_controls_route_switch_state",
            "npi_p6_05_routes_disabled",
            "set_tooling_engineering_controls_route_switch true true",
            "set_tooling_engineering_controls_route_switch false false",
            "run_tooling_engineering_controls_runtime_verifier fresh",
            "run_tooling_engineering_controls_route_probe disabled",
            "run_tooling_engineering_controls_route_probe recovered",
            "run_tooling_engineering_controls_runtime_verifier replay-only",
            "restore_tooling_engineering_controls_route_switch",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_manufacturing_runtime_verifier replay-only"),
            self.shell.index("run_tooling_engineering_controls_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_engineering_controls_route_probe disabled"),
            self.shell.index("run_tooling_engineering_controls_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_tooling_engineering_controls_route_probe recovered"),
            self.shell.index("run_tooling_engineering_controls_runtime_verifier replay-only"),
        )

    def test_verifier_covers_required_runtime_truth_and_failure_boundaries(self) -> None:
        required = (
            "TOOLING_IDEMPOTENCY_CONFLICT",
            "TOOLING_VERSION_CONFLICT",
            "TOOLING_REFERENCE_UNAVAILABLE",
            "TOOLING_ENGINEERING_CONTROLS_ROUTES_DISABLED",
            "Customer Standard, Trial Actual, and approved baseline separation drifted",
            "immutable defect succession, action, evidence, or blocking truth drifted",
            "Capacity Scenario recomputation, bottleneck, or gap drifted",
            "unauthorized and absent Projects are distinguishable",
            "unauthorized and absent command scopes are distinguishable",
            "accepted generic mutation",
            "cross-process replay changed immutable cardinality",
            "tooling_health_policy_unavailable",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.source)

    def test_manual_controlled_workflow_records_exact_cumulative_scope(self) -> None:
        self.assertIn(
            "name: P5 controlled document runtime and P6 Tooling through engineering controls",
            self.workflow,
        )
        self.assertIn("Verify cumulative P5 and P6-05 controlled runtime", self.workflow)
        self.assertIn("scope=p5-01-through-p6-05", self.workflow)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            self.workflow,
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)


if __name__ == "__main__":
    unittest.main()
