from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import frappe
from frappe import _


ITEM_OUTBOX_WRITE_FLAG = "npi_item_outbox_write"
ITEM_REQUEST_WRITE_FLAG = "npi_item_publish_request_write"
ITEM_IDEMPOTENCY_WRITE_FLAG = "npi_item_publish_idempotency_write"
ITEM_ATTEMPT_WRITE_FLAG = "npi_item_publish_attempt_write"
ITEM_RESULT_WRITE_FLAG = "npi_item_publish_result_write"
ITEM_MAPPING_WRITE_FLAG = "npi_item_mapping_write"
AUDIT_APPEND_FLAG = "npi_audit_append"


def require_item_outbox_write() -> None:
    _require_flag(
        ITEM_OUTBOX_WRITE_FLAG,
        _("Item publish Outbox messages can only be changed by the controlled Item execution service."),
    )


def require_item_request_write() -> None:
    _require_flag(
        ITEM_REQUEST_WRITE_FLAG,
        _("Item publish requests can only be changed through an authorized NPI command."),
    )


def require_item_idempotency_write() -> None:
    _require_flag(
        ITEM_IDEMPOTENCY_WRITE_FLAG,
        _("Item publish idempotency records can only be changed through an authorized NPI command."),
    )


def require_item_attempt_write() -> None:
    _require_flag(
        ITEM_ATTEMPT_WRITE_FLAG,
        _("Item publish attempts can only be changed by the controlled Item execution service."),
    )


def require_item_result_write() -> None:
    _require_flag(
        ITEM_RESULT_WRITE_FLAG,
        _("Item publish results can only be appended by the controlled Item execution service."),
    )


def require_item_mapping_write() -> None:
    _require_flag(
        ITEM_MAPPING_WRITE_FLAG,
        _("Item mapping records can only be changed by the controlled Item execution service."),
    )


def deny_item_history_update() -> None:
    frappe.throw(
        _("Item publish execution history cannot be changed."),
        frappe.PermissionError,
    )


def deny_item_history_delete() -> None:
    frappe.throw(
        _("Item publish execution history cannot be deleted."),
        frappe.PermissionError,
    )


def deny_legacy_outbox_promotion() -> None:
    frappe.throw(
        _("Legacy Outbox messages cannot be promoted into Item execution."),
        frappe.PermissionError,
    )


@contextmanager
def item_request_transaction_write() -> Iterator[None]:
    """Authorize one command/idempotency/request/Outbox/audit transaction."""

    with (
        _flag_scope(ITEM_REQUEST_WRITE_FLAG),
        _flag_scope(ITEM_IDEMPOTENCY_WRITE_FLAG),
        _flag_scope(ITEM_OUTBOX_WRITE_FLAG),
        _flag_scope(AUDIT_APPEND_FLAG),
    ):
        yield


@contextmanager
def item_claim_write() -> Iterator[None]:
    with (
        _flag_scope(ITEM_OUTBOX_WRITE_FLAG),
        _flag_scope(ITEM_REQUEST_WRITE_FLAG),
        _flag_scope(ITEM_ATTEMPT_WRITE_FLAG),
        _flag_scope(AUDIT_APPEND_FLAG),
    ):
        yield


@contextmanager
def item_result_transaction_write() -> Iterator[None]:
    """Authorize one result, mapping, terminal-state and audit transaction."""

    with (
        _flag_scope(ITEM_OUTBOX_WRITE_FLAG),
        _flag_scope(ITEM_REQUEST_WRITE_FLAG),
        _flag_scope(ITEM_ATTEMPT_WRITE_FLAG),
        _flag_scope(ITEM_RESULT_WRITE_FLAG),
        _flag_scope(ITEM_MAPPING_WRITE_FLAG),
        _flag_scope(AUDIT_APPEND_FLAG),
    ):
        yield


@contextmanager
def item_mapping_write() -> Iterator[None]:
    with _flag_scope(ITEM_MAPPING_WRITE_FLAG), _flag_scope(AUDIT_APPEND_FLAG):
        yield


def validate_one_way_transition(
    before: object,
    after: object,
    *,
    allowed: dict[str, frozenset[str]],
    label: str,
) -> None:
    previous = str(before or "")
    current = str(after or "")
    if current == previous:
        return
    if current not in allowed.get(previous, frozenset()):
        frappe.throw(
            _("{record} state transition is invalid.").format(record=label),
            frappe.ValidationError,
        )


def _require_flag(name: str, message: str) -> None:
    if not getattr(frappe.flags, name, False):
        frappe.throw(message, frappe.PermissionError)


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
