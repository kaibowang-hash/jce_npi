from __future__ import annotations

import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_mbom_execution_delete,
    require_mbom_execution_write,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")


class NPIERPMBOMMapping(Document):
    def autoname(self) -> None:
        self.assembly_source_key = _hash(
            self.assembly_source_key, _("Assembly Source Key")
        )
        self.name = self.assembly_source_key

    def before_insert(self) -> None:
        require_mbom_execution_write()

    def before_save(self) -> None:
        require_mbom_execution_write()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            for fieldname in (
                "assembly_source_key",
                "tenant_id",
                "project_global_id",
                "ebom_global_id",
                "stable_line_key",
                "formal_bom_id",
            ):
                if getattr(previous, fieldname, None) != getattr(self, fieldname, None):
                    frappe.throw(
                        _("ERPNext MBOM mapping identity fields are immutable."),
                        frappe.ValidationError,
                    )
        for fieldname, label in (
            ("assembly_source_key", _("Assembly Source Key")),
            ("source_hash", _("Source Hash")),
            ("topology_hash", _("Topology Hash")),
            (
                "last_target_idempotency_key_hash",
                _("Last Target Idempotency Key Hash"),
            ),
        ):
            setattr(self, fieldname, _hash(getattr(self, fieldname), label))
        self.project_global_id = _uuid(self.project_global_id, _("Project Global ID"))
        self.ebom_global_id = _uuid(self.ebom_global_id, _("EBOM Global ID"))
        self.last_request_global_id = _uuid(
            self.last_request_global_id, _("Last Request Global ID")
        )
        for value, label, maximum in (
            (self.tenant_id, _("Tenant ID"), 128),
            (self.stable_line_key, _("Stable Line Key"), 128),
            (self.formal_bom_id, _("Formal BOM ID"), 140),
            (self.target_version, _("Target Version"), 140),
        ):
            _text(value, label, maximum)
        expected_version = 1 if previous is None else int(previous.mapping_version) + 1
        if type(self.mapping_version) is not int or self.mapping_version != expected_version:
            frappe.throw(
                _("The ERPNext MBOM mapping version must advance by one."),
                frappe.ValidationError,
            )
        if self.submission_state not in {"editable_draft", "submitted_immutable"}:
            frappe.throw(_("BOM Submission State is invalid."), frappe.ValidationError)
        if not frappe.db.exists("BOM", self.formal_bom_id):
            frappe.throw(_("The mapped ERPNext BOM is unavailable."), frappe.ValidationError)

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


def _text(value: object, label: str, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
