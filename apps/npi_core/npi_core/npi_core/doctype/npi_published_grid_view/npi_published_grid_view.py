from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.grid_personalization.domain import GRID_ID, TABLE_SCHEMA_VERSION
from npi_core.grid_personalization.frappe_validation import (
    deny_grid_personalization_delete,
    frappe_utc_datetime_text,
    normalize_uuid_fields,
    require_actor,
    require_grid_personalization_write,
    require_hash,
    require_immutable_fields,
    require_positive_integer,
    require_tenant_id,
    require_trace_id,
)
from npi_core.project.frappe_validation import ensure_uuid


class NPIPublishedGridView(Document):
    _IDENTITY_FIELDS = (
        "global_id",
        "tenant_id",
        "project_global_id",
        "grid_id",
        "table_schema_version",
        "created_by",
        "created_at",
    )

    def before_insert(self) -> None:
        require_grid_personalization_write()

    def before_save(self) -> None:
        require_grid_personalization_write()

    def on_trash(self) -> None:
        deny_grid_personalization_delete()

    def validate(self) -> None:
        normalize_uuid_fields(
            self,
            (
                "global_id",
                "project_global_id",
                "current_revision_global_id",
            ),
        )
        self.tenant_id = require_tenant_id(self.tenant_id)
        if self.grid_id != GRID_ID or self.table_schema_version != (
            TABLE_SCHEMA_VERSION
        ):
            frappe.throw(
                _("Select the supported My Work grid schema."),
                frappe.ValidationError,
            )
        version = require_positive_integer(
            self.optimistic_version,
            _("Optimistic Version"),
        )
        revision_number = require_positive_integer(
            self.current_revision_number,
            _("Current Revision Number"),
        )
        self.current_revision_snapshot_hash = require_hash(
            self.current_revision_snapshot_hash,
            _("Current Revision Snapshot Hash"),
        )
        self.created_by = require_actor(self.created_by, _("Created By"))
        self.created_at = frappe_utc_datetime_text(
            self.created_at,
            _("Created At"),
        )
        self.request_id = ensure_uuid(self.request_id, _("Request ID"))
        self.trace_id = require_trace_id(self.trace_id)
        previous = self.get_doc_before_save()
        if previous is None:
            if version != 1 or revision_number != 1:
                frappe.throw(
                    _("A published view must begin with revision one."),
                    frappe.ValidationError,
                )
            return
        require_immutable_fields(self, previous, self._IDENTITY_FIELDS)
        if (
            version != int(previous.optimistic_version) + 1
            or revision_number != int(previous.current_revision_number) + 1
            or self.current_revision_global_id
            == previous.current_revision_global_id
            or self.current_revision_snapshot_hash
            == previous.current_revision_snapshot_hash
        ):
            frappe.throw(
                _("The published view pointer must advance to one exact successor."),
                frappe.ValidationError,
            )
