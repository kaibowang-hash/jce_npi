from __future__ import annotations

import json
import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_item_execution_delete,
    require_item_execution_write,
)
from npi_erpnext_connector.item_contract import canonical_hash, canonical_json


_HASH = re.compile(r"^[a-f0-9]{64}$")
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_INTENTS = {"create_item", "update_item_engineering_fields"}


class NPIERPItemOperationReceipt(Document):
    def autoname(self) -> None:
        self.target_idempotency_key_hash = _hash(
            self.target_idempotency_key_hash,
            _("Target Idempotency Key Hash"),
        )
        self.name = self.target_idempotency_key_hash

    def before_insert(self) -> None:
        require_item_execution_write()

    def before_save(self) -> None:
        require_item_execution_write()

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("ERPNext Item operation receipts are immutable."),
                frappe.ValidationError,
            )
        for fieldname, label in (
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("semantic_request_hash", _("Semantic Request Hash")),
            ("source_stream_key_hash", _("Item Source Stream Key Hash")),
            ("source_hash", _("Source Hash")),
            ("result_hash", _("Result Hash")),
        ):
            setattr(self, fieldname, _hash(getattr(self, fieldname), label))
        self.request_global_id = _uuid(self.request_global_id, _("Request Global ID"))
        if self.operation != "publish_released_item" or self.intent not in _INTENTS:
            frappe.throw(
                _("ERPNext Item operation receipt type is invalid."),
                frappe.ValidationError,
            )
        if type(self.mapping_version) is not int or self.mapping_version < 1:
            frappe.throw(
                _("Item Mapping Version is invalid."),
                frappe.ValidationError,
            )
        if not isinstance(self.trace_id, str) or _TRACE.fullmatch(self.trace_id) is None:
            frappe.throw(_("Trace ID is invalid."), frappe.ValidationError)
        for value, label in (
            (self.formal_item_code, _("Formal Item Code")),
            (self.target_version, _("Target Version")),
            (self.service_user, _("Service User")),
        ):
            if not isinstance(value, str) or not value or value != value.strip() or len(value) > 254:
                frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
        try:
            result = json.loads(self.result_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise frappe.ValidationError(_("Result JSON is invalid.")) from error
        expected = {
            "formalItemCode": self.formal_item_code,
            "targetVersion": self.target_version,
            "mappingVersion": self.mapping_version,
        }
        if (
            result != expected
            or canonical_json(result) != self.result_json
            or canonical_hash(result) != self.result_hash
        ):
            frappe.throw(
                _("ERPNext Item operation result binding is invalid."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_item_execution_delete()


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
