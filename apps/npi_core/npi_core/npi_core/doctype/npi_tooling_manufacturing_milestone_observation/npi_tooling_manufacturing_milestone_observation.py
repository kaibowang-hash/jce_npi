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
    optional_date_text,
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
    ToolingManufacturingMilestoneObservation,
    manufacturing_plan_from_snapshot,
    milestone_observation_from_snapshot,
)


class NPIToolingManufacturingMilestoneObservation(Document):
    """Immutable internal observation of one exact manufacturing milestone."""

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
            ("project_global_id", _("Project Global ID")),
            ("tooling_master_global_id", _("Tooling Master Global ID")),
            ("plan_revision_global_id", _("Manufacturing Plan Revision Global ID")),
            ("milestone_global_id", _("Manufacturing Milestone Global ID")),
            ("reported_by_member_global_id", _("Reported By Project Member Global ID")),
            ("request_id", _("Request ID")),
        ):
            setattr(self, fieldname, canonical_uuid(getattr(self, fieldname), label))
        self.predecessor_global_id = optional_uuid(
            self.predecessor_global_id,
            _("Predecessor Milestone Observation Global ID"),
        )
        self.actual_start = optional_date_text(self.actual_start, _("Actual Start"))
        self.actual_finish = optional_date_text(self.actual_finish, _("Actual Finish"))
        self.tenant_id = tenant_text(self.tenant_id)

    def validate(self) -> None:
        if self.get_doc_before_save() is not None:
            deny_tooling_history_update()
        supplied = json_object(self.observation_snapshot, _("Milestone Observation Snapshot"))
        value = tooling_domain_value(lambda: milestone_observation_from_snapshot(supplied))
        expected = (
            str(value.global_id), value.tenant_id, str(value.project_global_id),
            str(value.tooling_master_global_id), str(value.plan_revision_global_id),
            value.plan_revision_snapshot_hash, str(value.milestone_global_id),
            value.milestone_snapshot_hash, value.observation_version,
            str(value.predecessor_global_id) if value.predecessor_global_id else None,
            value.predecessor_snapshot_hash, value.progress_percentage,
            value.actual_start.isoformat() if value.actual_start else None,
            value.actual_finish.isoformat() if value.actual_finish else None,
            str(value.reported_by_member.global_id), str(value.request_id), value.trace_id,
        )
        actual = (
            self.global_id, self.tenant_id, self.project_global_id,
            self.tooling_master_global_id, self.plan_revision_global_id,
            self.plan_revision_snapshot_hash, self.milestone_global_id,
            self.milestone_snapshot_hash, self.observation_version,
            self.predecessor_global_id, self.predecessor_snapshot_hash or None,
            self.progress_percentage, self.actual_start or None,
            self.actual_finish or None, self.reported_by_member_global_id,
            self.request_id, self.trace_id,
        )
        if actual != expected:
            frappe.throw(
                _("Milestone Observation fields do not match the exact snapshot."),
                frappe.ValidationError,
            )
        if self.observation_key_hash not in (None, "", value.observation_key_hash):
            frappe.throw(
                _("Milestone Observation Key Hash does not match."),
                frappe.ValidationError,
            )
        if self.snapshot_hash not in (None, "", value.snapshot_hash):
            frappe.throw(
                _("Milestone Observation Snapshot Hash does not match."),
                frappe.ValidationError,
            )
        if json_array(self.evidence_snapshot, _("Milestone Evidence Snapshot")) != [
            item.snapshot_payload() for item in value.evidence
        ]:
            frappe.throw(
                _("Milestone Evidence Snapshot does not match the exact observation."),
                frappe.ValidationError,
            )
        if json_object(self.reporter_snapshot, _("Internal Reporter Snapshot")) != (
            value.reported_by_member.snapshot_payload()
        ):
            frappe.throw(
                _("Internal Reporter Snapshot does not match the exact observation."),
                frappe.ValidationError,
            )
        plan_row = require_exact_parent(
            "NPI Tooling Manufacturing Plan Revision",
            str(value.plan_revision_global_id),
            {
                "global_id": str(value.plan_revision_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "tooling_master_global_id": str(value.tooling_master_global_id),
                "snapshot_hash": value.plan_revision_snapshot_hash,
            },
            _("The Manufacturing Plan Revision is unavailable for this observation."),
            extra_fields=("plan_snapshot",),
        )
        plan = tooling_domain_value(
            lambda: manufacturing_plan_from_snapshot(json_object(
                plan_row.plan_snapshot,
                _("Manufacturing Plan Revision Snapshot"),
            ))
        )
        selected = next(
            (item for item in plan.milestones if item.global_id == value.milestone_global_id),
            None,
        )
        if selected is None or selected.snapshot_hash != value.milestone_snapshot_hash:
            frappe.throw(
                _("The exact manufacturing milestone is unavailable for this observation."),
                frappe.ValidationError,
            )
        if value.predecessor_global_id is not None:
            require_exact_parent(
                "NPI Tooling Manufacturing Milestone Observation",
                str(value.predecessor_global_id),
                {
                    "global_id": str(value.predecessor_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "plan_revision_global_id": str(value.plan_revision_global_id),
                    "milestone_global_id": str(value.milestone_global_id),
                    "snapshot_hash": value.predecessor_snapshot_hash,
                },
                _("The predecessor Milestone Observation is unavailable."),
            )
        require_exact_parent(
            "NPI Project Member",
            str(value.reported_by_member.global_id),
            {
                "global_id": str(value.reported_by_member.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "user_id": value.reported_by_member.user_id,
                "optimistic_version": value.reported_by_member.optimistic_version,
                "effective_to": None,
            },
            _("The internal reporting Project member is unavailable."),
        )
        for evidence in value.evidence:
            require_exact_parent(
                "NPI File Revision",
                str(evidence.file_revision_global_id),
                {
                    "global_id": str(evidence.file_revision_global_id),
                    "tenant_id": value.tenant_id,
                    "project_global_id": str(value.project_global_id),
                    "optimistic_version": evidence.file_optimistic_version,
                    "frappe_content_hash": evidence.frappe_content_hash,
                    "file_name": evidence.file_name,
                    "mime_type": evidence.mime_type,
                    "size_bytes": evidence.size_bytes,
                    "sha256": evidence.sha256,
                    "is_private": 1,
                    "scan_state": "clean",
                },
                _("A clean private File Revision is unavailable for this observation."),
            )
        self.manufacturing_plan_revision = str(value.plan_revision_global_id)
        self.reported_by_member = str(value.reported_by_member.global_id)
        self.observation_key_hash = value.observation_key_hash
        self.risk = value.risk
        self.note = value.note
        self.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
        self.evidence_snapshot = canonical_json(
            [item.snapshot_payload() for item in value.evidence]
        )
        self.reporter_snapshot = canonical_json(value.reported_by_member.snapshot_payload())
        self.observation_snapshot = canonical_json(value.snapshot_payload())
        self.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))

    def on_trash(self) -> None:
        deny_tooling_history_delete(self)
