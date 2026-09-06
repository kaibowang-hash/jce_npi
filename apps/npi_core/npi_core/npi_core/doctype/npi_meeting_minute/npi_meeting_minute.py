from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.collaboration.domain import STANDARD_MEETING_TEMPLATE, STANDARD_MEETING_TEMPLATE_HASH, canonical_hash
from npi_core.collaboration.frappe_validation import (
    canonical_json,
    deny_collaboration_delete,
    require_collaboration_write,
    validate_hash,
    validate_uuid,
)


class NPIMeetingMinute(Document):
    _EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

    def before_insert(self) -> None:
        require_collaboration_write()

    def before_save(self) -> None:
        require_collaboration_write()
        if not self.is_new():
            frappe.throw(_("Meeting minutes are immutable."), frappe.PermissionError)

    def on_trash(self) -> None:
        deny_collaboration_delete()

    def validate(self) -> None:
        self.global_id = validate_uuid(self.global_id, _("Global ID"))
        self.project_global_id = validate_uuid(self.project_global_id, _("Project Global ID"))
        self.template_global_id = validate_uuid(self.template_global_id, _("Template Global ID"))
        if (
            self.template_global_id != STANDARD_MEETING_TEMPLATE["globalId"]
            or self.template_version != STANDARD_MEETING_TEMPLATE["version"]
            or self.template_snapshot_hash != STANDARD_MEETING_TEMPLATE_HASH
        ):
            frappe.throw(_("Select the supported meeting template."), frappe.ValidationError)
        attendees, self.attendee_user_ids = canonical_json(self.attendee_user_ids, _("Meeting Attendees"), list)
        sections, self.sections = canonical_json(self.sections, _("Meeting Sections"), dict)
        if (
            not attendees
            or len(attendees) > 100
            or any(
                not isinstance(value, str)
                or value != value.strip().casefold()
                or self._EMAIL.fullmatch(value) is None
                for value in attendees
            )
            or len(attendees) != len(set(attendees))
        ):
            frappe.throw(_("Select 1 to 100 unique meeting attendees."), frappe.ValidationError)
        if set(sections) != set(STANDARD_MEETING_TEMPLATE["sectionKeys"]):
            frappe.throw(_("Complete every meeting template section."), frappe.ValidationError)
        if any(
            not isinstance(value, str) or not value.strip() or len(value) > 8_000
            for value in sections.values()
        ):
            frappe.throw(_("Complete every meeting template section."), frappe.ValidationError)
        if (
            not isinstance(self.title, str)
            or self.title != " ".join(self.title.split())
            or len(self.title) > 280
        ):
            frappe.throw(_("Enter a valid value."), frappe.ValidationError)
        if not self.occurred_at or not self.tenant_id or not self.created_by:
            frappe.throw(_("Meeting identity and time are required."), frappe.ValidationError)
        self.template_snapshot_hash = validate_hash(self.template_snapshot_hash, _("Template Snapshot Hash"))
        self.content_hash = validate_hash(self.content_hash, _("Content Hash"))
        occurred_at = frappe.utils.get_datetime(self.occurred_at)
        if occurred_at.tzinfo is None:
            from datetime import UTC

            occurred_at = occurred_at.replace(tzinfo=UTC)
        content = {
            "schemaVersion": 1,
            "templateRef": {
                "globalId": self.template_global_id,
                "version": self.template_version,
                "snapshotHash": self.template_snapshot_hash,
            },
            "title": self.title,
            "occurredAt": occurred_at.isoformat().replace("+00:00", "Z"),
            "attendeeUserIds": attendees,
            "sections": sections,
        }
        if canonical_hash(content) != self.content_hash:
            frappe.throw(_("Meeting content does not match its hash."), frappe.ValidationError)
        if self.optimistic_version != 1:
            frappe.throw(_("Meeting minutes start at version one."), frappe.ValidationError)
