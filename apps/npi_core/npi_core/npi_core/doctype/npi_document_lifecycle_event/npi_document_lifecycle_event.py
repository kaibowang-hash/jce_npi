from __future__ import annotations

from datetime import date, datetime

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
    nonnegative_integer,
    optional_date_text,
    optional_uuid,
    positive_integer,
    require_document_release_command_write,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_core.documents.release_domain import (
    DocumentLifecycleEvent,
    DocumentLifecycleEventType,
    DocumentLifecycleState,
    DocumentReleasePolicyReference,
)


_ALL_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "document_revision",
    "revision_global_id",
    "event_type",
    "from_state",
    "to_state",
    "from_version",
    "to_version",
    "review_cycle",
    "cycle_global_id",
    "policy_global_id",
    "policy_version",
    "policy_snapshot_hash",
    "evidence_snapshot_hash",
    "confirmation_hashes",
    "replacement_revision_global_id",
    "replacement_effective_date",
    "actor_user_id",
    "occurred_at",
    "request_id",
    "trace_id",
    "event_snapshot",
    "event_hash",
)


class NPIDocumentLifecycleEvent(Document):
    """Append-only exact transition evidence for a document revision."""

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
        self.review_cycle = canonical_uuid(
            self.review_cycle,
            _("Review Cycle"),
        )
        self.cycle_global_id = canonical_uuid(
            self.cycle_global_id,
            _("Review Cycle Global ID"),
        )
        self.policy_global_id = canonical_uuid(
            self.policy_global_id,
            _("Release Policy Global ID"),
        )
        self.replacement_revision_global_id = optional_uuid(
            self.replacement_revision_global_id,
            _("Replacement Revision Global ID"),
        )
        self.replacement_effective_date = optional_date_text(
            self.replacement_effective_date,
            _("Replacement Effective Date"),
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
        if self.review_cycle != self.cycle_global_id:
            frappe.throw(
                _("Review Cycle must match its exact Global ID."),
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
            _("The lifecycle event does not match its document revision."),
        )
        cycle = require_exact_parent(
            "NPI Document Review Cycle",
            self.review_cycle,
            {
                "global_id": self.cycle_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "revision_global_id": self.revision_global_id,
                "policy_global_id": self.policy_global_id,
                "policy_version": self.policy_version,
                "policy_snapshot_hash": self.policy_snapshot_hash,
            },
            _("The lifecycle event does not match its review cycle."),
            extra_fields=("evidence_snapshot_hash",),
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
            _("The lifecycle event release policy is unavailable."),
        )
        try:
            event_type = DocumentLifecycleEventType(str(self.event_type))
            from_state = DocumentLifecycleState(str(self.from_state))
            to_state = DocumentLifecycleState(str(self.to_state))
        except ValueError:
            frappe.throw(
                _("Select supported lifecycle event values."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        confirmation_hashes = tuple(
            lowercase_sha256(value, _("Confirmation Hash"))
            for value in json_array(
                self.confirmation_hashes,
                _("Confirmation Hashes"),
            )
        )
        review_events = {
            DocumentLifecycleEventType.SUBMITTED,
            DocumentLifecycleEventType.RESUBMITTED,
            DocumentLifecycleEventType.REVIEW_APPROVED,
            DocumentLifecycleEventType.REVIEW_REJECTED,
            DocumentLifecycleEventType.APPROVED,
        }
        if event_type in review_events:
            evidence_matches = (
                str(cycle.get("evidence_snapshot_hash"))
                == str(self.evidence_snapshot_hash)
            )
        else:
            confirmation_type = {
                DocumentLifecycleEventType.RELEASED: "release",
                DocumentLifecycleEventType.SUPERSEDED: "supersede",
                DocumentLifecycleEventType.OBSOLETE: "obsolete",
            }[event_type]
            confirmation = frappe.db.get_value(
                "NPI Document Confirmation",
                {
                    "revision_global_id": self.revision_global_id,
                    "cycle_global_id": self.cycle_global_id,
                    "confirmation_type": confirmation_type,
                    "evidence_snapshot_hash": self.evidence_snapshot_hash,
                },
                ["evidence_hash"],
                as_dict=True,
            )
            evidence_matches = bool(
                confirmation
                and str(confirmation.get("evidence_hash"))
                in confirmation_hashes
            )
        if not evidence_matches:
            frappe.throw(
                _("The lifecycle event does not match its review cycle."),
                frappe.ValidationError,
            )
        occurred_at_text = utc_datetime_text(
            self.occurred_at,
            _("Occurred At"),
        )
        occurred_at = datetime.fromisoformat(
            occurred_at_text.replace("Z", "+00:00")
        )
        event = document_domain_value(
            lambda: DocumentLifecycleEvent(
                global_id=self.global_id,
                revision_global_id=self.revision_global_id,
                event_type=event_type,
                from_state=from_state,
                to_state=to_state,
                from_version=nonnegative_integer(
                    self.from_version,
                    _("From Lifecycle Version"),
                ),
                to_version=positive_integer(
                    self.to_version,
                    _("To Lifecycle Version"),
                ),
                cycle_global_id=self.cycle_global_id,
                policy_ref=DocumentReleasePolicyReference(
                    global_id=self.policy_global_id,
                    version=self.policy_version,
                    snapshot_hash=self.policy_snapshot_hash,
                ),
                evidence_snapshot_hash=self.evidence_snapshot_hash,
                confirmation_hashes=confirmation_hashes,
                replacement_revision_global_id=(
                    self.replacement_revision_global_id
                ),
                replacement_effective_date=(
                    date.fromisoformat(self.replacement_effective_date)
                    if self.replacement_effective_date
                    else None
                ),
                actor_user_id=self.actor_user_id,
                occurred_at=occurred_at,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
        )
        expected_snapshot = event.event_payload()
        supplied_snapshot = json_object(
            self.event_snapshot,
            _("Lifecycle Event Snapshot"),
        )
        if supplied_snapshot != expected_snapshot or self.event_hash not in (
            None,
            "",
            event.event_hash,
        ):
            frappe.throw(
                _("Lifecycle Event Snapshot does not match the exact transition."),
                frappe.ValidationError,
            )
        self.global_id = str(event.global_id)
        self.revision_global_id = str(event.revision_global_id)
        self.event_type = event.event_type.value
        self.from_state = event.from_state.value
        self.to_state = event.to_state.value
        self.from_version = event.from_version
        self.to_version = event.to_version
        self.cycle_global_id = str(event.cycle_global_id)
        self.policy_global_id = str(event.policy_ref.global_id)
        self.policy_version = event.policy_ref.version
        self.policy_snapshot_hash = event.policy_ref.snapshot_hash
        self.evidence_snapshot_hash = event.evidence_snapshot_hash
        self.confirmation_hashes = canonical_json(
            list(event.confirmation_hashes)
        )
        self.replacement_revision_global_id = (
            str(event.replacement_revision_global_id)
            if event.replacement_revision_global_id
            else None
        )
        self.replacement_effective_date = (
            event.replacement_effective_date.isoformat()
            if event.replacement_effective_date
            else None
        )
        self.actor_user_id = actor_text(
            event.actor_user_id,
            _("Actor User ID"),
        )
        self.occurred_at = frappe_utc_datetime_text(
            event.occurred_at,
            _("Occurred At"),
        )
        self.request_id = required_text(event.request_id, _("Request ID"), 128)
        self.trace_id = required_text(event.trace_id, _("Trace ID"), 128)
        self.event_snapshot = canonical_json(expected_snapshot)
        self.event_hash = event.event_hash

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.to_version,
        )
