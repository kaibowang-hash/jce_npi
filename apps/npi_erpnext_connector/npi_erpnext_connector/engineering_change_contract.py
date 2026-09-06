from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

CONTRACT_VERSION = 1
SOURCE_API_VERSION = "npi.change-implementation-summary.v1"
OPERATION = "record_change_implementation_summary"
FORMAL_CHANGE_DOCTYPE = "Engineering Change Request"
MAX_REQUEST_BYTES = 262_144

_HASH = re.compile(r"^[a-f0-9]{64}$")
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TEXT = re.compile(r"^[^\x00-\x1f\x7f]{1,254}$")


class EngineeringChangeContractError(ValueError):
    """Raised when an implementation summary command is not exact."""


@dataclass(frozen=True, slots=True)
class EngineeringChangeSummaryCommand:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    actor_user_id: str
    tenant_id: str
    project_global_id: str
    change_global_id: str
    revision_global_id: str
    revision_number: int
    revision_snapshot_hash: str
    formal_change: Mapping[str, object]
    affected_versions_hash: str
    effectivity_hash: str
    disposition_hash: str
    revalidation_hash: str
    closure_evidence_hash: str
    profile_id: str
    profile_version: int
    profile_snapshot_hash: str
    raw: Mapping[str, object]

    @property
    def semantic_request_hash(self) -> str:
        value = dict(self.raw)
        value.pop("attemptGlobalId", None)
        value.pop("attemptNumber", None)
        return canonical_hash(value)


def decode_summary_command(raw_body: bytes) -> EngineeringChangeSummaryCommand:
    if not isinstance(raw_body, bytes) or not 2 <= len(raw_body) <= MAX_REQUEST_BYTES:
        raise EngineeringChangeContractError(
            "Engineering Change command body is invalid."
        )
    try:
        value = json.loads(raw_body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise EngineeringChangeContractError(
            "Engineering Change command body is invalid."
        ) from error
    return parse_summary_command(value)


def parse_summary_command(value: object) -> EngineeringChangeSummaryCommand:
    raw = _closed(
        value,
        {
            "contractVersion",
            "operation",
            "requestGlobalId",
            "attemptGlobalId",
            "attemptNumber",
            "targetIdempotencyKeyHash",
            "sourceHash",
            "actorUserId",
            "source",
        },
    )
    if raw["contractVersion"] != CONTRACT_VERSION or raw["operation"] != OPERATION:
        raise EngineeringChangeContractError(
            "Engineering Change command contract is unsupported."
        )
    request_id = _uuid(raw["requestGlobalId"], "requestGlobalId")
    attempt_id = _uuid(raw["attemptGlobalId"], "attemptGlobalId")
    attempt_number = _positive(raw["attemptNumber"], "attemptNumber")
    idempotency_hash = _hash(
        raw["targetIdempotencyKeyHash"], "targetIdempotencyKeyHash"
    )
    source_hash = _hash(raw["sourceHash"], "sourceHash")
    actor = _actor(raw["actorUserId"])
    source = _closed(
        raw["source"],
        {
            "api_version",
            "operation",
            "tenant_id",
            "project_global_id",
            "change_global_id",
            "revision_global_id",
            "revision_number",
            "revision_snapshot_hash",
            "formal_change",
            "affected_versions_hash",
            "effectivity_hash",
            "disposition_hash",
            "revalidation_hash",
            "closure_evidence_hash",
            "actor_user_id",
            "request_global_id",
            "profile_id",
            "profile_version",
            "profile_snapshot_hash",
            "source_hash",
        },
    )
    if source["api_version"] != SOURCE_API_VERSION or source["operation"] != OPERATION:
        raise EngineeringChangeContractError(
            "Engineering Change source contract is unsupported."
        )
    tenant_id = _text(source["tenant_id"], "tenant_id", 128)
    project_id = _uuid(source["project_global_id"], "project_global_id")
    change_id = _uuid(source["change_global_id"], "change_global_id")
    revision_id = _uuid(source["revision_global_id"], "revision_global_id")
    revision_number = _positive(source["revision_number"], "revision_number")
    revision_hash = _hash(source["revision_snapshot_hash"], "revision_snapshot_hash")
    formal = _formal_change(source["formal_change"])
    affected = _hash(source["affected_versions_hash"], "affected_versions_hash")
    effectivity = _hash(source["effectivity_hash"], "effectivity_hash")
    disposition = _hash(source["disposition_hash"], "disposition_hash")
    revalidation = _hash(source["revalidation_hash"], "revalidation_hash")
    closure = _hash(source["closure_evidence_hash"], "closure_evidence_hash")
    profile_id = _text(source["profile_id"], "profile_id", 140)
    profile_version = _positive(source["profile_version"], "profile_version")
    profile_hash = _hash(source["profile_snapshot_hash"], "profile_snapshot_hash")
    if (
        source["actor_user_id"] != actor
        or source["request_global_id"] != request_id
        or source["source_hash"] != source_hash
    ):
        raise EngineeringChangeContractError(
            "Engineering Change source identity is inconsistent."
        )
    summary = {
        key: source[key]
        for key in (
            "api_version",
            "operation",
            "tenant_id",
            "project_global_id",
            "change_global_id",
            "revision_global_id",
            "revision_number",
            "revision_snapshot_hash",
            "formal_change",
            "affected_versions_hash",
            "effectivity_hash",
            "disposition_hash",
            "revalidation_hash",
            "closure_evidence_hash",
        )
    }
    if canonical_hash(summary) != source_hash:
        raise EngineeringChangeContractError(
            "Engineering Change source hash does not match."
        )
    return EngineeringChangeSummaryCommand(
        request_id,
        attempt_id,
        attempt_number,
        idempotency_hash,
        source_hash,
        actor,
        tenant_id,
        project_id,
        change_id,
        revision_id,
        revision_number,
        revision_hash,
        formal,
        affected,
        effectivity,
        disposition,
        revalidation,
        closure,
        profile_id,
        profile_version,
        profile_hash,
        raw,
    )


def _formal_change(value: object) -> Mapping[str, object]:
    formal = _closed(
        value,
        {
            "doctype",
            "documentName",
            "rawStatus",
            "sourceVersion",
            "sourceModifiedAt",
            "sourceHash",
            "observedAt",
        },
    )
    if formal["doctype"] != FORMAL_CHANGE_DOCTYPE:
        raise EngineeringChangeContractError(
            "Engineering Change formal document type is invalid."
        )
    _text(formal["documentName"], "formal_change.documentName", 140)
    _text(formal["rawStatus"], "formal_change.rawStatus", 140)
    _text(formal["sourceVersion"], "formal_change.sourceVersion", 140)
    _hash(formal["sourceHash"], "formal_change.sourceHash")
    _datetime(formal["sourceModifiedAt"], "formal_change.sourceModifiedAt")
    _datetime(formal["observedAt"], "formal_change.observedAt")
    return formal


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise EngineeringChangeContractError(
            "Engineering Change value is not canonical JSON."
        ) from error


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _closed(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise EngineeringChangeContractError(
            "Engineering Change command shape is invalid."
        )
    return dict(value)


def _uuid(value: object, label: str) -> str:
    try:
        result = str(UUID(str(value)))
    except (TypeError, ValueError) as error:
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        ) from error
    if result != value:
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        )
    return result


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        )
    return value


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        )
    return value


def _actor(value: object) -> str:
    if (
        not isinstance(value, str)
        or value != value.casefold()
        or len(value) > 254
        or _ACTOR.fullmatch(value) is None
        or value in {"guest", "administrator"}
    ):
        raise EngineeringChangeContractError(
            "Engineering Change actorUserId is invalid."
        )
    return value


def _text(value: object, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or _TEXT.fullmatch(value) is None
        or value != value.strip()
    ):
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        )
    return value


def _datetime(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        ) from error
    if parsed.tzinfo is None:
        raise EngineeringChangeContractError(
            f"Engineering Change {label} is invalid."
        )
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise EngineeringChangeContractError(
                "Engineering Change JSON contains duplicate keys."
            )
        value[key] = item
    return value
