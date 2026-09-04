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
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_REFERENCE_SYSTEMS = frozenset({"NPI_ONE", "ERPNEXT"})
_T = TypeVar("_T")


class CavityStructuralState(StrEnum):
    ENABLED = "enabled"
    SEALED = "sealed"


class InsertValidationState(StrEnum):
    NOT_VALIDATED = "not_validated"
    VALIDATED = "validated"


class ExternalIdentityType(StrEnum):
    CUSTOMER = "customer"
    SN = "sn"
    KW = "kw"
    TH = "th"
    SUPPLIER_REFERENCE = "supplier_reference"


class PartSpecificationKind(StrEnum):
    MATERIAL_FAMILY = "material_family"
    GRADE = "grade"
    TRADEMARK = "trademark"
    COLOR = "color"
    COLOR_MASTERBATCH = "color_masterbatch"
    FDA_COMPLIANCE = "fda_compliance"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    SECONDARY_PROCESS = "secondary_process"


class ToolingProcessKind(StrEnum):
    PRIMARY_MOLDING = "primary_molding"
    SECOND_SHOT = "second_shot"
    OVERMOLD = "overmold"


@dataclass(frozen=True, slots=True)
class ToolingMeasurement:
    value: str
    unit: str
    source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _positive_decimal(self.value, "value"))
        object.__setattr__(self, "unit", _text(self.unit, "unit", 32))
        object.__setattr__(self, "source", _text(self.source, "source", 120))

    def snapshot_payload(self) -> dict[str, object]:
        return {"value": self.value, "unit": self.unit, "source": self.source}


@dataclass(frozen=True, slots=True)
class ToolingSpecification:
    tooling_type: str
    mold_base_material: str
    core_material: str
    hardness: ToolingMeasurement
    surface_treatment: str
    cavity_count: int
    hot_runner: str
    length: ToolingMeasurement
    width: ToolingMeasurement
    height: ToolingMeasurement
    weight: ToolingMeasurement
    clamp_tonnage: ToolingMeasurement
    tie_bar_spacing_x: ToolingMeasurement
    tie_bar_spacing_y: ToolingMeasurement
    injection_capacity: ToolingMeasurement
    machine_type: str
    target_cycle: ToolingMeasurement
    target_life: ToolingMeasurement
    warranty: str
    customer_standard: str
    interface_requirement: str
    spare_parts: tuple[str, ...]
    delivery_documents: tuple[str, ...]

    def __post_init__(self) -> None:
        for fieldname, maximum in (
            ("tooling_type", 80),
            ("mold_base_material", 160),
            ("core_material", 160),
            ("surface_treatment", 160),
            ("hot_runner", 160),
            ("machine_type", 120),
            ("warranty", 240),
            ("customer_standard", 500),
            ("interface_requirement", 500),
        ):
            object.__setattr__(
                self,
                fieldname,
                _text(getattr(self, fieldname), _camel(fieldname), maximum),
            )
        for fieldname in (
            "hardness",
            "length",
            "width",
            "height",
            "weight",
            "clamp_tonnage",
            "tie_bar_spacing_x",
            "tie_bar_spacing_y",
            "injection_capacity",
            "target_cycle",
            "target_life",
        ):
            if not isinstance(getattr(self, fieldname), ToolingMeasurement):
                raise _field_problem(
                    _camel(fieldname),
                    _("Enter a valid unit-bearing measurement."),
                )
        object.__setattr__(
            self,
            "cavity_count",
            _positive(self.cavity_count, "cavityCount"),
        )
        for fieldname in ("spare_parts", "delivery_documents"):
            values = _string_tuple(
                getattr(self, fieldname),
                _camel(fieldname),
                maximum=100,
                item_maximum=200,
            )
            if len(values) != len({value.casefold() for value in values}):
                raise _field_problem(
                    _camel(fieldname),
                    _("Values must be unique within this list."),
                )
            object.__setattr__(self, fieldname, values)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "toolingType": self.tooling_type,
            "moldBaseMaterial": self.mold_base_material,
            "coreMaterial": self.core_material,
            "hardness": self.hardness.snapshot_payload(),
            "surfaceTreatment": self.surface_treatment,
            "cavityCount": self.cavity_count,
            "hotRunner": self.hot_runner,
            "length": self.length.snapshot_payload(),
            "width": self.width.snapshot_payload(),
            "height": self.height.snapshot_payload(),
            "weight": self.weight.snapshot_payload(),
            "clampTonnage": self.clamp_tonnage.snapshot_payload(),
            "tieBarSpacingX": self.tie_bar_spacing_x.snapshot_payload(),
            "tieBarSpacingY": self.tie_bar_spacing_y.snapshot_payload(),
            "injectionCapacity": self.injection_capacity.snapshot_payload(),
            "machineType": self.machine_type,
            "targetCycle": self.target_cycle.snapshot_payload(),
            "targetLife": self.target_life.snapshot_payload(),
            "warranty": self.warranty,
            "customerStandard": self.customer_standard,
            "interfaceRequirement": self.interface_requirement,
            "spareParts": list(self.spare_parts),
            "deliveryDocuments": list(self.delivery_documents),
        }


@dataclass(frozen=True, slots=True)
class CavityMapping:
    global_id: UUID
    cavity_identifier: str
    tooling_applicability_global_id: UUID
    part_revision_global_id: UUID
    structural_state: CavityStructuralState

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "tooling_applicability_global_id",
            "part_revision_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(
            self,
            "cavity_identifier",
            _text(self.cavity_identifier, "cavityIdentifier", 64),
        )
        if not isinstance(self.structural_state, CavityStructuralState):
            raise _field_problem("structuralState", _("Select a supported value."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "cavityIdentifier": self.cavity_identifier,
            "toolingApplicabilityGlobalId": str(
                self.tooling_applicability_global_id
            ),
            "partRevisionGlobalId": str(self.part_revision_global_id),
            "structuralState": self.structural_state.value,
        }


@dataclass(frozen=True, slots=True)
class InsertApplicability:
    global_id: UUID
    insert_code: str
    insert_version: int
    tooling_applicability_global_id: UUID
    part_revision_global_id: UUID
    model_source_system: str | None
    model_source_object_id: str | None
    changeover_duration: ToolingMeasurement
    validation_state: InsertValidationState
    validated_by_user_id: str | None
    validated_at: datetime | None
    validation_reason: str | None

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "tooling_applicability_global_id",
            "part_revision_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "insert_code", _text(self.insert_code, "insertCode", 80))
        object.__setattr__(
            self,
            "insert_version",
            _positive(self.insert_version, "insertVersion"),
        )
        if (self.model_source_system is None) != (
            self.model_source_object_id is None
        ):
            raise _field_problem(
                "model",
                _("Reference source and object identity must be supplied together."),
            )
        if self.model_source_system is not None:
            if self.model_source_system not in _REFERENCE_SYSTEMS:
                raise _field_problem("modelSourceSystem", _("Select a supported value."))
            object.__setattr__(
                self,
                "model_source_object_id",
                _key(self.model_source_object_id, "modelSourceObjectId"),
            )
        if not isinstance(self.changeover_duration, ToolingMeasurement):
            raise _field_problem(
                "changeoverDuration",
                _("Enter a valid unit-bearing measurement."),
            )
        if not isinstance(self.validation_state, InsertValidationState):
            raise _field_problem("validationState", _("Select a supported value."))
        if self.validation_state is InsertValidationState.VALIDATED:
            if (
                self.validated_by_user_id is None
                or self.validated_at is None
                or self.validation_reason is None
            ):
                raise _field_problem(
                    "validationState",
                    _("Validated insert evidence is required."),
                )
            object.__setattr__(
                self,
                "validated_by_user_id",
                _actor(self.validated_by_user_id, "validatedByUserId"),
            )
            object.__setattr__(
                self,
                "validated_at",
                _aware_utc(self.validated_at, "validatedAt"),
            )
            object.__setattr__(
                self,
                "validation_reason",
                _text(self.validation_reason, "validationReason", 500),
            )
        elif any(
            value is not None
            for value in (
                self.validated_by_user_id,
                self.validated_at,
                self.validation_reason,
            )
        ):
            raise _field_problem(
                "validationState",
                _("Unvalidated inserts cannot retain validation evidence."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "insertCode": self.insert_code,
            "insertVersion": self.insert_version,
            "toolingApplicabilityGlobalId": str(
                self.tooling_applicability_global_id
            ),
            "partRevisionGlobalId": str(self.part_revision_global_id),
            "modelSourceSystem": self.model_source_system,
            "modelSourceObjectId": self.model_source_object_id,
            "changeoverDuration": self.changeover_duration.snapshot_payload(),
            "validationState": self.validation_state.value,
            "validatedByUserId": self.validated_by_user_id,
            "validatedAt": (
                _utc_text(self.validated_at)
                if self.validated_at is not None
                else None
            ),
            "validationReason": self.validation_reason,
        }


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    global_id: UUID
    identity_type: ExternalIdentityType
    value: str
    raw_value: str
    source_system: str
    source_object_id: str
    effective_from: date
    effective_to: date | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if not isinstance(self.identity_type, ExternalIdentityType):
            raise _field_problem("identityType", _("Select a supported value."))
        object.__setattr__(self, "value", _text(self.value, "value", 160))
        object.__setattr__(self, "raw_value", _text(self.raw_value, "rawValue", 500))
        if self.source_system not in _REFERENCE_SYSTEMS:
            raise _field_problem("sourceSystem", _("Select a supported value."))
        object.__setattr__(
            self,
            "source_object_id",
            _key(self.source_object_id, "sourceObjectId"),
        )
        if isinstance(self.effective_from, datetime) or not isinstance(
            self.effective_from,
            date,
        ):
            raise _field_problem("effectiveFrom", _("Enter a valid date."))
        if self.effective_to is not None and (
            isinstance(self.effective_to, datetime)
            or not isinstance(self.effective_to, date)
        ):
            raise _field_problem("effectiveTo", _("Enter a valid date."))
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise _field_problem(
                "effectiveTo",
                _("Effective To must be later than Effective From."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "identityType": self.identity_type.value,
            "value": self.value,
            "rawValue": self.raw_value,
            "sourceSystem": self.source_system,
            "sourceObjectId": self.source_object_id,
            "effectiveFrom": self.effective_from.isoformat(),
            "effectiveTo": self.effective_to.isoformat() if self.effective_to else None,
        }


@dataclass(frozen=True, slots=True)
class DocumentRevisionReference:
    global_id: UUID
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "snapshotHash"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {"globalId": str(self.global_id), "snapshotHash": self.snapshot_hash}


@dataclass(frozen=True, slots=True)
class ToolingRevision:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    revision_number: int
    revision_label: str
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    specification: ToolingSpecification
    cavities: tuple[CavityMapping, ...]
    inserts: tuple[InsertApplicability, ...]
    external_identities: tuple[ExternalIdentity, ...]
    design_document_revisions: tuple[DocumentRevisionReference, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    revision_key_hash: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
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
            self.revision_number,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "revisionNumber",
        )
        if not isinstance(self.specification, ToolingSpecification):
            raise _field_problem("specification", _("Enter a valid Tooling specification."))
        cavities = _typed_tuple(self.cavities, CavityMapping, "cavities", maximum=200)
        inserts = _typed_tuple(self.inserts, InsertApplicability, "inserts", maximum=200)
        external_identities = _typed_tuple(
            self.external_identities,
            ExternalIdentity,
            "externalIdentities",
            maximum=100,
        )
        design_revisions = _typed_tuple(
            self.design_document_revisions,
            DocumentRevisionReference,
            "designDocumentRevisions",
            maximum=50,
        )
        if len(cavities) != self.specification.cavity_count:
            raise _field_problem(
                "cavities",
                _("Cavity rows must match the declared cavity count."),
            )
        for values, path in (
            (cavities, "cavities"),
            (inserts, "inserts"),
            (external_identities, "externalIdentities"),
            (design_revisions, "designDocumentRevisions"),
        ):
            _require_unique_ids(values, path)
        if len(cavities) != len(
            {item.cavity_identifier.casefold() for item in cavities}
        ):
            raise _field_problem("cavities", _("Cavity identifiers must be unique."))
        if len(inserts) != len(
            {(item.insert_code.casefold(), item.insert_version) for item in inserts}
        ):
            raise _field_problem("inserts", _("Insert versions must be unique."))
        if len(external_identities) != len(
            {
                (
                    item.identity_type.value,
                    item.value.casefold(),
                    item.effective_from,
                    item.effective_to,
                )
                for item in external_identities
            }
        ):
            raise _field_problem(
                "externalIdentities",
                _("External identities and effectivity must be unique."),
            )
        object.__setattr__(self, "cavities", cavities)
        object.__setattr__(self, "inserts", inserts)
        object.__setattr__(self, "external_identities", external_identities)
        object.__setattr__(self, "design_document_revisions", design_revisions)
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "toolingMasterGlobalId": str(self.tooling_master_global_id),
                "revisionNumber": self.revision_number,
            }
        )
        if self.revision_key_hash and _hash(
            self.revision_key_hash,
            "revisionKeyHash",
        ) != expected_key:
            raise _field_problem(
                "revisionKeyHash",
                _("The Tooling Revision key does not match."),
            )
        object.__setattr__(self, "revision_key_hash", expected_key)
        expected_snapshot = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected_snapshot:
            raise _field_problem(
                "snapshotHash",
                _("The Tooling Revision snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_snapshot)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "revisionNumber": self.revision_number,
            "revisionLabel": self.revision_label,
            "predecessorGlobalId": (
                str(self.predecessor_global_id)
                if self.predecessor_global_id is not None
                else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "specification": self.specification.snapshot_payload(),
            "cavities": [item.snapshot_payload() for item in self.cavities],
            "inserts": [item.snapshot_payload() for item in self.inserts],
            "externalIdentities": [
                item.snapshot_payload() for item in self.external_identities
            ],
            "designDocumentRevisions": [
                item.snapshot_payload() for item in self.design_document_revisions
            ],
            "reason": self.reason,
            "revisionKeyHash": self.revision_key_hash,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class PartSpecificationItem:
    global_id: UUID
    kind: PartSpecificationKind
    normalized_value: str
    raw_value: str
    source_system: str
    source_object_id: str
    effective_from: date
    effective_to: date | None
    unit: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if not isinstance(self.kind, PartSpecificationKind):
            raise _field_problem("kind", _("Select a supported value."))
        object.__setattr__(
            self,
            "normalized_value",
            _text(self.normalized_value, "normalizedValue", 240),
        )
        object.__setattr__(self, "raw_value", _text(self.raw_value, "rawValue", 500))
        if self.source_system not in _REFERENCE_SYSTEMS:
            raise _field_problem("sourceSystem", _("Select a supported value."))
        object.__setattr__(
            self,
            "source_object_id",
            _key(self.source_object_id, "sourceObjectId"),
        )
        if isinstance(self.effective_from, datetime) or not isinstance(
            self.effective_from,
            date,
        ):
            raise _field_problem("effectiveFrom", _("Enter a valid date."))
        if self.effective_to is not None and (
            isinstance(self.effective_to, datetime)
            or not isinstance(self.effective_to, date)
        ):
            raise _field_problem("effectiveTo", _("Enter a valid date."))
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise _field_problem(
                "effectiveTo",
                _("Effective To must be later than Effective From."),
            )
        object.__setattr__(self, "unit", _optional_text(self.unit, "unit", 32))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "kind": self.kind.value,
            "normalizedValue": self.normalized_value,
            "rawValue": self.raw_value,
            "sourceSystem": self.source_system,
            "sourceObjectId": self.source_object_id,
            "effectiveFrom": self.effective_from.isoformat(),
            "effectiveTo": self.effective_to.isoformat() if self.effective_to else None,
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class PartControlledSpecification:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    part_global_id: UUID
    part_revision_global_id: UUID
    part_revision_snapshot_hash: str
    items: tuple[PartSpecificationItem, ...]
    external_identities: tuple[ExternalIdentity, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    specification_key_hash: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
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
        object.__setattr__(
            self,
            "part_revision_snapshot_hash",
            _hash(self.part_revision_snapshot_hash, "partRevisionSnapshotHash"),
        )
        items = _typed_tuple(self.items, PartSpecificationItem, "items", maximum=100)
        if not items:
            raise _field_problem("items", _("At least one controlled specification is required."))
        external_identities = _typed_tuple(
            self.external_identities,
            ExternalIdentity,
            "externalIdentities",
            maximum=100,
        )
        _require_unique_ids(items, "items")
        _require_unique_ids(external_identities, "externalIdentities")
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "external_identities", external_identities)
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "partRevisionGlobalId": str(self.part_revision_global_id),
            }
        )
        if self.specification_key_hash and _hash(
            self.specification_key_hash,
            "specificationKeyHash",
        ) != expected_key:
            raise _field_problem(
                "specificationKeyHash",
                _("The Part specification key does not match."),
            )
        object.__setattr__(self, "specification_key_hash", expected_key)
        expected_snapshot = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected_snapshot:
            raise _field_problem(
                "snapshotHash",
                _("The Part specification snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_snapshot)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "partGlobalId": str(self.part_global_id),
            "partRevisionGlobalId": str(self.part_revision_global_id),
            "partRevisionSnapshotHash": self.part_revision_snapshot_hash,
            "items": [item.snapshot_payload() for item in self.items],
            "externalIdentities": [
                item.snapshot_payload() for item in self.external_identities
            ],
            "specificationKeyHash": self.specification_key_hash,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingProcessStep:
    global_id: UUID
    step_order: int
    process_kind: ToolingProcessKind
    tooling_revision_global_id: UUID
    tooling_revision_snapshot_hash: str
    input_part_revision_global_ids: tuple[UUID, ...]
    output_part_revision_global_id: UUID
    parent_step_global_id: UUID | None
    machine_type: str
    clamp_tonnage: ToolingMeasurement

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "tooling_revision_global_id",
            "output_part_revision_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "step_order", _positive(self.step_order, "stepOrder"))
        if not isinstance(self.process_kind, ToolingProcessKind):
            raise _field_problem("processKind", _("Select a supported value."))
        object.__setattr__(
            self,
            "tooling_revision_snapshot_hash",
            _hash(self.tooling_revision_snapshot_hash, "toolingRevisionSnapshotHash"),
        )
        inputs = _uuid_tuple(
            self.input_part_revision_global_ids,
            "inputPartRevisionGlobalIds",
            maximum=20,
        )
        if not inputs:
            raise _field_problem("inputPartRevisionGlobalIds", _("At least one input Part Revision is required."))
        object.__setattr__(self, "input_part_revision_global_ids", inputs)
        object.__setattr__(
            self,
            "parent_step_global_id",
            _optional_uuid(self.parent_step_global_id, "parentStepGlobalId"),
        )
        if self.process_kind is ToolingProcessKind.PRIMARY_MOLDING:
            if self.parent_step_global_id is not None:
                raise _field_problem("parentStepGlobalId", _("A primary molding step cannot have a parent step."))
        elif self.parent_step_global_id is None:
            raise _field_problem("parentStepGlobalId", _("A secondary process step requires its parent step."))
        object.__setattr__(self, "machine_type", _text(self.machine_type, "machineType", 120))
        if not isinstance(self.clamp_tonnage, ToolingMeasurement):
            raise _field_problem("clampTonnage", _("Enter a valid unit-bearing measurement."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "stepOrder": self.step_order,
            "processKind": self.process_kind.value,
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "inputPartRevisionGlobalIds": [
                str(value) for value in self.input_part_revision_global_ids
            ],
            "outputPartRevisionGlobalId": str(self.output_part_revision_global_id),
            "parentStepGlobalId": (
                str(self.parent_step_global_id)
                if self.parent_step_global_id is not None
                else None
            ),
            "machineType": self.machine_type,
            "clampTonnage": self.clamp_tonnage.snapshot_payload(),
        }


@dataclass(frozen=True, slots=True)
class ToolingProcessChainRevision:
    global_id: UUID
    process_chain_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    chain_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    steps: tuple[ToolingProcessStep, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    version_key_hash: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "process_chain_global_id",
            "project_global_id",
            "request_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "chain_version", _positive(self.chain_version, "chainVersion"))
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
            self.chain_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "chainVersion",
        )
        steps = _typed_tuple(self.steps, ToolingProcessStep, "steps", maximum=20)
        if len(steps) < 2:
            raise _field_problem("steps", _("A process chain requires at least two ordered steps."))
        _require_unique_ids(steps, "steps")
        if [item.step_order for item in steps] != list(range(1, len(steps) + 1)):
            raise _field_problem("steps", _("Process step order must be contiguous."))
        if steps[0].process_kind is not ToolingProcessKind.PRIMARY_MOLDING:
            raise _field_problem("steps", _("The first process step must be primary molding."))
        if any(
            step.process_kind is ToolingProcessKind.PRIMARY_MOLDING
            for step in steps[1:]
        ):
            raise _field_problem(
                "steps",
                _("Only the first process step can be primary molding."),
            )
        by_id: dict[UUID, ToolingProcessStep] = {}
        for step in steps:
            if step.parent_step_global_id is not None:
                parent = by_id.get(step.parent_step_global_id)
                if parent is None:
                    raise _field_problem("steps", _("A process parent must be an earlier step."))
                if parent.output_part_revision_global_id not in step.input_part_revision_global_ids:
                    raise _field_problem("steps", _("A secondary process must consume its parent output."))
            by_id[step.global_id] = step
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "processChainGlobalId": str(self.process_chain_global_id),
                "chainVersion": self.chain_version,
            }
        )
        if self.version_key_hash and _hash(self.version_key_hash, "versionKeyHash") != expected_key:
            raise _field_problem("versionKeyHash", _("The process-chain version key does not match."))
        object.__setattr__(self, "version_key_hash", expected_key)
        expected_snapshot = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected_snapshot:
            raise _field_problem("snapshotHash", _("The process-chain snapshot hash does not match."))
        object.__setattr__(self, "snapshot_hash", expected_snapshot)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "processChainGlobalId": str(self.process_chain_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "chainVersion": self.chain_version,
            "predecessorGlobalId": (
                str(self.predecessor_global_id)
                if self.predecessor_global_id is not None
                else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "steps": [item.snapshot_payload() for item in self.steps],
            "reason": self.reason,
            "versionKeyHash": self.version_key_hash,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ToolingSetRevisionBinding:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    tooling_master_global_id: UUID
    tooling_set_global_id: UUID
    tooling_set_snapshot_hash: str
    tooling_revision_global_id: UUID
    tooling_revision_snapshot_hash: str
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    binding_key_hash: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "tooling_master_global_id",
            "tooling_set_global_id",
            "tooling_revision_global_id",
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
            "tooling_set_snapshot_hash",
            _hash(self.tooling_set_snapshot_hash, "toolingSetSnapshotHash"),
        )
        object.__setattr__(
            self,
            "tooling_revision_snapshot_hash",
            _hash(self.tooling_revision_snapshot_hash, "toolingRevisionSnapshotHash"),
        )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(self, "created_by_user_id", _actor(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _aware_utc(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "toolingSetGlobalId": str(self.tooling_set_global_id),
            }
        )
        if self.binding_key_hash and _hash(self.binding_key_hash, "bindingKeyHash") != expected_key:
            raise _field_problem("bindingKeyHash", _("The Set-source binding key does not match."))
        object.__setattr__(self, "binding_key_hash", expected_key)
        expected_snapshot = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(self.snapshot_hash, "snapshotHash") != expected_snapshot:
            raise _field_problem("snapshotHash", _("The Set-source binding snapshot hash does not match."))
        object.__setattr__(self, "snapshot_hash", expected_snapshot)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingSetGlobalId": str(self.tooling_set_global_id),
            "toolingSetSnapshotHash": self.tooling_set_snapshot_hash,
            "toolingRevisionGlobalId": str(self.tooling_revision_global_id),
            "toolingRevisionSnapshotHash": self.tooling_revision_snapshot_hash,
            "reason": self.reason,
            "bindingKeyHash": self.binding_key_hash,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_tooling_revision_successor(
    previous: ToolingRevision,
    successor: ToolingRevision,
) -> None:
    if (
        successor.tenant_id != previous.tenant_id
        or successor.project_global_id != previous.project_global_id
        or successor.tooling_master_global_id != previous.tooling_master_global_id
        or successor.revision_number != previous.revision_number + 1
        or successor.predecessor_global_id != previous.global_id
        or successor.predecessor_snapshot_hash != previous.snapshot_hash
    ):
        raise _field_problem(
            "revisionNumber",
            _("The Tooling Revision does not advance its exact predecessor."),
        )


def validate_process_chain_successor(
    previous: ToolingProcessChainRevision,
    successor: ToolingProcessChainRevision,
) -> None:
    if (
        successor.tenant_id != previous.tenant_id
        or successor.project_global_id != previous.project_global_id
        or successor.process_chain_global_id != previous.process_chain_global_id
        or successor.chain_version != previous.chain_version + 1
        or successor.predecessor_global_id != previous.global_id
        or successor.predecessor_snapshot_hash != previous.snapshot_hash
    ):
        raise _field_problem(
            "chainVersion",
            _("The process-chain version does not advance its exact predecessor."),
        )


def measurement_from_dict(value: object, path: str) -> ToolingMeasurement:
    record = _record(value, path, {"value", "unit", "source"})
    return ToolingMeasurement(
        value=record["value"],
        unit=record["unit"],
        source=record["source"],
    )


def tooling_specification_from_dict(value: object) -> ToolingSpecification:
    keys = {
        "toolingType",
        "moldBaseMaterial",
        "coreMaterial",
        "hardness",
        "surfaceTreatment",
        "cavityCount",
        "hotRunner",
        "length",
        "width",
        "height",
        "weight",
        "clampTonnage",
        "tieBarSpacingX",
        "tieBarSpacingY",
        "injectionCapacity",
        "machineType",
        "targetCycle",
        "targetLife",
        "warranty",
        "customerStandard",
        "interfaceRequirement",
        "spareParts",
        "deliveryDocuments",
    }
    record = _record(value, "specification", keys)
    return ToolingSpecification(
        tooling_type=record["toolingType"],
        mold_base_material=record["moldBaseMaterial"],
        core_material=record["coreMaterial"],
        hardness=measurement_from_dict(record["hardness"], "hardness"),
        surface_treatment=record["surfaceTreatment"],
        cavity_count=record["cavityCount"],
        hot_runner=record["hotRunner"],
        length=measurement_from_dict(record["length"], "length"),
        width=measurement_from_dict(record["width"], "width"),
        height=measurement_from_dict(record["height"], "height"),
        weight=measurement_from_dict(record["weight"], "weight"),
        clamp_tonnage=measurement_from_dict(record["clampTonnage"], "clampTonnage"),
        tie_bar_spacing_x=measurement_from_dict(record["tieBarSpacingX"], "tieBarSpacingX"),
        tie_bar_spacing_y=measurement_from_dict(record["tieBarSpacingY"], "tieBarSpacingY"),
        injection_capacity=measurement_from_dict(record["injectionCapacity"], "injectionCapacity"),
        machine_type=record["machineType"],
        target_cycle=measurement_from_dict(record["targetCycle"], "targetCycle"),
        target_life=measurement_from_dict(record["targetLife"], "targetLife"),
        warranty=record["warranty"],
        customer_standard=record["customerStandard"],
        interface_requirement=record["interfaceRequirement"],
        spare_parts=tuple(_list(record["spareParts"], "spareParts", maximum=100)),
        delivery_documents=tuple(_list(record["deliveryDocuments"], "deliveryDocuments", maximum=100)),
    )


def cavity_mapping_from_dict(value: object) -> CavityMapping:
    record = _record(
        value,
        "cavity",
        {
            "globalId",
            "cavityIdentifier",
            "toolingApplicabilityGlobalId",
            "partRevisionGlobalId",
            "structuralState",
        },
    )
    return CavityMapping(
        global_id=record["globalId"],
        cavity_identifier=record["cavityIdentifier"],
        tooling_applicability_global_id=record["toolingApplicabilityGlobalId"],
        part_revision_global_id=record["partRevisionGlobalId"],
        structural_state=_enum(record["structuralState"], CavityStructuralState, "structuralState"),
    )


def insert_applicability_from_dict(value: object) -> InsertApplicability:
    record = _record(
        value,
        "insert",
        {
            "globalId",
            "insertCode",
            "insertVersion",
            "toolingApplicabilityGlobalId",
            "partRevisionGlobalId",
            "modelSourceSystem",
            "modelSourceObjectId",
            "changeoverDuration",
            "validationState",
            "validatedByUserId",
            "validatedAt",
            "validationReason",
        },
    )
    return InsertApplicability(
        global_id=record["globalId"],
        insert_code=record["insertCode"],
        insert_version=record["insertVersion"],
        tooling_applicability_global_id=record["toolingApplicabilityGlobalId"],
        part_revision_global_id=record["partRevisionGlobalId"],
        model_source_system=record["modelSourceSystem"],
        model_source_object_id=record["modelSourceObjectId"],
        changeover_duration=measurement_from_dict(record["changeoverDuration"], "changeoverDuration"),
        validation_state=_enum(record["validationState"], InsertValidationState, "validationState"),
        validated_by_user_id=record["validatedByUserId"],
        validated_at=_optional_datetime(record["validatedAt"], "validatedAt"),
        validation_reason=record["validationReason"],
    )


def external_identity_from_dict(value: object) -> ExternalIdentity:
    record = _record(
        value,
        "externalIdentity",
        {
            "globalId",
            "identityType",
            "value",
            "rawValue",
            "sourceSystem",
            "sourceObjectId",
            "effectiveFrom",
            "effectiveTo",
        },
    )
    return ExternalIdentity(
        global_id=record["globalId"],
        identity_type=_enum(record["identityType"], ExternalIdentityType, "identityType"),
        value=record["value"],
        raw_value=record["rawValue"],
        source_system=record["sourceSystem"],
        source_object_id=record["sourceObjectId"],
        effective_from=_date(record["effectiveFrom"], "effectiveFrom"),
        effective_to=_optional_date(record["effectiveTo"], "effectiveTo"),
    )


def document_revision_reference_from_dict(value: object) -> DocumentRevisionReference:
    record = _record(value, "documentRevision", {"globalId", "snapshotHash"})
    return DocumentRevisionReference(
        global_id=record["globalId"],
        snapshot_hash=record["snapshotHash"],
    )


def part_specification_item_from_dict(value: object) -> PartSpecificationItem:
    record = _record(
        value,
        "item",
        {
            "globalId",
            "kind",
            "normalizedValue",
            "rawValue",
            "sourceSystem",
            "sourceObjectId",
            "effectiveFrom",
            "effectiveTo",
            "unit",
        },
    )
    return PartSpecificationItem(
        global_id=record["globalId"],
        kind=_enum(record["kind"], PartSpecificationKind, "kind"),
        normalized_value=record["normalizedValue"],
        raw_value=record["rawValue"],
        source_system=record["sourceSystem"],
        source_object_id=record["sourceObjectId"],
        effective_from=_date(record["effectiveFrom"], "effectiveFrom"),
        effective_to=_optional_date(record["effectiveTo"], "effectiveTo"),
        unit=record["unit"],
    )


def process_step_from_dict(value: object) -> ToolingProcessStep:
    record = _record(
        value,
        "step",
        {
            "globalId",
            "stepOrder",
            "processKind",
            "toolingRevisionGlobalId",
            "toolingRevisionSnapshotHash",
            "inputPartRevisionGlobalIds",
            "outputPartRevisionGlobalId",
            "parentStepGlobalId",
            "machineType",
            "clampTonnage",
        },
    )
    return ToolingProcessStep(
        global_id=record["globalId"],
        step_order=record["stepOrder"],
        process_kind=_enum(record["processKind"], ToolingProcessKind, "processKind"),
        tooling_revision_global_id=record["toolingRevisionGlobalId"],
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        input_part_revision_global_ids=tuple(
            _list(record["inputPartRevisionGlobalIds"], "inputPartRevisionGlobalIds", maximum=20)
        ),
        output_part_revision_global_id=record["outputPartRevisionGlobalId"],
        parent_step_global_id=record["parentStepGlobalId"],
        machine_type=record["machineType"],
        clamp_tonnage=measurement_from_dict(record["clampTonnage"], "clampTonnage"),
    )


def tooling_revision_from_snapshot(value: object) -> ToolingRevision:
    record = _record(
        value,
        "revisionSnapshot",
        {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "toolingMasterGlobalId",
            "revisionNumber",
            "revisionLabel",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "specification",
            "cavities",
            "inserts",
            "externalIdentities",
            "designDocumentRevisions",
            "reason",
            "revisionKeyHash",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return ToolingRevision(
        global_id=record["globalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        revision_number=record["revisionNumber"],
        revision_label=record["revisionLabel"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        specification=tooling_specification_from_dict(record["specification"]),
        cavities=tuple(
            cavity_mapping_from_dict(item)
            for item in _list(record["cavities"], "cavities", maximum=200)
        ),
        inserts=tuple(
            insert_applicability_from_dict(item)
            for item in _list(record["inserts"], "inserts", maximum=200)
        ),
        external_identities=tuple(
            external_identity_from_dict(item)
            for item in _list(record["externalIdentities"], "externalIdentities", maximum=100)
        ),
        design_document_revisions=tuple(
            document_revision_reference_from_dict(item)
            for item in _list(record["designDocumentRevisions"], "designDocumentRevisions", maximum=50)
        ),
        reason=record["reason"],
        revision_key_hash=record["revisionKeyHash"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
    )


def part_controlled_specification_from_snapshot(value: object) -> PartControlledSpecification:
    record = _record(
        value,
        "specificationSnapshot",
        {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "partGlobalId",
            "partRevisionGlobalId",
            "partRevisionSnapshotHash",
            "items",
            "externalIdentities",
            "specificationKeyHash",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return PartControlledSpecification(
        global_id=record["globalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        part_global_id=record["partGlobalId"],
        part_revision_global_id=record["partRevisionGlobalId"],
        part_revision_snapshot_hash=record["partRevisionSnapshotHash"],
        items=tuple(
            part_specification_item_from_dict(item)
            for item in _list(record["items"], "items", maximum=100)
        ),
        external_identities=tuple(
            external_identity_from_dict(item)
            for item in _list(record["externalIdentities"], "externalIdentities", maximum=100)
        ),
        specification_key_hash=record["specificationKeyHash"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
    )


def process_chain_revision_from_snapshot(value: object) -> ToolingProcessChainRevision:
    record = _record(
        value,
        "chainSnapshot",
        {
            "schemaVersion",
            "globalId",
            "processChainGlobalId",
            "tenantId",
            "projectGlobalId",
            "chainVersion",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "steps",
            "reason",
            "versionKeyHash",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return ToolingProcessChainRevision(
        global_id=record["globalId"],
        process_chain_global_id=record["processChainGlobalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        chain_version=record["chainVersion"],
        predecessor_global_id=record["predecessorGlobalId"],
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        steps=tuple(
            process_step_from_dict(item)
            for item in _list(record["steps"], "steps", maximum=20)
        ),
        reason=record["reason"],
        version_key_hash=record["versionKeyHash"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
    )


def set_revision_binding_from_snapshot(value: object) -> ToolingSetRevisionBinding:
    record = _record(
        value,
        "bindingSnapshot",
        {
            "schemaVersion",
            "globalId",
            "tenantId",
            "projectGlobalId",
            "toolingMasterGlobalId",
            "toolingSetGlobalId",
            "toolingSetSnapshotHash",
            "toolingRevisionGlobalId",
            "toolingRevisionSnapshotHash",
            "reason",
            "bindingKeyHash",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return ToolingSetRevisionBinding(
        global_id=record["globalId"],
        tenant_id=record["tenantId"],
        project_global_id=record["projectGlobalId"],
        tooling_master_global_id=record["toolingMasterGlobalId"],
        tooling_set_global_id=record["toolingSetGlobalId"],
        tooling_set_snapshot_hash=record["toolingSetSnapshotHash"],
        tooling_revision_global_id=record["toolingRevisionGlobalId"],
        tooling_revision_snapshot_hash=record["toolingRevisionSnapshotHash"],
        reason=record["reason"],
        binding_key_hash=record["bindingKeyHash"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime(record["createdAt"], "createdAt"),
        request_id=record["requestId"],
        trace_id=record["traceId"],
    )


def _record(value: object, path: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _field_problem(path, _("Enter a valid closed object."))
    return value


def _list(value: object, path: str, *, maximum: int) -> list[object]:
    if not isinstance(value, list) or len(value) > maximum:
        raise _field_problem(path, _("Enter a valid bounded list."))
    return value


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


def _uuid_tuple(value: object, path: str, *, maximum: int) -> tuple[UUID, ...]:
    if not isinstance(value, (tuple, list)) or len(value) > maximum:
        raise _field_problem(path, _("Enter a valid bounded list."))
    normalized = tuple(_uuid(item, path) for item in value)
    if len(normalized) != len(set(normalized)):
        raise _field_problem(path, _("Global IDs must be unique within this list."))
    return normalized


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid(value, path)


def _positive(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _field_problem(path, _("Enter a positive whole number."))
    return value


def _positive_decimal(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a positive decimal value."))
    normalized = value.strip()
    try:
        decimal = Decimal(normalized)
    except InvalidOperation as error:
        raise _field_problem(path, _("Enter a positive decimal value.")) from error
    if (
        not decimal.is_finite()
        or decimal <= 0
        or len(normalized) > 32
        or decimal.adjusted() > 24
        or decimal.adjusted() < -24
    ):
        raise _field_problem(path, _("Enter a positive decimal value."))
    canonical = format(decimal.normalize(), "f")
    return canonical if "." in canonical else f"{canonical}.0"


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field_problem(path, _("The value is too long."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value in (None, "") else _text(value, path, maximum)


def _string_tuple(
    value: object,
    path: str,
    *,
    maximum: int,
    item_maximum: int,
) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or len(value) > maximum:
        raise _field_problem(path, _("Enter a valid bounded list."))
    return tuple(_text(item, path, item_maximum) for item in value)


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


def _optional_hash(value: object, path: str) -> str | None:
    return None if value in (None, "") else _hash(value, path)


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
        return _aware_utc(value, path)
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _field_problem(path, _("Enter a timezone-aware date and time.")) from error
    return _aware_utc(parsed, path)


def _optional_datetime(value: object, path: str) -> datetime | None:
    return None if value in (None, "") else _datetime(value, path)


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


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
