from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import UTC, timedelta
from typing import Iterator

import frappe
from frappe import _
from frappe.utils import get_datetime

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
)
from npi_core.tooling.domain import sha256_json
from npi_core.tooling.export_domain import TOOLING_OBJECT_PACKAGE_VALIDITY


TOOLING_EXPORT_WRITE_FLAG = "npi_tooling_export_write"
AUDIT_APPEND_FLAG = "npi_audit_append"
PACKAGE_CREATE_DIAGNOSTIC_FLAG = "npi_tooling_package_create_diagnostic"
PACKAGE_CREATE_DIAGNOSTIC_HEADER = "p608-package-create-v1"
PACKAGE_CREATE_DIAGNOSTIC_CODES = frozenset(
    {
        "P608_PACKAGE_COMMAND_CONTEXT",
        "P608_PACKAGE_ROWS",
        "P608_PACKAGE_SELECTION",
        "P608_PACKAGE_IDENTITY",
        "P608_PACKAGE_RENDER",
        "P608_PACKAGE_RECEIPT_INSERT",
        "P608_PACKAGE_FILE_SAVE",
        "P608_PACKAGE_ORPHAN_CLEANUP",
        "P608_PACKAGE_INSERT",
        "P608_PACKAGE_RESPONSE_BUILD",
        "P608_PACKAGE_AUDIT_APPEND",
        "P608_PACKAGE_RECEIPT_SEAL",
        "P608_PACKAGE_TRANSACTION_LIFECYCLE",
        "P608_PACKAGE_WRITE_GUARD",
        "P608_PACKAGE_NORMALIZE_IDENTITIES",
        "P608_PACKAGE_BOUNDS",
        "P608_PACKAGE_CONFIDENTIALITY",
        "P608_PACKAGE_MIME",
        "P608_PACKAGE_HASHES",
        "P608_PACKAGE_MODE",
        "P608_PACKAGE_SNAPSHOT",
        "P608_PACKAGE_PROJECTION",
        "P608_PACKAGE_TIME_PROJECTION",
        "P608_PACKAGE_JSON_PROJECTION",
        "P608_PACKAGE_EXPIRY",
        "P608_PACKAGE_PARENT",
        "P608_PACKAGE_STANDARD_VALIDATION",
        "P608_PACKAGE_RECEIPT_NORMALIZE_IDENTITIES",
        "P608_PACKAGE_RECEIPT_HASHES",
        "P608_PACKAGE_RECEIPT_OPERATION",
        "P608_PACKAGE_RECEIPT_KEY",
        "P608_PACKAGE_RECEIPT_INITIAL_STATE",
        "P608_PACKAGE_RECEIPT_UPDATE_IDENTITY",
        "P608_PACKAGE_RECEIPT_SEAL_SHAPE",
        "P608_PACKAGE_RECEIPT_TARGET",
        "P608_PACKAGE_RECEIPT_TARGET_IDENTITY",
        "P608_PACKAGE_RECEIPT_RESPONSE",
        "P608_PACKAGE_RECEIPT_STANDARD_VALIDATION",
    }
)
_DIAGNOSTIC_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def require_tooling_export_write() -> None:
    if not getattr(frappe.flags, TOOLING_EXPORT_WRITE_FLAG, False):
        frappe.throw(
            _("Tooling export records can only be written by the controlled export command."),
            frappe.PermissionError,
        )


@contextmanager
def tooling_export_write() -> Iterator[None]:
    """Open only the controlled preference, package, and receipt write scope."""

    with _flag_scope(TOOLING_EXPORT_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        yield


@contextmanager
def tooling_package_create_diagnostics(
    trace_id: str,
    *,
    enabled: bool,
) -> Iterator[None]:
    """Activate one response-neutral package-create validation diagnostic."""

    state = (
        {"trace_id": trace_id, "substage": None, "recorded": False}
        if enabled and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
        else None
    )
    missing = object()
    previous = getattr(frappe.flags, PACKAGE_CREATE_DIAGNOSTIC_FLAG, missing)
    setattr(frappe.flags, PACKAGE_CREATE_DIAGNOSTIC_FLAG, state)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, PACKAGE_CREATE_DIAGNOSTIC_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, PACKAGE_CREATE_DIAGNOSTIC_FLAG, previous)


def mark_tooling_package_create_substage(code: str) -> None:
    state = _tooling_package_create_diagnostic_state()
    if state is not None and code in PACKAGE_CREATE_DIAGNOSTIC_CODES:
        state["substage"] = code


def record_tooling_package_create_fallback(error: Exception) -> None:
    state = _tooling_package_create_diagnostic_state()
    if state is None or state.get("recorded") is True:
        return
    candidate = state.get("substage")
    code = (
        str(candidate)
        if candidate in PACKAGE_CREATE_DIAGNOSTIC_CODES
        else "P608_PACKAGE_TRANSACTION_LIFECYCLE"
    )
    exception_type = type(error).__name__
    if _DIAGNOSTIC_TYPE_PATTERN.fullmatch(exception_type) is None:
        return
    state["recorded"] = True
    try:
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Tooling package creation failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        pass


def _tooling_package_create_diagnostic_state() -> dict[str, object] | None:
    state = getattr(frappe.flags, PACKAGE_CREATE_DIAGNOSTIC_FLAG, None)
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "substage", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _DIAGNOSTIC_TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
    ):
        return None
    return state


def deny_tooling_export_update() -> None:
    frappe.throw(
        _("Tooling export history is immutable."),
        frappe.PermissionError,
    )


def deny_tooling_export_delete(_document: object) -> None:
    frappe.throw(
        _("Tooling export records cannot be deleted."),
        frappe.PermissionError,
    )


def canonical_export_uuid(document: object, fieldname: str, label: str) -> None:
    setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))


def validate_immutable_snapshot(
    document: object,
    *,
    snapshot_field: str,
    snapshot_label: str,
    snapshot_hash_field: str,
    immutable_fields: tuple[str, ...],
) -> dict[str, object]:
    previous = document.get_doc_before_save()
    if previous is not None:
        assert_immutable_fields(document, previous, immutable_fields)
        deny_tooling_export_update()
    return validate_hashed_snapshot(
        document,
        snapshot_field=snapshot_field,
        snapshot_label=snapshot_label,
        snapshot_hash_field=snapshot_hash_field,
    )


def validate_hashed_snapshot(
    document: object,
    *,
    snapshot_field: str,
    snapshot_label: str,
    snapshot_hash_field: str,
) -> dict[str, object]:
    snapshot = json_object(getattr(document, snapshot_field), snapshot_label)
    expected_hash = sha256_json(snapshot)
    current_hash = getattr(document, snapshot_hash_field)
    if current_hash not in (None, "", expected_hash):
        frappe.throw(
            _("Tooling export snapshot hash does not match."),
            frappe.ValidationError,
        )
    setattr(document, snapshot_field, canonical_json(snapshot))
    setattr(
        document,
        snapshot_hash_field,
        lowercase_sha256(expected_hash, _("Snapshot Hash")),
    )
    return snapshot


def require_snapshot_projection(
    document: object,
    snapshot: dict[str, object],
    projection: tuple[tuple[str, str], ...],
) -> None:
    for fieldname, snapshot_key in projection:
        if str(getattr(document, fieldname)) != str(snapshot.get(snapshot_key)):
            frappe.throw(
                _("Tooling export fields do not match the exact snapshot."),
                frappe.ValidationError,
            )


def require_datetime_snapshot_projection(
    document: object,
    snapshot: dict[str, object],
    projection: tuple[tuple[str, str], ...],
) -> None:
    for fieldname, snapshot_key in projection:
        actual = get_datetime(getattr(document, fieldname))
        expected = get_datetime(snapshot.get(snapshot_key))
        if actual.tzinfo is not None:
            actual = actual.astimezone(UTC).replace(tzinfo=None)
        if expected.tzinfo is not None:
            expected = expected.astimezone(UTC).replace(tzinfo=None)
        if actual != expected:
            frappe.throw(
                _("Tooling export fields do not match the exact snapshot."),
                frappe.ValidationError,
            )


def require_json_projection(
    document: object,
    fieldname: str,
    snapshot: dict[str, object],
    snapshot_key: str,
) -> None:
    actual = frappe.parse_json(getattr(document, fieldname))
    if actual != snapshot.get(snapshot_key):
        frappe.throw(
            _("Tooling export fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    setattr(document, fieldname, canonical_json(actual))


def validate_preference_version(document: object, immutable_fields: tuple[str, ...]) -> None:
    previous = document.get_doc_before_save()
    current = getattr(document, "optimistic_version")
    if previous is None:
        if current != 1:
            frappe.throw(
                _("A new Tooling List preference must start at version one."),
                frappe.ValidationError,
            )
        return
    assert_immutable_fields(document, previous, immutable_fields)
    if current != previous.optimistic_version + 1:
        frappe.throw(
            _("The Tooling List preference version is stale."),
            frappe.ValidationError,
        )


def validate_package_expiry(document: object) -> None:
    generated_at = get_datetime(getattr(document, "generated_at"))
    expires_at = get_datetime(getattr(document, "expires_at"))
    if expires_at - generated_at != timedelta(seconds=TOOLING_OBJECT_PACKAGE_VALIDITY.total_seconds()):
        frappe.throw(
            _("The Tooling object package must expire after one hour."),
            frappe.ValidationError,
        )


@contextmanager
def _flag_scope(flag_name: str) -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, flag_name, missing)
    setattr(frappe.flags, flag_name, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, flag_name)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, flag_name, previous)
