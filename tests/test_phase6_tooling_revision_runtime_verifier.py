from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_revision_runtime.py"
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
            "verify_tooling_revision_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_revision_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling Revision runtime verifier cannot be imported")
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


class Phase6ToolingRevisionRuntimeVerifierTest(unittest.TestCase):
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
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertEqual(len(module.REVISION_DOCTYPES), 4)
        self.assertEqual(
            set(module.REVISION_DOCTYPES),
            {
                "NPI Tooling Revision",
                "NPI Part Controlled Specification",
                "NPI Tooling Process Chain Revision",
                "NPI Tooling Set Revision Binding",
            },
        )
        self.assertNotIn("core." + "whjichen.cn", self.source)
        for forbidden in (
            "production ERP",
            "supplier command",
            "lifecycle transition",
            "combined Trial command",
            "automatic impact command",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_payloads_preserve_exact_revision_specification_and_chain_truth(self) -> None:
        module = self.module
        applicability_id = "10000000-0000-4000-8000-000000000001"
        model_reference = {
            "sourceSystem": "ERPNEXT",
            "sourceObjectId": "SYNTHETIC-CURRENT-PROJECT",
        }
        revision_one = module.revision_payload(applicability_id, 1, model_reference)
        revision_two = module.revision_payload(applicability_id, 2, model_reference)
        self.assertNotIn("expectedVersion", revision_one)
        self.assertEqual(revision_two["expectedVersion"], 1)
        self.assertEqual(revision_one["cavities"][0]["structuralState"], "enabled")
        self.assertEqual(revision_one["inserts"][0]["validationState"], "validated")
        self.assertEqual(
            revision_one["inserts"][0]["model"],
            model_reference,
        )
        self.assertNotIn("RUNTIME-CUSTOMER", self.source)
        self.assertIn(
            'f"/api/npi/v1/projects/{project_id}/cockpit"',
            self.source,
        )
        self.assertEqual(len(module.part_specification_payload()["items"]), 4)
        chain = module.process_chain_payload(
            "20000000-0000-4000-8000-000000000002",
            (
                "30000000-0000-4000-8000-000000000003",
                "40000000-0000-4000-8000-000000000004",
            ),
            "50000000-0000-4000-8000-000000000005",
        )
        self.assertEqual([item["stepOrder"] for item in chain["steps"]], [1, 2])
        self.assertEqual(chain["steps"][1]["parentStepOrder"], 1)
        self.assertEqual(
            chain["steps"][1]["inputPartRevisionGlobalIds"],
            [chain["steps"][0]["outputPartRevisionGlobalId"]],
        )
        for payload in (revision_one, revision_two, module.part_specification_payload(), chain):
            serialized = str(payload).casefold()
            for forbidden in ("tenantid", "actor", "snapshot", "doctype", "lifecycle"):
                with self.subTest(forbidden=forbidden):
                    self.assertNotIn(forbidden, serialized)

    def test_request_delegates_to_closed_predecessor_transport(self) -> None:
        module = self.module
        raw = SimpleNamespace(
            status=200,
            headers={"X-Request-ID": "request"},
            body={"items": []},
        )
        with patch.object(module.predecessor, "tooling_request", return_value=raw) as request:
            result = module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/tooling/master/revisions",
                query_key="revision-list",
            )
        self.assertIs(result, raw)
        self.assertEqual(request.call_args.kwargs["query_key"], "p603-revision-list")
        self.assertNotIn("X-NPI-Diagnostic-Scope", self.source)

    def test_failed_command_reports_only_allowlisted_safe_server_diagnostic(self) -> None:
        module = self.module
        trace_id = "12345678-1234-4234-8234-123456789abc"
        result = SimpleNamespace(
            status=500,
            headers={"X-Request-ID": "request"},
            body={"code": "INTERNAL_SERVER_ERROR"},
            trace_id=trace_id,
        )
        diagnostic = ("OperationalError", "P603_REVISION_INSERT", trace_id)
        with (
            patch.object(
                module,
                "tooling_request",
                return_value=result,
            ) as request,
            patch.object(
                module.predecessor,
                "_sanitized_server_diagnostic",
                return_value=diagnostic,
            ) as read_diagnostic,
            self.assertRaisesRegex(
                RuntimeError,
                (
                    "HTTP 500 with problem code INTERNAL_SERVER_ERROR "
                    r"\[diagnostic_code=P603_REVISION_INSERT; "
                    r"exception_type=OperationalError; trace_id=" + trace_id + r"\]"
                ),
            ),
        ):
            module.command(
                object(),
                "http://127.0.0.1:8003",
                "csrf",
                "/api/npi/v1/projects/project/tooling/master/revisions",
                {},
                "revision-one",
            )
        self.assertTrue(request.call_args.kwargs["tooling_revision_create_diagnostic"])
        read_diagnostic.assert_called_once_with(
            trace_id,
            module._REVISION_CREATE_DIAGNOSTIC_CODES,
        )

    def test_applicability_selection_uses_nested_part_revision_projection(self) -> None:
        revision_id = "10000000-0000-4000-8000-000000000001"
        selected = self.module.exact_applicability(
            [
                {
                    "globalId": "20000000-0000-4000-8000-000000000002",
                    "part": {"globalId": revision_id},
                },
                {
                    "globalId": "30000000-0000-4000-8000-000000000003",
                    "part": {
                        "globalId": "40000000-0000-4000-8000-000000000004"
                    },
                },
            ],
            revision_id,
        )
        self.assertEqual(
            selected["globalId"],
            "20000000-0000-4000-8000-000000000002",
        )

    def test_shell_orchestrates_independent_fail_closed_switch_and_cleanup(self) -> None:
        required = (
            "tooling_revision_route_switch_state",
            "npi_p6_03_routes_disabled",
            "set_tooling_revision_route_switch true true",
            "set_tooling_revision_route_switch false false",
            "run_tooling_revision_runtime_verifier fresh",
            "run_tooling_revision_route_probe disabled",
            "run_tooling_revision_route_probe recovered",
            "run_tooling_revision_runtime_verifier replay-only",
            "restore_tooling_revision_route_switch",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_runtime_verifier fresh"),
            self.shell.index("run_tooling_revision_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_revision_route_probe disabled"),
            self.shell.index("run_tooling_revision_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_tooling_revision_route_probe recovered"),
            self.shell.index("run_tooling_revision_runtime_verifier replay-only"),
        )

    def test_manual_controlled_workflow_records_exact_cumulative_scope(self) -> None:
        self.assertIn(
            "name: P5 controlled document, EBOM, publish, and print runtime and P6 Tooling through immutable revisions",
            self.workflow,
        )
        self.assertIn("Verify cumulative P5 and P6-03 controlled runtime", self.workflow)
        self.assertIn("scope=p5-01-through-p6-03", self.workflow)
        self.assertIn("bash scripts/verify-frappe-runtime.sh --tooling-only", self.workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)


if __name__ == "__main__":
    unittest.main()
