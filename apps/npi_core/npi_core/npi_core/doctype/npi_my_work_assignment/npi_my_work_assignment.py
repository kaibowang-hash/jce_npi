from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_controls.frappe_validation import (
    canonical_datetime,
    canonicalize_json,
    deny_my_work_projection_delete,
    normalize_uuid_fields,
    require_actor,
    require_positive_integer,
    require_snapshot_hash,
    require_my_work_projection_write,
)


_SOURCE_TYPES = {
    "domain_work_item",
    "gate_review_assignment",
    "gate_review_invalidation",
}
_ASSIGNMENT_CODES = {
    "domain_work_item_owner",
    "gate_review_step",
    "gate_final_decision",
    "gate_reopen",
    "gate_exception",
    "gate_dependency_change",
}
_CATEGORIES = {"task", "approval", "blocker", "risk", "issue", "decision"}


class NPIMyWorkAssignment(Document):
    _IDENTITY_FIELDS = (
        "global_id",
        "assignment_key",
        "tenant_id",
        "actor_user_id",
        "project_global_id",
        "source_type",
        "source_global_id",
    )

    def before_insert(self) -> None:
        require_my_work_projection_write()

    def before_save(self) -> None:
        require_my_work_projection_write()

    def on_trash(self) -> None:
        deny_my_work_projection_delete()

    def validate(self) -> None:
        normalize_uuid_fields(
            self,
            ("global_id", "project_global_id", "source_global_id"),
        )
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        self.actor_user_id = require_actor(
            self.actor_user_id,
            _("Assigned User ID"),
        )
        if (
            not isinstance(self.assignment_key, str)
            or not self.assignment_key
            or len(self.assignment_key) > 500
        ):
            frappe.throw(
                _("My Work Assignment Key must be valid."),
                frappe.ValidationError,
            )
        if self.source_type not in _SOURCE_TYPES:
            frappe.throw(
                _("Select a supported My Work source type."),
                frappe.ValidationError,
            )
        require_positive_integer(self.source_version, _("Source Version"))
        if self.assignment_code not in _ASSIGNMENT_CODES:
            frappe.throw(
                _("Select a supported assignment reason."),
                frappe.ValidationError,
            )
        if self.category not in _CATEGORIES:
            frappe.throw(
                _("Select a supported My Work category."),
                frappe.ValidationError,
            )
        _validate_source_mapping(
            self.source_type,
            self.assignment_code,
            self.category,
        )
        _validate_priority(self.priority_scheme, self.priority_value)
        if type(self.blocking) not in {bool, int} or int(self.blocking) not in {
            0,
            1,
        }:
            frappe.throw(
                _("Blocking must be a valid true or false value."),
                frappe.ValidationError,
            )
        if type(self.active) not in {bool, int} or int(self.active) not in {0, 1}:
            frappe.throw(
                _("Active must be a valid true or false value."),
                frappe.ValidationError,
            )
        self.blocking = int(self.blocking)
        self.active = int(self.active)
        snapshot, self.source_snapshot = canonicalize_json(
            self.source_snapshot,
            expected_type=dict,
            label=_("My Work Source Snapshot"),
        )
        self.snapshot_hash = require_snapshot_hash(
            snapshot,
            self.snapshot_hash,
            _("Snapshot Hash"),
        )
        required = {
            "schemaVersion",
            "assignmentGlobalId",
            "assignmentKey",
            "tenantId",
            "actorUserId",
            "projectGlobalId",
            "sourceType",
            "sourceGlobalId",
            "sourceVersion",
            "assignmentCode",
            "category",
            "dueAt",
            "priority",
            "blocking",
            "active",
            "sourceDetail",
        }
        if set(snapshot) != required:
            frappe.throw(
                _("My Work Source Snapshot has an invalid structure."),
                frappe.ValidationError,
            )
        priority = (
            None
            if not self.priority_scheme
            else {
                "scheme": self.priority_scheme,
                "value": self.priority_value,
            }
        )
        snapshot_due_at = snapshot["dueAt"]
        persisted_due_at = (
            canonical_datetime(self.due_at, _("Due At"))
            if self.due_at
            else None
        )
        if snapshot_due_at is not None:
            snapshot_due_at = canonical_datetime(
                snapshot_due_at,
                _("Due At"),
            )
        canonical_datetime(self.indexed_at, _("Indexed At"))
        if (
            snapshot["schemaVersion"] != 1
            or snapshot["assignmentGlobalId"] != self.global_id
            or snapshot["assignmentKey"] != self.assignment_key
            or snapshot["tenantId"] != self.tenant_id
            or str(snapshot["actorUserId"]).casefold() != self.actor_user_id
            or snapshot["projectGlobalId"] != self.project_global_id
            or snapshot["sourceType"] != self.source_type
            or snapshot["sourceGlobalId"] != self.source_global_id
            or snapshot["sourceVersion"] != self.source_version
            or snapshot["assignmentCode"] != self.assignment_code
            or snapshot["category"] != self.category
            or snapshot_due_at != persisted_due_at
            or snapshot["priority"] != priority
            or snapshot["blocking"] is not bool(self.blocking)
            or snapshot["active"] is not bool(self.active)
            or not isinstance(snapshot["sourceDetail"], dict)
        ):
            frappe.throw(
                _("My Work Source Snapshot does not match the assignment."),
                frappe.ValidationError,
            )
        previous = self.get_doc_before_save()
        if previous is not None:
            for fieldname in self._IDENTITY_FIELDS:
                if self.get(fieldname) != previous.get(fieldname):
                    frappe.throw(
                        _("A protected field cannot be changed."),
                        frappe.ValidationError,
                    )


def _validate_source_mapping(
    source_type: str,
    assignment_code: str,
    category: str,
) -> None:
    valid = bool(
        (
            source_type == "domain_work_item"
            and assignment_code == "domain_work_item_owner"
            and category in {"task", "risk", "issue", "decision"}
        )
        or (
            source_type == "gate_review_assignment"
            and assignment_code
            in {
                "gate_review_step",
                "gate_final_decision",
                "gate_reopen",
                "gate_exception",
            }
            and category == "approval"
        )
        or (
            source_type == "gate_review_invalidation"
            and assignment_code == "gate_dependency_change"
            and category == "blocker"
        )
    )
    if not valid:
        frappe.throw(
            _("My Work source, reason, and category do not match."),
            frappe.ValidationError,
        )


def _validate_priority(scheme: object, value: object) -> None:
    if not scheme and not value:
        return
    valid = bool(
        (scheme == "domain_severity" and value in {"low", "medium", "high", "critical"})
        or (
            scheme == "gate_requirement_priority"
            and value in {"P0", "P1", "P2"}
        )
    )
    if not valid:
        frappe.throw(
            _("My Work priority vocabulary and value do not match."),
            frappe.ValidationError,
        )
