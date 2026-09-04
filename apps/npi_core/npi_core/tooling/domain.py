from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TypeVar
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


TOOLING_SCHEMA_VERSION = 1
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_CONTENT_HASH_PATTERN = re.compile(r"^[a-f0-9]{32,128}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_REFERENCE_SYSTEMS = frozenset({"NPI_ONE", "ERPNEXT"})
_T = TypeVar("_T")


class ToolingUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TOOLING_UNAVAILABLE",
            _("The related object is unavailable."),
        )


class ToolingReferenceUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TOOLING_REFERENCE_UNAVAILABLE",
            _("The related Project reference is unavailable."),
        )


class ToolingVersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOLING_VERSION_CONFLICT",
            _("The object was changed by another user."),
        )


class ToolingApplicabilityConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOLING_APPLICABILITY_CONFLICT",
            _("Applicability effectivity cannot overlap for the same relationship."),
        )


class ToolingIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOLING_IDEMPOTENCY_CONFLICT",
            _("The idempotency key was already used for a different request."),
        )


class ToolingIntakeVersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOLING_INTAKE_VERSION_CONFLICT",
            _("The object was changed by another user."),
        )


class ToolingEvidenceConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOLING_EVIDENCE_CONFLICT",
            _("The exact evidence reference is already attached."),
        )


class ToolingRequirementKind(StrEnum):
    NEW_TOOL = "new_tool"
    CUSTOMER_OWNED_INTAKE = "customer_owned_intake"
    COPY_OR_ADDITIONAL_SET = "copy_or_additional_set"
    MODIFICATION = "modification"
    REPAIR = "repair"
    CAPACITY_NEED = "capacity_need"


class ToolingInspectionCategory(StrEnum):
    APPEARANCE = "appearance"
    WATER_CIRCUIT = "water_circuit"
    HOT_RUNNER = "hot_runner"
    ELECTRICAL = "electrical"
    SAFETY = "safety"


class ToolingDifferenceSourceKind(StrEnum):
    ACCESSORY = "accessory"
    INSPECTION = "inspection"


class ToolingIntakeEvidenceRole(StrEnum):
    ARRIVAL_PHOTO = "arrival_photo"
    TRANSPORT_DOCUMENT = "transport_document"
    ACCESSORY_DOCUMENT = "accessory_document"
    INSPECTION_EVIDENCE = "inspection_evidence"
    CUSTOMER_CONFIRMATION = "customer_confirmation"


@dataclass(frozen=True, slots=True)
class EngineeringPartRevision:
    global_id: UUID
    part_global_id: UUID
    tenant_id: str
    originating_project_global_id: UUID
    revision_number: int
    revision_label: str
    title: str
    reason: str
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "part_global_id",
            "originating_project_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "revision_number",
            _positive(self.revision_number, "revisionNumber"),
        )
        object.__setattr__(
            self,
            "revision_label",
            _text(self.revision_label, "revisionLabel", 40),
        )
        object.__setattr__(self, "title", _text(self.title, "title", 140))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        object.__setattr__(
            self,
            "predecessor_snapshot_hash",
            _optional_hash(
                self.predecessor_snapshot_hash,
                "predecessorSnapshotHash",
            ),
        )
        if self.revision_number == 1:
            if (
                self.predecessor_global_id is not None
                or self.predecessor_snapshot_hash is not None
            ):
                raise _field_problem(
                    "predecessorGlobalId",
                    _("The first Part Revision cannot have a predecessor."),
                )
        elif (
            self.predecessor_global_id is None
            or self.predecessor_snapshot_hash is None
        ):
            raise _field_problem(
                "predecessorGlobalId",
                _("A successor Part Revision requires its exact predecessor."),
            )
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _field_problem(
                "snapshotHash",
                _("The Part Revision snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "partGlobalId": str(self.part_global_id),
            "tenantId": self.tenant_id,
            "originatingProjectGlobalId": str(self.originating_project_global_id),
            "revisionNumber": self.revision_number,
            "revisionLabel": self.revision_label,
            "title": self.title,
            "reason": self.reason,
            "predecessorGlobalId": (
                None
                if self.predecessor_global_id is None
                else str(self.predecessor_global_id)
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class EngineeringPart:
    global_id: UUID
    tenant_id: str
    originating_project_global_id: UUID
    title: str
    current_revision_global_id: UUID
    current_revision_number: int
    current_revision_snapshot_hash: str
    optimistic_version: int = 1

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "originating_project_global_id",
            "current_revision_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "title", _text(self.title, "title", 140))
        object.__setattr__(
            self,
            "current_revision_number",
            _positive(self.current_revision_number, "currentRevisionNumber"),
        )
        object.__setattr__(
            self,
            "current_revision_snapshot_hash",
            _hash(self.current_revision_snapshot_hash, "currentRevisionSnapshotHash"),
        )
        object.__setattr__(
            self,
            "optimistic_version",
            _positive(self.optimistic_version, "optimisticVersion"),
        )

    def advance(self, revision: EngineeringPartRevision) -> EngineeringPart:
        if (
            revision.part_global_id != self.global_id
            or revision.tenant_id != self.tenant_id
            or revision.originating_project_global_id
            != self.originating_project_global_id
            or revision.revision_number != self.current_revision_number + 1
            or revision.predecessor_global_id != self.current_revision_global_id
            or revision.predecessor_snapshot_hash
            != self.current_revision_snapshot_hash
        ):
            raise _field_problem(
                "revision",
                _("The Part Revision does not advance the exact current revision."),
            )
        return EngineeringPart(
            global_id=self.global_id,
            tenant_id=self.tenant_id,
            originating_project_global_id=self.originating_project_global_id,
            title=revision.title,
            current_revision_global_id=revision.global_id,
            current_revision_number=revision.revision_number,
            current_revision_snapshot_hash=revision.snapshot_hash,
            optimistic_version=self.optimistic_version + 1,
        )


@dataclass(frozen=True, slots=True)
class ToolingRequirement:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    kind: ToolingRequirementKind
    title: str
    reason: str
    target_part_revision_global_id: UUID | None
    target_date: date | None
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "project_global_id", "request_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        if not isinstance(self.kind, ToolingRequirementKind):
            raise _field_problem("kind", _("Select a supported value."))
        object.__setattr__(self, "title", _text(self.title, "title", 140))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "target_part_revision_global_id",
            _optional_uuid(
                self.target_part_revision_global_id,
                "targetPartRevisionGlobalId",
            ),
        )
        if self.target_date is not None and not isinstance(self.target_date, date):
            raise _field_problem("targetDate", _("Enter a valid date."))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _field_problem(
                "snapshotHash",
                _("The Tooling Requirement snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "kind": self.kind.value,
            "title": self.title,
            "reason": self.reason,
            "targetPartRevisionGlobalId": (
                None
                if self.target_part_revision_global_id is None
                else str(self.target_part_revision_global_id)
            ),
            "targetDate": (
                None if self.target_date is None else self.target_date.isoformat()
            ),
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingMaster:
    global_id: UUID
    tenant_id: str
    originating_project_global_id: UUID
    title: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "originating_project_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "title", _text(self.title, "title", 140))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _field_problem(
                "snapshotHash",
                _("The Tooling Master snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "originatingProjectGlobalId": str(self.originating_project_global_id),
            "title": self.title,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingSet:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_requirement_global_id: UUID
    requirement_kind: ToolingRequirementKind
    physical_serial: str
    customer_source_system: str | None
    customer_source_object_id: str | None
    custody_responsibility: str
    repair_authorization_reference: str
    return_conditions: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_requirement_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        if self.requirement_kind not in {
            ToolingRequirementKind.CUSTOMER_OWNED_INTAKE,
            ToolingRequirementKind.COPY_OR_ADDITIONAL_SET,
        }:
            raise _field_problem(
                "requirementKind",
                _("Select a customer-owned intake or copy/additional Set requirement."),
            )
        object.__setattr__(
            self,
            "physical_serial",
            _text(self.physical_serial, "physicalSerial", 80),
        )
        if (self.customer_source_system is None) != (
            self.customer_source_object_id is None
        ):
            raise _field_problem(
                "customer",
                _("Reference source and object identity must be supplied together."),
            )
        if self.requirement_kind is ToolingRequirementKind.CUSTOMER_OWNED_INTAKE:
            if self.customer_source_system is None:
                raise _field_problem(
                    "customer",
                    _("Customer ownership reference is required for a customer-owned intake."),
                )
        if self.customer_source_system is not None:
            if self.customer_source_system not in _REFERENCE_SYSTEMS:
                raise _field_problem("customer", _("Select a supported value."))
            object.__setattr__(
                self,
                "customer_source_object_id",
                _key(self.customer_source_object_id, "customerSourceObjectId"),
            )
        object.__setattr__(
            self,
            "custody_responsibility",
            _text(self.custody_responsibility, "custodyResponsibility", 500),
        )
        object.__setattr__(
            self,
            "repair_authorization_reference",
            _text(
                self.repair_authorization_reference,
                "repairAuthorizationReference",
                500,
            ),
        )
        object.__setattr__(
            self,
            "return_conditions",
            _text(self.return_conditions, "returnConditions", 500),
        )
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _field_problem(
                "snapshotHash",
                _("The Tooling Set snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingRequirementGlobalId": str(self.tooling_requirement_global_id),
            "requirementKind": self.requirement_kind.value,
            "physicalSerial": self.physical_serial,
            "customerSourceSystem": self.customer_source_system,
            "customerSourceObjectId": self.customer_source_object_id,
            "custodyResponsibility": self.custody_responsibility,
            "repairAuthorizationReference": self.repair_authorization_reference,
            "returnConditions": self.return_conditions,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingAccessoryLine:
    global_id: UUID
    description: str
    declared_quantity: int
    received_quantity: int
    unit: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(self, "description", _text(self.description, "description", 200))
        object.__setattr__(
            self,
            "declared_quantity",
            _non_negative(self.declared_quantity, "declaredQuantity"),
        )
        object.__setattr__(
            self,
            "received_quantity",
            _non_negative(self.received_quantity, "receivedQuantity"),
        )
        object.__setattr__(self, "unit", _text(self.unit, "unit", 24))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "description": self.description,
            "declaredQuantity": self.declared_quantity,
            "receivedQuantity": self.received_quantity,
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class ToolingInspectionObservation:
    global_id: UUID
    category: ToolingInspectionCategory
    observation: str
    difference_observed: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if not isinstance(self.category, ToolingInspectionCategory):
            raise _field_problem("category", _("Select a supported value."))
        object.__setattr__(self, "observation", _text(self.observation, "observation", 500))
        object.__setattr__(
            self,
            "difference_observed",
            _boolean(self.difference_observed, "differenceObserved"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "category": self.category.value,
            "observation": self.observation,
            "differenceObserved": self.difference_observed,
        }


@dataclass(frozen=True, slots=True)
class ToolingIntakeDifference:
    global_id: UUID
    source_kind: ToolingDifferenceSourceKind
    source_global_id: UUID
    description: str
    customer_confirmation_required: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(
            self,
            "source_global_id",
            _uuid(self.source_global_id, "sourceGlobalId"),
        )
        if not isinstance(self.source_kind, ToolingDifferenceSourceKind):
            raise _field_problem("sourceKind", _("Select a supported value."))
        object.__setattr__(self, "description", _text(self.description, "description", 500))
        object.__setattr__(
            self,
            "customer_confirmation_required",
            _boolean(
                self.customer_confirmation_required,
                "customerConfirmationRequired",
            ),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "sourceKind": self.source_kind.value,
            "sourceGlobalId": str(self.source_global_id),
            "description": self.description,
            "customerConfirmationRequired": self.customer_confirmation_required,
        }


@dataclass(frozen=True, slots=True)
class ToolingIntake:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_set_global_id: UUID
    intake_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    transport_provider: str
    transport_reference: str
    arrived_at: datetime
    custody_handover: str
    accessories: tuple[ToolingAccessoryLine, ...]
    inspections: tuple[ToolingInspectionObservation, ...]
    differences: tuple[ToolingIntakeDifference, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "intake_version", _positive(self.intake_version, "intakeVersion"))
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
        if self.intake_version == 1:
            if self.predecessor_global_id is not None or self.predecessor_snapshot_hash is not None:
                raise _field_problem(
                    "predecessorGlobalId",
                    _("The first Tooling Intake version cannot have a predecessor."),
                )
        elif self.predecessor_global_id is None or self.predecessor_snapshot_hash is None:
            raise _field_problem(
                "predecessorGlobalId",
                _("A successor Tooling Intake requires its exact predecessor."),
            )
        object.__setattr__(
            self,
            "transport_provider",
            _text(self.transport_provider, "transportProvider", 140),
        )
        object.__setattr__(
            self,
            "transport_reference",
            _text(self.transport_reference, "transportReference", 140),
        )
        object.__setattr__(self, "arrived_at", _aware_utc(self.arrived_at, "arrivedAt"))
        object.__setattr__(
            self,
            "custody_handover",
            _text(self.custody_handover, "custodyHandover", 500),
        )
        accessories = _typed_tuple(
            self.accessories,
            ToolingAccessoryLine,
            "accessories",
            maximum=100,
        )
        inspections = _typed_tuple(
            self.inspections,
            ToolingInspectionObservation,
            "inspections",
            maximum=5,
        )
        differences = _typed_tuple(
            self.differences,
            ToolingIntakeDifference,
            "differences",
            maximum=100,
        )
        object.__setattr__(self, "accessories", accessories)
        object.__setattr__(self, "inspections", inspections)
        object.__setattr__(self, "differences", differences)
        _require_unique_ids(accessories, "accessories")
        _require_unique_ids(inspections, "inspections")
        _require_unique_ids(differences, "differences")
        if {value.category for value in inspections} != set(ToolingInspectionCategory):
            raise _field_problem(
                "inspections",
                _("Record exactly one observation for each required inspection category."),
            )
        accessory_by_id = {value.global_id: value for value in accessories}
        inspection_by_id = {value.global_id: value for value in inspections}
        required_sources = {
            (ToolingDifferenceSourceKind.ACCESSORY, value.global_id)
            for value in accessories
            if value.declared_quantity != value.received_quantity
        } | {
            (ToolingDifferenceSourceKind.INSPECTION, value.global_id)
            for value in inspections
            if value.difference_observed
        }
        actual_sources: set[tuple[ToolingDifferenceSourceKind, UUID]] = set()
        for difference in differences:
            if difference.source_kind is ToolingDifferenceSourceKind.ACCESSORY:
                source = accessory_by_id.get(difference.source_global_id)
                valid = source is not None and source.declared_quantity != source.received_quantity
            else:
                source = inspection_by_id.get(difference.source_global_id)
                valid = source is not None and source.difference_observed
            if not valid:
                raise _field_problem(
                    "differences",
                    _("The Tooling Intake difference source is unavailable."),
                )
            actual_sources.add((difference.source_kind, difference.source_global_id))
        if not required_sources.issubset(actual_sources):
            raise _field_problem(
                "differences",
                _("Record a difference for every inspection or accessory discrepancy."),
            )
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected:
            raise _field_problem(
                "snapshotHash",
                _("The Tooling Intake snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "intakeVersion": self.intake_version,
            "predecessorGlobalId": (
                None if self.predecessor_global_id is None else str(self.predecessor_global_id)
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "transportProvider": self.transport_provider,
            "transportReference": self.transport_reference,
            "arrivedAt": _utc_text(self.arrived_at),
            "custodyHandover": self.custody_handover,
            "accessories": [value.snapshot_payload() for value in self.accessories],
            "inspections": [value.snapshot_payload() for value in self.inspections],
            "differences": [value.snapshot_payload() for value in self.differences],
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingIntakeEvidenceReference:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_set_global_id: UUID
    tooling_intake_global_id: UUID
    intake_snapshot_hash: str
    evidence_role: ToolingIntakeEvidenceRole
    difference_global_ids: tuple[UUID, ...]
    file_revision_global_id: UUID
    file_optimistic_version: int
    frappe_content_hash: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    evidence_key_hash: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "tooling_intake_global_id",
            "file_revision_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "intake_snapshot_hash",
            _hash(self.intake_snapshot_hash, "intakeSnapshotHash"),
        )
        if not isinstance(self.evidence_role, ToolingIntakeEvidenceRole):
            raise _field_problem("evidenceRole", _("Select a supported value."))
        difference_ids = tuple(
            _uuid(value, "differenceGlobalIds") for value in self.difference_global_ids
        )
        if len(difference_ids) > 100 or len(set(difference_ids)) != len(difference_ids):
            raise _field_problem("differenceGlobalIds", _("Enter a valid bounded list."))
        object.__setattr__(self, "difference_global_ids", difference_ids)
        if self.evidence_role is ToolingIntakeEvidenceRole.CUSTOMER_CONFIRMATION:
            if not difference_ids:
                raise _field_problem(
                    "differenceGlobalIds",
                    _("Customer confirmation evidence must identify an exact difference."),
                )
        elif difference_ids:
            raise _field_problem(
                "differenceGlobalIds",
                _("Only customer confirmation evidence can identify differences."),
            )
        object.__setattr__(
            self,
            "file_optimistic_version",
            _positive(self.file_optimistic_version, "fileOptimisticVersion"),
        )
        object.__setattr__(
            self,
            "frappe_content_hash",
            _content_hash(self.frappe_content_hash, "fileContentHash"),
        )
        object.__setattr__(self, "file_name", _text(self.file_name, "fileName", 255))
        object.__setattr__(self, "mime_type", _text(self.mime_type, "mimeType", 255))
        if (
            self.evidence_role is ToolingIntakeEvidenceRole.ARRIVAL_PHOTO
            and not self.mime_type.casefold().startswith("image/")
        ):
            raise _field_problem(
                "mimeType",
                _("Arrival photo evidence must use an image file."),
            )
        object.__setattr__(self, "size_bytes", _positive(self.size_bytes, "sizeBytes"))
        object.__setattr__(self, "sha256", _hash(self.sha256, "sha256"))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected_key = sha256_json(self.evidence_key_payload())
        if self.evidence_key_hash and _hash(self.evidence_key_hash, "evidenceKeyHash") != expected_key:
            raise _field_problem(
                "evidenceKeyHash",
                _("The Tooling Intake evidence key does not match."),
            )
        object.__setattr__(self, "evidence_key_hash", expected_key)
        expected_snapshot = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected_snapshot:
            raise _field_problem(
                "snapshotHash",
                _("The Tooling Intake evidence snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_snapshot)

    def evidence_key_payload(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "toolingIntakeGlobalId": str(self.tooling_intake_global_id),
            "evidenceRole": self.evidence_role.value,
            "differenceGlobalIds": [str(value) for value in self.difference_global_ids],
            "fileRevisionGlobalId": str(self.file_revision_global_id),
            "fileOptimisticVersion": self.file_optimistic_version,
        }

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "toolingIntakeGlobalId": str(self.tooling_intake_global_id),
            "intakeSnapshotHash": self.intake_snapshot_hash,
            "evidenceRole": self.evidence_role.value,
            "differenceGlobalIds": [str(value) for value in self.difference_global_ids],
            "fileRevisionGlobalId": str(self.file_revision_global_id),
            "fileOptimisticVersion": self.file_optimistic_version,
            "fileContentHash": self.frappe_content_hash,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "evidenceKeyHash": self.evidence_key_hash,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingApplicability:
    global_id: UUID
    relationship_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    part_global_id: UUID
    part_revision_global_id: UUID
    product_source_system: str | None
    product_source_object_id: str | None
    model_source_system: str | None
    model_source_object_id: str | None
    applicability_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    effective_from: date
    effective_to: date | None
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    relationship_key_hash: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "relationship_global_id",
            "project_global_id",
            "tooling_master_global_id",
            "part_global_id",
            "part_revision_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        for prefix in ("product", "model"):
            source_field = f"{prefix}_source_system"
            object_field = f"{prefix}_source_object_id"
            source = getattr(self, source_field)
            object_id = getattr(self, object_field)
            if (source is None) != (object_id is None):
                raise _field_problem(
                    _camel(source_field),
                    _("Reference source and object identity must be supplied together."),
                )
            if source is not None:
                if source not in _REFERENCE_SYSTEMS:
                    raise _field_problem(
                        _camel(source_field),
                        _("Select a supported value."),
                    )
                object.__setattr__(
                    self,
                    object_field,
                    _key(object_id, _camel(object_field)),
                )
        object.__setattr__(
            self,
            "applicability_version",
            _positive(self.applicability_version, "applicabilityVersion"),
        )
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        object.__setattr__(
            self,
            "predecessor_snapshot_hash",
            _optional_hash(
                self.predecessor_snapshot_hash,
                "predecessorSnapshotHash",
            ),
        )
        if self.applicability_version == 1:
            if (
                self.predecessor_global_id is not None
                or self.predecessor_snapshot_hash is not None
            ):
                raise _field_problem(
                    "predecessorGlobalId",
                    _("The first Applicability version cannot have a predecessor."),
                )
        elif (
            self.predecessor_global_id is None
            or self.predecessor_snapshot_hash is None
        ):
            raise _field_problem(
                "predecessorGlobalId",
                _("A successor Applicability requires its exact predecessor."),
            )
        if not isinstance(self.effective_from, date):
            raise _field_problem("effectiveFrom", _("Enter a valid date."))
        if self.effective_to is not None and not isinstance(self.effective_to, date):
            raise _field_problem("effectiveTo", _("Enter a valid date."))
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise _field_problem(
                "effectiveTo",
                _("Effective To must be later than Effective From."),
            )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected_relationship_key = sha256_json(self.relationship_payload())
        if (
            self.relationship_key_hash
            and _hash(self.relationship_key_hash, "relationshipKeyHash")
            != expected_relationship_key
        ):
            raise _field_problem(
                "relationshipKeyHash",
                _("The Applicability relationship key does not match."),
            )
        object.__setattr__(
            self,
            "relationship_key_hash",
            expected_relationship_key,
        )
        expected_snapshot = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected_snapshot:
            raise _field_problem(
                "snapshotHash",
                _("The Applicability snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_snapshot)

    def relationship_payload(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "partGlobalId": str(self.part_global_id),
            "partRevisionGlobalId": str(self.part_revision_global_id),
            "productSourceSystem": self.product_source_system,
            "productSourceObjectId": self.product_source_object_id,
            "modelSourceSystem": self.model_source_system,
            "modelSourceObjectId": self.model_source_object_id,
        }

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "relationshipGlobalId": str(self.relationship_global_id),
            **self.relationship_payload(),
            "relationshipKeyHash": self.relationship_key_hash,
            "applicabilityVersion": self.applicability_version,
            "predecessorGlobalId": (
                None
                if self.predecessor_global_id is None
                else str(self.predecessor_global_id)
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "effectiveFrom": self.effective_from.isoformat(),
            "effectiveTo": (
                None if self.effective_to is None else self.effective_to.isoformat()
            ),
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    def is_effective(self, on: date) -> bool:
        return bool(
            self.effective_from <= on
            and (self.effective_to is None or on < self.effective_to)
        )


def validate_applicability_successor(
    previous: ToolingApplicability,
    successor: ToolingApplicability,
) -> None:
    if (
        successor.relationship_global_id != previous.relationship_global_id
        or successor.relationship_key_hash != previous.relationship_key_hash
        or successor.applicability_version != previous.applicability_version + 1
        or successor.predecessor_global_id != previous.global_id
        or successor.predecessor_snapshot_hash != previous.snapshot_hash
    ):
        raise _field_problem(
            "applicabilityVersion",
            _("The Applicability version does not advance its exact predecessor."),
        )


def ensure_no_effectivity_overlap(
    candidate: ToolingApplicability,
    retained: tuple[ToolingApplicability, ...],
) -> None:
    for existing in retained:
        if existing.relationship_key_hash != candidate.relationship_key_hash:
            continue
        candidate_end = candidate.effective_to or date.max
        existing_end = existing.effective_to or date.max
        if candidate.effective_from < existing_end and existing.effective_from < candidate_end:
            raise _field_problem(
                "effectiveFrom",
                _("Applicability effectivity cannot overlap for the same relationship."),
            )


def validate_intake_successor(
    previous: ToolingIntake,
    successor: ToolingIntake,
) -> None:
    if (
        successor.tenant_id != previous.tenant_id
        or successor.project_global_id != previous.project_global_id
        or successor.tooling_master_global_id != previous.tooling_master_global_id
        or successor.tooling_set_global_id != previous.tooling_set_global_id
        or successor.intake_version != previous.intake_version + 1
        or successor.predecessor_global_id != previous.global_id
        or successor.predecessor_snapshot_hash != previous.snapshot_hash
    ):
        raise _field_problem(
            "intakeVersion",
            _("The Tooling Intake version does not advance its exact predecessor."),
        )


def sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _uuid(value: object, path: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid global ID.")) from error


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid(value, path)


def _positive(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _field_problem(path, _("Enter a positive whole number."))
    return value


def _non_negative(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _field_problem(path, _("Enter a non-negative whole number."))
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise _field_problem(path, _("Select true or false."))
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
    if len(normalized) > maximum or not all(
        isinstance(item, expected_type) for item in normalized
    ):
        raise _field_problem(path, _("Enter a valid bounded list."))
    return normalized


def _require_unique_ids(value: tuple[object, ...], path: str) -> None:
    identities = [getattr(item, "global_id", None) for item in value]
    if len(identities) != len(set(identities)):
        raise _field_problem(path, _("Global IDs must be unique within this list."))


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field_problem(path, _("The value is too long."))
    return normalized


def _key(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if _KEY_PATTERN.fullmatch(normalized) is None:
        raise _field_problem(path, _("Use a valid key."))
    return normalized


def _actor(value: object, path: str) -> str:
    normalized = _text(value, path, 254)
    if _ACTOR_PATTERN.fullmatch(normalized) is None:
        raise _field_problem(path, _("Enter a valid user identity."))
    return normalized


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid SHA-256 value."))
    return value


def _content_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _CONTENT_HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid file content hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value in (None, "") else _hash(value, path)


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
