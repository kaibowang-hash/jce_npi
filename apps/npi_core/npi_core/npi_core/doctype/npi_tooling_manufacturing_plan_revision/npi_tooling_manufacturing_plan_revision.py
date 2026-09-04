from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    tenant_text,
)
from npi_core.tooling.frappe_validation import (
    deny_tooling_history_delete,
    deny_tooling_history_update,
    require_tooling_command_write,
    tooling_domain_value,
)
from npi_core.tooling.manufacturing_domain import (
    ReleasedDocumentEvidence,
    ToolingManufacturingPlanRevision,
    manufacturing_plan_from_snapshot,
)


class NPIToolingManufacturingPlanRevision(Document):
    """Immutable internal sourcing, budget, evidence and milestone plan."""

    def autoname(self) -> None:
        self.global_id = canonical_uuid(self.global_id, _("Global ID"))
        self.name = self.global_id

    def before_insert(self) -> None:
        require_tooling_command_write()

    def before_save(self) -> None:
        require_tooling_command_write()
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()

    def before_validate(self) -> None:
        for fieldname, label in (
            ("global_id", _("Global ID")),
            ("plan_global_id", _("Manufacturing Plan Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("tooling_revision_global_id", _("Tooling Revision Global ID")),
            ("responsible_member_global_id", _("Responsible Project Member Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Manufacturing Plan Global ID"),
        )
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(self.plan_snapshot, _("Manufacturing Plan Revision Snapshot"))
        value = tooling_domain_value(lambda: manufacturing_plan_from_snapshot(supplied))
        expected = (
            str(value.global_id), str(value.plan_global_id), value.tenant_id,
            str(value.project_global_id), str(value.tooling_master_global_id),
            str(value.tooling_revision_global_id), value.tooling_revision_snapshot_hash,
            value.plan_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash, value.sourcing_strategy.value,
            str(value.responsible_member.global_id), str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.plan_global_id, self.tenant_id,
            self.project_global_id, self.tooling_master_global_id,
            self.tooling_revision_global_id, self.tooling_revision_snapshot_hash,
            self.plan_version, self.predecessor_global_id,
            self.predecessor_snapshot_hash or None, self.sourcing_strategy,
            self.responsible_member_global_id, self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Manufacturing Plan Revision fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.version_key_hash not in (None, "", value.version_key_hash):
            frappe.throw(
                _("Manufacturing Plan Version Key Hash does not match."),
                frappe.ValidationError,
            )
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(
                _("Manufacturing Plan Revision Snapshot Hash does not match."),
                frappe.ValidationError,
            )
        snapshots = (
            (
                json_object(self.responsibility_snapshot, _("Responsibility Snapshot")),
                value.responsible_member.snapshot_payload(),
                _("Responsibility Snapshot"),
            ),
            (
                json_object(self.cost_snapshot, _("Engineering Estimate and Budget Snapshot")),
                {
                    "engineeringEstimate": (
                        value.engineering_estimate.snapshot_payload()
                        if value.engineering_estimate else None
                    ),
                    "budget": value.budget.snapshot_payload() if value.budget else None,
                },
                _("Engineering Estimate and Budget Snapshot"),
            ),
            (
                json_array(
                    self.document_evidence_snapshot,
                    _("Released Planning Document Evidence Snapshot"),
                ),
                [item.snapshot_payload() for item in value.evidence],
                _("Released Planning Document Evidence Snapshot"),
            ),
            (
                json_array(self.design_release_snapshot, _("Design Release Evidence Snapshot")),
                [item.snapshot_payload() for item in value.design_release_evidence],
                _("Design Release Evidence Snapshot"),
            ),
            (
                json_array(self.milestone_snapshot, _("Manufacturing Milestone Snapshot")),
                [item.snapshot_payload() for item in value.milestones],
                _("Manufacturing Milestone Snapshot"),
            ),
        )
        for supplied_snapshot, expected_snapshot, label in snapshots:
            if supplied_snapshot != expected_snapshot:
                frappe.throw(
                    _("{field} does not match the exact manufacturing plan.").format(field=label),
                    frappe.ValidationError,
                )
        require_exact_parent(
            "NPI Tooling Master",
            str(value.tooling_master_global_id),
            {
                "global_id": str(value.tooling_master_global_id),
                "tenant_id": value.tenant_id,
                "originating_project_global_id": str(value.project_global_id),
            },
            _("The Tooling Master is unavailable for this manufacturing plan."),
        )
        revision_row = require_exact_parent(
            "NPI Tooling Revision",
            str(value.tooling_revision_global_id),
            {
                "global_id": str(value.tooling_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "snapshot_hash": value.tooling_revision_snapshot_hash,
            },
            _("The Tooling Revision is unavailable for this manufacturing plan."),
            extra_fields=("design_document_revision_snapshot",),
        )
        revision_design_documents = json_array(
            revision_row["design_document_revision_snapshot"],
            _("Design Document Revision Snapshot"),
        )
        expected_design_documents = {
            (item.get("globalId"), item.get("snapshotHash"))
            for item in revision_design_documents
            if isinstance(item, dict)
        }
        observed_design_documents = {
            (str(item.revision_global_id), item.revision_snapshot_hash)
            for item in value.design_release_evidence
        }
        if (
            len(expected_design_documents) != len(revision_design_documents)
            or observed_design_documents != expected_design_documents
        ):
            frappe.throw(
                _("Design release evidence does not match the exact Tooling Revision."),
                frappe.ValidationError,
            )
        if value.predecessor_global_id is not None:
            require_exact_parent(
                "NPI Tooling Manufacturing Plan Revision",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "plan_global_id": str(value.plan_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "tooling_master_global_id": str(value.tooling_master_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Manufacturing Plan Revision is unavailable."),
            )
        members = {value.responsible_member.global_id: value.responsible_member}
        for milestone in value.milestones:
            if milestone.responsible_member is not None:
                members[milestone.responsible_member.global_id] = milestone.responsible_member
        for responsibility in members.values():
            require_exact_parent(
                "NPI Project Member",
                str(responsibility.global_id),
                {
                    "global_id": str(responsibility.global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "user_id": responsibility.user_id,
                    "optimistic_version": responsibility.optimistic_version,
                    "effective_to": None,
                },
                _("A responsible Project member is unavailable for this manufacturing plan."),
            )
        released_documents = {
            item.document.revision_global_id: item.document for item in value.evidence
        }
        released_documents.update(
            {item.revision_global_id: item for item in value.design_release_evidence}
        )
        for evidence in released_documents.values():
            _require_released_document(value, evidence)
        self.tooling_master = str(value.tooling_master_global_id)
        self.tooling_revision = str(value.tooling_revision_global_id)
        self.responsible_member = str(value.responsible_member.global_id)
        self.version_key_hash = value.version_key_hash
        self.reason = value.reason
        self.created_by_user_id = value.created_by_user_id
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.responsibility_snapshot = canonical_json(value.responsible_member.snapshot_payload())
        self.cost_snapshot = canonical_json(
            {
                "engineeringEstimate": (
                    value.engineering_estimate.snapshot_payload()
                    if value.engineering_estimate else None
                ),
                "budget": value.budget.snapshot_payload() if value.budget else None,
            }
        )
        self.document_evidence_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.evidence]
        )
        self.design_release_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.design_release_evidence]
        )
        self.milestone_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.milestones]
        )
        self.plan_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)


def _require_released_document(
    plan: ToolingManufacturingPlanRevision,
    evidence: ReleasedDocumentEvidence,
) -> None:
    require_exact_parent(
        "NPI Document Revision",
        str(evidence.revision_global_id),
        {
            "global_id": str(evidence.revision_global_id),
            "tenant_id": plan.tenant_id,
            "project_global_id": str(plan.project_global_id),
            "snapshot_hash": evidence.revision_snapshot_hash,
        },
        _("A released Document Revision is unavailable for this manufacturing plan."),
    )
    require_exact_parent(
        "NPI Document Revision Lifecycle",
        str(evidence.lifecycle_global_id),
        {
            "global_id": str(evidence.lifecycle_global_id),
            "tenant_id": plan.tenant_id,
            "project_global_id": str(plan.project_global_id),
            "revision_global_id": str(evidence.revision_global_id),
            "current_state": "released",
            "lifecycle_version": evidence.lifecycle_version,
            "release_event_global_id": str(evidence.release_event_global_id),
            "release_snapshot_hash": evidence.release_snapshot_hash,
            "last_event_global_id": str(evidence.release_event_global_id),
        },
        _("The exact released Document lifecycle is unavailable for this manufacturing plan."),
    )
    require_exact_parent(
        "NPI Document Lifecycle Event",
        str(evidence.release_event_global_id),
        {
            "global_id": str(evidence.release_event_global_id),
            "tenant_id": plan.tenant_id,
            "project_global_id": str(plan.project_global_id),
            "revision_global_id": str(evidence.revision_global_id),
            "event_type": "released",
            "to_state": "released",
            "to_version": evidence.lifecycle_version,
            "event_hash": evidence.release_event_hash,
        },
        _("The exact Document release event is unavailable for this manufacturing plan."),
    )
