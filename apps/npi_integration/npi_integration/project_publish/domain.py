from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from uuid import UUID


CONTRACT_VERSION = 1
SOURCE_SCHEMA_VERSION = 1
OPERATION = "create_erp_project"
RECONCILE_OPERATION = "reconcile_erp_project"
EVENT_TYPE = "npi.erp_project_create.requested.v1"
MAX_REQUEST_BYTES = 262_144
MAX_AUTOMATIC_ATTEMPTS = 3
MAX_ATTEMPTS = 20

_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


class ProjectPublishError(ValueError):
    """Raised when an outbound Project value is not contract-safe."""


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ProjectPublishError(f"Project {label} is invalid.") from error
    return str(parsed)


@dataclass(frozen=True, slots=True)
class ProjectSource:
    tenant_id: str
    project_global_id: str
    business_code: str
    title: str
    project_type: str
    target_sop: str
    actor_user_id: str
    source_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or _TENANT.fullmatch(self.tenant_id) is None:
            raise ProjectPublishError("Project tenantId is invalid.")
        object.__setattr__(
            self,
            "project_global_id",
            parse_uuid(self.project_global_id, "projectGlobalId"),
        )
        if not isinstance(self.business_code, str) or _CODE.fullmatch(self.business_code) is None:
            raise ProjectPublishError("Project businessCode is invalid.")
        if (
            not isinstance(self.title, str)
            or not self.title
            or self.title != self.title.strip()
            or len(self.title) > 140
        ):
            raise ProjectPublishError("Project title is invalid.")
        if self.project_type not in {"customer_owned_tool", "new_tool", "tool_change"}:
            raise ProjectPublishError("Project projectType is invalid.")
        try:
            date.fromisoformat(self.target_sop)
        except (TypeError, ValueError) as error:
            raise ProjectPublishError("Project targetSop is invalid.") from error
        if (
            not isinstance(self.actor_user_id, str)
            or self.actor_user_id != self.actor_user_id.casefold()
            or len(self.actor_user_id) > 254
            or _ACTOR.fullmatch(self.actor_user_id) is None
        ):
            raise ProjectPublishError("Project actorUserId is invalid.")
        if type(self.source_version) is not int or self.source_version < 1:
            raise ProjectPublishError("Project sourceVersion is invalid.")

    @property
    def snapshot(self) -> dict[str, object]:
        return {
            "schemaVersion": SOURCE_SCHEMA_VERSION,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "businessCode": self.business_code,
            "title": self.title,
            "projectType": self.project_type,
            "targetSop": self.target_sop,
            "actorUserId": self.actor_user_id,
            "sourceVersion": self.source_version,
        }

    @property
    def source_hash(self) -> str:
        return canonical_hash(self.snapshot)

    @property
    def target_idempotency_key_hash(self) -> str:
        return canonical_hash(
            {
                "operation": OPERATION,
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
            }
        )


@dataclass(frozen=True, slots=True)
class PublishCommand:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    source: ProjectSource

    def payload(self) -> dict[str, object]:
        return {
            "contractVersion": CONTRACT_VERSION,
            "operation": OPERATION,
            "requestGlobalId": parse_uuid(self.request_global_id, "requestGlobalId"),
            "attemptGlobalId": parse_uuid(self.attempt_global_id, "attemptGlobalId"),
            "attemptNumber": self.attempt_number,
            "targetIdempotencyKeyHash": self.source.target_idempotency_key_hash,
            "sourceHash": self.source.source_hash,
            "actorUserId": self.source.actor_user_id,
            "source": self.source.snapshot,
        }


@dataclass(frozen=True, slots=True)
class ReconcileCommand:
    request_global_id: str
    attempt_global_id: str
    source: ProjectSource

    def payload(self) -> dict[str, object]:
        return {
            "contractVersion": CONTRACT_VERSION,
            "operation": RECONCILE_OPERATION,
            "requestGlobalId": parse_uuid(self.request_global_id, "requestGlobalId"),
            "attemptGlobalId": parse_uuid(self.attempt_global_id, "attemptGlobalId"),
            "targetIdempotencyKeyHash": self.source.target_idempotency_key_hash,
            "sourceHash": self.source.source_hash,
        }


@dataclass(frozen=True, slots=True)
class TargetObservation:
    http_status: int
    response_hash: str
    authenticated: bool
    contract_valid: bool
    formal_project_id: str | None
    target_version: str | None
    exact_replay: bool
    error_code: str | None
    found: bool | None = None


def restore_source(value: object, *, expected_hash: object) -> ProjectSource:
    try:
        raw = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError) as error:
        raise ProjectPublishError("Persisted Project source is invalid.") from error
    if not isinstance(raw, Mapping) or set(raw) != {
        "schemaVersion",
        "tenantId",
        "projectGlobalId",
        "businessCode",
        "title",
        "projectType",
        "targetSop",
        "actorUserId",
        "sourceVersion",
    } or raw.get("schemaVersion") != SOURCE_SCHEMA_VERSION:
        raise ProjectPublishError("Persisted Project source shape is invalid.")
    source = ProjectSource(
        tenant_id=str(raw["tenantId"]),
        project_global_id=str(raw["projectGlobalId"]),
        business_code=str(raw["businessCode"]),
        title=str(raw["title"]),
        project_type=str(raw["projectType"]),
        target_sop=str(raw["targetSop"]),
        actor_user_id=str(raw["actorUserId"]),
        source_version=raw["sourceVersion"],
    )
    if not isinstance(expected_hash, str) or _HASH.fullmatch(expected_hash) is None or source.source_hash != expected_hash:
        raise ProjectPublishError("Persisted Project source hash does not match.")
    return source
