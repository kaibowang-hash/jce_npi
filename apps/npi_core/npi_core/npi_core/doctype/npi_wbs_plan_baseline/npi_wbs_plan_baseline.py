from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project.frappe_validation import sha256_json
from npi_core.project_work.frappe_validation import (
    deny_project_work_history_delete,
    normalize_uuid_fields,
    require_project_work_command_write,
    validate_actor_identity,
    validate_hash,
    validate_project_identity,
)


class NPIWBSPlanBaseline(Document):
    def before_insert(self) -> None:
        require_project_work_command_write()

    def before_save(self) -> None:
        require_project_work_command_write()
        if not self.is_new():
            deny_project_work_history_delete()

    def on_trash(self) -> None:
        deny_project_work_history_delete()

    def validate(self) -> None:
        validate_project_identity(self)
        normalize_uuid_fields(self, ("work_policy_global_id",))
        self.snapshot_hash = validate_hash(
            self.snapshot_hash,
            _("Snapshot Hash"),
        )
        self.work_policy_snapshot_hash = validate_hash(
            self.work_policy_snapshot_hash,
            _("Work Policy Snapshot Hash"),
        )
        try:
            snapshot = (
                json.loads(self.snapshot)
                if isinstance(self.snapshot, str)
                else self.snapshot
            )
        except (TypeError, json.JSONDecodeError):
            snapshot = None
        if not isinstance(snapshot, dict) or sha256_json(snapshot) != self.snapshot_hash:
            frappe.throw(
                _("Plan Baseline Snapshot does not match its hash."),
                frappe.ValidationError,
            )
        self.snapshot = json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if (
            not isinstance(self.label, str)
            or not self.label.strip()
            or len(self.label) > 140
        ):
            frappe.throw(
                _("Enter a Plan Baseline label with no more than 140 characters."),
                frappe.ValidationError,
            )
        self.captured_by = validate_actor_identity(self.captured_by)
        self.optimistic_version = 1
        for value, label in (
            (self.plan_revision, _("Work Plan Revision")),
            (self.project_version, _("Project Version")),
            (self.work_policy_version, _("Work Policy Version")),
        ):
            if type(value) is not int or value < 1:
                frappe.throw(
                    _("{field} must be greater than zero.").format(
                        field=label
                    ),
                    frappe.ValidationError,
                )
