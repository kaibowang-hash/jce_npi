from __future__ import annotations

import json
import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_tool_asset_execution_delete,
    require_tool_asset_execution_write,
)
from npi_erpnext_connector.item_contract import canonical_hash, canonical_json


_HASH = re.compile(r"^[a-f0-9]{64}$")
_OPERATIONS = {"create_tool_asset", "update_tool_asset"}


class NPIERPToolAssetOperationReceipt(Document):
    def autoname(self) -> None:
        self.target_idempotency_key_hash = _hash(
            self.target_idempotency_key_hash,
            _("Target Idempotency Key Hash"),
        )
        self.name = self.target_idempotency_key_hash

    def before_insert(self) -> None:
        require_tool_asset_execution_write()

    def before_save(self) -> None:
        require_tool_asset_execution_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("ERPNext Tool Asset operation receipts are immutable."),
                frappe.PermissionError,
            )

    def validate(self) -> None:
        for fieldname, label in (
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("semantic_request_hash", _("Semantic Request Hash")),
            ("source_stream_key_hash", _("Tool Asset Source Stream Key Hash")),
            ("source_hash", _("Source Hash")),
            ("result_hash", _("Result Hash")),
        ):
            setattr(self, fieldname, _hash(getattr(self, fieldname), label))
        self.request_global_id = _uuid(
            self.request_global_id,
            _("Request Global ID"),
        )
        if self.operation not in _OPERATIONS:
            frappe.throw(_("Tool Asset Operation is invalid."), frappe.ValidationError)
        for value, label, maximum in (
            (self.formal_asset_id, _("Formal Asset ID"), 140),
            (self.target_version, _("Target Version"), 140),
            (self.trace_id, _("Trace ID"), 128),
        ):
            _text(value, label, maximum)
        if type(self.mapping_version) is not int or self.mapping_version < 1:
            frappe.throw(
                _("Tool Asset Mapping Version is invalid."),
                frappe.ValidationError,
            )
        try:
            result = json.loads(self.result_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise frappe.ValidationError(_("Result JSON is invalid.")) from error
        if (
            canonical_json(result) != self.result_json
            or canonical_hash(result) != self.result_hash
        ):
            frappe.throw(_("Result JSON is invalid."), frappe.ValidationError)
        if not frappe.db.exists("Asset", self.formal_asset_id):
            frappe.throw(
                _("The mapped ERPNext Asset is unavailable."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_tool_asset_execution_delete()


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
    return value


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise frappe.ValidationError(_("{0} is invalid.").format(label)) from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
    return str(parsed)


def _text(value: object, label: str, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
