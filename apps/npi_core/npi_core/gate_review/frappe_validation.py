from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.tracing import resolve_trace_id


GATE_REVIEW_COMMAND_FLAG = "npi_gate_review_command_write"

_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def ensure_uuid(value: object, field_label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError):
        frappe.throw(
            _("{field} must be a valid UUID.").format(field=field_label),
            frappe.ValidationError,
        )
    raise AssertionError("Frappe validation must raise an exception.")


def controlled_key(value: object, field_label: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a valid controlled key.").format(field=field_label),
            frappe.ValidationError,
        )
    return value


def lowercase_sha256(value: object, field_label: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(field=field_label),
            frappe.ValidationError,
        )
    return value


def positive_integer(value: object, field_label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        frappe.throw(
            _("{field} must be greater than zero.").format(field=field_label),
            frappe.ValidationError,
        )
    return value


def required_text(
    value: object,
    field_label: str,
    *,
    maximum: int = 2000,
) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        frappe.throw(
            _("{field} must contain a valid value.").format(field=field_label),
            frappe.ValidationError,
        )
    return value.strip()


def canonical_json(
    value: object,
    field_label: str,
    *,
    expected_type: type[dict] | type[list],
) -> tuple[Any, str]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        if not isinstance(parsed, expected_type):
            raise ValueError
        encoded = json.dumps(
            parsed,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        frappe.throw(
            _("{field} must contain valid canonical JSON.").format(field=field_label),
            frappe.ValidationError,
        )
    return parsed, encoded


def canonical_json_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def canonical_datetime(value: object, field_label: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            frappe.throw(
                _("{field} must be a valid date and time.").format(field=field_label),
                frappe.ValidationError,
            )
    else:
        frappe.throw(
            _("{field} must be a valid date and time.").format(field=field_label),
            frappe.ValidationError,
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def assert_immutable_fields(
    document: object,
    previous: object,
    fields: Iterable[str],
) -> None:
    for fieldname in fields:
        if _value(document, fieldname) != _value(previous, fieldname):
            frappe.throw(
                _("A protected Gate review field cannot be changed."),
                frappe.ValidationError,
            )


def require_gate_review_command_write() -> None:
    """Deny generic Desk/resource writes to controlled Gate review history."""
    if not getattr(frappe.flags, GATE_REVIEW_COMMAND_FLAG, False):
        frappe.throw(
            _(
                "Gate review history can only be changed through an authorized NPI Gate command."
            ),
            frappe.PermissionError,
        )


def deny_gate_review_history_delete(
    document: object | None = None,
    *,
    target_global_id: object | None = None,
    target_version: object = 1,
) -> None:
    """Retain history and persist an audit only after the denied delete rolls back."""
    if document is not None:
        _queue_gate_review_history_delete_attempt(
            document,
            target_global_id=target_global_id,
            target_version=target_version,
        )
    frappe.throw(
        _("Controlled Gate review history cannot be deleted."),
        frappe.PermissionError,
    )


def _queue_gate_review_history_delete_attempt(
    document: object,
    *,
    target_global_id: object | None,
    target_version: object,
) -> None:
    doctype = str(_value(document, "doctype") or "").strip()
    global_id = _audit_target_uuid(target_global_id)
    if global_id is None:
        global_id = _audit_target_uuid(_value(document, "name"))
    try:
        object_version = 0 if isinstance(target_version, bool) else int(target_version)
    except (TypeError, ValueError):
        object_version = 0
    # A damaged or not-yet-normalized test/document must still be denied.
    # Real retained history has a UUID target and positive business version.
    if not doctype or global_id is None or object_version < 1:
        return

    actor = str(getattr(getattr(frappe, "session", None), "user", None) or "Guest")
    trace_id = resolve_trace_id(_request_trace_header())
    event = create_audit_event(
        actor=actor,
        trace_id=trace_id,
        operation="gate.review.history.delete_attempt",
        global_id=global_id,
        object_version=object_version,
        result="denied",
        input_summary={"doctype": doctype},
    )
    audit_values = {
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
        missing = object()
        previous = getattr(frappe.flags, "npi_audit_append", missing)
        frappe.flags.npi_audit_append = True
        try:
            frappe.get_doc(dict(audit_values)).insert()
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            raise
        finally:
            if previous is missing:
                try:
                    delattr(frappe.flags, "npi_audit_append")
                except AttributeError:
                    pass
            else:
                frappe.flags.npi_audit_append = previous

    # Pinned Frappe v15 runs full-rollback callbacks FIFO in a new transaction.
    # This is deliberately the final action before the PermissionError below:
    # earlier callbacks run first and this last callback can safely commit the audit.
    frappe.db.after_rollback.add(persist_after_rollback)


def _request_trace_header() -> str | None:
    request_header = getattr(frappe, "get_request_header", None)
    if not callable(request_header):
        return None
    try:
        candidate = request_header("X-Trace-ID")
    except (AttributeError, RuntimeError):
        # Console/background administration has no bound HTTP request. The
        # denied operation still needs a fresh trace and must remain denied.
        return None
    return candidate if isinstance(candidate, str) else None


def _audit_target_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


def _value(document: object, fieldname: str) -> object:
    getter = getattr(document, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(document, fieldname, None)
