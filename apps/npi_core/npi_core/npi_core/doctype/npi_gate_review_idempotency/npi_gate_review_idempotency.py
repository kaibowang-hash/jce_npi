from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.gate_review.frappe_validation import (
    assert_immutable_fields,
    deny_gate_review_history_delete,
    ensure_uuid,
    lowercase_sha256,
    require_gate_review_command_write,
    required_text,
)


class NPIGateReviewIdempotency(Document):
    """Actor-scoped command receipt sealed once in the command transaction."""

    def before_insert(self) -> None:
        require_gate_review_command_write()

    def before_save(self) -> None:
        require_gate_review_command_write()

    def on_trash(self) -> None:
        deny_gate_review_history_delete(
            self,
            target_global_id=self.record_id,
            target_version=1,
        )

    def validate(self) -> None:
        self.record_id = ensure_uuid(self.record_id, _("Record ID"))
        self.project_global_id = ensure_uuid(
            self.project_global_id, _("Project Global ID")
        )
        self.gate_global_id = ensure_uuid(self.gate_global_id, _("Gate Global ID"))
        self.actor = required_text(self.actor, _("Actor"), maximum=254)
        self.tenant_id = required_text(self.tenant_id, _("Tenant ID"), maximum=140)
        self.operation = required_text(self.operation, _("Operation"), maximum=140)
        self.actor_key_hash = lowercase_sha256(self.actor_key_hash, _("Actor Key Hash"))
        self.payload_hash = lowercase_sha256(self.payload_hash, _("Payload Hash"))
        try:
            response = (
                json.loads(self.response_json)
                if isinstance(self.response_json, str)
                else self.response_json
            )
        except (TypeError, json.JSONDecodeError):
            response = None
        if not isinstance(response, dict):
            frappe.throw(
                _("Response JSON must be a JSON object."),
                frappe.ValidationError,
            )
        self.response_json = json.dumps(
            response,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
        previous = self.get_doc_before_save()
        if previous is None:
            if int(self.response_sealed or 0) != 0 or response:
                frappe.throw(
                    _(
                        "A Gate review idempotency response must be sealed after the command succeeds."
                    ),
                    frappe.ValidationError,
                )
            return
        assert_immutable_fields(
            self,
            previous,
            (
                "record_id",
                "actor",
                "tenant_id",
                "project_global_id",
                "gate_global_id",
                "operation",
                "actor_key_hash",
                "payload_hash",
            ),
        )
        if (
            int(previous.response_sealed or 0) != 0
            or int(self.response_sealed or 0) != 1
            or not response
        ):
            deny_gate_review_history_delete()
