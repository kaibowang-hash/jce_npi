from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    deny_document_history_update,
    document_domain_value,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    positive_integer,
    require_document_release_command_write,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_core.documents.release_domain import (
    DocumentReleasePolicyReference,
    DocumentReviewCycle,
    DocumentReviewerAssignment,
)
from npi_core.documents.release_frappe import review_evidence_value


_ALL_FIELDS = (
    "global_id",
    "cycle_key",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "document_revision",
    "revision_global_id",
    "cycle_number",
    "policy_global_id",
    "policy_version",
    "policy_snapshot_hash",
    "review_evidence",
    "evidence_snapshot_hash",
    "reviewer_assignments",
    "required_approval_count",
    "prior_rejected_cycle_global_id",
    "submitted_by_user_id",
    "submitted_at",
    "request_id",
    "trace_id",
    "cycle_snapshot",
    "snapshot_hash",
)


class NPIDocumentReviewCycle(Document):
    """Append-only exact review assignment and evidence snapshot."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_document_release_command_write()

    def before_save(self) -> None:
        require_document_release_command_write()
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
        self.revision_global_id = canonical_uuid(
            self.revision_global_id,
            _("Revision Global ID"),
        )
        self.policy_global_id = canonical_uuid(
            self.policy_global_id,
            _("Release Policy Global ID"),
        )
        self.prior_rejected_cycle_global_id = optional_uuid(
            self.prior_rejected_cycle_global_id,
            _("Prior Rejected Cycle Global ID"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_document_history_update()
        if self.document_revision != self.revision_global_id:
            frappe.throw(
                _("Document Revision must match its exact Global ID."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Document Revision",
            self.document_revision,
            {
                "global_id": self.revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
            },
            _("The review cycle does not match its document revision."),
            extra_fields=("snapshot_hash",),
        )
        require_exact_parent(
            "NPI Document Release Policy Version",
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
            _("The review-cycle release policy is unavailable."),
        )
        evidence = document_domain_value(
            lambda: review_evidence_value(self.review_evidence)
        )
        if str(evidence.revision_global_id) != self.revision_global_id:
            frappe.throw(
                _("Review Evidence must match the exact revision."),
                frappe.ValidationError,
            )
        if self.evidence_snapshot_hash not in (
            None,
            "",
            evidence.snapshot_hash,
        ):
            frappe.throw(
                _("Evidence Snapshot Hash does not match the review evidence."),
                frappe.ValidationError,
            )
        assignments_value = json_array(
            self.reviewer_assignments,
            _("Reviewer Assignments"),
        )
        if not all(
            isinstance(value, dict) and set(value) == {"slotKey", "userId"}
            for value in assignments_value
        ):
            frappe.throw(
                _("Reviewer Assignments must contain only valid assignments."),
                frappe.ValidationError,
            )
        assignments = tuple(
            DocumentReviewerAssignment(
                slot_key=value.get("slotKey"),
                user_id=value.get("userId"),
            )
            for value in assignments_value
        )
        submitted_at_text = utc_datetime_text(
            self.submitted_at,
            _("Submitted At"),
        )
        submitted_at = datetime.fromisoformat(
            submitted_at_text.replace("Z", "+00:00")
        )
        cycle = document_domain_value(
            lambda: DocumentReviewCycle(
                global_id=self.global_id,
                revision_global_id=self.revision_global_id,
                cycle_number=positive_integer(
                    self.cycle_number,
                    _("Review Cycle Number"),
                ),
                policy_ref=DocumentReleasePolicyReference(
                    global_id=self.policy_global_id,
                    version=self.policy_version,
                    snapshot_hash=self.policy_snapshot_hash,
                ),
                evidence=evidence,
                reviewer_assignments=assignments,
                required_approval_count=positive_integer(
                    self.required_approval_count,
                    _("Required Approval Count"),
                ),
                prior_rejected_cycle_global_id=(
                    self.prior_rejected_cycle_global_id
                ),
                submitted_by_user_id=self.submitted_by_user_id,
                submitted_at=submitted_at,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
        )
        expected_cycle_key = (
            f"{cycle.revision_global_id}:{cycle.cycle_number}"
        )
        expected_snapshot = cycle.snapshot_payload()
        supplied_snapshot = json_object(
            self.cycle_snapshot,
            _("Review Cycle Snapshot"),
        )
        if self.cycle_key not in (None, "", expected_cycle_key) or (
            supplied_snapshot != expected_snapshot
            or self.snapshot_hash not in (None, "", cycle.snapshot_hash)
        ):
            frappe.throw(
                _("Review Cycle Snapshot does not match the exact review input."),
                frappe.ValidationError,
            )
        self.global_id = str(cycle.global_id)
        self.cycle_key = expected_cycle_key
        self.revision_global_id = str(cycle.revision_global_id)
        self.cycle_number = cycle.cycle_number
        self.policy_global_id = str(cycle.policy_ref.global_id)
        self.policy_version = cycle.policy_ref.version
        self.policy_snapshot_hash = cycle.policy_ref.snapshot_hash
        self.review_evidence = canonical_json(cycle.evidence.canonical_dict())
        self.evidence_snapshot_hash = cycle.evidence.snapshot_hash
        self.reviewer_assignments = canonical_json(
            [value.canonical_dict() for value in cycle.reviewer_assignments]
        )
        self.required_approval_count = cycle.required_approval_count
        self.prior_rejected_cycle_global_id = (
            str(cycle.prior_rejected_cycle_global_id)
            if cycle.prior_rejected_cycle_global_id
            else None
        )
        self.submitted_by_user_id = actor_text(
            cycle.submitted_by_user_id,
            _("Submitted By"),
        )
        self.submitted_at = frappe_utc_datetime_text(
            cycle.submitted_at,
            _("Submitted At"),
        )
        self.request_id = required_text(cycle.request_id, _("Request ID"), 128)
        self.trace_id = required_text(cycle.trace_id, _("Trace ID"), 128)
        self.cycle_snapshot = canonical_json(expected_snapshot)
        self.snapshot_hash = lowercase_sha256(
            cycle.snapshot_hash,
            _("Review Cycle Snapshot Hash"),
        )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.cycle_number,
        )
