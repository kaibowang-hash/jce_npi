from __future__ import annotations

import json
import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from tests.test_phase7_released_trial_summary_domain import (
    PROJECT,
    ROUND,
    summary,
)


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_SOURCE = (
    ROOT / "apps/npi_core/npi_core/trial/released_summary_repository.py"
).read_text(encoding="utf-8")


class Phase7ReleasedTrialSummaryRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.saved_frappe = sys.modules.get("frappe")
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        sys.modules["frappe"] = frappe
        cls.repository = importlib.import_module(
            "npi_core.trial.released_summary_repository"
        )
        cls.validation = importlib.import_module(
            "npi_core.trial.released_summary_validation"
        )
        cls.errors = importlib.import_module("npi_core.foundation.errors")
        cls.domain = importlib.import_module(
            "npi_core.trial.released_summary_domain"
        )
        cls.Repository = cls.repository.FrappeReleasedTrialSummaryRepository

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("npi_core.trial.released_summary_repository", None)
        sys.modules.pop("npi_core.trial.released_summary_validation", None)
        if cls.saved_frappe is None:
            sys.modules.pop("frappe", None)
        else:
            sys.modules["frappe"] = cls.saved_frappe

    def test_closed_command_validation_accepts_only_canonical_exact_truth(self) -> None:
        value = {
            "expectedRoundOptimisticVersion": 7,
            "expectedRoundSnapshotHash": "2" * 64,
            "conclusionRevisionGlobalId": "00000000-0000-0000-0000-000000000016",
            "expectedConclusionVersion": 4,
            "expectedConclusionSnapshotHash": "f" * 64,
            "reason": "Retain the exact decided conclusion.",
        }
        parsed = self.validation.retain_released_summary_values(value)
        self.assertEqual(parsed["expected_round_optimistic_version"], 7)
        self.assertIsInstance(parsed["conclusion_revision_id"], UUID)
        revise = self.validation.revise_released_summary_values(
            value
            | {
                "predecessorRevisionGlobalId": "00000000-0000-0000-0000-000000000020",
                "expectedPredecessorVersion": 1,
                "expectedPredecessorSnapshotHash": "a" * 64,
            }
        )
        self.assertEqual(revise["expected_predecessor_version"], 1)
        for field, invalid in (
            ("expectedRoundOptimisticVersion", True),
            ("expectedConclusionSnapshotHash", "F" * 64),
            ("reason", " padded "),
        ):
            with self.subTest(field=field), self.assertRaises(
                self.errors.RequestValidationFailed
            ):
                self.validation.retain_released_summary_values(value | {field: invalid})

    def test_summary_insert_serializes_complete_replayable_snapshot(self) -> None:
        value = summary()
        captured: dict[str, object] = {}

        def get_doc(document):
            captured.update(document)
            return SimpleNamespace(insert=lambda: None)

        with patch.object(self.repository.frappe, "get_doc", get_doc, create=True):
            self.Repository._insert_summary(value)

        persisted = json.loads(str(captured["summary_snapshot"]))
        self.assertEqual(persisted["snapshotHash"], value.snapshot_hash)
        self.assertEqual(
            json.loads(str(captured["presentation_projection"])),
            value.snapshot_payload()["presentationProjection"],
        )
        self.assertEqual(captured["snapshot_hash"], value.snapshot_hash)
        self.assertEqual(captured["summary_version"], 1)

    def test_exact_graph_enumerates_tooling_trial_actions_and_verification(self) -> None:
        repository = object.__new__(self.Repository)

        def exact(value: int, marker: str) -> SimpleNamespace:
            return SimpleNamespace(global_id=UUID(int=value), snapshot_hash=marker * 64)

        plan = SimpleNamespace(**vars(exact(101, "1")), plan_version=3)
        input_lock = SimpleNamespace(**vars(exact(102, "3")), lock_version=2)
        actual = SimpleNamespace(
            **vars(exact(103, "4")),
            actual_version=5,
            parameters=(
                SimpleNamespace(
                    definition_key="injection_pressure",
                    state=SimpleNamespace(value="measured"),
                    value="82",
                    unit="MPa",
                ),
            ),
        )
        sample = SimpleNamespace(
            **vars(exact(104, "5")),
            sample_batch_global_id=UUID(int=204),
            sample_version=2,
            quantity=20,
            unit="pcs",
        )
        cavity = SimpleNamespace(
            **vars(exact(105, "6")),
            cavity_global_id=UUID(int=205),
            result_version=3,
            measurements=(
                SimpleNamespace(
                    characteristic_key="critical_length",
                    state=SimpleNamespace(value="measured"),
                    value="10.05",
                    unit="mm",
                ),
            ),
        )
        tooling_action = SimpleNamespace(
            global_id=UUID(int=301),
            action_type=SimpleNamespace(value="corrective"),
            state=SimpleNamespace(value="completed"),
            detail="Correct the exact Tooling condition.",
        )
        tooling_defect = SimpleNamespace(
            **vars(exact(106, "7")),
            tooling_master_global_id=UUID(int=206),
            defect_global_id=UUID(int=306),
            defect_version=1,
            state=SimpleNamespace(value="open"),
            business_code="TDEF-001",
            actions=(tooling_action,),
        )
        verification_ref = exact(108, "8")
        trial_action = SimpleNamespace(
            global_id=UUID(int=302),
            action_type=SimpleNamespace(value="corrective"),
            state=SimpleNamespace(value="verified"),
            detail="Verify the exact Trial correction.",
            verification_revision_global_id=verification_ref.global_id,
            verification_revision_snapshot_hash=verification_ref.snapshot_hash,
        )
        trial_defect = SimpleNamespace(
            **vars(exact(107, "a")),
            defect_global_id=UUID(int=307),
            defect_version=4,
            state=SimpleNamespace(value="closed"),
            business_code="DEF-001",
            actions=(trial_action,),
        )
        verification = SimpleNamespace(
            **vars(verification_ref),
            verification_global_id=UUID(int=308),
            attempt_sequence=1,
            defect_revision_global_id=trial_defect.global_id,
            result=SimpleNamespace(value="pass"),
        )
        reference = SimpleNamespace(
            **vars(exact(109, "b")),
            reference_global_id=UUID(int=309),
            reference_version=2,
            reference_kind=SimpleNamespace(value="controlled_quality_report"),
        )
        conclusion = SimpleNamespace(
            **vars(exact(110, "f")),
            conclusion_version=4,
            state=self.repository.TrialConclusionRevisionState.APPROVED,
            conclusion_code=SimpleNamespace(value="pass"),
            review_references=(exact(109, "b"),),
            comparison_snapshot=exact(111, "9"),
            blockers=(),
        )
        target = SimpleNamespace(
            trial_round_global_id=ROUND,
            trial_round_optimistic_version=5,
            trial_round_snapshot_hash="1" * 64,
            trial_plan_revision=exact(101, "1"),
            input_lock_revision=exact(102, "3"),
            actual_revision=exact(103, "4"),
            sample_revisions=(exact(104, "5"),),
            cavity_results=(SimpleNamespace(revision=exact(105, "6")),),
            defect_tips=(
                SimpleNamespace(
                    source_kind=self.repository.TrialDefectSourceKind.TOOLING,
                    revision=exact(106, "7"),
                ),
                SimpleNamespace(
                    source_kind=self.repository.TrialDefectSourceKind.TRIAL,
                    revision=exact(107, "a"),
                ),
            ),
        )
        comparison = SimpleNamespace(
            **vars(exact(111, "9")),
            sources=(SimpleNamespace(trial_round_global_id=UUID(int=999)), target),
            input_rows=(
                SimpleNamespace(
                    semantic_key="material.grade",
                    change_state=SimpleNamespace(value="changed"),
                    cells=(
                        SimpleNamespace(),
                        SimpleNamespace(
                            canonical_value="ABS-B",
                            source_revision=exact(102, "3"),
                        ),
                    ),
                ),
            ),
            metric_rows=(
                SimpleNamespace(
                    metric_kind=SimpleNamespace(value="parameter"),
                    metric_key="injection_pressure",
                    cavity_global_id=None,
                    cells=(
                        SimpleNamespace(),
                        SimpleNamespace(
                            state=self.repository.TrialComparisonCellState.MEASURED,
                            value="82",
                            unit="MPa",
                            source_revision=exact(103, "4"),
                        ),
                    ),
                ),
            ),
        )
        project = SimpleNamespace(tenant_id="tenant-a", global_id=str(PROJECT))
        trial_round = SimpleNamespace(
            global_id=ROUND,
            optimistic_version=7,
            snapshot_hash="2" * 64,
            trial_plan_revision_global_id=plan.global_id,
            trial_plan_revision_snapshot_hash=plan.snapshot_hash,
            tooling_master_global_id=tooling_defect.tooling_master_global_id,
        )
        values = {
            "NPI Trial Plan Revision": plan,
            "NPI Trial Input Lock Revision": input_lock,
            "NPI Trial Actual Revision": actual,
            "NPI Trial Sample Batch Revision": sample,
            "NPI Trial Cavity Result Revision": cavity,
            "NPI Tooling Defect Revision": tooling_defect,
            "NPI Trial Defect Revision": trial_defect,
            "NPI Trial Defect Verification Revision": verification,
        }
        repository._exact_comparison = lambda *_args: comparison
        repository._exact_reference_revision = lambda *_args: reference
        repository._exact_value = lambda _project, _round, doctype, *_args, **_kwargs: (
            values[doctype]
        )

        graph = repository._exact_source_graph(project, trial_round, conclusion)

        self.assertEqual(
            [value.kind.value for value in graph.manifest],
            [
                "trial_plan_revision",
                "trial_round",
                "trial_input_lock_revision",
                "trial_actual_revision",
                "trial_sample_batch_revision",
                "trial_cavity_result_revision",
                "tooling_defect_revision",
                "trial_defect_revision",
                "trial_defect_verification_revision",
                "trial_round_comparison_snapshot",
                "trial_review_reference_revision",
                "trial_conclusion_revision",
            ],
        )
        defect_keys = {value["factKey"] for value in graph.facts["defects"]}
        self.assertIn("toolingDefect.00000000-0000-0000-0000-000000000132", defect_keys)
        self.assertIn("defect.00000000-0000-0000-0000-000000000133", defect_keys)
        self.assertIn(
            "defectVerification.00000000-0000-0000-0000-000000000134.1",
            defect_keys,
        )

    def test_current_decided_conclusion_rejects_reopened_or_stale_tip(self) -> None:
        repository = object.__new__(self.Repository)
        trial_round = SimpleNamespace(
            global_id=ROUND,
            optimistic_version=7,
            snapshot_hash="2" * 64,
        )
        approved = SimpleNamespace(
            global_id=UUID(int=401),
            conclusion_global_id=UUID(int=400),
            conclusion_version=4,
            snapshot_hash="f" * 64,
            state=self.repository.TrialConclusionRevisionState.APPROVED,
            trial_round_optimistic_version=7,
            trial_round_snapshot_hash="2" * 64,
        )
        repository._conclusion_history = lambda *_args: (approved,)
        self.assertIs(
            repository._exact_current_decided_conclusion(
                SimpleNamespace(),
                trial_round,
                approved.global_id,
                approved.conclusion_version,
                approved.snapshot_hash,
            ),
            approved,
        )
        reopened = SimpleNamespace(
            **(
                vars(approved)
                | {
                    "global_id": UUID(int=402),
                    "conclusion_version": 5,
                    "state": self.repository.TrialConclusionRevisionState.REOPENED,
                }
            )
        )
        repository._conclusion_history = lambda *_args: (approved, reopened)
        with self.assertRaises(self.domain.ReleasedTrialSummaryConflict):
            repository._exact_current_decided_conclusion(
                SimpleNamespace(),
                trial_round,
                reopened.global_id,
                reopened.conclusion_version,
                reopened.snapshot_hash,
            )

    def test_project_authorization_precedes_round_and_summary_resolution(self) -> None:
        repository = object.__new__(self.Repository)
        repository._summary_command_start = lambda *_args: (None, None, "")
        repository._locked_exact_round = lambda *_args: self.fail(
            "Round resolution must not run before Project authorization."
        )
        repository._summary_history = lambda *_args, **_kwargs: self.fail(
            "Summary resolution must not run before Project authorization."
        )
        common = {
            "idempotency_key_hash": "b" * 64,
            "expected_round_optimistic_version": 7,
            "expected_round_snapshot_hash": "2" * 64,
            "conclusion_revision_id": UUID(int=501),
            "expected_conclusion_version": 4,
            "expected_conclusion_snapshot_hash": "f" * 64,
            "reason": "Retain the exact authorized summary.",
        }
        self.assertIsNone(repository.retain_summary(PROJECT, ROUND, **common))
        self.assertIsNone(
            repository.revise_summary(
                PROJECT,
                ROUND,
                UUID(int=502),
                predecessor_revision_id=UUID(int=503),
                expected_predecessor_version=1,
                expected_predecessor_snapshot_hash="a" * 64,
                **common,
            )
        )

    def test_absent_summary_stream_is_unavailable_before_predecessor_conflict(self) -> None:
        repository = object.__new__(self.Repository)
        project = SimpleNamespace()
        trial_round = SimpleNamespace()
        predecessor = SimpleNamespace(
            summary_global_id=UUID(int=601),
            global_id=UUID(int=602),
            summary_version=2,
            snapshot_hash="a" * 64,
        )
        repository._summary_command_start = lambda *_args: (project, None, "b" * 64)
        repository._locked_exact_round = lambda *_args: (SimpleNamespace(), trial_round)
        repository._summary_history = lambda *_args, **_kwargs: (predecessor,)
        repository._exact_current_decided_conclusion = lambda *_args: self.fail(
            "Conclusion resolution must not disclose an absent summary stream."
        )

        with self.assertRaises(self.domain.ReleasedTrialSummaryUnavailable):
            repository.revise_summary(
                PROJECT,
                ROUND,
                UUID(int=603),
                idempotency_key_hash="c" * 64,
                expected_round_optimistic_version=7,
                expected_round_snapshot_hash="2" * 64,
                conclusion_revision_id=UUID(int=604),
                expected_conclusion_version=5,
                expected_conclusion_snapshot_hash="f" * 64,
                predecessor_revision_id=predecessor.global_id,
                expected_predecessor_version=predecessor.summary_version,
                expected_predecessor_snapshot_hash=predecessor.snapshot_hash,
                reason="Probe an absent summary stream without disclosing history.",
            )

    def test_actor_receipt_row_audit_workspace_and_seal_order_is_atomic(self) -> None:
        value = summary()
        repository = object.__new__(self.Repository)
        repository.request_id = str(value.request_id)
        calls: list[str] = []
        receipt = SimpleNamespace()
        project = SimpleNamespace(global_id=str(PROJECT), tenant_id="tenant-a")
        trial_round = SimpleNamespace(global_id=ROUND)

        @contextmanager
        def transaction():
            calls.append("transaction.enter")
            try:
                yield
            except Exception:
                calls.append("transaction.rollback")
                raise
            calls.append("transaction.commit")

        repository._insert_receipt = lambda *_args, **_kwargs: (
            calls.append("receipt") or receipt
        )
        repository._insert_summary = lambda _value: calls.append("summary")
        repository._append_audit = lambda **_kwargs: calls.append("audit")
        repository._summary_workspace_for = lambda *_args: (
            calls.append("workspace") or {"sealed": True}
        )
        repository._seal_receipt = lambda *_args, **_kwargs: calls.append("seal")
        with patch.object(self.repository, "trial_command_write", transaction):
            outcome = repository._persist_summary(
                project,
                trial_round,
                value,
                operation="released_trial_summary.retain",
                idempotency_key_hash="b" * 64,
                payload_hash="c" * 64,
                now=value.created_at,
            )

        self.assertEqual(
            calls,
            [
                "transaction.enter",
                "receipt",
                "summary",
                "audit",
                "workspace",
                "seal",
                "transaction.commit",
            ],
        )
        self.assertEqual(outcome.response, {"sealed": True})

        calls.clear()
        repository._insert_summary = lambda _value: (_ for _ in ()).throw(
            self.domain.ReleasedTrialSummaryConflict()
        )
        with patch.object(self.repository, "trial_command_write", transaction):
            with self.assertRaises(self.domain.ReleasedTrialSummaryConflict):
                repository._persist_summary(
                    project,
                    trial_round,
                    value,
                    operation="released_trial_summary.retain",
                    idempotency_key_hash="b" * 64,
                    payload_hash="c" * 64,
                    now=value.created_at,
                )
        self.assertEqual(
            calls,
            ["transaction.enter", "receipt", "transaction.rollback"],
        )

    def test_repository_has_project_round_stream_locks_and_no_external_mutation(self) -> None:
        for marker in (
            "self._authorized_project(project_id)",
            "self._locked_authorized_project(project_id)",
            "self._execution_round(project, round_id, for_update=True)",
            "lock_tip=True",
            "self._idempotency_replay(",
            "self._insert_receipt(",
            "self._append_audit(",
            "self._seal_receipt(",
            '"released_trial_summary.retain"',
            '"released_trial_summary.revise"',
        ):
            self.assertIn(marker, REPOSITORY_SOURCE)
        for forbidden in (
            "frappe.db.set_value",
            "frappe.db." + "sql",
            ".delete()",
            "enqueue(",
            "outbox",
            "erpnext",
            "gate_transition",
        ):
            self.assertNotIn(forbidden, REPOSITORY_SOURCE.casefold())


if __name__ == "__main__":
    unittest.main()
