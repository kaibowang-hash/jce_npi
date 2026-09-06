from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import (
    TOOLING_SCHEMA_VERSION,
    ToolingRequirementKind,
    sha256_json,
)
from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility

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
_T = TypeVar("_T")


class ToolingAcceptanceCategory(StrEnum):
    TECHNICAL = "technical"
    QUALITY = "quality"
    CYCLE_CAPACITY = "cycle_capacity"
    SPARES_MAINTENANCE = "spares_maintenance"
    DOCUMENTS = "documents"
    WARRANTY_RESPONSIBILITY = "warranty_responsibility"
    COST = "cost"
    SAFETY_INTERFACE = "safety_interface"
    ASSET_LOCATION = "asset_location"


class ToolingEvidenceDisposition(StrEnum):
    EVIDENCE_RECORDED = "evidence_recorded"
    EVIDENCE_MISSING = "evidence_missing"
    NOT_APPLICABLE_ASSERTED = "not_applicable_asserted"


class ToolingAcceptanceEvidenceRole(StrEnum):
    CHECKLIST = "checklist"
    ACTION = "action"
    APPROVAL_REFERENCE = "approval_reference"
    CUSTOMER_AUTHORIZATION = "customer_authorization"
    QUOTE = "quote"
    REPAIR_VERIFICATION = "repair_verification"


class ToolingAssetActionKind(StrEnum):
    MOVE = "move"
    LOAN = "loan"
    RETURN = "return"
    ARCHIVE = "archive"
    SCRAP = "scrap"


class ToolingSpareKind(StrEnum):
    CRITICAL_SPARE = "critical_spare"
    WEAR_PART = "wear_part"


@dataclass(frozen=True, slots=True)
class ToolingAcceptanceFileEvidence:
    global_id: UUID
    role: ToolingAcceptanceEvidenceRole
    file_revision_global_id: UUID
    file_optimistic_version: int
    frappe_content_hash: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "evidence.globalId"))
        if not isinstance(self.role, ToolingAcceptanceEvidenceRole):
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
class ToolingAcceptanceChecklistItem:
    global_id: UUID
    category: ToolingAcceptanceCategory
    requirement_key: str
    requirement_statement: str
    disposition: ToolingEvidenceDisposition
    responsible_member: ProjectMemberResponsibility | None
    evidence: tuple[ToolingAcceptanceFileEvidence, ...]
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "checklist.globalId"))
        if not isinstance(self.category, ToolingAcceptanceCategory):
            raise _field_problem("checklist.category", _("Select a supported acceptance category."))
        object.__setattr__(self, "requirement_key", _key(self.requirement_key, "checklist.requirementKey", 128))
        object.__setattr__(
            self,
            "requirement_statement",
            _text(self.requirement_statement, "checklist.requirementStatement", 1_000),
        )
        if not isinstance(self.disposition, ToolingEvidenceDisposition):
            raise _field_problem("checklist.disposition", _("Select a supported evidence disposition."))
        if self.responsible_member is not None and not isinstance(
            self.responsible_member, ProjectMemberResponsibility
        ):
            raise _field_problem("checklist.responsibleMember", _("Select a valid Project member."))
        object.__setattr__(
            self,
            "evidence",
            _typed_tuple(self.evidence, ToolingAcceptanceFileEvidence, "checklist.evidence", maximum=20),
        )
        _unique((item.global_id for item in self.evidence), "checklist.evidence")
        if any(
            item.role is not ToolingAcceptanceEvidenceRole.CHECKLIST
            for item in self.evidence
        ):
            raise _field_problem(
                "checklist.evidence.role",
                _("Checklist evidence must use the checklist evidence role."),
            )
        object.__setattr__(self, "note", _optional_text(self.note, "checklist.note", 2_000))
        if self.disposition is ToolingEvidenceDisposition.EVIDENCE_RECORDED and not self.evidence:
            raise _field_problem(
                "checklist.evidence",
                _("Recorded checklist evidence requires at least one exact File Revision."),
            )
        if self.disposition is ToolingEvidenceDisposition.EVIDENCE_MISSING and self.evidence:
            raise _field_problem(
                "checklist.evidence",
                _("Missing checklist evidence cannot contain a File Revision."),
            )
        if self.disposition is ToolingEvidenceDisposition.NOT_APPLICABLE_ASSERTED and not self.note:
            raise _field_problem(
                "checklist.note",
                _("A not-applicable assertion requires an exact reason."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "category": self.category.value,
            "requirementKey": self.requirement_key,
            "requirementStatement": self.requirement_statement,
            "disposition": self.disposition.value,
            "responsibleMember": (
                self.responsible_member.snapshot_payload() if self.responsible_member else None
            ),
            "evidence": [item.snapshot_payload() for item in self.evidence],
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class ToolingAssetActionEvidence:
    global_id: UUID
    action_kind: ToolingAssetActionKind
    reason: str
    approval_reference: str
    proposed_effective_date: date | None
    evidence: tuple[ToolingAcceptanceFileEvidence, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "assetAction.globalId"))
        if not isinstance(self.action_kind, ToolingAssetActionKind):
            raise _field_problem("assetAction.actionKind", _("Select a supported Asset action."))
        object.__setattr__(self, "reason", _text(self.reason, "assetAction.reason", 2_000))
        object.__setattr__(
            self,
            "approval_reference",
            _text(self.approval_reference, "assetAction.approvalReference", 500),
        )
        object.__setattr__(
            self,
            "proposed_effective_date",
            _optional_date(self.proposed_effective_date, "assetAction.proposedEffectiveDate"),
        )
        object.__setattr__(
            self,
            "evidence",
            _typed_tuple(self.evidence, ToolingAcceptanceFileEvidence, "assetAction.evidence", maximum=20),
        )
        if not self.evidence:
            raise _field_problem(
                "assetAction.evidence",
                _("Asset action evidence requires at least one exact File Revision."),
            )
        _unique((item.global_id for item in self.evidence), "assetAction.evidence")
        if any(
            item.role
            not in {
                ToolingAcceptanceEvidenceRole.ACTION,
                ToolingAcceptanceEvidenceRole.APPROVAL_REFERENCE,
            }
            for item in self.evidence
        ):
            raise _field_problem(
                "assetAction.evidence.role",
                _("Asset action evidence must use an action or approval-reference role."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "actionKind": self.action_kind.value,
            "reason": self.reason,
            "approvalReference": self.approval_reference,
            "proposedEffectiveDate": (
                self.proposed_effective_date.isoformat() if self.proposed_effective_date else None
            ),
            "erpExecution": {
                "state": "unavailable",
                "reasonCode": "erp_asset_action_execution_unavailable",
            },
            "evidence": [item.snapshot_payload() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class ToolingSpareRecommendation:
    global_id: UUID
    recommendation_key: str
    kind: ToolingSpareKind
    description: str
    recommended_minimum_quantity: str
    unit: str
    supplier_source_system: str | None = None
    supplier_source_object_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "spare.globalId"))
        object.__setattr__(
            self,
            "recommendation_key",
            _key(self.recommendation_key, "spare.recommendationKey", 128),
        )
        if not isinstance(self.kind, ToolingSpareKind):
            raise _field_problem("spare.kind", _("Select a supported spare kind."))
        object.__setattr__(self, "description", _text(self.description, "spare.description", 1_000))
        object.__setattr__(
            self,
            "recommended_minimum_quantity",
            _decimal(self.recommended_minimum_quantity, "spare.recommendedMinimumQuantity", positive=True),
        )
        object.__setattr__(self, "unit", _key(self.unit, "spare.unit", 32))
        if (self.supplier_source_system is None) != (self.supplier_source_object_id is None):
            raise _field_problem(
                "spare.supplier",
                _("Supplier source and object identity must be supplied together."),
            )
        if self.supplier_source_system is not None:
            if self.supplier_source_system != "ERPNEXT":
                raise _field_problem(
                    "spare.supplierSourceSystem",
                    _("Formal Supplier references must use the ERPNext source."),
                )
            object.__setattr__(
                self,
                "supplier_source_object_id",
                _key(self.supplier_source_object_id, "spare.supplierSourceObjectId", 128),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "recommendationKey": self.recommendation_key,
            "kind": self.kind.value,
            "description": self.description,
            "recommendedMinimumQuantity": self.recommended_minimum_quantity,
            "unit": self.unit,
            "supplierReference": (
                {
                    "sourceSystem": self.supplier_source_system,
                    "sourceObjectId": self.supplier_source_object_id,
                }
                if self.supplier_source_system
                else {
                    "state": "unavailable",
                    "reasonCode": "formal_supplier_projection_unavailable",
                }
            ),
            "formalItemAndInventory": {
                "state": "unavailable",
                "reasonCode": "erp_spare_inventory_projection_unavailable",
            },
        }


@dataclass(frozen=True, slots=True)
class ToolingRepairEvidence:
    global_id: UUID
    authorization_reference: str
    quote_reference: str | None
    quote_currency: str | None
    quote_amount: str | None
    responsible_member: ProjectMemberResponsibility
    downtime_impact_hours: str
    detail: str
    customer_authorization_evidence: tuple[ToolingAcceptanceFileEvidence, ...]
    verification_evidence: tuple[ToolingAcceptanceFileEvidence, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "repair.globalId"))
        object.__setattr__(
            self,
            "authorization_reference",
            _text(self.authorization_reference, "repair.authorizationReference", 500),
        )
        object.__setattr__(self, "quote_reference", _optional_text(self.quote_reference, "repair.quoteReference", 500))
        if (self.quote_currency is None) != (self.quote_amount is None):
            raise _field_problem(
                "repair.quote",
                _("Repair quote currency and amount must be supplied together."),
            )
        if self.quote_currency is not None:
            object.__setattr__(self, "quote_currency", _currency(self.quote_currency, "repair.quoteCurrency"))
            object.__setattr__(self, "quote_amount", _decimal(self.quote_amount, "repair.quoteAmount", positive=False))
        if not isinstance(self.responsible_member, ProjectMemberResponsibility):
            raise _field_problem("repair.responsibleMember", _("Select a valid Project member."))
        object.__setattr__(
            self,
            "downtime_impact_hours",
            _decimal(self.downtime_impact_hours, "repair.downtimeImpactHours", positive=False),
        )
        object.__setattr__(self, "detail", _text(self.detail, "repair.detail", 4_000))
        for fieldname in ("customer_authorization_evidence", "verification_evidence"):
            value = _typed_tuple(
                getattr(self, fieldname),
                ToolingAcceptanceFileEvidence,
                _camel(fieldname),
                maximum=20,
            )
            object.__setattr__(self, fieldname, value)
            _unique((item.global_id for item in value), _camel(fieldname))
        if any(
            item.role is not ToolingAcceptanceEvidenceRole.CUSTOMER_AUTHORIZATION
            for item in self.customer_authorization_evidence
        ):
            raise _field_problem(
                "repair.customerAuthorizationEvidence.role",
                _("Customer authorization evidence must use the customer-authorization role."),
            )
        if any(
            item.role is not ToolingAcceptanceEvidenceRole.REPAIR_VERIFICATION
            for item in self.verification_evidence
        ):
            raise _field_problem(
                "repair.verificationEvidence.role",
                _("Repair verification evidence must use the repair-verification role."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "authorizationReference": self.authorization_reference,
            "quoteReference": self.quote_reference,
            "quote": (
                {"currency": self.quote_currency, "amount": self.quote_amount}
                if self.quote_currency
                else None
            ),
            "responsibleMember": self.responsible_member.snapshot_payload(),
            "downtimeImpactHours": self.downtime_impact_hours,
            "detail": self.detail,
            "customerAuthorizationEvidence": [
                item.snapshot_payload() for item in self.customer_authorization_evidence
            ],
            "verificationEvidence": [
                item.snapshot_payload() for item in self.verification_evidence
            ],
            "erpRepairResult": {
                "state": "unavailable",
                "reasonCode": "erp_repair_projection_unavailable",
            },
        }


@dataclass(frozen=True, slots=True)
class ToolingAcceptanceEvidenceRevision:
    global_id: UUID
    acceptance_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_master_snapshot_hash: str
    tooling_set_global_id: UUID
    tooling_set_snapshot_hash: str
    tooling_requirement_kind: ToolingRequirementKind
    set_revision_binding_global_id: UUID
    set_revision_binding_snapshot_hash: str
    tooling_revision_global_id: UUID
    tooling_revision_number: int
    tooling_revision_snapshot_hash: str
    acceptance_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    checklist: tuple[ToolingAcceptanceChecklistItem, ...]
    asset_actions: tuple[ToolingAssetActionEvidence, ...]
    spare_recommendations: tuple[ToolingSpareRecommendation, ...]
    repairs: tuple[ToolingRepairEvidence, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    schema_version: int = TOOLING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != TOOLING_SCHEMA_VERSION:
            raise _field_problem("schemaVersion", _("Select the supported Tooling schema version."))
        for fieldname in (
            "global_id",
            "acceptance_global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "set_revision_binding_global_id",
            "tooling_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128))
        for fieldname in (
            "tooling_master_snapshot_hash",
            "tooling_set_snapshot_hash",
            "set_revision_binding_snapshot_hash",
            "tooling_revision_snapshot_hash",
        ):
            object.__setattr__(self, fieldname, _hash(getattr(self, fieldname), _camel(fieldname)))
        if not isinstance(self.tooling_requirement_kind, ToolingRequirementKind):
            raise _field_problem("toolingRequirementKind", _("Select a supported Tooling Requirement kind."))
        object.__setattr__(
            self,
            "tooling_revision_number",
            _positive(self.tooling_revision_number, "toolingRevisionNumber"),
        )
        object.__setattr__(self, "acceptance_version", _positive(self.acceptance_version, "acceptanceVersion"))
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
            self.acceptance_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "predecessorGlobalId",
        )
        for fieldname, expected_type, maximum in (
            ("checklist", ToolingAcceptanceChecklistItem, 200),
            ("asset_actions", ToolingAssetActionEvidence, 100),
            ("spare_recommendations", ToolingSpareRecommendation, 200),
            ("repairs", ToolingRepairEvidence, 100),
        ):
            value = _typed_tuple(getattr(self, fieldname), expected_type, _camel(fieldname), maximum=maximum)
            object.__setattr__(self, fieldname, value)
            _unique((item.global_id for item in value), _camel(fieldname))
        _unique(
            (item.recommendation_key for item in self.spare_recommendations),
            "spareRecommendations.recommendationKey",
        )
        categories = {item.category for item in self.checklist}
        missing = set(ToolingAcceptanceCategory) - categories
        if missing:
            raise _field_problem(
                "checklist",
                _("Every required acceptance category must contain at least one checklist item."),
            )
        keys = [item.requirement_key for item in self.checklist]
        if len(set(keys)) != len(keys):
            raise _field_problem("checklist", _("Acceptance checklist requirement keys must be unique."))
        evidence_ids = [
            evidence.global_id
            for item in self.checklist
            for evidence in item.evidence
        ]
        evidence_ids.extend(
            evidence.global_id
            for action in self.asset_actions
            for evidence in action.evidence
        )
        evidence_ids.extend(
            evidence.global_id
            for repair in self.repairs
            for evidence in (
                *repair.customer_authorization_evidence,
                *repair.verification_evidence,
            )
        )
        _unique(evidence_ids, "evidence")
        if self.tooling_requirement_kind is ToolingRequirementKind.CUSTOMER_OWNED_INTAKE:
            for repair in self.repairs:
                if not repair.customer_authorization_evidence:
                    raise _field_problem(
                        "repairs.customerAuthorizationEvidence",
                        _("Customer-owned Tooling repairs require exact customer authorization evidence."),
                    )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId", 128))

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "acceptanceGlobalId": str(self.acceptance_global_id),
                "acceptanceVersion": self.acceptance_version,
            }
        )

    @property
    def category_coverage(self) -> list[dict[str, object]]:
        return [
            {
                "category": category.value,
                "itemCount": sum(1 for item in self.checklist if item.category is category),
                "recordedCount": sum(
                    1
                    for item in self.checklist
                    if item.category is category
                    and item.disposition is ToolingEvidenceDisposition.EVIDENCE_RECORDED
                ),
                "missingCount": sum(
                    1
                    for item in self.checklist
                    if item.category is category
                    and item.disposition is ToolingEvidenceDisposition.EVIDENCE_MISSING
                ),
                "notApplicableCount": sum(
                    1
                    for item in self.checklist
                    if item.category is category
                    and item.disposition is ToolingEvidenceDisposition.NOT_APPLICABLE_ASSERTED
                ),
            }
            for category in ToolingAcceptanceCategory
        ]

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "globalId": str(self.global_id),
            "acceptanceGlobalId": str(self.acceptance_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingMasterSnapshotHash": self.tooling_master_snapshot_hash,
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "toolingSetSnapshotHash": self.tooling_set_snapshot_hash,
            "toolingRequirementKind": self.tooling_requirement_kind.value,
            "setRevisionBindingGlobalId": str(self.set_revision_binding_global_id),
            "setRevisionBindingSnapshotHash": self.set_revision_binding_snapshot_hash,
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionNumber": self.tooling_revision_number,
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "acceptanceVersion": self.acceptance_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "checklist": [item.snapshot_payload() for item in self.checklist],
            "assetActions": [item.snapshot_payload() for item in self.asset_actions],
            "spareRecommendations": [
                item.snapshot_payload() for item in self.spare_recommendations
            ],
            "repairs": [item.snapshot_payload() for item in self.repairs],
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

    def public_dict(self) -> dict[str, object]:
        return {
            **self.snapshot_payload(),
            "snapshotHash": self.snapshot_hash,
            "categoryCoverage": self.category_coverage,
            "businessApproval": {
                "state": "unavailable",
                "reasonCode": "tooling_acceptance_policy_unavailable",
            },
        }


def validate_acceptance_successor(
    current: ToolingAcceptanceEvidenceRevision,
    successor: ToolingAcceptanceEvidenceRevision,
) -> None:
    if not isinstance(current, ToolingAcceptanceEvidenceRevision) or not isinstance(
        successor, ToolingAcceptanceEvidenceRevision
    ):
        raise _field_problem("acceptance", _("Enter valid Tooling acceptance evidence revisions."))
    for fieldname in (
        "acceptance_global_id",
        "tenant_id",
        "project_global_id",
        "tooling_master_global_id",
        "tooling_master_snapshot_hash",
        "tooling_set_global_id",
        "tooling_set_snapshot_hash",
        "tooling_requirement_kind",
        "set_revision_binding_global_id",
        "set_revision_binding_snapshot_hash",
        "tooling_revision_global_id",
        "tooling_revision_number",
        "tooling_revision_snapshot_hash",
    ):
        if getattr(current, fieldname) != getattr(successor, fieldname):
            raise _field_problem(
                _camel(fieldname),
                _("A successor acceptance revision cannot change its stable Tooling context."),
            )
    if successor.acceptance_version != current.acceptance_version + 1:
        raise _field_problem(
            "acceptanceVersion",
            _("A successor acceptance revision must increment the version by one."),
        )
    if (
        successor.predecessor_global_id != current.global_id
        or successor.predecessor_snapshot_hash != current.snapshot_hash
    ):
        raise _field_problem(
            "predecessorGlobalId",
            _("A successor acceptance revision must reference the exact current revision."),
        )


@dataclass(frozen=True, slots=True)
class ErpAssetMovementObservation:
    global_id: UUID
    action_kind: ToolingAssetActionKind
    from_location: str | None
    to_location: str | None
    occurred_at: datetime
    source_object_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "movement.globalId"))
        if not isinstance(self.action_kind, ToolingAssetActionKind):
            raise _field_problem("movement.actionKind", _("Select a supported Asset action."))
        object.__setattr__(self, "from_location", _optional_text(self.from_location, "movement.fromLocation", 255))
        object.__setattr__(self, "to_location", _optional_text(self.to_location, "movement.toLocation", 255))
        object.__setattr__(self, "occurred_at", _datetime(self.occurred_at, "movement.occurredAt"))
        object.__setattr__(self, "source_object_id", _key(self.source_object_id, "movement.sourceObjectId", 128))

    def public_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "actionKind": self.action_kind.value,
            "fromLocation": self.from_location,
            "toLocation": self.to_location,
            "occurredAt": _utc_text(self.occurred_at),
            "sourceObjectId": self.source_object_id,
        }


@dataclass(frozen=True, slots=True)
class ErpAssetRepairObservation:
    global_id: UUID
    summary: str
    downtime_hours: str
    completed_at: datetime
    source_object_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "repairObservation.globalId"))
        object.__setattr__(self, "summary", _text(self.summary, "repairObservation.summary", 2_000))
        object.__setattr__(
            self,
            "downtime_hours",
            _decimal(self.downtime_hours, "repairObservation.downtimeHours", positive=False),
        )
        object.__setattr__(self, "completed_at", _datetime(self.completed_at, "repairObservation.completedAt"))
        object.__setattr__(self, "source_object_id", _key(self.source_object_id, "repairObservation.sourceObjectId", 128))

    def public_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "summary": self.summary,
            "downtimeHours": self.downtime_hours,
            "completedAt": _utc_text(self.completed_at),
            "sourceObjectId": self.source_object_id,
        }


@dataclass(frozen=True, slots=True)
class ErpAssetSpareInventoryObservation:
    formal_item_id: str
    description: str
    stock_on_hand: str
    minimum_stock: str
    unit: str
    supplier_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "formal_item_id", _key(self.formal_item_id, "spareInventory.formalItemId", 128))
        object.__setattr__(self, "description", _text(self.description, "spareInventory.description", 1_000))
        object.__setattr__(self, "stock_on_hand", _decimal(self.stock_on_hand, "spareInventory.stockOnHand", positive=False))
        object.__setattr__(self, "minimum_stock", _decimal(self.minimum_stock, "spareInventory.minimumStock", positive=False))
        object.__setattr__(self, "unit", _key(self.unit, "spareInventory.unit", 32))
        object.__setattr__(self, "supplier_id", _optional_key(self.supplier_id, "spareInventory.supplierId", 128))

    def public_dict(self) -> dict[str, object]:
        return {
            "formalItemId": self.formal_item_id,
            "description": self.description,
            "stockOnHand": self.stock_on_hand,
            "minimumStock": self.minimum_stock,
            "unit": self.unit,
            "supplierId": self.supplier_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingAssetProjectionUnavailable:
    source_system: str = "ERPNEXT"
    editable_in: str = "ERPNEXT"
    state: str = "unavailable"
    reason_code: str = "erp_asset_projection_unavailable"

    def __post_init__(self) -> None:
        if (
            self.source_system != "ERPNEXT"
            or self.editable_in != "ERPNEXT"
            or self.state != "unavailable"
            or self.reason_code != "erp_asset_projection_unavailable"
        ):
            raise _field_problem("assetProjection", _("The unavailable ERP Asset projection is invalid."))

    def public_dict(self) -> dict[str, object]:
        return {
            "sourceSystem": self.source_system,
            "editableIn": self.editable_in,
            "state": self.state,
            "reasonCode": self.reason_code,
            "mappingCardinality": "zero_or_one_per_physical_set",
        }


@dataclass(frozen=True, slots=True)
class ToolingAssetProjectionAvailable:
    tooling_set_global_id: UUID
    mapping_version: int
    formal_asset_id: str
    target_version: str
    asset_state: str
    current_location: str
    shot_count: int
    expected_life_shots: int | None
    maintenance_due: date | None
    movements: tuple[ErpAssetMovementObservation, ...]
    repairs: tuple[ErpAssetRepairObservation, ...]
    spares: tuple[ErpAssetSpareInventoryObservation, ...]
    observation_global_id: UUID
    observation_hash: str
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "tooling_set_global_id", _uuid(self.tooling_set_global_id, "assetProjection.toolingSetGlobalId"))
        object.__setattr__(self, "mapping_version", _positive(self.mapping_version, "assetProjection.mappingVersion"))
        for fieldname, maximum in (
            ("formal_asset_id", 128),
            ("target_version", 128),
            ("asset_state", 128),
            ("current_location", 255),
        ):
            object.__setattr__(self, fieldname, _text(getattr(self, fieldname), _camel(fieldname), maximum))
        object.__setattr__(self, "shot_count", _nonnegative(self.shot_count, "assetProjection.shotCount"))
        if self.expected_life_shots is not None:
            object.__setattr__(self, "expected_life_shots", _positive(self.expected_life_shots, "assetProjection.expectedLifeShots"))
        object.__setattr__(self, "maintenance_due", _optional_date(self.maintenance_due, "assetProjection.maintenanceDue"))
        for fieldname, expected_type, maximum in (
            ("movements", ErpAssetMovementObservation, 200),
            ("repairs", ErpAssetRepairObservation, 200),
            ("spares", ErpAssetSpareInventoryObservation, 500),
        ):
            object.__setattr__(self, fieldname, _typed_tuple(getattr(self, fieldname), expected_type, _camel(fieldname), maximum=maximum))
        _unique((item.global_id for item in self.movements), "assetProjection.movements")
        _unique((item.global_id for item in self.repairs), "assetProjection.repairs")
        object.__setattr__(self, "observation_global_id", _uuid(self.observation_global_id, "assetProjection.observationGlobalId"))
        object.__setattr__(self, "observation_hash", _hash(self.observation_hash, "assetProjection.observationHash"))
        object.__setattr__(self, "observed_at", _datetime(self.observed_at, "assetProjection.observedAt"))

    def public_dict(self) -> dict[str, object]:
        return {
            "sourceSystem": "ERPNEXT",
            "editableIn": "ERPNEXT",
            "state": "available",
            "mappingCardinality": "zero_or_one_per_physical_set",
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "mappingVersion": self.mapping_version,
            "formalAssetId": self.formal_asset_id,
            "targetVersion": self.target_version,
            "assetState": self.asset_state,
            "currentLocation": self.current_location,
            "shotCount": self.shot_count,
            "expectedLifeShots": self.expected_life_shots,
            "maintenanceDue": self.maintenance_due.isoformat() if self.maintenance_due else None,
            "movements": [item.public_dict() for item in self.movements],
            "repairs": [item.public_dict() for item in self.repairs],
            "spares": [item.public_dict() for item in self.spares],
            "observationGlobalId": str(self.observation_global_id),
            "observationHash": self.observation_hash,
            "observedAt": _utc_text(self.observed_at),
        }


def acceptance_revision_from_snapshot(value: object) -> ToolingAcceptanceEvidenceRevision:
    record = _record(value, "acceptance", {
        "schemaVersion", "globalId", "acceptanceGlobalId", "tenantId", "projectGlobalId",
        "toolingMasterGlobalId", "toolingMasterSnapshotHash", "toolingSetGlobalId",
        "toolingSetSnapshotHash", "toolingRequirementKind", "setRevisionBindingGlobalId",
        "setRevisionBindingSnapshotHash", "toolingRevisionGlobalId",
        "toolingRevisionNumber", "toolingRevisionSnapshotHash", "acceptanceVersion",
        "predecessorGlobalId", "predecessorSnapshotHash", "checklist", "assetActions",
        "spareRecommendations", "repairs", "reason", "createdByUserId", "createdAt",
        "requestId", "traceId", "versionKeyHash",
    })
    result = ToolingAcceptanceEvidenceRevision(
        global_id=record["globalId"],
        acceptance_global_id=record["acceptanceGlobalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        tooling_master_snapshot_hash=record["toolingMasterSnapshotHash"],
        tooling_set_global_id=record["toolingSetGlobalId"],
        tooling_set_snapshot_hash=record["toolingSetSnapshotHash"],
        tooling_requirement_kind=ToolingRequirementKind(record["toolingRequirementKind"]),
        set_revision_binding_global_id=record["setRevisionBindingGlobalId"],
        set_revision_binding_snapshot_hash=record["setRevisionBindingSnapshotHash"],
        tooling_revision_global_id=record["toolingRevisionGlobalId"],
        tooling_revision_number=record["toolingRevisionNumber"],
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        acceptance_version=record["acceptanceVersion"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        checklist=tuple(_checklist_from_dict(item) for item in _list(record["checklist"], "checklist", 200)),
        asset_actions=tuple(_asset_action_from_dict(item) for item in _list(record["assetActions"], "assetActions", 100)),
        spare_recommendations=tuple(_spare_from_dict(item) for item in _list(record["spareRecommendations"], "spareRecommendations", 200)),
        repairs=tuple(_repair_from_dict(item) for item in _list(record["repairs"], "repairs", 100)),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=record["createdAt"],
        request_id=record["requestId"],
        trace_id=record["traceId"],
        schema_version=record["schemaVersion"],
    )
    if record["versionKeyHash"] != result.version_key_hash:
        raise _field_problem("versionKeyHash", _("The acceptance version key hash does not match."))
    return result


def _evidence_from_dict(value: object) -> ToolingAcceptanceFileEvidence:
    record = _record(value, "evidence", {
        "globalId", "role", "fileRevisionGlobalId", "fileOptimisticVersion",
        "frappeContentHash", "fileName", "mimeType", "sizeBytes", "sha256",
    })
    return ToolingAcceptanceFileEvidence(
        global_id=record["globalId"], role=ToolingAcceptanceEvidenceRole(record["role"]),
        file_revision_global_id=record["fileRevisionGlobalId"],
        file_optimistic_version=record["fileOptimisticVersion"],
        frappe_content_hash=record["frappeContentHash"], file_name=record["fileName"],
        mime_type=record["mimeType"], size_bytes=record["sizeBytes"], sha256=record["sha256"],
    )


def _member_from_dict(value: object) -> ProjectMemberResponsibility | None:
    if value is None:
        return None
    record = _record(value, "member", {"globalId", "userId", "optimisticVersion"})
    return ProjectMemberResponsibility(
        global_id=record["globalId"], user_id=record["userId"], optimistic_version=record["optimisticVersion"]
    )


def _checklist_from_dict(value: object) -> ToolingAcceptanceChecklistItem:
    record = _record(value, "checklist", {
        "globalId", "category", "requirementKey", "requirementStatement", "disposition",
        "responsibleMember", "evidence", "note",
    })
    return ToolingAcceptanceChecklistItem(
        global_id=record["globalId"], category=ToolingAcceptanceCategory(record["category"]),
        requirement_key=record["requirementKey"], requirement_statement=record["requirementStatement"],
        disposition=ToolingEvidenceDisposition(record["disposition"]),
        responsible_member=_member_from_dict(record["responsibleMember"]),
        evidence=tuple(_evidence_from_dict(item) for item in _list(record["evidence"], "checklist.evidence", 20)),
        note=record["note"],
    )


def _asset_action_from_dict(value: object) -> ToolingAssetActionEvidence:
    record = _record(value, "assetAction", {
        "globalId", "actionKind", "reason", "approvalReference", "proposedEffectiveDate",
        "erpExecution", "evidence",
    })
    expected = {"state": "unavailable", "reasonCode": "erp_asset_action_execution_unavailable"}
    if record["erpExecution"] != expected:
        raise _field_problem("assetAction.erpExecution", _("ERP Asset action execution must remain unavailable."))
    return ToolingAssetActionEvidence(
        global_id=record["globalId"], action_kind=ToolingAssetActionKind(record["actionKind"]),
        reason=record["reason"], approval_reference=record["approvalReference"],
        proposed_effective_date=record["proposedEffectiveDate"],
        evidence=tuple(_evidence_from_dict(item) for item in _list(record["evidence"], "assetAction.evidence", 20)),
    )


def _spare_from_dict(value: object) -> ToolingSpareRecommendation:
    record = _record(value, "spare", {
        "globalId", "recommendationKey", "kind", "description", "recommendedMinimumQuantity",
        "unit", "supplierReference", "formalItemAndInventory",
    })
    inventory = {"state": "unavailable", "reasonCode": "erp_spare_inventory_projection_unavailable"}
    if record["formalItemAndInventory"] != inventory:
        raise _field_problem("spare.formalItemAndInventory", _("Formal spare Item and inventory must remain unavailable."))
    supplier = record["supplierReference"]
    source_system = source_object_id = None
    if supplier != {"state": "unavailable", "reasonCode": "formal_supplier_projection_unavailable"}:
        supplier_record = _record(supplier, "spare.supplierReference", {"sourceSystem", "sourceObjectId"})
        source_system = supplier_record["sourceSystem"]
        source_object_id = supplier_record["sourceObjectId"]
    return ToolingSpareRecommendation(
        global_id=record["globalId"], recommendation_key=record["recommendationKey"],
        kind=ToolingSpareKind(record["kind"]), description=record["description"],
        recommended_minimum_quantity=record["recommendedMinimumQuantity"], unit=record["unit"],
        supplier_source_system=source_system, supplier_source_object_id=source_object_id,
    )


def _repair_from_dict(value: object) -> ToolingRepairEvidence:
    record = _record(value, "repair", {
        "globalId", "authorizationReference", "quoteReference", "quote", "responsibleMember",
        "downtimeImpactHours", "detail", "customerAuthorizationEvidence", "verificationEvidence",
        "erpRepairResult",
    })
    expected = {"state": "unavailable", "reasonCode": "erp_repair_projection_unavailable"}
    if record["erpRepairResult"] != expected:
        raise _field_problem("repair.erpRepairResult", _("ERP repair result must remain unavailable."))
    quote = record["quote"]
    currency = amount = None
    if quote is not None:
        quote_record = _record(quote, "repair.quote", {"currency", "amount"})
        currency, amount = quote_record["currency"], quote_record["amount"]
    member = _member_from_dict(record["responsibleMember"])
    if member is None:
        raise _field_problem("repair.responsibleMember", _("Select a valid Project member."))
    return ToolingRepairEvidence(
        global_id=record["globalId"], authorization_reference=record["authorizationReference"],
        quote_reference=record["quoteReference"], quote_currency=currency, quote_amount=amount,
        responsible_member=member, downtime_impact_hours=record["downtimeImpactHours"],
        detail=record["detail"],
        customer_authorization_evidence=tuple(_evidence_from_dict(item) for item in _list(record["customerAuthorizationEvidence"], "repair.customerAuthorizationEvidence", 20)),
        verification_evidence=tuple(_evidence_from_dict(item) for item in _list(record["verificationEvidence"], "repair.verificationEvidence", 20)),
    )


def _record(value: object, path: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _field_problem(path, _("Enter a closed object with the required fields."))
    return value


def _list(value: object, path: str, maximum: int) -> list[object]:
    if not isinstance(value, list) or len(value) > maximum:
        raise _field_problem(path, _("Enter a bounded list."))
    return value


def _uuid(value: object, path: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _field_problem(path, _("Enter a valid UUID.")) from error


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _field_problem(path, _("Enter a non-negative integer."))
    return value


def _typed_tuple(value: object, expected_type: type[_T], path: str, *, maximum: int) -> tuple[_T, ...]:
    if not isinstance(value, tuple) or len(value) > maximum or any(not isinstance(item, expected_type) for item in value):
        raise _field_problem(path, _("Enter a bounded list of valid records."))
    return value


def _unique(values, path: str) -> None:
    materialized = list(values)
    if len(set(materialized)) != len(materialized):
        raise _field_problem(path, _("Record identities must be unique."))


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter valid text."))
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or any(ord(char) < 32 for char in normalized):
        raise _field_problem(path, _("Enter valid text."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _key(value: object, path: str, maximum: int = 128) -> str:
    text = _text(value, path, maximum)
    if not _KEY_PATTERN.fullmatch(text):
        raise _field_problem(path, _("Enter a valid stable key."))
    return text


def _optional_key(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _key(value, path, maximum)


def _actor(value: object, path: str) -> str:
    if not isinstance(value, str) or not _ACTOR_PATTERN.fullmatch(value):
        raise _field_problem(path, _("Enter a valid actor identity."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise _field_problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _content_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or not _CONTENT_HASH_PATTERN.fullmatch(value):
        raise _field_problem(path, _("Enter a valid lowercase content hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _decimal(value: object, path: str, *, positive: bool) -> str:
    if isinstance(value, bool):
        raise _field_problem(path, _("Enter a valid decimal value."))
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise _field_problem(path, _("Enter a valid decimal value.")) from error
    if not decimal_value.is_finite() or (decimal_value <= 0 if positive else decimal_value < 0):
        raise _field_problem(path, _("Enter a valid decimal value."))
    normalized = format(decimal_value.normalize(), "f")
    return "0" if normalized == "-0" else normalized


def _currency(value: object, path: str) -> str:
    text = _text(value, path, 3).upper()
    if len(text) != 3 or not text.isalpha() or not text.isascii():
        raise _field_problem(path, _("Enter a three-letter currency code."))
    return text


def _optional_date(value: object, path: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        raise _field_problem(path, _("Enter a valid date."))
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid date.")) from error


def _datetime(value: object, path: str) -> datetime:
    if isinstance(value, str):
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            value = datetime.fromisoformat(candidate)
        except ValueError as error:
            raise _field_problem(path, _("Enter a timezone-aware datetime.")) from error
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise _field_problem(path, _("Enter a timezone-aware datetime."))
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_predecessor(version: int, global_id: UUID | None, snapshot_hash: str | None, path: str) -> None:
    if version == 1 and (global_id is not None or snapshot_hash is not None):
        raise _field_problem(path, _("The first revision cannot contain a predecessor."))
    if version > 1 and (global_id is None or snapshot_hash is None):
        raise _field_problem(path, _("A successor revision requires the exact predecessor."))


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item[:1].upper() + item[1:] for item in tail)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed(field_errors=[{"path": path, "message": message}])
