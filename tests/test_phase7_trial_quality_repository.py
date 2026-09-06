from __future__ import annotations

import sys
import types
import unittest
from datetime import UTC, date, datetime
from unittest.mock import patch
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


try:
    import frappe  # type: ignore
except ImportError:
    frappe = types.ModuleType("frappe")
    frappe._ = lambda source: source
    frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
    sys.modules["frappe"] = frappe

from npi_core.trial.execution_domain import (  # noqa: E402
    TrialLockedReference,
    TrialLockedReferenceKind,
)
from npi_core.trial.quality_domain import (  # noqa: E402
    TrialDefectPredecessorKind,
    TrialDefectRevision,
    TrialQualityConflict,
)
from npi_core.trial.quality_repository import FrappeTrialQualityRepository  # noqa: E402
from npi_core.trial.quality_validation import (  # noqa: E402
    create_defect_values,
    verification_values,
)


PROJECT_ID = UUID("2e96f421-5872-4c96-a0dd-718d5c970a21")
DEFECT_ID = UUID("427230fd-fc1f-4738-ac31-3fd098d91561")
REVISION_ID = UUID("29e933a3-3954-4a96-9400-2be1987ae370")
HASH = "a" * 64


class Phase7TrialQualityRepositoryTest(unittest.TestCase):
    def test_locked_context_requires_one_exact_cavity(self) -> None:
        references = tuple(
            TrialLockedReference(
                global_id=UUID(int=index + 1),
                kind=kind,
                optimistic_version=1,
                snapshot_hash=HASH,
            )
            for index, kind in enumerate(
                (
                    TrialLockedReferenceKind.TOOLING_REVISION,
                    TrialLockedReferenceKind.TOOLING_SET,
                    TrialLockedReferenceKind.CAVITY,
                )
            )
        )
        lock = types.SimpleNamespace(references=references)
        revision, tooling_set = FrappeTrialQualityRepository._locked_tooling_context(
            lock,
            references[-1].global_id,
        )
        self.assertEqual(revision.kind, TrialLockedReferenceKind.TOOLING_REVISION)
        self.assertEqual(tooling_set.kind, TrialLockedReferenceKind.TOOLING_SET)
        with self.assertRaises(Exception) as captured:
            FrappeTrialQualityRepository._locked_tooling_context(lock, UUID(int=99))
        self.assertEqual(
            getattr(captured.exception, "code", None),
            "TRIAL_QUALITY_REFERENCE_UNAVAILABLE",
        )

    def test_cross_store_tip_prefers_trial_and_requires_exact_kind_hash_version(self) -> None:
        p6 = types.SimpleNamespace(
            global_id=UUID(int=10),
            defect_global_id=DEFECT_ID,
            defect_version=2,
            snapshot_hash="b" * 64,
        )
        p7 = object.__new__(TrialDefectRevision)
        object.__setattr__(p7, "global_id", UUID(int=11))
        object.__setattr__(p7, "defect_global_id", DEFECT_ID)
        object.__setattr__(p7, "defect_version", 3)
        object.__setattr__(p7, "snapshot_hash", "c" * 64)
        harness = types.SimpleNamespace(
            _tooling_defect_chain=lambda *_args, **_kwargs: (p6,),
            _trial_defect_chain=lambda *_args, **_kwargs: (p7,),
        )
        expected = {
            "kind": TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION,
            "global_id": p7.global_id,
            "snapshot_hash": p7.snapshot_hash,
            "defect_version": p7.defect_version,
        }
        stable, current = FrappeTrialQualityRepository._exact_defect_tip(
            harness,
            types.SimpleNamespace(),
            UUID(int=20),
            DEFECT_ID,
            expected,
        )
        self.assertEqual(stable, DEFECT_ID)
        self.assertIs(current, p7)
        with self.assertRaises(TrialQualityConflict):
            FrappeTrialQualityRepository._exact_defect_tip(
                harness,
                types.SimpleNamespace(),
                UUID(int=20),
                DEFECT_ID,
                expected | {"kind": TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION},
            )

    def test_pareto_counts_only_latest_same_round_cavity_observation(self) -> None:
        round_id = UUID(int=30)
        cavity_id = UUID(int=31)
        older = types.SimpleNamespace(
            defect_global_id=DEFECT_ID,
            trial_round_global_id=round_id,
            cavity_global_id=cavity_id,
            defect_version=1,
            category_key="flash",
            severity=types.SimpleNamespace(value="high"),
            occurrence_count=1,
        )
        current = types.SimpleNamespace(
            **{
                **older.__dict__,
                "defect_version": 2,
                "occurrence_count": 3,
            }
        )
        rows = FrappeTrialQualityRepository._pareto((older, current))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["count"], 3)

    def test_exact_member_normalizes_frappe_datetime_date_without_type_error(self) -> None:
        member = types.SimpleNamespace(
            global_id=UUID(int=32),
            tenant_id="tenant-a",
            project_global_id=PROJECT_ID,
            optimistic_version=1,
            effective_from=datetime(2026, 8, 10, tzinfo=UTC),
            effective_to=None,
            user_id="responsible@example.invalid",
        )
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="tenant-a",
        )
        supplied = {"global_id": member.global_id, "optimistic_version": 1}
        with patch(
            "npi_core.trial.quality_repository._optional_doc",
            return_value=member,
        ):
            exact = FrappeTrialQualityRepository._exact_member(
                types.SimpleNamespace(),
                project,
                supplied,
            )
        self.assertEqual(exact.global_id, member.global_id)
        self.assertEqual(exact.user_id, member.user_id)
        self.assertEqual(member.effective_from.date(), date(2026, 8, 10))

    def test_create_defect_requires_complete_new_or_p6_predecessor_shape(self) -> None:
        base = {
            "expectedRoundOptimisticVersion": 3,
            "expectedRoundSnapshotHash": HASH,
            "expectedInputLockRevisionGlobalId": str(REVISION_ID),
            "expectedInputLockRevisionSnapshotHash": HASH,
            "defectGlobalId": None,
            "expectedPredecessorKind": None,
            "expectedPredecessorGlobalId": None,
            "expectedPredecessorSnapshotHash": None,
            "expectedDefectVersion": None,
            "sampleBatchRevisionGlobalId": None,
            "expectedSampleBatchRevisionSnapshotHash": None,
            "cavityGlobalId": str(UUID(int=40)),
            "businessCode": "D-1",
            "title": "Flash",
            "description": "Flash at the exact cavity.",
            "categoryKey": "flash",
            "location": "parting-line",
            "severity": "high",
            "blocking": False,
            "state": "open",
            "rootCauseState": "pending",
            "rootCause": None,
            "responsibleMember": None,
            "occurrenceCount": 1,
            "actions": [],
            "evidence": [{"globalId": str(UUID(int=41)), "snapshotHash": HASH}],
            "reason": "Record the first exact observation.",
        }
        prepared = create_defect_values(base)
        self.assertIsNone(prepared["defect_id"])
        self.assertIsNone(prepared["predecessor"])
        with self.assertRaises(Exception) as captured:
            create_defect_values(base | {"defectGlobalId": str(DEFECT_ID)})
        self.assertEqual(getattr(captured.exception, "code", None), "VALIDATION_FAILED")

    def test_verification_predecessor_pair_is_all_or_nothing(self) -> None:
        values = {
            "expectedDefectRevisionGlobalId": str(REVISION_ID),
            "expectedDefectRevisionSnapshotHash": HASH,
            "actionGlobalId": str(UUID(int=50)),
            "verificationGlobalId": str(UUID(int=51)),
            "expectedAttemptSequence": None,
            "targetRoundGlobalId": str(UUID(int=52)),
            "expectedTargetRoundOptimisticVersion": 4,
            "expectedTargetRoundSnapshotHash": HASH,
            "cavityResultRevisionGlobalId": str(UUID(int=53)),
            "expectedCavityResultRevisionSnapshotHash": HASH,
            "verifierMember": {"globalId": str(UUID(int=54)), "optimisticVersion": 2},
            "result": "pass",
            "finding": "Independent verification passed.",
            "observedAt": "2026-08-11T08:00:00Z",
            "evidence": [{"globalId": str(UUID(int=55)), "snapshotHash": HASH}],
        }
        with self.assertRaises(Exception) as captured:
            verification_values(values)
        self.assertEqual(getattr(captured.exception, "code", None), "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
