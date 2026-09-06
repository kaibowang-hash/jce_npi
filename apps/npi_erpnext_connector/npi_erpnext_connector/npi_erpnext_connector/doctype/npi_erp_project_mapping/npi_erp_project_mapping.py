from __future__ import annotations

from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_erpnext_connector.frappe_validation import (
    deny_project_delivery_delete,
    require_project_delivery_write,
)


class NPIERPProjectMapping(Document):
    def autoname(self) -> None:
        if not isinstance(self.source_project_id, str) or not self.source_project_id:
            frappe.throw(_("Source Project is required."), frappe.ValidationError)
        self.name = self.source_project_id

    def before_insert(self) -> None:
        require_project_delivery_write()

    def before_save(self) -> None:
        require_project_delivery_write()

    def validate(self) -> None:
        if self.get_doc_before_save():
            frappe.throw(
                _("A Project identity mapping is immutable."),
                frappe.ValidationError,
            )
        for fieldname, label in (
            ("target_project_global_id", _("Target Project Global ID")),
            ("receipt_id", _("Receipt ID")),
            ("event_id", _("Event ID")),
        ):
            setattr(self, fieldname, _uuid(getattr(self, fieldname, None), label))
        if int(self.source_version or 0) < 1 or not self.mapped_at:
            frappe.throw(_("Project mapping is incomplete."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_project_delivery_delete()


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise frappe.ValidationError(_("{0} is invalid.").format(label)) from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        frappe.throw(_("{0} is invalid.").format(label), frappe.ValidationError)
    return str(parsed)
