from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_uuid,
    deny_document_history_delete,
    document_domain_value,
    frappe_utc_datetime_text,
    lowercase_sha256,
    optional_date_text,
    optional_uuid,
    positive_integer,
    require_document_release_command_write,
    require_exact_parent,
    required_text,
    tenant_text,
)
from npi_core.documents.release_domain import (
    DocumentLifecycleState,
    DocumentRevisionLifecycle,
)


_IDENTITY_FIELDS = (
    "global_id",
    "tenant_id",
    "project_global_id",
    "document_global_id",
    "document_revision",
    "revision_global_id",
)


class NPIDocumentRevisionLifecycle(Document):
    """Guarded current-state projection over immutable revision history."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_document_release_command_write()

    def before_save(self) -> None:
        require_document_release_command_write()

    def before_validate(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.tenant_id = tenant_text(self.tenant_id)
        self.project_global_id = canonical_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.document_global_id = canonical_uuid(
            self.document_global_id,
            _("Controlled Document"),
        )
        self.document_revision = canonical_uuid(
            self.document_revision,
            _("Document Revision"),
        )
        self.revision_global_id = canonical_uuid(
            self.revision_global_id,
            _("Revision Global ID"),
        )
        for fieldname, label in (
            ("active_cycle_global_id", _("Active Review Cycle Global ID")),
            ("approved_cycle_global_id", _("Approved Review Cycle Global ID")),
            ("approved_event_global_id", _("Approved Event Global ID")),
            ("release_event_global_id", _("Release Event Global ID")),
            (
                "replacement_revision_global_id",
                _("Replacement Revision Global ID"),
            ),
            ("terminal_event_global_id", _("Terminal Event Global ID")),
        ):
            setattr(self, fieldname, optional_uuid(getattr(self, fieldname), label))
        self.last_event_global_id = canonical_uuid(
            self.last_event_global_id,
            _("Last Lifecycle Event"),
        )
        self.replacement_effective_date = optional_date_text(
            self.replacement_effective_date,
            _("Replacement Effective Date"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _IDENTITY_FIELDS)
        if (
            self.global_id != self.revision_global_id
            or self.document_revision != self.revision_global_id
        ):
            frappe.throw(
                _("Lifecycle identity must match the exact document revision."),
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
            _("The lifecycle projection does not match its document revision."),
        )
        try:
            current_state = DocumentLifecycleState(str(self.current_state))
        except ValueError:
            frappe.throw(
                _("Select a supported document lifecycle state."),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.")
        lifecycle_version = positive_integer(
            self.lifecycle_version,
            _("Lifecycle Version"),
        )
        event = require_exact_parent(
            "NPI Document Lifecycle Event",
            self.last_event_global_id,
            {
                "global_id": self.last_event_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "revision_global_id": self.revision_global_id,
                "to_state": current_state.value,
                "to_version": lifecycle_version,
            },
            _("The lifecycle projection does not match its exact last event."),
            extra_fields=("from_state", "from_version"),
        )
        if previous is None:
            valid_predecessor = (
                str(event.get("from_state")) == DocumentLifecycleState.DRAFT.value
                and int(event.get("from_version") or 0) == 0
                and current_state is DocumentLifecycleState.IN_REVIEW
                and lifecycle_version == 1
            )
        else:
            valid_predecessor = (
                str(event.get("from_state")) == str(previous.get("current_state"))
                and int(event.get("from_version") or 0)
                == int(previous.get("lifecycle_version") or 0)
                and lifecycle_version
                == int(previous.get("lifecycle_version") or 0) + 1
            )
        if not valid_predecessor:
            frappe.throw(
                _("The lifecycle projection must advance from its exact prior state."),
                frappe.ValidationError,
            )
        lifecycle = document_domain_value(
            lambda: DocumentRevisionLifecycle(
                revision_global_id=self.revision_global_id,
                state=current_state,
                version=lifecycle_version,
                active_cycle_global_id=self.active_cycle_global_id,
                approved_cycle_global_id=self.approved_cycle_global_id,
                approved_event_global_id=self.approved_event_global_id,
                release_event_global_id=self.release_event_global_id,
                release_snapshot_hash=(
                    lowercase_sha256(
                        self.release_snapshot_hash,
                        _("Release Snapshot Hash"),
                    )
                    if self.release_snapshot_hash not in (None, "")
                    else None
                ),
                replacement_revision_global_id=(
                    self.replacement_revision_global_id
                ),
                replacement_effective_date=(
                    date.fromisoformat(self.replacement_effective_date)
                    if self.replacement_effective_date
                    else None
                ),
                terminal_event_global_id=self.terminal_event_global_id,
            )
        )
        self.global_id = str(lifecycle.revision_global_id)
        self.document_revision = str(lifecycle.revision_global_id)
        self.revision_global_id = str(lifecycle.revision_global_id)
        self.current_state = lifecycle.state.value
        self.lifecycle_version = lifecycle.version
        self.active_cycle_global_id = (
            str(lifecycle.active_cycle_global_id)
            if lifecycle.active_cycle_global_id
            else None
        )
        self.approved_cycle_global_id = (
            str(lifecycle.approved_cycle_global_id)
            if lifecycle.approved_cycle_global_id
            else None
        )
        self.approved_event_global_id = (
            str(lifecycle.approved_event_global_id)
            if lifecycle.approved_event_global_id
            else None
        )
        self.release_event_global_id = (
            str(lifecycle.release_event_global_id)
            if lifecycle.release_event_global_id
            else None
        )
        self.release_snapshot_hash = lifecycle.release_snapshot_hash
        self.replacement_revision_global_id = (
            str(lifecycle.replacement_revision_global_id)
            if lifecycle.replacement_revision_global_id
            else None
        )
        self.replacement_effective_date = (
            lifecycle.replacement_effective_date.isoformat()
            if lifecycle.replacement_effective_date
            else None
        )
        self.terminal_event_global_id = (
            str(lifecycle.terminal_event_global_id)
            if lifecycle.terminal_event_global_id
            else None
        )
        self.updated_by_user_id = actor_text(
            self.updated_by_user_id,
            _("Updated By"),
        )
        self.updated_at = frappe_utc_datetime_text(
            self.updated_at,
            _("Updated At"),
        )
        self.request_id = required_text(self.request_id, _("Request ID"), 128)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.lifecycle_version,
        )
