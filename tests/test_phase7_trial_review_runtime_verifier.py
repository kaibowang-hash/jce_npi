from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_trial_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved = {
        name: sys.modules.pop(name, None)
        for name in ("verify_document_runtime", "verify_trial_review_runtime_contract")
    }
    spec = importlib.util.spec_from_file_location(
        "verify_trial_review_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Trial review runtime verifier cannot be imported")
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


class Phase7TrialReviewRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_review_runtime_uses_disposable_guarded_policy_fixture(self) -> None:
        for marker in (
            "ensure_trial_review_policy",
            "historical_trial_round_context",
            '"NPI Trial Conclusion Policy Version"',
            '"NPI Trial Round Comparison Snapshot"',
            '"NPI Trial Review Reference Revision"',
            '"NPI Trial Conclusion Revision"',
            "trial_command_write",
            '"npi_project_work_command_write"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        self.assertNotIn("ignore_" + "permissions=True", self.source)
        self.assertNotIn("core." + "whjichen.cn", self.source)

    def test_review_runtime_proves_exact_policy_comparison_and_history(self) -> None:
        review_source = inspect.getsource(self.module.run_review_fresh)
        for marker in (
            'kind="internal_sample_review"',
            'kind="controlled_quality_report"',
            'validate_problem(blocked, 422, "VALIDATION_FAILED")',
            'validate_problem(stale_reference, 409, "TRIAL_REVIEW_CONFLICT")',
            '"submitted", "approved", "reopened", "submitted", "rejected"',
            '"proposal_only"',
            '"P7-04 same-process conclusion replay changed sealed response truth"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, review_source + self.source)

    def test_review_runtime_proves_idor_replay_rollback_and_no_external_effect(self) -> None:
        for marker in (
            '"TRIAL_REVIEW_UNAVAILABLE"',
            '"TRIAL_REVIEW_ROUTES_DISABLED"',
            '"P7-04 policy blocker did not fail closed with rollback"',
            '"P7-04 cross-process review replay changed sealed truth or cardinality"',
            '"P7-04 controlled Trial review created ERP integration traffic"',
            '"customerSignature": "unavailable"',
            '"gate": "unavailable"',
            '"npiReadiness": "unavailable"',
            '"toolingLifecycle": "unavailable"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_shell_controls_review_switch_recovery_redaction_and_cleanup(self) -> None:
        for marker in (
            "trial_review_route_switch_state",
            "npi_p7_04_routes_disabled",
            "set_trial_review_route_switch true true",
            "run_trial_route_probe review-disabled",
            "set_trial_review_route_switch false false",
            "run_trial_route_probe review-recovered",
            "restore_trial_review_route_switch",
            "Failed to restore the P7-04 route-disable switch to absent.",
            "P7-04 raw Trial review value leaked into the runtime log.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)

    def test_workflow_records_exact_p704_scope(self) -> None:
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        for marker in (
            "P7-04 Trial review",
            "scope=p5-01-through-p7-04",
            "predecessor_scope=p5-01-through-p7-03",
            "tests.test_phase7_trial_review_runtime_verifier",
            "bash scripts/verify-frappe-runtime.sh --trial-only",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.workflow if marker.startswith("tests.") else runtime_job)


if __name__ == "__main__":
    unittest.main()
