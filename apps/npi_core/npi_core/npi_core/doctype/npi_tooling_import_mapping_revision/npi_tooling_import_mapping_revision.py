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
    "global_id", "mapping_global_id", "tenant_id", "project_global_id",
    "batch_global_id", "source_snapshot_hash", "inspection_global_id",
    "inspection_snapshot_hash", "mapping_version", "state", "customer_scope_id", "template_key",
    "source_signature", "entry_snapshot", "reason", "version_key_hash",
    "mapping_snapshot", "snapshot_hash", "created_by_user_id", "created_at",
    "request_id", "trace_id",
)


class NPIToolingImportMappingRevision(Document):
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
            ("mapping_global_id", _("Mapping Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("batch_global_id", _("Tooling Import Batch")),
            ("inspection_global_id", _("Tooling Import Inspection Revision")),
            ("request_id", _("Request ID")),
        ):
            canonical_import_uuid(self, fieldname, label)

    def validate(self) -> None:
        snapshot = validate_immutable_snapshot(
            self,
            snapshot_field="mapping_snapshot",
            snapshot_label=_("Tooling Import Mapping Snapshot"),
            snapshot_hash_field="snapshot_hash",
            immutable_fields=_IMMUTABLE_FIELDS,
        )
        require_snapshot_projection(
            self,
            snapshot,
            (
                ("global_id", "globalId"),
                ("mapping_global_id", "mappingGlobalId"),
                ("batch_global_id", "batchGlobalId"),
                ("source_snapshot_hash", "sourceSnapshotHash"),
                ("inspection_global_id", "inspectionGlobalId"),
                ("inspection_snapshot_hash", "inspectionSnapshotHash"),
                ("mapping_version", "mappingVersion"),
                ("state", "state"),
                ("customer_scope_id", "customerScopeId"),
                ("template_key", "templateKey"),
                ("source_signature", "sourceSignature"),
                ("reason", "reason"),
                ("created_by_user_id", "createdByUserId"),
            ),
        )
        if self.state not in {"proposal", "approved_fixture"}:
            frappe.throw(_("Production mapping approval is unavailable."), frappe.ValidationError)
        expected_key = sha256_json(
            {
                "mappingGlobalId": self.mapping_global_id,
                "mappingVersion": self.mapping_version,
            }
        )
        if self.version_key_hash not in (None, "", expected_key):
            frappe.throw(_("Mapping Version Key Hash does not match."), frappe.ValidationError)
        self.version_key_hash = expected_key
        require_exact_parent(
            "NPI Tooling Import Batch",
            self.batch_global_id,
            {
                "global_id": self.batch_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "customer_scope_id": self.customer_scope_id,
                "snapshot_hash": self.source_snapshot_hash,
            },
            _("The exact Tooling Import Batch is unavailable."),
        )
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
                "source_signature": self.source_signature,
            },
            _("The exact Tooling Import Inspection Revision is unavailable."),
        )

    def on_trash(self) -> None:
        deny_tooling_import_delete(self)
