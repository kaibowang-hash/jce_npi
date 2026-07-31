from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    frappe_utc_datetime_text,
    json_object,
    key_text,
    lowercase_sha256,
    optional_uuid,
    required_text,
    require_exact_parent,
    require_document_command_write,
    tenant_text,
)


_IDENTITY_FIELDS = (
    "record_id",
    "actor",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "operation",
    "actor_key_hash",
    "payload_hash",
    "request_id",
    "trace_id",
    "created_at",
)
_OPERATIONS = {
    "document.create",
    "document.lock.acquire",
    "document.lock.release",
    "document.lock.recover",
    "document.revision.create",
    "document.content",
    "document.review.submit",
    "document.review.resubmit",
    "document.review.approve",
    "document.review.reject",
    "document.release",
    "document.supersede",
    "document.obsolete",
}


class NPIDocumentCommandIdempotency(Document):
    """Actor-bound command receipt that can be sealed exactly once."""

    def autoname(self) -> None:
        self.record_id = canonical_uuid(self.record_id, _("Record ID"))
        self.name = self.record_id

    def before_insert(self) -> None:
        require_document_command_write()

    def before_save(self) -> None:
        require_document_command_write()

    def before_validate(self) -> None:
        self.record_id = canonical_uuid(self.record_id, _("Record ID"))
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.document_global_id = optional_uuid(
            self.document_global_id,
            _("Document Global ID"),
        )

    def validate(self) -> None:
        self.actor = actor_text(self.actor, _("Actor"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.operation = key_text(self.operation, _("Operation"))
        if self.operation not in _OPERATIONS:
            frappe.throw(
                _("Select a supported document command operation."),
                frappe.ValidationError,
            )
        if (
            self.operation == "document.create" and self.document_global_id is not None
        ) or (self.operation != "document.create" and self.document_global_id is None):
            frappe.throw(
                _("Document Global ID does not match the command operation."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {
                "global_id": self.project_global_id,
                "tenant_id": self.tenant_id,
            },
            _("The document command receipt does not match its Project and tenant."),
        )
        if self.document_global_id:
            require_exact_parent(
                "NPI Controlled Document",
                self.document_global_id,
                {
                    "global_id": self.document_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                },
                _(
                    "The document command receipt does not match its controlled document."
                ),
            )
        self.actor_key_hash = lowercase_sha256(
            self.actor_key_hash,
            _("Actor Key Hash"),
        )
        self.payload_hash = lowercase_sha256(
            self.payload_hash,
            _("Payload Hash"),
        )
        self.request_id = required_text(
            self.request_id,
            _("Request ID"),
            128,
        )
        self.trace_id = required_text(
            self.trace_id,
            _("Trace ID"),
            128,
        )
        self.created_at = frappe_utc_datetime_text(
            self.created_at,
            _("Created At"),
        )
        response = json_object(
            self.response_snapshot,
            _("Response Snapshot"),
        )
        self.response_snapshot = canonical_json(response)
        previous = self.get_doc_before_save()
        if previous is None:
            if int(self.response_sealed or 0) != 0 or response:
                frappe.throw(
                    _(
                        "A document command response must be sealed after the command succeeds."
                    ),
                    frappe.ValidationError,
                )
            return
        assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        if (
            int(previous.get("response_sealed") or 0) != 0
            or int(self.response_sealed or 0) != 1
            or not response
        ):
            frappe.throw(
                _("A document command response can only be sealed once."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.record_id,
            target_version=1,
        )
