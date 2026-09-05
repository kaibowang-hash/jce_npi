from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid5


SCHEMA_VERSION = 1
OPERATION = "replace_master_catalog"
SOURCE_SYSTEM = "ERPNEXT"
TARGET_SYSTEM = "NPI_ONE"
MAX_RECORDS = 10_000
EVENT_NAMESPACE = UUID("fd32b6e2-5eaf-46b3-aa1b-e1f432728fa7")
REQUEST_NAMESPACE = UUID("4eae6c67-fb0d-4aa6-8e64-1df2b27cb2f2")
UTC = timezone.utc


class MasterDataSenderError(ValueError):
    """Raised when an ERPNext master catalog cannot be represented safely."""


class MasterCatalogKind(str, Enum):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    ITEM_GROUP = "item_group"
    ITEM = "item"


@dataclass(frozen=True, slots=True)
class SourceMasterSnapshot:
    kind: MasterCatalogKind
    source_modified_at: datetime
    records: tuple[Mapping[str, object], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, MasterCatalogKind):
            raise MasterDataSenderError("Master catalog kind is invalid.")
        _utc(self.source_modified_at)
        if len(self.records) > MAX_RECORDS:
            raise MasterDataSenderError("Master catalog exceeds the safe bound.")
        keys = tuple(str(record.get("sourceKey", "")) for record in self.records)
        if keys != tuple(sorted(set(keys))) or any(not key for key in keys):
            raise MasterDataSenderError(
                "Master catalog records must be unique and sorted."
            )

    def payload(self, *, source_version: int) -> dict[str, object]:
        if type(source_version) is not int or not 1 <= source_version <= 2_147_483_647:
            raise MasterDataSenderError("Master catalog source version is invalid.")
        return {
            "catalogKind": self.kind.value,
            "sourceVersion": source_version,
            "sourceModifiedAt": utc_text(self.source_modified_at),
            "records": [dict(record) for record in self.records],
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(
            {
                "catalogKind": self.kind.value,
                "sourceModifiedAt": utc_text(self.source_modified_at),
                "records": [dict(record) for record in self.records],
            }
        )


@dataclass(frozen=True, slots=True)
class MasterSnapshotEvent:
    event: Mapping[str, object]
    request_id: UUID
    source_snapshot_hash: str

    @property
    def event_id(self) -> UUID:
        return UUID(str(self.event["eventId"]))

    @property
    def kind(self) -> MasterCatalogKind:
        return MasterCatalogKind(self.event["catalogKind"])

    @property
    def source_version(self) -> int:
        return int(self.event["sourceVersion"])

    @property
    def trace_id(self) -> str:
        return str(self.event["traceId"])

    @property
    def payload_hash(self) -> str:
        return str(self.event["payloadHash"])

    @property
    def event_hash(self) -> str:
        return canonical_hash(self.event)


def build_event(
    snapshot: SourceMasterSnapshot,
    *,
    source_version: int,
    issued_at: datetime,
    source_environment: str,
) -> MasterSnapshotEvent:
    if not isinstance(snapshot, SourceMasterSnapshot):
        raise MasterDataSenderError("Master catalog snapshot is invalid.")
    issued = _utc(issued_at)
    payload = snapshot.payload(source_version=source_version)
    if source_environment not in {
        "sandbox",
        "test",
        "testing",
        "qa",
        "staging",
        "stage",
    }:
        raise MasterDataSenderError("Master catalog source environment is invalid.")
    payload["sourceEnvironment"] = source_environment
    payload_hash = canonical_hash(payload)
    identity = f"{snapshot.kind.value}:{source_version}:{payload_hash}"
    event_id = uuid5(EVENT_NAMESPACE, identity)
    event = {
        "schemaVersion": SCHEMA_VERSION,
        "operation": OPERATION,
        "sourceSystem": SOURCE_SYSTEM,
        "targetSystem": TARGET_SYSTEM,
        "eventId": str(event_id),
        **payload,
        "issuedAt": utc_text(issued),
        "traceId": f"erp-master-{event_id.hex}",
        "payloadHash": payload_hash,
    }
    return MasterSnapshotEvent(
        event,
        uuid5(REQUEST_NAMESPACE, identity),
        snapshot.snapshot_hash,
    )


def restore_event(
    raw_event: object,
    *,
    request_id: object,
    source_snapshot_hash: object,
    event_hash: object,
) -> MasterSnapshotEvent:
    if not isinstance(raw_event, str):
        raise MasterDataSenderError("Stored master catalog event is invalid.")
    try:
        event = json.loads(raw_event)
        candidate = MasterSnapshotEvent(
            event,
            UUID(str(request_id)),
            str(source_snapshot_hash),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise MasterDataSenderError("Stored master catalog event is invalid.") from error
    identity = f"{candidate.kind.value}:{candidate.source_version}:{candidate.payload_hash}"
    expected_snapshot_hash = canonical_hash(
        {
            "catalogKind": candidate.kind.value,
            "sourceModifiedAt": event.get("sourceModifiedAt"),
            "records": event.get("records"),
        }
    )
    if (
        not isinstance(event, Mapping)
        or canonical_json(event) != raw_event
        or candidate.request_id != uuid5(REQUEST_NAMESPACE, identity)
        or candidate.event_id != uuid5(EVENT_NAMESPACE, identity)
        or candidate.event_hash != event_hash
        or candidate.source_snapshot_hash != expected_snapshot_hash
    ):
        raise MasterDataSenderError("Stored master catalog event binding is invalid.")
    return candidate


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
        raise MasterDataSenderError("Master catalog JSON is invalid.") from error


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_text(value: datetime) -> str:
    return _utc(value).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise MasterDataSenderError("Master catalog time is invalid.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
