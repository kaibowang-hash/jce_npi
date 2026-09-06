from __future__ import annotations

from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.request_security import (
    authenticated_user,
    reject_unexpected_request_fields,
    response_request_id,
)


_STATUS_FIELDS = frozenset({"receiptId"})
_TERMINAL_STATES = frozenset(
    {
        "succeeded",
        "failed_final",
        "quarantined",
        "superseded",
        "received_after_creation",
    }
)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_source_receipt(**request_fields: Any) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, object]:
        actor = authenticated_user()
        if "NPI API User" not in set(frappe.get_roles(actor) or ()):
            raise PermissionDenied()
        reject_unexpected_request_fields(_STATUS_FIELDS, request_fields)
        receipt_id = _receipt_id(request_fields.get("receiptId"))
        row = frappe.db.get_value(
            "NPI Inbox Message",
            str(receipt_id),
            [
                "receipt_id",
                "event_id",
                "state",
                "disposition",
                "project_global_id",
                "last_error_code",
                "trace_id",
            ],
            as_dict=True,
        )
        if not row:
            raise NpiProblem(
                404,
                "PROJECT_SOURCE_RECEIPT_NOT_FOUND",
                _("The Project source receipt was not found."),
            )
        state = str(row.get("state") or "")
        project_global_id = row.get("project_global_id") or None
        if state == "succeeded" and not project_global_id:
            raise RuntimeError("Project source receipt result is incomplete.")
        return {
            "receiptId": str(row.get("receipt_id") or receipt_id),
            "eventId": str(row.get("event_id") or ""),
            "state": state,
            "terminal": state in _TERMINAL_STATES,
            "disposition": str(row.get("disposition") or "pending"),
            "projectGlobalId": (
                str(project_global_id) if project_global_id is not None else None
            ),
            "errorCode": (
                str(row.get("last_error_code"))
                if row.get("last_error_code")
                else None
            ),
            "traceId": str(row.get("trace_id") or ""),
        }

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


def _receipt_id(value: object) -> UUID:
    try:
        receipt_id = UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        receipt_id = None
    if receipt_id is None or str(receipt_id) != value:
        raise RequestValidationFailed(
            [{"path": "receiptId", "message": _("Enter a valid receipt ID.")}]
        )
    return receipt_id
