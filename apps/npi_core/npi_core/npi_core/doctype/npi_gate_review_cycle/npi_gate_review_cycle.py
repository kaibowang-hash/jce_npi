from __future__ import annotations

from uuid import UUID, uuid5

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

_TRIGGERS = {"manual_start", "manual_reopen", "dependency_change"}
_STATES = {"active", "decided", "invalidated", "superseded"}
_TRANSITIONS = {
    ("active", "active"),
    ("active", "decided"),
    ("active", "superseded"),
    ("decided", "invalidated"),
}


class NPIGateReviewCycle(Document):
    """Frozen review input and policy binding with a narrow lifecycle."""

    _IMMUTABLE_FIELDS = (
        "global_id",
        "cycle_key",
        "tenant_id",
        "project_global_id",
        "gate_global_id",
        "gate_shell",
        "cycle_number",
        "trigger",
        "policy_global_id",
        "policy_version",
        "policy_snapshot_hash",
        "policy_snapshot",
        "authority_bindings",
        "selected_steps",
        "input_snapshot",
        "input_hash",
        "prior_cycle_global_id",
        "prior_decision_snapshot_global_id",
        "prior_decision_hash",
        "started_by",
        "started_at",
    )

    def autoname(self) -> None:
        self._normalize()
        self.name = self.global_id

    def before_insert(self) -> None:
        require_gate_review_command_write()

    def before_save(self) -> None:
        require_gate_review_command_write()

    def on_trash(self) -> None:
        deny_gate_review_history_delete()

    def before_validate(self) -> None:
        self._normalize()
        if self.is_new():
            self.state = "active"
            self.optimistic_version = 1

    def validate(self) -> None:
        self._normalize()
        if self.trigger not in _TRIGGERS or self.state not in _STATES:
            frappe.throw(
                _("Select a supported Gate review cycle state."),
                frappe.ValidationError,
            )
        self._validate_frozen_snapshots()
        self._validate_prior_decision()
        previous = self.get_doc_before_save()
        if previous is None:
            if self.state != "active" or self.optimistic_version != 1:
                frappe.throw(
                    _("A new Gate review cycle must start active at version one."),
                    frappe.ValidationError,
                )
            return
        assert_immutable_fields(self, previous, self._IMMUTABLE_FIELDS)
        if (str(previous.state), str(self.state)) not in _TRANSITIONS:
            frappe.throw(
                _("The Gate review cycle state transition is not allowed."),
                frappe.ValidationError,
            )
        if int(self.optimistic_version) != int(previous.optimistic_version) + 1:
            frappe.throw(
                _("Optimistic Version must advance by one."),
                frappe.ValidationError,
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
        self.policy_global_id = ensure_uuid(
            self.policy_global_id,
            _("Review Policy Global ID"),
        )
        self.cycle_number = positive_integer(
            self.cycle_number,
            _("Review Cycle Number"),
        )
        self.policy_version = positive_integer(
            self.policy_version,
            _("Review Policy Version"),
        )
        self.cycle_key = f"{self.gate_global_id}:{self.cycle_number}"
        if str(self.gate_shell) != self.gate_global_id:
            frappe.throw(
                _("Gate Shell must match the exact Gate Global ID."),
                frappe.ValidationError,
            )
        self.tenant_id = required_text(
            self.tenant_id,
            _("Tenant ID"),
            maximum=140,
        )
        self.started_by = required_text(
            self.started_by,
            _("Started By"),
            maximum=254,
        )
        canonical_datetime(self.started_at, _("Started At"))
        if self.optimistic_version:
            self.optimistic_version = positive_integer(
                self.optimistic_version,
                _("Optimistic Version"),
            )

    def _validate_frozen_snapshots(self) -> None:
        policy, self.policy_snapshot = canonical_json(
            self.policy_snapshot,
            _("Review Policy Snapshot"),
            expected_type=dict,
        )
        self.policy_snapshot_hash = lowercase_sha256(
            self.policy_snapshot_hash,
            _("Review Policy Snapshot Hash"),
        )
        if (
            canonical_json_hash(policy) != self.policy_snapshot_hash
            or policy.get("policyGlobalId") != self.policy_global_id
            or policy.get("policyVersion") != self.policy_version
        ):
            frappe.throw(
                _("Review Policy Snapshot does not match its exact reference."),
                frappe.ValidationError,
            )

        bindings, self.authority_bindings = canonical_json(
            self.authority_bindings,
            _("Authority Bindings"),
            expected_type=list,
        )
        selected_steps, self.selected_steps = canonical_json(
            self.selected_steps,
            _("Selected Review Steps"),
            expected_type=list,
        )
        self._validate_bindings(bindings)
        self._validate_selected_steps(selected_steps, bindings)

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

    @staticmethod
    def _validate_bindings(bindings: list[object]) -> None:
        if not bindings:
            frappe.throw(
                _("Bind every selected Gate review authority."),
                frappe.ValidationError,
            )
        slots: set[str] = set()
        for binding in bindings:
            if not isinstance(binding, dict) or set(binding) != {
                "slot",
                "memberGlobalId",
                "userId",
                "displayName",
            }:
                frappe.throw(
                    _("Authority Bindings contain an invalid binding."),
                    frappe.ValidationError,
                )
            slot = controlled_key(binding["slot"], _("Authority Slot"))
            ensure_uuid(binding["memberGlobalId"], _("Member Global ID"))
            required_text(binding["userId"], _("Assigned User"), maximum=254)
            required_text(binding["displayName"], _("Assigned Member"), maximum=140)
            if slot.casefold() in slots:
                frappe.throw(
                    _("Authority Binding slots must be unique."),
                    frappe.ValidationError,
                )
            slots.add(slot.casefold())

    @staticmethod
    def _validate_selected_steps(
        selected_steps: list[object],
        bindings: list[object],
    ) -> None:
        if not selected_steps:
            frappe.throw(
                _("Select at least one Gate review step."),
                frappe.ValidationError,
            )
        binding_slots = {
            str(binding["slot"]).casefold()
            for binding in bindings
            if isinstance(binding, dict)
        }
        keys: set[str] = set()
        for step in selected_steps:
            if not isinstance(step, dict) or set(step) != {
                "key",
                "sequence",
                "authoritySlot",
                "activation",
                "activationPriority",
            }:
                frappe.throw(
                    _("Selected Review Steps contain an invalid step."),
                    frappe.ValidationError,
                )
            key = controlled_key(step["key"], _("Review Step Key"))
            slot = controlled_key(step["authoritySlot"], _("Authority Slot"))
            positive_integer(step["sequence"], _("Review Step Sequence"))
            if step["activation"] not in {
                "always",
                "requirement_priority_present",
            }:
                frappe.throw(
                    _("Select a supported review activation."),
                    frappe.ValidationError,
                )
            if (
                step["activation"] == "always"
                and step["activationPriority"] is not None
            ) or (
                step["activation"] == "requirement_priority_present"
                and step["activationPriority"] not in {"P0", "P1", "P2"}
            ):
                frappe.throw(
                    _("Select a supported review activation priority."),
                    frappe.ValidationError,
                )
            if key.casefold() in keys or slot.casefold() not in binding_slots:
                frappe.throw(
                    _("Selected Review Steps do not match their authority bindings."),
                    frappe.ValidationError,
                )
            keys.add(key.casefold())

    def _validate_prior_decision(self) -> None:
        prior_cycle = self.prior_cycle_global_id not in (None, "")
        decision_values = (
            self.prior_decision_snapshot_global_id,
            self.prior_decision_hash,
        )
        has_decision = [value not in (None, "") for value in decision_values]
        if self.cycle_number == 1:
            if self.trigger != "manual_start" or prior_cycle or any(has_decision):
                frappe.throw(
                    _("An initial review cycle cannot reference a prior decision."),
                    frappe.ValidationError,
                )
            return
        if self.trigger == "manual_start" or not prior_cycle:
            frappe.throw(
                _("A successor review cycle requires the exact prior cycle."),
                frappe.ValidationError,
            )
        self.prior_cycle_global_id = ensure_uuid(
            self.prior_cycle_global_id,
            _("Prior Review Cycle Global ID"),
        )
        expected_prior_cycle = str(
            uuid5(
                UUID(self.gate_global_id),
                f"review-cycle:{self.cycle_number - 1}",
            )
        )
        if self.prior_cycle_global_id != expected_prior_cycle:
            frappe.throw(
                _("The prior review cycle identifier is not canonical."),
                frappe.ValidationError,
            )
        if any(has_decision) != all(has_decision) or (
            self.trigger == "manual_reopen" and not all(has_decision)
        ):
            frappe.throw(
                _("The successor prior decision reference is incomplete."),
                frappe.ValidationError,
            )
        if not any(has_decision):
            self.prior_decision_snapshot_global_id = None
            self.prior_decision_hash = None
            return
        self.prior_decision_snapshot_global_id = ensure_uuid(
            self.prior_decision_snapshot_global_id,
            _("Prior Decision Snapshot Global ID"),
        )
        self.prior_decision_hash = lowercase_sha256(
            self.prior_decision_hash,
            _("Prior Decision Hash"),
        )
