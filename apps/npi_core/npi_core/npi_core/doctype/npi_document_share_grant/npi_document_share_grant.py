from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.domain import sha256_json
from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    json_object,
    lowercase_sha256,
    required_text,
    require_exact_parent,
    require_document_command_write,
    tenant_text,
    utc_datetime_text,
)


_IDENTITY_FIELDS = (
    "global_id",
    "grant_key",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "document_revision_global_id",
    "document_revision_snapshot_hash",
    "revision_file_global_id",
    "revision_file_snapshot_hash",
    "file_revision_global_id",
    "share_label",
    "share_label_hash",
    "expires_at",
    "retrieval_state",
    "retrieval_reason_code",
    "grant_snapshot",
    "snapshot_hash",
    "created_by_user_id",
    "created_at",
    "request_id",
    "trace_id",
)
_CLOSED_STATES = {"revoked", "expired"}
_MAX_SYNTHETIC_TTL = timedelta(days=30)


class NPIDocumentShareGrant(Document):
    """Prepared metadata only; P5-01 deliberately has no redemption capability."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_document_command_write()

    def before_save(self) -> None:
        require_document_command_write()

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
        self.document_revision_global_id = canonical_uuid(
            self.document_revision_global_id,
            _("Document Revision Global ID"),
        )
        self.revision_file_global_id = canonical_uuid(
            self.revision_file_global_id,
            _("Revision File"),
        )
        self.file_revision_global_id = canonical_uuid(
            self.file_revision_global_id,
            _("File Revision Global ID"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        self.document_revision_snapshot_hash = lowercase_sha256(
            self.document_revision_snapshot_hash,
            _("Document Revision Snapshot Hash"),
        )
        self.revision_file_snapshot_hash = lowercase_sha256(
            self.revision_file_snapshot_hash,
            _("Revision File Snapshot Hash"),
        )
        require_exact_parent(
            "NPI Controlled Document",
            self.document_global_id,
            {
                "global_id": self.document_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
            },
            _("The share grant does not match its controlled document."),
        )
        require_exact_parent(
            "NPI Document Revision",
            self.document_revision_global_id,
            {
                "global_id": self.document_revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "snapshot_hash": self.document_revision_snapshot_hash,
            },
            _("The share grant does not match its document revision."),
        )
        require_exact_parent(
            "NPI Document Revision File",
            self.revision_file_global_id,
            {
                "global_id": self.revision_file_global_id,
                "file_revision_global_id": self.file_revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "document_revision_global_id": self.document_revision_global_id,
                "snapshot_hash": self.revision_file_snapshot_hash,
            },
            _("The share grant does not match its exact file revision."),
        )
        self.share_label = required_text(
            self.share_label,
            _("Share Label"),
            140,
        )
        expected_label_hash = hashlib.sha256(
            self.share_label.casefold().encode("utf-8")
        ).hexdigest()
        if (
            lowercase_sha256(
                self.share_label_hash,
                _("Share Label Hash"),
            )
            != expected_label_hash
        ):
            frappe.throw(
                _("Share Label Hash does not match the normalized Share Label."),
                frappe.ValidationError,
            )
        self.share_label_hash = expected_label_hash
        self.created_by_user_id = actor_text(
            self.created_by_user_id,
            _("Created By"),
        )
        self.created_at = utc_datetime_text(self.created_at, _("Created At"))
        self.expires_at = utc_datetime_text(self.expires_at, _("Expires At"))
        created_at = _as_datetime(self.created_at)
        expires_at = _as_datetime(self.expires_at)
        if expires_at <= created_at or expires_at - created_at > (_MAX_SYNTHETIC_TTL):
            frappe.throw(
                _(
                    "The disabled share grant expiry must follow creation within the bounded synthetic limit."
                ),
                frappe.ValidationError,
            )
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
        expected_grant_key = sha256_json(
            {
                "tenantId": self.tenant_id,
                "projectGlobalId": self.project_global_id,
                "documentGlobalId": self.document_global_id,
                "documentRevisionGlobalId": self.document_revision_global_id,
                "documentRevisionSnapshotHash": (self.document_revision_snapshot_hash),
                "revisionFileGlobalId": self.revision_file_global_id,
                "revisionFileSnapshotHash": self.revision_file_snapshot_hash,
                "fileRevisionGlobalId": self.file_revision_global_id,
                "shareLabelHash": self.share_label_hash,
            }
        )
        if self.grant_key not in (None, "", expected_grant_key):
            frappe.throw(
                _("Share Grant Key does not match the exact share grant."),
                frappe.ValidationError,
            )
        self.grant_key = expected_grant_key
        if (
            self.retrieval_state != "unavailable"
            or self.retrieval_reason_code != "external_access_policy_unavailable"
        ):
            frappe.throw(
                _("External document retrieval is unavailable."),
                frappe.ValidationError,
            )
        grant_snapshot = {
            "schemaVersion": 1,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "documentGlobalId": self.document_global_id,
            "documentRevisionGlobalId": self.document_revision_global_id,
            "documentRevisionSnapshotHash": self.document_revision_snapshot_hash,
            "revisionFileGlobalId": self.revision_file_global_id,
            "revisionFileSnapshotHash": self.revision_file_snapshot_hash,
            "fileRevisionGlobalId": self.file_revision_global_id,
            "shareLabelHash": self.share_label_hash,
            "expiresAt": self.expires_at,
            "retrievalState": "unavailable",
            "retrievalReasonCode": "external_access_policy_unavailable",
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at,
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        expected_snapshot_hash = sha256_json(grant_snapshot)
        if (
            json_object(self.grant_snapshot, _("Share Grant Snapshot"))
            != grant_snapshot
            or str(self.snapshot_hash) != expected_snapshot_hash
        ):
            frappe.throw(
                _("Share Grant Snapshot does not match its exact scope."),
                frappe.ValidationError,
            )
        self.grant_snapshot = canonical_json(grant_snapshot)
        self.snapshot_hash = expected_snapshot_hash
        if self.share_state not in {"prepared", *_CLOSED_STATES}:
            frappe.throw(
                _("Select a supported share grant state."),
                frappe.ValidationError,
            )
        if previous is None:
            if self.share_state != "prepared" or self.optimistic_version != 1:
                frappe.throw(
                    _("A new share grant must start prepared at version one."),
                    frappe.ValidationError,
                )
        elif (
            str(previous.get("share_state")) != "prepared"
            or self.share_state not in _CLOSED_STATES
            or self.optimistic_version
            != int(previous.get("optimistic_version") or 0) + 1
        ):
            frappe.throw(
                _("The share grant state transition is not allowed."),
                frappe.ValidationError,
            )
        if self.share_state == "prepared":
            if any(
                value not in (None, "")
                for value in (
                    self.closed_at,
                    self.closed_by_user_id,
                    self.closure_reason,
                )
            ):
                frappe.throw(
                    _("A prepared share grant cannot contain closure details."),
                    frappe.ValidationError,
                )
        else:
            self.closed_at = utc_datetime_text(self.closed_at, _("Closed At"))
            self.closed_by_user_id = actor_text(
                self.closed_by_user_id,
                _("Closed By"),
            )
            if self.share_state == "revoked":
                self.closure_reason = required_text(
                    self.closure_reason,
                    _("Closure Reason"),
                    1000,
                )
            elif self.closure_reason not in (None, ""):
                frappe.throw(
                    _("Only a revoked share grant records a closure reason."),
                    frappe.ValidationError,
                )
            if (
                self.share_state == "expired"
                and _as_datetime(self.closed_at) < expires_at
            ):
                frappe.throw(
                    _("A share grant cannot expire before its expiry time."),
                    frappe.ValidationError,
                )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.optimistic_version,
        )


def _as_datetime(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        frappe.throw(
            _("Enter a valid date and time."),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.") from error
    return parsed
