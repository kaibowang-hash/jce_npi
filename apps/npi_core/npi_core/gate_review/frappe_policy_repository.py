from __future__ import annotations

import json
from uuid import UUID, uuid5

import frappe

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.gate_review.domain import (
    ActivationKind,
    DependencyEvaluator,
    ExceptionRule,
    PolicyState,
    ReviewPolicyVersion,
    ReviewStep,
)
from npi_core.gate_template.frappe_repository import (
    load_published_gate_template_version,
)


def load_published_gate_review_policy_version(
    policy_global_id: UUID,
    policy_version: int,
    expected_snapshot_hash: str,
    *,
    require_enabled_root: bool = False,
) -> ReviewPolicyVersion | None:
    """Load one exact published policy and reject any persisted drift."""
    version_key = f"{policy_global_id}:{policy_version}"
    document = _optional_doc("NPI Gate Review Policy Version", version_key)
    if document is None:
        return None
    root = _optional_doc("NPI Gate Review Policy", str(document.gate_review_policy))
    if root is None or (require_enabled_root and int(root.enabled or 0) != 1):
        return None
    if (
        str(root.global_id) != str(document.policy_global_id)
        or str(root.global_id) != str(policy_global_id)
        or str(root.policy_code) != str(document.policy_code)
        or str(document.gate_review_policy) != str(root.global_id)
    ):
        raise ValueError("Persisted Gate Review Policy root integrity failed.")

    try:
        steps = _review_steps(document.review_steps)
        exceptions = _exception_rules(document.exception_rules)
        dependencies = _dependency_evaluators(document.dependency_evaluators)
        policy = ReviewPolicyVersion(
            global_id=UUID(str(document.global_id)),
            policy_global_id=UUID(str(document.policy_global_id)),
            policy_code=str(document.policy_code),
            policy_version=int(document.policy_version),
            version=int(document.optimistic_version),
            state=PolicyState(str(document.publication_state)),
            gate_template_global_id=UUID(str(document.gate_template_global_id)),
            gate_template_version=int(document.gate_template_version),
            gate_template_hash=str(document.gate_template_snapshot_hash),
            steps=steps,
            decision_authority_slot=str(document.decision_authority_slot),
            reopen_authority_slot=str(document.reopen_authority_slot),
            exception_rules=exceptions,
            dependency_evaluators=dependencies,
        )
    except (RequestValidationFailed, TypeError, ValueError) as error:
        raise ValueError(
            "Persisted Gate Review Policy content integrity failed."
        ) from error

    expected_global_id = uuid5(
        policy.policy_global_id,
        f"version:{policy.policy_version}",
    )
    canonical_snapshot = _canonical(policy.canonical_dict())
    if (
        policy.state is not PolicyState.PUBLISHED
        or policy.policy_global_id != policy_global_id
        or policy.policy_version != policy_version
        or policy.global_id != expected_global_id
        or str(document.version_key) != version_key
        or not document.published_at
        or str(document.review_steps)
        != _canonical([step.canonical_dict() for step in policy.steps])
        or str(document.exception_rules)
        != _canonical([rule.canonical_dict() for rule in policy.exception_rules])
        or str(document.dependency_evaluators)
        != _canonical([value.value for value in policy.dependency_evaluators])
        or str(document.snapshot) != canonical_snapshot
        or str(document.snapshot_hash) != policy.snapshot_hash
        or expected_snapshot_hash != policy.snapshot_hash
    ):
        raise ValueError("Persisted Gate Review Policy version integrity failed.")

    try:
        template = load_published_gate_template_version(
            policy.gate_template_global_id,
            policy.gate_template_version,
            policy.gate_template_hash,
        )
    except (RequestValidationFailed, TypeError, ValueError) as error:
        raise ValueError(
            "Persisted Gate Review Policy template reference integrity failed."
        ) from error
    if template is None:
        raise ValueError(
            "Persisted Gate Review Policy template reference integrity failed."
        )
    return policy


def load_exact_gate_review_policy_version(
    policy_global_id: UUID,
    policy_version: int,
    expected_snapshot_hash: str,
) -> ReviewPolicyVersion | None:
    """Return historical exact policy even if its administrative root is disabled."""
    return load_published_gate_review_policy_version(
        policy_global_id,
        policy_version,
        expected_snapshot_hash,
    )


def load_available_gate_review_policy_version(
    policy_global_id: UUID,
    policy_version: int,
    expected_snapshot_hash: str,
) -> ReviewPolicyVersion | None:
    """Return an exact published policy only while its root is selectable."""
    return load_published_gate_review_policy_version(
        policy_global_id,
        policy_version,
        expected_snapshot_hash,
        require_enabled_root=True,
    )


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _review_steps(value: object) -> tuple[ReviewStep, ...]:
    parsed = _json_array(value, "review steps")
    expected_fields = {
        "key",
        "sequence",
        "authoritySlot",
        "activation",
        "activationPriority",
    }
    if any(
        not isinstance(item, dict) or set(item) != expected_fields for item in parsed
    ):
        raise ValueError("Persisted review steps are not closed.")
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
    parsed = _json_array(value, "exception rules")
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
        raise ValueError("Persisted exception rules are not closed.")
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
    parsed = _json_array(value, "dependency evaluators")
    if any(not isinstance(item, str) for item in parsed):
        raise ValueError("Persisted dependency evaluators are not closed.")
    return tuple(DependencyEvaluator(item) for item in parsed)


def _json_array(value: object, label: str) -> list[object]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"Persisted {label} must be a JSON array.") from error
    if not isinstance(parsed, list):
        raise TypeError(f"Persisted {label} must be a JSON array.")
    return parsed


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
