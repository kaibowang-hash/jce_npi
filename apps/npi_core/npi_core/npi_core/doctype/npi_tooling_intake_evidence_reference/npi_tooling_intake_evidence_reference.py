from __future__ import annotations

from datetime import datetime
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    positive_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    has_live_private_file_identity,
)
from npi_core.tooling.domain import (
    ToolingIntakeEvidenceReference,
    ToolingIntakeEvidenceRole,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)


class NPIToolingIntakeEvidenceReference(Document):
    """Append-only URL-free reference to one exact clean private file revision."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_command_write()

    def before_save(self) -> None:
        require_tooling_command_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_set_global_id", _("Tooling Set Global ID")),
            ("tooling_intake_global_id", _("Tooling Intake Global ID")),
            ("file_revision_global_id", _("File Revision Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.intake_snapshot_hash = lowercase_sha256(
            self.intake_snapshot_hash,
            _("Tooling Intake Snapshot Hash"),
        )

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        require_exact_parent(
            "NPI Tooling Intake",
            self.tooling_intake_global_id,
            {
                "global_id": self.tooling_intake_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "tooling_master_global_id": self.tooling_master_global_id,
                "tooling_set_global_id": self.tooling_set_global_id,
                "snapshot_hash": self.intake_snapshot_hash,
            },
            _("The exact Tooling Intake version is unavailable."),
        )
        require_exact_parent(
            "NPI File Revision",
            self.file_revision_global_id,
            {
                "global_id": self.file_revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
            },
            _("The exact clean private File Revision is unavailable."),
        )
        file_revision = frappe.get_doc(
            "NPI File Revision",
            self.file_revision_global_id,
        )
        if (
            str(file_revision.global_id) != self.file_revision_global_id
            or str(file_revision.tenant_id) != self.tenant_id
            or str(file_revision.project_global_id) != self.project_global_id
            or str(file_revision.scan_state) != "clean"
            or not has_live_private_file_identity(file_revision)
        ):
            frappe.throw(
                _("The exact clean private File Revision is unavailable."),
                frappe.ValidationError,
            )
        try:
            role = ToolingIntakeEvidenceRole(str(self.evidence_role))
        except ValueError:
            frappe.throw(_("Select a supported value."), frappe.ValidationError)
            raise AssertionError("Frappe validation must raise.")
        difference_ids = tuple(
            UUID(canonical_uuid(value, _("Difference Global ID")))
            for value in json_array(
                self.difference_global_ids,
                _("Difference Global IDs"),
            )
        )
        intake = frappe.get_doc("NPI Tooling Intake", self.tooling_intake_global_id)
        intake_differences = {
            str(value.get("globalId"))
            for value in json_array(
                intake.difference_snapshot,
                _("Difference Snapshot"),
            )
            if isinstance(value, dict)
        }
        if any(str(value) not in intake_differences for value in difference_ids):
            frappe.throw(
                _("The customer confirmation difference is unavailable."),
                frappe.ValidationError,
            )
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        supplied = json_object(
            self.evidence_snapshot,
            _("Tooling Intake Evidence Snapshot"),
        )
        value = tooling_domain_value(
            lambda: ToolingIntakeEvidenceReference(
                global_id=UUID(self.global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                tooling_master_global_id=UUID(self.tooling_master_global_id),
                tooling_set_global_id=UUID(self.tooling_set_global_id),
                tooling_intake_global_id=UUID(self.tooling_intake_global_id),
                intake_snapshot_hash=lowercase_sha256(
                    self.intake_snapshot_hash,
                    _("Tooling Intake Snapshot Hash"),
                ),
                evidence_role=role,
                difference_global_ids=difference_ids,
                file_revision_global_id=UUID(self.file_revision_global_id),
                file_optimistic_version=positive_integer(
                    self.file_optimistic_version,
                    _("File Optimistic Version"),
                ),
                frappe_content_hash=str(self.frappe_content_hash or "").lower(),
                file_name=self.file_name,
                mime_type=self.mime_type,
                size_bytes=positive_integer(self.size_bytes, _("Size in Bytes")),
                sha256=lowercase_sha256(self.sha256, _("SHA-256")),
                created_by_user_id=actor_text(
                    self.created_by_user_id,
                    _("Created By User ID"),
                ),
                created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                evidence_key_hash=str(self.evidence_key_hash or ""),
                snapshot_hash=str(self.snapshot_hash or ""),
            )
        )
        if (
            value.file_optimistic_version != int(file_revision.optimistic_version)
            or value.frappe_content_hash
            != str(file_revision.frappe_content_hash).lower()
            or value.file_name != str(file_revision.file_name)
            or value.mime_type != str(file_revision.mime_type)
            or value.size_bytes != int(file_revision.size_bytes)
            or value.sha256 != str(file_revision.sha256).lower()
        ):
            frappe.throw(
                _("The Tooling Intake evidence does not match its exact File Revision."),
                frappe.ValidationError,
            )
        if supplied != value.snapshot_payload():
            frappe.throw(
                _("Tooling Intake Evidence Snapshot does not match its exact evidence."),
                frappe.ValidationError,
            )
        self.evidence_key_hash = value.evidence_key_hash
        self.tooling_intake = str(value.tooling_intake_global_id)
        self.evidence_role = value.evidence_role.value
        self.difference_global_ids = canonical_json(
            [str(item) for item in value.difference_global_ids]
        )
        self.file_revision = str(value.file_revision_global_id)
        self.file_optimistic_version = value.file_optimistic_version
        self.frappe_content_hash = value.frappe_content_hash
        self.file_name = value.file_name
        self.mime_type = value.mime_type
        self.size_bytes = value.size_bytes
        self.sha256 = value.sha256
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.trace_id = value.trace_id
        self.evidence_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = value.snapshot_hash

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
