from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import UTC, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.controlled_print.domain import MAX_SOURCE_SNAPSHOT_BYTES
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.trial.released_summary_domain import (
    ReleasedTrialSummaryRevision,
    ReleasedTrialSummarySourceKind,
    ReleasedTrialSummarySourceReference,
    build_released_trial_summary_projection,
    build_released_trial_summary_redaction_manifest,
    released_trial_summary_from_snapshot,
    validate_released_trial_summary_successor,
)
from npi_core.trial.review_domain import (
    TrialConclusionCode,
    TrialConclusionRevisionState,
)


def uid(value: int) -> UUID:
    return UUID(int=value)


NOW = datetime(2026, 8, 15, 8, 0, tzinfo=UTC)
PROJECT = uid(1)
PLAN = uid(2)
ROUND = uid(3)
SUMMARY = uid(4)


def source(
    kind: ReleasedTrialSummarySourceKind,
    value: int,
    version: int,
    marker: str,
) -> ReleasedTrialSummarySourceReference:
    return ReleasedTrialSummarySourceReference(kind, uid(value), version, marker * 64)


def manifest(
    *,
    conclusion_id: int = 16,
    conclusion_version: int = 4,
    conclusion_marker: str = "f",
) -> tuple[ReleasedTrialSummarySourceReference, ...]:
    return (
        source(ReleasedTrialSummarySourceKind.TRIAL_PLAN_REVISION, 5, 3, "1"),
        source(ReleasedTrialSummarySourceKind.TRIAL_ROUND, 3, 7, "2"),
        source(ReleasedTrialSummarySourceKind.TRIAL_INPUT_LOCK_REVISION, 6, 2, "3"),
        source(ReleasedTrialSummarySourceKind.TRIAL_ACTUAL_REVISION, 7, 5, "4"),
        source(ReleasedTrialSummarySourceKind.TRIAL_SAMPLE_BATCH_REVISION, 8, 2, "5"),
        source(ReleasedTrialSummarySourceKind.TRIAL_CAVITY_RESULT_REVISION, 9, 3, "6"),
        source(ReleasedTrialSummarySourceKind.TRIAL_DEFECT_REVISION, 10, 4, "7"),
        source(
            ReleasedTrialSummarySourceKind.TRIAL_DEFECT_VERIFICATION_REVISION,
            11,
            1,
            "8",
        ),
        source(
            ReleasedTrialSummarySourceKind.TRIAL_ROUND_COMPARISON_SNAPSHOT,
            12,
            1,
            "9",
        ),
        source(
            ReleasedTrialSummarySourceKind.TRIAL_REVIEW_REFERENCE_REVISION,
            13,
            2,
            "a",
        ),
        source(
            ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION,
            conclusion_id,
            conclusion_version,
            conclusion_marker,
        ),
    )


def fact(
    fact_key: str,
    value: object,
    source_reference: ReleasedTrialSummarySourceReference,
    *,
    value_state: str = "informational",
    unit: str | None = None,
) -> dict[str, object]:
    return {
        "factKey": fact_key,
        "valueState": value_state,
        "value": value,
        "unit": unit,
        "sourceReferences": [source_reference.snapshot_payload()],
    }


def facts(
    sources: tuple[ReleasedTrialSummarySourceReference, ...],
    note: str = "safe",
) -> dict[str, object]:
    return {
        "inputChanges": [fact("material.grade", note, sources[2])],
        "actualParameters": [
            fact("pressure", "82", sources[3], value_state="measured", unit="MPa")
        ],
        "samples": [fact("sample.batch", "S-01", sources[4])],
        "cavityResults": [fact("cavity.1", "measured", sources[5])],
        "defects": [fact("defect.flash", "closed", sources[6], value_state="closed")],
        "comparison": [fact("round.delta", "changed", sources[8])],
        "controlledReferences": [fact("quality.reference", "exact", sources[9])],
        "blockers": [],
    }


def projection(
    sources: tuple[ReleasedTrialSummarySourceReference, ...],
    *,
    state: TrialConclusionRevisionState = TrialConclusionRevisionState.APPROVED,
    note: str = "safe",
) -> dict[str, object]:
    return build_released_trial_summary_projection(
        project_global_id=PROJECT,
        trial_plan_global_id=PLAN,
        trial_round_global_id=ROUND,
        conclusion_revision=sources[-1],
        conclusion_state=state,
        conclusion_code=TrialConclusionCode.PASS,
        source_manifest=sources,
        facts=facts(sources, note),
    )


def summary(
    *,
    global_id: int = 20,
    summary_version: int = 1,
    predecessor: ReleasedTrialSummaryRevision | None = None,
    conclusion_id: int = 16,
    conclusion_version: int = 4,
    conclusion_marker: str = "f",
    state: TrialConclusionRevisionState = TrialConclusionRevisionState.APPROVED,
) -> ReleasedTrialSummaryRevision:
    sources = manifest(
        conclusion_id=conclusion_id,
        conclusion_version=conclusion_version,
        conclusion_marker=conclusion_marker,
    )
    return ReleasedTrialSummaryRevision(
        global_id=uid(global_id),
        summary_global_id=SUMMARY,
        tenant_id="tenant-a",
        project_global_id=PROJECT,
        trial_plan_global_id=PLAN,
        trial_round_global_id=ROUND,
        summary_version=summary_version,
        predecessor_global_id=predecessor.global_id if predecessor else None,
        predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
        trial_round_optimistic_version=7,
        trial_round_snapshot_hash="2" * 64,
        trial_plan_revision_global_id=uid(5),
        trial_plan_revision_snapshot_hash="1" * 64,
        conclusion_revision_global_id=uid(conclusion_id),
        conclusion_version=conclusion_version,
        conclusion_snapshot_hash=conclusion_marker * 64,
        conclusion_state=state,
        conclusion_code=TrialConclusionCode.PASS,
        source_manifest=sources,
        presentation_projection=projection(sources, state=state),
        redaction_manifest=build_released_trial_summary_redaction_manifest(),
        reason="Retain exact decided Trial truth.",
        created_by_user_id="system-manager@example.invalid",
        created_at=NOW,
        request_id=uid(30 + summary_version),
        trace_id=f"trace-p707-{summary_version}",
    )


class Phase7ReleasedTrialSummaryDomainTest(unittest.TestCase):
    def test_approved_and_rejected_decided_truth_are_retained_without_authority_upgrade(self) -> None:
        for state in (
            TrialConclusionRevisionState.APPROVED,
            TrialConclusionRevisionState.REJECTED,
        ):
            with self.subTest(state=state):
                value = summary(state=state)
                self.assertEqual(value.conclusion_state, state)
                self.assertEqual(
                    value.presentation_projection["externalEffects"],
                    {
                        "customerApproval": "unavailable",
                        "externalProjection": "unavailable",
                        "formalSignature": "unavailable",
                        "gateDecision": "unavailable",
                        "productionAcceptance": "unavailable",
                    },
                )

    def test_submitted_and_reopened_conclusions_cannot_be_retained(self) -> None:
        for state in (
            TrialConclusionRevisionState.SUBMITTED,
            TrialConclusionRevisionState.REOPENED,
        ):
            with self.subTest(state=state), self.assertRaises(RequestValidationFailed):
                summary(state=state)

    def test_manifest_requires_canonical_complete_unique_exact_sources(self) -> None:
        sources = manifest()
        for invalid in (
            sources[:-1],
            sources + (sources[-1],),
            tuple(reversed(sources)),
            tuple(item for item in sources if item.kind is not ReleasedTrialSummarySourceKind.TRIAL_ACTUAL_REVISION),
        ):
            with self.subTest(count=len(invalid)), self.assertRaises(RequestValidationFailed):
                projection(invalid)

        replacement_conclusion = source(
            ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION,
            17,
            5,
            "e",
        )
        with self.assertRaises(RequestValidationFailed):
            build_released_trial_summary_projection(
                project_global_id=PROJECT,
                trial_plan_global_id=PLAN,
                trial_round_global_id=ROUND,
                conclusion_revision=replacement_conclusion,
                conclusion_state=TrialConclusionRevisionState.APPROVED,
                conclusion_code=TrialConclusionCode.PASS,
                source_manifest=sources,
                facts=facts(sources),
            )

    def test_presentation_facts_are_closed_and_exact_source_bound(self) -> None:
        sources = manifest()
        base = facts(sources)
        invalid_rows = (
            {**base["inputChanges"][0], "latestValue": "unsafe"},
            {**base["inputChanges"][0], "valueState": "approved"},
            {**base["inputChanges"][0], "sourceReferences": []},
            {
                **base["inputChanges"][0],
                "sourceReferences": [
                    source(
                        ReleasedTrialSummarySourceKind.TRIAL_INPUT_LOCK_REVISION,
                        99,
                        1,
                        "b",
                    ).snapshot_payload()
                ],
            },
        )
        for invalid_row in invalid_rows:
            candidate = copy.deepcopy(base)
            candidate["inputChanges"] = [invalid_row]
            with self.subTest(row=invalid_row), self.assertRaises(RequestValidationFailed):
                build_released_trial_summary_projection(
                    project_global_id=PROJECT,
                    trial_plan_global_id=PLAN,
                    trial_round_global_id=ROUND,
                    conclusion_revision=sources[-1],
                    conclusion_state=TrialConclusionRevisionState.APPROVED,
                    conclusion_code=TrialConclusionCode.PASS,
                    source_manifest=sources,
                    facts=candidate,
                )

    def test_scalar_source_binding_rejects_latest_or_replacement_truth(self) -> None:
        sources = list(manifest())
        sources[1] = source(ReleasedTrialSummarySourceKind.TRIAL_ROUND, 3, 8, "2")
        with self.assertRaises(RequestValidationFailed):
            _rebuild(
                summary(),
                source_manifest=tuple(sources),
                presentation_projection=projection(tuple(sources)),
            )

    def test_redaction_manifest_is_closed_and_cannot_be_weakened(self) -> None:
        value = summary()
        weakened = copy.deepcopy(dict(value.redaction_manifest))
        weakened["appliedRuleCodes"] = list(weakened["appliedRuleCodes"][:-1])
        with self.assertRaises(RequestValidationFailed):
            _rebuild(value, redaction_manifest=weakened)

    def test_private_locators_and_sensitive_keys_fail_before_snapshot_creation(self) -> None:
        sources = manifest()
        for bad_facts in (
            {
                **facts(sources),
                "blockers": [
                    {**fact("blocked", "safe", sources[10]), "privateUrl": "/private/files/evidence.pdf"}
                ],
            },
            {
                **facts(sources),
                "blockers": [fact("blocked", "https://example.invalid/private", sources[10])],
            },
            {
                **facts(sources),
                "blockers": [
                    {**fact("blocked", "safe", sources[10]), "authorizationHeader": "redacted"}
                ],
            },
        ):
            with self.subTest(value=bad_facts["blockers"]), self.assertRaises(RequestValidationFailed):
                build_released_trial_summary_projection(
                    project_global_id=PROJECT,
                    trial_plan_global_id=PLAN,
                    trial_round_global_id=ROUND,
                    conclusion_revision=sources[-1],
                    conclusion_state=TrialConclusionRevisionState.APPROVED,
                    conclusion_code=TrialConclusionCode.PASS,
                    source_manifest=sources,
                    facts=bad_facts,
                )

    def test_projection_enforces_524288_utf8_bytes_without_truncation(self) -> None:
        sources = manifest()

        def attempt(count: int) -> dict[str, object]:
            candidate = facts(sources)
            candidate["inputChanges"] = [
                fact(f"material.grade.{index}", "x" * 3_900, sources[2])
                for index in range(count)
            ]
            return build_released_trial_summary_projection(
                project_global_id=PROJECT,
                trial_plan_global_id=PLAN,
                trial_round_global_id=ROUND,
                conclusion_revision=sources[-1],
                conclusion_state=TrialConclusionRevisionState.APPROVED,
                conclusion_code=TrialConclusionCode.PASS,
                source_manifest=sources,
                facts=candidate,
            )

        low, high = 0, 200
        while low + 1 < high:
            middle = (low + high) // 2
            try:
                attempt(middle)
                low = middle
            except RequestValidationFailed:
                high = middle
        accepted = attempt(low)
        encoded = json.dumps(
            accepted,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.assertLessEqual(len(encoded), MAX_SOURCE_SNAPSHOT_BYTES)
        with self.assertRaises(RequestValidationFailed):
            attempt(high)

    def test_successor_requires_exact_predecessor_and_new_decided_conclusion(self) -> None:
        first = summary()
        successor = summary(
            global_id=21,
            summary_version=2,
            predecessor=first,
            conclusion_id=17,
            conclusion_version=6,
            conclusion_marker="e",
        )
        validate_released_trial_summary_successor(first, successor)
        same_conclusion = _rebuild(
            successor,
            conclusion_revision_global_id=first.conclusion_revision_global_id,
            conclusion_version=first.conclusion_version,
            conclusion_snapshot_hash=first.conclusion_snapshot_hash,
            source_manifest=first.source_manifest,
            presentation_projection=first.presentation_projection,
        )
        with self.assertRaises(RequestValidationFailed):
            validate_released_trial_summary_successor(first, same_conclusion)

    def test_snapshot_round_trip_is_exact_and_rejects_extra_or_tampered_fields(self) -> None:
        value = summary()
        payload = {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}
        restored = released_trial_summary_from_snapshot(copy.deepcopy(payload))
        self.assertEqual(restored.snapshot_hash, value.snapshot_hash)
        self.assertEqual(restored.presentation_projection_hash, value.presentation_projection_hash)
        for mutation in ("extra", "snapshotHash"):
            candidate = copy.deepcopy(payload)
            if mutation == "extra":
                candidate["latest"] = True
            else:
                candidate["snapshotHash"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(RequestValidationFailed):
                released_trial_summary_from_snapshot(candidate)


def _rebuild(value: ReleasedTrialSummaryRevision, **changes: object) -> ReleasedTrialSummaryRevision:
    fields = {
        name: getattr(value, name)
        for name in value.__dataclass_fields__
        if name != "snapshot_hash"
    }
    fields.update(changes)
    return ReleasedTrialSummaryRevision(**fields, snapshot_hash="")


if __name__ == "__main__":
    unittest.main()
