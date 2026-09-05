from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import frappe

from npi_core.api import frappe_domain_call
from npi_core.request_security import (
    authenticated_user,
    reject_unexpected_request_fields,
    response_request_id,
)
from npi_integration.item_publish.connector_runtime import (
    configured_sandbox_environments,
)


_STATUS_FIELDS = frozenset()
_CONNECTION_FRESHNESS = timedelta(hours=2)
_TEST_ENVIRONMENTS = frozenset(
    {"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage"}
)


def _utc(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _latest_authorization_confirmation() -> datetime | None:
    rows = frappe.get_all(
        "NPI Authorization Projection",
        fields=["applied_at"],
        order_by="applied_at desc",
        page_length=1,
    )
    return _utc(rows[0].get("applied_at")) if rows else None


def _latest_master_data_confirmation() -> tuple[datetime | None, str | None]:
    rows = frappe.get_all(
        "NPI ERP Master Catalog Head",
        fields=["catalog_kind", "last_synchronized_at", "source_environment"],
        order_by="catalog_kind asc",
        page_length=5,
    )
    if not rows:
        return None, None
    environments = {row.get("source_environment") for row in rows}
    kinds = {row.get("catalog_kind") for row in rows}
    if len(environments) != 1 or not environments.issubset(_TEST_ENVIRONMENTS):
        raise RuntimeError("ERPNext master data environment is unsupported.")
    environment = str(next(iter(environments)))
    expected_kinds = {"customer", "supplier", "item_group", "item"}
    if len(rows) != len(expected_kinds) or kinds != expected_kinds:
        return None, environment
    confirmations = [_utc(row.get("last_synchronized_at")) for row in rows]
    if any(value is None for value in confirmations):
        return None, environment
    return min(value for value in confirmations if value is not None), environment


def _count(doctype: str, filters: dict[str, object] | None = None) -> int:
    value = frappe.db.count(doctype, filters=filters)
    if type(value) is not int or value < 0:
        raise RuntimeError("ERPNext connection status count is invalid.")
    return value


def _status(*, now: datetime) -> dict[str, object]:
    environments = configured_sandbox_environments(frappe.conf)
    if environments and environments[0] not in _TEST_ENVIRONMENTS:
        raise RuntimeError("ERPNext connection environment is unsupported.")
    master_confirmed_at, master_environment = _latest_master_data_confirmation()
    target_environment = "test" if environments or master_environment else None
    last_confirmed_at = _latest_authorization_confirmation()
    authorization_connected = bool(
        last_confirmed_at is not None
        and now - _CONNECTION_FRESHNESS <= last_confirmed_at <= now + timedelta(minutes=5)
    )
    item_configured = bool(environments)
    master_data_synchronized = bool(
        master_confirmed_at is not None
        and now - _CONNECTION_FRESHNESS
        <= master_confirmed_at
        <= now + timedelta(minutes=5)
    )
    project_synchronized = (
        _count(
            "NPI Project Source Binding",
            {"source_object_type": "Project", "stream_state": "bound"},
        )
        > 0
    )
    reporting_synchronized = master_data_synchronized or (
        _count("NPI ERP Projection Head", {"availability": "available"}) > 0
    )
    if authorization_connected:
        connection_state = "connected"
    elif item_configured:
        connection_state = "partially_connected"
    else:
        connection_state = "not_connected"
    return {
        "schemaVersion": 1,
        "targetSystem": "ERPNEXT",
        "targetEnvironment": target_environment,
        "connectionState": connection_state,
        "lastConfirmedAt": (
            last_confirmed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            if last_confirmed_at is not None
            else None
        ),
        "capabilities": {
            "authorizationSynchronization": authorization_connected,
            "itemCommands": item_configured,
            "projectSynchronization": project_synchronized,
            "masterDataSynchronization": master_data_synchronized,
            "reportingSynchronization": reporting_synchronized,
        },
    }


def _safe_status(*, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict[str, object]:
    try:
        return _status(now=clock().astimezone(UTC))
    except Exception:
        return {
            "schemaVersion": 1,
            "targetSystem": "ERPNEXT",
            "targetEnvironment": None,
            "connectionState": "unavailable",
            "lastConfirmedAt": None,
            "capabilities": {
                "authorizationSynchronization": False,
                "itemCommands": False,
                "projectSynchronization": False,
                "masterDataSynchronization": False,
                "reportingSynchronization": False,
            },
        }


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_erpnext_connection_status(**request_fields: Any) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, object]:
        authenticated_user()
        reject_unexpected_request_fields(_STATUS_FIELDS, request_fields)
        return _safe_status()

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )
