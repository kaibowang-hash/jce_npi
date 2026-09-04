from __future__ import annotations

from datetime import datetime
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
    optional_uuid,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.tooling.domain import ToolingRequirementKind, ToolingSet
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingSet(Document):
    """Immutable identity and custody provenance for one physical Set."""

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
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_requirement_global_id", _("Tooling Requirement Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.customer_source_object_id = optional_uuid(
            self.customer_source_object_id,
            _("Customer Source Object ID"),
        ) if self.customer_source_system == "NPI_ONE" else (
            str(self.customer_source_object_id or "").strip() or None
        )

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The Tooling Set does not match its Project and tenant."),
        )
        require_exact_parent(
            "NPI Tooling Master",
            self.tooling_master_global_id,
            {"global_id": self.tooling_master_global_id, "tenant_id": self.tenant_id},
            _("The Tooling Master is unavailable."),
        )
        require_exact_parent(
            "NPI Tooling Requirement",
            self.tooling_requirement_global_id,
            {
                "global_id": self.tooling_requirement_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "requirement_kind": self.requirement_kind,
            },
            _("The Tooling Requirement is unavailable for this physical Set."),
        )
        try:
            kind = ToolingRequirementKind(str(self.requirement_kind))
        except ValueError:
            frappe.throw(_("Select a supported value."), frappe.ValidationError)
            raise AssertionError("Frappe validation must raise.")
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        supplied = json_object(self.set_snapshot, _("Tooling Set Snapshot"))
        value = tooling_domain_value(
            lambda: ToolingSet(
                global_id=UUID(self.global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                tooling_master_global_id=UUID(self.tooling_master_global_id),
                tooling_requirement_global_id=UUID(
                    self.tooling_requirement_global_id
                ),
                requirement_kind=kind,
                physical_serial=self.physical_serial,
                customer_source_system=(
                    str(self.customer_source_system or "") or None
                ),
                customer_source_object_id=(
                    str(self.customer_source_object_id or "") or None
                ),
                custody_responsibility=self.custody_responsibility,
                repair_authorization_reference=self.repair_authorization_reference,
                return_conditions=self.return_conditions,
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
        if supplied != value.snapshot_payload():
            frappe.throw(
                _("Tooling Set Snapshot does not match its exact physical Set."),
                frappe.ValidationError,
            )
        self.tooling_master = str(value.tooling_master_global_id)
        self.tooling_requirement = str(value.tooling_requirement_global_id)
        self.requirement_kind = value.requirement_kind.value
        self.physical_serial = value.physical_serial
        self.customer_source_system = value.customer_source_system
        self.customer_source_object_id = value.customer_source_object_id
        self.custody_responsibility = value.custody_responsibility
        self.repair_authorization_reference = value.repair_authorization_reference
        self.return_conditions = value.return_conditions
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.trace_id = value.trace_id
        self.set_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = value.snapshot_hash

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
