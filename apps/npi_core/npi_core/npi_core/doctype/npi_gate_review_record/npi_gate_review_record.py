from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.gate_review.frappe_validation import (
    canonical_datetime,
    canonical_json,
    canonical_json_hash,
    controlled_key,
    deny_gate_review_history_delete,
    ensure_uuid,
    lowercase_sha256,
    positive_integer,
    require_gate_review_command_write,
    required_text,
)


class NPIGateReviewRecord(Document):
    """One immutable opinion for one selected assignment in a review cycle."""

    def autoname(self) -> None:
        self._normalize()
        self.name = self.global_id

    def before_insert(self) -> None:
        require_gate_review_command_write()

    def before_save(self) -> None:
        require_gate_review_command_write()
        self._deny_update()

    def on_trash(self) -> None:
        deny_gate_review_history_delete()

    def before_validate(self) -> None:
        self._normalize()
        self._build_snapshot()

    def validate(self) -> None:
        self._deny_update()
        self._normalize()
        self._build_snapshot()

    def _deny_update(self) -> None:
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("Gate review records cannot be changed."),
                frappe.PermissionError,
            )

    def _normalize(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        self.project_global_id = ensure_uuid(
            self.project_global_id,
            _("Project Global ID"),
        )
        self.gate_global_id = ensure_uuid(
            self.gate_global_id,
            _("Gate Global ID"),
        )
        self.cycle_global_id = ensure_uuid(
            self.cycle_global_id,
            _("Review Cycle Global ID"),
        )
        self.policy_global_id = ensure_uuid(
            self.policy_global_id,
            _("Review Policy Global ID"),
        )
        self.assigned_member_global_id = ensure_uuid(
            self.assigned_member_global_id,
            _("Assigned Member Global ID"),
        )
        self.tenant_id = required_text(
            self.tenant_id,
            _("Tenant ID"),
            maximum=140,
        )
        self.cycle_number = positive_integer(
            self.cycle_number,
            _("Review Cycle Number"),
        )
        self.policy_version = positive_integer(
            self.policy_version,
            _("Review Policy Version"),
        )
        self.review_step_key = controlled_key(
            self.review_step_key,
            _("Review Step Key"),
        )
        self.review_step_sequence = positive_integer(
            self.review_step_sequence,
            _("Review Step Sequence"),
        )
        self.authority_slot = controlled_key(
            self.authority_slot,
            _("Authority Slot"),
        )
        self.assigned_user_id = required_text(
            self.assigned_user_id,
            _("Assigned User"),
            maximum=254,
        )
        self.assigned_display_name = required_text(
            self.assigned_display_name,
            _("Assigned Member"),
            maximum=140,
        )
        self.actor_user_id = required_text(
            self.actor_user_id,
            _("Review Actor"),
            maximum=254,
        )
        if self.actor_user_id != self.assigned_user_id:
            frappe.throw(
                _("The assigned reviewer must be the review actor."),
                frappe.ValidationError,
            )
        if self.outcome not in {"approved", "rejected"}:
            frappe.throw(
                _("Select a supported review outcome."),
                frappe.ValidationError,
            )
        self.opinion = required_text(self.opinion, _("Review Opinion"))
        canonical_datetime(self.occurred_at, _("Occurred At"))
        self.policy_snapshot_hash = lowercase_sha256(
            self.policy_snapshot_hash,
            _("Review Policy Snapshot Hash"),
        )
        self.reviewed_input_hash = lowercase_sha256(
            self.reviewed_input_hash,
            _("Reviewed Input Hash"),
        )
        self.cycle_version_before = positive_integer(
            self.cycle_version_before,
            _("Cycle Version Before"),
        )
        self.cycle_version_after = positive_integer(
            self.cycle_version_after,
            _("Cycle Version After"),
        )
        if self.cycle_version_after != self.cycle_version_before + 1:
            frappe.throw(
                _("Cycle Version After must advance by one."),
                frappe.ValidationError,
            )
        self.request_id = required_text(
            self.request_id,
            _("Request ID"),
            maximum=140,
        )
        self.trace_id = required_text(
            self.trace_id,
            _("Trace ID"),
            maximum=140,
        )
        self.review_key = f"{self.cycle_global_id}:{self.review_step_key}"

    def _build_snapshot(self) -> None:
        snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "reviewKey": self.review_key,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "gateGlobalId": self.gate_global_id,
            "cycleGlobalId": self.cycle_global_id,
            "cycleNumber": self.cycle_number,
            "policyRef": {
                "globalId": self.policy_global_id,
                "version": self.policy_version,
                "snapshotHash": self.policy_snapshot_hash,
            },
            "step": {
                "key": self.review_step_key,
                "sequence": self.review_step_sequence,
                "authoritySlot": self.authority_slot,
            },
            "assignment": {
                "memberGlobalId": self.assigned_member_global_id,
                "userId": self.assigned_user_id,
                "displayName": self.assigned_display_name,
            },
            "actorUserId": self.actor_user_id,
            "outcome": self.outcome,
            "opinion": self.opinion,
            "occurredAt": canonical_datetime(self.occurred_at, _("Occurred At")),
            "reviewedInputHash": self.reviewed_input_hash,
            "cycleVersionBefore": self.cycle_version_before,
            "cycleVersionAfter": self.cycle_version_after,
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        _parsed, self.record_snapshot = canonical_json(
            snapshot,
            _("Review Record Snapshot"),
            expected_type=dict,
        )
        self.record_snapshot_hash = canonical_json_hash(snapshot)
