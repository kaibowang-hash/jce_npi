from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


QUALITY_LINK_SCHEMA_VERSION = 1
QUALITY_LINK_OPERATION = "link_observed_formal_quality_reference"
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


class QualityLinkContractError(ValueError):
    """Raised when formal-quality link input is not exact and closed."""


class QualitySourceKind(StrEnum):
    TRIAL_ROUND = "trial_round"
    TRIAL_DEFECT = "trial_defect"
    TRIAL_REVIEW = "trial_review"
    READINESS_ASSESSMENT = "readiness_assessment"
    CONTROLLED_QUALITY_REPORT = "controlled_quality_report"


class FormalQualityRecordKind(StrEnum):
    QUALITY_INSPECTION = "quality_inspection"
    NCR = "ncr"
    CAPA = "capa"


class QualityLinkState(StrEnum):
    LINKED = "linked"
    SUPERSEDED = "superseded"


class QualityLinkFaultKind(StrEnum):
    UNAVAILABLE = "unavailable"
    PERMISSION_DENIED = "permission_denied"
    SOURCE_CONFLICT = "source_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True, slots=True)
class QualitySourceReference:
    tenant_id: str
    project_global_id: UUID
    source_kind: QualitySourceKind
    source_global_id: UUID
    source_version: int
    source_state: str
    source_snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _tenant(self.tenant_id))
        object.__setattr__(self, "project_global_id", _uuid(self.project_global_id, "projectGlobalId"))
        if not isinstance(self.source_kind, QualitySourceKind):
            raise QualityLinkContractError("sourceKind is unsupported.")
        object.__setattr__(self, "source_global_id", _uuid(self.source_global_id, "sourceGlobalId"))
        object.__setattr__(self, "source_version", _positive(self.source_version, "sourceVersion"))
        object.__setattr__(self, "source_state", _code(self.source_state, "sourceState"))
        object.__setattr__(self, "source_snapshot_hash", _hash(self.source_snapshot_hash, "sourceSnapshotHash"))

    def payload(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "sourceKind": self.source_kind.value,
            "sourceGlobalId": str(self.source_global_id),
            "sourceVersion": self.source_version,
            "sourceState": self.source_state,
            "sourceSnapshotHash": self.source_snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class FormalQualityObservationReference:
    tenant_id: str
    project_global_id: UUID
    scope_kind: str
    scope_global_id: UUID
    observation_global_id: UUID
    head_global_id: UUID
    head_optimistic_version: int
    source_object_type: str
    source_object_id: str
    source_version: str
    record_kind: FormalQualityRecordKind
    status_code: str
    result_code: str | None
    payload_hash: str
    observation_hash: str
    head_hash: str
    freshness_policy_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _tenant(self.tenant_id))
        for name in ("project_global_id", "scope_global_id", "observation_global_id", "head_global_id"):
            object.__setattr__(self, name, _uuid(getattr(self, name), _camel(name)))
        object.__setattr__(self, "scope_kind", _one_of(self.scope_kind, "scopeKind", {"project", "trial_round", "readiness"}))
        object.__setattr__(self, "head_optimistic_version", _positive(self.head_optimistic_version, "headOptimisticVersion"))
        object.__setattr__(self, "source_object_type", _text(self.source_object_type, "sourceObjectType", 100))
        object.__setattr__(self, "source_object_id", _text(self.source_object_id, "sourceObjectId", 255))
        object.__setattr__(self, "source_version", _text(self.source_version, "sourceVersion", 255))
        if not isinstance(self.record_kind, FormalQualityRecordKind):
            raise QualityLinkContractError("recordKind is unsupported.")
        object.__setattr__(self, "status_code", _code(self.status_code, "statusCode"))
        if self.result_code is not None:
            object.__setattr__(self, "result_code", _code(self.result_code, "resultCode"))
        for name in ("payload_hash", "observation_hash", "head_hash"):
            object.__setattr__(self, name, _hash(getattr(self, name), _camel(name)))
        object.__setattr__(self, "freshness_policy_ref", _code(self.freshness_policy_ref, "freshnessPolicyRef"))

    @property
    def projection_kind(self) -> str:
        return "formal_quality_status"

    @property
    def source_system(self) -> str:
        return "ERPNEXT"

    @property
    def availability(self) -> str:
        return "available"

    @property
    def freshness(self) -> str:
        return "fresh"

    @property
    def disposition(self) -> str:
        return "applied_current"

    def payload(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "scopeKind": self.scope_kind,
            "scopeGlobalId": str(self.scope_global_id),
            "projectionKind": self.projection_kind,
            "sourceSystem": self.source_system,
            "availability": self.availability,
            "freshness": self.freshness,
            "disposition": self.disposition,
            "observationGlobalId": str(self.observation_global_id),
            "headGlobalId": str(self.head_global_id),
            "headOptimisticVersion": self.head_optimistic_version,
            "sourceObjectType": self.source_object_type,
            "sourceObjectId": self.source_object_id,
            "sourceVersion": self.source_version,
            "recordKind": self.record_kind.value,
            "statusCode": self.status_code,
            "resultCode": self.result_code,
            "payloadHash": self.payload_hash,
            "observationHash": self.observation_hash,
            "headHash": self.head_hash,
            "freshnessPolicyRef": self.freshness_policy_ref,
        }


@dataclass(frozen=True, slots=True)
class QualityLinkRevision:
    global_id: UUID
    stream_key_hash: str
    revision_number: int
    predecessor_global_id: UUID | None
    source: QualitySourceReference
    observation: FormalQualityObservationReference
    state: QualityLinkState
    actor_user_id: str
    trace_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(self, "stream_key_hash", _hash(self.stream_key_hash, "streamKeyHash"))
        object.__setattr__(self, "revision_number", _positive(self.revision_number, "revisionNumber"))
        predecessor = self.predecessor_global_id
        if self.revision_number == 1:
            if predecessor is not None:
                raise QualityLinkContractError("The first link revision cannot have a predecessor.")
        elif predecessor is None:
            raise QualityLinkContractError("A successor link revision requires its exact predecessor.")
        else:
            object.__setattr__(self, "predecessor_global_id", _uuid(predecessor, "predecessorGlobalId"))
        if not isinstance(self.source, QualitySourceReference) or not isinstance(self.observation, FormalQualityObservationReference):
            raise QualityLinkContractError("Link source and formal observation are required.")
        if (self.source.tenant_id, self.source.project_global_id) != (self.observation.tenant_id, self.observation.project_global_id):
            raise QualityLinkContractError("Link source and observation must share exact tenant and Project containment.")
        if not isinstance(self.state, QualityLinkState):
            raise QualityLinkContractError("linkState is unsupported.")
        object.__setattr__(self, "actor_user_id", _text(self.actor_user_id, "actorUserId", 254))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))

    def payload(self) -> dict[str, object]:
        return {
            "schemaVersion": QUALITY_LINK_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "streamKeyHash": self.stream_key_hash,
            "revisionNumber": self.revision_number,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "source": self.source.payload(),
            "formalObservation": self.observation.payload(),
            "linkState": self.state.value,
            "actorUserId": self.actor_user_id,
            "traceId": self.trace_id,
            "createdAt": _utc(self.created_at),
        }

    @property
    def payload_hash(self) -> str:
        return canonical_payload_hash(self.payload())


@dataclass(frozen=True, slots=True)
class QualityLinkCommandIdentity:
    tenant_id: str
    project_global_id: UUID
    actor_user_id: str
    operation: str
    idempotency_key_hash: str
    payload_hash: str
    source_snapshot_hash: str
    projection_head_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _tenant(self.tenant_id))
        object.__setattr__(self, "project_global_id", _uuid(self.project_global_id, "projectGlobalId"))
        object.__setattr__(self, "actor_user_id", _text(self.actor_user_id, "actorUserId", 254))
        if self.operation != QUALITY_LINK_OPERATION:
            raise QualityLinkContractError("Quality link operation is unsupported.")
        for name in ("idempotency_key_hash", "payload_hash", "source_snapshot_hash", "projection_head_hash"):
            object.__setattr__(self, name, _hash(getattr(self, name), _camel(name)))

    def payload(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "actorUserId": self.actor_user_id,
            "operation": self.operation,
            "idempotencyKeyHash": self.idempotency_key_hash,
            "payloadHash": self.payload_hash,
            "sourceSnapshotHash": self.source_snapshot_hash,
            "projectionHeadHash": self.projection_head_hash,
        }

    @property
    def receipt_key_hash(self) -> str:
        return canonical_payload_hash(self.payload())


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise QualityLinkContractError("Canonical payload must be an object.")
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise QualityLinkContractError("Canonical payload is not JSON-safe.") from error
    return hashlib.sha256(encoded).hexdigest()


def _uuid(value: object, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise QualityLinkContractError(f"{field} must be a valid global ID.") from error


def _text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str) or value != value.strip() or not value or len(value) > maximum:
        raise QualityLinkContractError(f"{field} is invalid.")
    return value


def _code(value: object, field: str) -> str:
    result = _text(value, field, 128)
    if _CODE.fullmatch(result) is None:
        raise QualityLinkContractError(f"{field} is invalid.")
    return result


def _tenant(value: object) -> str:
    result = _text(value, "tenantId", 128)
    if _TENANT.fullmatch(result) is None:
        raise QualityLinkContractError("tenantId is invalid.")
    return result


def _hash(value: object, field: str) -> str:
    result = _text(value, field, 64)
    if _HASH.fullmatch(result) is None:
        raise QualityLinkContractError(f"{field} must be a SHA-256 value.")
    return result


def _positive(value: object, field: str) -> int:
    if type(value) is not int or value < 1:
        raise QualityLinkContractError(f"{field} must be a positive whole number.")
    return value


def _one_of(value: object, field: str, allowed: set[str]) -> str:
    result = _text(value, field, 128)
    if result not in allowed:
        raise QualityLinkContractError(f"{field} is unsupported.")
    return result


def _datetime(value: object, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise QualityLinkContractError(f"{field} must be a date-time.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])
