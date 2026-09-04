from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Sequence
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.tooling.engineering_controls_domain import (
    ToolingDefectActionState,
    ToolingDefectActionType,
    ToolingDefectRevision,
    ToolingDefectRootCauseState,
    ToolingDefectSeverity,
    ToolingDefectState,
)
from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility
from npi_core.trial.domain import TRIAL_SCHEMA_VERSION, sha256_json

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


class TrialQualityMeasurementState(StrEnum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"


class TrialQualityComparisonState(StrEnum):
    NOT_MEASURED = "not_measured"
    WITHIN_SPEC = "within_spec"
    OUT_OF_SPEC = "out_of_spec"


class TrialQualityObservationSource(StrEnum):
    MANUAL = "manual"


class TrialDefectPredecessorKind(StrEnum):
    TOOLING_DEFECT_REVISION = "tooling_defect_revision"
    TRIAL_DEFECT_REVISION = "trial_defect_revision"


class TrialDefectVerificationResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class TrialQualityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TRIAL_QUALITY_UNAVAILABLE",
            _("The Trial quality workspace is unavailable."),
        )


class TrialQualityReferenceUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TRIAL_QUALITY_REFERENCE_UNAVAILABLE",
            _("The selected Trial quality reference is unavailable."),
        )


class TrialQualityConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TRIAL_QUALITY_CONFLICT",
            _("The Trial quality record was changed by another user."),
        )


class TrialQualityRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "TRIAL_QUALITY_ROUTES_DISABLED",
            _("The Trial quality workspace is temporarily unavailable."),
            _("The quality routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


@dataclass(frozen=True, slots=True)
class TrialQualityEvidenceReference:
    global_id: UUID
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "evidence.globalId"))
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "evidence.snapshotHash"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class TrialCavityMeasurement:
    characteristic_key: str
    label: str
    unit: str
    nominal_value: str
    lower_limit: str
    upper_limit: str
    required: bool
    state: TrialQualityMeasurementState
    value: str | None
    source: TrialQualityObservationSource
    observed_at: datetime
    observed_by_user_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "characteristic_key",
            _key(self.characteristic_key, "measurements.characteristicKey"),
        )
        object.__setattr__(self, "label", _text(self.label, "measurements.label", 255))
        object.__setattr__(self, "unit", _text(self.unit, "measurements.unit", 32))
        for fieldname, path in (
            ("nominal_value", "measurements.nominalValue"),
            ("lower_limit", "measurements.lowerLimit"),
            ("upper_limit", "measurements.upperLimit"),
        ):
            object.__setattr__(self, fieldname, _decimal(getattr(self, fieldname), path))
        lower = Decimal(self.lower_limit)
        nominal = Decimal(self.nominal_value)
        upper = Decimal(self.upper_limit)
        if not lower <= nominal <= upper:
            raise _problem(
                "measurements.nominalValue",
                _("The nominal value must be within the specification limits."),
            )
        if type(self.required) is not bool:
            raise _problem(
                "measurements.required",
                _("Select a valid true or false value."),
            )
        _enum(self.state, TrialQualityMeasurementState, "measurements.state")
        if self.state is TrialQualityMeasurementState.MEASURED:
            object.__setattr__(self, "value", _decimal(self.value, "measurements.value"))
        elif self.value is not None:
            raise _problem(
                "measurements.value",
                _("A not measured characteristic cannot contain a numeric value."),
            )
        _enum(self.source, TrialQualityObservationSource, "measurements.source")
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "measurements.observedAt"))
        object.__setattr__(
            self,
            "observed_by_user_id",
            _actor(self.observed_by_user_id, "measurements.observedByUserId"),
        )

    @property
    def comparison_state(self) -> TrialQualityComparisonState:
        if self.state is TrialQualityMeasurementState.NOT_MEASURED:
            return TrialQualityComparisonState.NOT_MEASURED
        value = Decimal(self.value or "0")
        if Decimal(self.lower_limit) <= value <= Decimal(self.upper_limit):
            return TrialQualityComparisonState.WITHIN_SPEC
        return TrialQualityComparisonState.OUT_OF_SPEC

    def definition_payload(self) -> dict[str, object]:
        return {
            "characteristicKey": self.characteristic_key,
            "label": self.label,
            "unit": self.unit,
            "nominalValue": self.nominal_value,
            "lowerLimit": self.lower_limit,
            "upperLimit": self.upper_limit,
            "required": self.required,
        }

    def snapshot_payload(self) -> dict[str, object]:
        return {
            **self.definition_payload(),
            "state": self.state.value,
            "value": self.value,
            "comparisonState": self.comparison_state.value,
            "source": self.source.value,
            "observedAt": _utc_text(self.observed_at),
            "observedByUserId": self.observed_by_user_id,
        }


@dataclass(frozen=True, slots=True)
class TrialCavityResultRevision:
    global_id: UUID
    cavity_result_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    input_lock_revision_global_id: UUID
    input_lock_revision_snapshot_hash: str
    sample_batch_revision_global_id: UUID
    sample_batch_revision_snapshot_hash: str
    tooling_revision_global_id: UUID
    tooling_revision_snapshot_hash: str
    tooling_set_global_id: UUID
    tooling_set_snapshot_hash: str
    cavity_global_id: UUID
    result_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    measurements: tuple[TrialCavityMeasurement, ...]
    evidence: tuple[TrialQualityEvidenceReference, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "cavity_result_global_id",
            "project_global_id",
            "trial_round_global_id",
            "input_lock_revision_global_id",
            "sample_batch_revision_global_id",
            "tooling_revision_global_id",
            "tooling_set_global_id",
            "cavity_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        for fieldname in (
            "input_lock_revision_snapshot_hash",
            "sample_batch_revision_snapshot_hash",
            "tooling_revision_snapshot_hash",
            "tooling_set_snapshot_hash",
        ):
            object.__setattr__(self, fieldname, _hash(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "result_version", _positive(self.result_version, "resultVersion"))
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        object.__setattr__(
            self,
            "predecessor_snapshot_hash",
            _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
        )
        _require_predecessor(
            self.result_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "predecessorGlobalId",
        )
        measurements = _typed_tuple(
            self.measurements,
            TrialCavityMeasurement,
            "measurements",
            minimum=1,
            maximum=500,
        )
        _unique((item.characteristic_key for item in measurements), "measurements")
        object.__setattr__(
            self,
            "measurements",
            tuple(sorted(measurements, key=lambda item: item.characteristic_key)),
        )
        evidence = _typed_tuple(
            self.evidence,
            TrialQualityEvidenceReference,
            "evidence",
            minimum=1,
            maximum=100,
        )
        _unique((item.global_id for item in evidence), "evidence")
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(evidence, key=lambda item: str(item.global_id))),
        )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial cavity result snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "cavityResultGlobalId": str(self.cavity_result_global_id),
                "resultVersion": self.result_version,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "cavityResultGlobalId": str(self.cavity_result_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "inputLockRevisionGlobalId": str(self.input_lock_revision_global_id),
            "inputLockRevisionSnapshotHash": self.input_lock_revision_snapshot_hash,
            "sampleBatchRevisionGlobalId": str(self.sample_batch_revision_global_id),
            "sampleBatchRevisionSnapshotHash": self.sample_batch_revision_snapshot_hash,
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "toolingSetSnapshotHash": self.tooling_set_snapshot_hash,
            "cavityGlobalId": str(self.cavity_global_id),
            "resultVersion": self.result_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "measurements": [item.snapshot_payload() for item in self.measurements],
            "evidence": [item.snapshot_payload() for item in self.evidence],
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_cavity_result_successor(
    predecessor: TrialCavityResultRevision,
    successor: TrialCavityResultRevision,
) -> None:
    immutable = (
        "cavity_result_global_id",
        "tenant_id",
        "project_global_id",
        "trial_round_global_id",
        "input_lock_revision_global_id",
        "input_lock_revision_snapshot_hash",
        "sample_batch_revision_global_id",
        "sample_batch_revision_snapshot_hash",
        "tooling_revision_global_id",
        "tooling_revision_snapshot_hash",
        "tooling_set_global_id",
        "tooling_set_snapshot_hash",
        "cavity_global_id",
        "evidence",
    )
    if (
        any(getattr(predecessor, field) != getattr(successor, field) for field in immutable)
        or successor.result_version != predecessor.result_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
        or tuple(item.definition_payload() for item in successor.measurements)
        != tuple(item.definition_payload() for item in predecessor.measurements)
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Trial cavity result revision."),
        )


@dataclass(frozen=True, slots=True)
class TrialDefectAction:
    global_id: UUID
    action_type: ToolingDefectActionType
    state: ToolingDefectActionState
    detail: str
    responsible_member: ProjectMemberResponsibility
    due_date: date
    target_round_global_id: UUID
    target_round_optimistic_version: int
    target_round_snapshot_hash: str
    verification_revision_global_id: UUID | None = None
    verification_revision_snapshot_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "actions.globalId"))
        _enum(self.action_type, ToolingDefectActionType, "actions.actionType")
        _enum(self.state, ToolingDefectActionState, "actions.state")
        object.__setattr__(self, "detail", _text(self.detail, "actions.detail", 2_000))
        if not isinstance(self.responsible_member, ProjectMemberResponsibility):
            raise _problem(
                "actions.responsibleMember",
                _("Select a valid Project member."),
            )
        object.__setattr__(self, "due_date", _date(self.due_date, "actions.dueDate"))
        object.__setattr__(
            self,
            "target_round_global_id",
            _uuid(self.target_round_global_id, "actions.targetRoundGlobalId"),
        )
        object.__setattr__(
            self,
            "target_round_optimistic_version",
            _positive(
                self.target_round_optimistic_version,
                "actions.targetRoundOptimisticVersion",
            ),
        )
        object.__setattr__(
            self,
            "target_round_snapshot_hash",
            _hash(self.target_round_snapshot_hash, "actions.targetRoundSnapshotHash"),
        )
        object.__setattr__(
            self,
            "verification_revision_global_id",
            _optional_uuid(
                self.verification_revision_global_id,
                "actions.verificationRevisionGlobalId",
            ),
        )
        object.__setattr__(
            self,
            "verification_revision_snapshot_hash",
            _optional_hash(
                self.verification_revision_snapshot_hash,
                "actions.verificationRevisionSnapshotHash",
            ),
        )
        has_verification = self.verification_revision_global_id is not None
        if has_verification != (self.verification_revision_snapshot_hash is not None):
            raise _problem(
                "actions.verificationRevisionGlobalId",
                _("Select one complete defect verification revision, or leave it empty."),
            )
        if (self.state is ToolingDefectActionState.VERIFIED) != has_verification:
            raise _problem(
                "actions.verificationRevisionGlobalId",
                _("A verified defect action requires one exact successful verification."),
            )

    def stable_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "actionType": self.action_type.value,
            "detail": self.detail,
            "responsibleMember": self.responsible_member.snapshot_payload(),
            "dueDate": self.due_date.isoformat(),
            "targetRoundGlobalId": str(self.target_round_global_id),
            "targetRoundOptimisticVersion": self.target_round_optimistic_version,
            "targetRoundSnapshotHash": self.target_round_snapshot_hash,
        }

    def snapshot_payload(self) -> dict[str, object]:
        return {
            **self.stable_payload(),
            "state": self.state.value,
            "verificationRevisionGlobalId": (
                str(self.verification_revision_global_id)
                if self.verification_revision_global_id
                else None
            ),
            "verificationRevisionSnapshotHash": self.verification_revision_snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class TrialDefectRevision:
    global_id: UUID
    defect_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    trial_round_global_id: UUID
    trial_round_optimistic_version: int
    trial_round_snapshot_hash: str
    input_lock_revision_global_id: UUID
    input_lock_revision_snapshot_hash: str
    tooling_revision_global_id: UUID
    tooling_revision_snapshot_hash: str
    tooling_set_global_id: UUID
    tooling_set_snapshot_hash: str
    cavity_global_id: UUID
    sample_batch_revision_global_id: UUID | None
    sample_batch_revision_snapshot_hash: str | None
    defect_version: int
    predecessor_kind: TrialDefectPredecessorKind | None
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    business_code: str
    title: str
    description: str
    category_key: str
    location: str
    severity: ToolingDefectSeverity
    blocking: bool
    state: ToolingDefectState
    root_cause_state: ToolingDefectRootCauseState
    root_cause: str | None
    responsible_member: ProjectMemberResponsibility | None
    occurrence_count: int
    actions: tuple[TrialDefectAction, ...]
    evidence: tuple[TrialQualityEvidenceReference, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "defect_global_id",
            "project_global_id",
            "tooling_master_global_id",
            "trial_round_global_id",
            "input_lock_revision_global_id",
            "tooling_revision_global_id",
            "tooling_set_global_id",
            "cavity_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "trial_round_optimistic_version",
            _positive(self.trial_round_optimistic_version, "trialRoundOptimisticVersion"),
        )
        for fieldname in (
            "trial_round_snapshot_hash",
            "input_lock_revision_snapshot_hash",
            "tooling_revision_snapshot_hash",
            "tooling_set_snapshot_hash",
        ):
            object.__setattr__(self, fieldname, _hash(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(
            self,
            "sample_batch_revision_global_id",
            _optional_uuid(
                self.sample_batch_revision_global_id,
                "sampleBatchRevisionGlobalId",
            ),
        )
        object.__setattr__(
            self,
            "sample_batch_revision_snapshot_hash",
            _optional_hash(
                self.sample_batch_revision_snapshot_hash,
                "sampleBatchRevisionSnapshotHash",
            ),
        )
        if (self.sample_batch_revision_global_id is None) != (
            self.sample_batch_revision_snapshot_hash is None
        ):
            raise _problem(
                "sampleBatchRevisionGlobalId",
                _("Select one complete Sample Batch revision, or leave it empty."),
            )
        object.__setattr__(self, "defect_version", _positive(self.defect_version, "defectVersion"))
        if self.predecessor_kind is not None:
            _enum(self.predecessor_kind, TrialDefectPredecessorKind, "predecessorKind")
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        object.__setattr__(
            self,
            "predecessor_snapshot_hash",
            _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
        )
        if self.defect_version == 1:
            if any(
                value is not None
                for value in (
                    self.predecessor_kind,
                    self.predecessor_global_id,
                    self.predecessor_snapshot_hash,
                )
            ):
                raise _problem(
                    "predecessorGlobalId",
                    _("The first Trial defect revision cannot have a predecessor."),
                )
            if self.state is not ToolingDefectState.OPEN:
                raise _problem("state", _("The first Trial defect revision must be open."))
        elif any(
            value is None
            for value in (
                self.predecessor_kind,
                self.predecessor_global_id,
                self.predecessor_snapshot_hash,
            )
        ):
            raise _problem(
                "predecessorGlobalId",
                _("A Trial defect successor requires its exact predecessor."),
            )
        object.__setattr__(self, "business_code", _key(self.business_code, "businessCode"))
        object.__setattr__(self, "title", _text(self.title, "title", 255))
        object.__setattr__(self, "description", _text(self.description, "description", 4_000))
        object.__setattr__(self, "category_key", _key(self.category_key, "categoryKey"))
        object.__setattr__(self, "location", _text(self.location, "location", 255))
        _enum(self.severity, ToolingDefectSeverity, "severity")
        if type(self.blocking) is not bool:
            raise _problem("blocking", _("Blocking must be a checkbox value."))
        _enum(self.state, ToolingDefectState, "state")
        _enum(self.root_cause_state, ToolingDefectRootCauseState, "rootCauseState")
        object.__setattr__(self, "root_cause", _optional_text(self.root_cause, "rootCause", 4_000))
        if (self.root_cause_state is ToolingDefectRootCauseState.RECORDED) != (
            self.root_cause is not None
        ):
            raise _problem(
                "rootCause",
                _("Recorded root cause state requires exact root cause text."),
            )
        if self.responsible_member is not None and not isinstance(
            self.responsible_member,
            ProjectMemberResponsibility,
        ):
            raise _problem("responsibleMember", _("Select a valid Project member."))
        if self.state is not ToolingDefectState.OPEN and self.responsible_member is None:
            raise _problem(
                "responsibleMember",
                _("Assigned defect states require a responsible Project member."),
            )
        object.__setattr__(
            self,
            "occurrence_count",
            _positive(self.occurrence_count, "occurrenceCount"),
        )
        actions = _typed_tuple(
            self.actions,
            TrialDefectAction,
            "actions",
            minimum=0,
            maximum=100,
        )
        _unique((item.global_id for item in actions), "actions")
        object.__setattr__(
            self,
            "actions",
            tuple(sorted(actions, key=lambda item: str(item.global_id))),
        )
        evidence = _typed_tuple(
            self.evidence,
            TrialQualityEvidenceReference,
            "evidence",
            minimum=1,
            maximum=100,
        )
        _unique((item.global_id for item in evidence), "evidence")
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(evidence, key=lambda item: str(item.global_id))),
        )
        if self.state is ToolingDefectState.READY_FOR_VERIFICATION and not any(
            item.action_type is ToolingDefectActionType.CORRECTIVE
            and item.state is not ToolingDefectActionState.PLANNED
            for item in self.actions
        ):
            raise _problem(
                "actions",
                _("Ready for verification requires a completed corrective action."),
            )
        if self.state is ToolingDefectState.CLOSED:
            if self.root_cause_state is not ToolingDefectRootCauseState.RECORDED:
                raise _problem("rootCause", _("Closed defects require an exact root cause."))
            if not self.actions or any(
                item.state is not ToolingDefectActionState.VERIFIED for item in self.actions
            ):
                raise _problem(
                    "actions",
                    _("Closed defects require independently verified actions."),
                )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial defect snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "defectGlobalId": str(self.defect_global_id),
                "defectVersion": self.defect_version,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "defectGlobalId": str(self.defect_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "trialRoundOptimisticVersion": self.trial_round_optimistic_version,
            "trialRoundSnapshotHash": self.trial_round_snapshot_hash,
            "inputLockRevisionGlobalId": str(self.input_lock_revision_global_id),
            "inputLockRevisionSnapshotHash": self.input_lock_revision_snapshot_hash,
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "toolingSetSnapshotHash": self.tooling_set_snapshot_hash,
            "cavityGlobalId": str(self.cavity_global_id),
            "sampleBatchRevisionGlobalId": (
                str(self.sample_batch_revision_global_id)
                if self.sample_batch_revision_global_id
                else None
            ),
            "sampleBatchRevisionSnapshotHash": self.sample_batch_revision_snapshot_hash,
            "defectVersion": self.defect_version,
            "predecessorKind": self.predecessor_kind.value if self.predecessor_kind else None,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "businessCode": self.business_code,
            "title": self.title,
            "description": self.description,
            "categoryKey": self.category_key,
            "location": self.location,
            "severity": self.severity.value,
            "blocking": self.blocking,
            "state": self.state.value,
            "rootCauseState": self.root_cause_state.value,
            "rootCause": self.root_cause,
            "responsibleMember": (
                self.responsible_member.snapshot_payload() if self.responsible_member else None
            ),
            "occurrenceCount": self.occurrence_count,
            "actions": [item.snapshot_payload() for item in self.actions],
            "evidence": [item.snapshot_payload() for item in self.evidence],
            "externalEffects": {
                "ncr": "unavailable",
                "qualityInspection": "unavailable",
                "gate": "unavailable",
                "toolingLifecycle": "unavailable",
            },
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


_DEFECT_TRANSITIONS: dict[ToolingDefectState, frozenset[ToolingDefectState]] = {
    ToolingDefectState.OPEN: frozenset(
        {ToolingDefectState.OPEN, ToolingDefectState.ASSIGNED}
    ),
    ToolingDefectState.ASSIGNED: frozenset(
        {ToolingDefectState.ASSIGNED, ToolingDefectState.IN_PROGRESS}
    ),
    ToolingDefectState.IN_PROGRESS: frozenset(
        {ToolingDefectState.IN_PROGRESS, ToolingDefectState.READY_FOR_VERIFICATION}
    ),
    ToolingDefectState.READY_FOR_VERIFICATION: frozenset(
        {ToolingDefectState.READY_FOR_VERIFICATION, ToolingDefectState.CLOSED}
    ),
    ToolingDefectState.CLOSED: frozenset(
        {ToolingDefectState.CLOSED, ToolingDefectState.REOPENED}
    ),
    ToolingDefectState.REOPENED: frozenset(
        {ToolingDefectState.REOPENED, ToolingDefectState.ASSIGNED}
    ),
}

_ACTION_TRANSITIONS: dict[ToolingDefectActionState, frozenset[ToolingDefectActionState]] = {
    ToolingDefectActionState.PLANNED: frozenset({ToolingDefectActionState.COMPLETED}),
    ToolingDefectActionState.COMPLETED: frozenset({ToolingDefectActionState.VERIFIED}),
    ToolingDefectActionState.VERIFIED: frozenset(),
}


def validate_trial_defect_successor(
    predecessor: ToolingDefectRevision | TrialDefectRevision,
    successor: TrialDefectRevision,
) -> None:
    expected_kind = (
        TrialDefectPredecessorKind.TOOLING_DEFECT_REVISION
        if isinstance(predecessor, ToolingDefectRevision)
        else TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION
    )
    stable = (
        predecessor.defect_global_id == successor.defect_global_id
        and predecessor.tenant_id == successor.tenant_id
        and predecessor.project_global_id == successor.project_global_id
        and predecessor.tooling_master_global_id == successor.tooling_master_global_id
        and predecessor.business_code == successor.business_code
    )
    if (
        not stable
        or successor.defect_version != predecessor.defect_version + 1
        or successor.predecessor_kind is not expected_kind
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
        or successor.state not in _DEFECT_TRANSITIONS[predecessor.state]
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current NPI defect revision."),
        )
    if isinstance(predecessor, ToolingDefectRevision):
        if (
            predecessor.cavity_global_id is not None
            and predecessor.cavity_global_id != successor.cavity_global_id
        ):
            raise _problem("cavityGlobalId", _("The NPI defect cavity cannot be rebound."))
        return
    if predecessor.trial_round_global_id == successor.trial_round_global_id:
        same_round_fields = (
            "trial_round_optimistic_version",
            "trial_round_snapshot_hash",
            "input_lock_revision_global_id",
            "input_lock_revision_snapshot_hash",
            "tooling_revision_global_id",
            "tooling_revision_snapshot_hash",
            "tooling_set_global_id",
            "tooling_set_snapshot_hash",
            "cavity_global_id",
            "sample_batch_revision_global_id",
            "sample_batch_revision_snapshot_hash",
        )
        if any(
            getattr(predecessor, field) != getattr(successor, field)
            for field in same_round_fields
        ):
            raise _problem(
                "trialRoundGlobalId",
                _("A defect update in the same Round cannot rebind exact Trial context."),
            )
    _validate_action_successors(predecessor.actions, successor.actions)
    previous_evidence = {item.global_id: item.snapshot_hash for item in predecessor.evidence}
    successor_evidence = {item.global_id: item.snapshot_hash for item in successor.evidence}
    if any(successor_evidence.get(key) != value for key, value in previous_evidence.items()):
        raise _problem("evidence", _("A Trial defect successor cannot remove or rebind evidence."))


def _validate_action_successors(
    predecessor: tuple[TrialDefectAction, ...],
    successor: tuple[TrialDefectAction, ...],
) -> None:
    successor_by_id = {item.global_id: item for item in successor}
    for current in predecessor:
        candidate = successor_by_id.get(current.global_id)
        if candidate is None or candidate.stable_payload() != current.stable_payload():
            raise _problem(
                "actions",
                _("A Trial defect successor cannot remove or rebind an existing action."),
            )
        if candidate.state != current.state and candidate.state not in _ACTION_TRANSITIONS[current.state]:
            raise _problem("actions.state", _("Select the next supported defect action state."))


@dataclass(frozen=True, slots=True)
class TrialDefectVerificationRevision:
    global_id: UUID
    verification_global_id: UUID
    attempt_sequence: int
    tenant_id: str
    project_global_id: UUID
    defect_global_id: UUID
    defect_revision_global_id: UUID
    defect_revision_snapshot_hash: str
    action_global_id: UUID
    target_round_global_id: UUID
    target_round_optimistic_version: int
    target_round_snapshot_hash: str
    verification_round_global_id: UUID
    verification_round_optimistic_version: int
    verification_round_snapshot_hash: str
    cavity_result_revision_global_id: UUID
    cavity_result_revision_snapshot_hash: str
    verifier_member: ProjectMemberResponsibility
    result: TrialDefectVerificationResult
    finding: str
    observed_at: datetime
    evidence: tuple[TrialQualityEvidenceReference, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "verification_global_id",
            "project_global_id",
            "defect_global_id",
            "defect_revision_global_id",
            "action_global_id",
            "target_round_global_id",
            "verification_round_global_id",
            "cavity_result_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "attempt_sequence", _positive(self.attempt_sequence, "attemptSequence"))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        for fieldname in (
            "defect_revision_snapshot_hash",
            "target_round_snapshot_hash",
            "verification_round_snapshot_hash",
            "cavity_result_revision_snapshot_hash",
        ):
            object.__setattr__(self, fieldname, _hash(getattr(self, fieldname), _camel(fieldname)))
        for fieldname in (
            "target_round_optimistic_version",
            "verification_round_optimistic_version",
        ):
            object.__setattr__(self, fieldname, _positive(getattr(self, fieldname), _camel(fieldname)))
        if not isinstance(self.verifier_member, ProjectMemberResponsibility):
            raise _problem("verifierMember", _("Select a valid Project member."))
        _enum(self.result, TrialDefectVerificationResult, "result")
        object.__setattr__(self, "finding", _text(self.finding, "finding", 4_000))
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "observedAt"))
        evidence = _typed_tuple(
            self.evidence,
            TrialQualityEvidenceReference,
            "evidence",
            minimum=1,
            maximum=100,
        )
        _unique((item.global_id for item in evidence), "evidence")
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(evidence, key=lambda item: str(item.global_id))),
        )
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial defect verification snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "verificationGlobalId": str(self.verification_global_id),
                "attemptSequence": self.attempt_sequence,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "verificationGlobalId": str(self.verification_global_id),
            "attemptSequence": self.attempt_sequence,
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "defectGlobalId": str(self.defect_global_id),
            "defectRevisionGlobalId": str(self.defect_revision_global_id),
            "defectRevisionSnapshotHash": self.defect_revision_snapshot_hash,
            "actionGlobalId": str(self.action_global_id),
            "targetRoundGlobalId": str(self.target_round_global_id),
            "targetRoundOptimisticVersion": self.target_round_optimistic_version,
            "targetRoundSnapshotHash": self.target_round_snapshot_hash,
            "verificationRoundGlobalId": str(self.verification_round_global_id),
            "verificationRoundOptimisticVersion": self.verification_round_optimistic_version,
            "verificationRoundSnapshotHash": self.verification_round_snapshot_hash,
            "cavityResultRevisionGlobalId": str(self.cavity_result_revision_global_id),
            "cavityResultRevisionSnapshotHash": self.cavity_result_revision_snapshot_hash,
            "verifierMember": self.verifier_member.snapshot_payload(),
            "result": self.result.value,
            "finding": self.finding,
            "observedAt": _utc_text(self.observed_at),
            "evidence": [item.snapshot_payload() for item in self.evidence],
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_trial_defect_verification(
    defect: TrialDefectRevision,
    cavity_result: TrialCavityResultRevision,
    verification: TrialDefectVerificationRevision,
) -> None:
    action = next(
        (item for item in defect.actions if item.global_id == verification.action_global_id),
        None,
    )
    if (
        verification.tenant_id != defect.tenant_id
        or verification.project_global_id != defect.project_global_id
        or verification.defect_global_id != defect.defect_global_id
        or verification.defect_revision_global_id != defect.global_id
        or verification.defect_revision_snapshot_hash != defect.snapshot_hash
        or action is None
    ):
        raise _problem(
            "defectRevisionGlobalId",
            _("Select the exact current Trial defect action."),
        )
    if action.state is not ToolingDefectActionState.COMPLETED:
        raise _problem("actionGlobalId", _("Only a completed defect action can be verified."))
    if (
        verification.target_round_global_id != action.target_round_global_id
        or verification.target_round_optimistic_version
        != action.target_round_optimistic_version
        or verification.target_round_snapshot_hash != action.target_round_snapshot_hash
        or verification.verification_round_global_id != action.target_round_global_id
        or verification.verification_round_optimistic_version
        != action.target_round_optimistic_version
        or verification.verification_round_snapshot_hash != action.target_round_snapshot_hash
    ):
        raise _problem(
            "verificationRoundGlobalId",
            _("Select the exact target Trial Round for verification."),
        )
    if (
        cavity_result.tenant_id != defect.tenant_id
        or cavity_result.project_global_id != defect.project_global_id
        or cavity_result.trial_round_global_id != verification.verification_round_global_id
        or cavity_result.cavity_global_id != defect.cavity_global_id
        or verification.cavity_result_revision_global_id != cavity_result.global_id
        or verification.cavity_result_revision_snapshot_hash != cavity_result.snapshot_hash
    ):
        raise _problem(
            "cavityResultRevisionGlobalId",
            _("Select the exact cavity result for this verification Round."),
        )
    if any(
        item.required and item.state is TrialQualityMeasurementState.NOT_MEASURED
        for item in cavity_result.measurements
    ):
        raise _problem(
            "cavityResultRevisionGlobalId",
            _("Measure every required cavity characteristic before verification."),
        )
    if verification.verifier_member.global_id == action.responsible_member.global_id:
        raise _problem(
            "verifierMember",
            _("The verifier must differ from the action responsible member."),
        )


def cavity_result_from_snapshot(value: object) -> TrialCavityResultRevision:
    record = _record(value, "cavityResultSnapshot", _CAVITY_RESULT_KEYS)
    _schema_version(record["schemaVersion"])
    return TrialCavityResultRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        cavity_result_global_id=_uuid_text(record["cavityResultGlobalId"], "cavityResultGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        input_lock_revision_global_id=_uuid_text(record["inputLockRevisionGlobalId"], "inputLockRevisionGlobalId"),
        input_lock_revision_snapshot_hash=record["inputLockRevisionSnapshotHash"],
        sample_batch_revision_global_id=_uuid_text(record["sampleBatchRevisionGlobalId"], "sampleBatchRevisionGlobalId"),
        sample_batch_revision_snapshot_hash=record["sampleBatchRevisionSnapshotHash"],
        tooling_revision_global_id=_uuid_text(record["toolingRevisionGlobalId"], "toolingRevisionGlobalId"),
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        tooling_set_global_id=_uuid_text(record["toolingSetGlobalId"], "toolingSetGlobalId"),
        tooling_set_snapshot_hash=record["toolingSetSnapshotHash"],
        cavity_global_id=_uuid_text(record["cavityGlobalId"], "cavityGlobalId"),
        result_version=record["resultVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        measurements=tuple(
            _measurement_from_snapshot(item)
            for item in _sequence(record["measurements"], "measurements", 500)
        ),
        evidence=tuple(
            _evidence_from_snapshot(item)
            for item in _sequence(record["evidence"], "evidence", 100)
        ),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def trial_defect_from_snapshot(value: object) -> TrialDefectRevision:
    record = _record(value, "trialDefectSnapshot", _TRIAL_DEFECT_KEYS)
    _schema_version(record["schemaVersion"])
    expected_external = {
        "ncr": "unavailable",
        "qualityInspection": "unavailable",
        "gate": "unavailable",
        "toolingLifecycle": "unavailable",
    }
    if record["externalEffects"] != expected_external:
        raise _problem("externalEffects", _("External Trial quality effects are unavailable."))
    return TrialDefectRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        defect_global_id=_uuid_text(record["defectGlobalId"], "defectGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        tooling_master_global_id=_uuid_text(record["toolingMasterGlobalId"], "toolingMasterGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        trial_round_optimistic_version=record["trialRoundOptimisticVersion"],
        trial_round_snapshot_hash=record["trialRoundSnapshotHash"],
        input_lock_revision_global_id=_uuid_text(record["inputLockRevisionGlobalId"], "inputLockRevisionGlobalId"),
        input_lock_revision_snapshot_hash=record["inputLockRevisionSnapshotHash"],
        tooling_revision_global_id=_uuid_text(record["toolingRevisionGlobalId"], "toolingRevisionGlobalId"),
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        tooling_set_global_id=_uuid_text(record["toolingSetGlobalId"], "toolingSetGlobalId"),
        tooling_set_snapshot_hash=record["toolingSetSnapshotHash"],
        cavity_global_id=_uuid_text(record["cavityGlobalId"], "cavityGlobalId"),
        sample_batch_revision_global_id=_optional_uuid_text(record["sampleBatchRevisionGlobalId"], "sampleBatchRevisionGlobalId"),
        sample_batch_revision_snapshot_hash=record["sampleBatchRevisionSnapshotHash"],
        defect_version=record["defectVersion"],
        predecessor_kind=(
            None
            if record["predecessorKind"] is None
            else _enum_text(record["predecessorKind"], TrialDefectPredecessorKind, "predecessorKind")
        ),
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        business_code=record["businessCode"],
        title=record["title"],
        description=record["description"],
        category_key=record["categoryKey"],
        location=record["location"],
        severity=_enum_text(record["severity"], ToolingDefectSeverity, "severity"),
        blocking=record["blocking"],
        state=_enum_text(record["state"], ToolingDefectState, "state"),
        root_cause_state=_enum_text(record["rootCauseState"], ToolingDefectRootCauseState, "rootCauseState"),
        root_cause=record["rootCause"],
        responsible_member=(
            None
            if record["responsibleMember"] is None
            else _member_from_snapshot(record["responsibleMember"], "responsibleMember")
        ),
        occurrence_count=record["occurrenceCount"],
        actions=tuple(
            _action_from_snapshot(item)
            for item in _sequence(record["actions"], "actions", 100)
        ),
        evidence=tuple(
            _evidence_from_snapshot(item)
            for item in _sequence(record["evidence"], "evidence", 100)
        ),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def verification_from_snapshot(value: object) -> TrialDefectVerificationRevision:
    record = _record(value, "verificationSnapshot", _VERIFICATION_KEYS)
    _schema_version(record["schemaVersion"])
    return TrialDefectVerificationRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        verification_global_id=_uuid_text(record["verificationGlobalId"], "verificationGlobalId"),
        attempt_sequence=record["attemptSequence"],
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        defect_global_id=_uuid_text(record["defectGlobalId"], "defectGlobalId"),
        defect_revision_global_id=_uuid_text(record["defectRevisionGlobalId"], "defectRevisionGlobalId"),
        defect_revision_snapshot_hash=record["defectRevisionSnapshotHash"],
        action_global_id=_uuid_text(record["actionGlobalId"], "actionGlobalId"),
        target_round_global_id=_uuid_text(record["targetRoundGlobalId"], "targetRoundGlobalId"),
        target_round_optimistic_version=record["targetRoundOptimisticVersion"],
        target_round_snapshot_hash=record["targetRoundSnapshotHash"],
        verification_round_global_id=_uuid_text(record["verificationRoundGlobalId"], "verificationRoundGlobalId"),
        verification_round_optimistic_version=record["verificationRoundOptimisticVersion"],
        verification_round_snapshot_hash=record["verificationRoundSnapshotHash"],
        cavity_result_revision_global_id=_uuid_text(record["cavityResultRevisionGlobalId"], "cavityResultRevisionGlobalId"),
        cavity_result_revision_snapshot_hash=record["cavityResultRevisionSnapshotHash"],
        verifier_member=_member_from_snapshot(record["verifierMember"], "verifierMember"),
        result=_enum_text(record["result"], TrialDefectVerificationResult, "result"),
        finding=record["finding"],
        observed_at=_datetime_text(record["observedAt"], "observedAt"),
        evidence=tuple(
            _evidence_from_snapshot(item)
            for item in _sequence(record["evidence"], "evidence", 100)
        ),
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


_CAVITY_RESULT_KEYS = {
    "schemaVersion", "globalId", "cavityResultGlobalId", "tenantId",
    "projectGlobalId", "trialRoundGlobalId", "inputLockRevisionGlobalId",
    "inputLockRevisionSnapshotHash", "sampleBatchRevisionGlobalId",
    "sampleBatchRevisionSnapshotHash", "toolingRevisionGlobalId",
    "toolingRevisionSnapshotHash", "toolingSetGlobalId", "toolingSetSnapshotHash",
    "cavityGlobalId", "resultVersion", "predecessorGlobalId",
    "predecessorSnapshotHash", "measurements", "evidence", "reason",
    "createdByUserId", "createdAt", "requestId", "traceId",
}

_TRIAL_DEFECT_KEYS = {
    "schemaVersion", "globalId", "defectGlobalId", "tenantId", "projectGlobalId",
    "toolingMasterGlobalId", "trialRoundGlobalId", "trialRoundOptimisticVersion",
    "trialRoundSnapshotHash", "inputLockRevisionGlobalId",
    "inputLockRevisionSnapshotHash", "toolingRevisionGlobalId",
    "toolingRevisionSnapshotHash", "toolingSetGlobalId", "toolingSetSnapshotHash",
    "cavityGlobalId", "sampleBatchRevisionGlobalId",
    "sampleBatchRevisionSnapshotHash", "defectVersion", "predecessorKind",
    "predecessorGlobalId", "predecessorSnapshotHash", "businessCode", "title",
    "description", "categoryKey", "location", "severity", "blocking", "state",
    "rootCauseState", "rootCause", "responsibleMember", "occurrenceCount", "actions",
    "evidence", "externalEffects", "reason", "createdByUserId", "createdAt",
    "requestId", "traceId",
}

_VERIFICATION_KEYS = {
    "schemaVersion", "globalId", "verificationGlobalId", "attemptSequence",
    "tenantId", "projectGlobalId", "defectGlobalId", "defectRevisionGlobalId",
    "defectRevisionSnapshotHash", "actionGlobalId", "targetRoundGlobalId",
    "targetRoundOptimisticVersion", "targetRoundSnapshotHash",
    "verificationRoundGlobalId", "verificationRoundOptimisticVersion",
    "verificationRoundSnapshotHash", "cavityResultRevisionGlobalId",
    "cavityResultRevisionSnapshotHash", "verifierMember", "result", "finding",
    "observedAt", "evidence", "createdByUserId", "createdAt", "requestId",
    "traceId",
}


def _measurement_from_snapshot(value: object) -> TrialCavityMeasurement:
    record = _record(
        value,
        "measurements",
        {
            "characteristicKey", "label", "unit", "nominalValue", "lowerLimit",
            "upperLimit", "required", "state", "value", "comparisonState",
            "source", "observedAt", "observedByUserId",
        },
    )
    result = TrialCavityMeasurement(
        characteristic_key=record["characteristicKey"],
        label=record["label"],
        unit=record["unit"],
        nominal_value=record["nominalValue"],
        lower_limit=record["lowerLimit"],
        upper_limit=record["upperLimit"],
        required=record["required"],
        state=_enum_text(record["state"], TrialQualityMeasurementState, "measurements.state"),
        value=record["value"],
        source=_enum_text(record["source"], TrialQualityObservationSource, "measurements.source"),
        observed_at=_datetime_text(record["observedAt"], "measurements.observedAt"),
        observed_by_user_id=record["observedByUserId"],
    )
    if record["comparisonState"] != result.comparison_state.value:
        raise _problem(
            "measurements.comparisonState",
            _("The cavity measurement comparison state does not match."),
        )
    return result


def _evidence_from_snapshot(value: object) -> TrialQualityEvidenceReference:
    record = _record(value, "evidence", {"globalId", "snapshotHash"})
    return TrialQualityEvidenceReference(
        global_id=_uuid_text(record["globalId"], "evidence.globalId"),
        snapshot_hash=record["snapshotHash"],
    )


def _action_from_snapshot(value: object) -> TrialDefectAction:
    record = _record(
        value,
        "actions",
        {
            "globalId", "actionType", "state", "detail", "responsibleMember",
            "dueDate", "targetRoundGlobalId", "targetRoundOptimisticVersion",
            "targetRoundSnapshotHash", "verificationRevisionGlobalId",
            "verificationRevisionSnapshotHash",
        },
    )
    return TrialDefectAction(
        global_id=_uuid_text(record["globalId"], "actions.globalId"),
        action_type=_enum_text(record["actionType"], ToolingDefectActionType, "actions.actionType"),
        state=_enum_text(record["state"], ToolingDefectActionState, "actions.state"),
        detail=record["detail"],
        responsible_member=_member_from_snapshot(record["responsibleMember"], "actions.responsibleMember"),
        due_date=_date_text(record["dueDate"], "actions.dueDate"),
        target_round_global_id=_uuid_text(record["targetRoundGlobalId"], "actions.targetRoundGlobalId"),
        target_round_optimistic_version=record["targetRoundOptimisticVersion"],
        target_round_snapshot_hash=record["targetRoundSnapshotHash"],
        verification_revision_global_id=_optional_uuid_text(record["verificationRevisionGlobalId"], "actions.verificationRevisionGlobalId"),
        verification_revision_snapshot_hash=record["verificationRevisionSnapshotHash"],
    )


def _member_from_snapshot(value: object, path: str) -> ProjectMemberResponsibility:
    record = _record(value, path, {"globalId", "userId", "optimisticVersion"})
    return ProjectMemberResponsibility(
        global_id=_uuid_text(record["globalId"], f"{path}.globalId"),
        user_id=record["userId"],
        optimistic_version=record["optimisticVersion"],
    )


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
        raise _problem(path, _("Enter a valid global ID."))
    return value


def _uuid_text(value: object, path: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _problem(path, _("Enter a valid global ID.")) from error


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _optional_uuid_text(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid_text(value, path)


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _problem(path, _("Enter a shorter value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _key(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if not normalized[0].isalnum() or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:@/-"
        for character in normalized
    ):
        raise _problem(path, _("Enter a valid value."))
    return normalized


def _actor(value: object, path: str) -> str:
    normalized = _text(value, path, 254).casefold()
    if any(character.isspace() or ord(character) < 32 for character in normalized):
        raise _problem(path, _("Enter a valid user ID."))
    return normalized


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _hash(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _decimal(value: object, path: str) -> str:
    normalized = _text(value, path, 64)
    try:
        parsed = Decimal(normalized)
    except InvalidOperation as error:
        raise _problem(path, _("Enter a valid numeric value.")) from error
    if not parsed.is_finite():
        raise _problem(path, _("Enter a valid numeric value."))
    return format(parsed.normalize(), "f")


def _aware(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a valid date and time."))
    return value.astimezone(UTC)


def _datetime_text(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise _problem(path, _("Enter a valid date and time."))
    try:
        return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")), path)
    except ValueError as error:
        raise _problem(path, _("Enter a valid date and time.")) from error


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _date(value: object, path: str) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise _problem(path, _("Enter a valid date."))
    return value


def _date_text(value: object, path: str) -> date:
    if not isinstance(value, str):
        raise _problem(path, _("Enter a valid date."))
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _problem(path, _("Enter a valid date.")) from error


def _enum(value: object, enum_type: type[StrEnum], path: str) -> StrEnum:
    if not isinstance(value, enum_type):
        raise _problem(path, _("Select a supported value."))
    return value


def _enum_text(value: object, enum_type: type[StrEnum], path: str) -> StrEnum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Select a supported value.")) from error


def _record(value: object, path: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _problem(path, _("Enter a valid closed object."))
    return value


def _sequence(value: object, path: str, maximum: int) -> Sequence[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > maximum
    ):
        raise _problem(path, _("Enter a valid list."))
    return value


def _typed_tuple(
    value: object,
    item_type: type,
    path: str,
    *,
    minimum: int,
    maximum: int,
) -> tuple:
    if not isinstance(value, tuple) or not minimum <= len(value) <= maximum:
        raise _problem(path, _("Enter a valid list."))
    if any(not isinstance(item, item_type) for item in value):
        raise _problem(path, _("Enter a valid list."))
    return value


def _unique(values: Sequence[object] | object, path: str) -> None:
    items = tuple(values)  # type: ignore[arg-type]
    if len(set(items)) != len(items):
        raise _problem(path, _("Values must be unique."))


def _require_predecessor(
    version: int,
    predecessor_global_id: UUID | None,
    predecessor_snapshot_hash: str | None,
    path: str,
) -> None:
    if version == 1:
        if predecessor_global_id is not None or predecessor_snapshot_hash is not None:
            raise _problem(path, _("The first revision cannot have a predecessor."))
    elif predecessor_global_id is None or predecessor_snapshot_hash is None:
        raise _problem(path, _("A successor requires its exact predecessor."))


def _schema_version(value: object) -> None:
    if value != TRIAL_SCHEMA_VERSION:
        raise _problem("schemaVersion", _("Select a supported schema version."))


def _set_snapshot_hash(instance: object, supplied: str, payload: object, message: str) -> None:
    expected = sha256_json(payload)
    if supplied and _hash(supplied, "snapshotHash") != expected:
        raise _problem("snapshotHash", message)
    object.__setattr__(instance, "snapshot_hash", expected)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)
