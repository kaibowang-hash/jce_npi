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
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.tooling.domain import ToolingMaster
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingMaster(Document):
    """Immutable same-tenant logical Tooling identity without lifecycle."""

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
            ("originating_project_global_id", _("Originating Project Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        require_exact_parent(
            "NPI Engineering Project",
            self.originating_project_global_id,
            {
                "global_id": self.originating_project_global_id,
                "tenant_id": self.tenant_id,
            },
            _("The Tooling Master does not match its originating Project and tenant."),
        )
        supplied = json_object(self.master_snapshot, _("Tooling Master Snapshot"))
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        master = tooling_domain_value(
            lambda: ToolingMaster(
                global_id=UUID(self.global_id),
                tenant_id=self.tenant_id,
                originating_project_global_id=UUID(self.originating_project_global_id),
                title=self.title,
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
        if supplied != master.snapshot_payload():
            frappe.throw(
                _("Tooling Master Snapshot does not match its exact identity."),
                frappe.ValidationError,
            )
        self.title = master.title
        self.created_by_user_id = master.created_by_user_id
        self.created_at = frappe_utc_datetime_text(master.created_at, _("Created At"))
        self.trace_id = master.trace_id
        self.master_snapshot = canonical_json(master.snapshot_payload())
        self.snapshot_hash = master.snapshot_hash

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
