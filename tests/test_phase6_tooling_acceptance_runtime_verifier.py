from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_acceptance_runtime.py"
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
            "verify_tooling_engineering_controls_runtime",
            "verify_tooling_acceptance_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_acceptance_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling acceptance runtime verifier cannot be imported")
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


class Phase6ToolingAcceptanceRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def context(self) -> dict[str, object]:
        return {
            "projectId": "10000000-0000-4000-8000-000000000001",
            "masterId": "20000000-0000-4000-8000-000000000002",
            "masterSnapshotHash": "a" * 64,
            "member": {
                "globalId": "30000000-0000-4000-8000-000000000003",
                "userId": self.module.ACTOR_USER,
                "optimisticVersion": 1,
            },
            "fileEvidence": {
                "fileRevisionGlobalId": "40000000-0000-4000-8000-000000000004",
                "fileOptimisticVersion": 2,
                "frappeContentHash": "b" * 32,
                "sha256": "c" * 64,
            },
            "revisionId": "50000000-0000-4000-8000-000000000005",
            "revisionNumber": 3,
            "revisionLabel": "C",
            "revisionSnapshotHash": "d" * 64,
            "toolingSetId": "60000000-0000-4000-8000-000000000006",
            "toolingSetSnapshotHash": "e" * 64,
            "bindingId": "70000000-0000-4000-8000-000000000007",
            "bindingSnapshotHash": "f" * 64,
            "requirementKind": "customer_owned_intake",
            "physicalSerial": "P6-02-PHYSICAL-001",
        }

    def acceptance(self, version: int) -> dict[str, object]:
        return {
            "globalId": f"80000000-0000-4000-8000-00000000000{version}",
            "acceptanceGlobalId": "90000000-0000-4000-8000-000000000009",
            "acceptanceVersion": version,
            "snapshotHash": str(version) * 64,
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
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("requests.post", self.source)
        self.assertNotIn("erpnext_url", self.source.casefold())

    def test_acceptance_payload_has_nine_categories_and_customer_authorization(self) -> None:
        module = self.module
        context = self.context()
        first = module.acceptance_payload(context, version=1)
        self.assertEqual(
            {item["category"] for item in first["checklist"]},
            set(module.ACCEPTANCE_CATEGORIES),
        )
        self.assertEqual(len(first["checklist"]), 9)
        self.assertNotIn("acceptanceGlobalId", first)
        self.assertNotIn("expectedVersion", first)
        self.assertEqual(
            first["repairs"][0]["customerAuthorizationEvidence"][0]["role"],
            "customer_authorization",
        )
        self.assertEqual(first["assetActions"][0]["evidence"][0]["role"], "action")
        predecessor_value = self.acceptance(1)
        second = module.acceptance_payload(
            context,
            version=2,
            predecessor_value=predecessor_value,
        )
        self.assertEqual(
            second["acceptanceGlobalId"], predecessor_value["acceptanceGlobalId"]
        )
        self.assertEqual(second["expectedVersion"], 1)

    def test_asset_request_payload_is_operation_specific_and_mock_only(self) -> None:
        module = self.module
        payload = module.asset_request_payload(self.context(), self.acceptance(2))
        self.assertEqual(payload["targetMode"], "mock")
        self.assertEqual(payload["acknowledgement"], module.ACKNOWLEDGEMENT)
        self.assertEqual(payload["acceptanceVersion"], 2)
        for forbidden in (
            "operation",
            "targetPayload",
            "assetId",
            "approvalState",
            "dispatch",
            "targetResult",
        ):
            self.assertNotIn(forbidden, payload)

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
                "/api/npi/v1/projects/project/tooling/master/acceptance-assets",
                query_key="acceptance",
            )
        self.assertIs(result, raw)
        self.assertEqual(request.call_args.kwargs["query_key"], "p606-acceptance")

    def test_project_context_binds_customer_owned_set_revision_and_master(self) -> None:
        module = self.module
        context = self.context()
        predecessor_context = {
            key: context[key]
            for key in (
                "projectId",
                "masterId",
                "member",
                "fileEvidence",
                "revisionId",
                "revisionSnapshotHash",
                "toolingSetId",
                "toolingSetSnapshotHash",
            )
        }
        predecessor_context["revisionId"] = (
            "51000000-0000-4000-8000-000000000005"
        )
        predecessor_context["revisionSnapshotHash"] = "9" * 64

        def fixture_rows(_administrator, _base_url, doctype, filters, fields=None):
            if doctype == "NPI Tooling Master":
                return [
                    {
                        "global_id": context["masterId"],
                        "snapshot_hash": context["masterSnapshotHash"],
                    }
                ]
            if doctype == "NPI Tooling Set":
                self.assertIn(["project_global_id", "=", context["projectId"]], filters)
                return [
                    {
                        "global_id": context["toolingSetId"],
                        "requirement_kind": context["requirementKind"],
                        "physical_serial": context["physicalSerial"],
                        "snapshot_hash": context["toolingSetSnapshotHash"],
                    }
                ]
            if doctype == "NPI Tooling Set Revision Binding":
                self.assertEqual(
                    filters,
                    [
                        ["project_global_id", "=", context["projectId"]],
                        ["tooling_set_global_id", "=", context["toolingSetId"]],
                    ],
                )
                return [
                    {
                        "global_id": context["bindingId"],
                        "tooling_revision_global_id": context["revisionId"],
                        "tooling_revision_snapshot_hash": context[
                            "revisionSnapshotHash"
                        ],
                        "snapshot_hash": context["bindingSnapshotHash"],
                    }
                ]
            if doctype == "NPI Tooling Revision":
                return [
                    {
                        "global_id": context["revisionId"],
                        "revision_number": context["revisionNumber"],
                        "revision_label": context["revisionLabel"],
                        "snapshot_hash": context["revisionSnapshotHash"],
                    }
                ]
            raise AssertionError(f"Unexpected fixture doctype: {doctype}")

        with (
            patch.object(
                module.predecessor,
                "project_context",
                return_value=predecessor_context,
            ),
            patch.object(module, "rows", side_effect=fixture_rows),
        ):
            resolved = module.project_context(object(), "http://127.0.0.1:8003")
        self.assertEqual(resolved["requirementKind"], "customer_owned_intake")
        self.assertEqual(resolved["bindingId"], context["bindingId"])
        self.assertEqual(resolved["revisionId"], context["revisionId"])
        self.assertEqual(
            resolved["engineeringRevisionId"],
            predecessor_context["revisionId"],
        )
        self.assertEqual(
            module.predecessor_context(resolved)["revisionId"],
            predecessor_context["revisionId"],
        )

    def test_verifier_covers_required_runtime_truth_and_failure_boundaries(self) -> None:
        required = (
            "TOOLING_IDEMPOTENCY_CONFLICT",
            "TOOLING_VERSION_CONFLICT",
            "TOOLING_REFERENCE_UNAVAILABLE",
            "VALIDATION_FAILED",
            "TOOLING_ACCEPTANCE_ASSETS_ROUTES_DISABLED",
            "customer-owned repair authorization truth drifted",
            "local Mock preparation created integration traffic",
            "accepted generic mutation",
            "cross-process replay changed immutable or integration cardinality",
            "unauthorized and absent request details are distinguishable",
            "phase_6_dispatch_prohibited",
            "zero_or_one_per_physical_set",
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

    def test_shell_orchestrates_independent_fail_closed_switch_and_cleanup(self) -> None:
        required = (
            "tooling_acceptance_assets_route_switch_state",
            "npi_p6_06_routes_disabled",
            "set_tooling_acceptance_assets_route_switch true true",
            "set_tooling_acceptance_assets_route_switch false false",
            "run_tooling_acceptance_runtime_verifier fresh",
            "run_tooling_acceptance_route_probe disabled",
            "run_tooling_acceptance_route_probe recovered",
            "run_tooling_acceptance_runtime_verifier replay-only",
            "restore_tooling_acceptance_assets_route_switch",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_engineering_controls_runtime_verifier replay-only"),
            self.shell.index("run_tooling_acceptance_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_acceptance_route_probe disabled"),
            self.shell.index("run_tooling_acceptance_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_tooling_acceptance_route_probe recovered"),
            self.shell.index("run_tooling_acceptance_runtime_verifier replay-only"),
        )

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
