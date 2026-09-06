from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import TOOLING_SCHEMA_VERSION, sha256_json

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_T = TypeVar("_T")


class ToolingSourcingStrategy(StrEnum):
    INTERNAL = "internal"
    SUPPLIER = "supplier"
    HYBRID = "hybrid"


class ToolingPlanEvidenceRole(StrEnum):
    DFM = "dfm"
    TOOLING_PROPOSAL = "tooling_proposal"
    QUOTATION = "quotation"
    BUDGET = "budget"


class ToolingMilestoneCategory(StrEnum):
    DESIGN = "design"
    MATERIAL_PREPARATION = "material_preparation"
    HEAT_TREATMENT = "heat_treatment"
    MACHINING = "machining"
    ASSEMBLY = "assembly"
    TRIAL_PREPARATION = "trial_preparation"
    DELIVERY = "delivery"


class ToolingMilestoneResponsibilityKind(StrEnum):
    INTERNAL = "internal"
    SUPPLIER = "supplier"


class ToolingMilestoneEvidenceRole(StrEnum):
    PROGRESS_EVIDENCE = "progress_evidence"
    TECHNICAL_EVIDENCE = "technical_evidence"
    DELIVERY_EVIDENCE = "delivery_evidence"


class DesignReleaseEvidenceState(StrEnum):
    SATISFIED = "satisfied"
    BLOCKED = "blocked"


class DesignReleaseBlockedReason(StrEnum):
    NO_DESIGN_DOCUMENTS = "no_design_documents"
    RELEASE_EVIDENCE_INCOMPLETE = "release_evidence_incomplete"


@dataclass(frozen=True, slots=True)
class ProjectMemberResponsibility:
    global_id: UUID
    user_id: str
    optimistic_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "member.globalId"))
        object.__setattr__(self, "user_id", _actor(self.user_id, "member.userId"))
        object.__setattr__(
            self,
            "optimistic_version",
            _positive(self.optimistic_version, "member.optimisticVersion"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "userId": self.user_id,
            "optimisticVersion": self.optimistic_version,
        }


@dataclass(frozen=True, slots=True)
class PlanningMoney:
    amount: str
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _decimal(self.amount, "amount", positive=True))
        object.__setattr__(self, "currency", _currency(self.currency, "currency"))

    def snapshot_payload(self) -> dict[str, object]:
        return {"amount": self.amount, "currency": self.currency}


@dataclass(frozen=True, slots=True)
class ReleasedDocumentEvidence:
    revision_global_id: UUID
    revision_snapshot_hash: str
    lifecycle_global_id: UUID
    lifecycle_version: int
    release_event_global_id: UUID
    release_event_hash: str
    release_snapshot_hash: str

    def __post_init__(self) -> None:
        for fieldname in (
            "revision_global_id",
            "lifecycle_global_id",
            "release_event_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(
            self,
            "revision_snapshot_hash",
            _hash(self.revision_snapshot_hash, "revisionSnapshotHash"),
        )
        object.__setattr__(
            self,
            "lifecycle_version",
            _positive(self.lifecycle_version, "lifecycleVersion"),
        )
        object.__setattr__(
            self,
            "release_event_hash",
            _hash(self.release_event_hash, "releaseEventHash"),
        )
        object.__setattr__(
            self,
            "release_snapshot_hash",
            _hash(self.release_snapshot_hash, "releaseSnapshotHash"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "revisionGlobalId": str(self.revision_global_id),
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "lifecycleGlobalId": str(self.lifecycle_global_id),
            "lifecycleVersion": self.lifecycle_version,
            "releaseEventGlobalId": str(self.release_event_global_id),
            "releaseEventHash": self.release_event_hash,
            "releaseSnapshotHash": self.release_snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolingPlanEvidence:
    role: ToolingPlanEvidenceRole
    document: ReleasedDocumentEvidence

    def __post_init__(self) -> None:
        if not isinstance(self.role, ToolingPlanEvidenceRole):
            raise _field_problem("evidence.role", _("Select a supported evidence role."))
        if not isinstance(self.document, ReleasedDocumentEvidence):
            raise _field_problem(
                "evidence.document",
                _("Enter valid released Document evidence."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {"role": self.role.value, "document": self.document.snapshot_payload()}


@dataclass(frozen=True, slots=True)
class ToolingManufacturingMilestone:
    global_id: UUID
    sequence: int
    category: ToolingMilestoneCategory
    planned_start: date
    planned_finish: date
    responsibility_kind: ToolingMilestoneResponsibilityKind
    responsible_member: ProjectMemberResponsibility | None
    predecessor_global_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "milestone.globalId"))
        object.__setattr__(self, "sequence", _positive(self.sequence, "milestone.sequence"))
        if not isinstance(self.category, ToolingMilestoneCategory):
            raise _field_problem("milestone.category", _("Select a supported milestone category."))
        object.__setattr__(
            self,
            "planned_start",
            _date(self.planned_start, "milestone.plannedStart"),
        )
        object.__setattr__(
            self,
            "planned_finish",
            _date(self.planned_finish, "milestone.plannedFinish"),
        )
        if self.planned_finish < self.planned_start:
            raise _field_problem(
                "milestone.plannedFinish",
                _("Planned finish cannot be earlier than planned start."),
            )
        if not isinstance(self.responsibility_kind, ToolingMilestoneResponsibilityKind):
            raise _field_problem(
                "milestone.responsibilityKind",
                _("Select a supported responsibility kind."),
            )
        if self.responsibility_kind is ToolingMilestoneResponsibilityKind.INTERNAL:
            if not isinstance(self.responsible_member, ProjectMemberResponsibility):
                raise _field_problem(
                    "milestone.responsibleMember",
                    _("Select an exact Project member for an internal milestone."),
                )
        elif self.responsible_member is not None:
            raise _field_problem(
                "milestone.responsibleMember",
                _("A supplier milestone cannot claim an internal responsible member."),
            )
        object.__setattr__(
            self,
            "predecessor_global_ids",
            _uuid_tuple(
                self.predecessor_global_ids,
                "milestone.predecessorGlobalIds",
                maximum=20,
            ),
        )

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self._content_payload())

    def _content_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "sequence": self.sequence,
            "category": self.category.value,
            "plannedStart": self.planned_start.isoformat(),
            "plannedFinish": self.planned_finish.isoformat(),
            "responsibilityKind": self.responsibility_kind.value,
            "responsibleMember": (
                self.responsible_member.snapshot_payload()
                if self.responsible_member is not None
                else None
            ),
            "predecessorGlobalIds": [str(value) for value in self.predecessor_global_ids],
        }

    def snapshot_payload(self) -> dict[str, object]:
        return {**self._content_payload(), "snapshotHash": self.snapshot_hash}


@dataclass(frozen=True, slots=True)
class ToolingManufacturingPlanRevision:
    global_id: UUID
    plan_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_revision_global_id: UUID
    tooling_revision_snapshot_hash: str
    plan_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    sourcing_strategy: ToolingSourcingStrategy
    responsible_member: ProjectMemberResponsibility
    engineering_estimate: PlanningMoney | None
    budget: PlanningMoney | None
    evidence: tuple[ToolingPlanEvidence, ...]
    design_release_evidence: tuple[ReleasedDocumentEvidence, ...]
    milestones: tuple[ToolingManufacturingMilestone, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    version_key_hash: str | None = None

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "plan_global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_revision_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        object.__setattr__(
            self,
            "tooling_revision_snapshot_hash",
            _hash(self.tooling_revision_snapshot_hash, "toolingRevisionSnapshotHash"),
        )
        object.__setattr__(self, "plan_version", _positive(self.plan_version, "planVersion"))
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
            self.plan_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "planVersion",
        )
        if not isinstance(self.sourcing_strategy, ToolingSourcingStrategy):
            raise _field_problem("sourcingStrategy", _("Select a supported sourcing strategy."))
        if not isinstance(self.responsible_member, ProjectMemberResponsibility):
            raise _field_problem(
                "responsibleMember",
                _("Select an exact responsible Project member."),
            )
        for fieldname in ("engineering_estimate", "budget"):
            value = getattr(self, fieldname)
            if value is not None and not isinstance(value, PlanningMoney):
                raise _field_problem(_camel(fieldname), _("Enter a valid planning amount."))
        if (
            self.engineering_estimate is not None
            and self.budget is not None
            and self.engineering_estimate.currency != self.budget.currency
        ):
            raise _field_problem(
                "budget.currency",
                _("Planning amounts must use one currency."),
            )
        object.__setattr__(
            self,
            "evidence",
            _typed_tuple(self.evidence, ToolingPlanEvidence, "evidence", maximum=4),
        )
        roles = [value.role for value in self.evidence]
        if len(roles) != len(set(roles)):
            raise _field_problem("evidence", _("Evidence roles must be unique."))
        object.__setattr__(
            self,
            "design_release_evidence",
            _typed_tuple(
                self.design_release_evidence,
                ReleasedDocumentEvidence,
                "designReleaseEvidence",
                maximum=50,
            ),
        )
        if not self.design_release_evidence:
            raise _field_problem(
                "designReleaseEvidence",
                _("Exact released design Document evidence is required."),
            )
        release_ids = [value.revision_global_id for value in self.design_release_evidence]
        if len(release_ids) != len(set(release_ids)):
            raise _field_problem(
                "designReleaseEvidence",
                _("Released Document revisions must be unique."),
            )
        all_released = [item.document for item in self.evidence]
        all_released.extend(self.design_release_evidence)
        release_by_revision: dict[UUID, ReleasedDocumentEvidence] = {}
        for released in all_released:
            previous = release_by_revision.setdefault(released.revision_global_id, released)
            if previous != released:
                raise _field_problem(
                    "evidence",
                    _("Released Document evidence must be consistent across roles."),
                )
        object.__setattr__(
            self,
            "milestones",
            _typed_tuple(
                self.milestones,
                ToolingManufacturingMilestone,
                "milestones",
                maximum=100,
            ),
        )
        if not self.milestones:
            raise _field_problem("milestones", _("Enter at least one manufacturing milestone."))
        _validate_milestone_graph(self.milestones)
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "projectGlobalId": str(self.project_global_id),
                "toolingMasterGlobalId": str(self.tooling_master_global_id),
                "planGlobalId": str(self.plan_global_id),
                "planVersion": self.plan_version,
            }
        )
        if self.version_key_hash not in (None, "", expected_key):
            raise _field_problem(
                "versionKeyHash",
                _("The manufacturing plan version key does not match."),
            )
        object.__setattr__(self, "version_key_hash", expected_key)

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "planGlobalId": str(self.plan_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "planVersion": self.plan_version,
            "predecessorGlobalId": (
                str(self.predecessor_global_id) if self.predecessor_global_id else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "sourcingStrategy": self.sourcing_strategy.value,
            "responsibleMember": self.responsible_member.snapshot_payload(),
            "engineeringEstimate": (
                self.engineering_estimate.snapshot_payload()
                if self.engineering_estimate is not None
                else None
            ),
            "budget": self.budget.snapshot_payload() if self.budget is not None else None,
            "evidence": [value.snapshot_payload() for value in self.evidence],
            "designReleaseEvidence": [
                value.snapshot_payload() for value in self.design_release_evidence
            ],
            "milestones": [value.snapshot_payload() for value in self.milestones],
            "reason": self.reason,
            "versionKeyHash": self.version_key_hash,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingMilestoneFileEvidence:
    global_id: UUID
    role: ToolingMilestoneEvidenceRole
    file_revision_global_id: UUID
    file_optimistic_version: int
    frappe_content_hash: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "evidence.globalId"))
        if not isinstance(self.role, ToolingMilestoneEvidenceRole):
            raise _field_problem("evidence.role", _("Select a supported milestone evidence role."))
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
        object.__setattr__(self, "mime_type", _text(self.mime_type, "evidence.mimeType", 127))
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes < 1:
            raise _field_problem("evidence.sizeBytes", _("Evidence size must be positive."))
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
class ToolingManufacturingMilestoneObservation:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    plan_revision_global_id: UUID
    plan_revision_snapshot_hash: str
    milestone_global_id: UUID
    milestone_snapshot_hash: str
    observation_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    progress_percentage: int
    actual_start: date | None
    actual_finish: date | None
    risk: str | None
    note: str | None
    evidence: tuple[ToolingMilestoneFileEvidence, ...]
    reported_by_member: ProjectMemberResponsibility
    created_at: datetime
    request_id: UUID
    trace_id: str
    observation_key_hash: str | None = None

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "tooling_master_global_id",
            "plan_revision_global_id",
            "milestone_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        object.__setattr__(
            self,
            "plan_revision_snapshot_hash",
            _hash(self.plan_revision_snapshot_hash, "planRevisionSnapshotHash"),
        )
        object.__setattr__(
            self,
            "milestone_snapshot_hash",
            _hash(self.milestone_snapshot_hash, "milestoneSnapshotHash"),
        )
        object.__setattr__(
            self,
            "observation_version",
            _positive(self.observation_version, "observationVersion"),
        )
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
            self.observation_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "observationVersion",
        )
        if (
            isinstance(self.progress_percentage, bool)
            or not isinstance(self.progress_percentage, int)
            or not 0 <= self.progress_percentage <= 100
        ):
            raise _field_problem(
                "progressPercentage",
                _("Progress percentage must be between zero and one hundred."),
            )
        object.__setattr__(self, "actual_start", _optional_date(self.actual_start, "actualStart"))
        object.__setattr__(self, "actual_finish", _optional_date(self.actual_finish, "actualFinish"))
        if self.actual_finish is not None and self.actual_start is None:
            raise _field_problem("actualFinish", _("Actual finish requires actual start."))
        if (
            self.actual_start is not None
            and self.actual_finish is not None
            and self.actual_finish < self.actual_start
        ):
            raise _field_problem(
                "actualFinish",
                _("Actual finish cannot be earlier than actual start."),
            )
        object.__setattr__(self, "risk", _optional_text(self.risk, "risk", 240))
        object.__setattr__(self, "note", _optional_text(self.note, "note", 1000))
        object.__setattr__(
            self,
            "evidence",
            _typed_tuple(
                self.evidence,
                ToolingMilestoneFileEvidence,
                "evidence",
                maximum=20,
            ),
        )
        for identities in (
            [value.global_id for value in self.evidence],
            [value.file_revision_global_id for value in self.evidence],
        ):
            if len(identities) != len(set(identities)):
                raise _field_problem("evidence", _("Milestone evidence must be unique."))
        if not isinstance(self.reported_by_member, ProjectMemberResponsibility):
            raise _field_problem(
                "reportedByMember",
                _("Select the exact internal Project member reporting this observation."),
            )
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "projectGlobalId": str(self.project_global_id),
                "planRevisionGlobalId": str(self.plan_revision_global_id),
                "milestoneGlobalId": str(self.milestone_global_id),
                "observationVersion": self.observation_version,
            }
        )
        if self.observation_key_hash not in (None, "", expected_key):
            raise _field_problem(
                "observationKeyHash",
                _("The milestone observation key does not match."),
            )
        object.__setattr__(self, "observation_key_hash", expected_key)

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "planRevisionGlobalId": str(self.plan_revision_global_id),
            "planRevisionSnapshotHash": self.plan_revision_snapshot_hash,
            "milestoneGlobalId": str(self.milestone_global_id),
            "milestoneSnapshotHash": self.milestone_snapshot_hash,
            "observationVersion": self.observation_version,
            "predecessorGlobalId": (
                str(self.predecessor_global_id) if self.predecessor_global_id else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "progressPercentage": self.progress_percentage,
            "actualStart": self.actual_start.isoformat() if self.actual_start else None,
            "actualFinish": self.actual_finish.isoformat() if self.actual_finish else None,
            "risk": self.risk,
            "note": self.note,
            "evidence": [value.snapshot_payload() for value in self.evidence],
            "reportedByMember": self.reported_by_member.snapshot_payload(),
            "observationKeyHash": self.observation_key_hash,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class DesignReleaseEvidenceCapability:
    state: DesignReleaseEvidenceState
    reason_code: DesignReleaseBlockedReason | None
    items: tuple[ReleasedDocumentEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.state, DesignReleaseEvidenceState):
            raise _field_problem("designRelease.state", _("Select a supported value."))
        object.__setattr__(
            self,
            "items",
            _typed_tuple(self.items, ReleasedDocumentEvidence, "designRelease.items", maximum=50),
        )
        if self.state is DesignReleaseEvidenceState.SATISFIED:
            valid = self.reason_code is None and bool(self.items)
        else:
            valid = isinstance(self.reason_code, DesignReleaseBlockedReason) and not self.items
        if not valid:
            raise _field_problem(
                "designRelease",
                _("Design release evidence capability has an invalid shape."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "reasonCode": self.reason_code.value if self.reason_code else None,
            "items": [value.snapshot_payload() for value in self.items],
        }


@dataclass(frozen=True, slots=True)
class ManufacturingAuthorizationUnavailable:
    state: str = "unavailable"
    reason_code: str = "tooling_lifecycle_policy_unavailable"

    def __post_init__(self) -> None:
        if (
            self.state != "unavailable"
            or self.reason_code != "tooling_lifecycle_policy_unavailable"
        ):
            raise _field_problem(
                "manufacturingAuthorization",
                _("Manufacturing authorization must remain unavailable."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {"state": self.state, "reasonCode": self.reason_code}


def design_release_capability(
    expected_revision_hashes: tuple[tuple[UUID, str], ...],
    released: tuple[ReleasedDocumentEvidence, ...],
) -> DesignReleaseEvidenceCapability:
    expected = tuple((_uuid(value[0], "revisionGlobalId"), _hash(value[1], "revisionSnapshotHash")) for value in expected_revision_hashes)
    if not expected:
        return DesignReleaseEvidenceCapability(
            DesignReleaseEvidenceState.BLOCKED,
            DesignReleaseBlockedReason.NO_DESIGN_DOCUMENTS,
            (),
        )
    if len({value[0] for value in expected}) != len(expected):
        raise _field_problem("designDocumentRevisions", _("Design Document revisions must be unique."))
    observed = _typed_tuple(released, ReleasedDocumentEvidence, "released", maximum=50)
    expected_set = set(expected)
    observed_set = {
        (value.revision_global_id, value.revision_snapshot_hash) for value in observed
    }
    if expected_set != observed_set or len(observed) != len(observed_set):
        return DesignReleaseEvidenceCapability(
            DesignReleaseEvidenceState.BLOCKED,
            DesignReleaseBlockedReason.RELEASE_EVIDENCE_INCOMPLETE,
            (),
        )
    return DesignReleaseEvidenceCapability(
        DesignReleaseEvidenceState.SATISFIED,
        None,
        tuple(sorted(observed, key=lambda value: str(value.revision_global_id))),
    )


@dataclass(frozen=True, slots=True)
class FormalSupplierReference:
    source_object_id: str
    target_version: str
    supplier_code: str
    supplier_name: str

    def __post_init__(self) -> None:
        for fieldname, maximum in (
            ("source_object_id", 128),
            ("target_version", 128),
            ("supplier_code", 128),
            ("supplier_name", 200),
        ):
            object.__setattr__(
                self,
                fieldname,
                _key(getattr(self, fieldname), _camel(fieldname), maximum)
                if fieldname != "supplier_name"
                else _text(getattr(self, fieldname), "supplierName", maximum),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceObjectId": self.source_object_id,
            "targetVersion": self.target_version,
            "supplierCode": self.supplier_code,
            "supplierName": self.supplier_name,
        }


@dataclass(frozen=True, slots=True)
class ErpActualCostRow:
    tooling_master_global_id: UUID
    source_row_id: str
    source_row_version: str
    supplier_source_object_id: str
    purchase_order_source_id: str
    purchase_receipt_source_id: str
    purchase_invoice_source_id: str
    actual_cost_source_id: str
    cost_type_code: str
    posting_date: date
    currency: str
    amount: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tooling_master_global_id",
            _uuid(self.tooling_master_global_id, "toolingMasterGlobalId"),
        )
        for fieldname in (
            "source_row_id",
            "source_row_version",
            "supplier_source_object_id",
            "purchase_order_source_id",
            "purchase_receipt_source_id",
            "purchase_invoice_source_id",
            "actual_cost_source_id",
            "cost_type_code",
        ):
            object.__setattr__(
                self,
                fieldname,
                _key(getattr(self, fieldname), _camel(fieldname), 128),
            )
        object.__setattr__(self, "posting_date", _date(self.posting_date, "postingDate"))
        object.__setattr__(self, "currency", _currency(self.currency, "currency"))
        object.__setattr__(self, "amount", _decimal(self.amount, "amount", positive=False))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "sourceRowId": self.source_row_id,
            "sourceRowVersion": self.source_row_version,
            "supplierSourceObjectId": self.supplier_source_object_id,
            "purchaseOrderSourceId": self.purchase_order_source_id,
            "purchaseReceiptSourceId": self.purchase_receipt_source_id,
            "purchaseInvoiceSourceId": self.purchase_invoice_source_id,
            "actualCostSourceId": self.actual_cost_source_id,
            "costTypeCode": self.cost_type_code,
            "postingDate": self.posting_date.isoformat(),
            "currency": self.currency,
            "amount": self.amount,
        }


@dataclass(frozen=True, slots=True)
class ErpActualCostSummary:
    tooling_master_global_id: UUID
    supplier_source_object_id: str
    cost_type_code: str
    currency: str
    amount: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tooling_master_global_id",
            _uuid(self.tooling_master_global_id, "toolingMasterGlobalId"),
        )
        object.__setattr__(
            self,
            "supplier_source_object_id",
            _key(self.supplier_source_object_id, "supplierSourceObjectId", 128),
        )
        object.__setattr__(self, "cost_type_code", _key(self.cost_type_code, "costTypeCode", 128))
        object.__setattr__(self, "currency", _currency(self.currency, "currency"))
        object.__setattr__(self, "amount", _decimal(self.amount, "amount", positive=False))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "supplierSourceObjectId": self.supplier_source_object_id,
            "costTypeCode": self.cost_type_code,
            "currency": self.currency,
            "amount": self.amount,
        }


@dataclass(frozen=True, slots=True)
class ToolingProcurementCostUnavailable:
    source_system: str = "ERPNEXT"
    editable_in: str = "ERPNEXT"
    state: str = "unavailable"
    reason_code: str = "erp_projection_unavailable"

    def __post_init__(self) -> None:
        if self.snapshot_payload() != {
            "sourceSystem": "ERPNEXT",
            "editableIn": "ERPNEXT",
            "state": "unavailable",
            "reasonCode": "erp_projection_unavailable",
        }:
            raise _field_problem(
                "erpProjection",
                _("The default ERP projection must remain unavailable and read-only."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceSystem": self.source_system,
            "editableIn": self.editable_in,
            "state": self.state,
            "reasonCode": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class ToolingProcurementCostAvailable:
    tooling_master_global_id: UUID
    observed_at: datetime
    target_version: str
    supplier: FormalSupplierReference
    rows: tuple[ErpActualCostRow, ...]
    summaries: tuple[ErpActualCostSummary, ...]
    source_system: str = "ERPNEXT"
    editable_in: str = "ERPNEXT"
    state: str = "available"

    def __post_init__(self) -> None:
        if (
            self.source_system != "ERPNEXT"
            or self.editable_in != "ERPNEXT"
            or self.state != "available"
        ):
            raise _field_problem(
                "erpProjection",
                _("An available ERP projection must remain target-confirmed and read-only."),
            )
        object.__setattr__(
            self,
            "tooling_master_global_id",
            _uuid(self.tooling_master_global_id, "toolingMasterGlobalId"),
        )
        object.__setattr__(self, "observed_at", _datetime(self.observed_at, "observedAt"))
        object.__setattr__(self, "target_version", _key(self.target_version, "targetVersion", 128))
        if not isinstance(self.supplier, FormalSupplierReference):
            raise _field_problem("supplier", _("Enter a valid formal Supplier reference."))
        object.__setattr__(self, "rows", _typed_tuple(self.rows, ErpActualCostRow, "rows", maximum=1000))
        if not self.rows:
            raise _field_problem("rows", _("A confirmed ERP projection requires source rows."))
        identities = [(value.source_row_id, value.source_row_version) for value in self.rows]
        if len(identities) != len(set(identities)):
            raise _field_problem("rows", _("ERP source row versions must be unique."))
        currencies = {value.currency for value in self.rows}
        if len(currencies) != 1:
            raise _field_problem("rows", _("ERP actual-cost rows must use one currency."))
        for value in self.rows:
            if (
                value.tooling_master_global_id != self.tooling_master_global_id
                or value.supplier_source_object_id != self.supplier.source_object_id
            ):
                raise _field_problem(
                    "rows",
                    _("ERP source rows do not match the exact Tooling Master and Supplier."),
                )
        object.__setattr__(
            self,
            "summaries",
            _typed_tuple(self.summaries, ErpActualCostSummary, "summaries", maximum=1000),
        )
        if self.summaries != aggregate_actual_costs(self.rows):
            raise _field_problem(
                "summaries",
                _("ERP actual-cost summaries do not match the exact source rows."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceSystem": self.source_system,
            "editableIn": self.editable_in,
            "state": self.state,
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "observedAt": _utc_text(self.observed_at),
            "targetVersion": self.target_version,
            "supplier": self.supplier.snapshot_payload(),
            "rows": [value.snapshot_payload() for value in self.rows],
            "summaries": [value.snapshot_payload() for value in self.summaries],
        }


ToolingProcurementCostProjection = (
    ToolingProcurementCostUnavailable | ToolingProcurementCostAvailable
)


def aggregate_actual_costs(
    rows: tuple[ErpActualCostRow, ...],
) -> tuple[ErpActualCostSummary, ...]:
    values = _typed_tuple(rows, ErpActualCostRow, "rows", maximum=1000)
    totals: dict[tuple[UUID, str, str, str], Decimal] = {}
    for value in values:
        key = (
            value.tooling_master_global_id,
            value.supplier_source_object_id,
            value.cost_type_code,
            value.currency,
        )
        totals[key] = totals.get(key, Decimal("0")) + Decimal(value.amount)
    return tuple(
        ErpActualCostSummary(
            tooling_master_global_id=key[0],
            supplier_source_object_id=key[1],
            cost_type_code=key[2],
            currency=key[3],
            amount=_decimal_text(total),
        )
        for key, total in sorted(
            totals.items(),
            key=lambda item: tuple(str(part) for part in item[0]),
        )
    )


def validate_manufacturing_plan_successor(
    previous: ToolingManufacturingPlanRevision,
    successor: ToolingManufacturingPlanRevision,
) -> None:
    if (
        successor.tenant_id != previous.tenant_id
        or successor.project_global_id != previous.project_global_id
        or successor.tooling_master_global_id != previous.tooling_master_global_id
        or successor.plan_global_id != previous.plan_global_id
        or successor.plan_version != previous.plan_version + 1
        or successor.predecessor_global_id != previous.global_id
        or successor.predecessor_snapshot_hash != previous.snapshot_hash
    ):
        raise _field_problem(
            "planVersion",
            _("The manufacturing plan does not advance its exact predecessor."),
        )


def validate_milestone_observation_successor(
    previous: ToolingManufacturingMilestoneObservation,
    successor: ToolingManufacturingMilestoneObservation,
) -> None:
    if (
        successor.tenant_id != previous.tenant_id
        or successor.project_global_id != previous.project_global_id
        or successor.tooling_master_global_id != previous.tooling_master_global_id
        or successor.plan_revision_global_id != previous.plan_revision_global_id
        or successor.plan_revision_snapshot_hash != previous.plan_revision_snapshot_hash
        or successor.milestone_global_id != previous.milestone_global_id
        or successor.milestone_snapshot_hash != previous.milestone_snapshot_hash
        or successor.observation_version != previous.observation_version + 1
        or successor.predecessor_global_id != previous.global_id
        or successor.predecessor_snapshot_hash != previous.snapshot_hash
    ):
        raise _field_problem(
            "observationVersion",
            _("The milestone observation does not advance its exact predecessor."),
        )


def manufacturing_plan_from_snapshot(value: object) -> ToolingManufacturingPlanRevision:
    record = _record(
        value,
        "planSnapshot",
        {
            "schemaVersion", "globalId", "planGlobalId", "tenantId",
            "projectGlobalId", "toolingMasterGlobalId", "toolingRevisionGlobalId",
            "toolingRevisionSnapshotHash", "planVersion", "predecessorGlobalId",
            "predecessorSnapshotHash", "sourcingStrategy", "responsibleMember",
            "engineeringEstimate", "budget", "evidence", "designReleaseEvidence",
            "milestones", "reason", "versionKeyHash", "createdByUserId",
            "createdAt", "requestId", "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return ToolingManufacturingPlanRevision(
        global_id=record["globalId"],
        plan_global_id=record["planGlobalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        tooling_revision_global_id=record["toolingRevisionGlobalId"],
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        plan_version=record["planVersion"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        sourcing_strategy=_enum(record["sourcingStrategy"], ToolingSourcingStrategy, "sourcingStrategy"),
        responsible_member=_member_from_dict(record["responsibleMember"], "responsibleMember"),
        engineering_estimate=_money_from_dict(record["engineeringEstimate"], "engineeringEstimate"),
        budget=_money_from_dict(record["budget"], "budget"),
        evidence=tuple(
            _plan_evidence_from_dict(item)
            for item in _list(record["evidence"], "evidence", maximum=4)
        ),
        design_release_evidence=tuple(
            _released_document_from_dict(item, "designReleaseEvidence")
            for item in _list(record["designReleaseEvidence"], "designReleaseEvidence", maximum=50)
        ),
        milestones=tuple(
            _milestone_from_dict(item)
            for item in _list(record["milestones"], "milestones", maximum=100)
        ),
        reason=record["reason"],
        version_key_hash=record["versionKeyHash"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
    )


def milestone_observation_from_snapshot(
    value: object,
) -> ToolingManufacturingMilestoneObservation:
    record = _record(
        value,
        "observationSnapshot",
        {
            "schemaVersion", "globalId", "tenantId", "projectGlobalId",
            "toolingMasterGlobalId", "planRevisionGlobalId",
            "planRevisionSnapshotHash", "milestoneGlobalId",
            "milestoneSnapshotHash", "observationVersion", "predecessorGlobalId",
            "predecessorSnapshotHash", "progressPercentage", "actualStart",
            "actualFinish", "risk", "note", "evidence", "reportedByMember",
            "observationKeyHash", "createdAt", "requestId", "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return ToolingManufacturingMilestoneObservation(
        global_id=record["globalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        plan_revision_global_id=record["planRevisionGlobalId"],
        plan_revision_snapshot_hash=record["planRevisionSnapshotHash"],
        milestone_global_id=record["milestoneGlobalId"],
        milestone_snapshot_hash=record["milestoneSnapshotHash"],
        observation_version=record["observationVersion"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        progress_percentage=record["progressPercentage"],
        actual_start=record["actualStart"],
        actual_finish=record["actualFinish"],
        risk=record["risk"],
        note=record["note"],
        evidence=tuple(
            _file_evidence_from_dict(item)
            for item in _list(record["evidence"], "evidence", maximum=20)
        ),
        reported_by_member=_member_from_dict(record["reportedByMember"], "reportedByMember"),
        observation_key_hash=record["observationKeyHash"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
    )


def procurement_cost_projection_from_snapshot(
    value: object,
) -> ToolingProcurementCostProjection:
    if not isinstance(value, dict):
        raise _field_problem("erpProjection", _("Enter a valid closed object."))
    if value.get("state") == "unavailable":
        _record(
            value,
            "erpProjection",
            {"sourceSystem", "editableIn", "state", "reasonCode"},
        )
        if value != ToolingProcurementCostUnavailable().snapshot_payload():
            raise _field_problem("erpProjection", _("Enter a valid unavailable ERP projection."))
        return ToolingProcurementCostUnavailable()
    record = _record(
        value,
        "erpProjection",
        {
            "sourceSystem", "editableIn", "state", "toolingMasterGlobalId",
            "observedAt", "targetVersion", "supplier", "rows", "summaries",
        },
    )
    if (
        record["sourceSystem"] != "ERPNEXT"
        or record["editableIn"] != "ERPNEXT"
        or record["state"] != "available"
    ):
        raise _field_problem("erpProjection", _("Enter a valid read-only ERP projection."))
    return ToolingProcurementCostAvailable(
        tooling_master_global_id=record["toolingMasterGlobalId"],
        observed_at=_datetime(record["observedAt"], "observedAt"),
        target_version=record["targetVersion"],
        supplier=_supplier_from_dict(record["supplier"]),
        rows=tuple(
            _cost_row_from_dict(item)
            for item in _list(record["rows"], "rows", maximum=1000)
        ),
        summaries=tuple(
            _cost_summary_from_dict(item)
            for item in _list(record["summaries"], "summaries", maximum=1000)
        ),
    )


def _validate_milestone_graph(
    milestones: tuple[ToolingManufacturingMilestone, ...],
) -> None:
    identities = [value.global_id for value in milestones]
    if len(identities) != len(set(identities)):
        raise _field_problem("milestones", _("Milestone global IDs must be unique."))
    seen: set[UUID] = set()
    for sequence, milestone in enumerate(milestones, start=1):
        if milestone.sequence != sequence:
            raise _field_problem(
                "milestones",
                _("Milestones must use contiguous dependency order."),
            )
        if milestone.global_id in milestone.predecessor_global_ids or not set(
            milestone.predecessor_global_ids
        ).issubset(seen):
            raise _field_problem(
                "milestones",
                _("Milestone dependencies must reference earlier milestones in this plan."),
            )
        seen.add(milestone.global_id)


def _member_from_dict(value: object, path: str) -> ProjectMemberResponsibility:
    record = _record(value, path, {"globalId", "userId", "optimisticVersion"})
    return ProjectMemberResponsibility(
        global_id=record["globalId"],
        user_id=record["userId"],
        optimistic_version=record["optimisticVersion"],
    )


def _money_from_dict(value: object, path: str) -> PlanningMoney | None:
    if value is None:
        return None
    record = _record(value, path, {"amount", "currency"})
    return PlanningMoney(amount=record["amount"], currency=record["currency"])


def _released_document_from_dict(value: object, path: str) -> ReleasedDocumentEvidence:
    record = _record(
        value,
        path,
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


def _plan_evidence_from_dict(value: object) -> ToolingPlanEvidence:
    record = _record(value, "evidence", {"role", "document"})
    return ToolingPlanEvidence(
        role=_enum(record["role"], ToolingPlanEvidenceRole, "evidence.role"),
        document=_released_document_from_dict(record["document"], "evidence.document"),
    )


def _milestone_from_dict(value: object) -> ToolingManufacturingMilestone:
    record = _record(
        value,
        "milestone",
        {
            "globalId", "sequence", "category", "plannedStart", "plannedFinish",
            "responsibilityKind", "responsibleMember", "predecessorGlobalIds",
            "snapshotHash",
        },
    )
    milestone = ToolingManufacturingMilestone(
        global_id=record["globalId"],
        sequence=record["sequence"],
        category=_enum(record["category"], ToolingMilestoneCategory, "milestone.category"),
        planned_start=record["plannedStart"],
        planned_finish=record["plannedFinish"],
        responsibility_kind=_enum(
            record["responsibilityKind"],
            ToolingMilestoneResponsibilityKind,
            "milestone.responsibilityKind",
        ),
        responsible_member=(
            _member_from_dict(record["responsibleMember"], "milestone.responsibleMember")
            if record["responsibleMember"] is not None
            else None
        ),
        predecessor_global_ids=tuple(
            _list(record["predecessorGlobalIds"], "milestone.predecessorGlobalIds", maximum=20)
        ),
    )
    if record["snapshotHash"] != milestone.snapshot_hash:
        raise _field_problem("milestone.snapshotHash", _("Milestone Snapshot Hash does not match."))
    return milestone


def _file_evidence_from_dict(value: object) -> ToolingMilestoneFileEvidence:
    record = _record(
        value,
        "evidence",
        {
            "globalId", "role", "fileRevisionGlobalId", "fileOptimisticVersion",
            "frappeContentHash", "fileName", "mimeType", "sizeBytes", "sha256",
        },
    )
    return ToolingMilestoneFileEvidence(
        global_id=record["globalId"],
        role=_enum(record["role"], ToolingMilestoneEvidenceRole, "evidence.role"),
        file_revision_global_id=record["fileRevisionGlobalId"],
        file_optimistic_version=record["fileOptimisticVersion"],
        frappe_content_hash=record["frappeContentHash"],
        file_name=record["fileName"],
        mime_type=record["mimeType"],
        size_bytes=record["sizeBytes"],
        sha256=record["sha256"],
    )


def _supplier_from_dict(value: object) -> FormalSupplierReference:
    record = _record(
        value,
        "supplier",
        {"sourceObjectId", "targetVersion", "supplierCode", "supplierName"},
    )
    return FormalSupplierReference(
        source_object_id=record["sourceObjectId"],
        target_version=record["targetVersion"],
        supplier_code=record["supplierCode"],
        supplier_name=record["supplierName"],
    )


def _cost_row_from_dict(value: object) -> ErpActualCostRow:
    record = _record(
        value,
        "row",
        {
            "toolingMasterGlobalId", "sourceRowId", "sourceRowVersion",
            "supplierSourceObjectId", "purchaseOrderSourceId",
            "purchaseReceiptSourceId", "purchaseInvoiceSourceId",
            "actualCostSourceId", "costTypeCode", "postingDate", "currency",
            "amount",
        },
    )
    return ErpActualCostRow(
        tooling_master_global_id=record["toolingMasterGlobalId"],
        source_row_id=record["sourceRowId"],
        source_row_version=record["sourceRowVersion"],
        supplier_source_object_id=record["supplierSourceObjectId"],
        purchase_order_source_id=record["purchaseOrderSourceId"],
        purchase_receipt_source_id=record["purchaseReceiptSourceId"],
        purchase_invoice_source_id=record["purchaseInvoiceSourceId"],
        actual_cost_source_id=record["actualCostSourceId"],
        cost_type_code=record["costTypeCode"],
        posting_date=record["postingDate"],
        currency=record["currency"],
        amount=record["amount"],
    )


def _cost_summary_from_dict(value: object) -> ErpActualCostSummary:
    record = _record(
        value,
        "summary",
        {
            "toolingMasterGlobalId", "supplierSourceObjectId", "costTypeCode",
            "currency", "amount",
        },
    )
    return ErpActualCostSummary(
        tooling_master_global_id=record["toolingMasterGlobalId"],
        supplier_source_object_id=record["supplierSourceObjectId"],
        cost_type_code=record["costTypeCode"],
        currency=record["currency"],
        amount=record["amount"],
    )


def _record(value: object, path: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _field_problem(path, _("Enter a valid closed object."))
    return value


def _list(value: object, path: str, *, maximum: int) -> list[object]:
    if not isinstance(value, list) or len(value) > maximum:
        raise _field_problem(path, _("Enter a valid bounded list."))
    return value


def _typed_tuple(
    value: object,
    expected_type: type[_T],
    path: str,
    *,
    maximum: int,
) -> tuple[_T, ...]:
    if not isinstance(value, (tuple, list)):
        raise _field_problem(path, _("Enter a valid bounded list."))
    normalized = tuple(value)
    if len(normalized) > maximum or not all(isinstance(item, expected_type) for item in normalized):
        raise _field_problem(path, _("Enter a valid bounded list."))
    return normalized


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
    if len(result) != len(set(result)):
        raise _field_problem(path, _("Global IDs must be unique within this list."))
    return result


def _positive(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _field_problem(path, _("Enter a positive whole number."))
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
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32,128}", value):
        raise _field_problem(path, _("Enter a valid content hash."))
    return value


def _key(value: object, path: str, maximum: int) -> str:
    normalized = _text(value, path, maximum)
    if _KEY_PATTERN.fullmatch(normalized) is None:
        raise _field_problem(path, _("Use a valid key."))
    return normalized


def _currency(value: object, path: str) -> str:
    if not isinstance(value, str) or _CURRENCY_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a three-letter uppercase currency code."))
    return value


def _decimal(value: object, path: str, *, positive: bool) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a valid decimal amount."))
    try:
        result = Decimal(value.strip())
    except InvalidOperation as error:
        raise _field_problem(path, _("Enter a valid decimal amount.")) from error
    if (
        not result.is_finite()
        or (positive and result <= 0)
        or len(value.strip()) > 32
        or result.adjusted() > 24
        or result.adjusted() < -24
    ):
        raise _field_problem(path, _("Enter a valid decimal amount."))
    return _decimal_text(result)


def _decimal_text(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    return normalized if "." in normalized else f"{normalized}.0"


def _date(value: object, path: str) -> date:
    if isinstance(value, datetime):
        raise _field_problem(path, _("Enter a valid date."))
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid date.")) from error


def _optional_date(value: object, path: str) -> date | None:
    return None if value in (None, "") else _date(value, path)


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


def _require_predecessor(
    version: int,
    predecessor_global_id: UUID | None,
    predecessor_snapshot_hash: str | None,
    path: str,
) -> None:
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
