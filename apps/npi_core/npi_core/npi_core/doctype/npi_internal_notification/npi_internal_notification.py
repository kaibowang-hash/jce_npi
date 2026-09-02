from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.collaboration.domain import NOTIFICATION_TITLE_SOURCES, NotificationKind, utc_text
from npi_core.collaboration.frappe_validation import (
    canonical_json,
    deny_collaboration_delete,
    immutable_fields,
    increment_version,
    require_collaboration_write,
    validate_hash,
    validate_uuid,
)


class NPIInternalNotification(Document):
    _KINDS = {"due_reminder", "overdue_escalation", "critical_blocker", "gate_attention"}
    _EMAIL_STATES = {"not_requested", "queued", "failed", "unavailable"}
    _SOURCE_TYPES = {
        "domain_work_item",
        "gate_review_assignment",
        "gate_review_invalidation",
    }
    _IDENTITY = (
        "global_id",
        "delivery_key_hash",
        "tenant_id",
        "recipient_user_id",
        "project_global_id",
        "source_type",
        "source_global_id",
        "source_version",
        "notification_kind",
        "critical_audit",
        "title_source",
        "message_parameters",
        "target_route",
        "source_due_at",
    )

    def before_insert(self) -> None:
        require_collaboration_write()

    def before_save(self) -> None:
        require_collaboration_write()

    def on_trash(self) -> None:
        deny_collaboration_delete()

    def validate(self) -> None:
        self.global_id = validate_uuid(self.global_id, _("Global ID"))
        self.project_global_id = validate_uuid(self.project_global_id, _("Project Global ID"))
        self.source_global_id = validate_uuid(self.source_global_id, _("Source Global ID"))
        self.delivery_key_hash = validate_hash(self.delivery_key_hash, _("Delivery Key Hash"))
        parameters, self.message_parameters = canonical_json(
            self.message_parameters,
            _("Message Parameters"),
            dict,
        )
        if self.notification_kind not in self._KINDS or self.email_delivery_state not in self._EMAIL_STATES:
            frappe.throw(_("Select a supported notification state."), frappe.ValidationError)
        if not self.tenant_id or not self.recipient_user_id or self.source_type not in self._SOURCE_TYPES:
            frappe.throw(_("Notification identity is required."), frappe.ValidationError)
        expected_route = f"/projects/{self.project_global_id}"
        if not isinstance(self.target_route, str) or not self.target_route.startswith(expected_route):
            frappe.throw(_("Notification target must stay inside its Project."), frappe.ValidationError)
        kind = NotificationKind(self.notification_kind)
        if self.title_source != NOTIFICATION_TITLE_SOURCES[kind]:
            frappe.throw(_("Notification title does not match its type."), frappe.ValidationError)
        critical = self.notification_kind == "critical_blocker"
        if bool(self.critical_audit) != critical:
            frappe.throw(_("Critical blocker notifications cannot be disabled."), frappe.ValidationError)
        if not self.source_due_at or int(self.source_version or 0) < 1:
            frappe.throw(_("Notification source version and due time are required."), frappe.ValidationError)
        due_at = frappe.utils.get_datetime(self.source_due_at)
        if due_at.tzinfo is None:
            from datetime import UTC

            due_at = due_at.replace(tzinfo=UTC)
        if set(parameters) != {"dueAt"} or parameters["dueAt"] != utc_text(due_at):
            frappe.throw(_("Notification message does not match its source."), frappe.ValidationError)
        if self.email_delivery_state in {"not_requested", "queued"} and self.failure_code:
            frappe.throw(_("Notification email state is inconsistent."), frappe.ValidationError)
        if self.email_delivery_state == "failed" and not self.failure_code:
            frappe.throw(_("Notification email failure requires a code."), frappe.ValidationError)
        immutable_fields(self, self._IDENTITY)
        increment_version(self)
