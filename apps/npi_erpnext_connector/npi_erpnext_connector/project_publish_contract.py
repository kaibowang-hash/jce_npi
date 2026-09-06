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
MAX_REQUEST_BYTES = 262_144
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


class ProjectPublishContractError(ValueError):
    """Raised when a Project publication command is not exactly shaped."""


@dataclass(frozen=True, slots=True)
class ProjectPublishCommand:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    actor_user_id: str
    tenant_id: str
    project_global_id: str
    business_code: str
    title: str
    project_type: str
    target_sop: str
    source_version: int
    raw: Mapping[str, object]

    @property
    def semantic_request_hash(self) -> str:
        value = dict(self.raw)
        value.pop("attemptGlobalId", None)
        value.pop("attemptNumber", None)
        return canonical_hash(value)


@dataclass(frozen=True, slots=True)
class ProjectReconcileCommand:
    request_global_id: str
    attempt_global_id: str
    target_idempotency_key_hash: str
    source_hash: str


def decode_publish_command(raw_body: bytes) -> ProjectPublishCommand:
    value = _closed(_decode(raw_body), {"contractVersion", "operation", "requestGlobalId", "attemptGlobalId", "attemptNumber", "targetIdempotencyKeyHash", "sourceHash", "actorUserId", "source"}, "Project command")
    if value["contractVersion"] != CONTRACT_VERSION or value["operation"] != OPERATION:
        raise ProjectPublishContractError("Project command contract is unsupported.")
    source = _closed(value["source"], {"schemaVersion", "tenantId", "projectGlobalId", "businessCode", "title", "projectType", "targetSop", "actorUserId", "sourceVersion"}, "Project source")
    if source["schemaVersion"] != SOURCE_SCHEMA_VERSION:
        raise ProjectPublishContractError("Project source contract is unsupported.")
    actor = _actor(value["actorUserId"])
    if actor != _actor(source["actorUserId"]):
        raise ProjectPublishContractError("Project business actor does not match its source.")
    source_hash = _hash(value["sourceHash"])
    if canonical_hash(source) != source_hash:
        raise ProjectPublishContractError("Project source hash does not match.")
    tenant = _pattern(source["tenantId"], _TENANT, "tenantId")
    project_id = _uuid(source["projectGlobalId"], "projectGlobalId")
    idempotency = _hash(value["targetIdempotencyKeyHash"])
    if idempotency != canonical_hash({"operation": OPERATION, "tenantId": tenant, "projectGlobalId": project_id}):
        raise ProjectPublishContractError("Project idempotency identity does not match.")
    title = _text(source["title"], "title", 140)
    project_type = source["projectType"]
    if project_type not in {"customer_owned_tool", "new_tool", "tool_change"}:
        raise ProjectPublishContractError("Project type is invalid.")
    target_sop = _text(source["targetSop"], "targetSop", 10)
    try:
        date.fromisoformat(target_sop)
    except ValueError as error:
        raise ProjectPublishContractError("Project targetSop is invalid.") from error
    attempt_number = value["attemptNumber"]
    source_version = source["sourceVersion"]
    if type(attempt_number) is not int or attempt_number < 1 or type(source_version) is not int or source_version < 1:
        raise ProjectPublishContractError("Project version is invalid.")
    return ProjectPublishCommand(_uuid(value["requestGlobalId"], "requestGlobalId"), _uuid(value["attemptGlobalId"], "attemptGlobalId"), attempt_number, idempotency, source_hash, actor, tenant, project_id, _pattern(source["businessCode"], _CODE, "businessCode"), title, str(project_type), target_sop, source_version, value)


def decode_reconcile_command(raw_body: bytes) -> ProjectReconcileCommand:
    value = _closed(_decode(raw_body), {"contractVersion", "operation", "requestGlobalId", "attemptGlobalId", "targetIdempotencyKeyHash", "sourceHash"}, "Project reconciliation command")
    if value["contractVersion"] != CONTRACT_VERSION or value["operation"] != RECONCILE_OPERATION:
        raise ProjectPublishContractError("Project reconciliation contract is unsupported.")
    return ProjectReconcileCommand(_uuid(value["requestGlobalId"], "requestGlobalId"), _uuid(value["attemptGlobalId"], "attemptGlobalId"), _hash(value["targetIdempotencyKeyHash"]), _hash(value["sourceHash"]))


def canonical_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _decode(raw_body: bytes) -> object:
    if not isinstance(raw_body, bytes) or not raw_body or len(raw_body) > MAX_REQUEST_BYTES:
        raise ProjectPublishContractError("Project command body is invalid.")
    try:
        return json.loads(raw_body.decode(), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProjectPublishContractError("Project command JSON is invalid.") from error


def _closed(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ProjectPublishContractError(f"{label} shape is invalid.")
    return value


def _uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ProjectPublishContractError(f"Project {label} is invalid.") from error


def _hash(value: object) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ProjectPublishContractError("Project hash is invalid.")
    return value


def _actor(value: object) -> str:
    if not isinstance(value, str) or value != value.casefold() or len(value) > 254 or _ACTOR.fullmatch(value) is None:
        raise ProjectPublishContractError("Project actor is invalid.")
    return value


def _pattern(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ProjectPublishContractError(f"Project {label} is invalid.")
    return value


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ProjectPublishContractError(f"Project {label} is invalid.")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ProjectPublishContractError("Project JSON contains duplicate keys.")
        value[key] = item
    return value
