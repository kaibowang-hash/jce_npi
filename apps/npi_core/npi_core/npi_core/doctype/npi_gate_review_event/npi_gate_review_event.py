from __future__ import annotations

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
    require_gate_review_command_write,
    required_text,
)


class NPIGateReviewEvent(Document):
    """Immutable exception, reopen, or invalidation history."""

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
        self._build_payload()

    def validate(self) -> None:
        self._deny_update()
        self._normalize()
        self._build_payload()

    def _deny_update(self) -> None:
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("Gate review events cannot be changed."),
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
        self.event_key = required_text(
            self.event_key,
            _("Review Event Key"),
            maximum=140,
        )
        self.tenant_id = required_text(
            self.tenant_id,
            _("Tenant ID"),
            maximum=140,
        )
        self.actor_user_id = required_text(
            self.actor_user_id,
            _("Event Actor"),
            maximum=254,
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
        canonical_datetime(self.occurred_at, _("Occurred At"))
        if self.successor_cycle_global_id:
            self.successor_cycle_global_id = ensure_uuid(
                self.successor_cycle_global_id,
                _("Successor Review Cycle Global ID"),
            )
        if self.action_global_id:
            self.action_global_id = ensure_uuid(
                self.action_global_id,
                _("Impact Action Global ID"),
            )
        self._validate_event_references()

    def _validate_event_references(self) -> None:
        successor = self.successor_cycle_global_id not in (None, "")
        action = self.action_global_id not in (None, "")
        valid = (
            (self.event_type == "exception_decided" and not successor and not action)
            or (self.event_type == "reopened" and successor and not action)
            or (self.event_type in {"invalidated", "refreshed"} and successor)
        )
        if not valid:
            frappe.throw(
                _("Review Event references do not match its event type."),
                frappe.ValidationError,
            )

    def _build_payload(self) -> None:
        supplied, _canonical_supplied = canonical_json(
            self.payload,
            _("Review Event Payload"),
            expected_type=dict,
        )
        detail = supplied.get("detail")
        self._validate_detail(detail)
        payload = {
            "schemaVersion": 1,
            "globalId": self.global_id,
            "eventKey": self.event_key,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "gateGlobalId": self.gate_global_id,
            "cycleGlobalId": self.cycle_global_id,
            "successorCycleGlobalId": self.successor_cycle_global_id or None,
            "actionGlobalId": self.action_global_id or None,
            "eventType": self.event_type,
            "actorUserId": self.actor_user_id,
            "occurredAt": canonical_datetime(self.occurred_at, _("Occurred At")),
            "requestId": self.request_id,
            "traceId": self.trace_id,
            "detail": detail,
        }
        if supplied != payload:
            frappe.throw(
                _("Review Event Payload does not match this event."),
                frappe.ValidationError,
            )
        _parsed, self.payload = canonical_json(
            payload,
            _("Review Event Payload"),
            expected_type=dict,
        )
        self.payload_hash = canonical_json_hash(payload)

    def _validate_detail(self, detail: object) -> None:
        if not isinstance(detail, dict):
            frappe.throw(
                _("Review Event Payload must contain an exact event detail."),
                frappe.ValidationError,
            )
        if self.event_type == "exception_decided":
            if set(detail) != {
                "exceptionGlobalId",
                "state",
                "decisionSnapshotHash",
            } or detail.get("state") not in {"approved", "rejected"}:
                frappe.throw(
                    _("Review Event Payload contains an invalid exception decision."),
                    frappe.ValidationError,
                )
            ensure_uuid(
                detail["exceptionGlobalId"],
                _("Review Exception Global ID"),
            )
            lowercase_sha256(
                detail["decisionSnapshotHash"],
                _("Exception Decision Snapshot Hash"),
            )
            return
        if self.event_type == "reopened":
            if set(detail) != {
                "reason",
                "priorDecisionSnapshotGlobalId",
                "priorDecisionHash",
            }:
                frappe.throw(
                    _("Review Event Payload contains an invalid reopen detail."),
                    frappe.ValidationError,
                )
            required_text(detail["reason"], _("Reopen Reason"))
            ensure_uuid(
                detail["priorDecisionSnapshotGlobalId"],
                _("Prior Decision Snapshot Global ID"),
            )
            lowercase_sha256(
                detail["priorDecisionHash"],
                _("Prior Decision Hash"),
            )
            return
        if self.event_type in {"invalidated", "refreshed"}:
            if set(detail) != {
                "reason",
                "oldInputHash",
                "newInputHash",
                "priorDecisionSnapshotGlobalId",
                "priorDecisionHash",
                "initiatedByUserId",
            }:
                frappe.throw(
                    _(
                        "Review Event Payload contains an invalid dependency refresh detail."
                    ),
                    frappe.ValidationError,
                )
            required_text(
                detail["reason"],
                _("Dependency Refresh Reason"),
                maximum=140,
            )
            old_hash = lowercase_sha256(
                detail["oldInputHash"],
                _("Old Review Input Hash"),
            )
            new_hash = lowercase_sha256(
                detail["newInputHash"],
                _("New Review Input Hash"),
            )
            if old_hash == new_hash:
                frappe.throw(
                    _("Review invalidation requires a changed input hash."),
                    frappe.ValidationError,
                )
            prior_id = detail["priorDecisionSnapshotGlobalId"]
            prior_hash = detail["priorDecisionHash"]
            has_prior_id = prior_id not in (None, "")
            has_prior_hash = prior_hash not in (None, "")
            if has_prior_id != has_prior_hash or (
                self.event_type == "invalidated" and not has_prior_id
            ):
                frappe.throw(
                    _("The dependency refresh prior decision is incomplete."),
                    frappe.ValidationError,
                )
            if has_prior_id:
                ensure_uuid(
                    prior_id,
                    _("Prior Decision Snapshot Global ID"),
                )
                lowercase_sha256(
                    prior_hash,
                    _("Prior Decision Hash"),
                )
            initiator = detail["initiatedByUserId"]
            if initiator is not None:
                required_text(
                    initiator,
                    _("Dependency Change Initiator"),
                    maximum=254,
                )
