from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_work.frappe_validation import (
    advance_version,
    deny_project_work_history_delete,
    normalize_uuid_fields,
    require_project_work_command_write,
    validate_key,
    validate_project_identity,
)


class NPIProjectRACIAssignment(Document):
    _RESPONSIBILITIES = frozenset(
        {"responsible", "accountable", "consulted", "informed"}
    )
    _CONTEXT_TYPES = frozenset({"project", "wbs_item", "domain_work_item"})

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
            ("context_global_id", "role_assignment_global_id"),
        )
        if self.context_type not in self._CONTEXT_TYPES:
            frappe.throw(
                _("Select a supported RACI context type."),
                frappe.ValidationError,
            )
        if self.responsibility not in self._RESPONSIBILITIES:
            frappe.throw(
                _("Select a supported RACI responsibility."),
                frappe.ValidationError,
            )
        self.responsibility_key = validate_key(
            self.responsibility_key,
            _("Responsibility Key"),
        )
        advance_version(
            self,
            immutable_fields=(
                "global_id",
                "tenant_id",
                "project_global_id",
                "context_type",
                "context_global_id",
                "responsibility_key",
                "role_assignment_global_id",
                "responsibility",
            ),
        )
