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
    json_object,
    require_document_release_command_write,
    require_exact_parent,
    required_text,
    tenant_text,
    utc_datetime_text,
)
from npi_core.documents.release_domain import (
    DocumentConfirmation,
    DocumentConfirmationType,
    DocumentReleasePolicyReference,
)


_ALL_FIELDS = (
    "global_id",
    "confirmation_key",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "document_revision",
    "revision_global_id",
    "review_cycle",
    "cycle_global_id",
    "policy_global_id",
    "policy_version",
    "policy_snapshot_hash",
    "evidence_snapshot_hash",
    "confirmation_type",
    "actor_user_id",
    "authority_slot",
    "confirmation_method",
    "confirmation_intent",
    "confirmed",
    "reason",
    "confirmed_at",
    "request_id",
    "trace_id",
    "confirmation_evidence",
    "evidence_hash",
)


class NPIDocumentConfirmation(Document):
    """Append-only authenticated electronic confirmation evidence."""

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
            _("The confirmation does not match its document revision."),
        )
        require_exact_parent(
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
                "evidence_snapshot_hash": self.evidence_snapshot_hash,
            },
            _("The confirmation does not match its review cycle."),
        )
        try:
            confirmation_type = DocumentConfirmationType(
                str(self.confirmation_type)
            )
        except ValueError:
            frappe.throw(
                _("Select a supported confirmation type."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        confirmed_at_text = utc_datetime_text(
            self.confirmed_at,
            _("Confirmed At"),
        )
        confirmed_at = datetime.fromisoformat(
            confirmed_at_text.replace("Z", "+00:00")
        )
        confirmation = document_domain_value(
            lambda: DocumentConfirmation(
                global_id=self.global_id,
                confirmation_key=self.confirmation_key,
                confirmation_type=confirmation_type,
                revision_global_id=self.revision_global_id,
                cycle_global_id=self.cycle_global_id,
                policy_ref=DocumentReleasePolicyReference(
                    global_id=self.policy_global_id,
                    version=self.policy_version,
                    snapshot_hash=self.policy_snapshot_hash,
                ),
                evidence_snapshot_hash=self.evidence_snapshot_hash,
                actor_user_id=self.actor_user_id,
                authority_slot=self.authority_slot,
                confirmation_method=self.confirmation_method,
                confirmation_intent=self.confirmation_intent,
                confirmed=(
                    type(self.confirmed) in {int, bool}
                    and int(self.confirmed) == 1
                ),
                reason=(
                    required_text(self.reason, _("Confirmation Reason"), 2000)
                    if self.reason not in (None, "")
                    else None
                ),
                confirmed_at=confirmed_at,
                request_id=self.request_id,
                trace_id=self.trace_id,
            )
        )
        expected_evidence = confirmation.evidence_payload()
        supplied_evidence = json_object(
            self.confirmation_evidence,
            _("Confirmation Evidence"),
        )
        if supplied_evidence != expected_evidence or self.evidence_hash not in (
            None,
            "",
            confirmation.evidence_hash,
        ):
            frappe.throw(
                _("Confirmation Evidence does not match the exact action."),
                frappe.ValidationError,
            )
        self.global_id = str(confirmation.global_id)
        self.confirmation_key = confirmation.confirmation_key
        self.confirmation_type = confirmation.confirmation_type.value
        self.revision_global_id = str(confirmation.revision_global_id)
        self.cycle_global_id = str(confirmation.cycle_global_id)
        self.policy_global_id = str(confirmation.policy_ref.global_id)
        self.policy_version = confirmation.policy_ref.version
        self.policy_snapshot_hash = confirmation.policy_ref.snapshot_hash
        self.evidence_snapshot_hash = confirmation.evidence_snapshot_hash
        self.actor_user_id = actor_text(
            confirmation.actor_user_id,
            _("Actor User ID"),
        )
        self.authority_slot = confirmation.authority_slot
        self.confirmation_method = confirmation.confirmation_method
        self.confirmation_intent = confirmation.confirmation_intent
        self.confirmed = 1
        self.reason = confirmation.reason
        self.confirmed_at = frappe_utc_datetime_text(
            confirmation.confirmed_at,
            _("Confirmed At"),
        )
        self.request_id = required_text(
            confirmation.request_id,
            _("Request ID"),
            128,
        )
        self.trace_id = required_text(
            confirmation.trace_id,
            _("Trace ID"),
            128,
        )
        self.confirmation_evidence = canonical_json(expected_evidence)
        self.evidence_hash = confirmation.evidence_hash

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=1,
        )
