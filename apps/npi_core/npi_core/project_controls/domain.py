from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Mapping, Sequence
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


_CONTROL_POLICY_VERSION_NAMESPACE = UUID("479fe5c8-cda3-4a07-ab48-6c649592f95a")
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")
_MAX_DECIMAL_TEXT_LENGTH = 64
_MAX_DECIMAL_PRECISION = 38
_MAX_DECIMAL_SCALE = 18
_HEALTH_DIMENSIONS = (
    "progress",
    "cost",
    "quality",
    "risk",
)
_COMPLETE_PREREQUISITES = frozenset(
    {
        "open_blockers",
        "controlled_files",
        "handover",
        "cost",
    }
)


class ControlPolicyPublicationState(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class HealthDimension(str, Enum):
    PROGRESS = "progress"
    COST = "cost"
    QUALITY = "quality"
    RISK = "risk"


class HealthRuleMode(str, Enum):
    MANUAL = "manual"
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    UNAVAILABLE = "unavailable"


class HealthStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNASSESSED = "unassessed"
    UNAVAILABLE = "unavailable"


class HealthAggregationMode(str, Enum):
    WORST_STATUS = "worst_status"


class ProjectLifecycleState(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectControlAction(str, Enum):
    PAUSE = "pause"
    CANCEL = "cancel"
    RESUME = "resume"
    COMPLETE = "complete"


class ProjectPrerequisiteKey(str, Enum):
    OPEN_BLOCKERS = "open_blockers"
    CONTROLLED_FILES = "controlled_files"
    HANDOVER = "handover"
    COST = "cost"


class PrerequisiteStatus(str, Enum):
    SATISFIED = "satisfied"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class PublishedProjectControlPolicyImmutable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PUBLISHED_PROJECT_CONTROL_POLICY_IMMUTABLE",
            _("A published Project Control Policy version cannot be changed."),
        )


class PublishedProjectControlPolicyRequired(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PUBLISHED_PROJECT_CONTROL_POLICY_REQUIRED",
            _("A published Project Control Policy version is required."),
        )


class ProjectControlPolicyMismatch(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PROJECT_CONTROL_POLICY_MISMATCH",
            _("The Project Control Policy binding is not current."),
        )


class ProjectControlAuthorityRequired(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "PROJECT_CONTROL_AUTHORITY_REQUIRED",
            _("The assigned Project control authority is required."),
        )


class ProjectTransitionUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PROJECT_TRANSITION_UNAVAILABLE",
            _("The requested Project lifecycle action is unavailable."),
        )


class ProjectTransitionBlocked(NpiProblem):
    def __init__(self, blocked_keys: Sequence[ProjectPrerequisiteKey]) -> None:
        super().__init__(
            409,
            "PROJECT_TRANSITION_BLOCKED",
            _("The Project lifecycle action is blocked by unmet prerequisites."),
            detail=_("Resolve every blocking prerequisite before trying again."),
            field_errors=[
                {
                    "path": f"prerequisites.{key.value}",
                    "message": _("Resolve this prerequisite."),
                }
                for key in blocked_keys
            ],
        )


class ProjectTransitionPrerequisiteUnavailable(NpiProblem):
    def __init__(
        self,
        unavailable_keys: Sequence[ProjectPrerequisiteKey],
    ) -> None:
        super().__init__(
            409,
            "PROJECT_TRANSITION_PREREQUISITE_UNAVAILABLE",
            _(
                "The Project lifecycle action cannot be evaluated because a prerequisite is unavailable."
            ),
            detail=_("Wait until every required readiness source is available."),
            field_errors=[
                {
                    "path": f"prerequisites.{key.value}",
                    "message": _("This readiness source is unavailable."),
                }
                for key in unavailable_keys
            ],
        )


def _validation(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _require_enum(value: object, expected: type[Enum], path: str):
    if not isinstance(value, expected):
        raise _validation(path, _("Select a supported value."))
    return value


def _require_uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
        raise _validation(path, _("Enter a valid global ID."))
    return value


def _require_positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _validation(path, _("Enter a positive integer."))
    return value


def _require_text(
    value: object,
    path: str,
    *,
    maximum_length: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _validation(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum_length or (
        pattern is not None and pattern.fullmatch(normalized) is None
    ):
        raise _validation(path, _("Enter a valid value."))
    return normalized


def _require_optional_text(
    value: object,
    path: str,
    *,
    maximum_length: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _validation(path, _("Enter a valid value."))
    normalized = value.strip()
    if len(normalized) > maximum_length:
        raise _validation(path, _("Enter a valid value."))
    return normalized or None


def _require_key(value: object, path: str) -> str:
    return _require_text(
        value,
        path,
        maximum_length=64,
        pattern=_KEY_PATTERN,
    )


def _require_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _validation(path, _("Enter a valid snapshot hash."))
    return value


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise _validation(path, _("Enter a finite number."))
    if not isinstance(value, (Decimal, int, float, str)):
        raise _validation(path, _("Enter a finite number."))
    if isinstance(value, str) and (
        len(value) > _MAX_DECIMAL_TEXT_LENGTH
        or _DECIMAL_PATTERN.fullmatch(value) is None
    ):
        raise _validation(path, _("Enter a finite number."))
    if isinstance(value, float) and not math.isfinite(value):
        raise _validation(path, _("Enter a finite number."))
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _validation(path, _("Enter a finite number."))
    if not result.is_finite():
        raise _validation(path, _("Enter a finite number."))
    decimal_tuple = result.as_tuple()
    digit_count = len(decimal_tuple.digits)
    exponent = int(decimal_tuple.exponent)
    scale = max(-exponent, 0)
    integer_digits = max(digit_count + exponent, 0)
    if (
        digit_count > _MAX_DECIMAL_PRECISION
        or scale > _MAX_DECIMAL_SCALE
        or integer_digits > _MAX_DECIMAL_PRECISION
    ):
        raise _validation(path, _("Enter a finite number."))
    return result


def _decimal_text(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        fixed = coefficient + ("0" * exponent)
    else:
        point = len(coefficient) + exponent
        fixed = (
            f"0.{('0' * -point)}{coefficient}"
            if point <= 0
            else f"{coefficient[:point]}.{coefficient[point:]}"
        )
        fixed = fixed.rstrip("0").rstrip(".")
    return f"-{fixed}" if sign else fixed


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PriorPolicyVersionReference:
    global_id: UUID
    policy_version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        _require_uuid(self.global_id, "priorVersionRef.globalId")
        _require_positive_integer(
            self.policy_version,
            "priorVersionRef.version",
        )
        _require_hash(
            self.snapshot_hash,
            "priorVersionRef.snapshotHash",
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.policy_version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class HealthDimensionRule:
    dimension: HealthDimension
    mode: HealthRuleMode
    green_threshold: Decimal | int | float | str | None = None
    yellow_threshold: Decimal | int | float | str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.dimension, HealthDimension, "healthRules.dimension")
        _require_enum(self.mode, HealthRuleMode, "healthRules.mode")
        if self.mode in {HealthRuleMode.MANUAL, HealthRuleMode.UNAVAILABLE}:
            if self.green_threshold is not None or self.yellow_threshold is not None:
                raise _validation(
                    "healthRules.thresholds",
                    _("This health rule mode does not accept thresholds."),
                )
            return
        green = _decimal(
            self.green_threshold,
            "healthRules.greenThreshold",
        )
        yellow = _decimal(
            self.yellow_threshold,
            "healthRules.yellowThreshold",
        )
        if self.mode is HealthRuleMode.HIGHER_IS_BETTER and yellow >= green:
            raise _validation(
                "healthRules.thresholds",
                _(
                    "A higher-is-better rule requires the yellow threshold below the green threshold."
                ),
            )
        if self.mode is HealthRuleMode.LOWER_IS_BETTER and green >= yellow:
            raise _validation(
                "healthRules.thresholds",
                _(
                    "A lower-is-better rule requires the green threshold below the yellow threshold."
                ),
            )
        object.__setattr__(self, "green_threshold", green)
        object.__setattr__(self, "yellow_threshold", yellow)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "dimension": self.dimension.value,
            "mode": self.mode.value,
            "greenThreshold": (
                _decimal_text(self.green_threshold)
                if isinstance(self.green_threshold, Decimal)
                else None
            ),
            "yellowThreshold": (
                _decimal_text(self.yellow_threshold)
                if isinstance(self.yellow_threshold, Decimal)
                else None
            ),
        }

    def evaluate(
        self,
        measurement: HealthMeasurement | None,
    ) -> HealthDimensionResult:
        if self.mode is HealthRuleMode.UNAVAILABLE:
            if measurement is not None:
                raise _validation(
                    f"measurements.{self.dimension.value}",
                    _("This health dimension is unavailable."),
                )
            return HealthDimensionResult(
                self.dimension,
                self.mode,
                HealthStatus.UNAVAILABLE,
            )
        if measurement is None:
            return HealthDimensionResult(
                self.dimension,
                self.mode,
                HealthStatus.UNASSESSED,
            )
        if measurement.dimension is not self.dimension:
            raise _validation(
                f"measurements.{self.dimension.value}",
                _("The health measurement dimension does not match its rule."),
            )
        if self.mode is HealthRuleMode.MANUAL:
            if (
                measurement.manual_status
                not in {
                    HealthStatus.GREEN,
                    HealthStatus.YELLOW,
                    HealthStatus.RED,
                }
                or measurement.numeric_value is not None
            ):
                raise _validation(
                    f"measurements.{self.dimension.value}",
                    _("Enter a supported manual health status."),
                )
            return HealthDimensionResult(
                self.dimension,
                self.mode,
                measurement.manual_status,
            )
        if measurement.numeric_value is None or measurement.manual_status is not None:
            raise _validation(
                f"measurements.{self.dimension.value}",
                _("Enter a numeric health measurement."),
            )
        value = measurement.numeric_value
        assert isinstance(value, Decimal)
        assert isinstance(self.green_threshold, Decimal)
        assert isinstance(self.yellow_threshold, Decimal)
        if self.mode is HealthRuleMode.HIGHER_IS_BETTER:
            status = (
                HealthStatus.GREEN
                if value >= self.green_threshold
                else (
                    HealthStatus.YELLOW
                    if value >= self.yellow_threshold
                    else HealthStatus.RED
                )
            )
        else:
            status = (
                HealthStatus.GREEN
                if value <= self.green_threshold
                else (
                    HealthStatus.YELLOW
                    if value <= self.yellow_threshold
                    else HealthStatus.RED
                )
            )
        return HealthDimensionResult(
            self.dimension,
            self.mode,
            status,
            numeric_value=value,
        )


@dataclass(frozen=True, slots=True)
class HealthAggregationRule:
    mode: HealthAggregationMode
    require_all: bool

    def __post_init__(self) -> None:
        _require_enum(self.mode, HealthAggregationMode, "aggregation.mode")
        if type(self.require_all) is not bool:
            raise _validation(
                "aggregation.requireAll",
                _("Select a valid true or false value."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "requireAll": self.require_all,
        }

    def aggregate(
        self,
        results: Sequence[HealthDimensionResult],
    ) -> HealthStatus:
        values = tuple(results)
        if len(values) != len(_HEALTH_DIMENSIONS) or {
            value.dimension.value for value in values
        } != set(_HEALTH_DIMENSIONS):
            raise _validation(
                "dimensionResults",
                _("Evaluate every required health dimension exactly once."),
            )
        statuses = {value.status for value in values}
        if self.require_all:
            if HealthStatus.UNAVAILABLE in statuses:
                return HealthStatus.UNAVAILABLE
            if HealthStatus.UNASSESSED in statuses:
                return HealthStatus.UNASSESSED
        assessed = statuses.intersection(
            {
                HealthStatus.GREEN,
                HealthStatus.YELLOW,
                HealthStatus.RED,
            }
        )
        if HealthStatus.RED in assessed:
            return HealthStatus.RED
        if HealthStatus.YELLOW in assessed:
            return HealthStatus.YELLOW
        if HealthStatus.GREEN in assessed:
            return HealthStatus.GREEN
        if HealthStatus.UNAVAILABLE in statuses:
            return HealthStatus.UNAVAILABLE
        return HealthStatus.UNASSESSED


@dataclass(frozen=True, slots=True)
class ProjectTransitionRule:
    source_state: ProjectLifecycleState
    action: ProjectControlAction
    target_state: ProjectLifecycleState
    authority_slot: str
    prerequisites: tuple[ProjectPrerequisiteKey, ...]

    def __post_init__(self) -> None:
        _require_enum(
            self.source_state,
            ProjectLifecycleState,
            "transitions.sourceState",
        )
        _require_enum(self.action, ProjectControlAction, "transitions.action")
        _require_enum(
            self.target_state,
            ProjectLifecycleState,
            "transitions.targetState",
        )
        object.__setattr__(
            self,
            "authority_slot",
            _require_key(
                self.authority_slot,
                "transitions.authoritySlot",
            ),
        )
        prerequisites = tuple(self.prerequisites)
        if any(
            not isinstance(value, ProjectPrerequisiteKey) for value in prerequisites
        ) or len(set(prerequisites)) != len(prerequisites):
            raise _validation(
                "transitions.prerequisites",
                _("Select unique supported Project prerequisites."),
            )
        object.__setattr__(
            self,
            "prerequisites",
            tuple(sorted(prerequisites, key=lambda value: value.value)),
        )
        if (
            self.source_state
            in {
                ProjectLifecycleState.COMPLETED,
                ProjectLifecycleState.CANCELLED,
            }
            or self.source_state is self.target_state
        ):
            raise _validation(
                "transitions.sourceState",
                _("Select a non-terminal Project transition."),
            )
        expected_target = {
            ProjectControlAction.PAUSE: ProjectLifecycleState.ON_HOLD,
            ProjectControlAction.CANCEL: ProjectLifecycleState.CANCELLED,
            ProjectControlAction.RESUME: ProjectLifecycleState.ACTIVE,
            ProjectControlAction.COMPLETE: ProjectLifecycleState.COMPLETED,
        }[self.action]
        if self.target_state is not expected_target:
            raise _validation(
                "transitions.targetState",
                _("Select the lifecycle state required by this action."),
            )
        if (
            self.action is ProjectControlAction.RESUME
            and self.source_state is not ProjectLifecycleState.ON_HOLD
        ):
            raise _validation(
                "transitions.sourceState",
                _("Resume is only available for a Project that is on hold."),
            )
        if (
            self.action is ProjectControlAction.PAUSE
            and self.source_state is ProjectLifecycleState.ON_HOLD
        ):
            raise _validation(
                "transitions.sourceState",
                _("A Project that is already on hold cannot be paused."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "sourceState": self.source_state.value,
            "action": self.action.value,
            "targetState": self.target_state.value,
            "authoritySlot": self.authority_slot,
            "prerequisites": [value.value for value in self.prerequisites],
        }


@dataclass(frozen=True, slots=True)
class ProjectControlPolicySnapshot:
    global_id: UUID
    policy_global_id: UUID
    policy_code: str
    policy_version: int
    prior_version_ref: PriorPolicyVersionReference | None
    authority_slots: tuple[str, ...]
    health_assessment_slot: str
    health_rules: tuple[HealthDimensionRule, ...]
    aggregation: HealthAggregationRule
    transitions: tuple[ProjectTransitionRule, ...]
    snapshot_hash: str

    def __post_init__(self) -> None:
        _validate_policy_identity(
            self.global_id,
            self.policy_global_id,
            self.policy_code,
            self.policy_version,
            self.prior_version_ref,
        )
        (
            authority_slots,
            health_rules,
            transitions,
        ) = _validate_policy_contents(
            self.authority_slots,
            self.health_assessment_slot,
            self.health_rules,
            self.aggregation,
            self.transitions,
            publishable=True,
        )
        object.__setattr__(self, "authority_slots", authority_slots)
        object.__setattr__(self, "health_rules", health_rules)
        object.__setattr__(self, "transitions", transitions)
        _require_hash(self.snapshot_hash, "snapshotHash")
        if self.snapshot_hash != _canonical_hash(self.canonical_dict()):
            raise _validation(
                "snapshotHash",
                _("The Project Control Policy snapshot hash is invalid."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return _policy_snapshot_payload(
            global_id=self.global_id,
            policy_global_id=self.policy_global_id,
            policy_code=self.policy_code,
            policy_version=self.policy_version,
            prior_version_ref=self.prior_version_ref,
            authority_slots=self.authority_slots,
            health_assessment_slot=self.health_assessment_slot,
            health_rules=self.health_rules,
            aggregation=self.aggregation,
            transitions=self.transitions,
        )

    def transition(
        self,
        source_state: ProjectLifecycleState,
        action: ProjectControlAction,
    ) -> ProjectTransitionRule:
        _require_enum(source_state, ProjectLifecycleState, "sourceState")
        _require_enum(action, ProjectControlAction, "action")
        matches = tuple(
            rule
            for rule in self.transitions
            if rule.source_state is source_state and rule.action is action
        )
        if len(matches) != 1:
            raise ProjectTransitionUnavailable()
        return matches[0]


@dataclass(frozen=True, slots=True)
class ProjectControlPolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    policy_code: str
    policy_version: int
    version: int
    title: str
    publication_state: ControlPolicyPublicationState
    prior_version_ref: PriorPolicyVersionReference | None
    authority_slots: tuple[str, ...]
    health_assessment_slot: str
    health_rules: tuple[HealthDimensionRule, ...]
    aggregation: HealthAggregationRule
    transitions: tuple[ProjectTransitionRule, ...]

    def __post_init__(self) -> None:
        _validate_policy_identity(
            self.global_id,
            self.policy_global_id,
            self.policy_code,
            self.policy_version,
            self.prior_version_ref,
        )
        _require_positive_integer(self.version, "version")
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "title", maximum_length=140),
        )
        _require_enum(
            self.publication_state,
            ControlPolicyPublicationState,
            "publicationState",
        )
        (
            authority_slots,
            health_rules,
            transitions,
        ) = _validate_policy_contents(
            self.authority_slots,
            self.health_assessment_slot,
            self.health_rules,
            self.aggregation,
            self.transitions,
            publishable=(
                self.publication_state is ControlPolicyPublicationState.PUBLISHED
            ),
        )
        object.__setattr__(self, "authority_slots", authority_slots)
        object.__setattr__(self, "health_rules", health_rules)
        object.__setattr__(self, "transitions", transitions)

    @classmethod
    def create_draft(
        cls,
        *,
        policy_global_id: UUID,
        policy_code: str,
        policy_version: int,
        title: str,
        authority_slots: tuple[str, ...],
        health_assessment_slot: str,
        health_rules: tuple[HealthDimensionRule, ...],
        aggregation: HealthAggregationRule,
        transitions: tuple[ProjectTransitionRule, ...],
        previous_version: ProjectControlPolicyVersion | None = None,
    ) -> ProjectControlPolicyVersion:
        _require_uuid(policy_global_id, "policyGlobalId")
        _require_positive_integer(policy_version, "policyVersion")
        prior_ref = None
        if previous_version is None:
            if policy_version != 1:
                raise _validation(
                    "policyVersion",
                    _("The first Project Control Policy version must be version 1."),
                )
        else:
            if (
                not isinstance(previous_version, ProjectControlPolicyVersion)
                or previous_version.publication_state
                is not ControlPolicyPublicationState.PUBLISHED
            ):
                raise PublishedProjectControlPolicyRequired()
            if (
                previous_version.policy_global_id != policy_global_id
                or previous_version.policy_code != policy_code
                or policy_version != previous_version.policy_version + 1
            ):
                raise _validation(
                    "policyVersion",
                    _(
                        "Project Control Policy versions must be contiguous within one policy."
                    ),
                )
            prior_ref = PriorPolicyVersionReference(
                previous_version.global_id,
                previous_version.policy_version,
                previous_version.snapshot_hash,
            )
        global_id = uuid5(
            _CONTROL_POLICY_VERSION_NAMESPACE,
            f"{policy_global_id}:{policy_version}",
        )
        return cls(
            global_id=global_id,
            policy_global_id=policy_global_id,
            policy_code=policy_code,
            policy_version=policy_version,
            version=1,
            title=title,
            publication_state=ControlPolicyPublicationState.DRAFT,
            prior_version_ref=prior_ref,
            authority_slots=authority_slots,
            health_assessment_slot=health_assessment_slot,
            health_rules=health_rules,
            aggregation=aggregation,
            transitions=transitions,
        )

    def edit_draft(
        self,
        *,
        expected_version: int,
        title: str | None = None,
        authority_slots: tuple[str, ...] | None = None,
        health_assessment_slot: str | None = None,
        health_rules: tuple[HealthDimensionRule, ...] | None = None,
        aggregation: HealthAggregationRule | None = None,
        transitions: tuple[ProjectTransitionRule, ...] | None = None,
    ) -> ProjectControlPolicyVersion:
        if self.publication_state is ControlPolicyPublicationState.PUBLISHED:
            raise PublishedProjectControlPolicyImmutable()
        return replace(
            self,
            version=next_version(self.version, expected_version),
            title=self.title if title is None else title,
            authority_slots=(
                self.authority_slots if authority_slots is None else authority_slots
            ),
            health_assessment_slot=(
                self.health_assessment_slot
                if health_assessment_slot is None
                else health_assessment_slot
            ),
            health_rules=(self.health_rules if health_rules is None else health_rules),
            aggregation=(self.aggregation if aggregation is None else aggregation),
            transitions=(self.transitions if transitions is None else transitions),
        )

    def publish(
        self,
        *,
        expected_version: int,
    ) -> ProjectControlPolicyVersion:
        if self.publication_state is ControlPolicyPublicationState.PUBLISHED:
            raise PublishedProjectControlPolicyImmutable()
        _validate_policy_contents(
            self.authority_slots,
            self.health_assessment_slot,
            self.health_rules,
            self.aggregation,
            self.transitions,
            publishable=True,
        )
        return replace(
            self,
            version=next_version(self.version, expected_version),
            publication_state=ControlPolicyPublicationState.PUBLISHED,
        )

    def next_draft(
        self,
        *,
        title: str,
        authority_slots: tuple[str, ...],
        health_assessment_slot: str,
        health_rules: tuple[HealthDimensionRule, ...],
        aggregation: HealthAggregationRule,
        transitions: tuple[ProjectTransitionRule, ...],
    ) -> ProjectControlPolicyVersion:
        if self.publication_state is not ControlPolicyPublicationState.PUBLISHED:
            raise PublishedProjectControlPolicyRequired()
        return ProjectControlPolicyVersion.create_draft(
            policy_global_id=self.policy_global_id,
            policy_code=self.policy_code,
            policy_version=self.policy_version + 1,
            title=title,
            authority_slots=authority_slots,
            health_assessment_slot=health_assessment_slot,
            health_rules=health_rules,
            aggregation=aggregation,
            transitions=transitions,
            previous_version=self,
        )

    def canonical_dict(self) -> dict[str, object]:
        return _policy_snapshot_payload(
            global_id=self.global_id,
            policy_global_id=self.policy_global_id,
            policy_code=self.policy_code,
            policy_version=self.policy_version,
            prior_version_ref=self.prior_version_ref,
            authority_slots=self.authority_slots,
            health_assessment_slot=self.health_assessment_slot,
            health_rules=self.health_rules,
            aggregation=self.aggregation,
            transitions=self.transitions,
        )

    @property
    def snapshot_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())

    def snapshot(self) -> ProjectControlPolicySnapshot:
        if self.publication_state is not ControlPolicyPublicationState.PUBLISHED:
            raise PublishedProjectControlPolicyRequired()
        return ProjectControlPolicySnapshot(
            global_id=self.global_id,
            policy_global_id=self.policy_global_id,
            policy_code=self.policy_code,
            policy_version=self.policy_version,
            prior_version_ref=self.prior_version_ref,
            authority_slots=self.authority_slots,
            health_assessment_slot=self.health_assessment_slot,
            health_rules=self.health_rules,
            aggregation=self.aggregation,
            transitions=self.transitions,
            snapshot_hash=self.snapshot_hash,
        )


def _validate_policy_identity(
    global_id: object,
    policy_global_id: object,
    policy_code: object,
    policy_version: object,
    prior_version_ref: object,
) -> None:
    version = _require_positive_integer(policy_version, "policyVersion")
    policy_identity = _require_uuid(policy_global_id, "policyGlobalId")
    version_identity = _require_uuid(global_id, "globalId")
    _require_text(
        policy_code,
        "policyCode",
        maximum_length=64,
        pattern=_CODE_PATTERN,
    )
    expected = uuid5(
        _CONTROL_POLICY_VERSION_NAMESPACE,
        f"{policy_identity}:{version}",
    )
    if version_identity != expected:
        raise _validation(
            "globalId",
            _("The Project Control Policy version identifier is not canonical."),
        )
    if version == 1:
        if prior_version_ref is not None:
            raise _validation(
                "priorVersionRef",
                _("The first policy version cannot have a prior version."),
            )
    else:
        if (
            not isinstance(
                prior_version_ref,
                PriorPolicyVersionReference,
            )
            or prior_version_ref.policy_version != version - 1
        ):
            raise _validation(
                "priorVersionRef",
                _("The prior Project Control Policy version is incomplete."),
            )
        expected_prior_global_id = uuid5(
            _CONTROL_POLICY_VERSION_NAMESPACE,
            f"{policy_identity}:{version - 1}",
        )
        if prior_version_ref.global_id != expected_prior_global_id:
            raise _validation(
                "priorVersionRef.globalId",
                _(
                    "The prior Project Control Policy version identifier is not canonical."
                ),
            )


def _validate_policy_contents(
    authority_slots: Sequence[object],
    health_assessment_slot: object,
    health_rules: Sequence[object],
    aggregation: object,
    transitions: Sequence[object],
    *,
    publishable: bool,
) -> tuple[
    tuple[str, ...],
    tuple[HealthDimensionRule, ...],
    tuple[ProjectTransitionRule, ...],
]:
    slots = tuple(
        sorted(
            (_require_key(value, "authoritySlots") for value in authority_slots),
            key=str.casefold,
        )
    )
    if len({slot.casefold() for slot in slots}) != len(slots):
        raise _validation(
            "authoritySlots",
            _("Project control authority slots must be unique."),
        )
    assessment_slot = _require_key(
        health_assessment_slot,
        "healthAssessmentSlot",
    )
    rules = tuple(health_rules)
    if any(type(value) is not HealthDimensionRule for value in rules):
        raise _validation(
            "healthRules",
            _("Enter valid Project health rules."),
        )
    rules = tuple(sorted(rules, key=lambda value: value.dimension.value))
    if len({rule.dimension for rule in rules}) != len(rules):
        raise _validation(
            "healthRules.dimension",
            _("Project health rule dimensions must be unique."),
        )
    if not isinstance(aggregation, HealthAggregationRule):
        raise _validation(
            "aggregation",
            _("Enter a valid Project health aggregation rule."),
        )
    transition_values = tuple(transitions)
    if any(type(value) is not ProjectTransitionRule for value in transition_values):
        raise _validation(
            "transitions",
            _("Enter valid Project lifecycle transitions."),
        )
    transition_values = tuple(
        sorted(
            transition_values,
            key=lambda value: (
                value.source_state.value,
                value.action.value,
                value.target_state.value,
            ),
        )
    )
    if len({(value.source_state, value.action) for value in transition_values}) != len(
        transition_values
    ):
        raise _validation(
            "transitions",
            _("A Project state and action can select only one transition."),
        )
    if publishable:
        if not slots:
            raise _validation(
                "authoritySlots",
                _("Add at least one Project control authority slot."),
            )
        if assessment_slot not in slots:
            raise _validation(
                "healthAssessmentSlot",
                _("Select a declared Project control authority slot."),
            )
        if {rule.dimension.value for rule in rules} != set(_HEALTH_DIMENSIONS):
            raise _validation(
                "healthRules",
                _("Define progress, cost, quality, and risk health rules."),
            )
        if not transition_values or {
            value.action for value in transition_values
        } != set(ProjectControlAction):
            raise _validation(
                "transitions",
                _("Define pause, cancel, resume, and complete transitions."),
            )
        if any(value.authority_slot not in slots for value in transition_values):
            raise _validation(
                "transitions.authoritySlot",
                _("Select a declared Project control authority slot."),
            )
        for transition in transition_values:
            if (
                transition.action is ProjectControlAction.COMPLETE
                and {value.value for value in transition.prerequisites}
                != _COMPLETE_PREREQUISITES
            ):
                raise _validation(
                    "transitions.prerequisites",
                    _(
                        "Every complete transition must check open blockers, controlled files, handover, and cost."
                    ),
                )
    return slots, rules, transition_values


def _policy_snapshot_payload(
    *,
    global_id: UUID,
    policy_global_id: UUID,
    policy_code: str,
    policy_version: int,
    prior_version_ref: PriorPolicyVersionReference | None,
    authority_slots: Sequence[str],
    health_assessment_slot: str,
    health_rules: Sequence[HealthDimensionRule],
    aggregation: HealthAggregationRule,
    transitions: Sequence[ProjectTransitionRule],
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "globalId": str(global_id),
        "policyGlobalId": str(policy_global_id),
        "policyCode": policy_code,
        "policyVersion": policy_version,
        "priorVersionRef": (
            prior_version_ref.canonical_dict()
            if prior_version_ref is not None
            else None
        ),
        "authoritySlots": sorted(authority_slots, key=str.casefold),
        "healthAssessmentSlot": health_assessment_slot,
        "healthRules": [
            value.canonical_dict()
            for value in sorted(
                health_rules,
                key=lambda item: item.dimension.value,
            )
        ],
        "aggregation": aggregation.canonical_dict(),
        "transitions": [
            value.canonical_dict()
            for value in sorted(
                transitions,
                key=lambda item: (
                    item.source_state.value,
                    item.action.value,
                    item.target_state.value,
                ),
            )
        ],
    }


@dataclass(frozen=True, slots=True)
class FrozenProjectControlAuthority:
    slot: str
    member_global_id: UUID
    user_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "slot",
            _require_key(self.slot, "bindings.slot"),
        )
        _require_uuid(
            self.member_global_id,
            "bindings.memberGlobalId",
        )
        object.__setattr__(
            self,
            "user_id",
            _require_text(
                self.user_id,
                "bindings.userId",
                maximum_length=254,
                pattern=_EMAIL_PATTERN,
            ).casefold(),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "slot": self.slot,
            "memberGlobalId": str(self.member_global_id),
            "userId": self.user_id,
        }


@dataclass(frozen=True, slots=True)
class ProjectControlBinding:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    policy_global_id: UUID
    policy_version: int
    policy_snapshot_hash: str
    authorities: tuple[FrozenProjectControlAuthority, ...]
    version: int = 1

    def __post_init__(self) -> None:
        _require_uuid(self.global_id, "globalId")
        object.__setattr__(
            self,
            "tenant_id",
            _require_text(
                self.tenant_id,
                "tenantId",
                maximum_length=128,
                pattern=_IDENTIFIER_PATTERN,
            ),
        )
        _require_uuid(self.project_global_id, "projectGlobalId")
        _require_uuid(self.policy_global_id, "policyRef.globalId")
        _require_positive_integer(
            self.policy_version,
            "policyRef.version",
        )
        _require_hash(
            self.policy_snapshot_hash,
            "policyRef.snapshotHash",
        )
        _require_positive_integer(self.version, "version")
        authorities = tuple(self.authorities)
        if any(
            type(value) is not FrozenProjectControlAuthority for value in authorities
        ):
            raise _validation(
                "bindings",
                _("Enter valid Project control authority bindings."),
            )
        authorities = tuple(
            sorted(authorities, key=lambda value: value.slot.casefold())
        )
        if len({value.slot.casefold() for value in authorities}) != len(authorities):
            raise _validation(
                "bindings.slot",
                _("Bind each Project control authority slot exactly once."),
            )
        object.__setattr__(self, "authorities", authorities)

    @classmethod
    def freeze(
        cls,
        *,
        global_id: UUID,
        tenant_id: str,
        project_global_id: UUID,
        policy: ProjectControlPolicySnapshot,
        authorities: tuple[FrozenProjectControlAuthority, ...],
    ) -> ProjectControlBinding:
        if not isinstance(policy, ProjectControlPolicySnapshot):
            raise PublishedProjectControlPolicyRequired()
        supplied_slots = {
            value.slot
            for value in authorities
            if isinstance(value, FrozenProjectControlAuthority)
        }
        if len(authorities) != len(policy.authority_slots) or supplied_slots != set(
            policy.authority_slots
        ):
            raise _validation(
                "bindings",
                _("Bind every Project control authority slot exactly once."),
            )
        return cls(
            global_id=global_id,
            tenant_id=tenant_id,
            project_global_id=project_global_id,
            policy_global_id=policy.policy_global_id,
            policy_version=policy.policy_version,
            policy_snapshot_hash=policy.snapshot_hash,
            authorities=authorities,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "policyRef": {
                "globalId": str(self.policy_global_id),
                "version": self.policy_version,
                "snapshotHash": self.policy_snapshot_hash,
            },
            "authorities": [value.canonical_dict() for value in self.authorities],
            "version": self.version,
        }

    @property
    def snapshot_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())

    def require_policy(
        self,
        policy: ProjectControlPolicySnapshot,
    ) -> None:
        if (
            not isinstance(policy, ProjectControlPolicySnapshot)
            or self.policy_global_id != policy.policy_global_id
            or self.policy_version != policy.policy_version
            or self.policy_snapshot_hash != policy.snapshot_hash
            or {authority.slot for authority in self.authorities}
            != set(policy.authority_slots)
        ):
            raise ProjectControlPolicyMismatch()

    def require_actor(
        self,
        slot: str,
        *,
        actor_member_global_id: UUID,
        actor_user_id: str,
    ) -> FrozenProjectControlAuthority:
        selected_slot = _require_key(slot, "authoritySlot")
        member_id = _require_uuid(
            actor_member_global_id,
            "actorMemberGlobalId",
        )
        user_id = _require_text(
            actor_user_id,
            "actorUserId",
            maximum_length=254,
            pattern=_EMAIL_PATTERN,
        ).casefold()
        for authority in self.authorities:
            if (
                authority.slot == selected_slot
                and authority.member_global_id == member_id
                and authority.user_id == user_id
            ):
                return authority
        raise ProjectControlAuthorityRequired()


@dataclass(frozen=True, slots=True)
class HealthMeasurement:
    dimension: HealthDimension
    numeric_value: Decimal | int | float | str | None = None
    manual_status: HealthStatus | None = None

    def __post_init__(self) -> None:
        _require_enum(self.dimension, HealthDimension, "measurements.dimension")
        if self.numeric_value is not None:
            object.__setattr__(
                self,
                "numeric_value",
                _decimal(
                    self.numeric_value,
                    f"measurements.{self.dimension.value}.value",
                ),
            )
        if self.manual_status is not None:
            _require_enum(
                self.manual_status,
                HealthStatus,
                f"measurements.{self.dimension.value}.status",
            )
        if self.numeric_value is not None and self.manual_status is not None:
            raise _validation(
                f"measurements.{self.dimension.value}",
                _("Enter either a numeric value or a manual status."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "dimension": self.dimension.value,
            "numericValue": (
                _decimal_text(self.numeric_value)
                if isinstance(self.numeric_value, Decimal)
                else None
            ),
            "manualStatus": (
                self.manual_status.value if self.manual_status is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class HealthDimensionResult:
    dimension: HealthDimension
    rule_mode: HealthRuleMode
    status: HealthStatus
    numeric_value: Decimal | None = None

    def __post_init__(self) -> None:
        _require_enum(self.dimension, HealthDimension, "results.dimension")
        _require_enum(self.rule_mode, HealthRuleMode, "results.ruleMode")
        _require_enum(self.status, HealthStatus, "results.status")
        if self.numeric_value is not None:
            object.__setattr__(
                self,
                "numeric_value",
                _decimal(self.numeric_value, "results.numericValue"),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "dimension": self.dimension.value,
            "ruleMode": self.rule_mode.value,
            "status": self.status.value,
            "numericValue": (
                _decimal_text(self.numeric_value)
                if self.numeric_value is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ProjectHealthEvaluation:
    policy_global_id: UUID
    policy_version: int
    policy_snapshot_hash: str
    dimension_results: tuple[HealthDimensionResult, ...]
    overall_status: HealthStatus
    reason: str | None
    recovery_plan: str | None

    def __post_init__(self) -> None:
        _require_uuid(self.policy_global_id, "policyRef.globalId")
        _require_positive_integer(self.policy_version, "policyRef.version")
        _require_hash(
            self.policy_snapshot_hash,
            "policyRef.snapshotHash",
        )
        results = tuple(self.dimension_results)
        if (
            len(results) != len(_HEALTH_DIMENSIONS)
            or any(type(value) is not HealthDimensionResult for value in results)
            or {value.dimension.value for value in results} != set(_HEALTH_DIMENSIONS)
        ):
            raise _validation(
                "dimensionResults",
                _("Evaluate every required health dimension exactly once."),
            )
        object.__setattr__(
            self,
            "dimension_results",
            tuple(sorted(results, key=lambda value: value.dimension.value)),
        )
        _require_enum(
            self.overall_status,
            HealthStatus,
            "overallStatus",
        )
        object.__setattr__(
            self,
            "reason",
            _require_optional_text(
                self.reason,
                "reason",
                maximum_length=2000,
            ),
        )
        object.__setattr__(
            self,
            "recovery_plan",
            _require_optional_text(
                self.recovery_plan,
                "recoveryPlan",
                maximum_length=4000,
            ),
        )
        if (
            self.overall_status is HealthStatus.RED
            or any(value.status is HealthStatus.RED for value in self.dimension_results)
        ) and (self.reason is None or self.recovery_plan is None):
            errors = []
            if self.reason is None:
                errors.append(
                    {
                        "path": "reason",
                        "message": _("Enter the reason for red Project health."),
                    }
                )
            if self.recovery_plan is None:
                errors.append(
                    {
                        "path": "recoveryPlan",
                        "message": _("Enter the recovery plan for red Project health."),
                    }
                )
            raise RequestValidationFailed(errors)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "policyRef": {
                "globalId": str(self.policy_global_id),
                "version": self.policy_version,
                "snapshotHash": self.policy_snapshot_hash,
            },
            "dimensionResults": [
                value.canonical_dict() for value in self.dimension_results
            ],
            "overallStatus": self.overall_status.value,
            "reason": self.reason,
            "recoveryPlan": self.recovery_plan,
        }

    @property
    def result_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())


def evaluate_project_health(
    *,
    policy: ProjectControlPolicySnapshot,
    binding: ProjectControlBinding,
    actor_member_global_id: UUID,
    actor_user_id: str,
    measurements: Sequence[HealthMeasurement],
    reason: str | None = None,
    recovery_plan: str | None = None,
) -> ProjectHealthEvaluation:
    if not isinstance(policy, ProjectControlPolicySnapshot):
        raise PublishedProjectControlPolicyRequired()
    if not isinstance(binding, ProjectControlBinding):
        raise ProjectControlPolicyMismatch()
    binding.require_policy(policy)
    binding.require_actor(
        policy.health_assessment_slot,
        actor_member_global_id=actor_member_global_id,
        actor_user_id=actor_user_id,
    )
    measurement_values = tuple(measurements)
    if any(type(value) is not HealthMeasurement for value in measurement_values) or len(
        {value.dimension for value in measurement_values}
    ) != len(measurement_values):
        raise _validation(
            "measurements",
            _("Enter each health measurement at most once."),
        )
    by_dimension = {value.dimension: value for value in measurement_values}
    results = tuple(
        rule.evaluate(by_dimension.get(rule.dimension)) for rule in policy.health_rules
    )
    overall = policy.aggregation.aggregate(results)
    return ProjectHealthEvaluation(
        policy_global_id=policy.policy_global_id,
        policy_version=policy.policy_version,
        policy_snapshot_hash=policy.snapshot_hash,
        dimension_results=results,
        overall_status=overall,
        reason=reason,
        recovery_plan=recovery_plan,
    )


@dataclass(frozen=True, slots=True)
class ProjectTransitionDecision:
    policy_global_id: UUID
    policy_version: int
    policy_snapshot_hash: str
    source_state: ProjectLifecycleState
    action: ProjectControlAction
    target_state: ProjectLifecycleState
    authority_slot: str
    reason: str
    project_version_before: int
    project_version_after: int

    def __post_init__(self) -> None:
        _require_uuid(self.policy_global_id, "policyRef.globalId")
        _require_positive_integer(self.policy_version, "policyRef.version")
        _require_hash(
            self.policy_snapshot_hash,
            "policyRef.snapshotHash",
        )
        _require_enum(self.source_state, ProjectLifecycleState, "sourceState")
        _require_enum(self.action, ProjectControlAction, "action")
        _require_enum(self.target_state, ProjectLifecycleState, "targetState")
        object.__setattr__(
            self,
            "authority_slot",
            _require_key(self.authority_slot, "authoritySlot"),
        )
        object.__setattr__(
            self,
            "reason",
            _require_text(self.reason, "reason", maximum_length=2000),
        )
        _require_positive_integer(
            self.project_version_before,
            "projectVersionBefore",
        )
        if self.project_version_after != self.project_version_before + 1:
            raise _validation(
                "projectVersionAfter",
                _("The Project version must advance by one."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "policyRef": {
                "globalId": str(self.policy_global_id),
                "version": self.policy_version,
                "snapshotHash": self.policy_snapshot_hash,
            },
            "sourceState": self.source_state.value,
            "action": self.action.value,
            "targetState": self.target_state.value,
            "authoritySlot": self.authority_slot,
            "reason": self.reason,
            "projectVersionBefore": self.project_version_before,
            "projectVersionAfter": self.project_version_after,
        }

    @property
    def decision_hash(self) -> str:
        return _canonical_hash(self.canonical_dict())


def evaluate_project_transition(
    *,
    policy: ProjectControlPolicySnapshot,
    binding: ProjectControlBinding,
    current_state: ProjectLifecycleState,
    action: ProjectControlAction,
    actor_member_global_id: UUID,
    actor_user_id: str,
    prerequisite_states: Mapping[
        ProjectPrerequisiteKey,
        PrerequisiteStatus,
    ],
    reason: str,
    current_project_version: int,
    expected_project_version: int,
) -> ProjectTransitionDecision:
    if not isinstance(policy, ProjectControlPolicySnapshot):
        raise PublishedProjectControlPolicyRequired()
    if not isinstance(binding, ProjectControlBinding):
        raise ProjectControlPolicyMismatch()
    state = _require_enum(
        current_state,
        ProjectLifecycleState,
        "currentState",
    )
    selected_action = _require_enum(
        action,
        ProjectControlAction,
        "action",
    )
    reason_value = _require_text(reason, "reason", maximum_length=2000)
    _require_positive_integer(
        current_project_version,
        "currentProjectVersion",
    )
    _require_positive_integer(
        expected_project_version,
        "expectedProjectVersion",
    )
    if current_project_version != expected_project_version:
        raise VersionConflict()
    binding.require_policy(policy)
    rule = policy.transition(state, selected_action)
    binding.require_actor(
        rule.authority_slot,
        actor_member_global_id=actor_member_global_id,
        actor_user_id=actor_user_id,
    )
    if not isinstance(prerequisite_states, Mapping):
        raise _validation(
            "prerequisites",
            _("Enter server-resolved Project prerequisites."),
        )
    supplied_keys = set(prerequisite_states)
    required_keys = set(rule.prerequisites)
    if supplied_keys != required_keys or any(
        not isinstance(key, ProjectPrerequisiteKey)
        or not isinstance(value, PrerequisiteStatus)
        for key, value in prerequisite_states.items()
    ):
        raise _validation(
            "prerequisites",
            _("Enter every server-resolved Project prerequisite exactly once."),
        )
    unavailable = tuple(
        sorted(
            (
                key
                for key in rule.prerequisites
                if prerequisite_states[key] is PrerequisiteStatus.UNAVAILABLE
            ),
            key=lambda value: value.value,
        )
    )
    if unavailable:
        raise ProjectTransitionPrerequisiteUnavailable(unavailable)
    blocked = tuple(
        sorted(
            (
                key
                for key in rule.prerequisites
                if prerequisite_states[key] is PrerequisiteStatus.BLOCKED
            ),
            key=lambda value: value.value,
        )
    )
    if blocked:
        raise ProjectTransitionBlocked(blocked)
    return ProjectTransitionDecision(
        policy_global_id=policy.policy_global_id,
        policy_version=policy.policy_version,
        policy_snapshot_hash=policy.snapshot_hash,
        source_state=rule.source_state,
        action=rule.action,
        target_state=rule.target_state,
        authority_slot=rule.authority_slot,
        reason=reason_value,
        project_version_before=current_project_version,
        project_version_after=current_project_version + 1,
    )
