from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_integration.project_publish.domain import parse_uuid
from npi_integration.project_publish.frappe_validation import deny_project_publish_delete, require_project_publish_write


class NPIERPProjectPublishAttempt(Document):
    def autoname(self) -> None:
        self.global_id = parse_uuid(self.global_id, "attemptGlobalId")
        self.name = self.global_id

    def before_insert(self) -> None:
        require_project_publish_write()

    def before_save(self) -> None:
        require_project_publish_write()

    def on_trash(self) -> None:
        deny_project_publish_delete()

    def validate(self) -> None:
        self.global_id = parse_uuid(self.global_id, "attemptGlobalId")
        self.request_global_id = parse_uuid(self.request_global_id, "requestGlobalId")
        if type(self.attempt_number) is not int or self.attempt_number < 1 or self.attempt_kind not in {"publish", "reconcile"}:
            frappe.throw(_("ERP Project publication attempt is invalid."), frappe.ValidationError)
        previous = self.get_doc_before_save()
        if previous is not None and previous.state != "started":
            frappe.throw(_("ERP Project publication attempt history is immutable."), frappe.PermissionError)
        if previous is not None:
            for fieldname in ("global_id", "request_global_id", "attempt_number", "attempt_kind", "attempt_key_hash", "trace_id", "started_at"):
                if self.get(fieldname) != previous.get(fieldname):
                    frappe.throw(_("ERP Project publication attempt identity is immutable."), frappe.ValidationError)
