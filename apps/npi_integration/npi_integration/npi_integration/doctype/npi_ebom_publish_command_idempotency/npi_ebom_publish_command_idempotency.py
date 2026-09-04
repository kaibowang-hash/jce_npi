from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_integration.publish_request.domain import sha256_json
from npi_integration.publish_request.frappe_validation import (
    deny_publish_history_delete,
    require_publish_request_write,
)


class NPIEBOMPublishCommandIdempotency(Document):
    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_publish_request_write()

    def before_save(self) -> None:
        require_publish_request_write()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.project_global_id = canonical_uuid(
            self.project_global_id, _("Project Global ID")
        )
        self.request_global_id = optional_uuid(
            self.request_global_id, _("Publish Request Global ID")
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        self.receipt_key = required_text(
            self.receipt_key, _("Receipt Key"), maximum=255
        )
        self.actor_user_id = required_text(
            self.actor_user_id, _("Actor User ID"), maximum=254
        )
        if self.operation != "ebom.publish_request.create":
            frappe.throw(
                _("Select the operation-specific EBOM publish command."),
                frappe.ValidationError,
            )
        self.idempotency_key_hash = lowercase_sha256(
            self.idempotency_key_hash, _("Idempotency Key Hash")
        )
        self.payload_hash = lowercase_sha256(
            self.payload_hash, _("Publish Request Payload Hash")
        )
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        utc_datetime_text(self.updated_at, _("Updated At"))
        before = self.get_doc_before_save()
        if before is not None:
            immutable = (
                "global_id",
                "receipt_key",
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
            )
            before_created_at = utc_datetime_text(
                before.created_at, _("Created At")
            )
            if (
                any(
                    getattr(before, name) != getattr(self, name)
                    for name in immutable
                )
                or before_created_at != created_at
            ):
                frappe.throw(
                    _("The publish command receipt identity cannot be changed."),
                    frappe.PermissionError,
                )
            if int(before.sealed or 0) == 1:
                frappe.throw(
                    _("A sealed publish command receipt cannot be changed."),
                    frappe.PermissionError,
                )
        if self.sealed:
            if not self.request_global_id or not self.response_payload or not self.response_hash:
                frappe.throw(
                    _("A sealed publish command receipt requires its exact response."),
                    frappe.ValidationError,
                )
            request = require_exact_parent(
                "NPI EBOM Publish Request",
                self.request_global_id,
                {
                    "global_id": self.request_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "actor_user_id": self.actor_user_id,
                },
                _("The sealed publish request is unavailable."),
                extra_fields=("payload_hash",),
            )
            response = json_object(
                self.response_payload, _("Sealed Response Payload")
            )
            if (
                response.get("globalId") != self.request_global_id
                or response.get("payloadHash") != str(request.payload_hash)
            ):
                frappe.throw(
                    _("The sealed response does not match its exact publish request."),
                    frappe.ValidationError,
                )
            canonical = canonical_json(response)
            if lowercase_sha256(self.response_hash, _("Sealed Response Hash")) != sha256_json(response):
                frappe.throw(
                    _("The sealed response hash does not match its payload."),
                    frappe.ValidationError,
                )
            self.response_payload = canonical
        elif self.request_global_id or self.response_payload or self.response_hash:
            frappe.throw(
                _("An unsealed publish command receipt cannot contain a response."),
                frappe.ValidationError,
            )

    def on_trash(self) -> None:
        deny_publish_history_delete(self, target_global_id=self.global_id)
