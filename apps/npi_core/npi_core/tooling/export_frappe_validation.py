from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
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
