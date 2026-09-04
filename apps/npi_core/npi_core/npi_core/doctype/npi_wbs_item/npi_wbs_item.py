from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_work.frappe_validation import (
    advance_version,
    deny_project_work_history_delete,
    normalize_uuid_fields,
    require_project_work_command_write,
    validate_date_bounds,
    validate_hash,
    validate_key,
    validate_project_identity,
)


class NPIWBSItem(Document):
    def before_insert(self) -> None:
        require_project_work_command_write()

    def before_save(self) -> None:
        require_project_work_command_write()

    def on_trash(self) -> None:
        deny_project_work_history_delete()

    def validate(self) -> None:
        validate_project_identity(self)
        normalize_uuid_fields(
            self,
            (
                "parent_global_id",
                "owner_role_assignment_global_id",
                "work_policy_global_id",
            ),
        )
        if self.parent_global_id == self.global_id:
            frappe.throw(
                _("A WBS item cannot be its own parent."),
                frappe.ValidationError,
            )
        self.status_key = validate_key(self.status_key, _("Status Key"))
        self.work_policy_snapshot_hash = validate_hash(
            self.work_policy_snapshot_hash,
            _("Work Policy Snapshot Hash"),
        )
        if type(self.work_policy_version) is not int or self.work_policy_version < 1:
            frappe.throw(
                _("Work Policy Version must be greater than zero."),
                frappe.ValidationError,
            )
        if type(self.plan_revision) is not int or self.plan_revision < 1:
            frappe.throw(
                _("Work Plan Revision must be greater than zero."),
                frappe.ValidationError,
            )
        if (
            type(self.progress_percent) is not int
            or self.progress_percent < 0
            or self.progress_percent > 100
        ):
            frappe.throw(
                _("Progress Percent must be between zero and one hundred."),
                frappe.ValidationError,
            )
        validate_date_bounds(
            self.planned_start,
            self.planned_end,
            start_label=_("Planned Start"),
            end_label=_("Planned End"),
        )
        validate_date_bounds(
            self.actual_start,
            self.actual_end,
            start_label=_("Actual Start"),
            end_label=_("Actual End"),
        )
        advance_version(
            self,
            immutable_fields=(
                "global_id",
                "tenant_id",
                "project_global_id",
                "wbs_code",
            ),
        )
