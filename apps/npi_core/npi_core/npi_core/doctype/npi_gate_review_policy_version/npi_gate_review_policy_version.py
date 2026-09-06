from __future__ import annotations

from uuid import UUID, uuid5

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.gate_review.domain import (
    ActivationKind,
    DependencyEvaluator,
    ExceptionRule,
    PolicyState,
    ReviewPolicyVersion,
    ReviewStep,
)
from npi_core.gate_review.frappe_validation import (
    assert_immutable_fields,
    canonical_json,
    ensure_uuid,
    positive_integer,
    required_text,
)
from npi_core.gate_template.frappe_repository import (
    load_published_gate_template_version,
)
from npi_core.project.frappe_validation import throw_domain_validation


class NPIGateReviewPolicyVersion(Document):
    """Versioned administrative definition; published policy is immutable."""

    _IDENTITY_FIELDS = (
        "global_id",
        "gate_review_policy",
        "policy_global_id",
        "policy_code",
        "policy_version",
        "version_key",
    )

    def autoname(self) -> None:
        self._set_policy_identity()
        self.name = self.version_key

    def before_validate(self) -> None:
        self._set_policy_identity()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and previous.publication_state == "published":
            frappe.throw(
                _("A published Gate Review Policy version cannot be changed."),
                frappe.ValidationError,
            )
        self._validate_new_version_sequence(previous)
        if previous is not None:
            assert_immutable_fields(self, previous, self._IDENTITY_FIELDS)

        self.title = required_text(
            self.title,
            _("Gate Review Policy Version Title"),
            maximum=140,
        )
        self.gate_template_global_id = ensure_uuid(
            self.gate_template_global_id,
            _("Gate Template Global ID"),
        )
        self.gate_template_version = positive_integer(
            self.gate_template_version,
            _("Gate Template Version"),
        )
        try:
            gate_template = load_published_gate_template_version(
                UUID(self.gate_template_global_id),
                self.gate_template_version,
                self.gate_template_snapshot_hash,
                require_enabled_root=True,
            )
        except (RequestValidationFailed, TypeError, ValueError):
            gate_template = None
        if gate_template is None:
            frappe.throw(
                _("Select an exact published Gate Template version."),
                frappe.ValidationError,
            )

        try:
            requested_state = PolicyState(self.publication_state or "draft")
            base_version = (
                positive_integer(
                    int(previous.optimistic_version),
                    _("Optimistic Version"),
                )
                if previous is not None
                else 1
            )
            if requested_state is PolicyState.PUBLISHED:
                policy = self._domain_policy(
                    state=PolicyState.DRAFT,
                    optimistic_version=base_version,
                ).publish(base_version)
            else:
                policy = self._domain_policy(
                    state=PolicyState.DRAFT,
                    optimistic_version=(
                        base_version + 1 if previous is not None else base_version
                    ),
                )
        except RequestValidationFailed as error:
            throw_domain_validation(error)
        except (TypeError, ValueError):
            frappe.throw(
                _("Enter a valid Gate Review Policy."),
                frappe.ValidationError,
            )
        else:
            self._apply_domain_policy(policy)

    def on_trash(self) -> None:
        if self.publication_state == "published":
            frappe.throw(
                _("A published Gate Review Policy version cannot be deleted."),
                frappe.PermissionError,
            )

    def _set_policy_identity(self) -> None:
        root = frappe.db.get_value(
            "NPI Gate Review Policy",
            self.gate_review_policy,
            ["global_id", "policy_code"],
            as_dict=True,
        )
        if root is None:
            frappe.throw(
                _("Select an existing Gate Review Policy."),
                frappe.ValidationError,
            )
        self.policy_global_id = ensure_uuid(
            root.global_id,
            _("Policy Global ID"),
        )
        self.policy_code = root.policy_code
        self.policy_version = positive_integer(
            self.policy_version,
            _("Policy Version"),
        )
        expected_global_id = uuid5(
            UUID(self.policy_global_id),
            f"version:{self.policy_version}",
        )
        if self.global_id:
            supplied_global_id = ensure_uuid(self.global_id, _("Global ID"))
            if UUID(supplied_global_id) != expected_global_id:
                frappe.throw(
                    _("Enter a valid Gate Review Policy version."),
                    frappe.ValidationError,
                )
        self.global_id = str(expected_global_id)
        self.version_key = f"{self.policy_global_id}:{self.policy_version}"

    def _validate_new_version_sequence(self, previous: object) -> None:
        if previous is not None:
            return
        if self.policy_version == 1:
            existing = frappe.db.get_value(
                "NPI Gate Review Policy Version",
                {"policy_global_id": self.policy_global_id},
                ["name"],
                as_dict=True,
            )
            valid_sequence = existing is None
        else:
            prior = frappe.db.get_value(
                "NPI Gate Review Policy Version",
                f"{self.policy_global_id}:{self.policy_version - 1}",
                ["publication_state"],
                as_dict=True,
            )
            valid_sequence = (
                prior is not None and prior.publication_state == "published"
            )
        if not valid_sequence:
            frappe.throw(
                _("Publish each Gate Review Policy version before creating the next."),
                frappe.ValidationError,
            )

    def _domain_policy(
        self,
        *,
        state: PolicyState,
        optimistic_version: int,
    ) -> ReviewPolicyVersion:
        steps = _review_steps(self.review_steps)
        exceptions = _exception_rules(self.exception_rules)
        dependencies = _dependency_evaluators(self.dependency_evaluators)
        return ReviewPolicyVersion(
            global_id=UUID(self.global_id),
            policy_global_id=UUID(self.policy_global_id),
            policy_code=self.policy_code,
            policy_version=self.policy_version,
            version=optimistic_version,
            state=state,
            gate_template_global_id=UUID(self.gate_template_global_id),
            gate_template_version=self.gate_template_version,
            gate_template_hash=self.gate_template_snapshot_hash,
            steps=steps,
            decision_authority_slot=self.decision_authority_slot,
            reopen_authority_slot=self.reopen_authority_slot,
            exception_rules=exceptions,
            dependency_evaluators=dependencies,
        )

    def _apply_domain_policy(self, policy: ReviewPolicyVersion) -> None:
        snapshot = policy.canonical_dict()
        self.policy_code = policy.policy_code
        self.optimistic_version = policy.version
        self.publication_state = policy.state.value
        self.gate_template_global_id = str(policy.gate_template_global_id)
        self.gate_template_version = policy.gate_template_version
        self.gate_template_snapshot_hash = policy.gate_template_hash
        self.review_steps = _canonical(snapshot["steps"])
        self.decision_authority_slot = policy.decision_authority_slot
        self.reopen_authority_slot = policy.reopen_authority_slot
        self.exception_rules = _canonical(snapshot["exceptionRules"])
        self.dependency_evaluators = _canonical(snapshot["dependencyEvaluators"])
        self.snapshot = _canonical(snapshot)
        self.snapshot_hash = policy.snapshot_hash
        self.published_at = (
            now_datetime() if policy.state is PolicyState.PUBLISHED else None
        )


def _review_steps(value: object) -> tuple[ReviewStep, ...]:
    parsed, _encoded = canonical_json(
        value,
        _("Review Steps"),
        expected_type=list,
    )
    expected_fields = {
        "key",
        "sequence",
        "authoritySlot",
        "activation",
        "activationPriority",
    }
    if any(
        not isinstance(item, dict)
        or set(item) != expected_fields
        for item in parsed
    ):
        frappe.throw(
            _("Review Steps contains an unsupported field."),
            frappe.ValidationError,
        )
    return tuple(
        ReviewStep(
            key=item["key"],
            sequence=item["sequence"],
            authority_slot=item["authoritySlot"],
            activation=ActivationKind(item["activation"]),
            activation_priority=item["activationPriority"],
        )
        for item in parsed
    )


def _exception_rules(value: object) -> tuple[ExceptionRule, ...]:
    parsed, _encoded = canonical_json(
        value,
        _("Exception Rules"),
        expected_type=list,
    )
    expected_fields = {
        "kind",
        "eligibleRequirementKeys",
        "approvalAuthoritySlot",
        "maximumValidityDays",
        "requiredClosureActionKind",
    }
    if any(
        not isinstance(item, dict)
        or set(item) != expected_fields
        or not isinstance(item["eligibleRequirementKeys"], list)
        for item in parsed
    ):
        frappe.throw(
            _("Exception Rules contains an unsupported field."),
            frappe.ValidationError,
        )
    return tuple(
        ExceptionRule(
            kind=item["kind"],
            eligible_requirement_keys=tuple(item["eligibleRequirementKeys"]),
            approval_authority_slot=item["approvalAuthoritySlot"],
            maximum_validity_days=item["maximumValidityDays"],
            required_closure_action_kind=item["requiredClosureActionKind"],
        )
        for item in parsed
    )


def _dependency_evaluators(value: object) -> tuple[DependencyEvaluator, ...]:
    parsed, _encoded = canonical_json(
        value,
        _("Dependency Evaluators"),
        expected_type=list,
    )
    if any(not isinstance(item, str) for item in parsed):
        frappe.throw(
            _("Dependency Evaluators contains an unsupported value."),
            frappe.ValidationError,
        )
    return tuple(DependencyEvaluator(item) for item in parsed)


def _canonical(value: object) -> str:
    _parsed, encoded = canonical_json(
        value,
        _("Canonical Policy Snapshot"),
        expected_type=type(value) if isinstance(value, (dict, list)) else dict,
    )
    return encoded
