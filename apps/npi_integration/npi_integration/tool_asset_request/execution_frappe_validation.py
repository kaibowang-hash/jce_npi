from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

import frappe
from frappe import _


TOOL_ASSET_EXECUTION_REQUEST_WRITE_FLAG = "npi_tool_asset_execution_request_write"
TOOL_ASSET_EXECUTION_IDEMPOTENCY_WRITE_FLAG = "npi_tool_asset_execution_idempotency_write"
TOOL_ASSET_EXECUTION_STREAM_WRITE_FLAG = "npi_tool_asset_execution_stream_write"
TOOL_ASSET_EXECUTION_ATTEMPT_WRITE_FLAG = "npi_tool_asset_execution_attempt_write"
TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG = "npi_tool_asset_execution_result_write"
TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG = "npi_tool_asset_execution_mapping_write"
TOOL_ASSET_EXECUTION_OUTBOX_WRITE_FLAG = "npi_tool_asset_execution_outbox_write"


@dataclass(frozen=True, slots=True)
class ToolAssetSupportWriteCapability:
    actor: str
    scope: str
    allowed: frozenset[tuple[str, str]]


_CURRENT_CAPABILITY: ContextVar[ToolAssetSupportWriteCapability | None] = ContextVar(
    "npi_tool_asset_support_write_capability",
    default=None,
)


_SUPPORT_FLAGS = {
    "NPI Tool Asset Request": TOOL_ASSET_EXECUTION_REQUEST_WRITE_FLAG,
    "NPI Tool Asset Command Idempotency": TOOL_ASSET_EXECUTION_IDEMPOTENCY_WRITE_FLAG,
    "NPI Tool Asset Stream Guard": TOOL_ASSET_EXECUTION_STREAM_WRITE_FLAG,
    "NPI Tool Asset Attempt": TOOL_ASSET_EXECUTION_ATTEMPT_WRITE_FLAG,
    "NPI Tool Asset Result": TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG,
    "NPI Tool Asset Field Result": TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG,
    "NPI Tool Asset Mapping Observation": TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG,
    "NPI Tool Asset Mapping Head": TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG,
    "NPI Outbox Message": TOOL_ASSET_EXECUTION_OUTBOX_WRITE_FLAG,
}


def require_tool_asset_execution_request_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_REQUEST_WRITE_FLAG, _("Tool Asset execution requests can only be changed through an authorized NPI command."))


def require_tool_asset_execution_idempotency_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_IDEMPOTENCY_WRITE_FLAG, _("Tool Asset execution idempotency records can only be changed through an authorized NPI command."))


def require_tool_asset_execution_stream_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_STREAM_WRITE_FLAG, _("Tool Asset execution stream guards can only be changed by the controlled execution service."))


def require_tool_asset_execution_attempt_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_ATTEMPT_WRITE_FLAG, _("Tool Asset execution attempts can only be changed by the controlled execution service."))


def require_tool_asset_execution_result_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_RESULT_WRITE_FLAG, _("Tool Asset execution results can only be appended by the controlled execution service."))


def require_tool_asset_execution_mapping_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_MAPPING_WRITE_FLAG, _("Tool Asset mapping records can only be changed by the controlled execution service."))


def require_tool_asset_execution_outbox_write() -> None:
    _require_flag(TOOL_ASSET_EXECUTION_OUTBOX_WRITE_FLAG, _("Tool Asset execution Outbox messages can only be changed by the controlled execution service."))


def require_tool_asset_execution_capability(doctype: str, action: str) -> None:
    capability = _CURRENT_CAPABILITY.get()
    if capability is None or (doctype, action) not in capability.allowed:
        frappe.throw(_("This Tool Asset support record is outside the active execution capability."), frappe.PermissionError)


def deny_tool_asset_execution_history_update() -> None:
    frappe.throw(_("Tool Asset execution history cannot be changed."), frappe.PermissionError)


def deny_tool_asset_execution_history_delete() -> None:
    frappe.throw(_("Tool Asset execution history cannot be deleted."), frappe.PermissionError)


def deny_tool_asset_outbox_conversion() -> None:
    frappe.throw(_("Outbox messages cannot be converted between Item, MBOM and Tool Asset execution."), frappe.PermissionError)


@contextmanager
def _tool_asset_support_write(
    actor: str,
    scope: str,
    allowed: frozenset[tuple[str, str]],
) -> Iterator[ToolAssetSupportWriteCapability]:
    """Internal capability seam; checkpoint 1 has no caller or write route."""

    capability = ToolAssetSupportWriteCapability(actor=actor, scope=scope, allowed=allowed)
    token = _CURRENT_CAPABILITY.set(capability)
    names = {_SUPPORT_FLAGS[doctype] for doctype, _action in allowed}
    previous = {name: getattr(frappe.flags, name, None) for name in names}
    try:
        for name in names:
            setattr(frappe.flags, name, True)
        yield capability
    finally:
        for name, value in previous.items():
            if value is None:
                try:
                    delattr(frappe.flags, name)
                except AttributeError:
                    pass
            else:
                setattr(frappe.flags, name, value)
        _CURRENT_CAPABILITY.reset(token)


def _require_flag(name: str, message: str) -> None:
    if not getattr(frappe.flags, name, False):
        frappe.throw(message, frappe.PermissionError)
