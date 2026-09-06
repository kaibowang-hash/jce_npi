from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.baseline_frappe import (
    baseline_dependency_value,
    require_baseline_dependency_system_write,
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
    require_exact_parent,
    required_text,
    tenant_text,
)


_ALL_FIELDS = (
    "global_id",
    "dependency_key",
    "tenant_id",
    "project_global_id",
    "document_baseline",
    "baseline_global_id",
    "baseline_snapshot_hash",
    "input_document_global_id",
    "input_revision_global_id",
    "input_revision_snapshot_hash",
    "gate_global_id",
    "requirement_global_id",
    "requirement_key",
    "evidence_reference_global_id",
    "registered_by_user_id",
    "registered_at",
    "request_id",
    "trace_id",
    "dependency_snapshot",
    "snapshot_hash",
)


class NPIBaselineGateDependency(Document):
    """Append-only explicit link from one baseline member to one Gate input."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_baseline_dependency_system_write()

    def before_save(self) -> None:
        require_baseline_dependency_system_write()
        if self.get_doc_before_save() is not None:
            deny_document_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("baseline_global_id", _("Baseline Global ID")),
            ("input_document_global_id", _("Input Document Global ID")),
            ("input_revision_global_id", _("Input Revision Global ID")),
            ("gate_global_id", _("Gate Global ID")),
            ("requirement_global_id", _("Requirement Global ID")),
            ("evidence_reference_global_id", _("Evidence Reference Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)
        self.document_baseline = canonical_uuid(
            self.document_baseline,
            _("Document Baseline"),
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
        require_exact_parent(
            "NPI Document Baseline",
            self.document_baseline,
            {
                "global_id": self.baseline_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "snapshot_hash": self.baseline_snapshot_hash,
            },
            _("The baseline dependency does not match its immutable baseline."),
        )
        member = frappe.db.get_value(
            "NPI Document Baseline Member",
            {
                "baseline_global_id": self.baseline_global_id,
                "revision_global_id": self.input_revision_global_id,
            },
            [
                "document_global_id",
                "revision_snapshot_hash",
                "baseline_snapshot_hash",
            ],
            as_dict=True,
        )
        if (
            not member
            or str(member.get("document_global_id"))
            != self.input_document_global_id
            or str(member.get("revision_snapshot_hash"))
            != self.input_revision_snapshot_hash
            or str(member.get("baseline_snapshot_hash"))
            != self.baseline_snapshot_hash
        ):
            frappe.throw(
                _("The Gate dependency input is not an exact baseline member."),
                frappe.ValidationError,
            )
        require_exact_parent(
            "NPI Gate Shell",
            self.gate_global_id,
            {
                "global_id": self.gate_global_id,
                "project_global_id": self.project_global_id,
            },
            _("The baseline dependency does not match its Gate."),
        )
        require_exact_parent(
            "NPI Gate Evidence Reference",
            self.evidence_reference_global_id,
            {
                "global_id": self.evidence_reference_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "gate_global_id": self.gate_global_id,
                "requirement_global_id": self.requirement_global_id,
                "requirement_key": self.requirement_key,
                "evidence_kind": "release_baseline",
                "source_object_type": "release_baseline",
                "source_global_id": self.baseline_global_id,
                "source_version": 1,
                "source_hash": self.baseline_snapshot_hash,
            },
            _("The baseline dependency does not match exact Gate evidence."),
        )
        self.baseline_snapshot_hash = lowercase_sha256(
            self.baseline_snapshot_hash,
            _("Baseline Snapshot Hash"),
        )
        self.input_revision_snapshot_hash = lowercase_sha256(
            self.input_revision_snapshot_hash,
            _("Input Revision Snapshot Hash"),
        )
        dependency = document_domain_value(
            lambda: baseline_dependency_value(self)
        )
        expected_snapshot = dependency.snapshot_payload()
        supplied_snapshot = json_object(
            self.dependency_snapshot,
            _("Canonical Dependency Snapshot"),
        )
        if (
            supplied_snapshot != expected_snapshot
            or self.dependency_key not in (None, "", dependency.dependency_key)
            or self.snapshot_hash not in (None, "", dependency.snapshot_hash)
        ):
            frappe.throw(
                _("Dependency Snapshot does not match its exact Gate input."),
                frappe.ValidationError,
            )
        self.dependency_key = dependency.dependency_key
        self.registered_by_user_id = actor_text(
            dependency.registered_by_user_id,
            _("Registered By User ID"),
        )
        self.registered_at = frappe_utc_datetime_text(
            dependency.registered_at,
            _("Registered At"),
        )
        self.request_id = required_text(self.request_id, _("Request ID"), 128)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.dependency_snapshot = canonical_json(expected_snapshot)
        self.snapshot_hash = dependency.snapshot_hash

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=1,
        )
