from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from frappe import _

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.engineering_controls_domain import (
    ToolingDefectActionState,
    ToolingDefectActionType,
    ToolingDefectRootCauseState,
    ToolingDefectSeverity,
    ToolingDefectState,
)
from npi_core.trial.quality_domain import (
    TrialDefectPredecessorKind,
    TrialDefectVerificationResult,
    TrialQualityMeasurementState,
    TrialQualityObservationSource,
)


ROUND_CONTEXT_FIELDS = frozenset(
    {
        "expectedRoundOptimisticVersion",
        "expectedRoundSnapshotHash",
        "expectedInputLockRevisionGlobalId",
        "expectedInputLockRevisionSnapshotHash",
    }
)
CREATE_CAVITY_RESULT_FIELDS = ROUND_CONTEXT_FIELDS | frozenset(
    {
        "sampleBatchRevisionGlobalId",
        "expectedSampleBatchRevisionSnapshotHash",
        "cavityGlobalId",
        "measurements",
        "evidence",
        "reason",
    }
)
REVISE_CAVITY_RESULT_FIELDS = ROUND_CONTEXT_FIELDS | frozenset(
    {
        "expectedRevisionGlobalId",
        "expectedRevisionSnapshotHash",
        "expectedResultVersion",
        "measurements",
        "reason",
    }
)
_DEFECT_VALUE_FIELDS = frozenset(
    {
        "sampleBatchRevisionGlobalId",
        "expectedSampleBatchRevisionSnapshotHash",
        "cavityGlobalId",
        "businessCode",
        "title",
        "description",
        "categoryKey",
        "location",
        "severity",
        "blocking",
        "state",
        "rootCauseState",
        "rootCause",
        "responsibleMember",
        "occurrenceCount",
        "actions",
        "evidence",
        "reason",
    }
)
_DEFECT_PREDECESSOR_FIELDS = frozenset(
    {
        "expectedPredecessorKind",
        "expectedPredecessorGlobalId",
        "expectedPredecessorSnapshotHash",
        "expectedDefectVersion",
    }
)
CREATE_DEFECT_FIELDS = (
    ROUND_CONTEXT_FIELDS
    | _DEFECT_VALUE_FIELDS
    | _DEFECT_PREDECESSOR_FIELDS
    | frozenset({"defectGlobalId"})
)
REVISE_DEFECT_FIELDS = ROUND_CONTEXT_FIELDS | _DEFECT_VALUE_FIELDS | _DEFECT_PREDECESSOR_FIELDS
VERIFY_DEFECT_FIELDS = frozenset(
    {
        "expectedDefectRevisionGlobalId",
        "expectedDefectRevisionSnapshotHash",
        "actionGlobalId",
        "verificationGlobalId",
        "expectedAttemptSequence",
        "targetRoundGlobalId",
        "expectedTargetRoundOptimisticVersion",
        "expectedTargetRoundSnapshotHash",
        "cavityResultRevisionGlobalId",
        "expectedCavityResultRevisionSnapshotHash",
        "verifierMember",
        "result",
        "finding",
        "observedAt",
        "evidence",
    }
)


def create_cavity_result_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_round_context(values),
        "sample_batch_revision_id": _uuid(
            values.get("sampleBatchRevisionGlobalId"),
            "sampleBatchRevisionGlobalId",
        ),
        "expected_sample_batch_revision_snapshot_hash": _hash(
            values.get("expectedSampleBatchRevisionSnapshotHash"),
            "expectedSampleBatchRevisionSnapshotHash",
        ),
        "cavity_id": _uuid(values.get("cavityGlobalId"), "cavityGlobalId"),
        "measurements": _measurements(values.get("measurements")),
        "evidence": _evidence(values.get("evidence")),
        "reason": _text(values.get("reason"), "reason", 1_000),
    }


def revise_cavity_result_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_round_context(values),
        "expected_revision_id": _uuid(
            values.get("expectedRevisionGlobalId"),
            "expectedRevisionGlobalId",
        ),
        "expected_revision_snapshot_hash": _hash(
            values.get("expectedRevisionSnapshotHash"),
            "expectedRevisionSnapshotHash",
        ),
        "expected_result_version": _positive(
            values.get("expectedResultVersion"),
            "expectedResultVersion",
        ),
        "measurements": _measurements(values.get("measurements")),
        "reason": _text(values.get("reason"), "reason", 1_000),
    }


def create_defect_values(values: Mapping[str, Any]) -> dict[str, Any]:
    prepared = _defect_values(values)
    defect_id = _optional_uuid(values.get("defectGlobalId"), "defectGlobalId")
    predecessor = _predecessor(values, required=False)
    if (defect_id is None) != (predecessor is None):
        raise _field(
            "defectGlobalId",
            _("Select one complete current NPI defect predecessor, or create a new defect."),
        )
    return {**prepared, "defect_id": defect_id, "predecessor": predecessor}


def revise_defect_values(values: Mapping[str, Any]) -> dict[str, Any]:
    predecessor = _predecessor(values, required=True)
    if predecessor is None:  # Kept explicit for type narrowing and fail-closed review.
        raise _field("expectedPredecessorGlobalId", _("Select the exact current NPI defect revision."))
    return {**_defect_values(values), "predecessor": predecessor}


def verification_values(values: Mapping[str, Any]) -> dict[str, Any]:
    verification_id = _optional_uuid(
        values.get("verificationGlobalId"),
        "verificationGlobalId",
    )
    expected_attempt = _optional_positive(
        values.get("expectedAttemptSequence"),
        "expectedAttemptSequence",
    )
    if (verification_id is None) != (expected_attempt is None):
        raise _field(
            "verificationGlobalId",
            _("Select one complete verification attempt predecessor, or start a new verification."),
        )
    return {
        "expected_defect_revision_id": _uuid(
            values.get("expectedDefectRevisionGlobalId"),
            "expectedDefectRevisionGlobalId",
        ),
        "expected_defect_revision_snapshot_hash": _hash(
            values.get("expectedDefectRevisionSnapshotHash"),
            "expectedDefectRevisionSnapshotHash",
        ),
        "action_id": _uuid(values.get("actionGlobalId"), "actionGlobalId"),
        "verification_id": verification_id,
        "expected_attempt_sequence": expected_attempt,
        "target_round_id": _uuid(values.get("targetRoundGlobalId"), "targetRoundGlobalId"),
        "expected_target_round_optimistic_version": _positive(
            values.get("expectedTargetRoundOptimisticVersion"),
            "expectedTargetRoundOptimisticVersion",
        ),
        "expected_target_round_snapshot_hash": _hash(
            values.get("expectedTargetRoundSnapshotHash"),
            "expectedTargetRoundSnapshotHash",
        ),
        "cavity_result_revision_id": _uuid(
            values.get("cavityResultRevisionGlobalId"),
            "cavityResultRevisionGlobalId",
        ),
        "expected_cavity_result_revision_snapshot_hash": _hash(
            values.get("expectedCavityResultRevisionSnapshotHash"),
            "expectedCavityResultRevisionSnapshotHash",
        ),
        "verifier_member": _member(values.get("verifierMember"), "verifierMember"),
        "result": _choice(
            values.get("result"),
            "result",
            TrialDefectVerificationResult,
        ),
        "finding": _text(values.get("finding"), "finding", 4_000),
        "observed_at": _datetime(values.get("observedAt"), "observedAt"),
        "evidence": _evidence(values.get("evidence")),
    }


def _round_context(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "expected_round_optimistic_version": _positive(
            values.get("expectedRoundOptimisticVersion"),
            "expectedRoundOptimisticVersion",
        ),
        "expected_round_snapshot_hash": _hash(
            values.get("expectedRoundSnapshotHash"),
            "expectedRoundSnapshotHash",
        ),
        "expected_input_lock_revision_id": _uuid(
            values.get("expectedInputLockRevisionGlobalId"),
            "expectedInputLockRevisionGlobalId",
        ),
        "expected_input_lock_revision_snapshot_hash": _hash(
            values.get("expectedInputLockRevisionSnapshotHash"),
            "expectedInputLockRevisionSnapshotHash",
        ),
    }


def _defect_values(values: Mapping[str, Any]) -> dict[str, Any]:
    sample_id = _optional_uuid(
        values.get("sampleBatchRevisionGlobalId"),
        "sampleBatchRevisionGlobalId",
    )
    sample_hash = _optional_hash(
        values.get("expectedSampleBatchRevisionSnapshotHash"),
        "expectedSampleBatchRevisionSnapshotHash",
    )
    if (sample_id is None) != (sample_hash is None):
        raise _field(
            "sampleBatchRevisionGlobalId",
            _("Select one complete Sample Batch revision, or leave it empty."),
        )
    responsible = values.get("responsibleMember")
    return {
        **_round_context(values),
        "sample_batch_revision_id": sample_id,
        "expected_sample_batch_revision_snapshot_hash": sample_hash,
        "cavity_id": _uuid(values.get("cavityGlobalId"), "cavityGlobalId"),
        "business_code": _key(values.get("businessCode"), "businessCode"),
        "title": _text(values.get("title"), "title", 255),
        "description": _text(values.get("description"), "description", 4_000),
        "category_key": _key(values.get("categoryKey"), "categoryKey"),
        "location": _text(values.get("location"), "location", 255),
        "severity": _choice(values.get("severity"), "severity", ToolingDefectSeverity),
        "blocking": _boolean(values.get("blocking"), "blocking"),
        "state": _choice(values.get("state"), "state", ToolingDefectState),
        "root_cause_state": _choice(
            values.get("rootCauseState"),
            "rootCauseState",
            ToolingDefectRootCauseState,
        ),
        "root_cause": _optional_text(values.get("rootCause"), "rootCause", 4_000),
        "responsible_member": (
            None if responsible is None else _member(responsible, "responsibleMember")
        ),
        "occurrence_count": _positive(values.get("occurrenceCount"), "occurrenceCount"),
        "actions": _actions(values.get("actions")),
        "evidence": _evidence(values.get("evidence")),
        "reason": _text(values.get("reason"), "reason", 1_000),
    }


def _predecessor(
    values: Mapping[str, Any],
    *,
    required: bool,
) -> dict[str, Any] | None:
    raw = (
        values.get("expectedPredecessorKind"),
        values.get("expectedPredecessorGlobalId"),
        values.get("expectedPredecessorSnapshotHash"),
        values.get("expectedDefectVersion"),
    )
    if all(value is None for value in raw) and not required:
        return None
    if any(value is None for value in raw):
        raise _field(
            "expectedPredecessorGlobalId",
            _("Select the exact current NPI defect revision."),
        )
    return {
        "kind": _choice(raw[0], "expectedPredecessorKind", TrialDefectPredecessorKind),
        "global_id": _uuid(raw[1], "expectedPredecessorGlobalId"),
        "snapshot_hash": _hash(raw[2], "expectedPredecessorSnapshotHash"),
        "defect_version": _positive(raw[3], "expectedDefectVersion"),
    }


def _measurements(value: object) -> tuple[dict[str, Any], ...]:
    prepared = []
    for index, item in enumerate(_array(value, "measurements", 1, 500)):
        path = f"measurements[{index}]"
        record = _closed(
            item,
            path,
            {
                "characteristicKey",
                "label",
                "unit",
                "nominalValue",
                "lowerLimit",
                "upperLimit",
                "required",
                "state",
                "value",
                "source",
                "observedAt",
            },
        )
        state = _choice(record["state"], f"{path}.state", TrialQualityMeasurementState)
        numeric = record["value"]
        if (state is TrialQualityMeasurementState.MEASURED) != (numeric is not None):
            raise _field(
                f"{path}.value",
                _("A measured characteristic requires one value; a missing measurement must stay empty."),
            )
        prepared.append(
            {
                "characteristic_key": _key(record["characteristicKey"], f"{path}.characteristicKey"),
                "label": _text(record["label"], f"{path}.label", 255),
                "unit": _text(record["unit"], f"{path}.unit", 32),
                "nominal_value": _text(record["nominalValue"], f"{path}.nominalValue", 64),
                "lower_limit": _text(record["lowerLimit"], f"{path}.lowerLimit", 64),
                "upper_limit": _text(record["upperLimit"], f"{path}.upperLimit", 64),
                "required": _boolean(record["required"], f"{path}.required"),
                "state": state,
                "value": None if numeric is None else _text(numeric, f"{path}.value", 64),
                "source": _choice(record["source"], f"{path}.source", TrialQualityObservationSource),
                "observed_at": _datetime(record["observedAt"], f"{path}.observedAt"),
            }
        )
    if len({item["characteristic_key"] for item in prepared}) != len(prepared):
        raise _field("measurements", _("Values must be unique."))
    return tuple(prepared)


def _actions(value: object) -> tuple[dict[str, Any], ...]:
    prepared = []
    for index, item in enumerate(_array(value, "actions", 0, 100)):
        path = f"actions[{index}]"
        record = _closed(
            item,
            path,
            {
                "globalId",
                "actionType",
                "state",
                "detail",
                "responsibleMember",
                "dueDate",
                "targetRoundGlobalId",
                "targetRoundOptimisticVersion",
                "targetRoundSnapshotHash",
                "verificationRevisionGlobalId",
                "verificationRevisionSnapshotHash",
            },
        )
        verification_id = _optional_uuid(
            record["verificationRevisionGlobalId"],
            f"{path}.verificationRevisionGlobalId",
        )
        verification_hash = _optional_hash(
            record["verificationRevisionSnapshotHash"],
            f"{path}.verificationRevisionSnapshotHash",
        )
        if (verification_id is None) != (verification_hash is None):
            raise _field(
                f"{path}.verificationRevisionGlobalId",
                _("Select one complete defect verification revision, or leave it empty."),
            )
        prepared.append(
            {
                "global_id": _optional_uuid(record["globalId"], f"{path}.globalId"),
                "action_type": _choice(record["actionType"], f"{path}.actionType", ToolingDefectActionType),
                "state": _choice(record["state"], f"{path}.state", ToolingDefectActionState),
                "detail": _text(record["detail"], f"{path}.detail", 2_000),
                "responsible_member": _member(record["responsibleMember"], f"{path}.responsibleMember"),
                "due_date": _date(record["dueDate"], f"{path}.dueDate"),
                "target_round_id": _uuid(record["targetRoundGlobalId"], f"{path}.targetRoundGlobalId"),
                "target_round_optimistic_version": _positive(record["targetRoundOptimisticVersion"], f"{path}.targetRoundOptimisticVersion"),
                "target_round_snapshot_hash": _hash(record["targetRoundSnapshotHash"], f"{path}.targetRoundSnapshotHash"),
                "verification_revision_id": verification_id,
                "verification_revision_snapshot_hash": verification_hash,
            }
        )
    stable_ids = [item["global_id"] for item in prepared if item["global_id"] is not None]
    if len(set(stable_ids)) != len(stable_ids):
        raise _field("actions", _("Values must be unique."))
    return tuple(prepared)


def _evidence(value: object) -> tuple[dict[str, Any], ...]:
    prepared = []
    for index, item in enumerate(_array(value, "evidence", 1, 100)):
        path = f"evidence[{index}]"
        record = _closed(item, path, {"globalId", "snapshotHash"})
        prepared.append(
            {
                "global_id": _uuid(record["globalId"], f"{path}.globalId"),
                "snapshot_hash": _hash(record["snapshotHash"], f"{path}.snapshotHash"),
            }
        )
    if len({item["global_id"] for item in prepared}) != len(prepared):
        raise _field("evidence", _("Values must be unique."))
    return tuple(prepared)


def _member(value: object, path: str) -> dict[str, Any]:
    record = _closed(value, path, {"globalId", "optimisticVersion"})
    return {
        "global_id": _uuid(record["globalId"], f"{path}.globalId"),
        "optimistic_version": _positive(record["optimisticVersion"], f"{path}.optimisticVersion"),
    }


def _closed(value: object, path: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _field(path, _("Enter a valid closed object."))
    return dict(value)


def _array(value: object, path: str, minimum: int, maximum: int) -> list[Any]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not minimum <= len(value) <= maximum
    ):
        raise _field(path, _("Enter a valid bounded list."))
    return list(value)


def _choice(value: object, path: str, enum_type):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise _field(path, _("Select a supported value.")) from error


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a valid global ID."))
    return parsed


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid(value, path)


def _hash(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _field(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value in (None, "") else _hash(value, path)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(path, _("Enter a positive integer."))
    return value


def _optional_positive(value: object, path: str) -> int | None:
    return None if value is None else _positive(value, path)


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _field(path, _("Select true or false."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field(path, _("Enter a shorter value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _key(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if not normalized[0].isalnum() or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:@/-"
        for character in normalized
    ):
        raise _field(path, _("Enter a valid value."))
    return normalized


def _datetime(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise _field(path, _("Enter a valid date and time.")) from error
    else:
        raise _field(path, _("Enter a valid date and time."))
    if parsed.tzinfo is None:
        raise _field(path, _("Enter a valid date and time."))
    return parsed.astimezone(UTC)


def _date(value: object, path: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise _field(path, _("Enter a valid date.")) from error
    raise _field(path, _("Enter a valid date."))


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
