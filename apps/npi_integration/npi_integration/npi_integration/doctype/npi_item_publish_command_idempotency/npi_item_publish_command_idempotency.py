from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.item_publish.domain import ITEM_PUBLISH_OPERATION, canonical_hash
from npi_integration.item_publish.frappe_validation import (
    deny_item_history_delete,
    deny_item_history_update,
    require_item_idempotency_write,
)


class NPIItemPublishCommandIdempotency(Document):
    def autoname(self) -> None:
        self.scope_key_hash = lowercase_sha256(
            self.scope_key_hash, _("Item Publish Idempotency Scope Hash")
        )
        self.name = self.scope_key_hash

    def before_insert(self) -> None:
        require_item_idempotency_write()

    def before_save(self) -> None:
        require_item_idempotency_write()
        if self.get_doc_before_save() is not None:
            deny_item_history_update()

    def before_validate(self) -> None:
        self.project_global_id = canonical_uuid(
            self.project_global_id, _("Project Global ID")
        )
        self.request_global_id = canonical_uuid(
            self.request_global_id, _("Item Publish Request")
        )
        self.tenant_id = tenant_text(self.tenant_id)
        self.actor_user_id = actor_text(self.actor_user_id, _("Actor User ID"))

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_item_history_update()
        if self.operation != ITEM_PUBLISH_OPERATION:
            frappe.throw(
                _("The Item publish idempotency operation is invalid."),
                frappe.ValidationError,
            )
        for fieldname, label in (
            ("scope_key_hash", _("Item Publish Idempotency Scope Hash")),
            ("idempotency_key_hash", _("Idempotency Key Hash")),
            ("request_payload_hash", _("Item Publish Request Payload Hash")),
            ("response_hash", _("Item Publish Sealed Response Hash")),
        ):
            setattr(self, fieldname, lowercase_sha256(getattr(self, fieldname), label))
        expected_scope_hash = canonical_hash(
            {
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "operation": self.operation,
                "actorUserId": self.actor_user_id,
                "idempotencyKeyHash": self.idempotency_key_hash,
            }
        )
        if self.scope_key_hash != expected_scope_hash:
            frappe.throw(
                _("The Item publish idempotency scope hash does not match its fields."),
                frappe.ValidationError,
            )
        response = json_object(
            self.response_snapshot, _("Item Publish Sealed Response")
        )
        if canonical_hash(response) != self.response_hash:
            frappe.throw(
                _("The Item publish sealed response hash does not match its fields."),
                frappe.ValidationError,
            )
        if response.get("requestGlobalId") != self.request_global_id:
            frappe.throw(
                _("The Item publish sealed response does not match its request."),
                frappe.ValidationError,
            )
        self.response_snapshot = canonical_json(response)
        self.created_at = frappe_utc_datetime_text(
            utc_datetime_text(self.created_at, _("Created At")), _("Created At")
        )
        required_text(self.operation, _("Item Publish Operation"), 64)

    def on_trash(self) -> None:
        deny_item_history_delete()
