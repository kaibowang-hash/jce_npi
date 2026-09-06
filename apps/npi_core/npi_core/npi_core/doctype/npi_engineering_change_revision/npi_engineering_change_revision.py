from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.change_control.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_change_history_delete,
    deny_change_history_update,
    lowercase_sha256,
    optional_sha256,
    optional_uuid,
    positive_integer,
    required_text,
    require_change_command_write,
    sha256_json,
    utc_datetime_text,
)


_ALL_FIELDS = (
    "global_id", "change_global_id", "version_key_hash", "tenant_id",
    "project_global_id", "revision", "predecessor_global_id",
    "predecessor_snapshot_hash", "internal_state", "title", "formal_change_snapshot",
    "impact_assessment_snapshot", "affected_object_snapshot",
    "implementation_task_snapshot", "effectivity_snapshot", "disposition_snapshot",
    "revalidation_snapshot", "cost_summary_snapshot", "closure_evidence_snapshot",
    "revision_reason", "created_by_user_id", "created_at", "request_id", "trace_id",
    "revision_snapshot", "snapshot_hash",
)
_LIST_SNAPSHOTS = (
    "impact_assessment_snapshot", "affected_object_snapshot",
    "implementation_task_snapshot", "effectivity_snapshot", "disposition_snapshot",
    "revalidation_snapshot",
)
_LIST_LABELS = {
    "impact_assessment_snapshot": _("Impact Assessment Snapshot"),
    "affected_object_snapshot": _("Affected Object Snapshot"),
    "implementation_task_snapshot": _("Implementation Task Snapshot"),
    "effectivity_snapshot": _("Effectivity Snapshot"),
    "disposition_snapshot": _("Disposition Snapshot"),
    "revalidation_snapshot": _("Revalidation Snapshot"),
}
_STATES = frozenset({"draft", "active", "ready_to_close", "closed", "cancelled"})


class NPIEngineeringChangeRevision(Document):
    """Immutable canonical engineering change revision."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_change_command_write()

    def before_save(self) -> None:
        require_change_command_write()
        if self.get_doc_before_save() is not None:
            deny_change_history_update()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(self, previous, _ALL_FIELDS)
            deny_change_history_update()
        for fieldname, label in (
            ("global_id", _("Global ID")), ("change_global_id", _("Engineering Change Global ID")),
            ("project_global_id", _("Project Global ID")), ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(self.predecessor_global_id, _("Predecessor Revision Global ID"))
        self.predecessor_snapshot_hash = optional_sha256(self.predecessor_snapshot_hash, _("Predecessor Snapshot Hash"))
        self.version_key_hash = lowercase_sha256(self.version_key_hash, _("Revision Key Hash"))
        self.snapshot_hash = lowercase_sha256(self.snapshot_hash, _("Snapshot Hash"))
        self.revision = positive_integer(self.revision, _("Revision"))
        self.tenant_id = required_text(self.tenant_id, _("Tenant ID"))
        expected_version_key = sha256_json(
            {
                "changeGlobalId": self.change_global_id,
                "revision": self.revision,
                "tenantId": self.tenant_id,
            }
        )
        if self.version_key_hash != expected_version_key:
            frappe.throw(
                _("The engineering change revision key does not match."),
                frappe.ValidationError,
            )
        if self.revision == 1 and (self.predecessor_global_id or self.predecessor_snapshot_hash):
            frappe.throw(_("The first revision cannot have a predecessor."), frappe.ValidationError)
        if self.revision > 1 and not (self.predecessor_global_id and self.predecessor_snapshot_hash):
            frappe.throw(_("A successor revision requires its exact predecessor."), frappe.ValidationError)
        if self.internal_state not in _STATES:
            frappe.throw(
                _("Select a supported engineering change state."),
                frappe.ValidationError,
            )
        self.title = required_text(self.title, _("Engineering Change Title"), 280)
        self.revision_reason = required_text(self.revision_reason, _("Revision Reason"), 4000)
        self.created_by_user_id = required_text(self.created_by_user_id, _("Created By User ID"), 254)
        self.trace_id = required_text(self.trace_id, _("Trace ID"))
        parsed: dict[str, object] = {}
        formal, self.formal_change_snapshot = canonical_json(self.formal_change_snapshot, _("Formal Change Observation Snapshot"), dict)
        parsed["formalChange"] = formal
        for fieldname in _LIST_SNAPSHOTS:
            value, text = canonical_json(
                getattr(self, fieldname),
                _LIST_LABELS[fieldname],
                list,
            )
            setattr(self, fieldname, text)
            parsed[fieldname] = value
        cost, self.cost_summary_snapshot = canonical_json(self.cost_summary_snapshot, _("Cost Summary Snapshot"), dict)
        closure, self.closure_evidence_snapshot = canonical_json(self.closure_evidence_snapshot, _("Closure Evidence Snapshot"), dict)
        parsed["costSummary"] = cost
        parsed["closureEvidence"] = closure
        snapshot, self.revision_snapshot = canonical_json(self.revision_snapshot, _("Canonical Engineering Change Revision Snapshot"), dict)
        ready_to_close = snapshot.get("readyToClose")
        if type(ready_to_close) is not bool:
            frappe.throw(
                _("The canonical revision must contain a valid closeout result."),
                frappe.ValidationError,
            )
        expected = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "changeGlobalId": self.change_global_id,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "revision": self.revision,
            "predecessorGlobalId": self.predecessor_global_id,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "state": self.internal_state,
            "title": self.title,
            "reason": self.revision_reason,
            "formalChange": formal or None,
            "impactAssessments": parsed["impact_assessment_snapshot"],
            "affectedObjects": parsed["affected_object_snapshot"],
            "implementationTasks": parsed["implementation_task_snapshot"],
            "effectivityRules": parsed["effectivity_snapshot"],
            "dispositions": parsed["disposition_snapshot"],
            "revalidationRequirements": parsed["revalidation_snapshot"],
            "costSummary": cost,
            "closureEvidence": closure or None,
            "readyToClose": ready_to_close,
            "createdByUserId": self.created_by_user_id,
            "createdAt": utc_datetime_text(self.created_at, _("Created At")),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        if snapshot != expected or sha256_json(snapshot) != self.snapshot_hash:
            frappe.throw(_("The engineering change revision snapshot hash does not match."), frappe.ValidationError)

    def on_trash(self) -> None:
        deny_change_history_delete(self)
