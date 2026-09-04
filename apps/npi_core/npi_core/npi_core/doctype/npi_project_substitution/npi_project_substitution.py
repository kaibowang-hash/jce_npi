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
    validate_project_identity,
)


class NPIProjectSubstitution(Document):
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
            ("role_assignment_global_id", "substitute_member_global_id"),
        )
        if not self.effective_to:
            frappe.throw(
                _("Effective To is required for a substitution."),
                frappe.ValidationError,
            )
        validate_date_bounds(
            self.effective_from,
            self.effective_to,
            start_label=_("Effective From"),
            end_label=_("Effective To"),
        )
        advance_version(
            self,
            immutable_fields=(
                "global_id",
                "tenant_id",
                "project_global_id",
                "role_assignment_global_id",
                "substitute_member_global_id",
            ),
        )
