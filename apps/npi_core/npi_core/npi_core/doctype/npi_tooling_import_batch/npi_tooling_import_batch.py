from __future__ import annotations

from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import require_exact_parent
from npi_core.tooling.import_frappe_validation import (
    canonical_import_uuid,
    deny_tooling_import_delete,
    deny_tooling_import_update,
    require_snapshot_projection,
    require_tooling_import_write,
    validate_immutable_snapshot,
)


_IMMUTABLE_FIELDS = (
    "global_id", "tenant_id", "project_global_id", "customer_scope_id",
    "file_revision_global_id", "file_optimistic_version", "frappe_content_hash",
    "file_name", "mime_type", "size_bytes", "sha256", "source_snapshot",
    "snapshot_hash", "created_by_user_id", "created_at", "request_id", "trace_id",
)


class NPIToolingImportBatch(Document):
    def autoname(self) -> None:
        canonical_import_uuid(self, "global_id", _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_import_write()

    def before_save(self) -> None:
        require_tooling_import_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_import_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("file_revision_global_id", _("File Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            canonical_import_uuid(self, fieldname, label)

    def validate(self) -> None:
        snapshot = validate_immutable_snapshot(
            self,
            snapshot_field="source_snapshot",
            snapshot_label=_("Tooling Import Source Snapshot"),
            snapshot_hash_field="snapshot_hash",
            immutable_fields=_IMMUTABLE_FIELDS,
        )
        require_snapshot_projection(
            self,
            snapshot,
            (
                ("global_id", "batchGlobalId"),
                ("tenant_id", "tenantId"),
                ("project_global_id", "projectGlobalId"),
                ("customer_scope_id", "customerScopeId"),
                ("file_revision_global_id", "fileRevisionGlobalId"),
                ("file_optimistic_version", "fileOptimisticVersion"),
                ("frappe_content_hash", "frappeContentHash"),
                ("file_name", "fileName"),
                ("mime_type", "mimeType"),
                ("size_bytes", "sizeBytes"),
                ("sha256", "sha256"),
                ("created_by_user_id", "createdByUserId"),
                ("request_id", "requestId"),
                ("trace_id", "traceId"),
            ),
        )
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The exact Project is unavailable for this Tooling import."),
        )
        require_exact_parent(
            "NPI File Revision",
            self.file_revision_global_id,
            {
                "global_id": self.file_revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "optimistic_version": self.file_optimistic_version,
                "frappe_content_hash": self.frappe_content_hash,
                "file_name": self.file_name,
                "mime_type": self.mime_type,
                "size_bytes": self.size_bytes,
                "sha256": self.sha256,
                "is_private": 1,
                "scan_state": "clean",
            },
            _("The exact clean private XLSX File Revision is unavailable."),
        )

    def on_trash(self) -> None:
        deny_tooling_import_delete(self)
