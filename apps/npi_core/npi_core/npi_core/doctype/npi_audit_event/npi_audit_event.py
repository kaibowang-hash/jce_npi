import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project.frappe_validation import deny_controlled_history_delete


class NPIAuditEvent(Document):
    """Administrative projection of an immutable NPI audit event."""

    def before_insert(self) -> None:
        if not getattr(frappe.flags, "npi_audit_append", False):
            frappe.throw(
                _("Audit events can only be appended by an authorized NPI command."),
                frappe.PermissionError,
            )

    def before_save(self) -> None:
        if not self.is_new():
            frappe.throw(
                _("Audit events cannot be changed."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_controlled_history_delete()
