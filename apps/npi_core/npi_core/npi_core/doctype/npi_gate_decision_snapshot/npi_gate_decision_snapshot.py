from __future__ import annotations

from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.gate_review.frappe_validation import (
    canonical_datetime,
    canonical_json,
    canonical_json_hash,
    deny_gate_review_history_delete,
    ensure_uuid,
    lowercase_sha256,
    positive_integer,
    require_gate_review_command_write,
    required_text,
)


class NPIGateDecisionSnapshot(Document):
    """One server-built immutable decision snapshot per completed cycle."""

    def autoname(self) -> None:
        self._normalize()
        self.name = self.global_id

    def before_insert(self) -> None:
        require_gate_review_command_write()

    def before_save(self) -> None:
        require_gate_review_command_write()
        self._deny_update()

    def on_trash(self) -> None:
        deny_gate_review_history_delete(
            self,
            target_global_id=self.global_id,
            target_version=self.cycle_version,
        )

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
                _("Gate decision snapshots cannot be changed."),
                frappe.PermissionError,
            )

    def _normalize(self) -> None:
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
        self.global_id = str(uuid5(UUID(self.cycle_global_id), "decision-snapshot"))
        self.policy_global_id = ensure_uuid(
            self.policy_global_id,
            _("Review Policy Global ID"),
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
        self.policy_snapshot_hash = lowercase_sha256(
            self.policy_snapshot_hash,
            _("Review Policy Snapshot Hash"),
        )
        self.cycle_version = positive_integer(
            self.cycle_version,
            _("Review Cycle Version"),
        )
        if self.outcome not in {"pass", "reject", "conditional_pass"}:
            frappe.throw(
                _("Select a supported Gate decision outcome."),
                frappe.ValidationError,
            )
        self.actor_user_id = required_text(
            self.actor_user_id,
            _("Decision Actor"),
            maximum=254,
        )
        canonical_datetime(self.occurred_at, _("Occurred At"))
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
        input_snapshot, self.input_snapshot = canonical_json(
            self.input_snapshot,
            _("Review Input Snapshot"),
            expected_type=dict,
        )
        self.input_hash = lowercase_sha256(
            self.input_hash,
            _("Review Input Hash"),
        )
        if not input_snapshot or canonical_json_hash(input_snapshot) != self.input_hash:
            frappe.throw(
                _("Review Input Snapshot does not match its hash."),
                frappe.ValidationError,
            )
        review_hashes, self.review_hashes = canonical_json(
            self.review_hashes,
            _("Review Record Hashes"),
            expected_type=list,
        )
        exception_hashes, self.exception_hashes = canonical_json(
            self.exception_hashes,
            _("Review Exception Hashes"),
            expected_type=list,
        )
        self._validate_hashes(review_hashes, _("Review Record Hashes"))
        self._validate_hashes(exception_hashes, _("Review Exception Hashes"))
        if self.outcome == "conditional_pass" and not exception_hashes:
            frappe.throw(
                _("A conditional pass requires an approved exception."),
                frappe.ValidationError,
            )

    @staticmethod
    def _validate_hashes(values: list[object], field_label: str) -> None:
        if len(values) != len(set(values)):
            frappe.throw(
                _("{field} must not contain duplicate hashes.").format(
                    field=field_label
                ),
                frappe.ValidationError,
            )
        for value in values:
            lowercase_sha256(value, field_label)

    def _build_snapshot(self) -> None:
        input_snapshot, _canonical_input = canonical_json(
            self.input_snapshot,
            _("Review Input Snapshot"),
            expected_type=dict,
        )
        review_hashes, _canonical_reviews = canonical_json(
            self.review_hashes,
            _("Review Record Hashes"),
            expected_type=list,
        )
        exception_hashes, _canonical_exceptions = canonical_json(
            self.exception_hashes,
            _("Review Exception Hashes"),
            expected_type=list,
        )
        snapshot = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "gateGlobalId": self.gate_global_id,
            "cycleGlobalId": self.cycle_global_id,
            "cycleNumber": self.cycle_number,
            "outcome": self.outcome,
            "actorUserId": self.actor_user_id,
            "occurredAt": canonical_datetime(self.occurred_at, _("Occurred At")),
            "policyRef": {
                "globalId": self.policy_global_id,
                "version": self.policy_version,
                "snapshotHash": self.policy_snapshot_hash,
            },
            "inputSnapshot": input_snapshot,
            "inputHash": self.input_hash,
            "reviewHashes": review_hashes,
            "exceptionHashes": exception_hashes,
            "cycleVersion": self.cycle_version,
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }
        _parsed, self.decision_snapshot = canonical_json(
            snapshot,
            _("Gate Decision Snapshot"),
            expected_type=dict,
        )
        self.snapshot_hash = canonical_json_hash(snapshot)
