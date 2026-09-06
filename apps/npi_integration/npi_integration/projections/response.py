from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from .domain import (
    PROJECTION_DEFINITIONS,
    ApplicationDisposition,
    ProjectionAvailability,
    ProjectionFreshness,
    ProjectionKind,
    ProjectionScopeKind,
)


MAX_PROJECT_PROJECTION_ITEMS = 200
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_ITEM_FIELDS = {
    "observationGlobalId",
    "projectionKind",
    "scopeKind",
    "scopeGlobalId",
    "availability",
    "freshness",
    "disposition",
    "sourceSystem",
    "sourceObjectType",
    "sourceObjectId",
    "sourceVersion",
    "sourceModifiedAt",
    "receivedAt",
    "payloadHash",
    "unavailableReasonCode",
    "values",
    "currentTruth",
    "editable",
}
_CURRENT_FIELDS = {
    "observationGlobalId",
    "headGlobalId",
    "headOptimisticVersion",
    "headHash",
    "sourceVersion",
    "sourceModifiedAt",
    "receivedAt",
    "payloadHash",
    "values",
}


def validate_project_projection_collection(
    value: object,
    *,
    expected_project_global_id: UUID,
) -> dict[str, Any]:
    """Close and normalize the public read model before Frappe serializes it."""

    project_id = _uuid(expected_project_global_id, "expectedProjectGlobalId")
    record = _closed(
        value,
        {"projectGlobalId", "accessState", "reasonCode", "permissions", "items"},
        "collection",
    )
    if _uuid(record["projectGlobalId"], "projectGlobalId") != project_id:
        raise ValueError("ERP projection response escaped its authorized Project.")
    access_state = record["accessState"]
    if access_state not in {"available", "redacted"}:
        raise ValueError("ERP projection access state is invalid.")
    permissions = _closed(
        record["permissions"], {"view", "edit", "refresh"}, "permissions"
    )
    if any(type(permissions[name]) is not bool for name in permissions):
        raise ValueError("ERP projection permissions are invalid.")
    items = _sequence(record["items"], "items", MAX_PROJECT_PROJECTION_ITEMS)
    if access_state == "redacted":
        if (
            record["reasonCode"] != "projection_access_redacted"
            or dict(permissions) != {"view": False, "edit": False, "refresh": False}
            or items
        ):
            raise ValueError("Redacted ERP projection response is invalid.")
    elif (
        record["reasonCode"] is not None
        or dict(permissions) != {"view": True, "edit": False, "refresh": False}
    ):
        raise ValueError("Available ERP projection response is invalid.")
    normalized_items = [
        _projection_item(item, project_global_id=project_id) for item in items
    ]
    identities = [
        (
            item["projectionKind"],
            item["scopeKind"],
            item["scopeGlobalId"],
            item["sourceObjectId"],
            item["observationGlobalId"],
        )
        for item in normalized_items
    ]
    if identities != sorted(identities) or len(identities) != len(set(identities)):
        raise ValueError("ERP projection response ordering is invalid.")
    return {
        "projectGlobalId": str(project_id),
        "accessState": access_state,
        "reasonCode": record["reasonCode"],
        "permissions": dict(permissions),
        "items": normalized_items,
    }


def _projection_item(
    value: object,
    *,
    project_global_id: UUID,
) -> dict[str, Any]:
    item = _closed(value, _ITEM_FIELDS, "item")
    kind = _enum(ProjectionKind, item["projectionKind"], "projectionKind")
    scope_kind = _enum(ProjectionScopeKind, item["scopeKind"], "scopeKind")
    scope_id = _uuid(item["scopeGlobalId"], "scopeGlobalId")
    definition = PROJECTION_DEFINITIONS[kind]
    if scope_kind not in definition.scopes:
        raise ValueError("ERP projection response scope is invalid.")
    if scope_kind is ProjectionScopeKind.PROJECT and scope_id != project_global_id:
        raise ValueError("ERP projection response Project scope is invalid.")
    availability = _enum(
        ProjectionAvailability, item["availability"], "availability"
    )
    freshness = _enum(ProjectionFreshness, item["freshness"], "freshness")
    disposition = _enum(
        ApplicationDisposition, item["disposition"], "disposition"
    )
    if item["sourceSystem"] != "ERPNEXT" or item["sourceObjectType"] != definition.source_object_type:
        raise ValueError("ERP projection response source identity is invalid.")
    if item["editable"] is not False:
        raise ValueError("ERP projection response must remain read-only.")
    source_version = _optional_text(item["sourceVersion"], "sourceVersion", 255)
    source_modified_at = _optional_datetime(
        item["sourceModifiedAt"], "sourceModifiedAt"
    )
    reason_code = _optional_text(
        item["unavailableReasonCode"], "unavailableReasonCode", 128
    )
    normalized_values = _values(kind, item["values"], optional=True)
    current = (
        None
        if item["currentTruth"] is None
        else _current_truth(kind, item["currentTruth"])
    )
    if availability is ProjectionAvailability.AVAILABLE and current is None:
        raise ValueError("Available ERP projection response has no current truth.")
    return {
        "observationGlobalId": str(
            _uuid(item["observationGlobalId"], "observationGlobalId")
        ),
        "projectionKind": kind.value,
        "scopeKind": scope_kind.value,
        "scopeGlobalId": str(scope_id),
        "availability": availability.value,
        "freshness": freshness.value,
        "disposition": disposition.value,
        "sourceSystem": "ERPNEXT",
        "sourceObjectType": definition.source_object_type,
        "sourceObjectId": _text(item["sourceObjectId"], "sourceObjectId", 255),
        "sourceVersion": source_version,
        "sourceModifiedAt": source_modified_at,
        "receivedAt": _datetime(item["receivedAt"], "receivedAt"),
        "payloadHash": _hash(item["payloadHash"], "payloadHash"),
        "unavailableReasonCode": reason_code,
        "values": normalized_values,
        "currentTruth": current,
        "editable": False,
    }


def _current_truth(kind: ProjectionKind, value: object) -> dict[str, Any]:
    record = _closed(value, _CURRENT_FIELDS, "currentTruth")
    return {
        "observationGlobalId": str(
            _uuid(record["observationGlobalId"], "currentTruth.observationGlobalId")
        ),
        "headGlobalId": str(
            _uuid(record["headGlobalId"], "currentTruth.headGlobalId")
        ),
        "headOptimisticVersion": _positive_int(
            record["headOptimisticVersion"], "currentTruth.headOptimisticVersion"
        ),
        "headHash": _hash(record["headHash"], "currentTruth.headHash"),
        "sourceVersion": _text(
            record["sourceVersion"], "currentTruth.sourceVersion", 255
        ),
        "sourceModifiedAt": _datetime(
            record["sourceModifiedAt"], "currentTruth.sourceModifiedAt"
        ),
        "receivedAt": _datetime(
            record["receivedAt"], "currentTruth.receivedAt"
        ),
        "payloadHash": _hash(
            record["payloadHash"], "currentTruth.payloadHash"
        ),
        "values": _values(kind, record["values"], optional=False),
    }


def _values(
    kind: ProjectionKind,
    value: object,
    *,
    optional: bool,
) -> dict[str, Any] | None:
    if optional and value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("ERP projection response values are invalid.")
    return PROJECTION_DEFINITIONS[kind].normalize_values(value)


def _closed(value: object, fields: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"ERP projection {path} is not closed.")
    return value


def _sequence(value: object, path: str, maximum: int) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"ERP projection {path} is invalid.")
    if len(value) > maximum:
        raise ValueError(f"ERP projection {path} exceeds its safe bound.")
    return value


def _enum(enum_type: type[Any], value: object, path: str):
    if not isinstance(value, str):
        raise ValueError(f"ERP projection {path} is invalid.")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(f"ERP projection {path} is invalid.") from error


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, (str, UUID)):
        raise ValueError(f"ERP projection {path} is invalid.")
    try:
        parsed = value if isinstance(value, UUID) else UUID(value)
    except ValueError as error:
        raise ValueError(f"ERP projection {path} is invalid.") from error
    if isinstance(value, str) and str(parsed) != value.casefold():
        raise ValueError(f"ERP projection {path} is invalid.")
    return parsed


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"ERP projection {path} is invalid.")
    return value


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _positive_int(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"ERP projection {path} is invalid.")
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"ERP projection {path} is invalid.")
    return value


def _datetime(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"ERP projection {path} is invalid.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"ERP projection {path} is invalid.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"ERP projection {path} is invalid.")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _optional_datetime(value: object, path: str) -> str | None:
    return None if value is None else _datetime(value, path)
