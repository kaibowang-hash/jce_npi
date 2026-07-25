from __future__ import annotations

from datetime import date, datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.domain import (
    ConnectorState,
    DocumentFileRole,
    DocumentPolicyReference,
    DocumentRevision,
    DocumentRevisionFile,
    DocumentRevisionState,
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
    optional_date_text,
    optional_uuid,
    positive_integer,
    required_text,
    require_exact_parent,
    require_document_command_write,
    tenant_text,
    utc_datetime_text,
)


_ALL_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "controlled_document",
    "document_global_id",
    "major",
    "minor",
    "revision_key",
    "reason",
    "effective_date",
    "predecessor_revision_global_id",
    "lock_global_id",
    "lock_version",
    "revision_state",
    "policy_global_id",
    "policy_version",
    "policy_snapshot_hash",
    "revision_snapshot",
    "snapshot_hash",
    "optimistic_version",
    "created_by_user_id",
    "created_at",
    "request_id",
    "trace_id",
)


class NPIDocumentRevision(Document):
    """Append-only document revision; P5-01 creates draft revisions only."""

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
        self.controlled_document = canonical_uuid(
            self.controlled_document,
            _("Controlled Document"),
        )
        self.document_global_id = canonical_uuid(
            self.document_global_id,
            _("Document Global ID"),
        )
        self.predecessor_revision_global_id = optional_uuid(
            self.predecessor_revision_global_id,
            _("Predecessor Revision Global ID"),
        )
        self.effective_date = optional_date_text(
            self.effective_date,
            _("Effective Date"),
        )
        self.lock_global_id = canonical_uuid(
            self.lock_global_id,
            _("Edit Lock Global ID"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_document_history_update()
        if self.controlled_document != self.document_global_id:
            frappe.throw(
                _("Controlled Document must match the exact Document Global ID."),
                frappe.ValidationError,
            )
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
        self.lock_version = positive_integer(
            self.lock_version,
            _("Edit Lock Version"),
        )
        parent = require_exact_parent(
            "NPI Controlled Document",
            self.controlled_document,
            {
                "global_id": self.document_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "policy_global_id": self.policy_global_id,
                "policy_version": self.policy_version,
                "policy_snapshot_hash": self.policy_snapshot_hash,
                "current_lock_global_id": self.lock_global_id,
                "current_lock_version": self.lock_version,
                "current_lock_holder_user_id": self.created_by_user_id,
            },
            _("The document revision does not match its controlled document."),
            extra_fields=(
                "current_revision_global_id",
                "current_revision_major",
                "current_revision_minor",
            ),
        )
        current_revision = parent.get("current_revision_global_id")
        if self.predecessor_revision_global_id is None:
            if current_revision not in (None, ""):
                frappe.throw(
                    _("The first revision cannot replace an existing revision."),
                    frappe.ValidationError,
                )
        elif str(current_revision) != self.predecessor_revision_global_id:
            frappe.throw(
                _("Predecessor Revision must be the exact current revision."),
                frappe.ValidationError,
            )
        elif (int(self.major), int(self.minor)) <= (
            int(parent.get("current_revision_major") or 0),
            int(parent.get("current_revision_minor") or 0),
        ):
            frappe.throw(
                _("The successor revision must be later than the current revision."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Document Lock Event",
            {
                "lock_global_id": self.lock_global_id,
                "lock_version": self.lock_version,
            },
            {
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "event_type": "acquired",
                "holder_user_id": self.created_by_user_id,
            },
            _("The document revision does not match an active edit lock."),
        )
        try:
            revision_state = DocumentRevisionState(str(self.revision_state))
        except ValueError:
            frappe.throw(
                _("Select a supported document revision state."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        expected_revision_key = sha256_json(
            {
                "documentGlobalId": self.document_global_id,
                "major": self.major,
                "minor": self.minor,
            }
        )
        if self.revision_key not in (None, "", expected_revision_key):
            frappe.throw(
                _("Revision Key does not match the exact document revision."),
                frappe.ValidationError,
            )
        snapshot = json_object(
            self.revision_snapshot,
            _("Revision Snapshot"),
        )
        file_snapshot = _validated_file_snapshot(
            snapshot.get("file"),
            self.global_id,
        )
        expected_snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "documentGlobalId": self.document_global_id,
            "major": self.major,
            "minor": self.minor,
            "reason": self.reason,
            "effectiveDate": self.effective_date,
            "predecessorRevisionId": self.predecessor_revision_global_id,
            "state": revision_state.value,
            "documentPolicyRef": {
                "globalId": str(self.policy_global_id),
                "version": self.policy_version,
                "snapshotHash": self.policy_snapshot_hash,
            },
            "lockRef": {
                "globalId": self.lock_global_id,
                "version": self.lock_version,
                "holderUserId": self.created_by_user_id,
            },
            "file": file_snapshot,
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at,
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        expected_snapshot_hash = sha256_json(expected_snapshot)
        if snapshot != expected_snapshot or str(self.snapshot_hash) != (
            expected_snapshot_hash
        ):
            frappe.throw(
                _("Revision Snapshot does not match the exact revision content."),
                frappe.ValidationError,
            )
        revision = document_domain_value(
            lambda: DocumentRevision(
                global_id=self.global_id,
                document_global_id=self.document_global_id,
                major=self.major,
                minor=self.minor,
                revision_key=expected_revision_key,
                reason=self.reason,
                effective_date=(
                    None
                    if self.effective_date in (None, "")
                    else date.fromisoformat(self.effective_date)
                ),
                predecessor_revision_id=self.predecessor_revision_global_id,
                state=revision_state,
                policy_ref=DocumentPolicyReference(
                    global_id=self.policy_global_id,
                    version=self.policy_version,
                    snapshot_hash=self.policy_snapshot_hash,
                ),
                snapshot_hash=expected_snapshot_hash,
                version=self.optimistic_version,
            )
        )
        if revision.state is not DocumentRevisionState.DRAFT or revision.version != 1:
            frappe.throw(
                _("A new document revision must remain draft at version one."),
                frappe.ValidationError,
            )
        self.global_id = str(revision.global_id)
        self.document_global_id = str(revision.document_global_id)
        self.revision_key = revision.revision_key
        self.major = revision.major
        self.minor = revision.minor
        self.reason = revision.reason
        self.effective_date = (
            revision.effective_date.isoformat() if revision.effective_date else None
        )
        self.predecessor_revision_global_id = (
            str(revision.predecessor_revision_id)
            if revision.predecessor_revision_id
            else None
        )
        self.policy_global_id = str(revision.policy_ref.global_id)
        self.policy_version = revision.policy_ref.version
        self.policy_snapshot_hash = revision.policy_ref.snapshot_hash
        self.revision_snapshot = canonical_json(expected_snapshot)
        self.snapshot_hash = revision.snapshot_hash
        self.optimistic_version = revision.version

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )


def _validated_file_snapshot(
    value: object,
    revision_global_id: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "globalId",
        "documentRevisionGlobalId",
        "file",
        "displayFileName",
        "role",
        "provenance",
        "connector",
    }:
        frappe.throw(
            _("Revision Snapshot contains an invalid file association."),
            frappe.ValidationError,
        )
    file_value = value.get("file")
    connector = value.get("connector")
    if not isinstance(file_value, dict) or set(file_value) != {
        "globalId",
        "fileDocumentGlobalId",
        "fileRevision",
        "optimisticVersion",
        "fileIdentity",
        "frappeContentHash",
        "fileName",
        "mimeType",
        "sizeBytes",
        "sha256",
        "scanState",
        "scanObservedAt",
        "private",
        "released",
    }:
        frappe.throw(
            _("Revision Snapshot contains an invalid file revision."),
            frappe.ValidationError,
        )
    if not isinstance(connector, dict) or set(connector) != {
        "state",
        "reasonCode",
    }:
        frappe.throw(
            _("Revision Snapshot contains an invalid connector state."),
            frappe.ValidationError,
        )
    try:
        association = document_domain_value(
            lambda: DocumentRevisionFile(
                global_id=value.get("globalId"),
                document_revision_global_id=value.get("documentRevisionGlobalId"),
                file_revision=FileRevisionSnapshot(
                    global_id=file_value.get("globalId"),
                    file_document_global_id=file_value.get("fileDocumentGlobalId"),
                    file_revision=file_value.get("fileRevision"),
                    optimistic_version=file_value.get("optimisticVersion"),
                    frappe_file_id=file_value.get("fileIdentity"),
                    frappe_content_hash=file_value.get("frappeContentHash"),
                    file_name=file_value.get("fileName"),
                    mime_type=file_value.get("mimeType"),
                    size_bytes=file_value.get("sizeBytes"),
                    sha256=file_value.get("sha256"),
                    scan_state=FileScanState(str(file_value.get("scanState"))),
                    scan_observed_at=(
                        None
                        if file_value.get("scanObservedAt") is None
                        else datetime.fromisoformat(
                            str(file_value.get("scanObservedAt")).replace(
                                "Z",
                                "+00:00",
                            )
                        )
                    ),
                    is_private=file_value.get("private"),
                    released=file_value.get("released"),
                ),
                display_file_name=value.get("displayFileName"),
                role=DocumentFileRole(str(value.get("role"))),
                provenance=value.get("provenance"),
                connector_state=ConnectorState(str(connector.get("state"))),
                connector_reason_code=connector.get("reasonCode"),
            )
        )
    except ValueError:
        frappe.throw(
            _("Revision Snapshot contains unsupported file state values."),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.")
    if str(association.document_revision_global_id) != revision_global_id:
        frappe.throw(
            _("Revision Snapshot file does not match the exact revision."),
            frappe.ValidationError,
        )
    if (
        association.connector_state is ConnectorState.UNAVAILABLE
        and association.connector_reason_code != "provider_not_configured"
    ):
        frappe.throw(
            _("The unavailable connector must report that no provider is configured."),
            frappe.ValidationError,
        )
    return association.canonical_dict()
