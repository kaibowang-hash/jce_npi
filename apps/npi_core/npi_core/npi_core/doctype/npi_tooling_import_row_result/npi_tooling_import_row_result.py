from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    json_array,
    require_exact_parent,
)
from npi_core.tooling.domain import sha256_json
from npi_core.tooling.import_frappe_validation import (
    canonical_import_uuid, deny_tooling_import_delete, deny_tooling_import_update,
    require_snapshot_projection, require_tooling_import_write, validate_immutable_snapshot,
)


_IMMUTABLE_FIELDS = (
    "global_id", "result_key_hash", "tenant_id", "project_global_id", "batch_global_id",
    "job_global_id", "worksheet_name", "source_row", "attempt", "state",
    "target_object_type", "target_global_id", "target_snapshot_hash",
    "field_result_snapshot", "row_result_snapshot", "snapshot_hash", "created_at",
    "request_id", "trace_id",
)


class NPIToolingImportRowResult(Document):
    def autoname(self) -> None:
        canonical_import_uuid(self, "global_id", _("Global ID")); self.name = self.global_id
    def before_insert(self) -> None: require_tooling_import_write()
    def before_save(self) -> None:
        require_tooling_import_write()
        if self.get_doc_before_save() is not None: deny_tooling_import_update()
    def before_validate(self) -> None:
        for fieldname, label in (("global_id", _("Global ID")), ("project_global_id", _("Project Global ID")),
                                 ("batch_global_id", _("Tooling Import Batch")), ("job_global_id", _("Tooling Import Job")),
                                 ("request_id", _("Request ID"))):
            canonical_import_uuid(self, fieldname, label)
    def validate(self) -> None:
        snapshot = validate_immutable_snapshot(
            self, snapshot_field="row_result_snapshot", snapshot_label=_("Tooling Import Row Result Snapshot"),
            snapshot_hash_field="snapshot_hash", immutable_fields=_IMMUTABLE_FIELDS,
        )
        require_snapshot_projection(self, snapshot, (("global_id", "globalId"), ("worksheet_name", "worksheetName"),
            ("source_row", "sourceRow"), ("attempt", "attempt"), ("state", "state"),
            ("target_object_type", "targetObjectType"), ("target_global_id", "targetGlobalId"),
            ("target_snapshot_hash", "targetSnapshotHash"), ("trace_id", "traceId")))
        field_results = json_array(
            self.field_result_snapshot,
            _("Import Field Result Snapshot"),
        )
        if field_results != snapshot.get("fieldResults"):
            frappe.throw(
                _("Import field results do not match the row result snapshot."),
                frappe.ValidationError,
            )
        self.field_result_snapshot = canonical_json(field_results)
        expected = sha256_json({"jobGlobalId": self.job_global_id, "worksheetName": self.worksheet_name,
                                "sourceRow": self.source_row, "attempt": self.attempt})
        if self.result_key_hash not in (None, "", expected):
            frappe.throw(
                _("Import Row Result Key Hash does not match."),
                frappe.ValidationError,
            )
        self.result_key_hash = expected
        require_exact_parent("NPI Tooling Import Job", self.job_global_id,
            {"global_id": self.job_global_id, "tenant_id": self.tenant_id,
             "project_global_id": self.project_global_id, "batch_global_id": self.batch_global_id,
             "attempt": self.attempt},
            _("The exact Tooling Import Job is unavailable."))
    def on_trash(self) -> None: deny_tooling_import_delete(self)
