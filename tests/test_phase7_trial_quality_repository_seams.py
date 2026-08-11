from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUALITY_REPOSITORY = ROOT / "apps/npi_core/npi_core/trial/quality_repository.py"
TOOLING_REPOSITORY = ROOT / "apps/npi_core/npi_core/tooling/engineering_controls_repository.py"
BFF = ROOT / "apps/npi_core/npi_core/bff.py"
QUALITY_DIAGNOSTICS = ROOT / "apps/npi_core/npi_core/trial/quality_diagnostics.py"


class Phase7TrialQualityRepositorySeamTest(unittest.TestCase):
    def test_quality_commands_share_project_lock_receipt_audit_and_write_scope(self) -> None:
        source = QUALITY_REPOSITORY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn("self._locked_authorized_project(project_id)", source)
        self.assertIn("self._idempotency_replay", source)
        self.assertIn("with trial_command_write():", source)
        self.assertIn("self._insert_receipt", source)
        self.assertIn("self._append_audit", source)
        self.assertIn("self._seal_receipt", source)
        self.assertNotIn("frappe.db.commit", source)
        self.assertTrue(any(isinstance(node, ast.ClassDef) for node in ast.walk(tree)))

    def test_p6_append_fails_closed_after_any_trial_successor(self) -> None:
        source = TOOLING_REPOSITORY.read_text(encoding="utf-8")
        predecessor = source[source.index("    def _defect_predecessor(") :]
        predecessor = predecessor[: predecessor.index("    def _process_profile_predecessor(")]
        self.assertIn('"NPI Trial Defect Revision"', predecessor)
        self.assertIn("if trial_successors:", predecessor)
        self.assertIn("raise ToolingVersionConflict()", predecessor)

    def test_quality_switch_is_independent_and_defaults_closed(self) -> None:
        source = BFF.read_text(encoding="utf-8")
        start = source.index("def _p7_03_routes_disabled")
        boundary = source[start : source.index("\ndef _p5_01_routes_disabled", start)]
        self.assertIn('configuration.get("npi_p7_03_routes_disabled")', boundary)
        self.assertIn("return value is not False", boundary)
        for command in (
            "get_trial_quality_workspace",
            "create_trial_cavity_result",
            "revise_trial_cavity_result",
            "create_trial_defect",
            "revise_trial_defect",
            "verify_trial_defect",
        ):
            self.assertIn(command, boundary)
        self.assertNotIn("get_trial_round_execution", boundary)

    def test_repository_has_no_external_quality_or_gate_mutation(self) -> None:
        source = QUALITY_REPOSITORY.read_text(encoding="utf-8").casefold()
        for forbidden in (
            "requests.post",
            "outbox",
            '"doctype": "npi quality inspection"',
            '"doctype": "npi ncr"',
            "gate decision",
            "tooling lifecycle event",
        ):
            self.assertNotIn(forbidden, source)

    def test_verified_action_requires_latest_pass_for_exact_target_round(self) -> None:
        source = QUALITY_REPOSITORY.read_text(encoding="utf-8")
        start = source.index("    def _exact_actions(")
        boundary = source[start : source.index("    def _cavity_measurements(", start)]
        for condition in (
            "verification.defect_global_id != predecessor.defect_global_id",
            "verification.action_global_id != global_id",
            "verification.target_round_global_id != target.global_id",
            "verification.target_round_snapshot_hash != target.snapshot_hash",
            "verification.result is not TrialDefectVerificationResult.PASS",
            "not chain or chain[-1].global_id != verification.global_id",
        ):
            self.assertIn(condition, boundary)

    def test_unexpected_type_diagnostics_are_bounded_and_response_neutral(self) -> None:
        source = QUALITY_DIAGNOSTICS.read_text(encoding="utf-8")
        self.assertIn("except TypeError as error:", source)
        self.assertIn("exception_type=type(error).__name__", source)
        self.assertIn("trace_id=trace_id", source)
        self.assertIn("raise\n", source)
        for forbidden in (
            "str(error)",
            "repr(error)",
            "traceback",
            "request_data",
            "response_body",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
