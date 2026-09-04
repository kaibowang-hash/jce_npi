from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import assert_immutable_fields, require_exact_parent
from npi_core.tooling.import_frappe_validation import (
    canonical_import_uuid,
    deny_tooling_import_delete,
    require_snapshot_projection,
    require_tooling_import_write,
    validate_hashed_snapshot,
)


_IDENTITY_FIELDS = (
    "global_id", "tenant_id", "project_global_id", "batch_global_id",
    "source_snapshot_hash", "preview_global_id", "preview_revision_global_id",
    "preview_snapshot_hash", "mapping_activation_global_id", "actor_user_id",
    "queued_at", "request_id", "trace_id",
)
_TRANSITIONS = {
    "queued": {"processing", "failed_final"},
    "processing": {"processing", "partially_succeeded", "succeeded", "failed_retryable", "failed_final"},
    "partially_succeeded": {"queued", "rolled_back", "rollback_denied"},
    "succeeded": {"rolled_back", "rollback_denied"},
    "failed_retryable": {"queued", "rollback_denied"},
    "failed_final": {"rollback_denied"},
    "rolled_back": set(),
    "rollback_denied": set(),
}


class NPIToolingImportJob(Document):
    def autoname(self) -> None:
        canonical_import_uuid(self, "global_id", _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_import_write()

    def before_save(self) -> None:
        require_tooling_import_write()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")), ("project_global_id", _("Project Global ID")),
            ("batch_global_id", _("Tooling Import Batch")),
            ("preview_global_id", _("Preview Global ID")),
            ("preview_revision_global_id", _("Tooling Import Preview Revision")),
            ("mapping_activation_global_id", _("Tooling Import Mapping Activation")),
            ("request_id", _("Request ID")),
        ):
            canonical_import_uuid(self, fieldname, label)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is None:
            if self.state != "queued" or int(self.attempt or 0) != 1 or int(self.optimistic_version or 0) != 1:
                frappe.throw(_("A new Tooling import job must start as queued attempt one."), frappe.ValidationError)
        else:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
            if self.state not in _TRANSITIONS.get(str(previous.state), set()):
                frappe.throw(_("The Tooling import job state transition is not allowed."), frappe.ValidationError)
            if int(self.optimistic_version or 0) != int(previous.optimistic_version) + 1:
                frappe.throw(_("The Tooling import job version must advance exactly once."), frappe.ValidationError)
            previous_attempt = int(previous.attempt)
            expected_attempt = previous_attempt + 1 if self.state == "queued" else previous_attempt
            if int(self.attempt or 0) != expected_attempt:
                frappe.throw(_("The Tooling import attempt does not match the state transition."), frappe.ValidationError)
            current_correction = (
                self.correction_artifact_global_id,
                self.correction_artifact_snapshot_hash,
            )
            previous_correction = (
                previous.correction_artifact_global_id,
                previous.correction_artifact_snapshot_hash,
            )
            if self.state == "queued":
                if any(value in (None, "") for value in current_correction):
                    frappe.throw(
                        _("A retry attempt requires an exact correction artifact."),
                        frappe.ValidationError,
                    )
            elif current_correction != previous_correction:
                frappe.throw(
                    _("The correction artifact can only change when a retry is queued."),
                    frappe.ValidationError,
                )
        if previous is None and any(
            value not in (None, "")
            for value in (
                self.correction_artifact_global_id,
                self.correction_artifact_snapshot_hash,
            )
        ):
            frappe.throw(
                _("The first import attempt cannot use a correction artifact."),
                frappe.ValidationError,
            )
        snapshot = validate_hashed_snapshot(
            self, snapshot_field="job_snapshot",
            snapshot_label=_("Tooling Import Job Snapshot"), snapshot_hash_field="snapshot_hash",
        )
        require_snapshot_projection(
            self, snapshot,
            (("global_id", "globalId"), ("batch_global_id", "batchGlobalId"),
             ("preview_global_id", "previewGlobalId"),
             ("preview_snapshot_hash", "previewSnapshotHash"),
             ("attempt", "attempt"), ("state", "state"),
             ("correction_artifact_global_id", "correctionArtifactGlobalId"),
             ("correction_artifact_snapshot_hash", "correctionArtifactSnapshotHash")),
        )
        require_exact_parent(
            "NPI Tooling Import Batch", self.batch_global_id,
            {"global_id": self.batch_global_id, "tenant_id": self.tenant_id,
             "project_global_id": self.project_global_id, "snapshot_hash": self.source_snapshot_hash},
            _("The exact Tooling Import Batch is unavailable."),
        )
        require_exact_parent(
            "NPI Tooling Import Preview Revision", self.preview_revision_global_id,
            {"global_id": self.preview_revision_global_id, "preview_global_id": self.preview_global_id,
             "tenant_id": self.tenant_id, "project_global_id": self.project_global_id,
             "batch_global_id": self.batch_global_id, "snapshot_hash": self.preview_snapshot_hash,
             "mapping_state": "approved_fixture"},
            _("The exact executable Tooling import preview is unavailable."),
        )
        require_exact_parent(
            "NPI Tooling Import Mapping Activation", self.mapping_activation_global_id,
            {"global_id": self.mapping_activation_global_id, "tenant_id": self.tenant_id,
             "project_global_id": self.project_global_id, "batch_global_id": self.batch_global_id,
             "state": "approved_fixture"},
            _("The exact fixture mapping activation is unavailable."),
        )
        if self.correction_artifact_global_id:
            require_exact_parent(
                "NPI Tooling Import Correction Artifact",
                self.correction_artifact_global_id,
                {
                    "global_id": self.correction_artifact_global_id,
                    "tenant_id": self.tenant_id,
                    "project_global_id": self.project_global_id,
                    "batch_global_id": self.batch_global_id,
                    "job_global_id": self.global_id,
                    "snapshot_hash": self.correction_artifact_snapshot_hash,
                },
                _("The exact correction artifact is unavailable."),
            )

    def on_trash(self) -> None:
        deny_tooling_import_delete(self)
