from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_work.frappe_validation import (
    advance_version,
    deny_project_work_history_delete,
    normalize_uuid_fields,
    require_project_work_command_write,
    validate_project_identity,
)


class NPIWBSDependency(Document):
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
            ("predecessor_global_id", "successor_global_id"),
        )
        if self.predecessor_global_id == self.successor_global_id:
            frappe.throw(
                _("A WBS dependency cannot reference the same item twice."),
                frappe.ValidationError,
            )
        if type(self.plan_revision) is not int or self.plan_revision < 1:
            frappe.throw(
                _("Work Plan Revision must be greater than zero."),
                frappe.ValidationError,
            )
        advance_version(
            self,
            immutable_fields=(
                "global_id",
                "tenant_id",
                "project_global_id",
                "predecessor_global_id",
                "successor_global_id",
            ),
        )
