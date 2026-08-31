from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.change_control.frappe_validation import (
    assert_immutable_fields, canonical_json, canonical_uuid, deny_change_history_delete,
    lowercase_sha256, optional_uuid, required_text, require_change_command_write,
)


class NPIEngineeringChangeIdempotency(Document):
    """Actor-scoped command receipt sealed once with the command transaction."""

    def autoname(self) -> None:
        self.record_id = canonical_uuid(self.record_id, _("Record ID"))
        self.name = self.record_id

    def before_insert(self) -> None:
        require_change_command_write()

    def before_save(self) -> None:
        require_change_command_write()

    def validate(self) -> None:
        self.record_id = canonical_uuid(self.record_id, _("Record ID"))
        self.project_global_id = canonical_uuid(self.project_global_id, _("Project Global ID"))
        self.change_global_id = optional_uuid(self.change_global_id, _("Engineering Change Global ID"))
        self.actor_user_id = required_text(self.actor_user_id, _("Actor User ID"), 254)
        self.tenant_id = required_text(self.tenant_id, _("Tenant ID"))
        self.operation = required_text(self.operation, _("Operation"))
        self.actor_key_hash = lowercase_sha256(self.actor_key_hash, _("Actor Key Hash"))
        self.payload_hash = lowercase_sha256(self.payload_hash, _("Payload Hash"))
        response, self.response_json = canonical_json(self.response_json, _("Response JSON"), dict)
        previous = self.get_doc_before_save()
        if previous is None:
            if int(self.response_sealed or 0) != 0 or response:
                frappe.throw(_("An idempotency response must be sealed after the command succeeds."), frappe.ValidationError)
            return
        assert_immutable_fields(
            self, previous,
            ("record_id", "actor_user_id", "tenant_id", "project_global_id", "change_global_id", "operation", "actor_key_hash", "payload_hash"),
        )
        if int(previous.response_sealed or 0) != 0 or int(self.response_sealed or 0) != 1 or not response:
            frappe.throw(_("An idempotency response can only be sealed once."), frappe.PermissionError)

    def on_trash(self) -> None:
        deny_change_history_delete(self)
