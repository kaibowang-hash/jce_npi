from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.baseline_frappe import (
    baseline_member_value,
    require_document_baseline_command_write,
)
from npi_core.documents.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    deny_document_history_update,
    document_domain_value,
    frappe_utc_datetime_text,
    json_object,
    lowercase_sha256,
    nonnegative_integer,
    positive_integer,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)


_ALL_FIELDS = (
    "global_id",
    "member_key",
    "document_baseline",
    "baseline_global_id",
    "baseline_snapshot_hash",
    "tenant_id",
    "project_global_id",
    "member_sequence",
    "controlled_document",
    "document_global_id",
    "document_revision",
    "revision_global_id",
    "major",
    "minor",
    "revision_snapshot_hash",
    "lifecycle_version",
    "release_event_global_id",
    "release_snapshot_hash",
    "release_evidence",
    "member_snapshot",
    "member_hash",
    "created_at",
)


class NPIDocumentBaselineMember(Document):
    """Append-only exact released revision within one immutable baseline."""

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
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("baseline_global_id", _("Baseline Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("document_global_id", _("Document Global ID")),
            ("revision_global_id", _("Revision Global ID")),
            ("release_event_global_id", _("Release Event Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.document_baseline = canonical_uuid(
            self.document_baseline,
            _("Document Baseline"),
        )
        self.controlled_document = canonical_uuid(
            self.controlled_document,
            _("Controlled Document"),
        )
        self.document_revision = canonical_uuid(
            self.document_revision,
            _("Document Revision"),
        )

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_document_history_update()
        if self.document_baseline != self.baseline_global_id:
            frappe.throw(
                _("Document Baseline must match its exact Global ID."),
                frappe.ValidationError,
            )
        if self.controlled_document != self.document_global_id:
            frappe.throw(
                _("Controlled Document must match its exact Global ID."),
                frappe.ValidationError,
            )
        if self.document_revision != self.revision_global_id:
            frappe.throw(
                _("Document Revision must match its exact Global ID."),
                frappe.ValidationError,
            )
        baseline = require_exact_parent(
            "NPI Document Baseline",
            self.document_baseline,
            {
                "global_id": self.baseline_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "snapshot_hash": self.baseline_snapshot_hash,
            },
            _("The baseline member does not match its immutable baseline."),
            extra_fields=("baseline_snapshot", "created_at"),
        )
        require_exact_parent(
            "NPI Controlled Document",
            self.controlled_document,
            {
                "global_id": self.document_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
            },
            _("The baseline member does not match its controlled document."),
        )
        require_exact_parent(
            "NPI Document Revision",
            self.document_revision,
            {
                "global_id": self.revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "major": self.major,
                "minor": self.minor,
                "snapshot_hash": self.revision_snapshot_hash,
            },
            _("The baseline member does not match its exact document revision."),
        )
        require_exact_parent(
            "NPI Document Revision Lifecycle",
            self.revision_global_id,
            {
                "revision_global_id": self.revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "current_state": "released",
                "lifecycle_version": self.lifecycle_version,
                "release_event_global_id": self.release_event_global_id,
                "release_snapshot_hash": self.release_snapshot_hash,
            },
            _("The baseline member is not the exact released document revision."),
        )
        self.member_sequence = positive_integer(
            self.member_sequence,
            _("Member Sequence"),
        )
        self.major = nonnegative_integer(self.major, _("Major Revision"))
        self.minor = nonnegative_integer(self.minor, _("Minor Revision"))
        self.lifecycle_version = positive_integer(
            self.lifecycle_version,
            _("Lifecycle Version"),
        )
        self.baseline_snapshot_hash = lowercase_sha256(
            self.baseline_snapshot_hash,
            _("Baseline Snapshot Hash"),
        )
        self.revision_snapshot_hash = lowercase_sha256(
            self.revision_snapshot_hash,
            _("Revision Snapshot Hash"),
        )
        self.release_snapshot_hash = lowercase_sha256(
            self.release_snapshot_hash,
            _("Release Snapshot Hash"),
        )
        member = document_domain_value(lambda: baseline_member_value(self))
        require_exact_parent(
            "NPI Document Lifecycle Event",
            self.release_event_global_id,
            {
                "global_id": self.release_event_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": self.document_global_id,
                "revision_global_id": self.revision_global_id,
                "event_type": "released",
                "to_state": "released",
                "to_version": self.lifecycle_version,
                "evidence_snapshot_hash": member.release_evidence.snapshot_hash,
            },
            _("The baseline member release event is unavailable."),
        )
        expected_snapshot = member.canonical_dict()
        supplied_snapshot = json_object(
            self.member_snapshot,
            _("Canonical Baseline Member Snapshot"),
        )
        baseline_snapshot = json_object(
            baseline.get("baseline_snapshot"),
            _("Canonical Baseline Snapshot"),
        )
        members = baseline_snapshot.get("members")
        expected_key = f"{self.baseline_global_id}:{member.sequence}"
        if (
            self.member_key not in (None, "", expected_key)
            or supplied_snapshot != expected_snapshot
            or not isinstance(members, list)
            or expected_snapshot not in members
            or self.member_hash not in (None, "", member.member_hash)
        ):
            frappe.throw(
                _("Baseline Member Snapshot does not match its immutable baseline."),
                frappe.ValidationError,
            )
        baseline_created_at = utc_datetime_text(
            baseline.get("created_at"),
            _("Created At"),
        )
        created_at = utc_datetime_text(self.created_at, _("Created At"))
        if created_at != baseline_created_at:
            frappe.throw(
                _("Baseline member creation time must match its baseline."),
                frappe.ValidationError,
            )
        self.global_id = str(member.global_id)
        self.member_key = expected_key
        self.release_evidence = canonical_json(
            member.release_evidence.canonical_dict()
        )
        self.member_snapshot = canonical_json(expected_snapshot)
        self.member_hash = member.member_hash
        self.created_at = frappe_utc_datetime_text(
            datetime.fromisoformat(created_at.replace("Z", "+00:00")),
            _("Created At"),
        )

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=1,
        )
