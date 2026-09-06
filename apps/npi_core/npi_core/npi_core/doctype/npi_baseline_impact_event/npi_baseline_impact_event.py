from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.baseline_frappe import (
    baseline_impact_value,
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
    "impact_key",
    "event_type",
    "tenant_id",
    "project_global_id",
    "dependency_global_id",
    "baseline_global_id",
    "baseline_snapshot_hash",
    "old_revision_global_id",
    "old_revision_snapshot_hash",
    "new_revision_global_id",
    "new_revision_snapshot_hash",
    "gate_global_id",
    "requirement_global_id",
    "evidence_reference_global_id",
    "initiated_by_user_id",
    "occurred_at",
    "request_id",
    "trace_id",
    "event_snapshot",
    "event_hash",
)


class NPIBaselineImpactEvent(Document):
    """Append-only invalidation for one explicitly registered dependency."""

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
            ("dependency_global_id", _("Dependency Global ID")),
            ("baseline_global_id", _("Baseline Global ID")),
            ("old_revision_global_id", _("Prior Revision Global ID")),
            ("new_revision_global_id", _("Successor Revision Global ID")),
            ("gate_global_id", _("Gate Global ID")),
            ("requirement_global_id", _("Requirement Global ID")),
            ("evidence_reference_global_id", _("Evidence Reference Global ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_document_history_update()
        dependency = require_exact_parent(
            "NPI Baseline Gate Dependency",
            self.dependency_global_id,
            {
                "global_id": self.dependency_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "baseline_global_id": self.baseline_global_id,
                "baseline_snapshot_hash": self.baseline_snapshot_hash,
                "input_revision_global_id": self.old_revision_global_id,
                "input_revision_snapshot_hash": self.old_revision_snapshot_hash,
                "gate_global_id": self.gate_global_id,
                "requirement_global_id": self.requirement_global_id,
                "evidence_reference_global_id": self.evidence_reference_global_id,
            },
            _("The impact event does not match its registered dependency."),
            extra_fields=("input_document_global_id",),
        )
        require_exact_parent(
            "NPI Document Revision",
            self.new_revision_global_id,
            {
                "global_id": self.new_revision_global_id,
                "tenant_id": self.tenant_id,
                "project_global_id": self.project_global_id,
                "document_global_id": dependency.get("input_document_global_id"),
                "predecessor_revision_global_id": self.old_revision_global_id,
                "snapshot_hash": self.new_revision_snapshot_hash,
            },
            _("The exact direct successor revision is unavailable."),
        )
        for fieldname, label in (
            ("baseline_snapshot_hash", _("Baseline Snapshot Hash")),
            ("old_revision_snapshot_hash", _("Prior Revision Snapshot Hash")),
            ("new_revision_snapshot_hash", _("Successor Revision Snapshot Hash")),
        ):
            setattr(
                self,
                fieldname,
                lowercase_sha256(getattr(self, fieldname), label),
            )
        event = document_domain_value(lambda: baseline_impact_value(self))
        expected_snapshot = event.event_payload()
        supplied_snapshot = json_object(
            self.event_snapshot,
            _("Canonical Impact Event Snapshot"),
        )
        if (
            supplied_snapshot != expected_snapshot
            or self.impact_key not in (None, "", event.impact_key)
            or self.event_hash not in (None, "", event.event_hash)
        ):
            frappe.throw(
                _("Impact Event Snapshot does not match its exact lineage."),
                frappe.ValidationError,
            )
        self.event_type = event.event_type.value
        self.impact_key = event.impact_key
        self.initiated_by_user_id = actor_text(
            event.initiated_by_user_id,
            _("Initiated By User ID"),
        )
        self.occurred_at = frappe_utc_datetime_text(
            event.occurred_at,
            _("Occurred At"),
        )
        self.request_id = required_text(self.request_id, _("Request ID"), 128)
        self.trace_id = required_text(self.trace_id, _("Trace ID"), 128)
        self.event_snapshot = canonical_json(expected_snapshot)
        self.event_hash = event.event_hash

    def on_trash(self) -> None:
        deny_document_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=1,
        )
