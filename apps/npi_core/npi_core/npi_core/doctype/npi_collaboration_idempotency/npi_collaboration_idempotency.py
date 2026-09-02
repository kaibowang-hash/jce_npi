from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.collaboration.frappe_validation import (
    canonical_json,
    deny_collaboration_delete,
    immutable_fields,
    require_collaboration_write,
    validate_hash,
    validate_uuid,
)


class NPICollaborationIdempotency(Document):
    _OPERATIONS = {
        "meeting_minute.create",
        "notification.mark_read",
        "notification_preference.set",
    }

    def before_insert(self) -> None:
        require_collaboration_write()

    def before_save(self) -> None:
        require_collaboration_write()

    def on_trash(self) -> None:
        deny_collaboration_delete()

    def validate(self) -> None:
        self.record_id = validate_uuid(self.record_id, _("Record ID"))
        self.actor_key_hash = validate_hash(self.actor_key_hash, _("Actor Key Hash"))
        self.payload_hash = validate_hash(self.payload_hash, _("Payload Hash"))
        response, self.response_json = canonical_json(self.response_json, _("Response JSON"), dict)
        if not self.actor or not self.tenant_id or self.operation not in self._OPERATIONS:
            frappe.throw(_("Idempotency identity is invalid."), frappe.ValidationError)
        previous = self.get_doc_before_save()
        if previous is None:
            if self.response_sealed or response:
                frappe.throw(_("An idempotency response must be sealed after success."), frappe.ValidationError)
            return
        immutable_fields(
            self,
            ("record_id", "actor", "tenant_id", "operation", "actor_key_hash", "payload_hash"),
        )
        if previous.response_sealed or self.response_sealed != 1 or not response:
            frappe.throw(_("A sealed idempotency response cannot be changed."), frappe.PermissionError)
