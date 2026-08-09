from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import lowercase_sha256, require_exact_parent
from npi_core.tooling.export_domain import (
    MAX_TOOLING_EXPORT_OBJECTS,
    TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY,
    TOOLING_OBJECT_PACKAGE_MIME_TYPE,
    ToolingExportMode,
)
from npi_core.tooling.export_frappe_validation import (
    canonical_export_uuid,
    deny_tooling_export_delete,
    deny_tooling_export_update,
    require_json_projection,
    require_snapshot_projection,
    require_tooling_export_write,
    validate_immutable_snapshot,
    validate_package_expiry,
)


_IMMUTABLE_FIELDS = (
    "global_id", "tenant_id", "project_global_id", "created_by_user_id",
    "mode", "language", "confidentiality_class", "object_count",
    "query_snapshot_hash", "object_refs", "generated_at", "expires_at",
    "frappe_file_id", "file_name", "mime_type", "size_bytes", "sha256",
    "manifest_sha256", "package_snapshot", "snapshot_hash", "request_id",
    "trace_id",
)


class NPIToolingExportPackage(Document):
    def autoname(self) -> None:
        canonical_export_uuid(self, "global_id", _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_export_write()

    def before_save(self) -> None:
        require_tooling_export_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_export_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("request_id", _("Request ID")),
        ):
            canonical_export_uuid(self, fieldname, label)

    def validate(self) -> None:
        if not 1 <= self.object_count <= MAX_TOOLING_EXPORT_OBJECTS:
            frappe.throw(
                _("Select between one and one hundred Tooling Masters."),
                frappe.ValidationError,
            )
        if self.confidentiality_class != TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY:
            frappe.throw(
                _("Select the internal Project confidentiality class."),
                frappe.ValidationError,
            )
        if self.mime_type != TOOLING_OBJECT_PACKAGE_MIME_TYPE:
            frappe.throw(
                _("Select the Tooling object package media type."),
                frappe.ValidationError,
            )
        self.sha256 = lowercase_sha256(self.sha256, _("SHA-256"))
        self.manifest_sha256 = lowercase_sha256(
            self.manifest_sha256,
            _("Manifest SHA-256"),
        )
        if self.mode == ToolingExportMode.FILTERED.value:
            self.query_snapshot_hash = lowercase_sha256(
                self.query_snapshot_hash,
                _("Query Snapshot Hash"),
            )
        elif self.mode != ToolingExportMode.SELECTION.value or self.query_snapshot_hash:
            frappe.throw(
                _("A selection export cannot include a filtered query snapshot."),
                frappe.ValidationError,
            )
        snapshot = validate_immutable_snapshot(
            self,
            snapshot_field="package_snapshot",
            snapshot_label=_("Tooling Export Package Snapshot"),
            snapshot_hash_field="snapshot_hash",
            immutable_fields=_IMMUTABLE_FIELDS,
        )
        require_snapshot_projection(
            self,
            snapshot,
            (
                ("global_id", "globalId"),
                ("tenant_id", "tenantId"),
                ("project_global_id", "projectGlobalId"),
                ("created_by_user_id", "createdByUserId"),
                ("mode", "mode"),
                ("language", "language"),
                ("confidentiality_class", "confidentialityClass"),
                ("object_count", "objectCount"),
                ("query_snapshot_hash", "querySnapshotHash"),
                ("generated_at", "generatedAt"),
                ("expires_at", "expiresAt"),
                ("frappe_file_id", "frappeFileId"),
                ("file_name", "fileName"),
                ("mime_type", "mimeType"),
                ("size_bytes", "sizeBytes"),
                ("sha256", "sha256"),
                ("manifest_sha256", "manifestSha256"),
                ("request_id", "requestId"),
                ("trace_id", "traceId"),
            ),
        )
        require_json_projection(self, "object_refs", snapshot, "objectRefs")
        validate_package_expiry(self)
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {"global_id": self.project_global_id, "tenant_id": self.tenant_id},
            _("The exact Project is unavailable for this Tooling export package."),
        )

    def on_trash(self) -> None:
        deny_tooling_export_delete(self)
