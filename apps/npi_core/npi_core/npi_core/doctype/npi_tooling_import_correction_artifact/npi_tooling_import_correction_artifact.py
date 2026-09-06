from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document
from npi_core.documents.frappe_validation import require_exact_parent
from npi_core.tooling.import_frappe_validation import canonical_import_uuid, correction_file_content, deny_tooling_import_delete, deny_tooling_import_update, require_snapshot_projection, require_tooling_import_write, validate_immutable_snapshot

_IMMUTABLE_FIELDS = ("global_id", "tenant_id", "project_global_id", "batch_global_id", "job_global_id", "job_snapshot_hash", "frappe_file_id", "file_name", "mime_type", "size_bytes", "sha256", "entry_count", "artifact_snapshot", "snapshot_hash", "created_by_user_id", "created_at", "request_id", "trace_id")
_VALIDATION_DIAGNOSTIC_CODES = frozenset(
    {
        "P607_CORRECTION_ARTIFACT_SNAPSHOT_VALIDATE",
        "P607_CORRECTION_ARTIFACT_PROJECTION_VALIDATE",
        "P607_CORRECTION_ARTIFACT_JOB_VALIDATE",
        "P607_CORRECTION_ARTIFACT_FILE_VALIDATE",
    }
)

class NPIToolingImportCorrectionArtifact(Document):
    def autoname(self) -> None: canonical_import_uuid(self, "global_id", _("Global ID")); self.name = self.global_id
    def before_insert(self) -> None: require_tooling_import_write()
    def before_save(self) -> None:
        require_tooling_import_write()
        if self.get_doc_before_save() is not None: deny_tooling_import_update()
    def before_validate(self) -> None:
        for fieldname, label in (("global_id", _("Global ID")), ("project_global_id", _("Project Global ID")), ("batch_global_id", _("Tooling Import Batch")), ("job_global_id", _("Tooling Import Job")), ("request_id", _("Request ID"))): canonical_import_uuid(self, fieldname, label)
    def validate(self) -> None:
        with _validation_step(
            "P607_CORRECTION_ARTIFACT_SNAPSHOT_VALIDATE",
            self.trace_id,
        ):
            snapshot = validate_immutable_snapshot(self, snapshot_field="artifact_snapshot", snapshot_label=_("Tooling Import Correction Artifact Snapshot"), snapshot_hash_field="snapshot_hash", immutable_fields=_IMMUTABLE_FIELDS)
        with _validation_step(
            "P607_CORRECTION_ARTIFACT_PROJECTION_VALIDATE",
            self.trace_id,
        ):
            require_snapshot_projection(self, snapshot, (("global_id", "globalId"), ("batch_global_id", "batchGlobalId"), ("job_global_id", "jobGlobalId"), ("job_snapshot_hash", "jobSnapshotHash"), ("frappe_file_id", "frappeFileId"), ("file_name", "fileName"), ("mime_type", "mimeType"), ("size_bytes", "sizeBytes"), ("sha256", "sha256"), ("entry_count", "entryCount"), ("created_by_user_id", "createdByUserId"), ("request_id", "requestId"), ("trace_id", "traceId")))
        with _validation_step(
            "P607_CORRECTION_ARTIFACT_JOB_VALIDATE",
            self.trace_id,
        ):
            require_exact_parent("NPI Tooling Import Job", self.job_global_id, {"global_id": self.job_global_id, "tenant_id": self.tenant_id, "project_global_id": self.project_global_id, "batch_global_id": self.batch_global_id, "snapshot_hash": self.job_snapshot_hash}, _("The exact Tooling Import Job is unavailable."))
        with _validation_step(
            "P607_CORRECTION_ARTIFACT_FILE_VALIDATE",
            self.trace_id,
        ):
            message = _("The exact private correction file is unavailable.")
            file_row = require_exact_parent(
                "File",
                self.frappe_file_id,
                {
                    "name": self.frappe_file_id,
                    "file_name": self.file_name,
                    "is_private": 1,
                },
                message,
                extra_fields=("file_size",),
            )
            content, frappe_file_size = correction_file_content(
                frappe.get_doc("File", self.frappe_file_id)
            )
            if (
                int(file_row["file_size"] or 0) != frappe_file_size
                or len(content) != int(self.size_bytes)
                or hashlib.sha256(content).hexdigest() != str(self.sha256)
            ):
                frappe.throw(message, frappe.ValidationError)
    def on_trash(self) -> None: deny_tooling_import_delete(self)


@contextmanager
def _validation_step(code: str, trace_id: str) -> Iterator[None]:
    """Record only a closed artifact-validation stage and exception type."""

    try:
        yield
    except Exception as error:
        try:
            exception_type = type(error).__name__
            if (
                code in _VALIDATION_DIAGNOSTIC_CODES
                and len(exception_type) <= 128
                and exception_type.isidentifier()
            ):
                from npi_core.api import record_safe_diagnostic

                record_safe_diagnostic(
                    code=code,
                    title="NPI Tooling import correction validation failed",
                    exception_type=exception_type,
                    trace_id=trace_id,
                )
        except Exception:
            # Diagnostics cannot change validation or transaction semantics.
            pass
        raise
