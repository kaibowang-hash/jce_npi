from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_integration.project_publish.domain import EVENT_TYPE, parse_uuid, restore_source
from npi_integration.project_publish.frappe_validation import (
    deny_project_publish_delete,
    require_project_publish_write,
)


_IMMUTABLE = (
    "global_id", "event_type", "tenant_id", "project_global_id", "source_version",
    "source_snapshot", "source_hash", "target_idempotency_key_hash", "actor_user_id",
    "trace_id", "created_at",
)
_TRANSITIONS = {
    "pending": {"processing", "failed_final"},
    "processing": {"pending", "succeeded", "failed_retryable", "failed_final", "uncertain"},
    "failed_retryable": {"processing", "failed_final"},
    "uncertain": {"processing", "failed_final"},
    "succeeded": set(),
    "failed_final": set(),
}


class NPIERPProjectPublishRequest(Document):
    def autoname(self) -> None:
        self.global_id = parse_uuid(self.global_id, "globalId")
        self.name = self.global_id

    def before_insert(self) -> None:
        require_project_publish_write()

    def before_save(self) -> None:
        require_project_publish_write()

    def on_trash(self) -> None:
        deny_project_publish_delete()

    def validate(self) -> None:
        self.global_id = parse_uuid(self.global_id, "globalId")
        self.project_global_id = parse_uuid(self.project_global_id, "projectGlobalId")
        if self.event_type != EVENT_TYPE or self.state not in _TRANSITIONS:
            frappe.throw(_("ERP Project publication request is invalid."), frappe.ValidationError)
        source = restore_source(self.source_snapshot, expected_hash=self.source_hash)
        if source.project_global_id != self.project_global_id or source.tenant_id != self.tenant_id or source.actor_user_id != self.actor_user_id or source.source_version != int(self.source_version):
            frappe.throw(_("ERP Project publication source does not match the request."), frappe.ValidationError)
        if source.target_idempotency_key_hash != self.target_idempotency_key_hash:
            frappe.throw(_("ERP Project publication idempotency identity does not match."), frappe.ValidationError)
        previous = self.get_doc_before_save()
        if previous is not None:
            for fieldname in _IMMUTABLE:
                if self.get(fieldname) != previous.get(fieldname):
                    frappe.throw(_("ERP Project publication request identity is immutable."), frappe.ValidationError)
            if self.state != previous.state and self.state not in _TRANSITIONS[str(previous.state)]:
                frappe.throw(_("ERP Project publication state transition is invalid."), frappe.ValidationError)
            if int(self.attempt_count or 0) < int(previous.attempt_count or 0):
                frappe.throw(_("ERP Project publication attempt count cannot decrease."), frappe.ValidationError)
