from __future__ import annotations

from datetime import UTC, datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.domain import (
    ConnectorState,
    DocumentFileRole,
    DocumentRevisionFile,
    FileRevisionSnapshot,
    FileScanState,
    sha256_json,
)
from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    deny_document_history_update,
    document_domain_value,
    json_object,
    required_text,
    require_exact_parent,
    require_document_command_write,
    tenant_text,
    utc_datetime_text,
)


_ALL_FIELDS = (
    "global_id",
    "association_key",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "document_revision",
    "document_revision_global_id",
    "file_revision",
    "file_revision_global_id",
    "file_document_global_id",
    "file_revision_number",
    "file_optimistic_version",
    "display_file_name",
    "frappe_file_id",
    "frappe_content_hash",
    "file_name",
    "mime_type",
    "size_bytes",
    "sha256",
    "scan_state",
    "scan_observed_at",
    "is_private",
    "released",
    "file_role",
    "provenance",
    "connector_state",
    "connector_reason_code",
    "file_revision_source_snapshot",
    "association_snapshot",
    "snapshot_hash",
    "optimistic_version",
    "created_by_user_id",
    "created_at",
    "request_id",
    "trace_id",
)


class NPIDocumentRevisionFile(Document):
    """Frozen association to the exact independently-versioned private file."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_document_command_write()

    def before_save(self) -> None:
        require_document_command_write()
        if self.get_doc_before_save() is not None:
            deny_document_history_update()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.document_global_id = canonical_uuid(
            self.document_global_id,
            _("Document Global ID"),
        )
        self.document_revision = canonical_uuid(
            self.document_revision,
            _("Document Revision"),
        )
        self.document_revision_global_id = canonical_uuid(
            self.document_revision_global_id,
            _("Document Revision Global ID"),
        )
        self.file_revision = canonical_uuid(
            self.file_revision,
            _("File Revision"),
        )
        self.file_revision_global_id = canonical_uuid(
            self.file_revision_global_id,
            _("File Revision Global ID"),
        )
        self.file_document_global_id = canonical_uuid(
            self.file_document_global_id,
            _("File Document Global ID"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_document_history_update()
        if self.document_revision != self.document_revision_global_id:
            frappe.throw(
                _("Document Revision must match its exact Global ID."),
                frappe.ValidationError,
            )
        if self.file_revision != self.file_revision_global_id:
            frappe.throw(
                _("File Revision must match its exact Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Document Revision",
            self.document_revision,
            {
                "global_id": self.document_revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
            },
            _("The file association does not match its document revision."),
        )
        require_exact_parent(
            "NPI File Revision",
            self.file_revision,
            {
                "global_id": self.file_revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.file_document_global_id,
                "revision": self.file_revision_number,
                "optimistic_version": self.file_optimistic_version,
                "frappe_file_id": self.frappe_file_id,
                "frappe_content_hash": self.frappe_content_hash,
                "file_name": self.file_name,
                "mime_type": self.mime_type,
                "size_bytes": self.size_bytes,
                "sha256": self.sha256,
                "scan_state": self.scan_state,
                "scan_observed_at": self.scan_observed_at,
                "is_private": 1,
                "released": self.released,
            },
            _("The file association does not match its exact private file revision."),
        )
        try:
            scan_state = FileScanState(str(self.scan_state))
            file_role = DocumentFileRole(str(self.file_role))
            connector_state = ConnectorState(str(self.connector_state))
        except ValueError:
            frappe.throw(
                _("Select supported file association states."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        if type(self.is_private) not in {int, bool} or int(self.is_private) != 1:
            frappe.throw(
                _("The exact file revision must remain private."),
                frappe.ValidationError,
            )
        if type(self.released) not in {int, bool} or int(self.released) not in {
            0,
            1,
        }:
            frappe.throw(
                _("Released must be a checkbox value."),
                frappe.ValidationError,
            )
        association = document_domain_value(
            lambda: DocumentRevisionFile(
                global_id=self.global_id,
                document_revision_global_id=self.document_revision_global_id,
                file_revision=FileRevisionSnapshot(
                    global_id=self.file_revision_global_id,
                    file_document_global_id=self.file_document_global_id,
                    file_revision=self.file_revision_number,
                    optimistic_version=self.file_optimistic_version,
                    frappe_file_id=self.frappe_file_id,
                    frappe_content_hash=self.frappe_content_hash,
                    file_name=self.file_name,
                    mime_type=self.mime_type,
                    size_bytes=self.size_bytes,
                    sha256=self.sha256,
                    scan_state=scan_state,
                    scan_observed_at=(
                        _as_utc_datetime(self.scan_observed_at)
                        if self.scan_observed_at not in (None, "")
                        else None
                    ),
                    is_private=True,
                    released=bool(int(self.released)),
                ),
                display_file_name=self.display_file_name,
                role=file_role,
                provenance=self.provenance,
                connector_state=connector_state,
                connector_reason_code=self.connector_reason_code,
            )
        )
        expected_association_key = sha256_json(
            {
                "documentRevisionGlobalId": str(
                    association.document_revision_global_id
                ),
                "fileRevisionGlobalId": str(association.file_revision.global_id),
            }
        )
        if self.association_key not in (
            None,
            "",
            expected_association_key,
        ):
            frappe.throw(
                _("File Association Key does not match the exact file revision."),
                frappe.ValidationError,
            )
        source_snapshot = association.file_revision.canonical_dict()
        if (
            json_object(
                self.file_revision_source_snapshot,
                _("File Revision Source Snapshot"),
            )
            != source_snapshot
        ):
            frappe.throw(
                _("File Revision Source Snapshot does not match the exact file."),
                frappe.ValidationError,
            )
        snapshot = {
            "schemaVersion": 1,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "documentGlobalId": self.document_global_id,
            "association": association.canonical_dict(),
        }
        expected_hash = sha256_json(snapshot)
        supplied_snapshot = json_object(
            self.association_snapshot,
            _("File Association Snapshot"),
        )
        if supplied_snapshot != snapshot or str(self.snapshot_hash) != expected_hash:
            frappe.throw(
                _("File Association Snapshot does not match the exact file revision."),
                frappe.ValidationError,
            )
        if association.connector_state is ConnectorState.UNAVAILABLE and (
            association.connector_reason_code != "provider_not_configured"
        ):
            frappe.throw(
                _(
                    "The unavailable connector must report that no provider is configured."
                ),
                frappe.ValidationError,
            )
        if self.optimistic_version != 1:
            frappe.throw(
                _("A new file association must remain at version one."),
                frappe.ValidationError,
            )
        self.global_id = str(association.global_id)
        self.association_key = expected_association_key
        self.document_revision_global_id = str(association.document_revision_global_id)
        self.file_revision_global_id = str(association.file_revision.global_id)
        self.file_document_global_id = str(
            association.file_revision.file_document_global_id
        )
        self.file_revision_number = association.file_revision.file_revision
        self.file_optimistic_version = association.file_revision.optimistic_version
        self.display_file_name = association.display_file_name
        self.frappe_file_id = association.file_revision.frappe_file_id
        self.frappe_content_hash = association.file_revision.frappe_content_hash
        self.file_name = association.file_revision.file_name
        self.mime_type = association.file_revision.mime_type
        self.size_bytes = association.file_revision.size_bytes
        self.sha256 = association.file_revision.sha256
        self.scan_state = association.file_revision.scan_state.value
        self.scan_observed_at = (
            utc_datetime_text(
                association.file_revision.scan_observed_at,
                _("Scan Observed At"),
            )
            if association.file_revision.scan_observed_at
            else None
        )
        self.is_private = 1
        self.released = int(association.file_revision.released)
        self.file_role = association.role.value
        self.provenance = association.provenance
        self.connector_state = association.connector_state.value
        self.connector_reason_code = association.connector_reason_code
        self.file_revision_source_snapshot = canonical_json(source_snapshot)
        self.association_snapshot = canonical_json(snapshot)
        self.snapshot_hash = expected_hash
        self.created_by_user_id = actor_text(
            self.created_by_user_id,
            _("Created By"),
        )
        self.created_at = utc_datetime_text(self.created_at, _("Created At"))
        self.request_id = required_text(
            self.request_id,
            _("Request ID"),
            128,
        )
        self.trace_id = required_text(
            self.trace_id,
            _("Trace ID"),
            128,
        )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )


def _as_utc_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            frappe.throw(
                _("Enter a valid date and time."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
