from __future__ import annotations

import ast
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_mbom_publish_runtime.py"
SHELL = ROOT / "scripts/verify-frappe-runtime.sh"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    name = "verify_mbom_publish_runtime_contract"
    saved = sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("MBOM runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": "0123456789abcdef0123456789abcdef"},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
        if saved is not None:
            sys.modules[name] = saved
    return module


class Phase8MbomPublishRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_verifier()
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_path_is_project_first_and_has_no_operation_selector(self):
        project = "00000000-0000-0000-0000-000000000001"
        request = "00000000-0000-0000-0000-000000000002"
        self.assertEqual(
            self.module.mbom_publish_path(project),
            f"/api/npi/v1/projects/{project}/mbom-publish-requests",
        )
        self.assertEqual(
            self.module.mbom_publish_path(project, request),
            f"/api/npi/v1/projects/{project}/mbom-publish-requests/{request}",
        )

    def test_profile_assertion_requires_exact_disposable_synthetic_shape(self):
        available = {
            "executionProfile": {
                "profileId": "mbom-synthetic-disposable-v1",
                "profileVersion": 1,
                "targetMode": "synthetic",
                "environmentCode": "disposable-test",
            },
            "permissions": {"canView": True, "canExecute": True},
        }
        self.module.assert_profile(available, available=True)
        self.module.assert_profile(
            {
                "executionProfile": None,
                "permissions": {"canView": True, "canExecute": False},
            },
            available=False,
        )
        with self.assertRaises(RuntimeError):
            self.module.assert_profile(
                {**available, "executionProfile": {**available["executionProfile"], "targetMode": "sandbox"}},
                available=True,
            )

    def test_no_formal_target_walker_fails_on_nested_id_or_version(self):
        self.module._assert_no_formal_target(
            {"nodes": [{"formalBomId": None, "targetVersion": None}]}
        )
        for value in (
            {"formalBomId": "BOM-1"},
            {"nodes": [{"targetVersion": "2"}]},
        ):
            with self.assertRaises(RuntimeError):
                self.module._assert_no_formal_target(value)

    def test_bench_child_hides_stderr_and_drops_password_environment(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_bench_fixture"
        )
        segment = ast.get_source_segment(self.source, function) or ""
        self.assertIn("stderr=subprocess.DEVNULL", segment)
        self.assertIn("tempfile.TemporaryFile", segment)
        for secret in (
            "NPI_RUNTIME_ADMINISTRATOR_PASSWORD",
            "NPI_RUNTIME_FIXTURE_PASSWORD",
            "NPI_ADMINISTRATOR_PASSWORD",
            "NPI_DATABASE_ROOT_PASSWORD",
        ):
            self.assertIn(secret, segment)

    def test_fixture_allowlist_has_only_input_capture_and_worker_exercise(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "run_local_bench_fixture"
        )
        literals = {
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertIn("capture_inputs", literals)
        self.assertIn("exercise_worker", literals)
        self.assertNotIn("retry", literals)
        self.assertNotIn("reconcile", literals)

    def test_worker_fixture_proves_terminal_replay_and_zero_mapping_head(self):
        function = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "exercise_worker"
        )
        segment = ast.get_source_segment(self.source, function) or ""
        self.assertEqual(segment.count("process_outbox_message(outbox_id)"), 2)
        self.assertIn('"NPI MBOM Mapping Head"', segment)
        self.assertIn('"not_claimed"', segment)
        self.assertIn('"synthetic_verified"', segment)

    def test_verifier_has_no_target_network_or_production_identity(self):
        for forbidden in (
            "erpnext.sandbox",
            "erpnext.production",
            "requests.",
            "httpx.",
            "formal_bom_id =",
            "submit_bom",
        ):
            self.assertNotIn(forbidden, self.source.casefold())

    def test_shell_runs_disabled_then_exact_marker_fresh_and_cleans_environment(self):
        shell = SHELL.read_text(encoding="utf-8")
        for marker in (
            "run_mbom_publish_runtime_verifier disabled",
            "run_mbom_publish_runtime_verifier fresh",
            "NPI_P8_04_RUNTIME_MARKER=npi-one-mbom-publish-disposable-v1",
            "clear_mbom_publish_runtime_environment",
            "mbom_publish_runtime_environment_active=true",
        ):
            self.assertIn(marker, shell)


if __name__ == "__main__":
    unittest.main()
