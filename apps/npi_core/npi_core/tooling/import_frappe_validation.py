from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
)
from npi_core.tooling.domain import sha256_json


TOOLING_IMPORT_WRITE_FLAG = "npi_tooling_import_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


def require_tooling_import_write() -> None:
    if not getattr(frappe.flags, TOOLING_IMPORT_WRITE_FLAG, False):
        frappe.throw(
            _("Tooling import history can only be written by the controlled import command."),
            frappe.PermissionError,
        )


@contextmanager
def tooling_import_write() -> Iterator[None]:
    """Open the narrow import-metadata and audit append scope."""

    with _flag_scope(TOOLING_IMPORT_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        yield


def deny_tooling_import_update() -> None:
    frappe.throw(
        _("Tooling import history is immutable."),
        frappe.PermissionError,
    )


def deny_tooling_import_delete(_document: object) -> None:
    frappe.throw(
        _("Tooling import history cannot be deleted."),
        frappe.PermissionError,
    )


def canonical_import_uuid(document: object, fieldname: str, label: str) -> None:
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
        deny_tooling_import_update()
    snapshot = json_object(getattr(document, snapshot_field), snapshot_label)
    expected_hash = sha256_json(snapshot)
    current_hash = getattr(document, snapshot_hash_field)
    if current_hash not in (None, "", expected_hash):
        frappe.throw(
            _("Tooling import snapshot hash does not match."),
            frappe.ValidationError,
        )
    setattr(document, snapshot_field, canonical_json(snapshot))
    setattr(
        document,
        snapshot_hash_field,
        lowercase_sha256(expected_hash, _("Snapshot Hash")),
    )
    return snapshot


def validate_hashed_snapshot(
    document: object,
    *,
    snapshot_field: str,
    snapshot_label: str,
    snapshot_hash_field: str,
) -> dict[str, object]:
    """Canonicalize a guarded mutable projection without weakening its hash."""

    snapshot = json_object(getattr(document, snapshot_field), snapshot_label)
    expected_hash = sha256_json(snapshot)
    current_hash = getattr(document, snapshot_hash_field)
    if current_hash not in (None, "", expected_hash):
        frappe.throw(
            _("Tooling import snapshot hash does not match."),
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
        actual = getattr(document, fieldname)
        expected = snapshot.get(snapshot_key)
        if str(actual) != str(expected):
            frappe.throw(
                _("Tooling import fields do not match the exact snapshot."),
                frappe.ValidationError,
            )


def correction_file_content(file_document: object) -> tuple[bytes, int]:
    """Return correction bytes plus the pinned Frappe File size representation.

    The legacy ``save_file`` path re-reads plain-text files during ``File``
    insertion. Pinned Frappe decodes that content to ``str`` and consequently
    stores ``file_size`` as a character count. The correction contract still
    exposes an actual byte count, so callers must keep the two measurements
    distinct while verifying both.
    """

    raw_content = file_document.get_content()
    if isinstance(raw_content, bytes):
        return raw_content, len(raw_content)
    if isinstance(raw_content, str):
        return raw_content.encode("utf-8"), len(raw_content)
    frappe.throw(
        _("The exact private correction file is unavailable."),
        frappe.ValidationError,
    )
    raise AssertionError("unreachable")


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
