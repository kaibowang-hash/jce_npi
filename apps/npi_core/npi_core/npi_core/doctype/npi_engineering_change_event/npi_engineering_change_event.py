from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.change_control.frappe_validation import (
    assert_immutable_fields, canonical_json, canonical_uuid, deny_change_history_delete,
    deny_change_history_update, lowercase_sha256, positive_integer, required_text,
    require_change_command_write, sha256_json,
    utc_datetime_text,
)


_ALL_FIELDS = (
    "global_id", "change_global_id", "tenant_id", "project_global_id",
    "revision_global_id", "revision",
    "revision_snapshot_hash", "event_type", "actor_user_id", "occurred_at",
    "request_id", "trace_id", "event_snapshot", "event_hash",
)
_EVENTS = frozenset({"created", "revised", "formal_observation_linked", "ready_to_close", "closed", "cancelled"})


class NPIEngineeringChangeEvent(Document):
    """Append-only audit event for one exact change revision."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_change_command_write()

    def before_save(self) -> None:
        require_change_command_write()
        if self.get_doc_before_save() is not None:
            deny_change_history_update()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_change_history_update()
        for fieldname, label in (
            ("global_id", _("Global ID")), ("change_global_id", _("Engineering Change Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("revision_global_id", _("Revision Global ID")), ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.revision = positive_integer(self.revision, _("Revision"))
        self.tenant_id = required_text(self.tenant_id, _("Tenant ID"))
        self.revision_snapshot_hash = lowercase_sha256(self.revision_snapshot_hash, _("Revision Snapshot Hash"))
        self.event_hash = lowercase_sha256(self.event_hash, _("Engineering Change Event Hash"))
        if self.event_type not in _EVENTS:
            frappe.throw(_("Select a supported engineering change event type."), frappe.ValidationError)
        self.actor_user_id = required_text(self.actor_user_id, _("Actor User ID"), 254)
        self.trace_id = required_text(self.trace_id, _("Trace ID"))
        snapshot, self.event_snapshot = canonical_json(self.event_snapshot, _("Canonical Engineering Change Event Snapshot"), dict)
        expected = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "changeGlobalId": self.change_global_id,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "revisionGlobalId": self.revision_global_id,
            "revision": self.revision,
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "eventType": self.event_type,
            "actorUserId": self.actor_user_id,
            "occurredAt": utc_datetime_text(self.occurred_at, _("Occurred At")),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        if snapshot != expected or sha256_json(snapshot) != self.event_hash:
            frappe.throw(_("The engineering change event hash does not match."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_change_history_delete(self)
