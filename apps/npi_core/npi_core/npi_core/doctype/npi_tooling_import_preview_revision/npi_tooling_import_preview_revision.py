from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import require_exact_parent
from npi_core.tooling.domain import sha256_json
from npi_core.tooling.import_frappe_validation import (
    canonical_import_uuid,
    deny_tooling_import_delete,
    deny_tooling_import_update,
    require_snapshot_projection,
    require_tooling_import_write,
    validate_immutable_snapshot,
)


_IMMUTABLE_FIELDS = (
    "global_id", "preview_global_id", "preview_version", "predecessor_global_id",
    "predecessor_snapshot_hash", "tenant_id", "project_global_id", "batch_global_id",
    "source_snapshot_hash", "inspection_global_id", "inspection_snapshot_hash",
    "mapping_global_id", "mapping_snapshot_hash", "mapping_state",
    "transformation_policy_version", "execution_eligible", "row_snapshot",
    "confirmation_snapshot", "version_key_hash",
    "preview_snapshot", "snapshot_hash", "created_by_user_id", "created_at",
    "request_id", "trace_id",
)


class NPIToolingImportPreviewRevision(Document):
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
            ("preview_global_id", _("Preview Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("batch_global_id", _("Tooling Import Batch")),
            ("inspection_global_id", _("Tooling Import Inspection Revision")),
            ("mapping_global_id", _("Tooling Import Mapping Revision")),
            ("request_id", _("Request ID")),
        ):
            canonical_import_uuid(self, fieldname, label)
        if self.predecessor_global_id:
            canonical_import_uuid(
                self,
                "predecessor_global_id",
                _("Predecessor Preview Revision"),
            )

    def validate(self) -> None:
        snapshot = validate_immutable_snapshot(
            self,
            snapshot_field="preview_snapshot",
            snapshot_label=_("Tooling Import Preview Snapshot"),
            snapshot_hash_field="snapshot_hash",
            immutable_fields=_IMMUTABLE_FIELDS,
        )
        require_snapshot_projection(
            self,
            snapshot,
            (
                ("global_id", "globalId"),
                ("preview_global_id", "previewGlobalId"),
                ("preview_version", "previewVersion"),
                ("predecessor_global_id", "predecessorGlobalId"),
                ("predecessor_snapshot_hash", "predecessorSnapshotHash"),
                ("batch_global_id", "batchGlobalId"),
                ("source_snapshot_hash", "sourceSnapshotHash"),
                ("inspection_global_id", "inspectionGlobalId"),
                ("inspection_snapshot_hash", "inspectionSnapshotHash"),
                ("mapping_global_id", "mappingGlobalId"),
                ("mapping_snapshot_hash", "mappingSnapshotHash"),
                ("mapping_state", "mappingState"),
                ("transformation_policy_version", "transformationPolicyVersion"),
                ("execution_eligible", "executionEligible"),
            ),
        )
        if self.mapping_state == "proposal" and int(self.execution_eligible or 0) != 0:
            frappe.throw(_("A mapping proposal cannot authorize import execution."), frappe.ValidationError)
        expected_key = sha256_json(
            {
                "previewGlobalId": self.preview_global_id,
                "previewVersion": self.preview_version,
            }
        )
        if self.version_key_hash not in (None, "", expected_key):
            frappe.throw(_("Preview Version Key Hash does not match."), frappe.ValidationError)
        self.version_key_hash = expected_key
        require_exact_parent(
            "NPI Tooling Import Inspection Revision",
            self.inspection_global_id,
            {
                "global_id": self.inspection_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "batch_global_id": self.batch_global_id,
                "source_snapshot_hash": self.source_snapshot_hash,
                "snapshot_hash": self.inspection_snapshot_hash,
            },
            _("The exact Tooling Import Inspection Revision is unavailable."),
        )
        require_exact_parent(
            "NPI Tooling Import Mapping Revision",
            self.mapping_global_id,
            {
                "global_id": self.mapping_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "batch_global_id": self.batch_global_id,
                "source_snapshot_hash": self.source_snapshot_hash,
                "inspection_global_id": self.inspection_global_id,
                "inspection_snapshot_hash": self.inspection_snapshot_hash,
                "state": self.mapping_state,
                "snapshot_hash": self.mapping_snapshot_hash,
            },
            _("The exact Tooling Import Mapping Revision is unavailable."),
        )
        if int(self.preview_version) == 1:
            if self.predecessor_global_id or self.predecessor_snapshot_hash:
                frappe.throw(_("The first preview revision cannot have a predecessor."), frappe.ValidationError)
        else:
            require_exact_parent(
                "NPI Tooling Import Preview Revision",
                self.predecessor_global_id,
                {
                    "global_id": self.predecessor_global_id,
                    "preview_global_id": self.preview_global_id,
                    "preview_version": int(self.preview_version) - 1,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "batch_global_id": self.batch_global_id,
                    "snapshot_hash": self.predecessor_snapshot_hash,
                },
                _("The exact predecessor Preview Revision is unavailable."),
            )

    def on_trash(self) -> None:
        deny_tooling_import_delete(self)
