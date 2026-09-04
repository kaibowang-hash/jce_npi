from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_controls.frappe_validation import (
    canonicalize_json,
    deny_project_control_history_delete,
    normalize_uuid_fields,
    require_actor,
    require_hash,
    require_project_control_write,
)


class NPIProjectControlIdempotency(Document):
    _IMMUTABLE_FIELDS = (
        "record_id",
        "actor",
        "tenant_id",
        "project_global_id",
        "operation",
        "actor_key_hash",
        "payload_hash",
    )

    def before_insert(self) -> None:
        require_project_control_write()

    def before_save(self) -> None:
        require_project_control_write()

    def on_trash(self) -> None:
        deny_project_control_history_delete()

    def validate(self) -> None:
        normalize_uuid_fields(self, ("record_id", "project_global_id"))
        self.actor = require_actor(self.actor, _("Actor"))
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        if (
            not isinstance(self.operation, str)
            or not self.operation
            or len(self.operation) > 64
        ):
            frappe.throw(
                _("Operation must be a valid controlled key."),
                frappe.ValidationError,
            )
        self.actor_key_hash = require_hash(
            self.actor_key_hash,
            _("Actor Key Hash"),
        )
        self.payload_hash = require_hash(
            self.payload_hash,
            _("Payload Hash"),
        )
        response, self.response_json = canonicalize_json(
            self.response_json,
            expected_type=dict,
            label=_("Response JSON"),
        )
        previous = self.get_doc_before_save()
        if previous is None:
            if int(self.response_sealed or 0) != 0 or response:
                frappe.throw(
                    _(
                        "A Project control idempotency response must be sealed after the command succeeds."
                    ),
                    frappe.ValidationError,
                )
            return
        for fieldname in self._IMMUTABLE_FIELDS:
            if self.get(fieldname) != previous.get(fieldname):
                frappe.throw(
                    _("A protected field cannot be changed."),
                    frappe.ValidationError,
                )
        if (
            int(previous.response_sealed or 0) != 0
            or int(self.response_sealed or 0) != 1
            or not response
        ):
            frappe.throw(
                _(
                    "A Project control idempotency response can only be sealed once."
                ),
                frappe.PermissionError,
            )
