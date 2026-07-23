from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_work.frappe_validation import (
    deny_project_work_history_delete,
    normalize_uuid_fields,
    require_project_work_command_write,
    validate_hash,
)
from npi_core.project.frappe_validation import assert_immutable_fields


class NPIProjectWorkIdempotency(Document):
    def before_insert(self) -> None:
        require_project_work_command_write()

    def before_save(self) -> None:
        require_project_work_command_write()

    def on_trash(self) -> None:
        deny_project_work_history_delete()

    def validate(self) -> None:
        normalize_uuid_fields(self, ("record_id", "project_global_id"))
        self.actor_key_hash = validate_hash(
            self.actor_key_hash,
            _("Actor Key Hash"),
        )
        self.payload_hash = validate_hash(
            self.payload_hash,
            _("Payload Hash"),
        )
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
        )
        previous = self.get_doc_before_save()
        if previous is None:
            if int(self.response_sealed or 0) != 0 or response:
                frappe.throw(
                    _("A Project work idempotency response must be sealed after the command succeeds."),
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
            deny_project_work_history_delete()
