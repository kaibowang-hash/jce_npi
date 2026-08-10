from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping, Sequence
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


TRIAL_SCHEMA_VERSION = 1
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ROUND_LABEL_PATTERN = re.compile(r"^T(?:0|[1-9][0-9]{0,3})$")
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class TrialPurpose(StrEnum):
    FIRST_TRIAL = "first_trial"
    TOOLING_CHANGE_VERIFICATION = "tooling_change_verification"
    DESIGN_VERIFICATION = "design_verification"
    MATERIAL_COLOR_VERIFICATION = "material_color_verification"
    CAPABILITY_STUDY = "capability_study"
    CUSTOMER_SAMPLE = "customer_sample"
    OTHER = "other"


class TrialResourceKind(StrEnum):
    MACHINE = "machine"
    AUXILIARY_EQUIPMENT = "auxiliary_equipment"
    MATERIAL = "material"


class TrialResourceSource(StrEnum):
    NPI_ONE = "NPI_ONE"
    ERPNEXT = "ERPNEXT"


class TrialRoundState(StrEnum):
    PLANNED = "planned"
    PREPARED = "prepared"
    RUNNING = "running"
    ANALYSIS = "analysis"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class TrialLifecycleEventType(StrEnum):
    CREATED = "created"
    CANCELLED = "cancelled"


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
        raise _problem(path, _("Enter a valid global ID."))
    return value


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _problem(path, _("Enter a shorter value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return _text(value, path, maximum)


def _key(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if _KEY_PATTERN.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid value."))
    return normalized


def _actor(value: object, path: str) -> str:
    if not isinstance(value, str) or _ACTOR_PATTERN.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid value."))
    return value


def _email(value: object, path: str) -> str:
    normalized = _text(value, path, 254).casefold()
    if _EMAIL_PATTERN.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid email address."))
    return normalized


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _problem(path, _("Enter zero or a positive integer."))
    return value


def _aware(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a valid date and time."))
    return value.astimezone(UTC)


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _enum(value: object, enum_type: type[StrEnum], path: str) -> StrEnum:
    if not isinstance(value, enum_type):
        raise _problem(path, _("Select a supported value."))
    return value


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class TrialResourceProposal:
    global_id: UUID
    kind: TrialResourceKind
    source_system: TrialResourceSource
    source_object_id: str
    label: str
    quantity: int | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "resources.globalId"))
        _enum(self.kind, TrialResourceKind, "resources.kind")
        _enum(self.source_system, TrialResourceSource, "resources.sourceSystem")
        object.__setattr__(
            self,
            "source_object_id",
            _key(self.source_object_id, "resources.sourceObjectId"),
        )
        object.__setattr__(self, "label", _text(self.label, "resources.label", 140))
        if (self.quantity is None) != (self.unit is None):
            raise _problem(
                "resources.quantity",
                _("Enter both the planned quantity and unit, or leave both empty."),
            )
        if self.quantity is not None:
            object.__setattr__(
                self,
                "quantity",
                _positive(self.quantity, "resources.quantity"),
            )
            object.__setattr__(self, "unit", _text(self.unit, "resources.unit", 32))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "kind": self.kind.value,
            "sourceSystem": self.source_system.value,
            "sourceObjectId": self.source_object_id,
            "label": self.label,
            "quantity": self.quantity,
            "unit": self.unit,
            "bookingState": "unavailable",
        }


@dataclass(frozen=True, slots=True)
class TrialProjectMemberReference:
    global_id: UUID
    user_id: str
    optimistic_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "members.globalId"))
        object.__setattr__(self, "user_id", _email(self.user_id, "members.userId"))
        object.__setattr__(
            self,
            "optimistic_version",
            _positive(self.optimistic_version, "members.optimisticVersion"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "userId": self.user_id,
            "optimisticVersion": self.optimistic_version,
        }


@dataclass(frozen=True, slots=True)
class TrialMeasurementPlanIntent:
    description: str | None = None
    document_revision_global_id: UUID | None = None
    document_revision_snapshot_hash: str | None = None
    document_optimistic_version: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "description",
            _optional_text(self.description, "measurementPlan.description", 1000),
        )
        supplied = (
            self.document_revision_global_id,
            self.document_revision_snapshot_hash,
            self.document_optimistic_version,
        )
        if any(value is not None for value in supplied):
            if not all(value is not None for value in supplied):
                raise _problem(
                    "measurementPlan.documentRevisionGlobalId",
                    _("Select one complete controlled document revision."),
                )
            object.__setattr__(
                self,
                "document_revision_global_id",
                _uuid(
                    self.document_revision_global_id,
                    "measurementPlan.documentRevisionGlobalId",
                ),
            )
            object.__setattr__(
                self,
                "document_revision_snapshot_hash",
                _hash(
                    self.document_revision_snapshot_hash,
                    "measurementPlan.documentRevisionSnapshotHash",
                ),
            )
            object.__setattr__(
                self,
                "document_optimistic_version",
                _positive(
                    self.document_optimistic_version,
                    "measurementPlan.documentOptimisticVersion",
                ),
            )
        if self.description is None and self.document_revision_global_id is None:
            raise _problem(
                "measurementPlan",
                _("Enter a measurement plan or select a controlled document revision."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "description": self.description,
            "documentRevisionGlobalId": (
                str(self.document_revision_global_id)
                if self.document_revision_global_id is not None
                else None
            ),
            "documentRevisionSnapshotHash": self.document_revision_snapshot_hash,
            "documentOptimisticVersion": self.document_optimistic_version,
            "lockState": "planning_intent_only",
        }


@dataclass(frozen=True, slots=True)
class TrialPlanRevision:
    global_id: UUID
    plan_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    plan_version: int
    purpose: TrialPurpose
    objective: str
    planned_start_at: datetime
    planned_end_at: datetime
    resources: tuple[TrialResourceProposal, ...]
    responsible_members: tuple[TrialProjectMemberReference, ...]
    sample_quantity: int
    measurement_plan: TrialMeasurementPlanIntent
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    predecessor_global_id: UUID | None = None
    predecessor_snapshot_hash: str | None = None
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "plan_global_id",
            "project_global_id",
            "tooling_master_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "plan_version", _positive(self.plan_version, "planVersion"))
        _enum(self.purpose, TrialPurpose, "purpose")
        object.__setattr__(self, "objective", _text(self.objective, "objective", 2000))
        object.__setattr__(
            self,
            "planned_start_at",
            _aware(self.planned_start_at, "plannedStartAt"),
        )
        object.__setattr__(
            self,
            "planned_end_at",
            _aware(self.planned_end_at, "plannedEndAt"),
        )
        if self.planned_end_at <= self.planned_start_at:
            raise _problem("plannedEndAt", _("The planned end must be after the start."))
        resources = tuple(self.resources)
        if not resources or len(resources) > 50 or any(
            not isinstance(value, TrialResourceProposal) for value in resources
        ):
            raise _problem("resources", _("Add between 1 and 50 valid resources."))
        if len({value.global_id for value in resources}) != len(resources):
            raise _problem("resources", _("Resource proposal IDs must be unique."))
        resource_kinds = {value.kind for value in resources}
        if not {TrialResourceKind.MACHINE, TrialResourceKind.MATERIAL}.issubset(
            resource_kinds
        ):
            raise _problem(
                "resources",
                _("Select a machine and material for the Trial Plan."),
            )
        members = tuple(self.responsible_members)
        if not members or len(members) > 50 or any(
            not isinstance(value, TrialProjectMemberReference) for value in members
        ):
            raise _problem("responsibleMembers", _("Select valid responsible Project members."))
        if len({value.global_id for value in members}) != len(members):
            raise _problem("responsibleMembers", _("Responsible Project members must be unique."))
        object.__setattr__(self, "resources", tuple(sorted(resources, key=lambda value: str(value.global_id))))
        object.__setattr__(self, "responsible_members", tuple(sorted(members, key=lambda value: str(value.global_id))))
        object.__setattr__(self, "sample_quantity", _positive(self.sample_quantity, "sampleQuantity"))
        if not isinstance(self.measurement_plan, TrialMeasurementPlanIntent):
            raise _problem("measurementPlan", _("Enter a valid measurement plan."))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        if self.predecessor_snapshot_hash is not None:
            object.__setattr__(
                self,
                "predecessor_snapshot_hash",
                _hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
            )
        if self.plan_version == 1:
            if self.predecessor_global_id is not None or self.predecessor_snapshot_hash is not None:
                raise _problem("predecessorGlobalId", _("The first Trial Plan revision cannot have a predecessor."))
        elif self.predecessor_global_id is None or self.predecessor_snapshot_hash is None:
            raise _problem("predecessorGlobalId", _("A successor Trial Plan revision requires its exact predecessor."))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _problem("snapshotHash", _("The Trial Plan snapshot hash does not match."))
        object.__setattr__(self, "snapshot_hash", expected)

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {"planGlobalId": str(self.plan_global_id), "planVersion": self.plan_version}
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "planGlobalId": str(self.plan_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "planVersion": self.plan_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "purpose": self.purpose.value,
            "objective": self.objective,
            "plannedStartAt": _utc_text(self.planned_start_at),
            "plannedEndAt": _utc_text(self.planned_end_at),
            "resources": [value.snapshot_payload() for value in self.resources],
            "responsibleMembers": [value.snapshot_payload() for value in self.responsible_members],
            "sampleQuantity": self.sample_quantity,
            "measurementPlan": self.measurement_plan.snapshot_payload(),
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_trial_plan_successor(
    predecessor: TrialPlanRevision,
    successor: TrialPlanRevision,
) -> None:
    if (
        successor.plan_global_id != predecessor.plan_global_id
        or successor.tenant_id != predecessor.tenant_id
        or successor.project_global_id != predecessor.project_global_id
        or successor.tooling_master_global_id != predecessor.tooling_master_global_id
        or successor.plan_version != predecessor.plan_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Trial Plan revision."),
        )


@dataclass(frozen=True, slots=True)
class TrialRoundLifecycleEvent:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    event_version: int
    event_type: TrialLifecycleEventType
    from_state: TrialRoundState | None
    to_state: TrialRoundState
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "project_global_id", "trial_round_global_id", "request_id"):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "event_version", _positive(self.event_version, "eventVersion"))
        _enum(self.event_type, TrialLifecycleEventType, "eventType")
        if self.from_state is not None:
            _enum(self.from_state, TrialRoundState, "fromState")
        _enum(self.to_state, TrialRoundState, "toState")
        if self.event_type is TrialLifecycleEventType.CREATED:
            if self.event_version != 1 or self.from_state is not None or self.to_state is not TrialRoundState.PLANNED:
                raise _problem("eventType", _("A Trial Round creation event must establish planned state."))
        elif (
            self.from_state is not TrialRoundState.PLANNED
            or self.to_state is not TrialRoundState.CANCELLED
        ):
            raise _problem("eventType", _("This Trial lifecycle transition is not active in this task."))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _problem("snapshotHash", _("The Trial lifecycle event hash does not match."))
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "eventVersion": self.event_version,
            "eventType": self.event_type.value,
            "fromState": self.from_state.value if self.from_state else None,
            "toState": self.to_state.value,
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class TrialRound:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_plan_global_id: UUID
    trial_plan_revision_global_id: UUID
    trial_plan_revision_snapshot_hash: str
    tooling_master_global_id: UUID
    round_sequence: int
    display_label: str
    purpose: TrialPurpose
    planned_start_at: datetime
    planned_end_at: datetime
    current_state: TrialRoundState
    current_event_global_id: UUID
    optimistic_version: int
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id", "project_global_id", "trial_plan_global_id",
            "trial_plan_revision_global_id", "tooling_master_global_id",
            "current_event_global_id", "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "trial_plan_revision_snapshot_hash",
            _hash(self.trial_plan_revision_snapshot_hash, "trialPlanRevisionSnapshotHash"),
        )
        object.__setattr__(self, "round_sequence", _nonnegative(self.round_sequence, "roundSequence"))
        label = _text(self.display_label, "displayLabel", 16).upper()
        if _ROUND_LABEL_PATTERN.fullmatch(label) is None:
            raise _problem("displayLabel", _("Enter a Trial Round label such as T0 or T1."))
        object.__setattr__(self, "display_label", label)
        _enum(self.purpose, TrialPurpose, "purpose")
        object.__setattr__(self, "planned_start_at", _aware(self.planned_start_at, "plannedStartAt"))
        object.__setattr__(self, "planned_end_at", _aware(self.planned_end_at, "plannedEndAt"))
        if self.planned_end_at <= self.planned_start_at:
            raise _problem("plannedEndAt", _("The planned end must be after the start."))
        _enum(self.current_state, TrialRoundState, "currentState")
        if self.current_state not in {
            TrialRoundState.PLANNED,
            TrialRoundState.CANCELLED,
        }:
            raise _problem(
                "currentState",
                _("This Trial Round state is not active in this task."),
            )
        object.__setattr__(self, "optimistic_version", _positive(self.optimistic_version, "optimisticVersion"))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _problem("snapshotHash", _("The Trial Round snapshot hash does not match."))
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialPlanGlobalId": str(self.trial_plan_global_id),
            "trialPlanRevisionGlobalId": str(self.trial_plan_revision_global_id),
            "trialPlanRevisionSnapshotHash": self.trial_plan_revision_snapshot_hash,
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "roundSequence": self.round_sequence,
            "displayLabel": self.display_label,
            "purpose": self.purpose.value,
            "plannedStartAt": _utc_text(self.planned_start_at),
            "plannedEndAt": _utc_text(self.planned_end_at),
            "currentState": self.current_state.value,
            "currentEventGlobalId": str(self.current_event_global_id),
            "optimisticVersion": self.optimistic_version,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def create_planned_trial_round(
    *,
    global_id: UUID,
    event_global_id: UUID,
    plan: TrialPlanRevision,
    round_sequence: int,
    display_label: str,
    reason: str,
    created_by_user_id: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> tuple[TrialRound, TrialRoundLifecycleEvent]:
    event = TrialRoundLifecycleEvent(
        global_id=event_global_id,
        tenant_id=plan.tenant_id,
        project_global_id=plan.project_global_id,
        trial_round_global_id=global_id,
        event_version=1,
        event_type=TrialLifecycleEventType.CREATED,
        from_state=None,
        to_state=TrialRoundState.PLANNED,
        reason=reason,
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        request_id=request_id,
        trace_id=trace_id,
    )
    trial_round = TrialRound(
        global_id=global_id,
        tenant_id=plan.tenant_id,
        project_global_id=plan.project_global_id,
        trial_plan_global_id=plan.plan_global_id,
        trial_plan_revision_global_id=plan.global_id,
        trial_plan_revision_snapshot_hash=plan.snapshot_hash,
        tooling_master_global_id=plan.tooling_master_global_id,
        round_sequence=round_sequence,
        display_label=display_label,
        purpose=plan.purpose,
        planned_start_at=plan.planned_start_at,
        planned_end_at=plan.planned_end_at,
        current_state=TrialRoundState.PLANNED,
        current_event_global_id=event.global_id,
        optimistic_version=1,
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        request_id=request_id,
        trace_id=trace_id,
    )
    return trial_round, event


@dataclass(frozen=True, slots=True)
class TrialPlanWorkLink:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_plan_global_id: UUID
    trial_plan_revision_global_id: UUID
    trial_plan_revision_snapshot_hash: str
    domain_work_item_global_id: UUID
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    trial_round_global_id: UUID | None = None
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id", "project_global_id", "trial_plan_global_id",
            "trial_plan_revision_global_id", "domain_work_item_global_id", "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "trial_plan_revision_snapshot_hash",
            _hash(self.trial_plan_revision_snapshot_hash, "trialPlanRevisionSnapshotHash"),
        )
        object.__setattr__(
            self,
            "trial_round_global_id",
            _optional_uuid(self.trial_round_global_id, "trialRoundGlobalId"),
        )
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _problem("snapshotHash", _("The Trial work link hash does not match."))
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialPlanGlobalId": str(self.trial_plan_global_id),
            "trialPlanRevisionGlobalId": str(self.trial_plan_revision_global_id),
            "trialPlanRevisionSnapshotHash": self.trial_plan_revision_snapshot_hash,
            "trialRoundGlobalId": str(self.trial_round_global_id) if self.trial_round_global_id else None,
            "domainWorkItemGlobalId": str(self.domain_work_item_global_id),
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def trial_plan_from_snapshot(value: object) -> TrialPlanRevision:
    record = _record(
        value,
        "planSnapshot",
        {
            "schemaVersion",
            "globalId",
            "planGlobalId",
            "tenantId",
            "projectGlobalId",
            "toolingMasterGlobalId",
            "planVersion",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "purpose",
            "objective",
            "plannedStartAt",
            "plannedEndAt",
            "resources",
            "responsibleMembers",
            "sampleQuantity",
            "measurementPlan",
            "reason",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    resources_value = _sequence(record["resources"], "resources", maximum=50)
    members_value = _sequence(
        record["responsibleMembers"],
        "responsibleMembers",
        maximum=50,
    )
    measurement = _record(
        record["measurementPlan"],
        "measurementPlan",
        {
            "description",
            "documentRevisionGlobalId",
            "documentRevisionSnapshotHash",
            "documentOptimisticVersion",
            "lockState",
        },
    )
    if measurement["lockState"] != "planning_intent_only":
        raise _problem("measurementPlan.lockState", _("Select a supported value."))

    resources: list[TrialResourceProposal] = []
    for entry in resources_value:
        item = _record(
            entry,
            "resources",
            {
                "globalId",
                "kind",
                "sourceSystem",
                "sourceObjectId",
                "label",
                "quantity",
                "unit",
                "bookingState",
            },
        )
        if item["bookingState"] != "unavailable":
            raise _problem("resources.bookingState", _("Select a supported value."))
        resources.append(
            TrialResourceProposal(
                global_id=_uuid_text(item["globalId"], "resources.globalId"),
                kind=_enum_text(item["kind"], TrialResourceKind, "resources.kind"),
                source_system=_enum_text(
                    item["sourceSystem"],
                    TrialResourceSource,
                    "resources.sourceSystem",
                ),
                source_object_id=item["sourceObjectId"],
                label=item["label"],
                quantity=item["quantity"],
                unit=item["unit"],
            )
        )

    members: list[TrialProjectMemberReference] = []
    for entry in members_value:
        item = _record(
            entry,
            "responsibleMembers",
            {"globalId", "userId", "optimisticVersion"},
        )
        members.append(
            TrialProjectMemberReference(
                global_id=_uuid_text(item["globalId"], "members.globalId"),
                user_id=item["userId"],
                optimistic_version=item["optimisticVersion"],
            )
        )
    return TrialPlanRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        plan_global_id=_uuid_text(record["planGlobalId"], "planGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        tooling_master_global_id=_uuid_text(
            record["toolingMasterGlobalId"],
            "toolingMasterGlobalId",
        ),
        plan_version=record["planVersion"],
        predecessor_global_id=_optional_uuid_text(
            record["predecessorGlobalId"],
            "predecessorGlobalId",
        ),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        purpose=_enum_text(record["purpose"], TrialPurpose, "purpose"),
        objective=record["objective"],
        planned_start_at=_datetime_text(record["plannedStartAt"], "plannedStartAt"),
        planned_end_at=_datetime_text(record["plannedEndAt"], "plannedEndAt"),
        resources=tuple(resources),
        responsible_members=tuple(members),
        sample_quantity=record["sampleQuantity"],
        measurement_plan=TrialMeasurementPlanIntent(
            description=measurement["description"],
            document_revision_global_id=_optional_uuid_text(
                measurement["documentRevisionGlobalId"],
                "measurementPlan.documentRevisionGlobalId",
            ),
            document_revision_snapshot_hash=measurement[
                "documentRevisionSnapshotHash"
            ],
            document_optimistic_version=measurement["documentOptimisticVersion"],
        ),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def trial_round_from_snapshot(value: object) -> TrialRound:
    record = _record(
        value,
        "roundSnapshot",
        {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "trialPlanGlobalId",
            "trialPlanRevisionGlobalId",
            "trialPlanRevisionSnapshotHash",
            "toolingMasterGlobalId",
            "roundSequence",
            "displayLabel",
            "purpose",
            "plannedStartAt",
            "plannedEndAt",
            "currentState",
            "currentEventGlobalId",
            "optimisticVersion",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return TrialRound(
        global_id=_uuid_text(record["globalId"], "globalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_plan_global_id=_uuid_text(
            record["trialPlanGlobalId"],
            "trialPlanGlobalId",
        ),
        trial_plan_revision_global_id=_uuid_text(
            record["trialPlanRevisionGlobalId"],
            "trialPlanRevisionGlobalId",
        ),
        trial_plan_revision_snapshot_hash=record["trialPlanRevisionSnapshotHash"],
        tooling_master_global_id=_uuid_text(
            record["toolingMasterGlobalId"],
            "toolingMasterGlobalId",
        ),
        round_sequence=record["roundSequence"],
        display_label=record["displayLabel"],
        purpose=_enum_text(record["purpose"], TrialPurpose, "purpose"),
        planned_start_at=_datetime_text(record["plannedStartAt"], "plannedStartAt"),
        planned_end_at=_datetime_text(record["plannedEndAt"], "plannedEndAt"),
        current_state=_enum_text(
            record["currentState"],
            TrialRoundState,
            "currentState",
        ),
        current_event_global_id=_uuid_text(
            record["currentEventGlobalId"],
            "currentEventGlobalId",
        ),
        optimistic_version=record["optimisticVersion"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def trial_event_from_snapshot(value: object) -> TrialRoundLifecycleEvent:
    record = _record(
        value,
        "eventSnapshot",
        {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "trialRoundGlobalId",
            "eventVersion",
            "eventType",
            "fromState",
            "toState",
            "reason",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return TrialRoundLifecycleEvent(
        global_id=_uuid_text(record["globalId"], "globalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(
            record["trialRoundGlobalId"],
            "trialRoundGlobalId",
        ),
        event_version=record["eventVersion"],
        event_type=_enum_text(
            record["eventType"],
            TrialLifecycleEventType,
            "eventType",
        ),
        from_state=(
            None
            if record["fromState"] is None
            else _enum_text(record["fromState"], TrialRoundState, "fromState")
        ),
        to_state=_enum_text(record["toState"], TrialRoundState, "toState"),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def trial_work_link_from_snapshot(value: object) -> TrialPlanWorkLink:
    record = _record(
        value,
        "linkSnapshot",
        {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "trialPlanGlobalId",
            "trialPlanRevisionGlobalId",
            "trialPlanRevisionSnapshotHash",
            "trialRoundGlobalId",
            "domainWorkItemGlobalId",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return TrialPlanWorkLink(
        global_id=_uuid_text(record["globalId"], "globalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_plan_global_id=_uuid_text(
            record["trialPlanGlobalId"],
            "trialPlanGlobalId",
        ),
        trial_plan_revision_global_id=_uuid_text(
            record["trialPlanRevisionGlobalId"],
            "trialPlanRevisionGlobalId",
        ),
        trial_plan_revision_snapshot_hash=record["trialPlanRevisionSnapshotHash"],
        trial_round_global_id=_optional_uuid_text(
            record["trialRoundGlobalId"],
            "trialRoundGlobalId",
        ),
        domain_work_item_global_id=_uuid_text(
            record["domainWorkItemGlobalId"],
            "domainWorkItemGlobalId",
        ),
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


def _record(value: object, path: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _problem(path, _("Enter a valid closed object."))
    return value


def _sequence(value: object, path: str, *, maximum: int) -> Sequence[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > maximum
    ):
        raise _problem(path, _("Enter a valid list."))
    return value


def _schema_version(value: object) -> None:
    if value != TRIAL_SCHEMA_VERSION:
        raise _problem("schemaVersion", _("Select a supported schema version."))


def _uuid_text(value: object, path: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _problem(path, _("Enter a valid global ID.")) from error


def _optional_uuid_text(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid_text(value, path)


def _datetime_text(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise _problem(path, _("Enter a valid date and time."))
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _problem(path, _("Enter a valid date and time.")) from error
    return _aware(parsed, path)


def _enum_text(value: object, enum_type: type[StrEnum], path: str):
    try:
        return enum_type(str(value))
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Select a supported value.")) from error
