from __future__ import annotations

from datetime import datetime
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.baseline_domain import (
    DocumentBaseline,
    DocumentBaselineMember,
    DocumentBaselinePolicyReference,
)
from npi_core.documents.baseline_frappe import (
    require_document_baseline_command_write,
)
from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    deny_document_history_update,
    document_domain_value,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    positive_integer,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_core.documents.release_frappe import review_evidence_value


_ALL_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "label",
    "baseline_version",
    "policy_global_id",
    "policy_version",
    "policy_snapshot_hash",
    "member_count",
    "baseline_snapshot",
    "snapshot_hash",
    "created_by_user_id",
    "created_at",
    "request_id",
    "trace_id",
)
_MEMBER_KEYS = {
    "globalId",
    "sequence",
    "documentGlobalId",
    "revisionGlobalId",
    "major",
    "minor",
    "revisionSnapshotHash",
    "lifecycleVersion",
    "releaseEventGlobalId",
    "releaseSnapshotHash",
    "releaseEvidence",
}


class NPIDocumentBaseline(Document):
    """Append-only exact release package of document and file revisions."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_document_baseline_command_write()

    def before_save(self) -> None:
        require_document_baseline_command_write()
        if self.get_doc_before_save() is not None:
            deny_document_history_update()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.policy_global_id = canonical_uuid(
            self.policy_global_id,
            _("Baseline Policy Global ID"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_document_history_update()
        require_exact_parent(
            "NPI Engineering Project",
            self.project_global_id,
            {
                "global_id": self.project_global_id,
                "tenant_id": self.tenant_id,
            },
            _("The document baseline does not match its Project and tenant."),
        )
        require_exact_parent(
            "NPI Document Baseline Policy Version",
            {
                "policy_global_id": self.policy_global_id,
                "policy_version": self.policy_version,
            },
            {
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "publication_state": "published",
                "snapshot_hash": self.policy_snapshot_hash,
            },
            _("The exact published baseline policy is unavailable."),
        )
        supplied_snapshot = json_object(
            self.baseline_snapshot,
            _("Canonical Baseline Snapshot"),
        )
        members_value = supplied_snapshot.get("members")
        if not isinstance(members_value, list):
            frappe.throw(
                _("Canonical Baseline Snapshot must contain exact members."),
                frappe.ValidationError,
            )
        members = tuple(self._member(value) for value in members_value)
        created_at_text = utc_datetime_text(self.created_at, _("Created At"))
        baseline = document_domain_value(
            lambda: DocumentBaseline(
                global_id=UUID(self.global_id),
                tenant_id=self.tenant_id,
                project_global_id=UUID(self.project_global_id),
                label=self.label,
                policy_ref=DocumentBaselinePolicyReference(
                    UUID(self.policy_global_id),
                    self.policy_version,
                    self.policy_snapshot_hash,
                ),
                members=members,
                created_by_user_id=self.created_by_user_id,
                created_at=datetime.fromisoformat(
                    created_at_text.replace("Z", "+00:00")
                ),
                request_id=self.request_id,
                trace_id=self.trace_id,
                version=self.baseline_version,
                snapshot_hash=str(self.snapshot_hash or ""),
            )
        )
        expected_snapshot = baseline.snapshot_payload()
        if supplied_snapshot != expected_snapshot:
            frappe.throw(
                _("Canonical Baseline Snapshot does not match its exact members."),
                frappe.ValidationError,
            )
        expected_member_count = len(baseline.members)
        if positive_integer(self.member_count, _("Member Count")) != expected_member_count:
            frappe.throw(
                _("Member Count does not match the baseline snapshot."),
                frappe.ValidationError,
            )
        self.label = required_text(baseline.label, _("Baseline Label"), 140)
        self.baseline_version = baseline.version
        self.policy_version = baseline.policy_ref.version
        self.policy_snapshot_hash = lowercase_sha256(
            baseline.policy_ref.snapshot_hash,
            _("Baseline Policy Snapshot Hash"),
        )
        self.member_count = expected_member_count
        self.baseline_snapshot = canonical_json(expected_snapshot)
        self.snapshot_hash = lowercase_sha256(
            baseline.snapshot_hash,
            _("Baseline Snapshot Hash"),
        )
        self.created_by_user_id = actor_text(
            baseline.created_by_user_id,
            _("Created By User ID"),
        )
        self.created_at = frappe_utc_datetime_text(
            baseline.created_at,
            _("Created At"),
        )
        self.request_id = required_text(self.request_id, _("Request ID"), 128)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=1,
        )

    @staticmethod
    def _member(value: object) -> DocumentBaselineMember:
        if not isinstance(value, dict) or set(value) != _MEMBER_KEYS:
            frappe.throw(
                _("Canonical Baseline Snapshot contains an invalid member."),
                frappe.ValidationError,
            )
        return document_domain_value(
            lambda: DocumentBaselineMember(
                global_id=_snapshot_uuid(value.get("globalId"), _("Global ID")),
                sequence=value.get("sequence"),
                document_global_id=_snapshot_uuid(
                    value.get("documentGlobalId"),
                    _("Document Global ID"),
                ),
                revision_global_id=_snapshot_uuid(
                    value.get("revisionGlobalId"),
                    _("Revision Global ID"),
                ),
                major=value.get("major"),
                minor=value.get("minor"),
                revision_snapshot_hash=value.get("revisionSnapshotHash"),
                lifecycle_version=value.get("lifecycleVersion"),
                release_event_global_id=_snapshot_uuid(
                    value.get("releaseEventGlobalId"),
                    _("Release Event Global ID"),
                ),
                release_snapshot_hash=value.get("releaseSnapshotHash"),
                release_evidence=review_evidence_value(
                    value.get("releaseEvidence")
                ),
            )
        )


def _snapshot_uuid(value: object, label: str) -> UUID:
    return UUID(canonical_uuid(value, label))
