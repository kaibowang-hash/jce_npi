from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    lowercase_sha256,
)
from npi_core.tooling.domain import sha256_json
from npi_core.tooling.export_domain import (
    ToolingExportOperation,
    tooling_export_receipt_key_hash,
)
from npi_core.tooling.export_frappe_validation import (
    canonical_export_uuid,
    deny_tooling_export_delete,
    require_tooling_export_write,
)


_IDENTITY_FIELDS = (
    "global_id", "receipt_key_hash", "tenant_id", "project_global_id",
    "actor_user_id", "operation", "idempotency_key_hash", "payload_hash",
    "created_at", "request_id", "trace_id",
)


class NPIToolingExportCommandIdempotency(Document):
    def autoname(self) -> None:
        canonical_export_uuid(self, "global_id", _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_export_write()

    def before_save(self) -> None:
        require_tooling_export_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_id", _("Request ID")),
        ):
            canonical_export_uuid(self, fieldname, label)

    def validate(self) -> None:
        self.receipt_key_hash = lowercase_sha256(
            self.receipt_key_hash,
            _("Receipt Key Hash"),
        )
        self.idempotency_key_hash = lowercase_sha256(
            self.idempotency_key_hash,
            _("Idempotency Key Hash"),
        )
        self.payload_hash = lowercase_sha256(self.payload_hash, _("Payload Hash"))
        if self.operation not in {item.value for item in ToolingExportOperation}:
            frappe.throw(_("Select a supported Tooling export operation."), frappe.ValidationError)
        expected_receipt_key = tooling_export_receipt_key_hash(
            tenant_id=self.tenant_id,
            project_global_id=self.project_global_id,
            actor_user_id=self.actor_user_id,
            operation=ToolingExportOperation(self.operation),
            idempotency_key_hash=self.idempotency_key_hash,
        )
        if self.receipt_key_hash != expected_receipt_key:
            frappe.throw(
                _("The Tooling export receipt key does not match."),
                frappe.ValidationError,
            )
        previous = self.get_doc_before_save()
        if previous is None:
            if self.sealed or any(
                getattr(self, fieldname)
                for fieldname in (
                    "target_doctype", "target_global_id", "response_snapshot",
                    "response_hash", "sealed_at",
                )
            ):
                frappe.throw(
                    _("A new Tooling export receipt must be unsealed."),
                    frappe.ValidationError,
                )
            return
        assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        if previous.sealed:
            frappe.throw(_("Tooling export receipts are immutable after sealing."), frappe.PermissionError)
        if not self.sealed or not all(
            getattr(self, fieldname)
            for fieldname in (
                "target_doctype", "target_global_id", "response_snapshot",
                "response_hash", "sealed_at",
            )
        ):
            frappe.throw(
                _("A Tooling export receipt can only advance once to a complete sealed response."),
                frappe.ValidationError,
            )
        if self.target_doctype != "NPI Tooling Export Package":
            frappe.throw(
                _("The Tooling export receipt target is unsupported."),
                frappe.ValidationError,
            )
        canonical_export_uuid(self, "target_global_id", _("Target Global ID"))
        response = frappe.parse_json(self.response_snapshot)
        expected_hash = sha256_json(response)
        if self.response_hash not in ("", expected_hash):
            frappe.throw(_("Tooling export response hash does not match."), frappe.ValidationError)
        self.response_snapshot = canonical_json(response)
        self.response_hash = lowercase_sha256(expected_hash, _("Response Hash"))

    def on_trash(self) -> None:
        deny_tooling_export_delete(self)
