from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.gate_evidence.domain import evidence_reference_key


_CONTROLLED_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_RAW_PRIVATE_FILE_MARKER = "/private/files/"

FILE_REVISION_COMMAND_FLAG = "npi_file_revision_command_write"
FILE_SCAN_RESULT_FLAG = "npi_file_scan_result_write"
GATE_EVIDENCE_COMMAND_FLAG = "npi_gate_evidence_command_write"


def require_file_revision_command_write() -> None:
    _require_flag(
        FILE_REVISION_COMMAND_FLAG,
        _("File revisions can only be changed through an authorized NPI file command."),
    )


def require_file_scan_result_write() -> None:
    _require_flag(
        FILE_SCAN_RESULT_FLAG,
        _("File scan results can only be changed by an authorized scanner operation."),
    )


def require_gate_evidence_command_write() -> None:
    _require_flag(
        GATE_EVIDENCE_COMMAND_FLAG,
        _(
            "Gate evidence references can only be added through an authorized NPI Gate command."
        ),
    )


def has_controlled_file_write() -> bool:
    return bool(
        getattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, False)
        or getattr(frappe.flags, FILE_SCAN_RESULT_FLAG, False)
    )


def deny_controlled_evidence_delete() -> None:
    frappe.throw(
        _("Controlled Gate evidence history cannot be deleted."),
        frappe.PermissionError,
    )


def canonical_uuid(value: object, label_source: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        frappe.throw(
            _("{field} must be a valid UUID.").format(field=label_source),
            frappe.ValidationError,
        )
    return str(parsed)


def controlled_key(value: object, label_source: str) -> str:
    if not isinstance(value, str) or _CONTROLLED_KEY_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a valid controlled key.").format(field=label_source),
            frappe.ValidationError,
        )
    return value


def lowercase_sha256(value: object, label_source: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        frappe.throw(
            _("{field} must be a lowercase SHA-256 hash.").format(field=label_source),
            frappe.ValidationError,
        )
    return value


def positive_integer(value: object, label_source: str) -> int:
    if type(value) is not int or value < 1:
        frappe.throw(
            _("{field} must be greater than zero.").format(field=label_source),
            frappe.ValidationError,
        )
    return value


def canonical_json_object(
    value: object, label_source: str
) -> tuple[dict[str, Any], str]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, dict):
        frappe.throw(
            _("{field} must be a JSON object.").format(field=label_source),
            frappe.ValidationError,
        )
    _deny_raw_private_file_data(parsed)
    canonical = json.dumps(
        parsed,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return json.loads(canonical), canonical


def canonical_snapshot_hash(snapshot: Mapping[str, object]) -> str:
    canonical = json.dumps(
        dict(snapshot),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_flag(flag_name: str, message: str) -> None:
    if not getattr(frappe.flags, flag_name, False):
        frappe.throw(message, frappe.PermissionError)


def _deny_raw_private_file_data(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized_key = re.sub(r"[^a-z]", "", str(key).casefold())
            if "url" in normalized_key:
                frappe.throw(
                    _("A controlled evidence snapshot cannot contain a raw file URL."),
                    frappe.ValidationError,
                )
            _deny_raw_private_file_data(nested)
        return
    if isinstance(value, list | tuple):
        for nested in value:
            _deny_raw_private_file_data(nested)
        return
    if isinstance(value, str) and _RAW_PRIVATE_FILE_MARKER in value.casefold():
        frappe.throw(
            _("A controlled evidence snapshot cannot contain a raw file URL."),
            frappe.ValidationError,
        )
