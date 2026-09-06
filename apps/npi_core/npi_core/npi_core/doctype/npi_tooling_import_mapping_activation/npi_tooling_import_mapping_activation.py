from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    json_array,
    require_exact_parent,
)
from npi_core.tooling.import_frappe_validation import (
    canonical_import_uuid,
    deny_tooling_import_delete,
    deny_tooling_import_update,
    require_snapshot_projection,
    require_tooling_import_write,
    validate_immutable_snapshot,
)


_IMMUTABLE_FIELDS = (
    "global_id", "state", "tenant_id", "project_global_id", "batch_global_id",
    "source_snapshot_hash", "source_sha256", "customer_scope_id", "fixture_version",
    "mapping_revision_global_id", "mapping_snapshot_hash", "source_signature",
    "binding_snapshot", "activation_snapshot", "snapshot_hash", "created_by_user_id",
    "created_at", "request_id", "trace_id",
)


class NPIToolingImportMappingActivation(Document):
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
            ("mapping_revision_global_id", _("Tooling Import Mapping Revision")),
            ("request_id", _("Request ID")),
        ):
            canonical_import_uuid(self, fieldname, label)

    def validate(self) -> None:
        snapshot = validate_immutable_snapshot(
            self,
            snapshot_field="activation_snapshot",
            snapshot_label=_("Tooling Import Mapping Activation Snapshot"),
            snapshot_hash_field="snapshot_hash",
            immutable_fields=_IMMUTABLE_FIELDS,
        )
        require_snapshot_projection(
            self,
            snapshot,
            (
                ("global_id", "globalId"), ("state", "state"),
                ("tenant_id", "tenantId"), ("project_global_id", "projectGlobalId"),
                ("batch_global_id", "batchGlobalId"),
                ("source_snapshot_hash", "sourceSnapshotHash"),
                ("source_sha256", "sourceSha256"),
                ("customer_scope_id", "customerScopeId"),
                ("fixture_version", "fixtureVersion"),
                ("mapping_revision_global_id", "mappingRevisionGlobalId"),
                ("mapping_snapshot_hash", "mappingSnapshotHash"),
                ("source_signature", "sourceSignature"),
                ("created_by_user_id", "createdByUserId"),
                ("request_id", "requestId"), ("trace_id", "traceId"),
            ),
        )
        bindings = json_array(
            self.binding_snapshot,
            _("Execution Field Binding Snapshot"),
        )
        if bindings != snapshot.get("bindings"):
            frappe.throw(
                _("Execution field bindings do not match the activation snapshot."),
                frappe.ValidationError,
            )
        self.binding_snapshot = canonical_json(bindings)
        if self.state != "approved_fixture":
            frappe.throw(
                _("Production mapping approval is unavailable."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Tooling Import Batch", self.batch_global_id,
            {"global_id": self.batch_global_id, "tenant_id": self.tenant_id,
             "project_global_id": self.project_global_id,
             "customer_scope_id": self.customer_scope_id,
             "snapshot_hash": self.source_snapshot_hash, "sha256": self.source_sha256},
            _("The exact Tooling Import Batch is unavailable."),
        )
        require_exact_parent(
            "NPI Tooling Import Mapping Revision", self.mapping_revision_global_id,
            {"global_id": self.mapping_revision_global_id, "tenant_id": self.tenant_id,
             "project_global_id": self.project_global_id, "batch_global_id": self.batch_global_id,
             "state": "approved_fixture", "snapshot_hash": self.mapping_snapshot_hash,
             "source_signature": self.source_signature},
            _("The exact approved fixture mapping is unavailable."),
        )

    def on_trash(self) -> None:
        deny_tooling_import_delete(self)
