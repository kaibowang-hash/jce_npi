from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "apps/npi_integration")]


class Phase8ToolAssetRuntimeVerifierTest(unittest.TestCase):
    def setUp(self):
        fake = sys.modules.setdefault("frappe", types.ModuleType("frappe"))
        fake.session = types.SimpleNamespace(user="worker@example.invalid")
        self.fixture = importlib.reload(importlib.import_module("npi_integration.tool_asset_request.runtime_fixture"))
        self.verifier = importlib.reload(importlib.import_module("verify_tool_asset_execution_runtime"))
        self.environment = {"NPI_TOOL_ASSET_RUNTIME_MARKER":"npi-one-tool-asset-disposable-v1", "NPI_TOOL_ASSET_REQUESTER_USER":"engineer@example.invalid", "NPI_TOOL_ASSET_WORKER_USER":"worker@example.invalid"}

    def test_disabled_by_default_installs_no_profile_or_adapter(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.fixture.resolve_profile("tenant-a", str(UUID(int=1))))
            self.assertIsNone(self.fixture.resolve_adapter_registry())

    def test_disposable_configuration_is_network_free_and_shell_governed(self):
        source = (ROOT / "apps/npi_integration/npi_integration/tool_asset_request/runtime_fixture.py").read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("httpx", source)
        shell = (ROOT / "scripts/verify-frappe-runtime.sh").read_text(encoding="utf-8")
        for marker in ("run_tool_asset_runtime_verifier disabled", "run_tool_asset_runtime_verifier fresh", "NPI_TOOL_ASSET_RUNTIME_MARKER=npi-one-tool-asset-disposable-v1", "verify_tool_asset_execution_runtime.py"):
            self.assertIn(marker, shell)

    def test_synthetic_adapter_preserves_operation_and_returns_no_formal_identity(self):
        from tests.test_phase8_tool_asset_adapters import command
        with patch.dict(os.environ, self.environment, clear=True):
            response = self.fixture.synthetic_adapter(command())
        self.assertIsNone(response.formal_asset_id)
        self.assertIsNone(response.target_version)

    def test_runtime_covers_default_off_create_worker_replay_and_zero_mapping(self):
        source = (ROOT / "scripts/verify_tool_asset_execution_runtime.py").read_text(encoding="utf-8")
        for marker in ("run_disabled_probe", "commandContexts", '"state") == "queued"', "exercise_worker", "terminalReplayNotClaimed", "mappingHeadCount", "fieldResultCount", "_assert_no_formal_target"):
            self.assertIn(marker, source)
        self.assertIn("stderr=subprocess.DEVNULL", source)
        self.assertIn("tempfile.TemporaryFile", source)
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("P5 controlled runtime through P8-05 Tool Asset command and Outbox worker", workflow)
        self.assertIn("printf 'scope=p5-01-through-p8-05\\n'", workflow)
        self.assertIn("printf 'predecessor_scope=p5-01-through-p8-04\\n'", workflow)
        self.assertIn("tests/e2e/p8-05-tool-asset-execution-live.spec.ts", workflow)
        self.assertIn(
            "frontend/tests/e2e/p8-05-tool-asset-execution-live.spec.ts-snapshots/p8-05-*-linux.png",
            workflow,
        )

    def test_disabled_probe_runs_after_retained_p6_export_fixture(self):
        shell = (ROOT / "scripts/verify-frappe-runtime.sh").read_text(encoding="utf-8")
        self.assertLess(
            shell.index("run_tooling_import_runtime_verifier replay-only"),
            shell.index("run_tool_asset_runtime_verifier disabled"),
        )
        self.assertLess(
            shell.index("run_tooling_export_runtime_verifier replay-only"),
            shell.index("run_tool_asset_runtime_verifier disabled"),
        )
        revision = (ROOT / "scripts/verify_tooling_revision_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("exact_retained_master", revision)
        self.assertIn("exact_retained_part", revision)
        self.assertIn("originatingProjectGlobalId", revision)
        retained_part_source = revision[
            revision.index("def exact_retained_part(") : revision.index("\ndef command(")
        ]
        self.assertNotIn("originatingProjectGlobalId", retained_part_source)
        project_context_source = revision[
            revision.index("def project_context(") : revision.index("\ndef dedicated_part_context(")
        ]
        self.assertLess(
            project_context_source.index("exact_retained_master("),
            project_context_source.index("exact_retained_part("),
        )
        self.assertIn(
            'workspace.body.get("applicability")',
            project_context_source,
        )

    def test_retained_context_explicitly_requires_available_erp_projection(self):
        retained = ({"projectId": str(UUID(int=1))}, object(), object(), object())
        with patch.object(
            self.verifier.tooling_runtime,
            "replay_context",
            return_value=retained,
        ) as replay:
            context, second = self.verifier._retained_context(
                object(),
                "http://127.0.0.1:8003",
            )
        self.assertIs(context, retained[0])
        self.assertIs(second, retained[2])
        self.assertEqual(
            replay.call_args.kwargs,
            {
                "expected_erp_projection_mode": (
                    self.verifier.tooling_runtime.ExpectedErpProjectionMode.AVAILABLE
                )
            },
        )

    def test_projection_mode_is_explicitly_forwarded_through_p6_chain(self):
        manufacturing = (
            ROOT / "scripts" / "verify_tooling_manufacturing_runtime.py"
        ).read_text(encoding="utf-8")
        engineering = (
            ROOT / "scripts" / "verify_tooling_engineering_controls_runtime.py"
        ).read_text(encoding="utf-8")
        acceptance = (
            ROOT / "scripts" / "verify_tooling_acceptance_runtime.py"
        ).read_text(encoding="utf-8")
        tool_asset = (
            ROOT / "scripts" / "verify_tool_asset_execution_runtime.py"
        ).read_text(encoding="utf-8")
        for source in (manufacturing, engineering, acceptance):
            with self.subTest(source=source[:40]):
                self.assertIn("ExpectedErpProjectionMode.UNAVAILABLE", source)
                self.assertIn(
                    "expected_erp_projection_mode=expected_erp_projection_mode",
                    source,
                )
        self.assertIn("ExpectedErpProjectionMode.AVAILABLE", tool_asset)
        self.assertEqual(
            sum(
                source.count("ExpectedErpProjectionMode.AVAILABLE")
                for source in (manufacturing, engineering, acceptance, tool_asset)
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
