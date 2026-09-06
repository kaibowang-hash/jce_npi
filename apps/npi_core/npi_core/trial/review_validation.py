from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from frappe import _

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.trial.review_domain import (
    TrialConclusionCode,
    TrialConclusionRevisionState,
    TrialReviewReferenceKind,
)


POLICY_CONTEXT_FIELDS = frozenset(
    {
        "policyRevisionGlobalId",
        "expectedPolicyRevisionSnapshotHash",
        "expectedRoundOptimisticVersion",
        "expectedRoundSnapshotHash",
    }
)
BEGIN_ANALYSIS_FIELDS = POLICY_CONTEXT_FIELDS | frozenset({"reason"})
CREATE_COMPARISON_FIELDS = POLICY_CONTEXT_FIELDS | frozenset({"rounds", "reason"})
CREATE_REFERENCE_FIELDS = POLICY_CONTEXT_FIELDS | frozenset(
    {
        "referenceGlobalId",
        "expectedReferenceRevisionGlobalId",
        "expectedReferenceRevisionSnapshotHash",
        "expectedReferenceVersion",
        "comparisonSnapshotGlobalId",
        "expectedComparisonSnapshotHash",
        "referenceKind",
        "partRevisionGlobalId",
        "expectedPartRevisionSnapshotHash",
        "toolingMasterGlobalId",
        "toolingRevisionGlobalId",
        "expectedToolingRevisionSnapshotHash",
        "toolingSetGlobalId",
        "expectedToolingSetSnapshotHash",
        "fileRevisionGlobalId",
        "expectedFileRevisionSnapshotHash",
        "effectiveFrom",
        "effectiveTo",
        "reason",
    }
)
SUBMIT_CONCLUSION_FIELDS = POLICY_CONTEXT_FIELDS | frozenset(
    {
        "conclusionGlobalId",
        "expectedConclusionRevisionGlobalId",
        "expectedConclusionRevisionSnapshotHash",
        "expectedConclusionVersion",
        "comparisonSnapshotGlobalId",
        "expectedComparisonSnapshotHash",
        "reviewReferences",
        "conclusionCode",
        "proposedNextWork",
        "proposedGateEffect",
        "proposedNpiEffect",
        "reason",
    }
)
DECIDE_CONCLUSION_FIELDS = POLICY_CONTEXT_FIELDS | frozenset(
    {
        "expectedConclusionRevisionGlobalId",
        "expectedConclusionRevisionSnapshotHash",
        "expectedConclusionVersion",
        "decision",
        "reason",
    }
)
REOPEN_CONCLUSION_FIELDS = POLICY_CONTEXT_FIELDS | frozenset(
    {
        "conclusionGlobalId",
        "expectedConclusionRevisionGlobalId",
        "expectedConclusionRevisionSnapshotHash",
        "expectedConclusionVersion",
        "reason",
    }
)


def policy_context_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "policy_revision_id": _uuid(
            values.get("policyRevisionGlobalId"),
            "policyRevisionGlobalId",
        ),
        "expected_policy_revision_snapshot_hash": _hash(
            values.get("expectedPolicyRevisionSnapshotHash"),
            "expectedPolicyRevisionSnapshotHash",
        ),
        "expected_round_optimistic_version": _positive(
            values.get("expectedRoundOptimisticVersion"),
            "expectedRoundOptimisticVersion",
        ),
        "expected_round_snapshot_hash": _hash(
            values.get("expectedRoundSnapshotHash"),
            "expectedRoundSnapshotHash",
        ),
    }


def begin_analysis_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **policy_context_values(values),
        "reason": _text(values.get("reason"), "reason", 1_000),
    }


def comparison_values(values: Mapping[str, Any]) -> dict[str, Any]:
    rounds = []
    for index, item in enumerate(_array(values.get("rounds"), "rounds", 2, 100)):
        path = f"rounds[{index}]"
        record = _closed(
            item,
            path,
            {
                "trialRoundGlobalId",
                "expectedOptimisticVersion",
                "expectedSnapshotHash",
            },
        )
        rounds.append(
            {
                "global_id": _uuid(record["trialRoundGlobalId"], f"{path}.trialRoundGlobalId"),
                "optimistic_version": _positive(
                    record["expectedOptimisticVersion"],
                    f"{path}.expectedOptimisticVersion",
                ),
                "snapshot_hash": _hash(
                    record["expectedSnapshotHash"],
                    f"{path}.expectedSnapshotHash",
                ),
            }
        )
    if len({item["global_id"] for item in rounds}) != len(rounds):
        raise _field("rounds", _("Values must be unique."))
    return {
        **policy_context_values(values),
        "rounds": tuple(rounds),
        "reason": _text(values.get("reason"), "reason", 1_000),
    }


def reference_values(values: Mapping[str, Any]) -> dict[str, Any]:
    reference = _optional_predecessor(
        values,
        stable_key="referenceGlobalId",
        revision_key="expectedReferenceRevisionGlobalId",
        hash_key="expectedReferenceRevisionSnapshotHash",
        version_key="expectedReferenceVersion",
    )
    effective_from = _optional_date(values.get("effectiveFrom"), "effectiveFrom")
    effective_to = _optional_date(values.get("effectiveTo"), "effectiveTo")
    if effective_from and effective_to and effective_to < effective_from:
        raise _field("effectiveTo", _("The end date must not be before the start date."))
    return {
        **policy_context_values(values),
        "reference_predecessor": reference,
        "comparison_snapshot_id": _uuid(
            values.get("comparisonSnapshotGlobalId"),
            "comparisonSnapshotGlobalId",
        ),
        "expected_comparison_snapshot_hash": _hash(
            values.get("expectedComparisonSnapshotHash"),
            "expectedComparisonSnapshotHash",
        ),
        "reference_kind": _choice(
            values.get("referenceKind"),
            "referenceKind",
            TrialReviewReferenceKind,
        ),
        "part_revision": _exact_reference(values, "partRevision"),
        "tooling_master_id": _uuid(
            values.get("toolingMasterGlobalId"),
            "toolingMasterGlobalId",
        ),
        "tooling_revision": _exact_reference(values, "toolingRevision"),
        "tooling_set": _exact_reference(values, "toolingSet"),
        "file_revision": _exact_reference(values, "fileRevision"),
        "effective_from": effective_from,
        "effective_to": effective_to,
        "reason": _text(values.get("reason"), "reason", 1_000),
    }


def conclusion_values(values: Mapping[str, Any]) -> dict[str, Any]:
    predecessor = _optional_predecessor(
        values,
        stable_key="conclusionGlobalId",
        revision_key="expectedConclusionRevisionGlobalId",
        hash_key="expectedConclusionRevisionSnapshotHash",
        version_key="expectedConclusionVersion",
    )
    references = _exact_reference_array(values.get("reviewReferences"), "reviewReferences", 1, 100)
    next_work = tuple(
        _text(item, f"proposedNextWork[{index}]", 1_000)
        for index, item in enumerate(
            _array(values.get("proposedNextWork"), "proposedNextWork", 1, 100)
        )
    )
    return {
        **policy_context_values(values),
        "conclusion_predecessor": predecessor,
        "comparison_snapshot_id": _uuid(
            values.get("comparisonSnapshotGlobalId"),
            "comparisonSnapshotGlobalId",
        ),
        "expected_comparison_snapshot_hash": _hash(
            values.get("expectedComparisonSnapshotHash"),
            "expectedComparisonSnapshotHash",
        ),
        "review_references": references,
        "conclusion_code": _choice(
            values.get("conclusionCode"),
            "conclusionCode",
            TrialConclusionCode,
        ),
        "proposed_next_work": next_work,
        "proposed_gate_effect": _text(
            values.get("proposedGateEffect"),
            "proposedGateEffect",
            1_000,
        ),
        "proposed_npi_effect": _text(
            values.get("proposedNpiEffect"),
            "proposedNpiEffect",
            1_000,
        ),
        "reason": _text(values.get("reason"), "reason", 2_000),
    }


def decision_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **policy_context_values(values),
        "expected_conclusion_revision_id": _uuid(
            values.get("expectedConclusionRevisionGlobalId"),
            "expectedConclusionRevisionGlobalId",
        ),
        "expected_conclusion_revision_snapshot_hash": _hash(
            values.get("expectedConclusionRevisionSnapshotHash"),
            "expectedConclusionRevisionSnapshotHash",
        ),
        "expected_conclusion_version": _positive(
            values.get("expectedConclusionVersion"),
            "expectedConclusionVersion",
        ),
        "decision": _choice(
            values.get("decision"),
            "decision",
            TrialConclusionRevisionState,
            allowed={
                TrialConclusionRevisionState.APPROVED,
                TrialConclusionRevisionState.REJECTED,
            },
        ),
        "reason": _text(values.get("reason"), "reason", 2_000),
    }


def reopen_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **policy_context_values(values),
        "conclusion_id": _uuid(values.get("conclusionGlobalId"), "conclusionGlobalId"),
        "expected_conclusion_revision_id": _uuid(
            values.get("expectedConclusionRevisionGlobalId"),
            "expectedConclusionRevisionGlobalId",
        ),
        "expected_conclusion_revision_snapshot_hash": _hash(
            values.get("expectedConclusionRevisionSnapshotHash"),
            "expectedConclusionRevisionSnapshotHash",
        ),
        "expected_conclusion_version": _positive(
            values.get("expectedConclusionVersion"),
            "expectedConclusionVersion",
        ),
        "reason": _text(values.get("reason"), "reason", 2_000),
    }


def _optional_predecessor(
    values: Mapping[str, Any],
    *,
    stable_key: str,
    revision_key: str,
    hash_key: str,
    version_key: str,
) -> dict[str, Any] | None:
    raw = (
        values.get(stable_key),
        values.get(revision_key),
        values.get(hash_key),
        values.get(version_key),
    )
    if all(value is None for value in raw):
        return None
    if any(value is None for value in raw):
        raise _field(stable_key, _("Select one complete exact predecessor, or leave it empty."))
    return {
        "stable_id": _uuid(raw[0], stable_key),
        "revision_id": _uuid(raw[1], revision_key),
        "snapshot_hash": _hash(raw[2], hash_key),
        "version": _positive(raw[3], version_key),
    }


def _exact_reference(values: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    lower = prefix[0].lower() + prefix[1:]
    upper = prefix[0].upper() + prefix[1:]
    return {
        "global_id": _uuid(values.get(f"{lower}GlobalId"), f"{lower}GlobalId"),
        "snapshot_hash": _hash(
            values.get(f"expected{upper}SnapshotHash"),
            f"expected{upper}SnapshotHash",
        ),
    }


def _exact_reference_array(
    value: object,
    path: str,
    minimum: int,
    maximum: int,
) -> tuple[dict[str, Any], ...]:
    prepared = []
    for index, item in enumerate(_array(value, path, minimum, maximum)):
        item_path = f"{path}[{index}]"
        record = _closed(item, item_path, {"globalId", "snapshotHash"})
        prepared.append(
            {
                "global_id": _uuid(record["globalId"], f"{item_path}.globalId"),
                "snapshot_hash": _hash(record["snapshotHash"], f"{item_path}.snapshotHash"),
            }
        )
    if len({item["global_id"] for item in prepared}) != len(prepared):
        raise _field(path, _("Values must be unique."))
    return tuple(prepared)


def _closed(value: object, path: str, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _field(path, _("Enter a valid closed object."))
    return value


def _array(
    value: object,
    path: str,
    minimum: int,
    maximum: int,
) -> Sequence[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not minimum <= len(value) <= maximum
    ):
        raise _field(path, _("Enter a valid list."))
    return value


def _choice(
    value: object,
    path: str,
    enum_type: type[StrEnum],
    *,
    allowed: set[StrEnum] | None = None,
) -> StrEnum:
    try:
        result = enum_type(value)
    except (TypeError, ValueError) as error:
        raise _field(path, _("Select a supported value.")) from error
    if allowed is not None and result not in allowed:
        raise _field(path, _("Select a supported value."))
    return result


def _uuid(value: object, path: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(path, _("Enter a positive integer."))
    return value


def _hash(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _field(path, _("Enter a valid SHA-256 hash."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field(path, _("Enter a shorter value."))
    return normalized


def _optional_date(value: object, path: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _field(path, _("Enter a valid date.")) from error


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
