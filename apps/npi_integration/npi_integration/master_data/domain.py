from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from uuid import UUID, uuid5


SCHEMA_VERSION = 1
OPERATION = "replace_master_catalog"
SOURCE_SYSTEM = "ERPNEXT"
TARGET_SYSTEM = "NPI_ONE"
MAX_RECORDS = 10_000
HEAD_NAMESPACE = UUID("8e104483-48fb-4594-b65e-36f57d31ff2f")
SNAPSHOT_NAMESPACE = UUID("e8756681-e6b2-4135-bf71-97b78f88ea41")
ENTRY_NAMESPACE = UUID("9b7319d0-ce2b-4ed0-a9c5-a1cd1afdd7a2")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_TEST_ENVIRONMENTS = {"sandbox", "test", "testing", "qa", "staging", "stage"}


class MasterDataContractError(ValueError):
    """Raised when ERPNext master data does not match the closed contract."""


class MasterCatalogKind(str, Enum):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    ITEM_GROUP = "item_group"
    ITEM = "item"
    MACHINE = "machine"


_RECORD_FIELDS = {
    MasterCatalogKind.MACHINE: frozenset(
        {"sourceKey", "displayName", "enabled", "groupKey", "sourceModifiedAt"}
    ),
    MasterCatalogKind.CUSTOMER: frozenset(
        {"sourceKey", "displayName", "enabled", "groupKey", "sourceModifiedAt"}
    ),
    MasterCatalogKind.SUPPLIER: frozenset(
        {"sourceKey", "displayName", "enabled", "groupKey", "sourceModifiedAt"}
    ),
    MasterCatalogKind.ITEM_GROUP: frozenset(
        {
            "sourceKey",
            "displayName",
            "enabled",
            "parentKey",
            "isGroup",
            "sourceModifiedAt",
        }
    ),
    MasterCatalogKind.ITEM: frozenset(
        {
            "sourceKey",
            "displayName",
            "enabled",
            "groupKey",
            "stockUom",
            "isStockItem",
            "sourceModifiedAt",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class MasterRecord:
    kind: MasterCatalogKind
    values: Mapping[str, object]

    @classmethod
    def from_mapping(
        cls, kind: MasterCatalogKind, value: object
    ) -> MasterRecord:
        if not isinstance(kind, MasterCatalogKind):
            raise MasterDataContractError("Master catalog kind is invalid.")
        if not isinstance(value, Mapping) or set(value) != _RECORD_FIELDS[kind]:
            raise MasterDataContractError("Master catalog record shape is invalid.")
        normalized: dict[str, object] = {
            "sourceKey": _text(value["sourceKey"], "sourceKey", 255),
            "displayName": _text(value["displayName"], "displayName", 255),
            "enabled": _boolean(value["enabled"], "enabled"),
            "sourceModifiedAt": _utc_text(
                value["sourceModifiedAt"], "sourceModifiedAt"
            ),
        }
        if kind in {MasterCatalogKind.CUSTOMER, MasterCatalogKind.SUPPLIER, MasterCatalogKind.MACHINE}:
            normalized["groupKey"] = _optional_text(
                value["groupKey"], "groupKey", 255
            )
        elif kind is MasterCatalogKind.ITEM_GROUP:
            normalized["parentKey"] = _optional_text(
                value["parentKey"], "parentKey", 255
            )
            normalized["isGroup"] = _boolean(value["isGroup"], "isGroup")
        else:
            normalized["groupKey"] = _text(value["groupKey"], "groupKey", 255)
            normalized["stockUom"] = _text(value["stockUom"], "stockUom", 140)
            normalized["isStockItem"] = _boolean(
                value["isStockItem"], "isStockItem"
            )
        return cls(kind, MappingProxyType(normalized))

    def mapping(self) -> dict[str, object]:
        return dict(self.values)

    @property
    def source_key(self) -> str:
        return str(self.values["sourceKey"])

    @property
    def source_hash(self) -> str:
        return canonical_hash(self.mapping())


@dataclass(frozen=True, slots=True)
class MasterSnapshotEvent:
    event_id: UUID
    kind: MasterCatalogKind
    source_environment: str
    source_version: int
    source_modified_at: str
    records: tuple[MasterRecord, ...]
    issued_at: str
    trace_id: str
    payload_hash: str

    @classmethod
    def from_mapping(cls, value: object) -> MasterSnapshotEvent:
        source = _closed(
            value,
            {
                "schemaVersion",
                "operation",
                "sourceSystem",
                "targetSystem",
                "eventId",
                "catalogKind",
                "sourceEnvironment",
                "sourceVersion",
                "sourceModifiedAt",
                "records",
                "issuedAt",
                "traceId",
                "payloadHash",
            },
        )
        if (
            source["schemaVersion"] != SCHEMA_VERSION
            or source["operation"] != OPERATION
            or source["sourceSystem"] != SOURCE_SYSTEM
            or source["targetSystem"] != TARGET_SYSTEM
        ):
            raise MasterDataContractError("Master snapshot ownership is invalid.")
        try:
            kind = MasterCatalogKind(source["catalogKind"])
            event_id = UUID(str(source["eventId"]))
        except (TypeError, ValueError) as error:
            raise MasterDataContractError("Master snapshot identity is invalid.") from error
        if str(event_id) != source["eventId"] or event_id.int == 0:
            raise MasterDataContractError("Master snapshot identity is invalid.")
        source_environment = source["sourceEnvironment"]
        if (
            not isinstance(source_environment, str)
            or source_environment not in _TEST_ENVIRONMENTS
        ):
            raise MasterDataContractError("Master snapshot environment is invalid.")
        source_version = _positive_int(source["sourceVersion"], "sourceVersion")
        source_modified_at = _utc_text(
            source["sourceModifiedAt"], "sourceModifiedAt"
        )
        issued_at = _utc_text(source["issuedAt"], "issuedAt")
        trace_id = source["traceId"]
        if not isinstance(trace_id, str) or _TRACE.fullmatch(trace_id) is None:
            raise MasterDataContractError("Master snapshot trace identity is invalid.")
        raw_records = source["records"]
        if (
            not isinstance(raw_records, Sequence)
            or isinstance(raw_records, (str, bytes, bytearray))
            or len(raw_records) > MAX_RECORDS
        ):
            raise MasterDataContractError("Master snapshot record count is invalid.")
        records = tuple(MasterRecord.from_mapping(kind, item) for item in raw_records)
        keys = tuple(record.source_key for record in records)
        if keys != tuple(sorted(set(keys))):
            raise MasterDataContractError(
                "Master snapshot records must be unique and sorted."
            )
        payload_hash = source["payloadHash"]
        if not isinstance(payload_hash, str) or _HASH.fullmatch(payload_hash) is None:
            raise MasterDataContractError("Master snapshot payload hash is invalid.")
        result = cls(
            event_id,
            kind,
            source_environment,
            source_version,
            source_modified_at,
            records,
            issued_at,
            trace_id,
            payload_hash,
        )
        if payload_hash != canonical_hash(result.payload_mapping()):
            raise MasterDataContractError("Master snapshot payload hash does not match.")
        return result

    def payload_mapping(self) -> dict[str, object]:
        return {
            "catalogKind": self.kind.value,
            "sourceEnvironment": self.source_environment,
            "sourceVersion": self.source_version,
            "sourceModifiedAt": self.source_modified_at,
            "records": [record.mapping() for record in self.records],
        }

    def mapping(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "operation": OPERATION,
            "sourceSystem": SOURCE_SYSTEM,
            "targetSystem": TARGET_SYSTEM,
            "eventId": str(self.event_id),
            **self.payload_mapping(),
            "issuedAt": self.issued_at,
            "traceId": self.trace_id,
            "payloadHash": self.payload_hash,
        }

    @property
    def event_hash(self) -> str:
        return canonical_hash(self.mapping())

    def head_id(self, tenant_id: str) -> UUID:
        return uuid5(HEAD_NAMESPACE, f"{_tenant(tenant_id)}:{self.kind.value}")

    def snapshot_id(self, tenant_id: str) -> UUID:
        return uuid5(SNAPSHOT_NAMESPACE, f"{_tenant(tenant_id)}:{self.event_id}")

    def entry_id(self, tenant_id: str, source_key: str) -> UUID:
        return uuid5(
            ENTRY_NAMESPACE,
            f"{_tenant(tenant_id)}:{self.kind.value}:{_text(source_key, 'sourceKey', 255)}",
        )


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
        raise MasterDataContractError("Master data JSON is invalid.") from error


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_text(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise MasterDataContractError("Master data time must be timezone aware.")
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _closed(value: object, keys: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise MasterDataContractError("Master snapshot shape is invalid.")
    return value


def _text(value: object, field: str, limit: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > limit
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise MasterDataContractError(f"{field} is invalid.")
    return value


def _optional_text(value: object, field: str, limit: int) -> str | None:
    return None if value is None else _text(value, field, limit)


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise MasterDataContractError(f"{field} is invalid.")
    return value


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        raise MasterDataContractError(f"{field} is invalid.")
    return value


def _utc_text(value: object, field: str) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise MasterDataContractError(f"{field} is invalid.")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise MasterDataContractError(f"{field} is invalid.") from error
    if utc_text(parsed) != value:
        raise MasterDataContractError(f"{field} is invalid.")
    return value


def _tenant(value: object) -> str:
    return _text(value, "tenantId", 128)
