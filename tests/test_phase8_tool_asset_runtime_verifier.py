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


if __name__ == "__main__":
    unittest.main()
