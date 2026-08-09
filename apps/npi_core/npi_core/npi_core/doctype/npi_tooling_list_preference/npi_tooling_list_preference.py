from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import require_exact_parent
from npi_core.tooling.export_domain import (
    TOOLING_LIST_GRID_ID,
    TOOLING_LIST_TABLE_SCHEMA_VERSION,
    ToolingListViewId,
    tooling_list_preference_key_hash,
)
from npi_core.tooling.export_frappe_validation import (
    canonical_export_uuid,
    deny_tooling_export_delete,
    require_snapshot_projection,
    require_tooling_export_write,
    validate_hashed_snapshot,
    validate_preference_version,
)


_IMMUTABLE_FIELDS = (
    "global_id",
    "preference_key_hash",
    "tenant_id",
    "project_global_id",
    "actor_user_id",
    "grid_id",
    "table_schema_version",
    "view_id",
)


class NPIToolingListPreference(Document):
    def autoname(self) -> None:
        canonical_export_uuid(self, "global_id", _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_export_write()

    def before_save(self) -> None:
        require_tooling_export_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_id", _("Request ID")),
        ):
            canonical_export_uuid(self, fieldname, label)

    def validate(self) -> None:
        validate_preference_version(self, _IMMUTABLE_FIELDS)
        expected_key = tooling_list_preference_key_hash(
            tenant_id=self.tenant_id,
            project_global_id=self.project_global_id,
            actor_user_id=self.actor_user_id,
            view_id=ToolingListViewId(self.view_id),
            grid_id=self.grid_id,
            table_schema_version=self.table_schema_version,
        )
        if self.preference_key_hash != expected_key:
            frappe.throw(
                _("The Tooling List preference key does not match."),
                frappe.ValidationError,
            )
        if self.grid_id != TOOLING_LIST_GRID_ID or self.table_schema_version != TOOLING_LIST_TABLE_SCHEMA_VERSION:
            frappe.throw(
                _("The Tooling List table schema is unsupported."),
                frappe.ValidationError,
            )
        snapshot = validate_hashed_snapshot(
            self,
            snapshot_field="preference_snapshot",
            snapshot_label=_("Tooling List Preference Snapshot"),
            snapshot_hash_field="snapshot_hash",
        )
        require_snapshot_projection(
            self,
            snapshot,
            (
                ("global_id", "globalId"),
                ("preference_key_hash", "preferenceKeyHash"),
                ("tenant_id", "tenantId"),
                ("project_global_id", "projectGlobalId"),
                ("actor_user_id", "actorUserId"),
                ("grid_id", "gridId"),
                ("table_schema_version", "tableSchemaVersion"),
                ("view_id", "viewId"),
                ("optimistic_version", "optimisticVersion"),
                ("last_changed_by", "lastChangedBy"),
                ("last_changed_at", "lastChangedAt"),
                ("request_id", "requestId"),
                ("trace_id", "traceId"),
            ),
        )
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The exact Project is unavailable for this Tooling List preference."),
        )

    def on_trash(self) -> None:
        deny_tooling_export_delete(self)
