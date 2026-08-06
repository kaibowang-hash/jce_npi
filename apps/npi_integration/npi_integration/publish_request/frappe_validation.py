from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.tracing import resolve_trace_id


PUBLISH_POLICY_WRITE_FLAG = "npi_ebom_publish_policy_write"
PUBLISH_REQUEST_WRITE_FLAG = "npi_ebom_publish_request_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


def require_publish_policy_write() -> None:
    if not getattr(frappe.flags, PUBLISH_POLICY_WRITE_FLAG, False):
        frappe.throw(
            _(
                "EBOM publish policies can only be changed through authorized administration."
            ),
            frappe.PermissionError,
        )


def require_publish_request_write() -> None:
    if not getattr(frappe.flags, PUBLISH_REQUEST_WRITE_FLAG, False):
        frappe.throw(
            _(
                "Formal Item and MBOM publish requests can only be changed through an authorized NPI command."
            ),
            frappe.PermissionError,
        )


@contextmanager
def publish_policy_write() -> Iterator[None]:
    with _flag_scope(PUBLISH_POLICY_WRITE_FLAG):
        yield


@contextmanager
def publish_request_write() -> Iterator[None]:
    with _flag_scope(PUBLISH_REQUEST_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        yield


def deny_publish_history_update() -> None:
    frappe.throw(
        _("Formal Item and MBOM publish-request history cannot be changed."),
        frappe.PermissionError,
    )


def deny_publish_history_delete(
    document: object | None = None,
    *,
    target_global_id: object | None = None,
    target_version: object = 1,
) -> None:
    if document is not None:
        _queue_delete_attempt(
            document,
            target_global_id=target_global_id,
            target_version=target_version,
        )
    frappe.throw(
        _("Formal Item and MBOM publish-request history cannot be deleted."),
        frappe.PermissionError,
    )


def validate_internal_requester_users(user_ids: tuple[str, ...]) -> None:
    for user_id in user_ids:
        row = frappe.db.get_value(
            "User",
            user_id,
            ["name", "enabled", "user_type"],
            as_dict=True,
        )
        try:
            enabled = int(_value(row, "enabled") or 0) if row else 0
        except (TypeError, ValueError):
            enabled = 0
        if (
            not row
            or str(_value(row, "name")).casefold() != user_id.casefold()
            or enabled != 1
            or str(_value(row, "user_type")) != "System User"
        ):
            frappe.throw(
                _("Publish-request policy users must be enabled internal system users."),
                frappe.ValidationError,
            )


@contextmanager
def _flag_scope(name: str) -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, name, missing)
    setattr(frappe.flags, name, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, name)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, name, previous)


def _queue_delete_attempt(
    document: object,
    *,
    target_global_id: object | None,
    target_version: object,
) -> None:
    doctype = str(_value(document, "doctype") or "").strip()
    global_id = (
        _audit_uuid(target_global_id)
        or _audit_uuid(_value(document, "global_id"))
        or _audit_uuid(_value(document, "name"))
    )
    try:
        object_version = 0 if isinstance(target_version, bool) else int(target_version)
    except (TypeError, ValueError):
        object_version = 0
    if not doctype or global_id is None or object_version < 1:
        return
    actor = str(getattr(getattr(frappe, "session", None), "user", None) or "Guest")
    trace_id = resolve_trace_id(_trace_header())
    event = create_audit_event(
        actor=actor,
        trace_id=trace_id,
        operation="ebom.publish_request.history.delete_attempt",
        global_id=global_id,
        object_version=object_version,
        result="denied",
        input_summary={"doctype": doctype},
    )
    values: dict[str, object] = {
        "doctype": "NPI Audit Event",
        "event_id": str(event.event_id),
        "global_id": str(event.global_id),
        "object_version": event.object_version,
        "actor": event.actor,
        "trace_id": event.trace_id,
        "operation": event.operation,
        "result": event.result,
        "input_summary": dict(event.input_summary),
    }

    def persist_after_rollback() -> None:
        with _flag_scope(AUDIT_APPEND_FLAG):
            try:
                frappe.get_doc(dict(values)).insert()
                frappe.db.commit()
            except Exception:
                frappe.db.rollback()
                raise

    frappe.db.after_rollback.add(persist_after_rollback)


def _trace_header() -> str | None:
    getter = getattr(frappe, "get_request_header", None)
    if not callable(getter):
        return None
    try:
        value = getter("X-Trace-ID")
    except (AttributeError, RuntimeError):
        return None
    return value if isinstance(value, str) else None


def _audit_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


def _value(source: object, name: str) -> object:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)
