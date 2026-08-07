from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_controlled_print_runtime.py"
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
            "verify_controlled_print_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_controlled_print_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Controlled-print runtime verifier cannot be imported")
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


class Phase5ControlledPrintRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_is_synthetic_and_has_no_production_adapter(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.SOURCE_KIND, "npi.synthetic_runtime_project")
        self.assertRegex(module.REGISTRY_ID, r"^[a-f0-9-]{36}$")
        self.assertRegex(module.MAPPING_ID, r"^[a-f0-9-]{36}$")
        self.assertEqual(UUID(module.REGISTRY_ID).version, 4)
        self.assertEqual(UUID(module.MAPPING_ID).version, 4)
        self.assertNotEqual(module.REGISTRY_ID, module.MAPPING_ID)
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertNotIn("core." + "whjichen.cn", self.source)
        for forbidden in ("ERPNext", "credential", "external QR", "source adapter URL"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_request_payload_is_exact_and_browser_cannot_select_output_truth(self) -> None:
        project_id = "10000000-0000-4000-8000-000000000001"
        payload = self.module.create_payload(project_id, 7)
        self.assertEqual(
            payload,
            {
                "sourceKind": "npi.synthetic_runtime_project",
                "sourceGlobalId": self.module.runtime_source_id(project_id),
                "sourceVersion": 7,
                "language": "en",
            },
        )
        self.assertEqual(UUID(str(payload["sourceGlobalId"])).version, 4)
        self.assertNotEqual(payload["sourceGlobalId"], project_id)
        serialized = str(payload).casefold()
        for forbidden in (
            "template",
            "printformat",
            "watermark",
            "fileurl",
            "signer",
            "copystate",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_http_failure_evidence_exposes_only_code_and_field_paths(self) -> None:
        result = SimpleNamespace(
            status=422,
            body={
                "code": "VALIDATION_FAILED",
                "errors": [
                    {"path": "requestId", "message": "private-message"},
                    {"path": "sourceGlobalId", "message": "private-message"},
                ],
            },
        )

        evidence = self.module.http_failure_evidence(result)

        self.assertEqual(
            evidence,
            "HTTP 422; code=VALIDATION_FAILED; paths=requestId,sourceGlobalId",
        )
        self.assertNotIn("private-message", evidence)

    def test_schema_and_fixture_surface_are_exactly_guarded(self) -> None:
        self.assertEqual(len(self.module.CONTROLLED_PRINT_DOCTYPES), 6)
        self.assertIn("_require_disposable_site()", self.source)
        self.assertIn(
            "controlled_print_registry_write",
            self.source,
        )
        self.assertIn("sourceMutated", self.source)
        self.assertIn("printFormatMutated", self.source)
        self.assertIn("crossProcessReplay", self.source)
        self.assertNotIn("ignore_mandatory", self.source)
        self.assertNotIn("ignore_validate", self.source)

    def test_shell_orders_runtime_after_predecessor_replay_and_restores_switch(self) -> None:
        self.assertLess(
            self.shell.index("run_document_runtime_verifier replay-only"),
            self.shell.index("run_controlled_print_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_controlled_print_runtime_verifier fresh"),
            self.shell.index("run_controlled_print_route_probe disabled"),
        )
        self.assertLess(
            self.shell.index("run_controlled_print_route_probe recovered"),
            self.shell.index("run_controlled_print_runtime_verifier replay-only"),
        )
        for fragment in (
            "npi_p5_06_routes_disabled",
            "controlled_print_route_disable_original_state",
            "restore_controlled_print_route_switch",
            "P5-06 route-disable switch to absent",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)

    def test_manual_lane_records_cumulative_p506_scope_without_secrets(self) -> None:
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        for fragment in (
            "P5 controlled document, EBOM, publish, and print runtime",
            "bash scripts/verify-frappe-runtime.sh --document-only",
            "scope=p5-01-through-p5-06",
            "runtime_marker=npi-one-local-runtime-disposable-v1",
            "docker compose down --volumes",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)


if __name__ == "__main__":
    unittest.main()
