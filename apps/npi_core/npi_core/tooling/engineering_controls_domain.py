from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import TOOLING_SCHEMA_VERSION, sha256_json
from npi_core.tooling.manufacturing_domain import (
    ProjectMemberResponsibility,
    ReleasedDocumentEvidence,
)

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CONTENT_HASH_PATTERN = re.compile(r"^[a-f0-9]{32,128}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ROUNDING_QUANTUM = Decimal("0.000001")
_T = TypeVar("_T")


class ToolingDefectState(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    READY_FOR_VERIFICATION = "ready_for_verification"
    CLOSED = "closed"
    REOPENED = "reopened"


class ToolingDefectSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolingDefectRootCauseState(StrEnum):
    PENDING = "pending"
    RECORDED = "recorded"


class ToolingDefectContextKind(StrEnum):
    TOOLING_REVISION = "tooling_revision"
    MANUFACTURING_MILESTONE_OBSERVATION = "manufacturing_milestone_observation"
    TOOLING_INTAKE = "tooling_intake"
    UNAVAILABLE_TRIAL_CONTEXT = "unavailable_trial_context"


class ToolingDefectActionType(StrEnum):
    CONTAINMENT = "containment"
    CORRECTIVE = "corrective"
    PREVENTIVE = "preventive"


class ToolingDefectActionState(StrEnum):
    PLANNED = "planned"
    COMPLETED = "completed"
    VERIFIED = "verified"


class ToolingDefectEvidenceRole(StrEnum):
    DETECTION = "detection"
    ANALYSIS = "analysis"
    ACTION = "action"
    VERIFICATION = "verification"


class ToolingProcessLayer(StrEnum):
    CUSTOMER_STANDARD = "customer_standard"
    TRIAL_ACTUAL = "trial_actual"
    APPROVED_BASELINE = "approved_baseline"


class ToolingProcessContextKind(StrEnum):
    RELEASED_DOCUMENT = "released_document"
    TOOLING_REVISION_SPECIFICATION = "tooling_revision_specification"
    TRIAL_MEASUREMENT = "trial_measurement"
    APPROVED_TRIAL = "approved_trial"


class ToolingProcessMetricCode(StrEnum):
    CYCLE_TIME = "cycle_time"
    PART_WEIGHT = "part_weight"
    RUNNER_WEIGHT = "runner_weight"
    GROSS_WEIGHT_PER_CAVITY = "gross_weight_per_cavity"
    MACHINE_TONNAGE = "machine_tonnage"
    MACHINE_TYPE = "machine_type"


class ToolingProcessValueKind(StrEnum):
    NUMERIC = "numeric"
    TEXT = "text"


class ToolingProcessComparisonState(StrEnum):
    NOT_MEASURED = "not_measured"
    WITHIN_TOLERANCE = "within_tolerance"
    OUTSIDE_TOLERANCE = "outside_tolerance"
    UNAVAILABLE = "unavailable"


class CapacityProvenanceKind(StrEnum):
    CUSTOMER_STANDARD = "customer_standard"
    TOOLING_REVISION = "tooling_revision"
    TOOLING_APPLICABILITY = "tooling_applicability"
    TOOLING_SET_SELECTION = "tooling_set_selection"
    SCENARIO_ASSUMPTION = "scenario_assumption"


@dataclass(frozen=True, slots=True)
class ToolingDefectDetectionContext:
    kind: ToolingDefectContextKind
    global_id: UUID | None
    snapshot_hash: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ToolingDefectContextKind):
            raise _field_problem("detectionContext.kind", _("Select a supported value."))
        if self.kind is ToolingDefectContextKind.UNAVAILABLE_TRIAL_CONTEXT:
            if self.global_id is not None or self.snapshot_hash is not None:
                raise _field_problem(
                    "detectionContext",
                    _("Unavailable Trial context cannot contain an object reference."),
                )
            return
        object.__setattr__(
            self,
            "global_id",
            _uuid(self.global_id, "detectionContext.globalId"),
        )
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "detectionContext.snapshotHash"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "globalId": str(self.global_id) if self.global_id else None,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolingDefectFileEvidence:
    global_id: UUID
    role: ToolingDefectEvidenceRole
    file_revision_global_id: UUID
    file_optimistic_version: int
    frappe_content_hash: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "evidence.globalId"))
        if not isinstance(self.role, ToolingDefectEvidenceRole):
            raise _field_problem("evidence.role", _("Select a supported evidence role."))
        object.__setattr__(
            self,
            "file_revision_global_id",
            _uuid(self.file_revision_global_id, "evidence.fileRevisionGlobalId"),
        )
        object.__setattr__(
            self,
            "file_optimistic_version",
            _positive(self.file_optimistic_version, "evidence.fileOptimisticVersion"),
        )
        object.__setattr__(
            self,
            "frappe_content_hash",
            _content_hash(self.frappe_content_hash, "evidence.frappeContentHash"),
        )
        object.__setattr__(self, "file_name", _text(self.file_name, "evidence.fileName", 255))
        object.__setattr__(self, "mime_type", _text(self.mime_type, "evidence.mimeType", 255))
        object.__setattr__(self, "size_bytes", _positive(self.size_bytes, "evidence.sizeBytes"))
        object.__setattr__(self, "sha256", _hash(self.sha256, "evidence.sha256"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "role": self.role.value,
            "fileRevisionGlobalId": str(self.file_revision_global_id),
            "fileOptimisticVersion": self.file_optimistic_version,
            "frappeContentHash": self.frappe_content_hash,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class ToolingDefectAction:
    global_id: UUID
    action_type: ToolingDefectActionType
    state: ToolingDefectActionState
    detail: str
    responsible_member: ProjectMemberResponsibility
    due_date: date
    evidence: tuple[ToolingDefectFileEvidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "action.globalId"))
        if not isinstance(self.action_type, ToolingDefectActionType):
            raise _field_problem("action.actionType", _("Select a supported value."))
        if not isinstance(self.state, ToolingDefectActionState):
            raise _field_problem("action.state", _("Select a supported value."))
        object.__setattr__(self, "detail", _text(self.detail, "action.detail", 2_000))
        if not isinstance(self.responsible_member, ProjectMemberResponsibility):
            raise _field_problem("action.responsibleMember", _("Select a valid Project member."))
        object.__setattr__(self, "due_date", _date(self.due_date, "action.dueDate"))
        object.__setattr__(
            self,
            "evidence",
            _typed_tuple(self.evidence, ToolingDefectFileEvidence, "action.evidence", maximum=20),
        )
        _unique((item.global_id for item in self.evidence), "action.evidence")
        if self.state is ToolingDefectActionState.VERIFIED and not self.evidence:
            raise _field_problem(
                "action.evidence",
                _("Verified defect actions require exact evidence."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "actionType": self.action_type.value,
            "state": self.state.value,
            "detail": self.detail,
            "responsibleMember": self.responsible_member.snapshot_payload(),
            "dueDate": self.due_date.isoformat(),
            "evidence": [item.snapshot_payload() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class ToolingDefectRevision:
    global_id: UUID
    defect_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_revision_global_id: UUID
    tooling_revision_snapshot_hash: str
    cavity_global_id: UUID | None
    cavity_identifier: str | None
    defect_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    business_code: str
    title: str
    description: str
    category_key: str
    severity: ToolingDefectSeverity
    blocking: bool
    state: ToolingDefectState
    detection_context: ToolingDefectDetectionContext
    root_cause_state: ToolingDefectRootCauseState
    root_cause: str | None
    responsible_member: ProjectMemberResponsibility | None
    target_round_label: str | None
    actions: tuple[ToolingDefectAction, ...]
    evidence: tuple[ToolingDefectFileEvidence, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    schema_version: int = TOOLING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)
        for fieldname in (
            "global_id",
            "defect_global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        object.__setattr__(
            self,
            "tooling_revision_snapshot_hash",
            _hash(self.tooling_revision_snapshot_hash, "toolingRevisionSnapshotHash"),
        )
        object.__setattr__(self, "cavity_global_id", _optional_uuid(self.cavity_global_id, "cavityGlobalId"))
        object.__setattr__(self, "cavity_identifier", _optional_text(self.cavity_identifier, "cavityIdentifier", 128))
        if (self.cavity_global_id is None) != (self.cavity_identifier is None):
            raise _field_problem(
                "cavityGlobalId",
                _("Cavity identity and identifier must be provided together."),
            )
        object.__setattr__(self, "defect_version", _positive(self.defect_version, "defectVersion"))
        object.__setattr__(self, "predecessor_global_id", _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"))
        object.__setattr__(self, "predecessor_snapshot_hash", _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"))
        _require_predecessor(
            self.defect_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "predecessorGlobalId",
        )
        object.__setattr__(self, "business_code", _key(self.business_code, "businessCode", 64))
        object.__setattr__(self, "title", _text(self.title, "title", 255))
        object.__setattr__(self, "description", _text(self.description, "description", 4_000))
        object.__setattr__(self, "category_key", _key(self.category_key, "categoryKey", 128))
        if not isinstance(self.severity, ToolingDefectSeverity):
            raise _field_problem("severity", _("Select a supported severity."))
        if type(self.blocking) is not bool:
            raise _field_problem("blocking", _("Blocking must be a checkbox value."))
        if not isinstance(self.state, ToolingDefectState):
            raise _field_problem("state", _("Select a supported value."))
        if self.defect_version == 1 and self.state is not ToolingDefectState.OPEN:
            raise _field_problem(
                "state",
                _("The first Tooling defect revision must be open."),
            )
        if not isinstance(self.detection_context, ToolingDefectDetectionContext):
            raise _field_problem("detectionContext", _("Enter a valid detection context."))
        if not isinstance(self.root_cause_state, ToolingDefectRootCauseState):
            raise _field_problem("rootCauseState", _("Select a supported value."))
        object.__setattr__(self, "root_cause", _optional_text(self.root_cause, "rootCause", 4_000))
        if (self.root_cause_state is ToolingDefectRootCauseState.RECORDED) != (self.root_cause is not None):
            raise _field_problem(
                "rootCause",
                _("Recorded root cause state requires exact root cause text."),
            )
        if self.responsible_member is not None and not isinstance(
            self.responsible_member, ProjectMemberResponsibility
        ):
            raise _field_problem("responsibleMember", _("Select a valid Project member."))
        if self.state is not ToolingDefectState.OPEN and self.responsible_member is None:
            raise _field_problem(
                "responsibleMember",
                _("Assigned defect states require a responsible Project member."),
            )
        object.__setattr__(self, "target_round_label", _optional_text(self.target_round_label, "targetRoundLabel", 64))
        object.__setattr__(self, "actions", _typed_tuple(self.actions, ToolingDefectAction, "actions", maximum=100))
        object.__setattr__(self, "evidence", _typed_tuple(self.evidence, ToolingDefectFileEvidence, "evidence", maximum=100))
        _unique((item.global_id for item in self.actions), "actions")
        evidence_ids = [item.global_id for item in self.evidence]
        evidence_ids.extend(item.global_id for action in self.actions for item in action.evidence)
        _unique(evidence_ids, "evidence")
        if self.state is ToolingDefectState.READY_FOR_VERIFICATION and not any(
            item.action_type is ToolingDefectActionType.CORRECTIVE for item in self.actions
        ):
            raise _field_problem(
                "actions",
                _("Ready for verification requires a corrective action."),
            )
        if self.state is ToolingDefectState.CLOSED:
            if not self.actions or any(
                item.state is ToolingDefectActionState.PLANNED for item in self.actions
            ):
                raise _field_problem(
                    "actions",
                    _("Closed defects require completed or verified actions."),
                )
            if not any(item.role is ToolingDefectEvidenceRole.VERIFICATION for item in self.evidence):
                raise _field_problem(
                    "evidence",
                    _("Closed defects require exact verification evidence."),
                )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId", 128))

    @property
    def version_key_hash(self) -> str:
        return sha256_json({"defectGlobalId": str(self.defect_global_id), "defectVersion": self.defect_version})

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "globalId": str(self.global_id),
            "defectGlobalId": str(self.defect_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "cavityGlobalId": str(self.cavity_global_id) if self.cavity_global_id else None,
            "cavityIdentifier": self.cavity_identifier,
            "defectVersion": self.defect_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "businessCode": self.business_code,
            "title": self.title,
            "description": self.description,
            "categoryKey": self.category_key,
            "severity": self.severity.value,
            "blocking": self.blocking,
            "state": self.state.value,
            "detectionContext": self.detection_context.snapshot_payload(),
            "rootCauseState": self.root_cause_state.value,
            "rootCause": self.root_cause,
            "responsibleMember": self.responsible_member.snapshot_payload() if self.responsible_member else None,
            "targetRoundLabel": self.target_round_label,
            "trialReference": {
                "state": "unavailable",
                "reasonCode": "trial_context_unavailable",
            },
            "actions": [item.snapshot_payload() for item in self.actions],
            "evidence": [item.snapshot_payload() for item in self.evidence],
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "versionKeyHash": self.version_key_hash,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


_DEFECT_TRANSITIONS: dict[ToolingDefectState, frozenset[ToolingDefectState]] = {
    ToolingDefectState.OPEN: frozenset({ToolingDefectState.ASSIGNED}),
    ToolingDefectState.ASSIGNED: frozenset({ToolingDefectState.IN_PROGRESS}),
    ToolingDefectState.IN_PROGRESS: frozenset({ToolingDefectState.READY_FOR_VERIFICATION}),
    ToolingDefectState.READY_FOR_VERIFICATION: frozenset({ToolingDefectState.CLOSED}),
    ToolingDefectState.CLOSED: frozenset({ToolingDefectState.REOPENED}),
    ToolingDefectState.REOPENED: frozenset({ToolingDefectState.ASSIGNED}),
}


def validate_tooling_defect_successor(
    current: ToolingDefectRevision,
    successor: ToolingDefectRevision,
) -> None:
    if not isinstance(current, ToolingDefectRevision) or not isinstance(successor, ToolingDefectRevision):
        raise _field_problem("defect", _("Enter valid Tooling defect revisions."))
    immutable = (
        "defect_global_id",
        "tenant_id",
        "project_global_id",
        "tooling_master_global_id",
        "business_code",
    )
    if any(getattr(current, field) != getattr(successor, field) for field in immutable):
        raise _field_problem("defect", _("A Tooling defect successor cannot change stable identity."))
    if (
        successor.defect_version != current.defect_version + 1
        or successor.predecessor_global_id != current.global_id
        or successor.predecessor_snapshot_hash != current.snapshot_hash
    ):
        raise _field_problem("predecessorGlobalId", _("Select the exact current Tooling defect revision."))
    if successor.state not in _DEFECT_TRANSITIONS[current.state]:
        raise _field_problem("state", _("Select the next supported Tooling defect state."))
    if current.state is ToolingDefectState.CLOSED and successor.state is ToolingDefectState.REOPENED:
        if successor.reason == current.reason:
            raise _field_problem("reason", _("Reopening a defect requires a new reason."))
    _validate_action_successors(current.actions, successor.actions)
    current_evidence = {item.global_id: item for item in current.evidence}
    successor_evidence = {item.global_id: item for item in successor.evidence}
    if not set(current_evidence).issubset(successor_evidence) or any(
        successor_evidence[key] != value for key, value in current_evidence.items()
    ):
        raise _field_problem("evidence", _("Existing Tooling defect evidence must be retained."))


def _validate_action_successors(
    current_actions: tuple[ToolingDefectAction, ...],
    successor_actions: tuple[ToolingDefectAction, ...],
) -> None:
    current_by_id = {item.global_id: item for item in current_actions}
    successor_by_id = {item.global_id: item for item in successor_actions}
    if not set(current_by_id).issubset(successor_by_id):
        raise _field_problem("actions", _("A Tooling defect successor cannot remove actions."))
    order = {
        ToolingDefectActionState.PLANNED: 0,
        ToolingDefectActionState.COMPLETED: 1,
        ToolingDefectActionState.VERIFIED: 2,
    }
    for global_id, current in current_by_id.items():
        successor = successor_by_id[global_id]
        if (
            current.action_type != successor.action_type
            or current.detail != successor.detail
            or current.responsible_member != successor.responsible_member
            or current.due_date != successor.due_date
            or order[successor.state] < order[current.state]
        ):
            raise _field_problem("actions", _("Existing defect action identity and history must be retained."))
        current_evidence = {item.global_id: item for item in current.evidence}
        successor_evidence = {item.global_id: item for item in successor.evidence}
        if not set(current_evidence).issubset(successor_evidence) or any(
            successor_evidence[key] != value for key, value in current_evidence.items()
        ):
            raise _field_problem("actions", _("Existing defect action evidence must be retained."))


@dataclass(frozen=True, slots=True)
class ToolingProcessContextEvidence:
    kind: ToolingProcessContextKind
    global_id: UUID
    snapshot_hash: str
    released_document: ReleasedDocumentEvidence | None = None
    approval_event_global_id: UUID | None = None
    approval_event_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ToolingProcessContextKind):
            raise _field_problem("context.kind", _("Select a supported value."))
        object.__setattr__(self, "global_id", _uuid(self.global_id, "context.globalId"))
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "context.snapshotHash"))
        released_required = self.kind is ToolingProcessContextKind.RELEASED_DOCUMENT
        if released_required:
            if (
                not isinstance(self.released_document, ReleasedDocumentEvidence)
                or self.released_document.revision_global_id != self.global_id
                or self.released_document.revision_snapshot_hash != self.snapshot_hash
            ):
                raise _field_problem(
                    "context.releasedDocument",
                    _("Released Document context requires exact release evidence."),
                )
        elif self.released_document is not None:
            raise _field_problem(
                "context.releasedDocument",
                _("Only released Document context can contain Document release evidence."),
            )
        object.__setattr__(self, "approval_event_global_id", _optional_uuid(self.approval_event_global_id, "context.approvalEventGlobalId"))
        object.__setattr__(self, "approval_event_hash", _optional_hash(self.approval_event_hash, "context.approvalEventHash"))
        approval_required = self.kind is ToolingProcessContextKind.APPROVED_TRIAL
        if approval_required != (self.approval_event_global_id is not None and self.approval_event_hash is not None):
            raise _field_problem(
                "context.approvalEventGlobalId",
                _("Approved Trial context requires an exact approval event."),
            )
        if not approval_required and (self.approval_event_global_id is not None or self.approval_event_hash is not None):
            raise _field_problem("context", _("Only approved Trial context can contain an approval event."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "globalId": str(self.global_id),
            "snapshotHash": self.snapshot_hash,
            "releasedDocument": (
                self.released_document.snapshot_payload()
                if self.released_document is not None
                else None
            ),
            "approvalEventGlobalId": str(self.approval_event_global_id) if self.approval_event_global_id else None,
            "approvalEventHash": self.approval_event_hash,
        }


@dataclass(frozen=True, slots=True)
class ProcessComparisonRuleSnapshot:
    global_id: UUID
    rule_version: int
    unit: str
    minimum: str
    maximum: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "rule.globalId"))
        object.__setattr__(self, "rule_version", _positive(self.rule_version, "rule.ruleVersion"))
        object.__setattr__(self, "unit", _key(self.unit, "rule.unit", 32))
        object.__setattr__(self, "minimum", _decimal(self.minimum, "rule.minimum"))
        object.__setattr__(self, "maximum", _decimal(self.maximum, "rule.maximum"))
        if Decimal(self.maximum) < Decimal(self.minimum):
            raise _field_problem("rule.maximum", _("Maximum tolerance cannot be lower than minimum tolerance."))

    def snapshot_payload(self) -> dict[str, object]:
        payload = {
            "globalId": str(self.global_id),
            "ruleVersion": self.rule_version,
            "unit": self.unit,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }
        return {**payload, "snapshotHash": sha256_json(payload)}

    @property
    def snapshot_hash(self) -> str:
        return str(self.snapshot_payload()["snapshotHash"])


@dataclass(frozen=True, slots=True)
class ToolingProcessMetric:
    global_id: UUID
    code: ToolingProcessMetricCode
    value_kind: ToolingProcessValueKind
    numeric_value: str | None
    text_value: str | None
    unit: str | None
    comparison_rule: ProcessComparisonRuleSnapshot | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "metric.globalId"))
        if not isinstance(self.code, ToolingProcessMetricCode):
            raise _field_problem("metric.code", _("Select a supported process metric."))
        if not isinstance(self.value_kind, ToolingProcessValueKind):
            raise _field_problem("metric.valueKind", _("Select a supported value kind."))
        numeric = None if self.numeric_value in (None, "") else _decimal(self.numeric_value, "metric.numericValue")
        text = _optional_text(self.text_value, "metric.textValue", 255)
        unit = None if self.unit in (None, "") else _key(self.unit, "metric.unit", 32)
        if self.value_kind is ToolingProcessValueKind.NUMERIC:
            if numeric is None or text is not None or unit is None:
                raise _field_problem("metric", _("Numeric process metrics require one value and unit."))
        elif text is None or numeric is not None or unit is not None:
            raise _field_problem("metric", _("Text process metrics require one text value without a unit."))
        if self.code is ToolingProcessMetricCode.MACHINE_TYPE and self.value_kind is not ToolingProcessValueKind.TEXT:
            raise _field_problem("metric.valueKind", _("Machine type must be a text process metric."))
        if self.code is not ToolingProcessMetricCode.MACHINE_TYPE and self.value_kind is not ToolingProcessValueKind.NUMERIC:
            raise _field_problem("metric.valueKind", _("This process metric must be numeric."))
        if self.comparison_rule is not None:
            if not isinstance(self.comparison_rule, ProcessComparisonRuleSnapshot):
                raise _field_problem("metric.comparisonRule", _("Enter a valid comparison rule."))
            if numeric is None or unit != self.comparison_rule.unit:
                raise _field_problem("metric.comparisonRule", _("Comparison rule unit must match the metric unit."))
        object.__setattr__(self, "numeric_value", numeric)
        object.__setattr__(self, "text_value", text)
        object.__setattr__(self, "unit", unit)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "code": self.code.value,
            "valueKind": self.value_kind.value,
            "numericValue": self.numeric_value,
            "textValue": self.text_value,
            "unit": self.unit,
            "comparisonRule": self.comparison_rule.snapshot_payload() if self.comparison_rule else None,
        }


@dataclass(frozen=True, slots=True)
class ToolingProcessProfileRevision:
    global_id: UUID
    profile_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_revision_global_id: UUID
    tooling_revision_snapshot_hash: str
    layer: ToolingProcessLayer
    profile_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    context: ToolingProcessContextEvidence
    effective_from: date
    metrics: tuple[ToolingProcessMetric, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    schema_version: int = TOOLING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)
        for fieldname in (
            "global_id", "profile_global_id", "project_global_id",
            "tooling_master_global_id", "tooling_revision_global_id", "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        object.__setattr__(self, "tooling_revision_snapshot_hash", _hash(self.tooling_revision_snapshot_hash, "toolingRevisionSnapshotHash"))
        if not isinstance(self.layer, ToolingProcessLayer):
            raise _field_problem("layer", _("Select a supported process fact layer."))
        object.__setattr__(self, "profile_version", _positive(self.profile_version, "profileVersion"))
        object.__setattr__(self, "predecessor_global_id", _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"))
        object.__setattr__(self, "predecessor_snapshot_hash", _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"))
        _require_predecessor(self.profile_version, self.predecessor_global_id, self.predecessor_snapshot_hash, "predecessorGlobalId")
        if not isinstance(self.context, ToolingProcessContextEvidence):
            raise _field_problem("context", _("Enter valid process source context."))
        allowed_contexts = {
            ToolingProcessLayer.CUSTOMER_STANDARD: {
                ToolingProcessContextKind.RELEASED_DOCUMENT,
                ToolingProcessContextKind.TOOLING_REVISION_SPECIFICATION,
            },
            ToolingProcessLayer.TRIAL_ACTUAL: {ToolingProcessContextKind.TRIAL_MEASUREMENT},
            ToolingProcessLayer.APPROVED_BASELINE: {ToolingProcessContextKind.APPROVED_TRIAL},
        }
        if self.context.kind not in allowed_contexts[self.layer]:
            raise _field_problem("context.kind", _("Process source context does not match its fact layer."))
        object.__setattr__(self, "effective_from", _date(self.effective_from, "effectiveFrom"))
        object.__setattr__(self, "metrics", _typed_tuple(self.metrics, ToolingProcessMetric, "metrics", maximum=32))
        if not self.metrics:
            raise _field_problem("metrics", _("Enter at least one process metric."))
        _unique((item.global_id for item in self.metrics), "metrics")
        _unique((item.code for item in self.metrics), "metrics.code")
        if self.layer is not ToolingProcessLayer.CUSTOMER_STANDARD and any(item.comparison_rule for item in self.metrics):
            raise _field_problem("metrics.comparisonRule", _("Only Customer Standard metrics can own comparison rules."))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId", 128))

    @property
    def version_key_hash(self) -> str:
        return sha256_json({"profileGlobalId": str(self.profile_global_id), "profileVersion": self.profile_version})

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "globalId": str(self.global_id),
            "profileGlobalId": str(self.profile_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "layer": self.layer.value,
            "profileVersion": self.profile_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "context": self.context.snapshot_payload(),
            "effectiveFrom": self.effective_from.isoformat(),
            "metrics": [item.snapshot_payload() for item in self.metrics],
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "versionKeyHash": self.version_key_hash,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


def validate_process_profile_successor(
    current: ToolingProcessProfileRevision,
    successor: ToolingProcessProfileRevision,
) -> None:
    if (
        current.profile_global_id != successor.profile_global_id
        or current.tenant_id != successor.tenant_id
        or current.project_global_id != successor.project_global_id
        or current.tooling_master_global_id != successor.tooling_master_global_id
        or current.layer != successor.layer
        or successor.profile_version != current.profile_version + 1
        or successor.predecessor_global_id != current.global_id
        or successor.predecessor_snapshot_hash != current.snapshot_hash
    ):
        raise _field_problem("predecessorGlobalId", _("Select the exact current process profile revision."))


@dataclass(frozen=True, slots=True)
class ToolingProcessComparison:
    state: ToolingProcessComparisonState
    reference_layer: ToolingProcessLayer
    metric_code: ToolingProcessMetricCode
    unit: str | None
    reference_value: str | None
    actual_value: str | None
    delta: str | None
    percent_delta: str | None
    rule_global_id: UUID | None
    rule_version: int | None
    rule_snapshot_hash: str | None

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "referenceLayer": self.reference_layer.value,
            "metricCode": self.metric_code.value,
            "unit": self.unit,
            "referenceValue": self.reference_value,
            "actualValue": self.actual_value,
            "delta": self.delta,
            "percentDelta": self.percent_delta,
            "ruleGlobalId": str(self.rule_global_id) if self.rule_global_id else None,
            "ruleVersion": self.rule_version,
            "ruleSnapshotHash": self.rule_snapshot_hash,
            "visualSemantics": {
                "state": "unavailable",
                "reasonCode": "variance_exception_color_policy_unavailable",
            },
        }


def compare_process_metric(
    reference_layer: ToolingProcessLayer,
    reference: ToolingProcessMetric,
    actual: ToolingProcessMetric | None,
) -> ToolingProcessComparison:
    if reference_layer not in {
        ToolingProcessLayer.CUSTOMER_STANDARD,
        ToolingProcessLayer.APPROVED_BASELINE,
    }:
        raise _field_problem("referenceLayer", _("Select a supported comparison reference layer."))
    base = {
        "reference_layer": reference_layer,
        "metric_code": reference.code,
        "unit": reference.unit,
        "reference_value": reference.numeric_value or reference.text_value,
        "actual_value": None if actual is None else actual.numeric_value or actual.text_value,
    }
    if actual is None:
        return ToolingProcessComparison(
            state=ToolingProcessComparisonState.NOT_MEASURED,
            delta=None,
            percent_delta=None,
            rule_global_id=None,
            rule_version=None,
            rule_snapshot_hash=None,
            **base,
        )
    if (
        reference.code != actual.code
        or reference.value_kind is not ToolingProcessValueKind.NUMERIC
        or actual.value_kind is not ToolingProcessValueKind.NUMERIC
        or reference.unit != actual.unit
        or reference.comparison_rule is None
    ):
        return ToolingProcessComparison(
            state=ToolingProcessComparisonState.UNAVAILABLE,
            delta=None,
            percent_delta=None,
            rule_global_id=None,
            rule_version=None,
            rule_snapshot_hash=None,
            **base,
        )
    reference_value = Decimal(reference.numeric_value or "0")
    actual_value = Decimal(actual.numeric_value or "0")
    rule = reference.comparison_rule
    delta = actual_value - reference_value
    percent = None if reference_value == 0 else delta / reference_value * 100
    state = (
        ToolingProcessComparisonState.WITHIN_TOLERANCE
        if Decimal(rule.minimum) <= actual_value <= Decimal(rule.maximum)
        else ToolingProcessComparisonState.OUTSIDE_TOLERANCE
    )
    return ToolingProcessComparison(
        state=state,
        delta=_decimal_text(delta),
        percent_delta=None if percent is None else _rounded_text(percent),
        rule_global_id=rule.global_id,
        rule_version=rule.rule_version,
        rule_snapshot_hash=rule.snapshot_hash,
        **base,
    )


@dataclass(frozen=True, slots=True)
class CapacityInputProvenance:
    kind: CapacityProvenanceKind
    global_id: UUID | None
    snapshot_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CapacityProvenanceKind):
            raise _field_problem("provenance.kind", _("Select a supported value."))
        object.__setattr__(self, "global_id", _optional_uuid(self.global_id, "provenance.globalId"))
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "provenance.snapshotHash"))
        if (self.kind is CapacityProvenanceKind.SCENARIO_ASSUMPTION) != (self.global_id is None):
            raise _field_problem(
                "provenance.globalId",
                _("Only a scenario assumption can omit its exact source identity."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "globalId": str(self.global_id) if self.global_id else None,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolingCapacityLineInput:
    global_id: UUID
    part_revision_global_id: UUID
    part_revision_snapshot_hash: str
    applicability_global_id: UUID
    applicability_snapshot_hash: str
    available_hours_per_day: str
    working_days_per_month: int
    oee_ratio: str
    yield_ratio: str
    cycle_seconds: str
    cavity_count: int
    usage_per_assembly: str
    effective_set_count: int
    selected_tooling_set_global_ids: tuple[UUID, ...]
    cycle_provenance: CapacityInputProvenance
    cavity_provenance: CapacityInputProvenance
    usage_provenance: CapacityInputProvenance
    set_provenance: CapacityInputProvenance

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "part_revision_global_id", "applicability_global_id"):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "part_revision_snapshot_hash", _hash(self.part_revision_snapshot_hash, "partRevisionSnapshotHash"))
        object.__setattr__(self, "applicability_snapshot_hash", _hash(self.applicability_snapshot_hash, "applicabilitySnapshotHash"))
        object.__setattr__(self, "available_hours_per_day", _bounded_decimal(self.available_hours_per_day, "availableHoursPerDay", minimum=Decimal("0"), maximum=Decimal("24")))
        days = _positive(self.working_days_per_month, "workingDaysPerMonth")
        if days > 31:
            raise _field_problem("workingDaysPerMonth", _("Working days per month cannot exceed 31."))
        object.__setattr__(self, "working_days_per_month", days)
        object.__setattr__(self, "oee_ratio", _bounded_decimal(self.oee_ratio, "oeeRatio", minimum=Decimal("0"), maximum=Decimal("1")))
        object.__setattr__(self, "yield_ratio", _bounded_decimal(self.yield_ratio, "yieldRatio", minimum=Decimal("0"), maximum=Decimal("1")))
        object.__setattr__(self, "cycle_seconds", _positive_decimal(self.cycle_seconds, "cycleSeconds"))
        object.__setattr__(self, "cavity_count", _positive(self.cavity_count, "cavityCount"))
        object.__setattr__(self, "usage_per_assembly", _positive_decimal(self.usage_per_assembly, "usagePerAssembly"))
        object.__setattr__(self, "effective_set_count", _whole(self.effective_set_count, "effectiveSetCount"))
        object.__setattr__(self, "selected_tooling_set_global_ids", _uuid_tuple(self.selected_tooling_set_global_ids, "selectedToolingSetGlobalIds", maximum=100))
        if self.selected_tooling_set_global_ids and len(self.selected_tooling_set_global_ids) != self.effective_set_count:
            raise _field_problem(
                "selectedToolingSetGlobalIds",
                _("Selected Tooling Sets must match the effective set assumption."),
            )
        for fieldname in (
            "cycle_provenance", "cavity_provenance", "usage_provenance", "set_provenance"
        ):
            if not isinstance(getattr(self, fieldname), CapacityInputProvenance):
                raise _field_problem(_camel(fieldname), _("Enter valid capacity input provenance."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "partRevisionGlobalId": str(self.part_revision_global_id),
            "partRevisionSnapshotHash": self.part_revision_snapshot_hash,
            "applicabilityGlobalId": str(self.applicability_global_id),
            "applicabilitySnapshotHash": self.applicability_snapshot_hash,
            "availableHoursPerDay": self.available_hours_per_day,
            "workingDaysPerMonth": self.working_days_per_month,
            "oeeRatio": self.oee_ratio,
            "yieldRatio": self.yield_ratio,
            "cycleSeconds": self.cycle_seconds,
            "cavityCount": self.cavity_count,
            "usagePerAssembly": self.usage_per_assembly,
            "effectiveSetCount": self.effective_set_count,
            "selectedToolingSetGlobalIds": [str(value) for value in self.selected_tooling_set_global_ids],
            "cycleProvenance": self.cycle_provenance.snapshot_payload(),
            "cavityProvenance": self.cavity_provenance.snapshot_payload(),
            "usageProvenance": self.usage_provenance.snapshot_payload(),
            "setProvenance": self.set_provenance.snapshot_payload(),
        }


@dataclass(frozen=True, slots=True)
class ToolingCapacityLineResult:
    global_id: UUID
    parts_per_day: str
    parts_per_month: str
    assembly_units_per_day: str
    assembly_units_per_month: str

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "partsPerDay": self.parts_per_day,
            "partsPerMonth": self.parts_per_month,
            "assemblyUnitsPerDay": self.assembly_units_per_day,
            "assemblyUnitsPerMonth": self.assembly_units_per_month,
        }


@dataclass(frozen=True, slots=True)
class ToolingCapacityScenarioRevision:
    global_id: UUID
    scenario_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    scenario_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    title: str
    effective_from: date
    target_monthly_assembly_units: str
    lines: tuple[ToolingCapacityLineInput, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    schema_version: int = TOOLING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)
        for fieldname in (
            "global_id", "scenario_global_id", "project_global_id",
            "tooling_master_global_id", "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        object.__setattr__(self, "scenario_version", _positive(self.scenario_version, "scenarioVersion"))
        object.__setattr__(self, "predecessor_global_id", _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"))
        object.__setattr__(self, "predecessor_snapshot_hash", _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"))
        _require_predecessor(self.scenario_version, self.predecessor_global_id, self.predecessor_snapshot_hash, "predecessorGlobalId")
        object.__setattr__(self, "title", _text(self.title, "title", 255))
        object.__setattr__(self, "effective_from", _date(self.effective_from, "effectiveFrom"))
        object.__setattr__(self, "target_monthly_assembly_units", _nonnegative_decimal(self.target_monthly_assembly_units, "targetMonthlyAssemblyUnits"))
        object.__setattr__(self, "lines", _typed_tuple(self.lines, ToolingCapacityLineInput, "lines", maximum=100))
        if not self.lines:
            raise _field_problem("lines", _("Enter at least one capacity line."))
        _unique((item.global_id for item in self.lines), "lines")
        _unique((item.applicability_global_id for item in self.lines), "lines.applicabilityGlobalId")
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId", 128))

    @property
    def version_key_hash(self) -> str:
        return sha256_json({"scenarioGlobalId": str(self.scenario_global_id), "scenarioVersion": self.scenario_version})

    @property
    def results(self) -> tuple[ToolingCapacityLineResult, ...]:
        return tuple(_capacity_result(line) for line in self.lines)

    @property
    def scenario_assembly_units_per_month(self) -> str:
        return min((item.assembly_units_per_month for item in self.results), key=Decimal)

    @property
    def bottleneck_line_global_ids(self) -> tuple[UUID, ...]:
        minimum = Decimal(self.scenario_assembly_units_per_month)
        return tuple(
            item.global_id
            for item in sorted(self.results, key=lambda value: str(value.global_id))
            if Decimal(item.assembly_units_per_month) == minimum
        )

    @property
    def gap(self) -> str:
        value = max(
            Decimal(self.target_monthly_assembly_units) - Decimal(self.scenario_assembly_units_per_month),
            Decimal("0"),
        )
        return _rounded_text(value)

    def result_payload(self) -> dict[str, object]:
        return {
            "formulaVersion": "capacity.v1",
            "roundingRule": "decimal-6-half-even",
            "lineResults": [item.snapshot_payload() for item in self.results],
            "scenarioAssemblyUnitsPerMonth": self.scenario_assembly_units_per_month,
            "bottleneckLineGlobalIds": [str(value) for value in self.bottleneck_line_global_ids],
            "gap": self.gap,
        }

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "globalId": str(self.global_id),
            "scenarioGlobalId": str(self.scenario_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "scenarioVersion": self.scenario_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "title": self.title,
            "effectiveFrom": self.effective_from.isoformat(),
            "targetMonthlyAssemblyUnits": self.target_monthly_assembly_units,
            "formulaVersion": "capacity.v1",
            "roundingRule": "decimal-6-half-even",
            "lines": [item.snapshot_payload() for item in self.lines],
            "result": self.result_payload(),
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "versionKeyHash": self.version_key_hash,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


def validate_capacity_scenario_successor(
    current: ToolingCapacityScenarioRevision,
    successor: ToolingCapacityScenarioRevision,
) -> None:
    if (
        current.scenario_global_id != successor.scenario_global_id
        or current.tenant_id != successor.tenant_id
        or current.project_global_id != successor.project_global_id
        or current.tooling_master_global_id != successor.tooling_master_global_id
        or successor.scenario_version != current.scenario_version + 1
        or successor.predecessor_global_id != current.global_id
        or successor.predecessor_snapshot_hash != current.snapshot_hash
    ):
        raise _field_problem("predecessorGlobalId", _("Select the exact current Capacity Scenario revision."))


def _capacity_result(line: ToolingCapacityLineInput) -> ToolingCapacityLineResult:
    with localcontext() as context:
        context.prec = 50
        parts_per_day = (
            Decimal(line.available_hours_per_day)
            * Decimal("3600")
            / Decimal(line.cycle_seconds)
            * Decimal(line.oee_ratio)
            * Decimal(line.yield_ratio)
            * Decimal(line.cavity_count)
            * Decimal(line.effective_set_count)
        )
        parts_per_month = parts_per_day * Decimal(line.working_days_per_month)
        assembly_per_day = parts_per_day / Decimal(line.usage_per_assembly)
        assembly_per_month = parts_per_month / Decimal(line.usage_per_assembly)
    return ToolingCapacityLineResult(
        global_id=line.global_id,
        parts_per_day=_rounded_text(parts_per_day),
        parts_per_month=_rounded_text(parts_per_month),
        assembly_units_per_day=_rounded_text(assembly_per_day),
        assembly_units_per_month=_rounded_text(assembly_per_month),
    )


@dataclass(frozen=True, slots=True)
class ToolingHealthUnavailable:
    source_system: str = "ERPNEXT"
    editable_in: str = "ERPNEXT"
    state: str = "unavailable"

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceSystem": self.source_system,
            "editableIn": self.editable_in,
            "state": self.state,
            "shotCount": {"state": "unavailable", "reasonCode": "erp_shot_count_unavailable"},
            "calibration": {"state": "unavailable", "reasonCode": "shot_count_calibration_policy_unavailable"},
            "maintenance": {"state": "unavailable", "reasonCode": "erp_maintenance_projection_unavailable"},
            "healthScore": {"state": "unavailable", "reasonCode": "tooling_health_policy_unavailable"},
        }


def tooling_health_from_snapshot(value: object) -> ToolingHealthUnavailable:
    expected = ToolingHealthUnavailable().snapshot_payload()
    if value != expected:
        raise _field_problem("health", _("Enter a valid unavailable Tooling health projection."))
    return ToolingHealthUnavailable()


def defect_revision_from_snapshot(value: object) -> ToolingDefectRevision:
    record = _record(
        value,
        "defect",
        {
            "schemaVersion", "globalId", "defectGlobalId", "tenantId",
            "projectGlobalId", "toolingMasterGlobalId", "toolingRevisionGlobalId",
            "toolingRevisionSnapshotHash", "cavityGlobalId", "cavityIdentifier",
            "defectVersion", "predecessorGlobalId", "predecessorSnapshotHash",
            "businessCode", "title", "description", "categoryKey", "severity",
            "blocking", "state", "detectionContext", "rootCauseState", "rootCause",
            "responsibleMember", "targetRoundLabel", "trialReference", "actions",
            "evidence", "reason", "createdByUserId", "createdAt", "requestId",
            "traceId", "versionKeyHash",
        },
    )
    trial_reference = {
        "state": "unavailable",
        "reasonCode": "trial_context_unavailable",
    }
    if record["trialReference"] != trial_reference:
        raise _field_problem("trialReference", _("Trial context must remain unavailable in this phase."))
    result = ToolingDefectRevision(
        global_id=record["globalId"],
        defect_global_id=record["defectGlobalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        tooling_revision_global_id=record["toolingRevisionGlobalId"],
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        cavity_global_id=record["cavityGlobalId"],
        cavity_identifier=record["cavityIdentifier"],
        defect_version=record["defectVersion"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        business_code=record["businessCode"],
        title=record["title"],
        description=record["description"],
        category_key=record["categoryKey"],
        severity=_enum(record["severity"], ToolingDefectSeverity, "severity"),
        blocking=record["blocking"],
        state=_enum(record["state"], ToolingDefectState, "state"),
        detection_context=_defect_context_from_dict(record["detectionContext"]),
        root_cause_state=_enum(record["rootCauseState"], ToolingDefectRootCauseState, "rootCauseState"),
        root_cause=record["rootCause"],
        responsible_member=_member_from_dict(record["responsibleMember"], "responsibleMember") if record["responsibleMember"] is not None else None,
        target_round_label=record["targetRoundLabel"],
        actions=tuple(_defect_action_from_dict(item) for item in _list(record["actions"], "actions", maximum=100)),
        evidence=tuple(_defect_evidence_from_dict(item) for item in _list(record["evidence"], "evidence", maximum=100)),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
        schema_version=record["schemaVersion"],
    )
    if record["versionKeyHash"] != result.version_key_hash:
        raise _field_problem("versionKeyHash", _("Tooling Defect Version Key Hash does not match."))
    return result


def process_profile_from_snapshot(value: object) -> ToolingProcessProfileRevision:
    record = _record(
        value,
        "profile",
        {
            "schemaVersion", "globalId", "profileGlobalId", "tenantId",
            "projectGlobalId", "toolingMasterGlobalId", "toolingRevisionGlobalId",
            "toolingRevisionSnapshotHash", "layer", "profileVersion",
            "predecessorGlobalId", "predecessorSnapshotHash", "context",
            "effectiveFrom", "metrics", "reason", "createdByUserId", "createdAt",
            "requestId", "traceId", "versionKeyHash",
        },
    )
    result = ToolingProcessProfileRevision(
        global_id=record["globalId"],
        profile_global_id=record["profileGlobalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        tooling_revision_global_id=record["toolingRevisionGlobalId"],
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        layer=_enum(record["layer"], ToolingProcessLayer, "layer"),
        profile_version=record["profileVersion"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        context=_process_context_from_dict(record["context"]),
        effective_from=_date(record["effectiveFrom"], "effectiveFrom"),
        metrics=tuple(_process_metric_from_dict(item) for item in _list(record["metrics"], "metrics", maximum=32)),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
        schema_version=record["schemaVersion"],
    )
    if record["versionKeyHash"] != result.version_key_hash:
        raise _field_problem("versionKeyHash", _("Process Profile Version Key Hash does not match."))
    return result


def capacity_scenario_from_snapshot(value: object) -> ToolingCapacityScenarioRevision:
    record = _record(
        value,
        "scenario",
        {
            "schemaVersion", "globalId", "scenarioGlobalId", "tenantId",
            "projectGlobalId", "toolingMasterGlobalId", "scenarioVersion",
            "predecessorGlobalId", "predecessorSnapshotHash", "title",
            "effectiveFrom", "targetMonthlyAssemblyUnits", "formulaVersion",
            "roundingRule", "lines", "result", "reason", "createdByUserId",
            "createdAt", "requestId", "traceId", "versionKeyHash",
        },
    )
    if record["formulaVersion"] != "capacity.v1" or record["roundingRule"] != "decimal-6-half-even":
        raise _field_problem("formulaVersion", _("Select the supported capacity formula version."))
    result = ToolingCapacityScenarioRevision(
        global_id=record["globalId"],
        scenario_global_id=record["scenarioGlobalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        scenario_version=record["scenarioVersion"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        title=record["title"],
        effective_from=_date(record["effectiveFrom"], "effectiveFrom"),
        target_monthly_assembly_units=record["targetMonthlyAssemblyUnits"],
        lines=tuple(_capacity_line_from_dict(item) for item in _list(record["lines"], "lines", maximum=100)),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
        schema_version=record["schemaVersion"],
    )
    if record["versionKeyHash"] != result.version_key_hash:
        raise _field_problem("versionKeyHash", _("Capacity Scenario Version Key Hash does not match."))
    if record["result"] != result.result_payload():
        raise _field_problem("result", _("Capacity Scenario result does not match its exact inputs."))
    return result


def _defect_context_from_dict(value: object) -> ToolingDefectDetectionContext:
    record = _record(value, "detectionContext", {"kind", "globalId", "snapshotHash"})
    return ToolingDefectDetectionContext(
        kind=_enum(record["kind"], ToolingDefectContextKind, "detectionContext.kind"),
        global_id=record["globalId"],
        snapshot_hash=record["snapshotHash"],
    )


def _defect_evidence_from_dict(value: object) -> ToolingDefectFileEvidence:
    record = _record(
        value,
        "evidence",
        {
            "globalId", "role", "fileRevisionGlobalId", "fileOptimisticVersion",
            "frappeContentHash", "fileName", "mimeType", "sizeBytes", "sha256",
        },
    )
    return ToolingDefectFileEvidence(
        global_id=record["globalId"],
        role=_enum(record["role"], ToolingDefectEvidenceRole, "evidence.role"),
        file_revision_global_id=record["fileRevisionGlobalId"],
        file_optimistic_version=record["fileOptimisticVersion"],
        frappe_content_hash=record["frappeContentHash"],
        file_name=record["fileName"],
        mime_type=record["mimeType"],
        size_bytes=record["sizeBytes"],
        sha256=record["sha256"],
    )


def _defect_action_from_dict(value: object) -> ToolingDefectAction:
    record = _record(
        value,
        "action",
        {"globalId", "actionType", "state", "detail", "responsibleMember", "dueDate", "evidence"},
    )
    return ToolingDefectAction(
        global_id=record["globalId"],
        action_type=_enum(record["actionType"], ToolingDefectActionType, "action.actionType"),
        state=_enum(record["state"], ToolingDefectActionState, "action.state"),
        detail=record["detail"],
        responsible_member=_member_from_dict(record["responsibleMember"], "action.responsibleMember"),
        due_date=_date(record["dueDate"], "action.dueDate"),
        evidence=tuple(_defect_evidence_from_dict(item) for item in _list(record["evidence"], "action.evidence", maximum=20)),
    )


def _member_from_dict(value: object, path: str) -> ProjectMemberResponsibility:
    record = _record(value, path, {"globalId", "userId", "optimisticVersion"})
    return ProjectMemberResponsibility(
        global_id=record["globalId"],
        user_id=record["userId"],
        optimistic_version=record["optimisticVersion"],
    )


def _process_context_from_dict(value: object) -> ToolingProcessContextEvidence:
    record = _record(
        value,
        "context",
        {
            "kind", "globalId", "snapshotHash", "releasedDocument",
            "approvalEventGlobalId", "approvalEventHash",
        },
    )
    return ToolingProcessContextEvidence(
        kind=_enum(record["kind"], ToolingProcessContextKind, "context.kind"),
        global_id=record["globalId"],
        snapshot_hash=record["snapshotHash"],
        released_document=(
            _released_document_from_dict(record["releasedDocument"])
            if record["releasedDocument"] is not None
            else None
        ),
        approval_event_global_id=record["approvalEventGlobalId"],
        approval_event_hash=record["approvalEventHash"],
    )


def _released_document_from_dict(value: object) -> ReleasedDocumentEvidence:
    record = _record(
        value,
        "releasedDocument",
        {
            "revisionGlobalId", "revisionSnapshotHash", "lifecycleGlobalId",
            "lifecycleVersion", "releaseEventGlobalId", "releaseEventHash",
            "releaseSnapshotHash",
        },
    )
    return ReleasedDocumentEvidence(
        revision_global_id=record["revisionGlobalId"],
        revision_snapshot_hash=record["revisionSnapshotHash"],
        lifecycle_global_id=record["lifecycleGlobalId"],
        lifecycle_version=record["lifecycleVersion"],
        release_event_global_id=record["releaseEventGlobalId"],
        release_event_hash=record["releaseEventHash"],
        release_snapshot_hash=record["releaseSnapshotHash"],
    )


def _comparison_rule_from_dict(value: object) -> ProcessComparisonRuleSnapshot | None:
    if value is None:
        return None
    record = _record(value, "comparisonRule", {"globalId", "ruleVersion", "unit", "minimum", "maximum", "snapshotHash"})
    result = ProcessComparisonRuleSnapshot(
        global_id=record["globalId"],
        rule_version=record["ruleVersion"],
        unit=record["unit"],
        minimum=record["minimum"],
        maximum=record["maximum"],
    )
    if record["snapshotHash"] != result.snapshot_hash:
        raise _field_problem("comparisonRule.snapshotHash", _("Comparison Rule Snapshot Hash does not match."))
    return result


def _process_metric_from_dict(value: object) -> ToolingProcessMetric:
    record = _record(
        value,
        "metric",
        {"globalId", "code", "valueKind", "numericValue", "textValue", "unit", "comparisonRule"},
    )
    return ToolingProcessMetric(
        global_id=record["globalId"],
        code=_enum(record["code"], ToolingProcessMetricCode, "metric.code"),
        value_kind=_enum(record["valueKind"], ToolingProcessValueKind, "metric.valueKind"),
        numeric_value=record["numericValue"],
        text_value=record["textValue"],
        unit=record["unit"],
        comparison_rule=_comparison_rule_from_dict(record["comparisonRule"]),
    )


def _capacity_provenance_from_dict(value: object, path: str) -> CapacityInputProvenance:
    record = _record(value, path, {"kind", "globalId", "snapshotHash"})
    return CapacityInputProvenance(
        kind=_enum(record["kind"], CapacityProvenanceKind, f"{path}.kind"),
        global_id=record["globalId"],
        snapshot_hash=record["snapshotHash"],
    )


def _capacity_line_from_dict(value: object) -> ToolingCapacityLineInput:
    record = _record(
        value,
        "line",
        {
            "globalId", "partRevisionGlobalId", "partRevisionSnapshotHash",
            "applicabilityGlobalId", "applicabilitySnapshotHash",
            "availableHoursPerDay", "workingDaysPerMonth", "oeeRatio",
            "yieldRatio", "cycleSeconds", "cavityCount", "usagePerAssembly",
            "effectiveSetCount", "selectedToolingSetGlobalIds", "cycleProvenance",
            "cavityProvenance", "usageProvenance", "setProvenance",
        },
    )
    return ToolingCapacityLineInput(
        global_id=record["globalId"],
        part_revision_global_id=record["partRevisionGlobalId"],
        part_revision_snapshot_hash=record["partRevisionSnapshotHash"],
        applicability_global_id=record["applicabilityGlobalId"],
        applicability_snapshot_hash=record["applicabilitySnapshotHash"],
        available_hours_per_day=record["availableHoursPerDay"],
        working_days_per_month=record["workingDaysPerMonth"],
        oee_ratio=record["oeeRatio"],
        yield_ratio=record["yieldRatio"],
        cycle_seconds=record["cycleSeconds"],
        cavity_count=record["cavityCount"],
        usage_per_assembly=record["usagePerAssembly"],
        effective_set_count=record["effectiveSetCount"],
        selected_tooling_set_global_ids=tuple(_list(record["selectedToolingSetGlobalIds"], "selectedToolingSetGlobalIds", maximum=100)),
        cycle_provenance=_capacity_provenance_from_dict(record["cycleProvenance"], "cycleProvenance"),
        cavity_provenance=_capacity_provenance_from_dict(record["cavityProvenance"], "cavityProvenance"),
        usage_provenance=_capacity_provenance_from_dict(record["usageProvenance"], "usageProvenance"),
        set_provenance=_capacity_provenance_from_dict(record["setProvenance"], "setProvenance"),
    )


def _record(value: object, path: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _field_problem(path, _("Enter a valid closed object."))
    return value


def _list(value: object, path: str, *, maximum: int) -> list[object]:
    if not isinstance(value, list) or len(value) > maximum:
        raise _field_problem(path, _("Enter a valid bounded list."))
    return value


def _typed_tuple(value: object, expected_type: type[_T], path: str, *, maximum: int) -> tuple[_T, ...]:
    if not isinstance(value, (tuple, list)):
        raise _field_problem(path, _("Enter a valid bounded list."))
    normalized = tuple(value)
    if len(normalized) > maximum or not all(isinstance(item, expected_type) for item in normalized):
        raise _field_problem(path, _("Enter a valid bounded list."))
    return normalized


def _unique(values: object, path: str) -> None:
    normalized = tuple(values)  # type: ignore[arg-type]
    if len(normalized) != len(set(normalized)):
        raise _field_problem(path, _("Values must be unique within this list."))


def _schema_version(value: object) -> None:
    if value != TOOLING_SCHEMA_VERSION:
        raise _field_problem("schemaVersion", _("Select a supported schema version."))


def _enum(value: object, enum_type: type[_T], path: str) -> _T:
    try:
        return enum_type(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as error:
        raise _field_problem(path, _("Select a supported value.")) from error


def _uuid(value: object, path: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid global ID.")) from error


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid(value, path)


def _uuid_tuple(value: object, path: str, *, maximum: int) -> tuple[UUID, ...]:
    if not isinstance(value, (tuple, list)) or len(value) > maximum:
        raise _field_problem(path, _("Enter a valid bounded list."))
    result = tuple(_uuid(item, path) for item in value)
    _unique(result, path)
    return result


def _positive(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _field_problem(path, _("Enter a positive whole number."))
    return value


def _whole(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _field_problem(path, _("Enter a non-negative whole number."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field_problem(path, _("The value is too long."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value in (None, "") else _text(value, path, maximum)


def _actor(value: object, path: str) -> str:
    normalized = _text(value, path, 254)
    if _ACTOR_PATTERN.fullmatch(normalized) is None:
        raise _field_problem(path, _("Enter a valid user identity."))
    return normalized


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid SHA-256 value."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value in (None, "") else _hash(value, path)


def _content_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _CONTENT_HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid content hash."))
    return value


def _key(value: object, path: str, maximum: int) -> str:
    normalized = _text(value, path, maximum)
    if _KEY_PATTERN.fullmatch(normalized) is None:
        raise _field_problem(path, _("Use a valid key."))
    return normalized


def _decimal(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a valid decimal amount."))
    try:
        result = Decimal(value.strip())
    except InvalidOperation as error:
        raise _field_problem(path, _("Enter a valid decimal amount.")) from error
    if not result.is_finite() or len(value.strip()) > 32 or result.adjusted() > 24 or result.adjusted() < -24:
        raise _field_problem(path, _("Enter a valid decimal amount."))
    return _decimal_text(result)


def _positive_decimal(value: object, path: str) -> str:
    result = _decimal(value, path)
    if Decimal(result) <= 0:
        raise _field_problem(path, _("Enter a positive decimal amount."))
    return result


def _nonnegative_decimal(value: object, path: str) -> str:
    result = _decimal(value, path)
    if Decimal(result) < 0:
        raise _field_problem(path, _("Enter a non-negative decimal amount."))
    return result


def _bounded_decimal(value: object, path: str, *, minimum: Decimal, maximum: Decimal) -> str:
    result = _decimal(value, path)
    if not minimum <= Decimal(result) <= maximum:
        raise _field_problem(path, _("Enter a decimal value within the allowed range."))
    return result


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0.0"
    normalized = format(value.normalize(), "f")
    return normalized if "." in normalized else f"{normalized}.0"


def _rounded_text(value: Decimal) -> str:
    return format(value.quantize(_ROUNDING_QUANTUM, rounding=ROUND_HALF_EVEN), "f")


def _date(value: object, path: str) -> date:
    if isinstance(value, datetime):
        raise _field_problem(path, _("Enter a valid date."))
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid date.")) from error


def _datetime(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise _field_problem(path, _("Enter a timezone-aware date and time.")) from error
    else:
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    if parsed.tzinfo is None:
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_predecessor(version: int, predecessor_global_id: UUID | None, predecessor_snapshot_hash: str | None, path: str) -> None:
    if version == 1:
        if predecessor_global_id is not None or predecessor_snapshot_hash is not None:
            raise _field_problem(path, _("The first version cannot have a predecessor."))
    elif predecessor_global_id is None or predecessor_snapshot_hash is None:
        raise _field_problem(path, _("A successor version requires its exact predecessor."))


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
