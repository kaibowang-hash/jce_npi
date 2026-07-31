from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "implementation" / "AUTOPILOT_CONTROLLER.md"
QUALITY_GATE = ROOT / "implementation" / "QUALITY_GATE.md"
PHASE_ANCHOR = ROOT / "implementation" / "phase-5-requirement-anchor.md"


class AutopilotControllerTest(unittest.TestCase):
    def test_repair_budget_counts_only_uniquely_proven_product_roots(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")
        for required_guard in (
            "Repair-round accounting is product-root based:",
            "environment remediation",
            "do not consume a product-root",
            "`IN_PROGRESS_DIAGNOSTIC`",
            "evidence uniquely proves",
            "five complete product-root repair rounds",
        ):
            self.assertIn(required_guard, source)

    def test_diagnostic_progress_never_weakens_product_or_gate_truth(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")
        for required_guard in (
            "is never a Gate `PASS`",
            "Requirement, API, permission, Schema, ownership, lock, version, audit,",
            "idempotency, transaction-order and PASS-criterion changes",
            "cannot be relabelled as `PASS`",
        ):
            self.assertIn(required_guard, source)

        quality_gate = QUALITY_GATE.read_text(encoding="utf-8")
        self.assertIn(
            "Gate criteria cannot be weakened to fit implementation.",
            quality_gate,
        )

    def test_p5_01_requirement_path_and_non_scope_remain_frozen(self) -> None:
        anchor = PHASE_ANCHOR.read_text(encoding="utf-8")
        for requirement_id in (
            "FR-DS-001",
            "FR-DS-003",
            "FR-DS-004",
            "FR-DS-007",
            "FR-DS-008",
            "FR-DS-009",
            "FR-DS-014",
        ):
            self.assertIn(f"| {requirement_id} | P5-01 |", anchor)
        self.assertIn(
            "P5-01 does not review, approve, release, supersede, baseline, "
            "publish an EBOM,",
            anchor,
        )


if __name__ == "__main__":
    unittest.main()
