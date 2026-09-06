from __future__ import annotations

import json
import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_mbom_execution_delete,
    require_mbom_execution_write,
)
from npi_erpnext_connector.item_contract import canonical_hash, canonical_json


_HASH = re.compile(r"^[a-f0-9]{64}$")
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class NPIERPMBOMOperationReceipt(Document):
    def autoname(self) -> None:
        self.target_idempotency_key_hash = _hash(
            self.target_idempotency_key_hash,
            _("Target Idempotency Key Hash"),
        )
        self.name = self.target_idempotency_key_hash

    def before_insert(self) -> None:
        require_mbom_execution_write()

    def before_save(self) -> None:
        require_mbom_execution_write()

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("ERPNext MBOM operation receipts are immutable."),
                frappe.ValidationError,
            )
        for fieldname, label in (
            ("target_idempotency_key_hash", _("Target Idempotency Key Hash")),
            ("semantic_request_hash", _("Semantic Request Hash")),
            ("source_hash", _("Source Hash")),
            ("topology_hash", _("Topology Hash")),
            ("result_hash", _("Result Hash")),
        ):
            setattr(self, fieldname, _hash(getattr(self, fieldname), label))
        self.request_global_id = _uuid(self.request_global_id, _("Request Global ID"))
        if self.operation != "publish_released_mbom":
            frappe.throw(
                _("ERPNext MBOM operation receipt type is invalid."),
                frappe.ValidationError,
            )
        if not isinstance(self.trace_id, str) or _TRACE.fullmatch(self.trace_id) is None:
            frappe.throw(_("Trace ID is invalid."), frappe.ValidationError)
        if (
            not isinstance(self.service_user, str)
            or not self.service_user
            or self.service_user != self.service_user.strip()
            or len(self.service_user) > 254
        ):
            frappe.throw(_("Service User is invalid."), frappe.ValidationError)
        try:
            result = json.loads(self.result_json)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise frappe.ValidationError(_("Result JSON is invalid.")) from error
        if (
            not isinstance(result, list)
            or not result
            or len(result) > 499
            or canonical_json(result) != self.result_json
            or canonical_hash(result) != self.result_hash
        ):
            frappe.throw(
                _("ERPNext MBOM operation result binding is invalid."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_mbom_execution_delete()


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
