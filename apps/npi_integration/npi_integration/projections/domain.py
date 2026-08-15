from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID


PROJECTION_SCHEMA_VERSION = 1
PROJECTION_ADAPTER_CONTRACT_VERSION = "npi.erp-projection.v1"
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_DECIMAL_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


class ProjectionContractError(ValueError):
    """Raised when target-owned projection input is not exactly contract-shaped."""


class ProjectionKind(StrEnum):
    CUSTOMER_MASTER = "customer_master"
    SUPPLIER_MASTER = "supplier_master"
    FORMAL_ITEM_MASTER = "formal_item_master"
    TOOLING_PROCUREMENT_COST = "tooling_procurement_cost"
    PROJECT_COST = "project_cost"
    FORMAL_QUALITY_STATUS = "formal_quality_status"
    TOOL_ASSET_STATUS = "tool_asset_status"


class ProjectionScopeKind(StrEnum):
    PROJECT = "project"
    TOOLING_MASTER = "tooling_master"
    TOOLING_SET = "tooling_set"
    ENGINEERING_ITEM = "engineering_item"
    TRIAL_ROUND = "trial_round"
    READINESS = "readiness"


class AdapterMode(StrEnum):
    MOCK = "mock"
    SANDBOX = "sandbox"
    SYNTHETIC = "synthetic"


class ProjectionAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    SYNTHETIC = "synthetic"


class ProjectionFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ApplicationDisposition(StrEnum):
    APPLIED_CURRENT = "applied_current"
    UNAVAILABLE_CURRENT = "unavailable_current"
    SUPERSEDED = "superseded"
    DUPLICATE_EXACT = "duplicate_exact"
    CONFLICTED = "conflicted"
    SYNTHETIC_RETAINED = "synthetic_retained"


class ProjectionSensitivity(StrEnum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


@dataclass(frozen=True, slots=True)
class ProjectionDefinition:
    kind: ProjectionKind
    event_type: str
    source_object_type: str
    scopes: frozenset[ProjectionScopeKind]
    normalize_values: Callable[[Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ProjectionContext:
    tenant_id: str
    project_global_id: UUID
    scope_kind: ProjectionScopeKind
    scope_global_id: UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _tenant(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "projectGlobalId"),
        )
        if not isinstance(self.scope_kind, ProjectionScopeKind):
            raise ProjectionContractError("scopeKind is unsupported.")
        object.__setattr__(
            self,
            "scope_global_id",
            _uuid(self.scope_global_id, "scopeGlobalId"),
        )
        if (
            self.scope_kind is ProjectionScopeKind.PROJECT
            and self.scope_global_id != self.project_global_id
        ):
            raise ProjectionContractError("Project scope must use the exact Project ID.")


@dataclass(frozen=True, slots=True)
class ProjectionRefreshTarget:
    context: ProjectionContext
    kind: ProjectionKind
    source_object_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.context, ProjectionContext):
            raise ProjectionContractError("Projection refresh context is invalid.")
        if not isinstance(self.kind, ProjectionKind):
            raise ProjectionContractError("projectionKind is unsupported.")
        if self.context.scope_kind not in PROJECTION_DEFINITIONS[self.kind].scopes:
            raise ProjectionContractError(
                "Projection kind does not support the selected server-owned scope."
            )
        object.__setattr__(
            self,
            "source_object_id",
            _text(self.source_object_id, "sourceObjectId", 255),
        )

    @property
    def source_object_type(self) -> str:
        return PROJECTION_DEFINITIONS[self.kind].source_object_type


@dataclass(frozen=True, slots=True)
class ProjectionReaderResult:
    kind: ProjectionKind
    adapter_mode: AdapterMode
    source_environment: str
    source_object_id: str
    source_version: str | None
    source_modified_at: datetime | None
    availability: ProjectionAvailability
    values: Mapping[str, Any] | None
    unavailable_reason_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProjectionKind):
            raise ProjectionContractError("projectionKind is unsupported.")
        if not isinstance(self.adapter_mode, AdapterMode):
            raise ProjectionContractError("adapterMode is unsupported.")
        if not isinstance(self.availability, ProjectionAvailability):
            raise ProjectionContractError("availability is unsupported.")
        object.__setattr__(
            self,
            "source_environment",
            _code(self.source_environment, "sourceEnvironment"),
        )
        object.__setattr__(
            self,
            "source_object_id",
            _text(self.source_object_id, "sourceObjectId", 255),
        )
        if self.availability is ProjectionAvailability.UNAVAILABLE:
            if self.values is not None:
                raise ProjectionContractError(
                    "An unavailable projection cannot contain target values."
                )
            object.__setattr__(
                self,
                "unavailable_reason_code",
                _code(self.unavailable_reason_code, "unavailableReasonCode"),
            )
            if self.adapter_mode is AdapterMode.SYNTHETIC:
                raise ProjectionContractError(
                    "Synthetic proof must remain visibly synthetic."
                )
            if self.source_version is not None:
                object.__setattr__(
                    self,
                    "source_version",
                    _text(self.source_version, "sourceVersion", 255),
                )
            object.__setattr__(
                self,
                "source_modified_at",
                _optional_datetime(self.source_modified_at, "sourceModifiedAt"),
            )
            return

        expected_mode = (
            AdapterMode.SANDBOX
            if self.availability is ProjectionAvailability.AVAILABLE
            else AdapterMode.SYNTHETIC
        )
        if self.adapter_mode is not expected_mode:
            raise ProjectionContractError(
                "Only confirmed sandbox input can be available; synthetic input stays synthetic."
            )
        if self.unavailable_reason_code is not None:
            raise ProjectionContractError(
                "Available or synthetic projection input cannot contain an unavailable reason."
            )
        object.__setattr__(
            self,
            "source_version",
            _text(self.source_version, "sourceVersion", 255),
        )
        object.__setattr__(
            self,
            "source_modified_at",
            _datetime(self.source_modified_at, "sourceModifiedAt"),
        )
        if not isinstance(self.values, Mapping):
            raise ProjectionContractError("Projection values must be an object.")
        normalized = PROJECTION_DEFINITIONS[self.kind].normalize_values(self.values)
        object.__setattr__(self, "values", MappingProxyType(normalized))

    @property
    def source_object_type(self) -> str:
        return PROJECTION_DEFINITIONS[self.kind].source_object_type

    def event_payload(
        self,
        *,
        context: ProjectionContext,
        received_at: datetime,
    ) -> dict[str, Any]:
        if context.scope_kind not in PROJECTION_DEFINITIONS[self.kind].scopes:
            raise ProjectionContractError(
                "Projection kind does not support the selected server-owned scope."
            )
        return {
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "adapter_contract_version": PROJECTION_ADAPTER_CONTRACT_VERSION,
            "projection_kind": self.kind.value,
            "tenant_id": context.tenant_id,
            "project_global_id": str(context.project_global_id),
            "scope_kind": context.scope_kind.value,
            "scope_global_id": str(context.scope_global_id),
            "adapter_mode": self.adapter_mode.value,
            "source_environment": self.source_environment,
            "source_object_id": self.source_object_id,
            "source_version": self.source_version,
            "source_modified_at": (
                _utc_text(self.source_modified_at)
                if self.source_modified_at is not None
                else None
            ),
            "received_at": _utc_text(_datetime(received_at, "receivedAt")),
            "availability": self.availability.value,
            "unavailable_reason_code": self.unavailable_reason_code,
            "values": dict(self.values) if self.values is not None else None,
        }


@dataclass(frozen=True, slots=True)
class ProjectionApplyOutcome:
    observation_global_id: UUID
    disposition: ApplicationDisposition
    head_optimistic_version: int
    replayed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_global_id",
            _uuid(self.observation_global_id, "observationGlobalId"),
        )
        if not isinstance(self.disposition, ApplicationDisposition):
            raise ProjectionContractError("Projection disposition is unsupported.")
        if type(self.head_optimistic_version) is not int or self.head_optimistic_version < 1:
            raise ProjectionContractError(
                "Projection head version must be a positive whole number."
            )
        if type(self.replayed) is not bool:
            raise ProjectionContractError("Projection replay state must be boolean.")


@dataclass(frozen=True, slots=True)
class CurrentProjectionIdentity:
    event_id: UUID
    source_object_id: str
    source_version: str
    source_modified_at: datetime
    payload_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _uuid(self.event_id, "eventId"))
        object.__setattr__(
            self,
            "source_object_id",
            _text(self.source_object_id, "sourceObjectId", 255),
        )
        object.__setattr__(
            self,
            "source_version",
            _text(self.source_version, "sourceVersion", 255),
        )
        object.__setattr__(
            self,
            "source_modified_at",
            _datetime(self.source_modified_at, "sourceModifiedAt"),
        )
        object.__setattr__(
            self,
            "payload_hash",
            _hash(self.payload_hash, "payloadHash"),
        )


def classify_observation(
    current: CurrentProjectionIdentity | None,
    *,
    event_id: UUID,
    result: ProjectionReaderResult,
    payload_hash: str,
) -> ApplicationDisposition:
    """Classify one observation without comparing opaque source versions."""

    candidate_event_id = _uuid(event_id, "eventId")
    candidate_hash = _hash(payload_hash, "payloadHash")
    if current is not None and candidate_event_id == current.event_id:
        return (
            ApplicationDisposition.DUPLICATE_EXACT
            if candidate_hash == current.payload_hash
            else ApplicationDisposition.CONFLICTED
        )
    if result.availability is ProjectionAvailability.SYNTHETIC:
        return ApplicationDisposition.SYNTHETIC_RETAINED
    if result.availability is ProjectionAvailability.UNAVAILABLE:
        return ApplicationDisposition.UNAVAILABLE_CURRENT
    if result.source_modified_at is None or result.source_version is None:
        raise ProjectionContractError(
            "An available observation requires source ordering truth."
        )
    if current is None:
        return ApplicationDisposition.APPLIED_CURRENT
    if result.source_object_id != current.source_object_id:
        raise ProjectionContractError(
            "Observation ordering requires one exact source-object stream."
        )
    if result.source_modified_at > current.source_modified_at:
        return ApplicationDisposition.APPLIED_CURRENT
    if result.source_modified_at < current.source_modified_at:
        return ApplicationDisposition.SUPERSEDED
    if (
        result.source_version == current.source_version
        and candidate_hash == current.payload_hash
    ):
        return ApplicationDisposition.DUPLICATE_EXACT
    return ApplicationDisposition.CONFLICTED


def projection_freshness(
    *,
    observed_at: datetime,
    now: datetime,
    maximum_age_seconds: int | None,
) -> ProjectionFreshness:
    observed = _datetime(observed_at, "observedAt")
    clock = _datetime(now, "now")
    if clock < observed:
        raise ProjectionContractError("Freshness clock cannot precede observation time.")
    if maximum_age_seconds is None:
        return ProjectionFreshness.UNKNOWN
    if type(maximum_age_seconds) is not int or maximum_age_seconds < 1:
        raise ProjectionContractError("Freshness maximum age must be positive.")
    age = (clock - observed).total_seconds()
    return (
        ProjectionFreshness.FRESH
        if age <= maximum_age_seconds
        else ProjectionFreshness.STALE
    )


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise ProjectionContractError("Canonical payload must be an object.")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _master_values(value: Mapping[str, Any]) -> dict[str, Any]:
    record = _closed(value, {"code", "displayName", "enabled", "statusCode"}, "values")
    return {
        "code": _code(record["code"], "values.code"),
        "displayName": _text(record["displayName"], "values.displayName", 200),
        "enabled": _boolean(record["enabled"], "values.enabled"),
        "statusCode": _optional_code(record["statusCode"], "values.statusCode"),
    }


def _item_values(value: Mapping[str, Any]) -> dict[str, Any]:
    record = _closed(
        value,
        {"itemCode", "stockUom", "enabled", "statusCode"},
        "values",
    )
    return {
        "itemCode": _code(record["itemCode"], "values.itemCode"),
        "stockUom": _code(record["stockUom"], "values.stockUom"),
        "enabled": _boolean(record["enabled"], "values.enabled"),
        "statusCode": _optional_code(record["statusCode"], "values.statusCode"),
    }


def _tooling_cost_values(value: Mapping[str, Any]) -> dict[str, Any]:
    record = _closed(value, {"toolingMasterGlobalId", "supplier", "rows"}, "values")
    supplier = _closed(
        _mapping(record["supplier"], "values.supplier"),
        {"sourceObjectId", "targetVersion", "supplierCode", "supplierName"},
        "values.supplier",
    )
    rows = _sequence(record["rows"], "values.rows", minimum=1, maximum=1000)
    normalized_rows = [
        _cost_row(_mapping(row, f"values.rows[{index}]"), index)
        for index, row in enumerate(rows)
    ]
    identities = {(row["sourceRowId"], row["sourceRowVersion"]) for row in normalized_rows}
    if len(identities) != len(normalized_rows):
        raise ProjectionContractError("Tooling cost source-row versions must be unique.")
    tooling_master_id = str(_uuid(record["toolingMasterGlobalId"], "values.toolingMasterGlobalId"))
    supplier_id = _text(supplier["sourceObjectId"], "values.supplier.sourceObjectId", 128)
    for row in normalized_rows:
        if (
            row["toolingMasterGlobalId"] != tooling_master_id
            or row["supplierSourceObjectId"] != supplier_id
        ):
            raise ProjectionContractError(
                "Tooling cost rows must match the exact Tooling Master and Supplier."
            )
    return {
        "toolingMasterGlobalId": tooling_master_id,
        "supplier": {
            "sourceObjectId": supplier_id,
            "targetVersion": _text(supplier["targetVersion"], "values.supplier.targetVersion", 128),
            "supplierCode": _code(supplier["supplierCode"], "values.supplier.supplierCode"),
            "supplierName": _text(supplier["supplierName"], "values.supplier.supplierName", 200),
        },
        "rows": normalized_rows,
    }


def _cost_row(value: Mapping[str, Any], index: int) -> dict[str, Any]:
    path = f"values.rows[{index}]"
    record = _closed(
        value,
        {
            "toolingMasterGlobalId",
            "sourceRowId",
            "sourceRowVersion",
            "supplierSourceObjectId",
            "purchaseOrderSourceId",
            "purchaseReceiptSourceId",
            "purchaseInvoiceSourceId",
            "actualCostSourceId",
            "costTypeCode",
            "postingDate",
            "currency",
            "amount",
        },
        path,
    )
    return {
        "toolingMasterGlobalId": str(_uuid(record["toolingMasterGlobalId"], f"{path}.toolingMasterGlobalId")),
        "sourceRowId": _text(record["sourceRowId"], f"{path}.sourceRowId", 128),
        "sourceRowVersion": _text(record["sourceRowVersion"], f"{path}.sourceRowVersion", 128),
        "supplierSourceObjectId": _text(record["supplierSourceObjectId"], f"{path}.supplierSourceObjectId", 128),
        "purchaseOrderSourceId": _text(record["purchaseOrderSourceId"], f"{path}.purchaseOrderSourceId", 128),
        "purchaseReceiptSourceId": _text(record["purchaseReceiptSourceId"], f"{path}.purchaseReceiptSourceId", 128),
        "purchaseInvoiceSourceId": _text(record["purchaseInvoiceSourceId"], f"{path}.purchaseInvoiceSourceId", 128),
        "actualCostSourceId": _text(record["actualCostSourceId"], f"{path}.actualCostSourceId", 128),
        "costTypeCode": _code(record["costTypeCode"], f"{path}.costTypeCode"),
        "postingDate": _date_text(record["postingDate"], f"{path}.postingDate"),
        "currency": _currency(record["currency"], f"{path}.currency"),
        "amount": _decimal(record["amount"], f"{path}.amount"),
    }


def _project_cost_values(value: Mapping[str, Any]) -> dict[str, Any]:
    record = _closed(value, {"rows"}, "values")
    rows = _sequence(record["rows"], "values.rows", minimum=1, maximum=1000)
    normalized = []
    for index, item in enumerate(rows):
        path = f"values.rows[{index}]"
        row = _closed(
            _mapping(item, path),
            {
                "rowKind",
                "sourceRowId",
                "sourceRowVersion",
                "postingDate",
                "currency",
                "amount",
                "hours",
            },
            path,
        )
        kind = _one_of(
            row["rowKind"],
            f"{path}.rowKind",
            {"commitment", "actual_cost", "labor_hours", "expense"},
        )
        currency = None
        amount = None
        hours = None
        if kind == "labor_hours":
            if row["currency"] is not None or row["amount"] is not None:
                raise ProjectionContractError("Labor-hour rows cannot claim monetary values.")
            hours = _decimal(row["hours"], f"{path}.hours", nonnegative=True)
        else:
            if row["hours"] is not None:
                raise ProjectionContractError("Monetary rows cannot claim labor hours.")
            currency = _currency(row["currency"], f"{path}.currency")
            amount = _decimal(row["amount"], f"{path}.amount")
        normalized.append(
            {
                "rowKind": kind,
                "sourceRowId": _text(row["sourceRowId"], f"{path}.sourceRowId", 128),
                "sourceRowVersion": _text(row["sourceRowVersion"], f"{path}.sourceRowVersion", 128),
                "postingDate": _date_text(row["postingDate"], f"{path}.postingDate"),
                "currency": currency,
                "amount": amount,
                "hours": hours,
            }
        )
    identities = {(row["sourceRowId"], row["sourceRowVersion"]) for row in normalized}
    if len(identities) != len(normalized):
        raise ProjectionContractError("Project cost source-row versions must be unique.")
    return {"rows": normalized}


def _quality_values(value: Mapping[str, Any]) -> dict[str, Any]:
    record = _closed(
        value,
        {"recordKind", "statusCode", "resultCode", "observedAt"},
        "values",
    )
    return {
        "recordKind": _one_of(
            record["recordKind"],
            "values.recordKind",
            {"quality_inspection", "ncr", "capa"},
        ),
        "statusCode": _code(record["statusCode"], "values.statusCode"),
        "resultCode": _optional_code(record["resultCode"], "values.resultCode"),
        "observedAt": _utc_text(_datetime(record["observedAt"], "values.observedAt")),
    }


def _asset_values(value: Mapping[str, Any]) -> dict[str, Any]:
    record = _closed(
        value,
        {
            "toolingSetGlobalId",
            "mappingVersion",
            "formalAssetId",
            "targetVersion",
            "assetState",
            "currentLocation",
            "shotCount",
            "expectedLifeShots",
            "maintenanceDue",
            "movements",
            "repairs",
            "spares",
        },
        "values",
    )
    movements = _normalize_records(
        record["movements"],
        "values.movements",
        200,
        {
            "globalId": ("uuid", None),
            "actionKind": ("code", None),
            "fromLocation": ("optional_text", 255),
            "toLocation": ("optional_text", 255),
            "occurredAt": ("datetime", None),
            "sourceObjectId": ("text", 128),
        },
    )
    if any(
        item["actionKind"] not in {"move", "loan", "return", "archive", "scrap"}
        for item in movements
    ):
        raise ProjectionContractError("Asset movement actionKind is unsupported.")
    repairs = _normalize_records(
        record["repairs"],
        "values.repairs",
        200,
        {
            "globalId": ("uuid", None),
            "summary": ("text", 2000),
            "downtimeHours": ("decimal_nonnegative", None),
            "completedAt": ("datetime", None),
            "sourceObjectId": ("text", 128),
        },
    )
    spares = _normalize_records(
        record["spares"],
        "values.spares",
        500,
        {
            "formalItemId": ("text", 128),
            "description": ("text", 1000),
            "stockOnHand": ("decimal_nonnegative", None),
            "minimumStock": ("decimal_nonnegative", None),
            "unit": ("code", 32),
            "supplierId": ("optional_text", 128),
        },
    )
    for path, rows in (("movements", movements), ("repairs", repairs)):
        identities = [row["globalId"] for row in rows]
        if len(identities) != len(set(identities)):
            raise ProjectionContractError(f"Asset {path} identities must be unique.")
    expected_life = record["expectedLifeShots"]
    if expected_life is not None:
        expected_life = _positive_int(expected_life, "values.expectedLifeShots")
    maintenance_due = record["maintenanceDue"]
    if maintenance_due is not None:
        maintenance_due = _date_text(maintenance_due, "values.maintenanceDue")
    return {
        "toolingSetGlobalId": str(_uuid(record["toolingSetGlobalId"], "values.toolingSetGlobalId")),
        "mappingVersion": _positive_int(record["mappingVersion"], "values.mappingVersion"),
        "formalAssetId": _text(record["formalAssetId"], "values.formalAssetId", 128),
        "targetVersion": _text(record["targetVersion"], "values.targetVersion", 128),
        "assetState": _code(record["assetState"], "values.assetState"),
        "currentLocation": _text(record["currentLocation"], "values.currentLocation", 255),
        "shotCount": _nonnegative_int(record["shotCount"], "values.shotCount"),
        "expectedLifeShots": expected_life,
        "maintenanceDue": maintenance_due,
        "movements": movements,
        "repairs": repairs,
        "spares": spares,
    }


def _normalize_records(
    value: object,
    path: str,
    maximum: int,
    fields: Mapping[str, tuple[str, int | None]],
) -> list[dict[str, Any]]:
    rows = _sequence(value, path, minimum=0, maximum=maximum)
    normalized = []
    for index, item in enumerate(rows):
        item_path = f"{path}[{index}]"
        record = _closed(_mapping(item, item_path), set(fields), item_path)
        output: dict[str, Any] = {}
        for name, (kind, size) in fields.items():
            field_path = f"{item_path}.{name}"
            candidate = record[name]
            if kind == "uuid":
                output[name] = str(_uuid(candidate, field_path))
            elif kind == "code":
                output[name] = _code(candidate, field_path, int(size or 128))
            elif kind == "text":
                output[name] = _text(candidate, field_path, int(size or 255))
            elif kind == "optional_text":
                output[name] = (
                    None
                    if candidate is None
                    else _text(candidate, field_path, int(size or 255))
                )
            elif kind == "datetime":
                output[name] = _utc_text(_datetime(candidate, field_path))
            elif kind == "decimal_nonnegative":
                output[name] = _decimal(candidate, field_path, nonnegative=True)
            else:  # pragma: no cover - catalog construction guard
                raise AssertionError(f"Unsupported normalizer: {kind}")
        normalized.append(output)
    return normalized


PROJECTION_DEFINITIONS = MappingProxyType(
    {
        ProjectionKind.CUSTOMER_MASTER: ProjectionDefinition(
            ProjectionKind.CUSTOMER_MASTER,
            "erpnext.customer_master.observed",
            "Customer",
            frozenset({ProjectionScopeKind.PROJECT}),
            _master_values,
        ),
        ProjectionKind.SUPPLIER_MASTER: ProjectionDefinition(
            ProjectionKind.SUPPLIER_MASTER,
            "erpnext.supplier_master.observed",
            "Supplier",
            frozenset({ProjectionScopeKind.TOOLING_MASTER}),
            _master_values,
        ),
        ProjectionKind.FORMAL_ITEM_MASTER: ProjectionDefinition(
            ProjectionKind.FORMAL_ITEM_MASTER,
            "erpnext.formal_item_master.observed",
            "Item",
            frozenset({ProjectionScopeKind.ENGINEERING_ITEM}),
            _item_values,
        ),
        ProjectionKind.TOOLING_PROCUREMENT_COST: ProjectionDefinition(
            ProjectionKind.TOOLING_PROCUREMENT_COST,
            "erpnext.tooling_procurement_cost.observed",
            "ToolingProcurementCost",
            frozenset({ProjectionScopeKind.TOOLING_MASTER}),
            _tooling_cost_values,
        ),
        ProjectionKind.PROJECT_COST: ProjectionDefinition(
            ProjectionKind.PROJECT_COST,
            "erpnext.project_cost.observed",
            "ProjectCost",
            frozenset({ProjectionScopeKind.PROJECT}),
            _project_cost_values,
        ),
        ProjectionKind.FORMAL_QUALITY_STATUS: ProjectionDefinition(
            ProjectionKind.FORMAL_QUALITY_STATUS,
            "erpnext.formal_quality_status.observed",
            "FormalQualityStatus",
            frozenset(
                {
                    ProjectionScopeKind.PROJECT,
                    ProjectionScopeKind.TRIAL_ROUND,
                    ProjectionScopeKind.READINESS,
                }
            ),
            _quality_values,
        ),
        ProjectionKind.TOOL_ASSET_STATUS: ProjectionDefinition(
            ProjectionKind.TOOL_ASSET_STATUS,
            "erpnext.tool_asset_status.observed",
            "Asset",
            frozenset({ProjectionScopeKind.TOOLING_SET}),
            _asset_values,
        ),
    }
)


def _closed(value: Mapping[str, Any], fields: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ProjectionContractError(f"{path} must contain exactly {sorted(fields)}.")
    return value


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProjectionContractError(f"{path} must be an object.")
    return value


def _sequence(value: object, path: str, *, minimum: int, maximum: int) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ProjectionContractError(f"{path} must be an array.")
    if not minimum <= len(value) <= maximum:
        raise ProjectionContractError(f"{path} size is outside the supported boundary.")
    return value


def _uuid(value: object, path: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ProjectionContractError(f"{path} must be a valid UUID.") from error


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectionContractError(f"{path} is required.")
    normalized = value.strip()
    if len(normalized) > maximum or any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise ProjectionContractError(f"{path} is invalid.")
    return normalized


def _code(value: object, path: str, maximum: int = 128) -> str:
    normalized = _text(value, path, maximum)
    if _CODE_PATTERN.fullmatch(normalized) is None:
        raise ProjectionContractError(f"{path} must be a controlled code.")
    return normalized


def _tenant(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if _TENANT_PATTERN.fullmatch(normalized) is None:
        raise ProjectionContractError(f"{path} must be a controlled tenant ID.")
    return normalized


def _optional_code(value: object, path: str) -> str | None:
    return None if value is None else _code(value, path)


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise ProjectionContractError(f"{path} must be a boolean.")
    return value


def _positive_int(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise ProjectionContractError(f"{path} must be a positive whole number.")
    return value


def _nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ProjectionContractError(f"{path} cannot be negative.")
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise ProjectionContractError(f"{path} must be a lowercase SHA-256 value.")
    return value


def _datetime(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ProjectionContractError(f"{path} must be a valid date-time.") from error
    else:
        raise ProjectionContractError(f"{path} must be a valid date-time.")
    if parsed.tzinfo is None:
        raise ProjectionContractError(f"{path} must include a timezone.")
    return parsed.astimezone(UTC)


def _optional_datetime(value: object, path: str) -> datetime | None:
    return None if value is None else _datetime(value, path)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _date_text(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise ProjectionContractError(f"{path} must be a date.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ProjectionContractError(f"{path} must be a date.") from error


def _currency(value: object, path: str) -> str:
    if not isinstance(value, str) or _CURRENCY_PATTERN.fullmatch(value) is None:
        raise ProjectionContractError(f"{path} must be a three-letter currency code.")
    return value


def _decimal(value: object, path: str, *, nonnegative: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 32 or _DECIMAL_PATTERN.fullmatch(value) is None:
        raise ProjectionContractError(f"{path} must be a canonical decimal string.")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ProjectionContractError(f"{path} must be a canonical decimal string.") from error
    if not parsed.is_finite() or (nonnegative and parsed < 0):
        raise ProjectionContractError(f"{path} is outside the supported range.")
    return value


def _one_of(value: object, path: str, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ProjectionContractError(f"{path} is unsupported.")
    return value
