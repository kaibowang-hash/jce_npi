from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
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
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_REFERENCE_SYSTEMS = frozenset({"NPI_ONE", "ERPNEXT"})


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


class ToolingRequirementKind(StrEnum):
    NEW_TOOL = "new_tool"
    CUSTOMER_OWNED_INTAKE = "customer_owned_intake"
    COPY_OR_ADDITIONAL_SET = "copy_or_additional_set"
    MODIFICATION = "modification"
    REPAIR = "repair"
    CAPACITY_NEED = "capacity_need"


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
