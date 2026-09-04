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
    "global_id", "tenant_id", "project_global_id", "batch_global_id",
    "source_snapshot_hash", "inspection_version", "inspection_policy_version",
    "detection_policy_version", "worksheet_name", "header_row", "source_signature",
    "column_snapshot", "region_snapshot", "formula_error_snapshot",
    "image_anchor_snapshot", "passive_report_hash", "inspection_snapshot",
    "snapshot_hash", "created_by_user_id", "created_at", "request_id", "trace_id",
)


class NPIToolingImportInspectionRevision(Document):
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
            ("batch_global_id", _("Tooling Import Batch")),
            ("request_id", _("Request ID")),
        ):
            canonical_import_uuid(self, fieldname, label)

    def validate(self) -> None:
        snapshot = validate_immutable_snapshot(
            self,
            snapshot_field="inspection_snapshot",
            snapshot_label=_("Tooling Import Inspection Snapshot"),
            snapshot_hash_field="snapshot_hash",
            immutable_fields=_IMMUTABLE_FIELDS,
        )
        require_snapshot_projection(
            self,
            snapshot,
            (
                ("global_id", "globalId"),
                ("batch_global_id", "batchGlobalId"),
                ("source_snapshot_hash", "sourceSnapshotHash"),
                ("inspection_version", "inspectionVersion"),
                ("inspection_policy_version", "inspectionPolicyVersion"),
                ("detection_policy_version", "detectionPolicyVersion"),
                ("worksheet_name", "worksheetName"),
                ("header_row", "headerRow"),
                ("source_signature", "sourceSignature"),
                ("passive_report_hash", "passiveReportHash"),
            ),
        )
        require_exact_parent(
            "NPI Tooling Import Batch",
            self.batch_global_id,
            {
                "global_id": self.batch_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "snapshot_hash": self.source_snapshot_hash,
            },
            _("The exact Tooling Import Batch is unavailable."),
        )

    def on_trash(self) -> None:
        deny_tooling_import_delete(self)
