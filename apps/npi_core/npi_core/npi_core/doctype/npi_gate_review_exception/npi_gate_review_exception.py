from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.gate_review.frappe_validation import (
    assert_immutable_fields,
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


class NPIGateReviewException(Document):
    """Immutable exception request with one controlled terminal decision."""

    _IMMUTABLE_REQUEST_FIELDS = (
        "global_id",
        "exception_key",
        "tenant_id",
        "project_global_id",
        "gate_global_id",
        "cycle_global_id",
        "policy_global_id",
        "policy_version",
        "policy_snapshot_hash",
        "requirement_global_id",
        "requirement_key",
        "exception_kind",
        "reason",
        "risk",
        "requester_member_global_id",
        "requester_user_id",
        "requested_at",
        "expires_at",
        "closure_action_global_id",
        "closure_action_version",
        "closure_action_snapshot_hash",
        "approver_authority_slot",
        "approver_member_global_id",
        "approver_user_id",
        "request_snapshot",
        "request_snapshot_hash",
    )

    def autoname(self) -> None:
        self._normalize_request()
        self.name = self.global_id

    def before_insert(self) -> None:
        require_gate_review_command_write()

    def before_save(self) -> None:
        require_gate_review_command_write()

    def on_trash(self) -> None:
        deny_gate_review_history_delete()

    def before_validate(self) -> None:
        self._normalize_request()
        self._build_request_snapshot()
        if self.is_new():
            self.state = "pending"
            self.optimistic_version = 1
        elif self.state in {"approved", "rejected"}:
            self._build_decision_snapshot()

    def validate(self) -> None:
        self._normalize_request()
        self._build_request_snapshot()
        previous = self.get_doc_before_save()
        if previous is None:
            if self.state != "pending" or self.optimistic_version != 1:
                frappe.throw(
                    _("A new Gate review exception must start pending at version one."),
                    frappe.ValidationError,
                )
            if any(
                value not in (None, "")
                for value in (
                    self.approval_opinion,
                    self.decided_at,
                    self.decision_snapshot,
                    self.decision_snapshot_hash,
                )
            ):
                frappe.throw(
                    _("A pending Gate review exception cannot contain a decision."),
                    frappe.ValidationError,
                )
            return

        assert_immutable_fields(self, previous, self._IMMUTABLE_REQUEST_FIELDS)
        if previous.state != "pending" or self.state not in {"approved", "rejected"}:
            frappe.throw(
                _("The Gate review exception state transition is not allowed."),
                frappe.ValidationError,
            )
        if int(self.optimistic_version) != int(previous.optimistic_version) + 1:
            frappe.throw(
                _("Optimistic Version must advance by one."),
                frappe.ValidationError,
            )
        self._build_decision_snapshot()

    def _normalize_request(self) -> None:
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
        self.requirement_global_id = ensure_uuid(
            self.requirement_global_id,
            _("Requirement Global ID"),
        )
        self.requester_member_global_id = ensure_uuid(
            self.requester_member_global_id,
            _("Requester Member Global ID"),
        )
        self.approver_member_global_id = ensure_uuid(
            self.approver_member_global_id,
            _("Approver Member Global ID"),
        )
        self.closure_action_global_id = ensure_uuid(
            self.closure_action_global_id,
            _("Closure Action Global ID"),
        )
        self.closure_action_version = positive_integer(
            self.closure_action_version,
            _("Closure Action Version"),
        )
        self.closure_action_snapshot_hash = lowercase_sha256(
            self.closure_action_snapshot_hash,
            _("Closure Action Snapshot Hash"),
        )
        self.exception_key = f"{self.cycle_global_id}:{self.global_id}"
        self.tenant_id = required_text(
            self.tenant_id,
            _("Tenant ID"),
            maximum=140,
        )
        self.policy_version = positive_integer(
            self.policy_version,
            _("Review Policy Version"),
        )
        self.policy_snapshot_hash = lowercase_sha256(
            self.policy_snapshot_hash,
            _("Review Policy Snapshot Hash"),
        )
        self.requirement_key = controlled_key(
            self.requirement_key,
            _("Requirement Key"),
        )
        self.exception_kind = controlled_key(
            self.exception_kind,
            _("Review Exception Kind"),
        )
        self.reason = required_text(self.reason, _("Exception Reason"))
        self.risk = required_text(self.risk, _("Exception Risk"))
        self.requester_user_id = required_text(
            self.requester_user_id,
            _("Requester User"),
            maximum=254,
        )
        self.approver_authority_slot = controlled_key(
            self.approver_authority_slot,
            _("Approver Authority Slot"),
        )
        self.approver_user_id = required_text(
            self.approver_user_id,
            _("Approver User"),
            maximum=254,
        )
        if (
            self.requester_member_global_id == self.approver_member_global_id
            or self.requester_user_id == self.approver_user_id
        ):
            frappe.throw(
                _("The exception requester cannot approve the same exception."),
                frappe.ValidationError,
            )
        requested_at = canonical_datetime(self.requested_at, _("Requested At"))
        expires_at = canonical_datetime(self.expires_at, _("Expires At"))
        if expires_at <= requested_at:
            frappe.throw(
                _("Exception expiry must be later than its request time."),
                frappe.ValidationError,
            )
        if self.optimistic_version:
            self.optimistic_version = positive_integer(
                self.optimistic_version,
                _("Optimistic Version"),
            )

    def _build_request_snapshot(self) -> None:
        previous_snapshot = None
        schema_version = 2
        previous = self.get_doc_before_save()
        if previous is not None:
            previous_snapshot, _canonical_previous = canonical_json(
                previous.request_snapshot,
                _("Exception Request Snapshot"),
                expected_type=dict,
            )
            schema_version = previous_snapshot.get("schemaVersion")
            if type(schema_version) is not int or schema_version not in {1, 2}:
                frappe.throw(
                    _("Enter an exact closure action reference."),
                    frappe.ValidationError,
                )
            if previous_snapshot.get("closureActionRef") != {
                "globalId": self.closure_action_global_id,
                "version": self.closure_action_version,
                "snapshotHash": self.closure_action_snapshot_hash,
            }:
                frappe.throw(
                    _("Enter an exact closure action reference."),
                    frappe.ValidationError,
                )
        snapshot = {
            "schemaVersion": schema_version,
            "globalId": self.global_id,
            "exceptionKey": self.exception_key,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "gateGlobalId": self.gate_global_id,
            "cycleGlobalId": self.cycle_global_id,
            "policyRef": {
                "globalId": self.policy_global_id,
                "version": self.policy_version,
                "snapshotHash": self.policy_snapshot_hash,
            },
            "requirementRef": {
                "globalId": self.requirement_global_id,
                "key": self.requirement_key,
            },
            "kind": self.exception_kind,
            "reason": self.reason,
            "risk": self.risk,
            "requester": {
                "memberGlobalId": self.requester_member_global_id,
                "userId": self.requester_user_id,
            },
            "requestedAt": canonical_datetime(
                self.requested_at,
                _("Requested At"),
            ),
            "expiresAt": canonical_datetime(self.expires_at, _("Expires At")),
            "closureActionRef": {
                "globalId": self.closure_action_global_id,
                "version": self.closure_action_version,
                "snapshotHash": self.closure_action_snapshot_hash,
            },
            "approver": {
                "authoritySlot": self.approver_authority_slot,
                "memberGlobalId": self.approver_member_global_id,
                "userId": self.approver_user_id,
            },
        }
        _parsed, self.request_snapshot = canonical_json(
            snapshot,
            _("Exception Request Snapshot"),
            expected_type=dict,
        )
        self.request_snapshot_hash = canonical_json_hash(snapshot)

    def _build_decision_snapshot(self) -> None:
        if self.state not in {"approved", "rejected"}:
            frappe.throw(
                _("Select a supported exception decision."),
                frappe.ValidationError,
            )
        self.approval_opinion = required_text(
            self.approval_opinion,
            _("Approval Opinion"),
        )
        snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "requestSnapshotHash": self.request_snapshot_hash,
            "state": self.state,
            "approver": {
                "authoritySlot": self.approver_authority_slot,
                "memberGlobalId": self.approver_member_global_id,
                "userId": self.approver_user_id,
            },
            "opinion": self.approval_opinion,
            "decidedAt": canonical_datetime(self.decided_at, _("Decided At")),
            "optimisticVersion": self.optimistic_version,
        }
        _parsed, self.decision_snapshot = canonical_json(
            snapshot,
            _("Exception Decision Snapshot"),
            expected_type=dict,
        )
        self.decision_snapshot_hash = canonical_json_hash(snapshot)
