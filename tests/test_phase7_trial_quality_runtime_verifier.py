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
        for name in ("verify_document_runtime", "verify_trial_quality_runtime_contract")
    }
    spec = importlib.util.spec_from_file_location(
        "verify_trial_quality_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Trial quality runtime verifier cannot be imported")
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


class Phase7TrialQualityRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_quality_runtime_uses_exact_disposable_site_and_guarded_metadata(self) -> None:
        for marker in (
            'BENCH_PATH = ROOT / "tmp" / "frappe-bench"',
            "document_runtime._validated_runtime_site()",
            '"NPI Trial Cavity Result Revision"',
            '"NPI Trial Defect Revision"',
            '"NPI Trial Defect Verification Revision"',
            "ensure_trial_quality_verifier_member",
            '"npi_project_work_command_write"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        self.assertNotIn("ignore_" + "permissions=True", self.source)
        self.assertNotIn("core." + "whjichen.cn", self.source)

    def test_quality_runtime_proves_exact_lineage_and_independent_verification(self) -> None:
        for marker in (
            "run_target_execution_fresh",
            "run_quality_fresh",
            'display_label="T1"',
            'predecessor_kind="tooling_defect_revision"',
            'predecessor_kind="trial_defect_revision"',
            'state="ready_for_verification"',
            'result="fail"',
            'result="pass"',
            '("closed", "reopened")',
            '"P7-03 cross-Round defect observation drifted"',
            '"P7-03 close/reopen, verified action or Pareto truth drifted"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_round_cardinality_tracks_primary_then_target_creation(self) -> None:
        fresh_source = inspect.getsource(self.module.run_fresh)
        primary_projection = fresh_source.split("planned_round = command", 1)[1].split(
            "round_value = exact_single", 1
        )[0]
        self.assertIn("rounds=1", primary_projection)

        retained_source = inspect.getsource(self.module.retained_detail)
        self.assertIn("rounds=2", retained_source)

    def test_independent_verifier_uses_a_distinct_retained_fixture_user(self) -> None:
        self.assertTrue(self.module.VERIFIER_USER.endswith("@example.invalid"))
        self.assertNotIn(
            self.module.VERIFIER_USER,
            {self.module.ACTOR_USER, self.module.UNRELATED_USER},
        )
        quality_source = inspect.getsource(self.module.run_quality_fresh)
        self.assertLess(
            quality_source.index("create_internal_fixture_user"),
            quality_source.index('"ensure_trial_quality_verifier_member"'),
        )
        member_source = inspect.getsource(
            self.module.ensure_trial_quality_verifier_member
        )
        self.assertIn('"user_id": VERIFIER_USER', member_source)
        self.assertNotIn('"user_id": ACTOR_USER', member_source)

    def test_quality_runtime_is_fail_closed_and_has_no_external_authority(self) -> None:
        for marker in (
            'validate_problem(stale_result, 409, "TRIAL_QUALITY_CONFLICT")',
            'validate_problem(idempotency_conflict, 409, "TRIAL_IDEMPOTENCY_CONFLICT")',
            '"TRIAL_QUALITY_UNAVAILABLE"',
            '"TRIAL_QUALITY_ROUTES_DISABLED"',
            '"ncr": "unavailable"',
            '"qualityInspection": "unavailable"',
            '"gate": "unavailable"',
            '"toolingLifecycle": "unavailable"',
            '"P7-03 controlled Trial quality created ERP integration traffic"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_shell_controls_quality_switch_recovery_redaction_and_cleanup(self) -> None:
        for marker in (
            "trial_quality_route_switch_state",
            "npi_p7_03_routes_disabled",
            "set_trial_quality_route_switch true true",
            "run_trial_route_probe quality-disabled",
            "set_trial_quality_route_switch false false",
            "run_trial_route_probe quality-recovered",
            "restore_trial_quality_route_switch",
            "Failed to restore the P7-03 route-disable switch to absent.",
            "Controlled synthetic cavity width",
            "P7-03 raw Trial quality value leaked into the runtime log.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)

    def test_cross_process_replay_and_complete_scope_are_recorded(self) -> None:
        for marker in (
            "run_quality_replay",
            '"P7-03 cross-process command was not replayed: {key}"',
            '"P7-03 cross-process replay changed immutable cardinality or integration truth"',
            "P7-03 Trial quality",
            "scope=p5-01-through-p7-03",
            "predecessor_scope=p5-01-through-p7-02",
            "python -m unittest tests.test_phase7_trial_runtime_verifier tests.test_phase7_trial_quality_runtime_verifier -v",
            "bash scripts/verify-frappe-runtime.sh --trial-only",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source + self.workflow)


if __name__ == "__main__":
    unittest.main()
