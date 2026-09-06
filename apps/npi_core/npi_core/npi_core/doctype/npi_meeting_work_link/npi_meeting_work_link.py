from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.collaboration.frappe_validation import deny_collaboration_delete, require_collaboration_write, validate_uuid


class NPIMeetingWorkLink(Document):
    def before_insert(self) -> None:
        require_collaboration_write()

    def before_save(self) -> None:
        require_collaboration_write()
        if not self.is_new():
            frappe.throw(_("Meeting work links are immutable."), frappe.PermissionError)

    def on_trash(self) -> None:
        deny_collaboration_delete()

    def validate(self) -> None:
        for fieldname, label in (
            ("link_id", _("Link ID")),
            ("project_global_id", _("Project Global ID")),
            ("meeting_global_id", _("Meeting Global ID")),
            ("work_item_global_id", _("Work Item Global ID")),
        ):
            self.set(fieldname, validate_uuid(self.get(fieldname), label))
        if self.kind not in {"action", "decision_request"}:
            frappe.throw(_("Select an action or decision request."), frappe.ValidationError)
        if not self.tenant_id:
            frappe.throw(_("Meeting work link identity is required."), frappe.ValidationError)
        if (
            not isinstance(self.item_key, str)
            or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", self.item_key) is None
        ):
            frappe.throw(_("Enter a valid controlled key."), frappe.ValidationError)
