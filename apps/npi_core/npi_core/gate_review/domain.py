from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TypeVar
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

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
MAX_REVIEW_STEPS = 32
MAX_EXCEPTION_RULES = 32
MAX_EXCEPTION_VALIDITY_DAYS = 3650
MAX_REQUIREMENTS = 256
MAX_EVIDENCE = 512
MAX_BLOCKERS = 256
MAX_DEPENDENCIES = 256
_EnumValue = TypeVar("_EnumValue", bound=Enum)


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


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise _validation(path, _("Enter a valid identifier."))
    return value


def _positive_int(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _validation(path, _("Enter a positive integer."))
    return value


def _non_negative_int(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _validation(path, _("Enter a non-negative integer."))
    return value


def _bool(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _validation(path, _("Select a valid true or false value."))
    return value


def _enum(value: object, expected: type[_EnumValue], path: str) -> _EnumValue:
    if type(value) is not expected:
        raise _validation(path, _("Select a supported value."))
    return value


def _aware(value: object, path: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise _validation(path, _("Enter a timezone-aware date and time."))
    return value.astimezone(timezone.utc)


def _priority(value: object, path: str) -> str:
    if value not in {"P0", "P1", "P2"} or not isinstance(value, str):
        raise _validation(path, _("Select a supported requirement priority."))
    return value


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


class PolicyState(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ActivationKind(str, Enum):
    ALWAYS = "always"
    REQUIREMENT_PRIORITY_PRESENT = "requirement_priority_present"


class DependencyEvaluator(str, Enum):
    GATE_INPUT_SNAPSHOT = "gate_input_snapshot"


class ReviewOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionOutcome(str, Enum):
    PASS = "pass"
    CONDITIONAL_PASS = "conditional_pass"
    REJECT = "reject"


class CycleState(str, Enum):
    ACTIVE = "active"
    DECIDED = "decided"
    INVALIDATED = "invalidated"
    SUPERSEDED = "superseded"


class CycleTrigger(str, Enum):
    MANUAL_START = "manual_start"
    MANUAL_REOPEN = "manual_reopen"
    DEPENDENCY_CHANGE = "dependency_change"


class ExceptionOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ExceptionState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewEventKind(str, Enum):
    EXCEPTION_DECIDED = "exception_decided"
    REOPENED = "reopened"
    INVALIDATED = "invalidated"
    REFRESHED = "refreshed"


class ReviewDenied(NpiProblem):
    def __init__(self, code: str, title: str) -> None:
        super().__init__(409, code, title)


@dataclass(frozen=True, slots=True)
class GateRequirementInput:
    global_id: UUID
    requirement_key: str
    priority: str
    source_version: int
    source_hash: str
    evidence_complete: bool

    def __post_init__(self) -> None:
        _uuid(self.global_id, "requirements.globalId")
        object.__setattr__(
            self, "requirement_key", _key(self.requirement_key, "requirements.key")
        )
        object.__setattr__(
            self, "priority", _priority(self.priority, "requirements.priority")
        )
        _positive_int(self.source_version, "requirements.sourceVersion")
        _hash(self.source_hash, "requirements.sourceHash")
        _bool(self.evidence_complete, "requirements.evidenceComplete")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "requirementKey": self.requirement_key,
            "priority": self.priority,
            "sourceVersion": self.source_version,
            "sourceHash": self.source_hash,
            "evidenceComplete": self.evidence_complete,
        }


@dataclass(frozen=True, slots=True)
class GateEvidenceInput:
    global_id: UUID
    requirement_global_id: UUID
    evidence_kind: str
    source_global_id: UUID
    source_version: int
    source_hash: str
    is_file: bool
    file_safe: bool

    def __post_init__(self) -> None:
        _uuid(self.global_id, "evidence.globalId")
        _uuid(self.requirement_global_id, "evidence.requirementGlobalId")
        object.__setattr__(
            self, "evidence_kind", _key(self.evidence_kind, "evidence.kind")
        )
        _uuid(self.source_global_id, "evidence.sourceGlobalId")
        _positive_int(self.source_version, "evidence.sourceVersion")
        _hash(self.source_hash, "evidence.sourceHash")
        _bool(self.is_file, "evidence.isFile")
        _bool(self.file_safe, "evidence.fileSafe")
        if not self.is_file and not self.file_safe:
            raise _validation(
                "evidence.fileSafe",
                _("Only file evidence can have a file-safety failure."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "requirementGlobalId": str(self.requirement_global_id),
            "evidenceKind": self.evidence_kind,
            "sourceGlobalId": str(self.source_global_id),
            "sourceVersion": self.source_version,
            "sourceHash": self.source_hash,
            "isFile": self.is_file,
            "fileSafe": self.file_safe,
        }


@dataclass(frozen=True, slots=True)
class GateBlockerInput:
    global_id: UUID
    version: int
    state: str
    blocking: bool
    terminal: bool

    def __post_init__(self) -> None:
        _uuid(self.global_id, "blockers.globalId")
        _positive_int(self.version, "blockers.version")
        object.__setattr__(self, "state", _key(self.state, "blockers.state"))
        _bool(self.blocking, "blockers.blocking")
        _bool(self.terminal, "blockers.terminal")

    @property
    def active(self) -> bool:
        return self.blocking and not self.terminal

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "state": self.state,
            "blocking": self.blocking,
            "terminal": self.terminal,
        }


@dataclass(frozen=True, slots=True)
class GateDependencyInput:
    kind: DependencyEvaluator
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        _enum(self.kind, DependencyEvaluator, "dependencies.kind")
        _uuid(self.global_id, "dependencies.globalId")
        _positive_int(self.version, "dependencies.version")
        _hash(self.snapshot_hash, "dependencies.snapshotHash")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class GateInputSnapshot:
    gate_global_id: UUID
    project_global_id: UUID
    tenant_id: str
    # Stable review-input version; review pointer/decision persistence must not bump it.
    gate_version: int
    requirements: tuple[GateRequirementInput, ...]
    evidence: tuple[GateEvidenceInput, ...]
    blockers: tuple[GateBlockerInput, ...]
    dependencies: tuple[GateDependencyInput, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        _uuid(self.gate_global_id, "gateGlobalId")
        _uuid(self.project_global_id, "projectGlobalId")
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 140))
        _positive_int(self.gate_version, "gateVersion")
        if self.schema_version != 1 or type(self.schema_version) is not int:
            raise _validation("schemaVersion", _("Select a supported schema version."))
        requirements = tuple(self.requirements)
        evidence = tuple(self.evidence)
        blockers = tuple(self.blockers)
        dependencies = tuple(self.dependencies)
        if (
            any(type(value) is not GateRequirementInput for value in requirements)
            or any(type(value) is not GateEvidenceInput for value in evidence)
            or any(type(value) is not GateBlockerInput for value in blockers)
            or any(type(value) is not GateDependencyInput for value in dependencies)
        ):
            raise _validation("inputSnapshot", _("Enter a valid Gate input snapshot."))
        if (
            len(requirements) > MAX_REQUIREMENTS
            or len(evidence) > MAX_EVIDENCE
            or len(blockers) > MAX_BLOCKERS
            or len(dependencies) > MAX_DEPENDENCIES
        ):
            raise _validation(
                "inputSnapshot", _("Too many Gate input records were supplied.")
            )
        requirement_ids = {value.global_id for value in requirements}
        if (
            len(requirement_ids) != len(requirements)
            or len({value.requirement_key.casefold() for value in requirements})
            != len(requirements)
            or len({value.global_id for value in evidence}) != len(evidence)
            or len({value.global_id for value in blockers}) != len(blockers)
            or len({(value.kind, value.global_id) for value in dependencies})
            != len(dependencies)
        ):
            raise _validation(
                "inputSnapshot", _("Gate input identities must be unique.")
            )
        if any(
            value.requirement_global_id not in requirement_ids for value in evidence
        ):
            raise _validation(
                "evidence.requirementGlobalId",
                _("Evidence must reference a requirement in this snapshot."),
            )
        object.__setattr__(self, "requirements", requirements)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "dependencies", dependencies)

    @property
    def requirement_priorities(self) -> frozenset[str]:
        return frozenset(value.priority for value in self.requirements)

    @property
    def missing_requirements(self) -> tuple[GateRequirementInput, ...]:
        return tuple(
            value for value in self.requirements if not value.evidence_complete
        )

    @property
    def file_evidence_safe(self) -> bool:
        return not any(value.is_file and not value.file_safe for value in self.evidence)

    @property
    def active_blockers(self) -> tuple[GateBlockerInput, ...]:
        return tuple(value for value in self.blockers if value.active)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "gateGlobalId": str(self.gate_global_id),
            "projectGlobalId": str(self.project_global_id),
            "tenantId": self.tenant_id,
            "gateVersion": self.gate_version,
            "requirements": [
                value.canonical_dict()
                for value in sorted(
                    self.requirements, key=lambda item: str(item.global_id)
                )
            ],
            "evidence": [
                value.canonical_dict()
                for value in sorted(self.evidence, key=lambda item: str(item.global_id))
            ],
            "blockers": [
                value.canonical_dict()
                for value in sorted(self.blockers, key=lambda item: str(item.global_id))
            ],
            "dependencies": [
                value.canonical_dict()
                for value in sorted(
                    self.dependencies,
                    key=lambda item: (item.kind.value, str(item.global_id)),
                )
            ],
        }

    @property
    def snapshot_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class ExceptionRule:
    kind: str
    eligible_requirement_keys: tuple[str, ...]
    approval_authority_slot: str
    maximum_validity_days: int
    required_closure_action_kind: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _key(self.kind, "exceptionRules.kind"))
        keys = tuple(
            _key(value, "exceptionRules.eligibleRequirementKeys")
            for value in self.eligible_requirement_keys
        )
        if not keys or len({value.casefold() for value in keys}) != len(keys):
            raise _validation(
                "exceptionRules.eligibleRequirementKeys",
                _("Enter unique eligible requirement keys."),
            )
        object.__setattr__(self, "eligible_requirement_keys", keys)
        object.__setattr__(
            self,
            "approval_authority_slot",
            _key(
                self.approval_authority_slot,
                "exceptionRules.approvalAuthoritySlot",
            ),
        )
        _positive_int(self.maximum_validity_days, "exceptionRules.maximumValidityDays")
        if self.maximum_validity_days > MAX_EXCEPTION_VALIDITY_DAYS:
            raise _validation(
                "exceptionRules.maximumValidityDays",
                _("The maximum exception validity is too long."),
            )
        object.__setattr__(
            self,
            "required_closure_action_kind",
            _key(
                self.required_closure_action_kind,
                "exceptionRules.requiredClosureActionKind",
            ),
        )
        if self.required_closure_action_kind != "action":
            raise _validation(
                "exceptionRules.requiredClosureActionKind",
                _("The closure action kind must be action."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "eligibleRequirementKeys": list(self.eligible_requirement_keys),
            "approvalAuthoritySlot": self.approval_authority_slot,
            "maximumValidityDays": self.maximum_validity_days,
            "requiredClosureActionKind": self.required_closure_action_kind,
        }


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
        _positive_int(self.sequence, "steps.sequence")
        _enum(self.activation, ActivationKind, "steps.activation")
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
        if not isinstance(priorities, frozenset) or any(
            value not in {"P0", "P1", "P2"} for value in priorities
        ):
            raise _validation(
                "requirementPriorities",
                _("Select supported requirement priorities."),
            )
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
    exception_rules: tuple[ExceptionRule, ...]
    dependency_evaluators: tuple[DependencyEvaluator, ...]

    def __post_init__(self) -> None:
        _uuid(self.policy_global_id, "policyGlobalId")
        _uuid(self.global_id, "globalId")
        if self.global_id != uuid5(
            self.policy_global_id, f"version:{self.policy_version}"
        ):
            raise _validation(
                "globalId", _("The policy version identifier is not canonical.")
            )
        object.__setattr__(self, "policy_code", _key(self.policy_code, "policyCode"))
        _enum(self.state, PolicyState, "state")
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
        _uuid(self.gate_template_global_id, "gateTemplateGlobalId")
        _hash(self.gate_template_hash, "gateTemplateHash")
        _positive_int(self.policy_version, "policyVersion")
        _positive_int(self.version, "version")
        _positive_int(self.gate_template_version, "gateTemplateVersion")
        steps = tuple(self.steps)
        if (
            not steps
            or len(steps) > MAX_REVIEW_STEPS
            or any(type(step) is not ReviewStep for step in steps)
        ):
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
        exception_rules = tuple(self.exception_rules)
        if (
            len(exception_rules) > MAX_EXCEPTION_RULES
            or any(type(rule) is not ExceptionRule for rule in exception_rules)
            or len({rule.kind.casefold() for rule in exception_rules})
            != len(exception_rules)
        ):
            raise _validation(
                "exceptionRules", _("Enter unique supported exception rules.")
            )
        evaluators = tuple(self.dependency_evaluators)
        if (
            not evaluators
            or any(type(value) is not DependencyEvaluator for value in evaluators)
            or len(set(evaluators)) != len(evaluators)
        ):
            raise _validation(
                "dependencyEvaluators",
                _("Select unique supported dependency evaluators."),
            )
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "exception_rules", exception_rules)
        object.__setattr__(self, "dependency_evaluators", evaluators)

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
        exception_rules: tuple[ExceptionRule, ...],
        dependency_evaluators: tuple[DependencyEvaluator, ...],
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
            exception_rules,
            dependency_evaluators,
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
            "exceptionRules": [rule.canonical_dict() for rule in self.exception_rules],
            "dependencyEvaluators": [
                evaluator.value for evaluator in self.dependency_evaluators
            ],
        }

    @property
    def snapshot_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())

    def publish(self, expected_version: int) -> ReviewPolicyVersion:
        if self.state is PolicyState.PUBLISHED:
            raise ReviewDenied(
                "PUBLISHED_REVIEW_POLICY_IMMUTABLE",
                _("A published review policy version cannot be changed."),
            )
        _positive_int(expected_version, "expectedVersion")
        if expected_version != self.version:
            raise VersionConflict()
        return replace(
            self,
            state=PolicyState.PUBLISHED,
            version=next_version(self.version, self.version),
        )

    def next_draft(
        self,
        *,
        expected_version: int,
        gate_template_global_id: UUID,
        gate_template_version: int,
        gate_template_hash: str,
        steps: tuple[ReviewStep, ...],
        decision_authority_slot: str,
        reopen_authority_slot: str,
        exception_rules: tuple[ExceptionRule, ...],
        dependency_evaluators: tuple[DependencyEvaluator, ...],
    ) -> ReviewPolicyVersion:
        if self.state is not PolicyState.PUBLISHED:
            raise ReviewDenied(
                "PUBLISHED_REVIEW_POLICY_REQUIRED",
                _("Only a published policy can create its next draft version."),
            )
        _positive_int(expected_version, "expectedVersion")
        if expected_version != self.version:
            raise VersionConflict()
        policy_version = self.policy_version + 1
        return ReviewPolicyVersion(
            global_id=uuid5(self.policy_global_id, f"version:{policy_version}"),
            policy_global_id=self.policy_global_id,
            policy_code=self.policy_code,
            policy_version=policy_version,
            version=1,
            state=PolicyState.DRAFT,
            gate_template_global_id=gate_template_global_id,
            gate_template_version=gate_template_version,
            gate_template_hash=gate_template_hash,
            steps=steps,
            decision_authority_slot=decision_authority_slot,
            reopen_authority_slot=reopen_authority_slot,
            exception_rules=exception_rules,
            dependency_evaluators=dependency_evaluators,
        )


@dataclass(frozen=True, slots=True)
class AuthorityBinding:
    slot: str
    member_global_id: UUID
    user_id: str
    display_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot", _key(self.slot, "bindings.slot"))
        _uuid(self.member_global_id, "bindings.memberGlobalId")
        object.__setattr__(self, "user_id", _text(self.user_id, "bindings.userId", 140))
        object.__setattr__(
            self, "display_name", _text(self.display_name, "bindings.displayName", 140)
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "slot": self.slot,
            "memberGlobalId": str(self.member_global_id),
            "userId": self.user_id,
            "displayName": self.display_name,
        }


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_key", _key(self.step_key, "stepKey"))
        object.__setattr__(
            self, "actor_user_id", _text(self.actor_user_id, "actorUserId", 140)
        )
        _enum(self.outcome, ReviewOutcome, "outcome")
        object.__setattr__(self, "opinion", _text(self.opinion, "opinion"))
        object.__setattr__(self, "occurred_at", _aware(self.occurred_at, "occurredAt"))
        _hash(self.reviewed_input_hash, "reviewedInputHash")
        _positive_int(self.policy_version, "policyVersion")
        _hash(self.policy_hash, "policyHash")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "stepKey": self.step_key,
            "actorUserId": self.actor_user_id,
            "outcome": self.outcome.value,
            "opinion": self.opinion,
            "occurredAt": self.occurred_at.isoformat(),
            "reviewedInputHash": self.reviewed_input_hash,
            "policyVersion": self.policy_version,
            "policyHash": self.policy_hash,
        }

    @property
    def snapshot_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class ClosureActionReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "closureActionRef.globalId")
        _positive_int(self.version, "closureActionRef.version")
        _hash(self.snapshot_hash, "closureActionRef.snapshotHash")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    gate_global_id: UUID
    cycle_global_id: UUID
    cycle_number: int
    outcome: DecisionOutcome
    actor_user_id: str
    occurred_at: datetime
    policy_global_id: UUID
    policy_version: int
    policy_hash: str
    input_snapshot: GateInputSnapshot
    review_hashes: tuple[str, ...]
    exception_hashes: tuple[str, ...]
    cycle_version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "globalId")
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 140))
        _uuid(self.project_global_id, "projectGlobalId")
        _uuid(self.gate_global_id, "gateGlobalId")
        _uuid(self.cycle_global_id, "cycleGlobalId")
        if self.global_id != uuid5(self.cycle_global_id, "decision-snapshot"):
            raise _validation(
                "globalId", _("The Gate decision identifier is not canonical.")
            )
        _positive_int(self.cycle_number, "cycleNumber")
        _enum(self.outcome, DecisionOutcome, "outcome")
        object.__setattr__(
            self, "actor_user_id", _text(self.actor_user_id, "actorUserId", 140)
        )
        object.__setattr__(self, "occurred_at", _aware(self.occurred_at, "occurredAt"))
        _uuid(self.policy_global_id, "policyGlobalId")
        _positive_int(self.policy_version, "policyVersion")
        _hash(self.policy_hash, "policyHash")
        if type(self.input_snapshot) is not GateInputSnapshot:
            raise _validation("inputSnapshot", _("Enter a valid Gate input snapshot."))
        if (
            self.input_snapshot.gate_global_id != self.gate_global_id
            or self.input_snapshot.project_global_id != self.project_global_id
            or self.input_snapshot.tenant_id != self.tenant_id
        ):
            raise _validation(
                "inputSnapshot", _("The decision input scope does not match.")
            )
        hashes = tuple(self.review_hashes)
        exception_hashes = tuple(self.exception_hashes)
        for value in hashes:
            _hash(value, "reviewHashes")
        for value in exception_hashes:
            _hash(value, "exceptionHashes")
        object.__setattr__(self, "review_hashes", hashes)
        object.__setattr__(self, "exception_hashes", exception_hashes)
        _positive_int(self.cycle_version, "cycleVersion")
        _hash(self.snapshot_hash, "snapshotHash")
        if self.snapshot_hash != _canonical_hash(self.canonical_payload()):
            raise _validation(
                "snapshotHash", _("The Gate decision snapshot hash is invalid.")
            )

    @property
    def input_hash(self) -> str:
        return self.input_snapshot.snapshot_hash

    def canonical_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "gateGlobalId": str(self.gate_global_id),
            "cycleGlobalId": str(self.cycle_global_id),
            "cycleNumber": self.cycle_number,
            "outcome": self.outcome.value,
            "actorUserId": self.actor_user_id,
            "occurredAt": self.occurred_at.isoformat(),
            "policyGlobalId": str(self.policy_global_id),
            "policyVersion": self.policy_version,
            "policyHash": self.policy_hash,
            "inputSnapshot": self.input_snapshot.canonical_dict(),
            "inputHash": self.input_hash,
            "reviewHashes": list(self.review_hashes),
            "exceptionHashes": list(self.exception_hashes),
            "cycleVersion": self.cycle_version,
        }

    @classmethod
    def build(
        cls,
        *,
        tenant_id: str,
        project_global_id: UUID,
        gate_global_id: UUID,
        cycle_global_id: UUID,
        cycle_number: int,
        outcome: DecisionOutcome,
        actor_user_id: str,
        occurred_at: datetime,
        policy_global_id: UUID,
        policy_version: int,
        policy_hash: str,
        input_snapshot: GateInputSnapshot,
        review_hashes: tuple[str, ...],
        exception_hashes: tuple[str, ...],
        cycle_version: int,
    ) -> DecisionSnapshot:
        selected_outcome = _enum(outcome, DecisionOutcome, "outcome")
        global_id = uuid5(cycle_global_id, "decision-snapshot")
        occurred = _aware(occurred_at, "occurredAt")
        payload = {
            "globalId": str(global_id),
            "tenantId": tenant_id,
            "projectGlobalId": str(project_global_id),
            "gateGlobalId": str(gate_global_id),
            "cycleGlobalId": str(cycle_global_id),
            "cycleNumber": cycle_number,
            "outcome": selected_outcome.value,
            "actorUserId": actor_user_id,
            "occurredAt": occurred.isoformat(),
            "policyGlobalId": str(policy_global_id),
            "policyVersion": policy_version,
            "policyHash": policy_hash,
            "inputSnapshot": input_snapshot.canonical_dict(),
            "inputHash": input_snapshot.snapshot_hash,
            "reviewHashes": list(review_hashes),
            "exceptionHashes": list(exception_hashes),
            "cycleVersion": cycle_version,
        }
        return cls(
            global_id=global_id,
            tenant_id=tenant_id,
            project_global_id=project_global_id,
            gate_global_id=gate_global_id,
            cycle_global_id=cycle_global_id,
            cycle_number=cycle_number,
            outcome=selected_outcome,
            actor_user_id=actor_user_id,
            occurred_at=occurred,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            policy_hash=policy_hash,
            input_snapshot=input_snapshot,
            review_hashes=review_hashes,
            exception_hashes=exception_hashes,
            cycle_version=cycle_version,
            snapshot_hash=_canonical_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class ReviewException:
    global_id: UUID
    cycle_global_id: UUID
    gate_global_id: UUID
    project_global_id: UUID
    tenant_id: str
    policy_global_id: UUID
    kind: str
    requirement_global_id: UUID
    requirement_key: str
    requirement_priority: str
    approval_authority_slot: str
    approval_member_global_id: UUID
    approval_user_id: str
    requester_member_global_id: UUID
    requester_user_id: str
    reason: str
    risk: str
    closure_action_ref: ClosureActionReference
    closure_action_kind: str
    requested_at: datetime
    expires_at: datetime
    policy_version: int
    policy_hash: str
    input_hash: str
    version: int = 1
    state: ExceptionState = ExceptionState.PENDING
    outcome: ExceptionOutcome | None = None
    decision_actor_user_id: str | None = None
    decision_opinion: str | None = None
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.global_id, "exceptionGlobalId")
        _uuid(self.cycle_global_id, "cycleGlobalId")
        _uuid(self.gate_global_id, "gateGlobalId")
        _uuid(self.project_global_id, "projectGlobalId")
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 140))
        _uuid(self.policy_global_id, "policyGlobalId")
        object.__setattr__(self, "kind", _key(self.kind, "kind"))
        _uuid(self.requirement_global_id, "requirementGlobalId")
        object.__setattr__(
            self, "requirement_key", _key(self.requirement_key, "requirementKey")
        )
        object.__setattr__(
            self,
            "requirement_priority",
            _priority(self.requirement_priority, "requirementPriority"),
        )
        object.__setattr__(
            self,
            "approval_authority_slot",
            _key(self.approval_authority_slot, "approvalAuthoritySlot"),
        )
        _uuid(self.approval_member_global_id, "approvalMemberGlobalId")
        object.__setattr__(
            self,
            "approval_user_id",
            _text(self.approval_user_id, "approvalUserId", 140),
        )
        _uuid(self.requester_member_global_id, "requesterMemberGlobalId")
        object.__setattr__(
            self,
            "requester_user_id",
            _text(self.requester_user_id, "requesterUserId", 140),
        )
        if (
            self.requester_user_id == self.approval_user_id
            or self.requester_member_global_id == self.approval_member_global_id
        ):
            raise _validation(
                "requesterUserId",
                _("The requester and exception approver must be different users."),
            )
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        object.__setattr__(self, "risk", _text(self.risk, "risk"))
        if type(self.closure_action_ref) is not ClosureActionReference:
            raise _validation(
                "closureActionRef",
                _("Enter an exact closure action reference."),
            )
        object.__setattr__(
            self,
            "closure_action_kind",
            _key(self.closure_action_kind, "closureActionKind"),
        )
        if self.closure_action_kind != "action":
            raise _validation(
                "closureActionKind",
                _("The exception must reference a closure action."),
            )
        object.__setattr__(
            self, "requested_at", _aware(self.requested_at, "requestedAt")
        )
        object.__setattr__(self, "expires_at", _aware(self.expires_at, "expiresAt"))
        if self.expires_at <= self.requested_at:
            raise _validation(
                "expiresAt", _("The expiry must be after the request time.")
            )
        _positive_int(self.policy_version, "policyVersion")
        _hash(self.policy_hash, "policyHash")
        _hash(self.input_hash, "inputHash")
        _positive_int(self.version, "version")
        _enum(self.state, ExceptionState, "state")
        if self.state is ExceptionState.PENDING:
            if any(
                value is not None
                for value in (
                    self.outcome,
                    self.decision_actor_user_id,
                    self.decision_opinion,
                    self.decided_at,
                )
            ):
                raise _validation(
                    "state", _("A pending exception cannot have a decision.")
                )
        else:
            if (
                type(self.outcome) is not ExceptionOutcome
                or self.decision_actor_user_id is None
                or self.decision_opinion is None
                or self.decided_at is None
                or (
                    self.state is ExceptionState.APPROVED
                    and self.outcome is not ExceptionOutcome.APPROVED
                )
                or (
                    self.state is ExceptionState.REJECTED
                    and self.outcome is not ExceptionOutcome.REJECTED
                )
            ):
                raise _validation(
                    "state", _("A closed exception requires an exact decision.")
                )
            object.__setattr__(
                self,
                "decision_actor_user_id",
                _text(self.decision_actor_user_id, "decisionActorUserId", 140),
            )
            object.__setattr__(
                self,
                "decision_opinion",
                _text(self.decision_opinion, "decisionOpinion"),
            )
            object.__setattr__(self, "decided_at", _aware(self.decided_at, "decidedAt"))
            if self.decision_actor_user_id != self.approval_user_id:
                raise _validation(
                    "decisionActorUserId",
                    _("The exception decision actor must match its approver."),
                )
            if self.decided_at < self.requested_at:
                raise _validation(
                    "decidedAt", _("The decision cannot predate the request.")
                )
            if (
                self.state is ExceptionState.APPROVED
                and self.decided_at >= self.expires_at
            ):
                raise _validation(
                    "decidedAt",
                    _("An approved exception must be decided before expiry."),
                )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "cycleGlobalId": str(self.cycle_global_id),
            "gateGlobalId": str(self.gate_global_id),
            "projectGlobalId": str(self.project_global_id),
            "tenantId": self.tenant_id,
            "policyGlobalId": str(self.policy_global_id),
            "kind": self.kind,
            "requirementGlobalId": str(self.requirement_global_id),
            "requirementKey": self.requirement_key,
            "requirementPriority": self.requirement_priority,
            "approvalAuthoritySlot": self.approval_authority_slot,
            "approvalMemberGlobalId": str(self.approval_member_global_id),
            "approvalUserId": self.approval_user_id,
            "requesterMemberGlobalId": str(self.requester_member_global_id),
            "requesterUserId": self.requester_user_id,
            "reason": self.reason,
            "risk": self.risk,
            "closureActionRef": self.closure_action_ref.canonical_dict(),
            "closureActionKind": self.closure_action_kind,
            "requestedAt": self.requested_at.isoformat(),
            "expiresAt": self.expires_at.isoformat(),
            "policyVersion": self.policy_version,
            "policyHash": self.policy_hash,
            "inputHash": self.input_hash,
            "version": self.version,
            "state": self.state.value,
            "outcome": self.outcome.value if self.outcome is not None else None,
            "decisionActorUserId": self.decision_actor_user_id,
            "decisionOpinion": self.decision_opinion,
            "decidedAt": (
                self.decided_at.isoformat() if self.decided_at is not None else None
            ),
        }

    @property
    def snapshot_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())

    @property
    def closure_action_global_id(self) -> UUID:
        return self.closure_action_ref.global_id

    def decide(
        self,
        *,
        actor_user_id: str,
        outcome: ExceptionOutcome,
        opinion: str,
        occurred_at: datetime,
        expected_version: int,
        expected_input_hash: str,
    ) -> ReviewException:
        _positive_int(expected_version, "expectedVersion")
        _hash(expected_input_hash, "expectedInputHash")
        if expected_version != self.version or expected_input_hash != self.input_hash:
            raise VersionConflict()
        if self.state is not ExceptionState.PENDING:
            raise ReviewDenied(
                "EXCEPTION_ALREADY_DECIDED",
                _("This exception request already has a decision."),
            )
        actor = _text(actor_user_id, "actorUserId", 140)
        if actor != self.approval_user_id or actor == self.requester_user_id:
            raise ReviewDenied(
                "EXCEPTION_APPROVAL_AUTHORITY_REQUIRED",
                _("The assigned exception approval authority is required."),
            )
        selected_outcome = _enum(outcome, ExceptionOutcome, "outcome")
        decided_at = _aware(occurred_at, "occurredAt")
        if decided_at < self.requested_at:
            raise _validation(
                "occurredAt", _("The decision cannot predate the request.")
            )
        if (
            selected_outcome is ExceptionOutcome.APPROVED
            and decided_at >= self.expires_at
        ):
            raise ReviewDenied(
                "EXCEPTION_EXPIRED", _("An expired exception cannot be approved.")
            )
        return replace(
            self,
            version=next_version(self.version, self.version),
            state=(
                ExceptionState.APPROVED
                if selected_outcome is ExceptionOutcome.APPROVED
                else ExceptionState.REJECTED
            ),
            outcome=selected_outcome,
            decision_actor_user_id=actor,
            decision_opinion=_text(opinion, "opinion"),
            decided_at=decided_at,
        )

    def supports(
        self,
        requirement: GateRequirementInput,
        *,
        policy: ReviewPolicyVersion,
        input_hash: str,
        at: datetime,
        current_closure_action_ref: ClosureActionReference | None,
    ) -> bool:
        now = _aware(at, "occurredAt")
        return (
            self.state is ExceptionState.APPROVED
            and self.outcome is ExceptionOutcome.APPROVED
            and self.requirement_global_id == requirement.global_id
            and self.requirement_key == requirement.requirement_key
            and self.requirement_priority == requirement.priority
            and self.policy_version == policy.policy_version
            and self.policy_hash == policy.snapshot_hash
            and self.input_hash == input_hash
            and current_closure_action_ref == self.closure_action_ref
            and now < self.expires_at
        )


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    global_id: UUID
    kind: ReviewEventKind
    gate_global_id: UUID
    project_global_id: UUID
    old_cycle_global_id: UUID
    new_cycle_global_id: UUID
    old_input_hash: str
    new_input_hash: str
    prior_decision_snapshot_global_id: UUID | None
    prior_decision_hash: str | None
    actor_user_id: str
    initiated_by_user_id: str | None
    reason: str
    occurred_at: datetime
    event_hash: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "eventGlobalId")
        _enum(self.kind, ReviewEventKind, "eventKind")
        _uuid(self.gate_global_id, "gateGlobalId")
        _uuid(self.project_global_id, "projectGlobalId")
        _uuid(self.old_cycle_global_id, "oldCycleGlobalId")
        _uuid(self.new_cycle_global_id, "newCycleGlobalId")
        if self.old_cycle_global_id == self.new_cycle_global_id:
            raise _validation(
                "newCycleGlobalId", _("A transition must create a new cycle.")
            )
        expected_global_id = uuid5(
            self.old_cycle_global_id,
            f"{self.kind.value}:{self.new_cycle_global_id}:{self.new_input_hash}",
        )
        if self.global_id != expected_global_id:
            raise _validation(
                "eventGlobalId", _("The review event identifier is not canonical.")
            )
        _hash(self.old_input_hash, "oldInputHash")
        _hash(self.new_input_hash, "newInputHash")
        has_prior_id = self.prior_decision_snapshot_global_id is not None
        has_prior_hash = self.prior_decision_hash is not None
        if has_prior_id != has_prior_hash or (
            self.kind in {ReviewEventKind.REOPENED, ReviewEventKind.INVALIDATED}
            and not has_prior_id
        ):
            raise _validation(
                "priorDecisionHash",
                _("The review event prior decision reference is incomplete."),
            )
        if self.prior_decision_snapshot_global_id is not None:
            _uuid(
                self.prior_decision_snapshot_global_id,
                "priorDecisionSnapshotGlobalId",
            )
        if self.prior_decision_hash is not None:
            _hash(self.prior_decision_hash, "priorDecisionHash")
        object.__setattr__(
            self, "actor_user_id", _text(self.actor_user_id, "actorUserId", 140)
        )
        if self.initiated_by_user_id is not None:
            object.__setattr__(
                self,
                "initiated_by_user_id",
                _text(self.initiated_by_user_id, "initiatedByUserId", 140),
            )
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        object.__setattr__(self, "occurred_at", _aware(self.occurred_at, "occurredAt"))
        _hash(self.event_hash, "eventHash")
        if self.event_hash != _canonical_hash(self.canonical_payload()):
            raise _validation("eventHash", _("The review event hash is invalid."))

    def canonical_payload(self) -> dict[str, object]:
        return {
            "eventGlobalId": str(self.global_id),
            "kind": self.kind.value,
            "gateGlobalId": str(self.gate_global_id),
            "projectGlobalId": str(self.project_global_id),
            "oldCycleGlobalId": str(self.old_cycle_global_id),
            "newCycleGlobalId": str(self.new_cycle_global_id),
            "oldInputHash": self.old_input_hash,
            "newInputHash": self.new_input_hash,
            "priorDecisionSnapshotGlobalId": (
                str(self.prior_decision_snapshot_global_id)
                if self.prior_decision_snapshot_global_id is not None
                else None
            ),
            "priorDecisionHash": self.prior_decision_hash,
            "actorUserId": self.actor_user_id,
            "initiatedByUserId": self.initiated_by_user_id,
            "reason": self.reason,
            "occurredAt": self.occurred_at.isoformat(),
        }

    @classmethod
    def build(
        cls,
        *,
        kind: ReviewEventKind,
        gate_global_id: UUID,
        project_global_id: UUID,
        old_cycle_global_id: UUID,
        new_cycle_global_id: UUID,
        old_input_hash: str,
        new_input_hash: str,
        prior_decision_snapshot_global_id: UUID | None,
        prior_decision_hash: str | None,
        actor_user_id: str,
        initiated_by_user_id: str | None,
        reason: str,
        occurred_at: datetime,
    ) -> ReviewEvent:
        selected_kind = _enum(kind, ReviewEventKind, "eventKind")
        event_global_id = uuid5(
            old_cycle_global_id,
            f"{selected_kind.value}:{new_cycle_global_id}:{new_input_hash}",
        )
        occurred = _aware(occurred_at, "occurredAt")
        payload = {
            "eventGlobalId": str(event_global_id),
            "kind": selected_kind.value,
            "gateGlobalId": str(gate_global_id),
            "projectGlobalId": str(project_global_id),
            "oldCycleGlobalId": str(old_cycle_global_id),
            "newCycleGlobalId": str(new_cycle_global_id),
            "oldInputHash": old_input_hash,
            "newInputHash": new_input_hash,
            "priorDecisionSnapshotGlobalId": (
                str(prior_decision_snapshot_global_id)
                if prior_decision_snapshot_global_id is not None
                else None
            ),
            "priorDecisionHash": prior_decision_hash,
            "actorUserId": actor_user_id,
            "initiatedByUserId": initiated_by_user_id,
            "reason": reason,
            "occurredAt": occurred.isoformat(),
        }
        return cls(
            global_id=event_global_id,
            kind=selected_kind,
            gate_global_id=gate_global_id,
            project_global_id=project_global_id,
            old_cycle_global_id=old_cycle_global_id,
            new_cycle_global_id=new_cycle_global_id,
            old_input_hash=old_input_hash,
            new_input_hash=new_input_hash,
            prior_decision_snapshot_global_id=prior_decision_snapshot_global_id,
            prior_decision_hash=prior_decision_hash,
            actor_user_id=actor_user_id,
            initiated_by_user_id=initiated_by_user_id,
            reason=reason,
            occurred_at=occurred,
            event_hash=_canonical_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class ReviewCycle:
    global_id: UUID
    gate_global_id: UUID
    project_global_id: UUID
    tenant_id: str
    cycle_number: int
    trigger: CycleTrigger
    policy: ReviewPolicyVersion
    bindings: tuple[AuthorityBinding, ...]
    selected_steps: tuple[ReviewStep, ...]
    input_snapshot: GateInputSnapshot
    version: int = 1
    state: CycleState = CycleState.ACTIVE
    reviews: tuple[ReviewRecord, ...] = ()
    exceptions: tuple[ReviewException, ...] = ()
    decision: DecisionSnapshot | None = None
    prior_cycle_global_id: UUID | None = None
    prior_decision_snapshot_global_id: UUID | None = None
    prior_decision_hash: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.global_id, "globalId")
        _uuid(self.gate_global_id, "gateGlobalId")
        _uuid(self.project_global_id, "projectGlobalId")
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 140))
        _positive_int(self.cycle_number, "cycleNumber")
        if self.global_id != uuid5(
            self.gate_global_id, f"review-cycle:{self.cycle_number}"
        ):
            raise _validation(
                "globalId", _("The review cycle identifier is not canonical.")
            )
        _enum(self.trigger, CycleTrigger, "trigger")
        if type(self.policy) is not ReviewPolicyVersion:
            raise _validation("policy", _("Enter a valid review policy."))
        if self.policy.state is not PolicyState.PUBLISHED:
            raise ReviewDenied(
                "REVIEW_POLICY_UNAVAILABLE",
                _("A published review policy is required."),
            )
        bindings = tuple(self.bindings)
        selected_steps = tuple(self.selected_steps)
        reviews = tuple(self.reviews)
        exceptions = tuple(self.exceptions)
        if (
            any(type(value) is not AuthorityBinding for value in bindings)
            or not selected_steps
            or any(type(value) is not ReviewStep for value in selected_steps)
            or any(type(value) is not ReviewRecord for value in reviews)
            or any(type(value) is not ReviewException for value in exceptions)
        ):
            raise _validation("reviewCycle", _("Enter a valid review cycle."))
        if type(self.input_snapshot) is not GateInputSnapshot:
            raise _validation("inputSnapshot", _("Enter a valid Gate input snapshot."))
        if (
            self.input_snapshot.gate_global_id != self.gate_global_id
            or self.input_snapshot.project_global_id != self.project_global_id
            or self.input_snapshot.tenant_id != self.tenant_id
        ):
            raise _validation(
                "inputSnapshot", _("The Gate input snapshot scope does not match.")
            )
        expected_steps = tuple(
            step
            for step in self.policy.steps
            if step.selected(self.input_snapshot.requirement_priorities)
        )
        if selected_steps != expected_steps:
            raise _validation(
                "selectedSteps",
                _("Selected review steps must match the frozen Gate input."),
            )
        required_slots = {
            step.authority_slot.casefold() for step in self.policy.steps
        } | {
            self.policy.decision_authority_slot.casefold(),
            self.policy.reopen_authority_slot.casefold(),
            *(
                rule.approval_authority_slot.casefold()
                for rule in self.policy.exception_rules
            ),
        }
        bound_slots = {binding.slot.casefold() for binding in bindings}
        if len(bound_slots) != len(bindings) or bound_slots != required_slots:
            raise _validation(
                "bindings",
                _("Bind every selected policy authority exactly once."),
            )
        binding_by_slot = {value.slot.casefold(): value for value in bindings}
        if len({value.step_key for value in reviews}) != len(reviews):
            raise _validation("reviews", _("Review records must be unique."))
        selected_by_key = {value.key: value for value in selected_steps}
        prior_reviews: list[ReviewRecord] = []
        for value in reviews:
            step = selected_by_key.get(value.step_key)
            if (
                step is None
                or value.actor_user_id
                != binding_by_slot[step.authority_slot.casefold()].user_id
                or value.reviewed_input_hash != self.input_snapshot.snapshot_hash
                or value.policy_version != self.policy.policy_version
                or value.policy_hash != self.policy.snapshot_hash
            ):
                raise _validation(
                    "reviews", _("Review records do not match this review cycle.")
                )
            prior_approved = {
                item.step_key
                for item in prior_reviews
                if item.outcome is ReviewOutcome.APPROVED
            }
            if any(
                candidate.sequence < step.sequence
                and candidate.key not in prior_approved
                for candidate in selected_steps
            ):
                raise _validation(
                    "reviews", _("Review records do not follow the selected sequence.")
                )
            prior_reviews.append(value)
        if len({value.global_id for value in exceptions}) != len(exceptions):
            raise _validation(
                "exceptions", _("Exception records do not match this review cycle.")
            )
        requirement_by_id = {
            value.global_id: value for value in self.input_snapshot.requirements
        }
        rule_by_kind = {value.kind: value for value in self.policy.exception_rules}
        for value in exceptions:
            requirement = requirement_by_id.get(value.requirement_global_id)
            rule = rule_by_kind.get(value.kind)
            if (
                value.cycle_global_id != self.global_id
                or value.gate_global_id != self.gate_global_id
                or value.project_global_id != self.project_global_id
                or value.tenant_id != self.tenant_id
                or value.policy_global_id != self.policy.policy_global_id
                or value.policy_version != self.policy.policy_version
                or value.policy_hash != self.policy.snapshot_hash
                or value.input_hash != self.input_snapshot.snapshot_hash
                or requirement is None
                or rule is None
                or value.requirement_key != requirement.requirement_key
                or value.requirement_priority != requirement.priority
                or requirement.evidence_complete
                or requirement.priority == "P0"
                or requirement.requirement_key not in rule.eligible_requirement_keys
                or not self.input_snapshot.file_evidence_safe
                or value.approval_authority_slot != rule.approval_authority_slot
                or value.closure_action_kind != rule.required_closure_action_kind
                or value.expires_at
                > value.requested_at + timedelta(days=rule.maximum_validity_days)
            ):
                raise _validation(
                    "exceptions", _("Exception records do not match this review cycle.")
                )
            approval_binding = binding_by_slot[rule.approval_authority_slot.casefold()]
            if (
                value.approval_member_global_id != approval_binding.member_global_id
                or value.approval_user_id != approval_binding.user_id
            ):
                raise _validation(
                    "exceptions",
                    _("Exception approval binding does not match this review cycle."),
                )
        _positive_int(self.version, "version")
        _enum(self.state, CycleState, "state")
        if self.cycle_number == 1:
            if (
                self.trigger is not CycleTrigger.MANUAL_START
                or self.prior_cycle_global_id is not None
                or self.prior_decision_snapshot_global_id is not None
                or self.prior_decision_hash is not None
            ):
                raise _validation(
                    "trigger", _("The first review cycle must be a manual start.")
                )
        else:
            if (
                self.trigger is CycleTrigger.MANUAL_START
                or self.prior_cycle_global_id is None
            ):
                raise _validation(
                    "priorCycleGlobalId",
                    _("A successor cycle requires its prior cycle."),
                )
            _uuid(self.prior_cycle_global_id, "priorCycleGlobalId")
            if self.prior_cycle_global_id != uuid5(
                self.gate_global_id,
                f"review-cycle:{self.cycle_number - 1}",
            ):
                raise _validation(
                    "priorCycleGlobalId",
                    _("The prior review cycle identifier is not canonical."),
                )
            has_prior_id = self.prior_decision_snapshot_global_id is not None
            has_prior_hash = self.prior_decision_hash is not None
            if has_prior_id != has_prior_hash or (
                self.trigger is CycleTrigger.MANUAL_REOPEN and not has_prior_id
            ):
                raise _validation(
                    "priorDecisionHash",
                    _("The successor prior decision reference is incomplete."),
                )
            if self.prior_decision_snapshot_global_id is not None:
                _uuid(
                    self.prior_decision_snapshot_global_id,
                    "priorDecisionSnapshotGlobalId",
                )
            if self.prior_decision_hash is not None:
                _hash(self.prior_decision_hash, "priorDecisionHash")
        if self.decision is not None and type(self.decision) is not DecisionSnapshot:
            raise _validation("decision", _("Enter a valid Gate decision snapshot."))
        if self.state in {CycleState.ACTIVE, CycleState.SUPERSEDED}:
            if self.decision is not None:
                raise _validation(
                    "state",
                    _("An active or superseded cycle cannot have a decision."),
                )
        else:
            if self.decision is None:
                raise _validation(
                    "state", _("A decided or invalidated cycle requires a decision.")
                )
            if (
                self.decision.cycle_global_id != self.global_id
                or self.decision.global_id != uuid5(self.global_id, "decision-snapshot")
                or self.decision.cycle_number != self.cycle_number
                or self.decision.gate_global_id != self.gate_global_id
                or self.decision.project_global_id != self.project_global_id
                or self.decision.tenant_id != self.tenant_id
                or self.decision.policy_global_id != self.policy.policy_global_id
                or self.decision.policy_version != self.policy.policy_version
                or self.decision.policy_hash != self.policy.snapshot_hash
                or self.decision.input_snapshot.canonical_dict()
                != self.input_snapshot.canonical_dict()
                or self.decision.review_hashes
                != tuple(value.snapshot_hash for value in reviews)
                or self.decision.exception_hashes
                != tuple(
                    value.snapshot_hash
                    for value in sorted(
                        exceptions, key=lambda item: str(item.global_id)
                    )
                )
                or self.decision.actor_user_id
                != binding_by_slot[
                    self.policy.decision_authority_slot.casefold()
                ].user_id
            ):
                raise _validation(
                    "decision", _("The decision does not match this review cycle.")
                )
            expected_cycle_version = (
                self.version - 1
                if self.state is CycleState.DECIDED
                else self.version - 2
            )
            if self.decision.cycle_version != expected_cycle_version:
                raise _validation(
                    "decision",
                    _("The decision version does not match this review cycle."),
                )
            if any(value.occurred_at > self.decision.occurred_at for value in reviews):
                raise _validation(
                    "decision", _("A decision cannot predate its review records.")
                )
            if self.decision.outcome in {
                DecisionOutcome.PASS,
                DecisionOutcome.CONDITIONAL_PASS,
            }:
                approved = {
                    value.step_key
                    for value in reviews
                    if value.outcome is ReviewOutcome.APPROVED
                }
                missing = self.input_snapshot.missing_requirements
                if (
                    any(value.key not in approved for value in selected_steps)
                    or not self.input_snapshot.file_evidence_safe
                    or bool(self.input_snapshot.active_blockers)
                    or any(value.priority == "P0" for value in missing)
                    or (self.decision.outcome is DecisionOutcome.PASS and bool(missing))
                    or (
                        self.decision.outcome is DecisionOutcome.CONDITIONAL_PASS
                        and not missing
                    )
                ):
                    raise _validation(
                        "decision",
                        _("The decision outcome does not match the frozen Gate input."),
                    )
                if self.decision.outcome is DecisionOutcome.CONDITIONAL_PASS and any(
                    not any(
                        exception.supports(
                            requirement,
                            policy=self.policy,
                            input_hash=self.input_snapshot.snapshot_hash,
                            at=self.decision.occurred_at,
                            current_closure_action_ref=exception.closure_action_ref,
                        )
                        for exception in exceptions
                    )
                    for requirement in missing
                ):
                    raise _validation(
                        "decision",
                        _(
                            "The conditional decision lacks an exact approved exception."
                        ),
                    )
        object.__setattr__(self, "bindings", bindings)
        object.__setattr__(self, "selected_steps", selected_steps)
        object.__setattr__(self, "reviews", reviews)
        object.__setattr__(self, "exceptions", exceptions)

    @property
    def input_hash(self) -> str:
        return self.input_snapshot.snapshot_hash

    @classmethod
    def start(
        cls,
        *,
        gate_global_id: UUID,
        project_global_id: UUID,
        tenant_id: str,
        cycle_number: int,
        trigger: CycleTrigger,
        policy: ReviewPolicyVersion,
        bindings: tuple[AuthorityBinding, ...],
        input_snapshot: GateInputSnapshot,
        prior_cycle_global_id: UUID | None = None,
        prior_decision_snapshot_global_id: UUID | None = None,
        prior_decision_hash: str | None = None,
    ) -> ReviewCycle:
        if type(policy) is not ReviewPolicyVersion:
            raise _validation("policy", _("Enter a valid review policy."))
        if policy.state is not PolicyState.PUBLISHED:
            raise ReviewDenied(
                "REVIEW_POLICY_UNAVAILABLE",
                _("A published review policy is required."),
            )
        selected = tuple(
            step
            for step in policy.steps
            if step.selected(input_snapshot.requirement_priorities)
        )
        return cls(
            uuid5(gate_global_id, f"review-cycle:{cycle_number}"),
            gate_global_id,
            project_global_id,
            _text(tenant_id, "tenantId", 140),
            cycle_number,
            trigger,
            policy,
            tuple(bindings),
            selected,
            input_snapshot,
            prior_cycle_global_id=prior_cycle_global_id,
            prior_decision_snapshot_global_id=prior_decision_snapshot_global_id,
            prior_decision_hash=prior_decision_hash,
        )

    def _binding(self, slot: str) -> AuthorityBinding:
        return next(
            value for value in self.bindings if value.slot.casefold() == slot.casefold()
        )

    def _check_precondition(
        self, *, expected_version: int, expected_input_hash: str
    ) -> None:
        _positive_int(expected_version, "expectedVersion")
        _hash(expected_input_hash, "expectedInputHash")
        if expected_version != self.version or expected_input_hash != self.input_hash:
            raise VersionConflict()

    def _check_current_input(self, current_input: GateInputSnapshot) -> None:
        if type(current_input) is not GateInputSnapshot:
            raise _validation("currentInput", _("Enter a valid Gate input snapshot."))
        if (
            current_input.gate_global_id != self.gate_global_id
            or current_input.project_global_id != self.project_global_id
            or current_input.tenant_id != self.tenant_id
        ):
            raise _validation(
                "currentInput", _("The current Gate input scope does not match.")
            )
        if current_input.snapshot_hash != self.input_hash:
            raise ReviewDenied(
                "GATE_INPUT_CHANGED",
                _("The Gate input changed and requires a new review cycle."),
            )

    def ensure_current_input(self, current_input: GateInputSnapshot) -> None:
        self._check_current_input(current_input)

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
                "REVIEW_CYCLE_CLOSED", _("This review cycle is not active.")
            )
        self._check_precondition(
            expected_version=expected_version,
            expected_input_hash=expected_input_hash,
        )
        selected_outcome = _enum(outcome, ReviewOutcome, "outcome")
        actor = _text(actor_user_id, "actorUserId", 140)
        try:
            step = next(value for value in self.selected_steps if value.key == step_key)
        except StopIteration as error:
            raise ReviewDenied(
                "REVIEW_STEP_NOT_SELECTED", _("This review step is not selected.")
            ) from error
        if any(value.step_key == step.key for value in self.reviews):
            raise ReviewDenied(
                "REVIEW_ALREADY_RECORDED",
                _("This review has already been recorded."),
            )
        if self._binding(step.authority_slot).user_id != actor:
            raise ReviewDenied(
                "REVIEW_AUTHORITY_REQUIRED", _("The assigned reviewer is required.")
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
                _("Complete every earlier review sequence first."),
            )
        record = ReviewRecord(
            step.key,
            actor,
            selected_outcome,
            _text(opinion, "opinion"),
            _aware(occurred_at, "occurredAt"),
            self.input_hash,
            self.policy.policy_version,
            self.policy.snapshot_hash,
        )
        return replace(
            self,
            reviews=(*self.reviews, record),
            version=next_version(self.version, self.version),
        )

    def request_exception(
        self,
        *,
        exception_global_id: UUID,
        requester_member_global_id: UUID,
        actor_user_id: str,
        kind: str,
        requirement_key: str,
        reason: str,
        risk: str,
        closure_action_ref: ClosureActionReference,
        closure_action_kind: str,
        requested_at: datetime,
        expires_at: datetime,
        expected_version: int,
        expected_input_hash: str,
    ) -> ReviewCycle:
        if self.state is not CycleState.ACTIVE:
            raise ReviewDenied(
                "REVIEW_CYCLE_CLOSED", _("This review cycle is not active.")
            )
        self._check_precondition(
            expected_version=expected_version,
            expected_input_hash=expected_input_hash,
        )
        selected_kind = _key(kind, "kind")
        try:
            rule = next(
                value
                for value in self.policy.exception_rules
                if value.kind == selected_kind
            )
        except StopIteration as error:
            raise ReviewDenied(
                "EXCEPTION_NOT_ELIGIBLE",
                _("The published policy does not allow this exception."),
            ) from error
        selected_requirement_key = _key(requirement_key, "requirementKey")
        try:
            requirement = next(
                value
                for value in self.input_snapshot.requirements
                if value.requirement_key == selected_requirement_key
            )
        except StopIteration as error:
            raise ReviewDenied(
                "EXCEPTION_NOT_ELIGIBLE",
                _("This requirement is not in the frozen Gate input."),
            ) from error
        if (
            requirement.requirement_key not in rule.eligible_requirement_keys
            or requirement.priority == "P0"
            or requirement.evidence_complete
        ):
            raise ReviewDenied(
                "EXCEPTION_NOT_ELIGIBLE",
                _("This requirement cannot use the selected exception."),
            )
        if not self.input_snapshot.file_evidence_safe:
            raise ReviewDenied(
                "FILE_EVIDENCE_UNSAFE",
                _("Unsafe file evidence cannot be excepted."),
            )
        if closure_action_kind != rule.required_closure_action_kind:
            raise ReviewDenied(
                "CLOSURE_ACTION_REQUIRED",
                _("The required closure action is missing."),
            )
        requested = _aware(requested_at, "requestedAt")
        expires = _aware(expires_at, "expiresAt")
        if expires > requested + timedelta(days=rule.maximum_validity_days):
            raise ReviewDenied(
                "EXCEPTION_VALIDITY_EXCEEDED",
                _("The exception expiry exceeds the published policy."),
            )
        binding = self._binding(rule.approval_authority_slot)
        actor = _text(actor_user_id, "actorUserId", 140)
        requester_member = _uuid(requester_member_global_id, "requesterMemberGlobalId")
        if actor == binding.user_id or requester_member == binding.member_global_id:
            raise ReviewDenied(
                "EXCEPTION_REQUESTER_APPROVER_CONFLICT",
                _("The exception requester and approver must be different users."),
            )
        value = ReviewException(
            global_id=_uuid(exception_global_id, "exceptionGlobalId"),
            cycle_global_id=self.global_id,
            gate_global_id=self.gate_global_id,
            project_global_id=self.project_global_id,
            tenant_id=self.tenant_id,
            policy_global_id=self.policy.policy_global_id,
            kind=rule.kind,
            requirement_global_id=requirement.global_id,
            requirement_key=requirement.requirement_key,
            requirement_priority=requirement.priority,
            approval_authority_slot=rule.approval_authority_slot,
            approval_member_global_id=binding.member_global_id,
            approval_user_id=binding.user_id,
            requester_member_global_id=requester_member,
            requester_user_id=actor,
            reason=reason,
            risk=risk,
            closure_action_ref=closure_action_ref,
            closure_action_kind=closure_action_kind,
            requested_at=requested,
            expires_at=expires,
            policy_version=self.policy.policy_version,
            policy_hash=self.policy.snapshot_hash,
            input_hash=self.input_hash,
        )
        if any(item.global_id == value.global_id for item in self.exceptions):
            raise ReviewDenied(
                "EXCEPTION_ALREADY_EXISTS",
                _("This exception request already exists."),
            )
        return replace(
            self,
            exceptions=(*self.exceptions, value),
            version=next_version(self.version, self.version),
        )

    def decide_exception(
        self,
        *,
        exception_global_id: UUID,
        actor_user_id: str,
        outcome: ExceptionOutcome,
        opinion: str,
        occurred_at: datetime,
        expected_version: int,
        expected_input_hash: str,
        expected_exception_version: int,
    ) -> ReviewCycle:
        if self.state is not CycleState.ACTIVE:
            raise ReviewDenied(
                "REVIEW_CYCLE_CLOSED", _("This review cycle is not active.")
            )
        self._check_precondition(
            expected_version=expected_version,
            expected_input_hash=expected_input_hash,
        )
        identity = _uuid(exception_global_id, "exceptionGlobalId")
        try:
            value = next(item for item in self.exceptions if item.global_id == identity)
        except StopIteration as error:
            raise ReviewDenied(
                "EXCEPTION_NOT_FOUND", _("The exception request was not found.")
            ) from error
        decided = value.decide(
            actor_user_id=actor_user_id,
            outcome=outcome,
            opinion=opinion,
            occurred_at=occurred_at,
            expected_version=expected_exception_version,
            expected_input_hash=expected_input_hash,
        )
        return replace(
            self,
            exceptions=tuple(
                decided if item.global_id == identity else item
                for item in self.exceptions
            ),
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
        current_input: GateInputSnapshot,
        current_closure_action_refs: Mapping[
            UUID, ClosureActionReference
        ] | None = None,
    ) -> ReviewCycle:
        if self.state is not CycleState.ACTIVE:
            raise ReviewDenied(
                "REVIEW_CYCLE_CLOSED", _("This review cycle is not active.")
            )
        self._check_precondition(
            expected_version=expected_version,
            expected_input_hash=expected_input_hash,
        )
        self._check_current_input(current_input)
        actor = _text(actor_user_id, "actorUserId", 140)
        selected_outcome = _enum(outcome, DecisionOutcome, "outcome")
        decided_at = _aware(occurred_at, "occurredAt")
        if self._binding(self.policy.decision_authority_slot).user_id != actor:
            raise ReviewDenied(
                "DECISION_AUTHORITY_REQUIRED",
                _("The assigned decision authority is required."),
            )
        if selected_outcome in {
            DecisionOutcome.PASS,
            DecisionOutcome.CONDITIONAL_PASS,
        }:
            approved = {
                value.step_key
                for value in self.reviews
                if value.outcome is ReviewOutcome.APPROVED
            }
            if any(value.key not in approved for value in self.selected_steps):
                raise ReviewDenied(
                    "REVIEWS_INCOMPLETE",
                    _("Every selected review must approve before this Gate can pass."),
                )
            if not current_input.file_evidence_safe:
                raise ReviewDenied(
                    "FILE_EVIDENCE_UNSAFE",
                    _("File evidence is not safe and current."),
                )
            if current_input.active_blockers:
                raise ReviewDenied(
                    "GATE_BLOCKED",
                    _("Resolve every blocking item before this Gate can pass."),
                )
            missing = current_input.missing_requirements
            if any(value.priority == "P0" for value in missing):
                raise ReviewDenied(
                    "REQUIRED_P0_EVIDENCE_MISSING",
                    _("Required P0 evidence cannot be excepted."),
                )
            if selected_outcome is DecisionOutcome.PASS and missing:
                raise ReviewDenied(
                    "REQUIRED_EVIDENCE_MISSING", _("Required evidence is missing.")
                )
            if selected_outcome is DecisionOutcome.CONDITIONAL_PASS and not missing:
                raise ReviewDenied(
                    "EXCEPTION_NOT_REQUIRED",
                    _("A conditional pass requires an eligible evidence exception."),
                )
            if selected_outcome is DecisionOutcome.CONDITIONAL_PASS:
                for requirement in missing:
                    rule_kinds = {
                        rule.kind
                        for rule in self.policy.exception_rules
                        if requirement.requirement_key in rule.eligible_requirement_keys
                    }
                    if not any(
                        value.kind in rule_kinds
                        and value.supports(
                            requirement,
                            policy=self.policy,
                            input_hash=self.input_hash,
                            at=decided_at,
                            current_closure_action_ref=(
                                (current_closure_action_refs or {}).get(
                                    value.global_id
                                )
                            ),
                        )
                        for value in self.exceptions
                    ):
                        raise ReviewDenied(
                            "APPROVED_EXCEPTION_REQUIRED",
                            _(
                                "Every excepted requirement needs a current approved exception."
                            ),
                        )
        review_hashes = tuple(value.snapshot_hash for value in self.reviews)
        exception_hashes = tuple(
            value.snapshot_hash
            for value in sorted(self.exceptions, key=lambda item: str(item.global_id))
        )
        decision = DecisionSnapshot.build(
            tenant_id=self.tenant_id,
            project_global_id=self.project_global_id,
            gate_global_id=self.gate_global_id,
            cycle_global_id=self.global_id,
            cycle_number=self.cycle_number,
            outcome=selected_outcome,
            actor_user_id=actor,
            occurred_at=decided_at,
            policy_global_id=self.policy.policy_global_id,
            policy_version=self.policy.policy_version,
            policy_hash=self.policy.snapshot_hash,
            input_snapshot=current_input,
            review_hashes=review_hashes,
            exception_hashes=exception_hashes,
            cycle_version=self.version,
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
        current_input: GateInputSnapshot,
        current_bindings: tuple[AuthorityBinding, ...],
        gate_current_cycle_global_id: UUID,
        expected_version: int,
        expected_input_hash: str,
    ) -> ReviewTransition:
        if self.state is not CycleState.DECIDED or self.decision is None:
            raise ReviewDenied(
                "DECISION_REQUIRED",
                _("A completed decision is required before reopening."),
            )
        self._check_precondition(
            expected_version=expected_version,
            expected_input_hash=expected_input_hash,
        )
        current_cycle_id = _uuid(
            gate_current_cycle_global_id, "gateCurrentCycleGlobalId"
        )
        if current_cycle_id != self.global_id:
            raise VersionConflict()
        actor = _text(actor_user_id, "actorUserId", 140)
        if self._binding(self.policy.reopen_authority_slot).user_id != actor:
            raise ReviewDenied(
                "REOPEN_AUTHORITY_REQUIRED",
                _("The assigned reopen authority is required."),
            )
        return self._transition(
            kind=ReviewEventKind.REOPENED,
            trigger=CycleTrigger.MANUAL_REOPEN,
            actor_user_id=actor,
            reason=_text(reason, "reason"),
            occurred_at=_aware(occurred_at, "occurredAt"),
            current_input=current_input,
            current_bindings=current_bindings,
        )

    def invalidate_for_dependency_change(
        self,
        *,
        actor_user_id: str,
        initiated_by_user_id: str | None = None,
        reason: str,
        occurred_at: datetime,
        current_input: GateInputSnapshot,
        current_bindings: tuple[AuthorityBinding, ...],
        gate_current_cycle_global_id: UUID,
        expected_version: int,
        expected_input_hash: str,
    ) -> ReviewTransition:
        if self.state not in {CycleState.ACTIVE, CycleState.DECIDED}:
            raise ReviewDenied(
                "CURRENT_CYCLE_REQUIRED",
                _("A current active or decided cycle is required before refresh."),
            )
        self._check_precondition(
            expected_version=expected_version,
            expected_input_hash=expected_input_hash,
        )
        current_cycle_id = _uuid(
            gate_current_cycle_global_id, "gateCurrentCycleGlobalId"
        )
        if current_cycle_id != self.global_id:
            raise VersionConflict()
        if (
            DependencyEvaluator.GATE_INPUT_SNAPSHOT
            not in self.policy.dependency_evaluators
        ):
            raise ReviewDenied(
                "DEPENDENCY_EVALUATOR_UNAVAILABLE",
                _("The published policy does not allow this dependency evaluator."),
            )
        if (
            type(current_input) is GateInputSnapshot
            and current_input.snapshot_hash == self.input_hash
        ):
            raise ReviewDenied(
                "DEPENDENCY_UNCHANGED",
                _("The Gate input has not changed."),
            )
        return self._transition(
            kind=(
                ReviewEventKind.INVALIDATED
                if self.state is CycleState.DECIDED
                else ReviewEventKind.REFRESHED
            ),
            trigger=CycleTrigger.DEPENDENCY_CHANGE,
            actor_user_id=_text(actor_user_id, "actorUserId", 140),
            initiated_by_user_id=(
                _text(initiated_by_user_id, "initiatedByUserId", 140)
                if initiated_by_user_id is not None
                else None
            ),
            reason=_text(reason, "reason"),
            occurred_at=_aware(occurred_at, "occurredAt"),
            current_input=current_input,
            current_bindings=current_bindings,
        )

    def _transition(
        self,
        *,
        kind: ReviewEventKind,
        trigger: CycleTrigger,
        actor_user_id: str,
        initiated_by_user_id: str | None = None,
        reason: str,
        occurred_at: datetime,
        current_input: GateInputSnapshot,
        current_bindings: tuple[AuthorityBinding, ...],
    ) -> ReviewTransition:
        if type(current_input) is not GateInputSnapshot:
            raise _validation("currentInput", _("Enter a valid Gate input snapshot."))
        if (
            current_input.gate_global_id != self.gate_global_id
            or current_input.project_global_id != self.project_global_id
            or current_input.tenant_id != self.tenant_id
        ):
            raise _validation(
                "currentInput", _("The current Gate input scope does not match.")
            )
        if any(type(value) is not AuthorityBinding for value in current_bindings):
            raise _validation(
                "currentBindings", _("Enter valid current authority bindings.")
            )
        prior_decision = self.decision
        prior_decision_snapshot_global_id = (
            prior_decision.global_id
            if prior_decision is not None
            else self.prior_decision_snapshot_global_id
        )
        prior_decision_hash = (
            prior_decision.snapshot_hash
            if prior_decision is not None
            else self.prior_decision_hash
        )
        successor = ReviewCycle.start(
            gate_global_id=self.gate_global_id,
            project_global_id=self.project_global_id,
            tenant_id=self.tenant_id,
            cycle_number=self.cycle_number + 1,
            trigger=trigger,
            policy=self.policy,
            bindings=tuple(current_bindings),
            input_snapshot=current_input,
            prior_cycle_global_id=self.global_id,
            prior_decision_snapshot_global_id=(prior_decision_snapshot_global_id),
            prior_decision_hash=prior_decision_hash,
        )
        prior = replace(
            self,
            state=(
                CycleState.INVALIDATED
                if prior_decision is not None
                else CycleState.SUPERSEDED
            ),
            version=next_version(self.version, self.version),
        )
        event = ReviewEvent.build(
            kind=kind,
            gate_global_id=self.gate_global_id,
            project_global_id=self.project_global_id,
            old_cycle_global_id=self.global_id,
            new_cycle_global_id=successor.global_id,
            old_input_hash=self.input_hash,
            new_input_hash=current_input.snapshot_hash,
            prior_decision_snapshot_global_id=(prior_decision_snapshot_global_id),
            prior_decision_hash=prior_decision_hash,
            actor_user_id=actor_user_id,
            initiated_by_user_id=initiated_by_user_id,
            reason=reason,
            occurred_at=occurred_at,
        )
        return ReviewTransition(prior, successor, event)


@dataclass(frozen=True, slots=True)
class ReviewTransition:
    prior_cycle: ReviewCycle
    current_cycle: ReviewCycle
    event: ReviewEvent

    def __post_init__(self) -> None:
        expected_event_kind = {
            CycleTrigger.MANUAL_REOPEN: ReviewEventKind.REOPENED,
            CycleTrigger.DEPENDENCY_CHANGE: (
                ReviewEventKind.INVALIDATED
                if (
                    type(self.prior_cycle) is ReviewCycle
                    and self.prior_cycle.state is CycleState.INVALIDATED
                )
                else ReviewEventKind.REFRESHED
            ),
        }.get(
            self.current_cycle.trigger
            if type(self.current_cycle) is ReviewCycle
            else None
        )
        if (
            type(self.prior_cycle) is not ReviewCycle
            or type(self.current_cycle) is not ReviewCycle
            or type(self.event) is not ReviewEvent
            or self.prior_cycle.state
            not in {CycleState.INVALIDATED, CycleState.SUPERSEDED}
            or (
                self.prior_cycle.state is CycleState.INVALIDATED
                and self.prior_cycle.decision is None
            )
            or (
                self.prior_cycle.state is CycleState.SUPERSEDED
                and self.prior_cycle.decision is not None
            )
            or self.current_cycle.state is not CycleState.ACTIVE
            or self.current_cycle.prior_cycle_global_id != self.prior_cycle.global_id
            or self.current_cycle.prior_decision_snapshot_global_id
            != (
                self.prior_cycle.decision.global_id
                if self.prior_cycle.decision is not None
                else self.prior_cycle.prior_decision_snapshot_global_id
            )
            or self.current_cycle.prior_decision_hash
            != (
                self.prior_cycle.decision.snapshot_hash
                if self.prior_cycle.decision is not None
                else self.prior_cycle.prior_decision_hash
            )
            or self.current_cycle.cycle_number != self.prior_cycle.cycle_number + 1
            or self.current_cycle.gate_global_id != self.prior_cycle.gate_global_id
            or self.current_cycle.project_global_id
            != self.prior_cycle.project_global_id
            or self.current_cycle.tenant_id != self.prior_cycle.tenant_id
            or self.current_cycle.policy != self.prior_cycle.policy
            or expected_event_kind is None
            or self.event.kind is not expected_event_kind
            or self.event.gate_global_id != self.prior_cycle.gate_global_id
            or self.event.project_global_id != self.prior_cycle.project_global_id
            or self.event.old_cycle_global_id != self.prior_cycle.global_id
            or self.event.new_cycle_global_id != self.current_cycle.global_id
            or self.event.old_input_hash != self.prior_cycle.input_hash
            or self.event.new_input_hash != self.current_cycle.input_hash
            or self.event.prior_decision_snapshot_global_id
            != self.current_cycle.prior_decision_snapshot_global_id
            or self.event.prior_decision_hash != self.current_cycle.prior_decision_hash
        ):
            raise _validation("transition", _("Enter a valid review cycle transition."))


def downstream_decision_is_current(
    cycle: ReviewCycle,
    *,
    gate_current_cycle_global_id: UUID,
    current_input: GateInputSnapshot,
    at: datetime,
    current_closure_action_refs: Mapping[
        UUID, ClosureActionReference
    ] | None = None,
) -> bool:
    if type(cycle) is not ReviewCycle:
        raise _validation("cycle", _("Enter a valid review cycle."))
    current_cycle_id = _uuid(gate_current_cycle_global_id, "gateCurrentCycleGlobalId")
    checked_at = _aware(at, "at")
    if type(current_input) is not GateInputSnapshot:
        raise _validation("currentInput", _("Enter a valid Gate input snapshot."))
    current = (
        cycle.global_id == current_cycle_id
        and cycle.state is CycleState.DECIDED
        and cycle.decision is not None
        and cycle.decision.outcome
        in {DecisionOutcome.PASS, DecisionOutcome.CONDITIONAL_PASS}
        and cycle.gate_global_id == current_input.gate_global_id
        and cycle.project_global_id == current_input.project_global_id
        and cycle.tenant_id == current_input.tenant_id
        and cycle.input_hash == current_input.snapshot_hash
        and cycle.decision.input_hash == current_input.snapshot_hash
        and checked_at >= cycle.decision.occurred_at
    )
    if not current or cycle.decision is None:
        return False
    if cycle.decision.outcome is DecisionOutcome.PASS:
        return True
    decision_exception_hashes = set(cycle.decision.exception_hashes)
    for requirement in current_input.missing_requirements:
        rule_kinds = {
            rule.kind
            for rule in cycle.policy.exception_rules
            if requirement.requirement_key in rule.eligible_requirement_keys
        }
        if requirement.priority == "P0" or not any(
            value.kind in rule_kinds
            and value.snapshot_hash in decision_exception_hashes
            and value.supports(
                requirement,
                policy=cycle.policy,
                input_hash=current_input.snapshot_hash,
                at=checked_at,
                current_closure_action_ref=(
                    (current_closure_action_refs or {}).get(value.global_id)
                ),
            )
            for value in cycle.exceptions
        ):
            return False
    return True
