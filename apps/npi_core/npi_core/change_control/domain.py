from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Iterable
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps this domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


CHANGE_CONTROL_SCHEMA_VERSION = 1
FORMAL_CHANGE_DOCTYPE = "Engineering Change Request"
MAX_REFERENCES = 1_000

_HASH = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ImpactCategory(StrEnum):
    PRODUCT = "product"
    DRAWING = "drawing"
    EBOM = "ebom"
    MBOM = "mbom"
    TOOLING = "tooling"
    PROCESS = "process"
    QUALITY = "quality"
    INVENTORY_WIP = "inventory_wip"
    SUPPLIER = "supplier"
    COST = "cost"
    DELIVERY = "delivery"
    CUSTOMER = "customer"


class ImpactConclusion(StrEnum):
    PENDING = "pending"
    NOT_AFFECTED = "not_affected"
    AFFECTED = "affected"


class AffectedObjectKind(StrEnum):
    ENGINEERING_PART_REVISION = "engineering_part_revision"
    ENGINEERING_BOM_REVISION = "engineering_bom_revision"
    MANUFACTURING_BOM_REVISION = "manufacturing_bom_revision"
    CONTROLLED_DOCUMENT_REVISION = "controlled_document_revision"
    DOCUMENT_BASELINE = "document_baseline"
    TOOLING_REVISION = "tooling_revision"
    TOOLING_SET_BINDING = "tooling_set_binding"
    TRIAL_PLAN_REVISION = "trial_plan_revision"
    TRIAL_CONCLUSION_REVISION = "trial_conclusion_revision"
    RELEASED_TRIAL_SUMMARY_REVISION = "released_trial_summary_revision"
    GATE_REVIEW_CYCLE = "gate_review_cycle"
    ERP_ITEM = "erp_item"
    ERP_FORMAL_QUALITY = "erp_formal_quality"
    OTHER_CONTROLLED_REFERENCE = "other_controlled_reference"


class ImplementationTaskKind(StrEnum):
    DESIGN = "design"
    TOOL_MODIFICATION = "tool_modification"
    PROCUREMENT = "procurement"
    TRIAL = "trial"
    QUALITY = "quality"
    CUTOVER = "cutover"


class EffectivityKind(StrEnum):
    DATE = "date"
    ORDER = "order"
    BATCH = "batch"
    INVENTORY_DEPLETION = "inventory_depletion"
    SERIAL_OR_SHOT = "serial_or_shot"
    CUSTOMER_APPROVAL = "customer_approval"


class DispositionScope(StrEnum):
    OLD_INVENTORY = "old_inventory"
    WORK_IN_PROGRESS = "work_in_progress"
    IN_TRANSIT = "in_transit"
    OLD_LABEL_OR_FILE = "old_label_or_file"
    CUSTOMER_INVENTORY = "customer_inventory"


class DispositionKind(StrEnum):
    USE_AS_IS = "use_as_is"
    REWORK = "rework"
    SCRAP = "scrap"
    RETURN_TO_SUPPLIER = "return_to_supplier"
    SEGREGATE = "segregate"
    RELABEL = "relabel"
    CUSTOMER_APPROVAL = "customer_approval"
    OTHER = "other"


class RevalidationKind(StrEnum):
    DESIGN_REVIEW = "design_review"
    TOOL_MODIFICATION = "tool_modification"
    PROCUREMENT = "procurement"
    TRIAL = "trial"
    FAI = "fai"
    QUALITY = "quality"
    CUSTOMER_APPROVAL = "customer_approval"
    NPI_GATE_REVIEW = "npi_gate_review"
    CUTOVER = "cutover"


class RevalidationState(StrEnum):
    REQUIRED = "required"
    IN_PROGRESS = "in_progress"
    SATISFIED = "satisfied"
    WAIVED = "waived"


class EngineeringChangeState(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    READY_TO_CLOSE = "ready_to_close"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class EngineeringChangeEventType(StrEnum):
    CREATED = "created"
    REVISED = "revised"
    FORMAL_OBSERVATION_LINKED = "formal_observation_linked"
    READY_TO_CLOSE = "ready_to_close"
    CLOSED = "closed"
    CANCELLED = "cancelled"


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise _problem(path, _("Enter a valid global ID."))
    return value


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _problem(path, _("Enter a valid value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _email(value: object, path: str) -> str:
    normalized = _text(value, path, 254).casefold()
    if _EMAIL.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid user ID."))
    return normalized


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _problem(path, _("Enter a non-negative integer."))
    return value


def _datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a valid timestamp."))
    return value.astimezone(UTC)


def _optional_date(value: object, path: str) -> date | None:
    if value is None:
        return None
    if type(value) is not date:
        raise _problem(path, _("Enter a valid date."))
    return value


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool):
        raise _problem(path, _("Enter a valid decimal value."))
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _problem(path, _("Enter a valid decimal value.")) from None
    if not normalized.is_finite():
        raise _problem(path, _("Enter a finite decimal value."))
    return normalized.normalize()


def _enum(value: object, expected: type[StrEnum], path: str):
    if not isinstance(value, expected):
        raise _problem(path, _("Select a supported value."))
    return value


def _items(value: object, expected: type, path: str) -> tuple:
    if not isinstance(value, (tuple, list)):
        raise _problem(path, _("Enter a valid list."))
    result = tuple(value)
    if len(result) > MAX_REFERENCES or any(
        not isinstance(item, expected) for item in result
    ):
        raise _problem(path, _("Enter a valid list."))
    return result


def _uuid_references(value: object, path: str) -> tuple[UUID, ...]:
    if not isinstance(value, (tuple, list)):
        raise _problem(path, _("Enter a valid list."))
    result = tuple(_uuid(item, f"{path}[{index}]") for index, item in enumerate(value))
    if len(result) > MAX_REFERENCES or len(set(result)) != len(result):
        raise _problem(path, _("Values must be unique."))
    return result


def _unique(values: Iterable[object], path: str) -> None:
    materialized = tuple(values)
    if len(set(materialized)) != len(materialized):
        raise _problem(path, _("Values must be unique."))


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FormalChangeObservation:
    document_name: str
    raw_status: str
    source_version: str
    source_modified_at: datetime
    source_hash: str
    observed_at: datetime
    doctype: str = FORMAL_CHANGE_DOCTYPE

    def __post_init__(self) -> None:
        if self.doctype != FORMAL_CHANGE_DOCTYPE:
            raise _problem("formalChange.doctype", _("Select the supported formal change type."))
        object.__setattr__(self, "document_name", _text(self.document_name, "formalChange.documentName", 140))
        object.__setattr__(self, "raw_status", _text(self.raw_status, "formalChange.rawStatus", 140))
        object.__setattr__(self, "source_version", _text(self.source_version, "formalChange.sourceVersion", 140))
        object.__setattr__(self, "source_modified_at", _datetime(self.source_modified_at, "formalChange.sourceModifiedAt"))
        object.__setattr__(self, "source_hash", _hash(self.source_hash, "formalChange.sourceHash"))
        object.__setattr__(self, "observed_at", _datetime(self.observed_at, "formalChange.observedAt"))

    def payload(self) -> dict[str, object]:
        return {
            "doctype": self.doctype,
            "documentName": self.document_name,
            "rawStatus": self.raw_status,
            "sourceVersion": self.source_version,
            "sourceModifiedAt": _utc(self.source_modified_at),
            "sourceHash": self.source_hash,
            "observedAt": _utc(self.observed_at),
        }


@dataclass(frozen=True, slots=True)
class ImpactAssessment:
    category: ImpactCategory
    conclusion: ImpactConclusion
    responsible_user_id: str
    rationale: str
    evidence_reference_global_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", _enum(self.category, ImpactCategory, "impact.category"))
        object.__setattr__(self, "conclusion", _enum(self.conclusion, ImpactConclusion, "impact.conclusion"))
        object.__setattr__(self, "responsible_user_id", _email(self.responsible_user_id, "impact.responsibleUserId"))
        object.__setattr__(self, "rationale", _text(self.rationale, "impact.rationale", 4_000))
        object.__setattr__(self, "evidence_reference_global_ids", _uuid_references(self.evidence_reference_global_ids, "impact.evidenceReferenceGlobalIds"))

    def payload(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "conclusion": self.conclusion.value,
            "responsibleUserId": self.responsible_user_id,
            "rationale": self.rationale,
            "evidenceReferenceGlobalIds": [str(value) for value in self.evidence_reference_global_ids],
        }


@dataclass(frozen=True, slots=True)
class AffectedObjectVersion:
    category: ImpactCategory
    kind: AffectedObjectKind
    object_global_id: UUID
    prior_version_global_id: UUID | None
    prior_snapshot_hash: str | None
    successor_version_global_id: UUID | None
    successor_snapshot_hash: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", _enum(self.category, ImpactCategory, "affectedObject.category"))
        object.__setattr__(self, "kind", _enum(self.kind, AffectedObjectKind, "affectedObject.kind"))
        object.__setattr__(self, "object_global_id", _uuid(self.object_global_id, "affectedObject.objectGlobalId"))
        object.__setattr__(self, "prior_version_global_id", _optional_uuid(self.prior_version_global_id, "affectedObject.priorVersionGlobalId"))
        object.__setattr__(self, "prior_snapshot_hash", _optional_hash(self.prior_snapshot_hash, "affectedObject.priorSnapshotHash"))
        object.__setattr__(self, "successor_version_global_id", _optional_uuid(self.successor_version_global_id, "affectedObject.successorVersionGlobalId"))
        object.__setattr__(self, "successor_snapshot_hash", _optional_hash(self.successor_snapshot_hash, "affectedObject.successorSnapshotHash"))
        prior = (self.prior_version_global_id, self.prior_snapshot_hash)
        successor = (self.successor_version_global_id, self.successor_snapshot_hash)
        if (prior[0] is None) != (prior[1] is None) or (successor[0] is None) != (successor[1] is None):
            raise _problem("affectedObject", _("A version reference must include its exact hash."))
        if prior[0] is None and successor[0] is None:
            raise _problem("affectedObject", _("Enter a prior or successor version."))
        if prior == successor:
            raise _problem("affectedObject", _("Prior and successor versions must differ."))

    def payload(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "kind": self.kind.value,
            "objectGlobalId": str(self.object_global_id),
            "priorVersionGlobalId": None if self.prior_version_global_id is None else str(self.prior_version_global_id),
            "priorSnapshotHash": self.prior_snapshot_hash,
            "successorVersionGlobalId": None if self.successor_version_global_id is None else str(self.successor_version_global_id),
            "successorSnapshotHash": self.successor_snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ImplementationTaskLink:
    kind: ImplementationTaskKind
    work_item_global_id: UUID
    purpose: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(self.kind, ImplementationTaskKind, "implementationTask.kind"))
        object.__setattr__(self, "work_item_global_id", _uuid(self.work_item_global_id, "implementationTask.workItemGlobalId"))
        object.__setattr__(self, "purpose", _text(self.purpose, "implementationTask.purpose", 500))

    def payload(self) -> dict[str, object]:
        return {"kind": self.kind.value, "workItemGlobalId": str(self.work_item_global_id), "purpose": self.purpose}


@dataclass(frozen=True, slots=True)
class EffectivityRule:
    kind: EffectivityKind
    effective_date: date | None = None
    selector_reference: str | None = None
    validation_evidence_global_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(self.kind, EffectivityKind, "effectivity.kind"))
        object.__setattr__(self, "effective_date", _optional_date(self.effective_date, "effectivity.effectiveDate"))
        object.__setattr__(self, "selector_reference", _optional_text(self.selector_reference, "effectivity.selectorReference", 280))
        object.__setattr__(self, "validation_evidence_global_id", _optional_uuid(self.validation_evidence_global_id, "effectivity.validationEvidenceGlobalId"))
        if self.kind is EffectivityKind.DATE:
            if self.effective_date is None or self.selector_reference is not None:
                raise _problem("effectivity", _("Date effectivity requires only an effective date."))
        elif self.effective_date is not None or self.selector_reference is None:
            raise _problem("effectivity", _("This effectivity method requires only a selector reference."))

    def payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "effectiveDate": None if self.effective_date is None else self.effective_date.isoformat(),
            "selectorReference": self.selector_reference,
            "validationEvidenceGlobalId": None if self.validation_evidence_global_id is None else str(self.validation_evidence_global_id),
        }


@dataclass(frozen=True, slots=True)
class DispositionDecision:
    scope: DispositionScope
    decision: DispositionKind
    approved_by_user_id: str
    approval_evidence_global_id: UUID
    execution_evidence_global_id: UUID | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", _enum(self.scope, DispositionScope, "disposition.scope"))
        object.__setattr__(self, "decision", _enum(self.decision, DispositionKind, "disposition.decision"))
        object.__setattr__(self, "approved_by_user_id", _email(self.approved_by_user_id, "disposition.approvedByUserId"))
        object.__setattr__(self, "approval_evidence_global_id", _uuid(self.approval_evidence_global_id, "disposition.approvalEvidenceGlobalId"))
        object.__setattr__(self, "execution_evidence_global_id", _optional_uuid(self.execution_evidence_global_id, "disposition.executionEvidenceGlobalId"))
        object.__setattr__(self, "note", _optional_text(self.note, "disposition.note", 2_000))

    def payload(self) -> dict[str, object]:
        return {
            "scope": self.scope.value,
            "decision": self.decision.value,
            "approvedByUserId": self.approved_by_user_id,
            "approvalEvidenceGlobalId": str(self.approval_evidence_global_id),
            "executionEvidenceGlobalId": None if self.execution_evidence_global_id is None else str(self.execution_evidence_global_id),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class RevalidationRequirement:
    kind: RevalidationKind
    state: RevalidationState
    responsible_user_id: str
    work_item_global_id: UUID | None = None
    gate_review_global_id: UUID | None = None
    evidence_reference_global_ids: tuple[UUID, ...] = ()
    waiver_approval_global_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(self.kind, RevalidationKind, "revalidation.kind"))
        object.__setattr__(self, "state", _enum(self.state, RevalidationState, "revalidation.state"))
        object.__setattr__(self, "responsible_user_id", _email(self.responsible_user_id, "revalidation.responsibleUserId"))
        object.__setattr__(self, "work_item_global_id", _optional_uuid(self.work_item_global_id, "revalidation.workItemGlobalId"))
        object.__setattr__(self, "gate_review_global_id", _optional_uuid(self.gate_review_global_id, "revalidation.gateReviewGlobalId"))
        object.__setattr__(self, "evidence_reference_global_ids", _uuid_references(self.evidence_reference_global_ids, "revalidation.evidenceReferenceGlobalIds"))
        object.__setattr__(self, "waiver_approval_global_id", _optional_uuid(self.waiver_approval_global_id, "revalidation.waiverApprovalGlobalId"))
        if self.state is RevalidationState.SATISFIED and not self.evidence_reference_global_ids:
            raise _problem("revalidation.evidenceReferenceGlobalIds", _("Satisfied revalidation requires evidence."))
        if self.state is RevalidationState.WAIVED and (
            not self.evidence_reference_global_ids or self.waiver_approval_global_id is None
        ):
            raise _problem("revalidation", _("Waived revalidation requires evidence and an approval."))
        if self.state is not RevalidationState.WAIVED and self.waiver_approval_global_id is not None:
            raise _problem("revalidation.waiverApprovalGlobalId", _("Only waived revalidation may reference a waiver approval."))

    @property
    def complete(self) -> bool:
        return self.state in {RevalidationState.SATISFIED, RevalidationState.WAIVED}

    def payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "state": self.state.value,
            "responsibleUserId": self.responsible_user_id,
            "workItemGlobalId": None if self.work_item_global_id is None else str(self.work_item_global_id),
            "gateReviewGlobalId": None if self.gate_review_global_id is None else str(self.gate_review_global_id),
            "evidenceReferenceGlobalIds": [str(value) for value in self.evidence_reference_global_ids],
            "waiverApprovalGlobalId": None if self.waiver_approval_global_id is None else str(self.waiver_approval_global_id),
        }


@dataclass(frozen=True, slots=True)
class CostSummary:
    currency: str
    engineering_cost: Decimal = Decimal("0")
    tooling_cost: Decimal = Decimal("0")
    scrap_cost: Decimal = Decimal("0")
    logistics_cost: Decimal = Decimal("0")
    downtime_minutes: int = 0
    delivery_impact_days: int = 0

    def __post_init__(self) -> None:
        currency = _text(self.currency, "cost.currency", 3).upper()
        if _CURRENCY.fullmatch(currency) is None:
            raise _problem("cost.currency", _("Enter a valid currency code."))
        object.__setattr__(self, "currency", currency)
        for fieldname in ("engineering_cost", "tooling_cost", "scrap_cost", "logistics_cost"):
            normalized = _decimal(getattr(self, fieldname), f"cost.{fieldname}")
            if normalized < 0:
                raise _problem(f"cost.{fieldname}", _("Enter a non-negative value."))
            object.__setattr__(self, fieldname, normalized)
        object.__setattr__(self, "downtime_minutes", _nonnegative(self.downtime_minutes, "cost.downtimeMinutes"))
        object.__setattr__(self, "delivery_impact_days", _nonnegative(self.delivery_impact_days, "cost.deliveryImpactDays"))

    def payload(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "engineeringCost": _decimal_text(self.engineering_cost),
            "toolingCost": _decimal_text(self.tooling_cost),
            "scrapCost": _decimal_text(self.scrap_cost),
            "logisticsCost": _decimal_text(self.logistics_cost),
            "downtimeMinutes": self.downtime_minutes,
            "deliveryImpactDays": self.delivery_impact_days,
        }


@dataclass(frozen=True, slots=True)
class ClosureEvidence:
    new_versions_released: bool
    erp_update_observed: bool
    old_versions_withdrawn: bool
    effectivity_validated: bool
    dispositions_executed: bool
    evidence_reference_global_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        for fieldname in (
            "new_versions_released",
            "erp_update_observed",
            "old_versions_withdrawn",
            "effectivity_validated",
            "dispositions_executed",
        ):
            if type(getattr(self, fieldname)) is not bool:
                raise _problem(f"closure.{fieldname}", _("Enter a valid true or false value."))
        object.__setattr__(self, "evidence_reference_global_ids", _uuid_references(self.evidence_reference_global_ids, "closure.evidenceReferenceGlobalIds"))

    @property
    def complete(self) -> bool:
        return all(
            (
                self.new_versions_released,
                self.erp_update_observed,
                self.old_versions_withdrawn,
                self.effectivity_validated,
                self.dispositions_executed,
                bool(self.evidence_reference_global_ids),
            )
        )

    def payload(self) -> dict[str, object]:
        return {
            "newVersionsReleased": self.new_versions_released,
            "erpUpdateObserved": self.erp_update_observed,
            "oldVersionsWithdrawn": self.old_versions_withdrawn,
            "effectivityValidated": self.effectivity_validated,
            "dispositionsExecuted": self.dispositions_executed,
            "evidenceReferenceGlobalIds": [str(value) for value in self.evidence_reference_global_ids],
        }


@dataclass(frozen=True, slots=True)
class EngineeringChangeRevision:
    global_id: UUID
    change_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    revision: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    state: EngineeringChangeState
    title: str
    reason: str
    formal_change: FormalChangeObservation | None
    impact_assessments: tuple[ImpactAssessment, ...]
    affected_objects: tuple[AffectedObjectVersion, ...]
    implementation_tasks: tuple[ImplementationTaskLink, ...]
    effectivity_rules: tuple[EffectivityRule, ...]
    dispositions: tuple[DispositionDecision, ...]
    revalidation_requirements: tuple[RevalidationRequirement, ...]
    cost_summary: CostSummary
    closure_evidence: ClosureEvidence | None
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(self, "change_global_id", _uuid(self.change_global_id, "changeGlobalId"))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 140))
        object.__setattr__(self, "project_global_id", _uuid(self.project_global_id, "projectGlobalId"))
        object.__setattr__(self, "revision", _positive(self.revision, "revision"))
        object.__setattr__(self, "predecessor_global_id", _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"))
        object.__setattr__(self, "predecessor_snapshot_hash", _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"))
        if self.revision == 1 and (self.predecessor_global_id is not None or self.predecessor_snapshot_hash is not None):
            raise _problem("predecessorGlobalId", _("The first revision cannot have a predecessor."))
        if self.revision > 1 and (self.predecessor_global_id is None or self.predecessor_snapshot_hash is None):
            raise _problem("predecessorGlobalId", _("A successor revision requires its exact predecessor."))
        object.__setattr__(self, "state", _enum(self.state, EngineeringChangeState, "state"))
        object.__setattr__(self, "title", _text(self.title, "title", 280))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 4_000))
        if self.formal_change is not None and not isinstance(self.formal_change, FormalChangeObservation):
            raise _problem("formalChange", _("Enter a valid formal change observation."))
        object.__setattr__(self, "impact_assessments", _items(self.impact_assessments, ImpactAssessment, "impactAssessments"))
        categories = tuple(item.category for item in self.impact_assessments)
        if set(categories) != set(ImpactCategory) or len(categories) != len(ImpactCategory):
            raise _problem("impactAssessments", _("Assess every required impact category exactly once."))
        object.__setattr__(self, "affected_objects", _items(self.affected_objects, AffectedObjectVersion, "affectedObjects"))
        object.__setattr__(self, "implementation_tasks", _items(self.implementation_tasks, ImplementationTaskLink, "implementationTasks"))
        object.__setattr__(self, "effectivity_rules", _items(self.effectivity_rules, EffectivityRule, "effectivityRules"))
        object.__setattr__(self, "dispositions", _items(self.dispositions, DispositionDecision, "dispositions"))
        object.__setattr__(self, "revalidation_requirements", _items(self.revalidation_requirements, RevalidationRequirement, "revalidationRequirements"))
        _unique(
            ((item.kind, item.object_global_id) for item in self.affected_objects),
            "affectedObjects",
        )
        _unique(
            ((item.kind, item.work_item_global_id) for item in self.implementation_tasks),
            "implementationTasks",
        )
        _unique((item.kind for item in self.effectivity_rules), "effectivityRules")
        _unique((item.scope for item in self.dispositions), "dispositions")
        _unique(
            (item.kind for item in self.revalidation_requirements),
            "revalidationRequirements",
        )
        impact_by_category = {item.category: item for item in self.impact_assessments}
        for item in self.affected_objects:
            if impact_by_category[item.category].conclusion is not ImpactConclusion.AFFECTED:
                raise _problem("affectedObjects", _("Affected objects require an affected category conclusion."))
        if not isinstance(self.cost_summary, CostSummary):
            raise _problem("costSummary", _("Enter a valid cost summary."))
        if self.closure_evidence is not None and not isinstance(self.closure_evidence, ClosureEvidence):
            raise _problem("closureEvidence", _("Enter valid closure evidence."))
        object.__setattr__(self, "created_by_user_id", _email(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        trace = _text(self.trace_id, "traceId", 140)
        if _KEY.fullmatch(trace) is None:
            raise _problem("traceId", _("Enter a valid trace ID."))
        object.__setattr__(self, "trace_id", trace)
        if self.state in {EngineeringChangeState.READY_TO_CLOSE, EngineeringChangeState.CLOSED} and not self.ready_to_close:
            raise _problem("closureEvidence", _("Complete all closeout evidence and revalidation before closing the change."))

    @property
    def ready_to_close(self) -> bool:
        return bool(
            self.formal_change is not None
            and self.closure_evidence is not None
            and self.closure_evidence.complete
            and all(item.complete for item in self.revalidation_requirements)
            and bool(self.effectivity_rules)
            and all(item.validation_evidence_global_id is not None for item in self.effectivity_rules)
            and all(item.execution_evidence_global_id is not None for item in self.dispositions)
            and all(item.conclusion is not ImpactConclusion.PENDING for item in self.impact_assessments)
        )

    def revision_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": CHANGE_CONTROL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "changeGlobalId": str(self.change_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "revision": self.revision,
            "predecessorGlobalId": None if self.predecessor_global_id is None else str(self.predecessor_global_id),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "state": self.state.value,
            "title": self.title,
            "reason": self.reason,
            "formalChange": None if self.formal_change is None else self.formal_change.payload(),
            "impactAssessments": [item.payload() for item in self.impact_assessments],
            "affectedObjects": [item.payload() for item in self.affected_objects],
            "implementationTasks": [item.payload() for item in self.implementation_tasks],
            "effectivityRules": [item.payload() for item in self.effectivity_rules],
            "dispositions": [item.payload() for item in self.dispositions],
            "revalidationRequirements": [item.payload() for item in self.revalidation_requirements],
            "costSummary": self.cost_summary.payload(),
            "closureEvidence": None if self.closure_evidence is None else self.closure_evidence.payload(),
            "readyToClose": self.ready_to_close,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.revision_payload())

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "changeGlobalId": str(self.change_global_id),
                "revision": self.revision,
                "tenantId": self.tenant_id,
            }
        )

    def successor(
        self,
        *,
        global_id: UUID,
        state: EngineeringChangeState | None = None,
        reason: str,
        created_by_user_id: str,
        created_at: datetime,
        request_id: UUID,
        trace_id: str,
        formal_change: FormalChangeObservation | None = None,
        impact_assessments: tuple[ImpactAssessment, ...] | None = None,
        affected_objects: tuple[AffectedObjectVersion, ...] | None = None,
        implementation_tasks: tuple[ImplementationTaskLink, ...] | None = None,
        effectivity_rules: tuple[EffectivityRule, ...] | None = None,
        dispositions: tuple[DispositionDecision, ...] | None = None,
        revalidation_requirements: tuple[RevalidationRequirement, ...] | None = None,
        cost_summary: CostSummary | None = None,
        closure_evidence: ClosureEvidence | None = None,
    ) -> EngineeringChangeRevision:
        return replace(
            self,
            global_id=global_id,
            revision=self.revision + 1,
            predecessor_global_id=self.global_id,
            predecessor_snapshot_hash=self.snapshot_hash,
            state=self.state if state is None else state,
            reason=reason,
            created_by_user_id=created_by_user_id,
            created_at=created_at,
            request_id=request_id,
            trace_id=trace_id,
            formal_change=self.formal_change if formal_change is None else formal_change,
            impact_assessments=self.impact_assessments if impact_assessments is None else impact_assessments,
            affected_objects=self.affected_objects if affected_objects is None else affected_objects,
            implementation_tasks=self.implementation_tasks if implementation_tasks is None else implementation_tasks,
            effectivity_rules=self.effectivity_rules if effectivity_rules is None else effectivity_rules,
            dispositions=self.dispositions if dispositions is None else dispositions,
            revalidation_requirements=self.revalidation_requirements if revalidation_requirements is None else revalidation_requirements,
            cost_summary=self.cost_summary if cost_summary is None else cost_summary,
            closure_evidence=self.closure_evidence if closure_evidence is None else closure_evidence,
        )


@dataclass(frozen=True, slots=True)
class EngineeringChangeEvent:
    global_id: UUID
    change_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    revision_global_id: UUID
    revision: int
    revision_snapshot_hash: str
    event_type: EngineeringChangeEventType
    actor_user_id: str
    occurred_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "event.globalId"))
        object.__setattr__(self, "change_global_id", _uuid(self.change_global_id, "event.changeGlobalId"))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "event.tenantId", 140))
        object.__setattr__(self, "project_global_id", _uuid(self.project_global_id, "event.projectGlobalId"))
        object.__setattr__(self, "revision_global_id", _uuid(self.revision_global_id, "event.revisionGlobalId"))
        object.__setattr__(self, "revision", _positive(self.revision, "event.revision"))
        object.__setattr__(self, "revision_snapshot_hash", _hash(self.revision_snapshot_hash, "event.revisionSnapshotHash"))
        object.__setattr__(self, "event_type", _enum(self.event_type, EngineeringChangeEventType, "event.eventType"))
        object.__setattr__(self, "actor_user_id", _email(self.actor_user_id, "event.actorUserId"))
        object.__setattr__(self, "occurred_at", _datetime(self.occurred_at, "event.occurredAt"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "event.requestId"))
        trace = _text(self.trace_id, "event.traceId", 140)
        if _KEY.fullmatch(trace) is None:
            raise _problem("event.traceId", _("Enter a valid trace ID."))
        object.__setattr__(self, "trace_id", trace)

    def event_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": CHANGE_CONTROL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "changeGlobalId": str(self.change_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "revisionGlobalId": str(self.revision_global_id),
            "revision": self.revision,
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "eventType": self.event_type.value,
            "actorUserId": self.actor_user_id,
            "occurredAt": _utc(self.occurred_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def event_hash(self) -> str:
        return sha256_json(self.event_payload())
