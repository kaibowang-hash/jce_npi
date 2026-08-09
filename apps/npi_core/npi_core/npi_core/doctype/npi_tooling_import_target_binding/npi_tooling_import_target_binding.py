from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from npi_core.documents.frappe_validation import require_exact_parent
from npi_core.tooling.import_frappe_validation import canonical_import_uuid, deny_tooling_import_delete, deny_tooling_import_update, require_snapshot_projection, require_tooling_import_write, validate_immutable_snapshot

_IMMUTABLE_FIELDS = ("global_id", "row_result_global_id", "tenant_id", "project_global_id", "batch_global_id", "job_global_id", "action", "target_object_type", "target_root_global_id", "target_global_id", "target_version", "target_snapshot_hash", "mapping_revision_global_id", "mapping_snapshot_hash", "provenance_hash", "binding_snapshot", "snapshot_hash", "created_at", "request_id", "trace_id")

class NPIToolingImportTargetBinding(Document):
    def autoname(self) -> None: canonical_import_uuid(self, "global_id", _("Global ID")); self.name = self.global_id
    def before_insert(self) -> None: require_tooling_import_write()
    def before_save(self) -> None:
        require_tooling_import_write()
        if self.get_doc_before_save() is not None: deny_tooling_import_update()
    def before_validate(self) -> None:
        for fieldname, label in (("global_id", _("Global ID")), ("row_result_global_id", _("Tooling Import Row Result")), ("project_global_id", _("Project Global ID")), ("batch_global_id", _("Tooling Import Batch")), ("job_global_id", _("Tooling Import Job")), ("target_root_global_id", _("Target Root Global ID")), ("target_global_id", _("Target Global ID")), ("mapping_revision_global_id", _("Tooling Import Mapping Revision")), ("request_id", _("Request ID"))): canonical_import_uuid(self, fieldname, label)
    def validate(self) -> None:
        snapshot = validate_immutable_snapshot(self, snapshot_field="binding_snapshot", snapshot_label=_("Tooling Import Target Binding Snapshot"), snapshot_hash_field="snapshot_hash", immutable_fields=_IMMUTABLE_FIELDS)
        require_snapshot_projection(self, snapshot, (("global_id", "globalId"), ("row_result_global_id", "rowResultGlobalId"), ("batch_global_id", "batchGlobalId"), ("job_global_id", "jobGlobalId"), ("action", "action"), ("target_object_type", "targetObjectType"), ("target_root_global_id", "targetRootGlobalId"), ("target_global_id", "targetGlobalId"), ("target_version", "targetVersion"), ("target_snapshot_hash", "targetSnapshotHash"), ("mapping_revision_global_id", "mappingRevisionGlobalId"), ("mapping_snapshot_hash", "mappingSnapshotHash"), ("provenance_hash", "provenanceHash")))
        if self.action != "create" or self.target_object_type != "engineering_part_revision":
            frappe.throw(_("Only the controlled created Part Revision target can be bound."), frappe.ValidationError)
        require_exact_parent("NPI Tooling Import Row Result", self.row_result_global_id, {"global_id": self.row_result_global_id, "tenant_id": self.tenant_id, "project_global_id": self.project_global_id, "batch_global_id": self.batch_global_id, "job_global_id": self.job_global_id, "state": "created", "target_object_type": self.target_object_type, "target_global_id": self.target_global_id, "target_snapshot_hash": self.target_snapshot_hash}, _("The exact successful import row result is unavailable."))
        require_exact_parent("NPI Engineering Part Revision", self.target_global_id, {"global_id": self.target_global_id, "part_global_id": self.target_root_global_id, "tenant_id": self.tenant_id, "originating_project_global_id": self.project_global_id, "revision_number": self.target_version, "snapshot_hash": self.target_snapshot_hash}, _("The exact imported Part Revision is unavailable."))
        require_exact_parent("NPI Engineering Part", self.target_root_global_id, {"global_id": self.target_root_global_id, "tenant_id": self.tenant_id, "originating_project_global_id": self.project_global_id, "current_revision_global_id": self.target_global_id, "current_revision_number": self.target_version, "current_revision_snapshot_hash": self.target_snapshot_hash, "optimistic_version": self.target_version}, _("The exact imported Part is unavailable."))
    def on_trash(self) -> None: deny_tooling_import_delete(self)
