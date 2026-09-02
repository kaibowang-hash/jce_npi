from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.collaboration.domain import preference_email_kinds
from npi_core.collaboration.frappe_validation import (
    canonical_json,
    deny_collaboration_delete,
    immutable_fields,
    increment_version,
    require_collaboration_write,
    validate_uuid,
)


class NPINotificationPreference(Document):
    def before_insert(self) -> None:
        require_collaboration_write()

    def before_save(self) -> None:
        require_collaboration_write()

    def on_trash(self) -> None:
        deny_collaboration_delete()

    def validate(self) -> None:
        self.global_id = validate_uuid(self.global_id, _("Global ID"))
        values, _ = canonical_json(self.email_kinds, _("Notification Email Types"), list)
        self.email_kinds = json.dumps(
            [item.value for item in preference_email_kinds(values)],
            separators=(",", ":"),
        )
        if not self.tenant_id or not self.user_id:
            frappe.throw(_("Notification preference identity is required."), frappe.ValidationError)
        if not self.critical_audit_email:
            frappe.throw(_("Critical audit notifications cannot be disabled."), frappe.ValidationError)
        immutable_fields(self, ("global_id", "tenant_id", "user_id", "critical_audit_email"))
        increment_version(self)
