from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_object,
    optional_date_text,
    optional_uuid,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.tooling.domain import ToolingRequirement, ToolingRequirementKind
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingRequirement(Document):
    """Immutable Project statement of why Tooling is needed."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_command_write()

    def before_save(self) -> None:
        require_tooling_command_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.target_part_revision_global_id = optional_uuid(
            self.target_part_revision_global_id,
            _("Target Part Revision Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The Tooling Requirement does not match its Project and tenant."),
        )
        if self.target_part_revision_global_id:
            require_exact_parent(
                "NPI Engineering Part Revision",
                self.target_part_revision_global_id,
                {"tenant_id": self.tenant_id},
                _("The target Part Revision is unavailable."),
            )
        try:
            kind = ToolingRequirementKind(str(self.requirement_kind))
        except ValueError:
            frappe.throw(_("Select a supported value."), frappe.ValidationError)
            raise AssertionError("Frappe validation must raise.")
        target_date = optional_date_text(self.target_date, _("Target Date"))
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        supplied = json_object(
            self.requirement_snapshot,
            _("Tooling Requirement Snapshot"),
        )
        requirement = tooling_domain_value(
            lambda: ToolingRequirement(
                global_id=UUID(self.global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                kind=kind,
                title=self.title,
                reason=self.reason,
                target_part_revision_global_id=(
                    UUID(self.target_part_revision_global_id)
                    if self.target_part_revision_global_id
                    else None
                ),
                target_date=(
                    date.fromisoformat(target_date)
                    if target_date
                    else None
                ),
                created_by_user_id=actor_text(
                    self.created_by_user_id,
                    _("Created By User ID"),
                ),
                created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                snapshot_hash=str(self.snapshot_hash or ""),
            )
        )
        if supplied != requirement.snapshot_payload():
            frappe.throw(
                _("Tooling Requirement Snapshot does not match its exact requirement."),
                frappe.ValidationError,
            )
        self.requirement_kind = requirement.kind.value
        self.title = requirement.title
        self.reason = requirement.reason
        self.created_by_user_id = requirement.created_by_user_id
        self.created_at = frappe_utc_datetime_text(requirement.created_at, _("Created At"))
        self.trace_id = requirement.trace_id
        self.requirement_snapshot = canonical_json(requirement.snapshot_payload())
        self.snapshot_hash = requirement.snapshot_hash

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
