from __future__ import annotations

import importlib
import sys
import types
import unittest
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


PROJECT = "2e96f421-5872-4c96-a0dd-718d5c970a21"
ROUND = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
ROUND_2 = "9ef990dc-d4e2-4325-8093-54dcd3dd6168"
REVISION = "29e933a3-3954-4a96-9400-2be1987ae370"
REVISION_2 = "39e933a3-3954-4a96-9400-2be1987ae370"
STABLE = "49e933a3-3954-4a96-9400-2be1987ae370"
MASTER = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
SHA = "a" * 64


class Phase7TrialReviewValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.saved_frappe = sys.modules.get("frappe")
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        sys.modules["frappe"] = frappe
        cls.validation = importlib.import_module("npi_core.trial.review_validation")
        cls.repository = importlib.import_module("npi_core.trial.review_repository")
        cls.review_domain = importlib.import_module("npi_core.trial.review_domain")
        cls.execution_domain = importlib.import_module("npi_core.trial.execution_domain")
        cls.errors = importlib.import_module("npi_core.foundation.errors")

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("npi_core.trial.review_validation", None)
        sys.modules.pop("npi_core.trial.review_repository", None)
        if cls.saved_frappe is None:
            sys.modules.pop("frappe", None)
        else:
            sys.modules["frappe"] = cls.saved_frappe

    def policy(self) -> dict[str, object]:
        return {
            "policyRevisionGlobalId": REVISION,
            "expectedPolicyRevisionSnapshotHash": SHA,
            "expectedRoundOptimisticVersion": 3,
            "expectedRoundSnapshotHash": SHA,
        }

    def test_policy_context_rejects_noncanonical_hash_and_boolean_version(self) -> None:
        values = self.policy()
        values["expectedPolicyRevisionSnapshotHash"] = "A" * 64
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.policy_context_values(values)
        values = self.policy()
        values["expectedRoundOptimisticVersion"] = True
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.policy_context_values(values)

    def test_comparison_requires_unique_closed_exact_rounds(self) -> None:
        values = self.policy() | {
            "rounds": [
                {
                    "trialRoundGlobalId": ROUND,
                    "expectedOptimisticVersion": 3,
                    "expectedSnapshotHash": SHA,
                },
                {
                    "trialRoundGlobalId": ROUND_2,
                    "expectedOptimisticVersion": 4,
                    "expectedSnapshotHash": SHA,
                },
            ],
            "reason": "Compare exact retained Round sources.",
        }
        result = self.validation.comparison_values(values)
        self.assertEqual([item["global_id"] for item in result["rounds"]], [UUID(ROUND), UUID(ROUND_2)])
        values["rounds"][1]["trialRoundGlobalId"] = ROUND
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.comparison_values(values)
        values["rounds"][1]["unexpected"] = "drift"
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.comparison_values(values)

    def test_reference_predecessor_is_all_or_none_and_dates_are_ordered(self) -> None:
        values = self.policy() | {
            "referenceGlobalId": None,
            "expectedReferenceRevisionGlobalId": None,
            "expectedReferenceRevisionSnapshotHash": None,
            "expectedReferenceVersion": None,
            "comparisonSnapshotGlobalId": REVISION,
            "expectedComparisonSnapshotHash": SHA,
            "referenceKind": "controlled_quality_report",
            "partRevisionGlobalId": REVISION,
            "expectedPartRevisionSnapshotHash": SHA,
            "toolingMasterGlobalId": MASTER,
            "toolingRevisionGlobalId": REVISION,
            "expectedToolingRevisionSnapshotHash": SHA,
            "toolingSetGlobalId": REVISION,
            "expectedToolingSetSnapshotHash": SHA,
            "fileRevisionGlobalId": REVISION,
            "expectedFileRevisionSnapshotHash": SHA,
            "effectiveFrom": "2026-08-01",
            "effectiveTo": "2026-08-31",
            "reason": "Bind an exact controlled review input.",
        }
        result = self.validation.reference_values(values)
        self.assertIsNone(result["reference_predecessor"])
        values["referenceGlobalId"] = STABLE
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.reference_values(values)
        values["referenceGlobalId"] = None
        values["effectiveTo"] = "2026-07-31"
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.reference_values(values)

    def test_conclusion_requires_unique_exact_references_and_supported_decision(self) -> None:
        values = self.policy() | {
            "conclusionGlobalId": None,
            "expectedConclusionRevisionGlobalId": None,
            "expectedConclusionRevisionSnapshotHash": None,
            "expectedConclusionVersion": None,
            "comparisonSnapshotGlobalId": REVISION,
            "expectedComparisonSnapshotHash": SHA,
            "reviewReferences": [
                {"globalId": REVISION, "snapshotHash": SHA},
                {"globalId": REVISION_2, "snapshotHash": SHA},
            ],
            "conclusionCode": "conditional_pass",
            "proposedNextWork": ["Verify the retained corrective action."],
            "proposedGateEffect": "Proposal only; no Gate transition.",
            "proposedNpiEffect": "Proposal only; no NPI readiness mutation.",
            "reason": "Submit exact review sources.",
        }
        result = self.validation.conclusion_values(values)
        self.assertEqual(result["conclusion_code"].value, "conditional_pass")
        values["reviewReferences"][1]["globalId"] = REVISION
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.conclusion_values(values)

        decision = self.policy() | {
            "expectedConclusionRevisionGlobalId": REVISION,
            "expectedConclusionRevisionSnapshotHash": SHA,
            "expectedConclusionVersion": 1,
            "decision": "reopened",
            "reason": "Do not accept an implicit reopen as a decision.",
        }
        with self.assertRaises(self.errors.RequestValidationFailed):
            self.validation.decision_values(decision)

    def test_missing_governed_metrics_remain_unavailable_and_never_become_zero(self) -> None:
        sources = (
            types.SimpleNamespace(trial_round_global_id=UUID(ROUND)),
            types.SimpleNamespace(trial_round_global_id=UUID(ROUND_2)),
        )
        contexts = (
            {"input_lock": None, "actual": None, "cavities": ()},
            {"input_lock": None, "actual": None, "cavities": ()},
        )
        repository = object.__new__(self.repository.FrappeTrialReviewRepository)
        rows = repository._metric_rows(sources, contexts)
        self.assertEqual(
            {row.metric_kind.value for row in rows},
            {"parameter", "dimension", "cycle_time", "yield"},
        )
        self.assertTrue(
            all(
                cell.state.value == "unavailable"
                and cell.value is None
                and cell.source_revision is None
                for row in rows
                for cell in row.cells
            )
        )

    def test_explicit_not_measured_parameter_retains_exact_actual_source(self) -> None:
        actual_id = UUID(REVISION)
        source = types.SimpleNamespace(trial_round_global_id=UUID(ROUND))
        context = {
            "actual": types.SimpleNamespace(global_id=actual_id, snapshot_hash=SHA)
        }
        definition = types.SimpleNamespace(
            unit="degC",
            lower_limit="200",
            upper_limit="240",
        )
        observation = types.SimpleNamespace(
            state=self.execution_domain.TrialMeasurementState.NOT_MEASURED
        )
        cell = self.repository.FrappeTrialReviewRepository._parameter_cell(
            source,
            context,
            definition,
            observation,
        )
        self.assertEqual(cell.state.value, "not_measured")
        self.assertIsNone(cell.value)
        self.assertEqual(cell.source_revision.global_id, actual_id)
        self.assertEqual(cell.source_revision.snapshot_hash, SHA)


if __name__ == "__main__":
    unittest.main()
