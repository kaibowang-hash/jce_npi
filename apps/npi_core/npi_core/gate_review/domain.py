from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid5

from npi_core.foundation.concurrency import next_version
from npi_core.foundation.errors import (
    NpiProblem,
    RequestValidationFailed,
    VersionConflict,
)

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _(source: str) -> str:
        return source


_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
MAX_REVIEW_STEPS = 32


def _validation(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _text(value: object, path: str, maximum: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise _validation(path, _("Enter a valid value."))
    return value.strip()


def _key(value: object, path: str) -> str:
    result = _text(value, path, 64)
    if _KEY.fullmatch(result) is None:
        raise _validation(path, _("Enter a valid value."))
    return result


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _validation(path, _("Enter a valid SHA-256 hash."))
    return value


def _canonical_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


class PolicyState(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ActivationKind(str, Enum):
    ALWAYS = "always"
    REQUIREMENT_PRIORITY_PRESENT = "requirement_priority_present"


class ReviewOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionOutcome(str, Enum):
    PASS = "pass"
    REJECT = "reject"


class CycleState(str, Enum):
    ACTIVE = "active"
    DECIDED = "decided"
    INVALIDATED = "invalidated"


class ReviewDenied(NpiProblem):
    def __init__(self, code: str, title: str) -> None:
        super().__init__(409, code, _(title))


@dataclass(frozen=True, slots=True)
class ReviewStep:
    key: str
    sequence: int
    authority_slot: str
    activation: ActivationKind = ActivationKind.ALWAYS
    activation_priority: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "steps.key"))
        object.__setattr__(
            self, "authority_slot", _key(self.authority_slot, "steps.authoritySlot")
        )
        if type(self.sequence) is not int or self.sequence < 1:
            raise _validation("steps.sequence", _("Enter a positive sequence."))
        if not isinstance(self.activation, ActivationKind):
            raise _validation("steps.activation", _("Select a supported condition."))
        if (
            self.activation is ActivationKind.ALWAYS
            and self.activation_priority is not None
        ):
            raise _validation(
                "steps.activationPriority",
                _("This condition does not accept a priority."),
            )
        if (
            self.activation is ActivationKind.REQUIREMENT_PRIORITY_PRESENT
            and self.activation_priority not in {"P0", "P1", "P2"}
        ):
            raise _validation(
                "steps.activationPriority",
                _("Select a supported requirement priority."),
            )

    def selected(self, priorities: frozenset[str]) -> bool:
        if self.activation is ActivationKind.ALWAYS:
            return True
        return self.activation_priority in priorities

    def canonical_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "sequence": self.sequence,
            "authoritySlot": self.authority_slot,
            "activation": self.activation.value,
            "activationPriority": self.activation_priority,
        }


@dataclass(frozen=True, slots=True)
class ReviewPolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    policy_code: str
    policy_version: int
    version: int
    state: PolicyState
    gate_template_global_id: UUID
    gate_template_version: int
    gate_template_hash: str
    steps: tuple[ReviewStep, ...]
    decision_authority_slot: str
    reopen_authority_slot: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_code", _key(self.policy_code, "policyCode"))
        object.__setattr__(
            self,
            "decision_authority_slot",
            _key(self.decision_authority_slot, "decisionAuthoritySlot"),
        )
        object.__setattr__(
            self,
            "reopen_authority_slot",
            _key(self.reopen_authority_slot, "reopenAuthoritySlot"),
        )
        _hash(self.gate_template_hash, "gateTemplateHash")
        if (
            self.policy_version < 1
            or self.version < 1
            or self.gate_template_version < 1
        ):
            raise _validation("policyVersion", _("Enter a positive version."))
        steps = tuple(self.steps)
        if not steps or len(steps) > MAX_REVIEW_STEPS:
            raise _validation("steps", _("Enter between one and 32 review steps."))
        if len({step.key.casefold() for step in steps}) != len(steps):
            raise _validation("steps.key", _("Review step keys must be unique."))
        if len({step.authority_slot.casefold() for step in steps}) != len(steps):
            raise _validation(
                "steps.authoritySlot", _("Review authority slots must be unique.")
            )
        review_slots = {step.authority_slot.casefold() for step in steps}
        if (
            self.decision_authority_slot.casefold() in review_slots
            or self.reopen_authority_slot.casefold() in review_slots
        ):
            raise _validation(
                "authoritySlots",
                _(
                    "Decision and reopen authority must be separate from review assignments."
                ),
            )
        object.__setattr__(self, "steps", steps)

    @classmethod
    def create_draft(
        cls,
        *,
        policy_global_id: UUID,
        policy_code: str,
        gate_template_global_id: UUID,
        gate_template_version: int,
        gate_template_hash: str,
        steps: tuple[ReviewStep, ...],
        decision_authority_slot: str,
        reopen_authority_slot: str,
    ) -> ReviewPolicyVersion:
        return cls(
            uuid5(policy_global_id, "version:1"),
            policy_global_id,
            policy_code,
            1,
            1,
            PolicyState.DRAFT,
            gate_template_global_id,
            gate_template_version,
            gate_template_hash,
            steps,
            decision_authority_slot,
            reopen_authority_slot,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "policyGlobalId": str(self.policy_global_id),
            "policyCode": self.policy_code,
            "policyVersion": self.policy_version,
            "gateTemplateGlobalId": str(self.gate_template_global_id),
            "gateTemplateVersion": self.gate_template_version,
            "gateTemplateHash": self.gate_template_hash,
            "steps": [step.canonical_dict() for step in self.steps],
            "decisionAuthoritySlot": self.decision_authority_slot,
            "reopenAuthoritySlot": self.reopen_authority_slot,
        }

    @property
    def snapshot_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())

    def publish(self, expected_version: int) -> ReviewPolicyVersion:
        if self.state is PolicyState.PUBLISHED:
            raise ReviewDenied(
                "PUBLISHED_REVIEW_POLICY_IMMUTABLE",
                "A published review policy version cannot be changed.",
            )
        if expected_version != self.version:
            raise VersionConflict()
        return replace(
            self,
            state=PolicyState.PUBLISHED,
            version=next_version(self.version, self.version),
        )


@dataclass(frozen=True, slots=True)
class AuthorityBinding:
    slot: str
    member_global_id: UUID
    user_id: str
    display_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot", _key(self.slot, "bindings.slot"))
        object.__setattr__(self, "user_id", _text(self.user_id, "bindings.userId", 140))
        object.__setattr__(
            self, "display_name", _text(self.display_name, "bindings.displayName", 140)
        )


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    step_key: str
    actor_user_id: str
    outcome: ReviewOutcome
    opinion: str
    occurred_at: datetime
    reviewed_input_hash: str
    policy_version: int
    policy_hash: str


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    cycle_global_id: UUID
    outcome: DecisionOutcome
    actor_user_id: str
    occurred_at: datetime
    policy_version: int
    policy_hash: str
    input_hash: str
    review_hashes: tuple[str, ...]
    snapshot_hash: str


@dataclass(frozen=True, slots=True)
class ReviewCycle:
    global_id: UUID
    gate_global_id: UUID
    project_global_id: UUID
    tenant_id: str
    cycle_number: int
    policy: ReviewPolicyVersion
    bindings: tuple[AuthorityBinding, ...]
    selected_steps: tuple[ReviewStep, ...]
    input_hash: str
    version: int = 1
    state: CycleState = CycleState.ACTIVE
    reviews: tuple[ReviewRecord, ...] = ()
    decision: DecisionSnapshot | None = None
    prior_decision_hash: str | None = None

    @classmethod
    def start(
        cls,
        *,
        gate_global_id: UUID,
        project_global_id: UUID,
        tenant_id: str,
        cycle_number: int,
        policy: ReviewPolicyVersion,
        bindings: tuple[AuthorityBinding, ...],
        requirement_priorities: frozenset[str],
        input_hash: str,
        prior_decision_hash: str | None = None,
    ) -> ReviewCycle:
        if policy.state is not PolicyState.PUBLISHED:
            raise ReviewDenied(
                "REVIEW_POLICY_UNAVAILABLE", "A published review policy is required."
            )
        _hash(input_hash, "inputHash")
        selected = tuple(
            step for step in policy.steps if step.selected(requirement_priorities)
        )
        required_slots = {step.authority_slot for step in selected} | {
            policy.decision_authority_slot,
            policy.reopen_authority_slot,
        }
        mapping = {binding.slot: binding for binding in bindings}
        if len(mapping) != len(bindings) or set(mapping) != required_slots:
            raise _validation(
                "bindings",
                _("Bind every selected review and decision authority exactly once."),
            )
        return cls(
            uuid5(gate_global_id, f"review-cycle:{cycle_number}"),
            gate_global_id,
            project_global_id,
            _text(tenant_id, "tenantId", 140),
            cycle_number,
            policy,
            tuple(bindings),
            selected,
            input_hash,
            prior_decision_hash=prior_decision_hash,
        )

    def _binding(self, slot: str) -> AuthorityBinding:
        return next(value for value in self.bindings if value.slot == slot)

    def submit_review(
        self,
        *,
        step_key: str,
        actor_user_id: str,
        outcome: ReviewOutcome,
        opinion: str,
        occurred_at: datetime,
        expected_version: int,
        expected_input_hash: str,
    ) -> ReviewCycle:
        if self.state is not CycleState.ACTIVE:
            raise ReviewDenied(
                "REVIEW_CYCLE_CLOSED", "This review cycle is not active."
            )
        if expected_version != self.version or expected_input_hash != self.input_hash:
            raise VersionConflict()
        try:
            step = next(value for value in self.selected_steps if value.key == step_key)
        except StopIteration as error:
            raise ReviewDenied(
                "REVIEW_STEP_NOT_SELECTED", "This review step is not selected."
            ) from error
        if any(value.step_key == step.key for value in self.reviews):
            raise ReviewDenied(
                "REVIEW_ALREADY_RECORDED", "This review has already been recorded."
            )
        if self._binding(step.authority_slot).user_id != actor_user_id:
            raise ReviewDenied(
                "REVIEW_AUTHORITY_REQUIRED", "The assigned reviewer is required."
            )
        earlier = [
            value for value in self.selected_steps if value.sequence < step.sequence
        ]
        approved = {
            value.step_key
            for value in self.reviews
            if value.outcome is ReviewOutcome.APPROVED
        }
        if any(value.key not in approved for value in earlier):
            raise ReviewDenied(
                "REVIEW_SEQUENCE_BLOCKED",
                "Complete every earlier review sequence first.",
            )
        if not isinstance(outcome, ReviewOutcome):
            raise _validation("outcome", _("Select a supported review outcome."))
        record = ReviewRecord(
            step.key,
            actor_user_id,
            outcome,
            _text(opinion, "opinion"),
            occurred_at,
            self.input_hash,
            self.policy.policy_version,
            self.policy.snapshot_hash,
        )
        return replace(
            self,
            reviews=(*self.reviews, record),
            version=next_version(self.version, self.version),
        )

    def decide(
        self,
        *,
        actor_user_id: str,
        outcome: DecisionOutcome,
        occurred_at: datetime,
        expected_version: int,
        expected_input_hash: str,
        required_evidence_complete: bool,
        file_evidence_safe: bool,
        blocking_items: int,
    ) -> ReviewCycle:
        if self.state is not CycleState.ACTIVE:
            raise ReviewDenied(
                "REVIEW_CYCLE_CLOSED", "This review cycle is not active."
            )
        if expected_version != self.version or expected_input_hash != self.input_hash:
            raise VersionConflict()
        if self._binding(self.policy.decision_authority_slot).user_id != actor_user_id:
            raise ReviewDenied(
                "DECISION_AUTHORITY_REQUIRED",
                "The assigned decision authority is required.",
            )
        if outcome is DecisionOutcome.PASS:
            approved = {
                value.step_key
                for value in self.reviews
                if value.outcome is ReviewOutcome.APPROVED
            }
            if any(value.key not in approved for value in self.selected_steps):
                raise ReviewDenied(
                    "REVIEWS_INCOMPLETE",
                    "Every selected review must approve before this Gate can pass.",
                )
            if not required_evidence_complete:
                raise ReviewDenied(
                    "REQUIRED_EVIDENCE_MISSING", "Required evidence is missing."
                )
            if not file_evidence_safe:
                raise ReviewDenied(
                    "FILE_EVIDENCE_UNSAFE", "File evidence is not safe and current."
                )
            if type(blocking_items) is not int or blocking_items < 0:
                raise _validation("blockingItems", _("Enter a valid blocker count."))
            if blocking_items:
                raise ReviewDenied(
                    "GATE_BLOCKED",
                    "Resolve every blocking item before this Gate can pass.",
                )
        review_hashes = tuple(
            _canonical_hash(
                {
                    "stepKey": value.step_key,
                    "actorUserId": value.actor_user_id,
                    "outcome": value.outcome.value,
                    "opinion": value.opinion,
                    "occurredAt": value.occurred_at.astimezone(
                        timezone.utc
                    ).isoformat(),
                    "reviewedInputHash": value.reviewed_input_hash,
                }
            )
            for value in self.reviews
        )
        payload = {
            "cycleGlobalId": str(self.global_id),
            "outcome": outcome.value,
            "actorUserId": actor_user_id,
            "occurredAt": occurred_at.astimezone(timezone.utc).isoformat(),
            "policyVersion": self.policy.policy_version,
            "policyHash": self.policy.snapshot_hash,
            "inputHash": self.input_hash,
            "reviewHashes": list(review_hashes),
        }
        decision = DecisionSnapshot(
            self.global_id,
            outcome,
            actor_user_id,
            occurred_at,
            self.policy.policy_version,
            self.policy.snapshot_hash,
            self.input_hash,
            review_hashes,
            _canonical_hash(payload),
        )
        return replace(
            self,
            state=CycleState.DECIDED,
            decision=decision,
            version=next_version(self.version, self.version),
        )

    def reopen(
        self,
        *,
        actor_user_id: str,
        reason: str,
        occurred_at: datetime,
        current_input_hash: str,
    ) -> ReviewCycle:
        del occurred_at  # Event persistence owns the timestamp; it is intentionally not caller-derived state.
        if self.state is not CycleState.DECIDED or self.decision is None:
            raise ReviewDenied(
                "DECISION_REQUIRED",
                "A completed decision is required before reopening.",
            )
        if self._binding(self.policy.reopen_authority_slot).user_id != actor_user_id:
            raise ReviewDenied(
                "REOPEN_AUTHORITY_REQUIRED",
                "The assigned reopen authority is required.",
            )
        _text(reason, "reason")
        _hash(current_input_hash, "inputHash")
        return ReviewCycle.start(
            gate_global_id=self.gate_global_id,
            project_global_id=self.project_global_id,
            tenant_id=self.tenant_id,
            cycle_number=self.cycle_number + 1,
            policy=self.policy,
            bindings=self.bindings,
            requirement_priorities=frozenset(
                step.activation_priority
                for step in self.selected_steps
                if step.activation_priority
            ),
            input_hash=current_input_hash,
            prior_decision_hash=self.decision.snapshot_hash,
        )


def downstream_decision_is_current(cycle: ReviewCycle, current_input_hash: str) -> bool:
    return (
        cycle.state is CycleState.DECIDED
        and cycle.decision is not None
        and cycle.decision.outcome is DecisionOutcome.PASS
        and cycle.input_hash == current_input_hash
    )
