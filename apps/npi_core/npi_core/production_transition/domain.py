from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID, uuid5

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.project.domain import ProjectType

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


PRODUCTION_TRANSITION_SCHEMA_VERSION = 1
MAX_POLICY_REQUIREMENTS = 100
MAX_RECEIVING_GROUPS = 100
MAX_ACKNOWLEDGEMENT_SLOTS = 100
MAX_POLICY_APPLICABILITY_REFERENCES = 1_000
MAX_ACKNOWLEDGEMENT_SLOT_ROLE_KEYS = 100
MAX_PROJECT_CUSTOMER_REFERENCES = 1_000
MAX_MANIFEST_SOURCES = 1_000
MAX_UNRESOLVED_ACTIONS = 10_000
MAX_OBSERVATION_REFERENCES = 1_000

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ProductionTransitionPolicyImmutable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PRODUCTION_TRANSITION_POLICY_IMMUTABLE",
            _("A published Production Transition Policy version cannot be changed."),
        )


class ProductionTransitionPolicyPublishedRequired(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "PRODUCTION_TRANSITION_POLICY_PUBLISHED_REQUIRED",
            _("Publish the current Production Transition Policy version first."),
        )


class ProductionTransitionVersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PRODUCTION_TRANSITION_VERSION_CONFLICT",
            _("The production transition record was changed by another user."),
        )


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise _problem(path, _("Enter a valid global ID."))
    return value


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _problem(path, _("Enter a non-negative integer."))
    return value


def _text(
    value: object,
    path: str,
    maximum: int,
    *,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum or (pattern and pattern.fullmatch(normalized) is None):
        raise _problem(path, _("Enter a valid value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _email(value: object, path: str) -> str:
    normalized = _text(value, path, 254).casefold()
    if _EMAIL.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid user ID."))
    return normalized


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _date(value: object, path: str) -> date:
    if type(value) is not date:
        raise _problem(path, _("Enter a valid date."))
    return value


def _optional_date(value: object, path: str) -> date | None:
    return None if value is None else _date(value, path)


def _datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a valid timestamp."))
    return value.astimezone(UTC)


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool):
        raise _problem(path, _("Enter a valid decimal value."))
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _problem(path, _("Enter a valid decimal value.")) from None
    if not normalized.is_finite():
        raise _problem(path, _("Enter a finite decimal value."))
    return normalized.normalize()


def _enum(value: object, expected: type[StrEnum], path: str):
    if not isinstance(value, expected):
        raise _problem(path, _("Select a supported value."))
    return value


def _tuple_of(value: object, expected: type, path: str, maximum: int) -> tuple:
    if not isinstance(value, (tuple, list)):
        raise _problem(path, _("Enter a valid list."))
    result = tuple(value)
    if len(result) > maximum or any(not isinstance(item, expected) for item in result):
        raise _problem(path, _("Enter a valid list."))
    return result


def _unique(values: Sequence[object], path: str) -> None:
    if len(set(values)) != len(values):
        raise _problem(path, _("Values must be unique."))


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class PolicyPublicationState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class AcknowledgementDirection(StrEnum):
    SENDER = "sender"
    RECEIVER = "receiver"


class HandoverSourceKind(StrEnum):
    READINESS_INSTANCE_REVISION = "readiness_instance_revision"
    DOMAIN_WORK_ITEM = "domain_work_item"
    RELEASED_DOCUMENT = "released_document"
    RELEASE_BASELINE = "release_baseline"
    FILE_REVISION = "file_revision"
    TOOLING_CAPACITY_SCENARIO = "tooling_capacity_scenario"
    TRIAL_DEFECT_REVISION = "trial_defect_revision"
    TRIAL_REVIEW_REFERENCE = "trial_review_reference"
    TRIAL_CONCLUSION = "trial_conclusion"


CLOSED_HANDOVER_SOURCE_KINDS = tuple(HandoverSourceKind)


class WorkItemKind(StrEnum):
    ACTION = "action"
    DECISION_REQUEST = "decision_request"
    ISSUE = "issue"
    RISK = "risk"


UNRESOLVED_ACTION_SELECTOR: Mapping[str, object] = MappingProxyType(
    {
        "mode": "all_non_terminal",
        "kinds": tuple(value.value for value in WorkItemKind),
    }
)


class ObservationProviderKind(StrEnum):
    ACTUAL_SOP = "actual_sop"
    FIRST_BATCH_YIELD = "first_batch_yield"
    CUSTOMER_COMPLAINT = "customer_complaint"
    PRODUCTION_CYCLE_TIME = "production_cycle_time"
    TOOLING_STABILITY = "tooling_stability"


MANDATORY_OBSERVATION_PROVIDER_KINDS = tuple(ObservationProviderKind)


class ObservationProviderState(StrEnum):
    UNAVAILABLE = "unavailable"


class ObservationState(StrEnum):
    NOT_EVALUABLE = "not_evaluable"


class ObservationReferenceUsage(StrEnum):
    CONTEXT = "context"
    RETROSPECTIVE = "retrospective"


class MetricComparator(StrEnum):
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EQUAL = "equal"


class TechnicalDisposition(StrEnum):
    NOT_EVALUABLE = "not_evaluable"
    WITHIN_RULE = "within_rule"
    OUTSIDE_RULE = "outside_rule"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class ExactVersionReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "reference.globalId"))
        object.__setattr__(self, "version", _positive(self.version, "reference.version"))
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "reference.snapshotHash"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ProductionTransitionApplicability:
    project_types: tuple[ProjectType, ...]
    project_global_ids: tuple[UUID, ...] = ()
    customer_reference_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        project_types = _tuple_of(self.project_types, ProjectType, "applicability.projectTypes", 20)
        if not project_types:
            raise _problem("applicability.projectTypes", _("Select at least one Project type."))
        _unique(project_types, "applicability.projectTypes")
        raw_project_ids = _tuple_of(
            self.project_global_ids,
            UUID,
            "applicability.projectGlobalIds",
            MAX_POLICY_APPLICABILITY_REFERENCES,
        )
        project_ids = tuple(
            sorted(
                (
                    _uuid(value, "applicability.projectGlobalIds")
                    for value in raw_project_ids
                ),
                key=str,
            )
        )
        raw_customer_keys = _tuple_of(
            self.customer_reference_keys,
            str,
            "applicability.customerReferenceKeys",
            MAX_POLICY_APPLICABILITY_REFERENCES,
        )
        customer_keys = tuple(
            sorted(
                _text(value, "applicability.customerReferenceKeys", 256)
                for value in raw_customer_keys
            )
        )
        _unique(project_ids, "applicability.projectGlobalIds")
        _unique(customer_keys, "applicability.customerReferenceKeys")
        object.__setattr__(self, "project_types", tuple(sorted(project_types, key=lambda value: value.value)))
        object.__setattr__(self, "project_global_ids", project_ids)
        object.__setattr__(self, "customer_reference_keys", customer_keys)

    def applies_to(self, project: ProjectTransitionSnapshot) -> bool:
        return (
            project.project_type in self.project_types
            and (not self.project_global_ids or project.global_id in self.project_global_ids)
            and (
                not self.customer_reference_keys
                or bool(set(self.customer_reference_keys) & set(project.customer_reference_keys))
            )
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "projectTypes": [value.value for value in self.project_types],
            "projectGlobalIds": [str(value) for value in self.project_global_ids],
            "customerReferenceKeys": list(self.customer_reference_keys),
        }


@dataclass(frozen=True, slots=True)
class ReceivingGroupDefinition:
    key: str
    title: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _text(self.key, "receivingGroups.key", 128, pattern=_KEY))
        object.__setattr__(self, "title", _text(self.title, "receivingGroups.title", 200))

    def snapshot_payload(self) -> dict[str, object]:
        return {"key": self.key, "title": self.title}


@dataclass(frozen=True, slots=True)
class AcknowledgementSlotDefinition:
    key: str
    group_key: str
    direction: AcknowledgementDirection
    allowed_project_role_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _text(self.key, "acknowledgementSlots.key", 128, pattern=_KEY))
        object.__setattr__(
            self,
            "group_key",
            _text(self.group_key, "acknowledgementSlots.groupKey", 128, pattern=_KEY),
        )
        _enum(self.direction, AcknowledgementDirection, "acknowledgementSlots.direction")
        raw_role_keys = _tuple_of(
            self.allowed_project_role_keys,
            str,
            "acknowledgementSlots.allowedProjectRoleKeys",
            MAX_ACKNOWLEDGEMENT_SLOT_ROLE_KEYS,
        )
        role_keys = tuple(
            sorted(
                _text(value, "acknowledgementSlots.allowedProjectRoleKeys", 128, pattern=_KEY)
                for value in raw_role_keys
            )
        )
        if not role_keys:
            raise _problem(
                "acknowledgementSlots.allowedProjectRoleKeys",
                _("Select at least one Project role."),
            )
        _unique(role_keys, "acknowledgementSlots.allowedProjectRoleKeys")
        object.__setattr__(self, "allowed_project_role_keys", role_keys)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "groupKey": self.group_key,
            "direction": self.direction.value,
            "allowedProjectRoleKeys": list(self.allowed_project_role_keys),
        }


@dataclass(frozen=True, slots=True)
class HandoverObjectRequirement:
    key: str
    accepted_source_kinds: tuple[HandoverSourceKind, ...]
    manifest_role: str
    minimum_count: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _text(self.key, "handoverRequirements.key", 128, pattern=_KEY))
        kinds = _tuple_of(
            self.accepted_source_kinds,
            HandoverSourceKind,
            "handoverRequirements.acceptedSourceKinds",
            len(HandoverSourceKind),
        )
        if not kinds:
            raise _problem(
                "handoverRequirements.acceptedSourceKinds",
                _("Select at least one source kind."),
            )
        _unique(kinds, "handoverRequirements.acceptedSourceKinds")
        object.__setattr__(self, "accepted_source_kinds", tuple(sorted(kinds, key=lambda value: value.value)))
        object.__setattr__(
            self,
            "manifest_role",
            _text(self.manifest_role, "handoverRequirements.manifestRole", 128, pattern=_KEY),
        )
        count = _positive(self.minimum_count, "handoverRequirements.minimumCount")
        if count > MAX_MANIFEST_SOURCES:
            raise _problem(
                "handoverRequirements.minimumCount",
                _("Enter a supported object count."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "acceptedSourceKinds": [value.value for value in self.accepted_source_kinds],
            "manifestRole": self.manifest_role,
            "minimumCount": self.minimum_count,
        }


@dataclass(frozen=True, slots=True)
class ObservationSourceRule:
    provider_kind: ObservationProviderKind
    unit: str | None = None
    comparator: MetricComparator | None = None
    threshold: Decimal | None = None
    allowed_dispositions: tuple[TechnicalDisposition, ...] = ()

    def __post_init__(self) -> None:
        _enum(self.provider_kind, ObservationProviderKind, "observationSourceRules.providerKind")
        if self.provider_kind is ObservationProviderKind.ACTUAL_SOP:
            if any(value is not None for value in (self.unit, self.comparator, self.threshold)):
                raise _problem(
                    "observationSourceRules.actualSop",
                    _("Actual SOP cannot define a metric threshold."),
                )
        else:
            object.__setattr__(self, "unit", _text(self.unit, "observationSourceRules.unit", 32))
            _enum(self.comparator, MetricComparator, "observationSourceRules.comparator")
            object.__setattr__(self, "threshold", _decimal(self.threshold, "observationSourceRules.threshold"))
        dispositions = _tuple_of(
            self.allowed_dispositions,
            TechnicalDisposition,
            "observationSourceRules.allowedDispositions",
            len(TechnicalDisposition),
        )
        if not dispositions:
            raise _problem(
                "observationSourceRules.allowedDispositions",
                _("Select at least one technical disposition."),
            )
        if TechnicalDisposition.NOT_EVALUABLE not in dispositions:
            raise _problem(
                "observationSourceRules.allowedDispositions",
                _("The not-evaluable disposition is required."),
            )
        _unique(dispositions, "observationSourceRules.allowedDispositions")
        object.__setattr__(self, "allowed_dispositions", tuple(sorted(dispositions, key=lambda value: value.value)))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "providerKind": self.provider_kind.value,
            "unit": self.unit,
            "comparator": self.comparator.value if self.comparator is not None else None,
            "threshold": _decimal_text(self.threshold) if self.threshold is not None else None,
            "allowedDispositions": [value.value for value in self.allowed_dispositions],
        }


@dataclass(frozen=True, slots=True)
class ProductionTransitionPolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    tenant_id: str
    policy_code: str
    policy_version: int
    optimistic_version: int
    title: str
    publication_state: PolicyPublicationState
    prior_version_ref: ExactVersionReference | None
    applicability: ProductionTransitionApplicability
    receiving_groups: tuple[ReceivingGroupDefinition, ...]
    acknowledgement_slots: tuple[AcknowledgementSlotDefinition, ...]
    handover_requirements: tuple[HandoverObjectRequirement, ...]
    observation_source_rules: tuple[ObservationSourceRule, ...]
    observation_window_days: int
    changed_by_user_id: str
    changed_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        policy_id = _uuid(self.policy_global_id, "policyGlobalId")
        version = _positive(self.policy_version, "policyVersion")
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        expected_id = uuid5(policy_id, f"npi-production-transition-policy-version:{version}")
        if self.global_id != expected_id:
            raise _problem("globalId", _("The policy version identifier is not canonical."))
        object.__setattr__(
            self,
            "tenant_id",
            _text(self.tenant_id, "tenantId", 128, pattern=_TENANT),
        )
        object.__setattr__(self, "policy_code", _text(self.policy_code, "policyCode", 64, pattern=_CODE))
        _positive(self.optimistic_version, "optimisticVersion")
        object.__setattr__(self, "title", _text(self.title, "title", 200))
        _enum(self.publication_state, PolicyPublicationState, "publicationState")
        if version == 1 and self.prior_version_ref is not None:
            raise _problem(
                "priorVersionRef",
                _("The first policy version cannot have a predecessor."),
            )
        if version > 1:
            if not isinstance(self.prior_version_ref, ExactVersionReference):
                raise _problem(
                    "priorVersionRef",
                    _("Select the exact preceding published policy version."),
                )
            if self.prior_version_ref.version != version - 1:
                raise _problem("priorVersionRef.version", _("Policy versions must be contiguous."))
            expected_prior_id = uuid5(
                policy_id,
                f"npi-production-transition-policy-version:{version - 1}",
            )
            if self.prior_version_ref.global_id != expected_prior_id:
                raise _problem(
                    "priorVersionRef.globalId",
                    _("Select the exact preceding version from this policy stream."),
                )
        if not isinstance(self.applicability, ProductionTransitionApplicability):
            raise _problem("applicability", _("Enter valid Project applicability."))
        groups = _tuple_of(self.receiving_groups, ReceivingGroupDefinition, "receivingGroups", MAX_RECEIVING_GROUPS)
        slots = _tuple_of(
            self.acknowledgement_slots,
            AcknowledgementSlotDefinition,
            "acknowledgementSlots",
            MAX_ACKNOWLEDGEMENT_SLOTS,
        )
        requirements = _tuple_of(
            self.handover_requirements,
            HandoverObjectRequirement,
            "handoverRequirements",
            MAX_POLICY_REQUIREMENTS,
        )
        rules = _tuple_of(
            self.observation_source_rules,
            ObservationSourceRule,
            "observationSourceRules",
            len(ObservationProviderKind),
        )
        _unique(tuple(value.key.casefold() for value in groups), "receivingGroups.key")
        _unique(tuple(value.key.casefold() for value in slots), "acknowledgementSlots.key")
        _unique(tuple(value.key.casefold() for value in requirements), "handoverRequirements.key")
        _unique(tuple(value.provider_kind for value in rules), "observationSourceRules.providerKind")
        group_keys = {value.key for value in groups}
        if any(value.group_key not in group_keys for value in slots):
            raise _problem(
                "acknowledgementSlots.groupKey",
                _("Select a receiving group defined by this policy."),
            )
        provider_kinds = {value.provider_kind for value in rules}
        if provider_kinds != set(MANDATORY_OBSERVATION_PROVIDER_KINDS):
            raise _problem(
                "observationSourceRules",
                _("Define all five mandatory observation providers exactly once."),
            )
        _positive(self.observation_window_days, "observationWindowDays")
        if self.observation_window_days > 3_650:
            raise _problem("observationWindowDays", _("Enter a supported observation window."))
        object.__setattr__(
            self,
            "changed_by_user_id",
            _email(self.changed_by_user_id, "changedByUserId"),
        )
        object.__setattr__(self, "changed_at", _datetime(self.changed_at, "changedAt"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128, pattern=_KEY))
        object.__setattr__(self, "receiving_groups", groups)
        object.__setattr__(self, "acknowledgement_slots", slots)
        object.__setattr__(self, "handover_requirements", requirements)
        object.__setattr__(
            self,
            "observation_source_rules",
            tuple(sorted(rules, key=lambda value: value.provider_kind.value)),
        )
        if self.publication_state is PolicyPublicationState.PUBLISHED:
            self._require_publishable()

    @classmethod
    def create_draft(
        cls,
        *,
        policy_global_id: UUID,
        tenant_id: str,
        policy_code: str,
        title: str,
        applicability: ProductionTransitionApplicability,
        receiving_groups: tuple[ReceivingGroupDefinition, ...],
        acknowledgement_slots: tuple[AcknowledgementSlotDefinition, ...],
        handover_requirements: tuple[HandoverObjectRequirement, ...],
        observation_source_rules: tuple[ObservationSourceRule, ...],
        observation_window_days: int,
        changed_by_user_id: str,
        changed_at: datetime,
        request_id: UUID,
        trace_id: str,
    ) -> ProductionTransitionPolicyVersion:
        policy_id = _uuid(policy_global_id, "policyGlobalId")
        return cls(
            global_id=uuid5(policy_id, "npi-production-transition-policy-version:1"),
            policy_global_id=policy_id,
            tenant_id=tenant_id,
            policy_code=policy_code,
            policy_version=1,
            optimistic_version=1,
            title=title,
            publication_state=PolicyPublicationState.DRAFT,
            prior_version_ref=None,
            applicability=applicability,
            receiving_groups=receiving_groups,
            acknowledgement_slots=acknowledgement_slots,
            handover_requirements=handover_requirements,
            observation_source_rules=observation_source_rules,
            observation_window_days=observation_window_days,
            changed_by_user_id=changed_by_user_id,
            changed_at=changed_at,
            request_id=request_id,
            trace_id=trace_id,
        )

    def edit_draft(
        self,
        *,
        expected_version: int,
        changed_by_user_id: str,
        changed_at: datetime,
        request_id: UUID,
        trace_id: str,
        **changes: object,
    ) -> ProductionTransitionPolicyVersion:
        if self.publication_state is PolicyPublicationState.PUBLISHED:
            raise ProductionTransitionPolicyImmutable()
        if expected_version != self.optimistic_version:
            raise ProductionTransitionVersionConflict()
        allowed = {
            "title",
            "applicability",
            "receiving_groups",
            "acknowledgement_slots",
            "handover_requirements",
            "observation_source_rules",
            "observation_window_days",
        }
        if set(changes) - allowed:
            raise _problem("policy", _("Enter only supported policy changes."))
        return replace(
            self,
            optimistic_version=self.optimistic_version + 1,
            changed_by_user_id=changed_by_user_id,
            changed_at=changed_at,
            request_id=request_id,
            trace_id=trace_id,
            **changes,
        )

    def publish(
        self,
        *,
        expected_version: int,
        changed_by_user_id: str,
        changed_at: datetime,
        request_id: UUID,
        trace_id: str,
    ) -> ProductionTransitionPolicyVersion:
        if self.publication_state is PolicyPublicationState.PUBLISHED:
            raise ProductionTransitionPolicyImmutable()
        if expected_version != self.optimistic_version:
            raise ProductionTransitionVersionConflict()
        self._require_publishable()
        return replace(
            self,
            optimistic_version=self.optimistic_version + 1,
            publication_state=PolicyPublicationState.PUBLISHED,
            changed_by_user_id=changed_by_user_id,
            changed_at=changed_at,
            request_id=request_id,
            trace_id=trace_id,
        )

    def next_draft(
        self,
        *,
        changed_by_user_id: str,
        changed_at: datetime,
        request_id: UUID,
        trace_id: str,
    ) -> ProductionTransitionPolicyVersion:
        if self.publication_state is not PolicyPublicationState.PUBLISHED:
            raise ProductionTransitionPolicyPublishedRequired()
        version = self.policy_version + 1
        return ProductionTransitionPolicyVersion(
            global_id=uuid5(self.policy_global_id, f"npi-production-transition-policy-version:{version}"),
            policy_global_id=self.policy_global_id,
            tenant_id=self.tenant_id,
            policy_code=self.policy_code,
            policy_version=version,
            optimistic_version=1,
            title=self.title,
            publication_state=PolicyPublicationState.DRAFT,
            prior_version_ref=ExactVersionReference(self.global_id, self.policy_version, self.snapshot_hash),
            applicability=self.applicability,
            receiving_groups=self.receiving_groups,
            acknowledgement_slots=self.acknowledgement_slots,
            handover_requirements=self.handover_requirements,
            observation_source_rules=self.observation_source_rules,
            observation_window_days=self.observation_window_days,
            changed_by_user_id=changed_by_user_id,
            changed_at=changed_at,
            request_id=request_id,
            trace_id=trace_id,
        )

    def _require_publishable(self) -> None:
        if not self.receiving_groups or not self.acknowledgement_slots or not self.handover_requirements:
            raise _problem(
                "policy",
                _(
                    "Add receiving groups, acknowledgement slots, and handover requirements before publishing."
                ),
            )
        if sum(value.minimum_count for value in self.handover_requirements) > MAX_MANIFEST_SOURCES:
            raise _problem(
                "handoverRequirements.minimumCount",
                _("Enter a supported object count."),
            )
        directions = {value.direction for value in self.acknowledgement_slots}
        if not {AcknowledgementDirection.SENDER, AcknowledgementDirection.RECEIVER}.issubset(directions):
            raise _problem(
                "acknowledgementSlots",
                _("Define at least one sender slot and one receiver slot."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": PRODUCTION_TRANSITION_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "policyGlobalId": str(self.policy_global_id),
            "tenantId": self.tenant_id,
            "policyCode": self.policy_code,
            "policyVersion": self.policy_version,
            "versionKeyHash": self.version_key_hash,
            "optimisticVersion": self.optimistic_version,
            "title": self.title,
            "publicationState": self.publication_state.value,
            "priorVersionRef": self.prior_version_ref.snapshot_payload() if self.prior_version_ref else None,
            "applicability": self.applicability.snapshot_payload(),
            "receivingGroups": [value.snapshot_payload() for value in self.receiving_groups],
            "acknowledgementSlots": [value.snapshot_payload() for value in self.acknowledgement_slots],
            "handoverRequirements": [value.snapshot_payload() for value in self.handover_requirements],
            "unresolvedActionSelector": {
                "mode": UNRESOLVED_ACTION_SELECTOR["mode"],
                "kinds": list(UNRESOLVED_ACTION_SELECTOR["kinds"]),
            },
            "observationSourceRules": [value.snapshot_payload() for value in self.observation_source_rules],
            "observationWindowDays": self.observation_window_days,
            "authorityBoundary": "npi_technical_configuration_only",
            "changedByUserId": self.changed_by_user_id,
            "changedAt": _utc(self.changed_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "tenantId": self.tenant_id,
                "policyGlobalId": str(self.policy_global_id),
                "policyVersion": self.policy_version,
            }
        )


def validate_policy_persistence_transition(
    previous: ProductionTransitionPolicyVersion | None,
    current: ProductionTransitionPolicyVersion,
) -> None:
    if not isinstance(current, ProductionTransitionPolicyVersion):
        raise _problem(
            "policy",
            _("Production Transition Policy fields do not match the exact snapshot."),
        )
    if previous is None:
        if (
            current.publication_state is not PolicyPublicationState.DRAFT
            or current.optimistic_version != 1
        ):
            raise _problem(
                "optimisticVersion",
                _("Optimistic Version must advance by one."),
            )
        return
    if not isinstance(previous, ProductionTransitionPolicyVersion):
        raise _problem(
            "policy",
            _("Production Transition Policy fields do not match the exact snapshot."),
        )
    if previous.publication_state is PolicyPublicationState.PUBLISHED:
        raise ProductionTransitionPolicyImmutable()
    if current.publication_state is PolicyPublicationState.DRAFT:
        expected = previous.edit_draft(
            expected_version=previous.optimistic_version,
            changed_by_user_id=current.changed_by_user_id,
            changed_at=current.changed_at,
            request_id=current.request_id,
            trace_id=current.trace_id,
            title=current.title,
            applicability=current.applicability,
            receiving_groups=current.receiving_groups,
            acknowledgement_slots=current.acknowledgement_slots,
            handover_requirements=current.handover_requirements,
            observation_source_rules=current.observation_source_rules,
            observation_window_days=current.observation_window_days,
        )
    else:
        expected = previous.publish(
            expected_version=previous.optimistic_version,
            changed_by_user_id=current.changed_by_user_id,
            changed_at=current.changed_at,
            request_id=current.request_id,
            trace_id=current.trace_id,
        )
    if current != expected:
        raise _problem(
            "policy",
            _("Production Transition Policy fields do not match the exact snapshot."),
        )


@dataclass(frozen=True, slots=True)
class ProjectTransitionSnapshot:
    global_id: UUID
    tenant_id: str
    optimistic_version: int
    business_code: str
    title: str
    project_type: ProjectType
    owner_user_id: str
    target_sop_date: date | None
    lifecycle_state: str
    template_ref: ExactVersionReference
    work_policy_ref: ExactVersionReference
    customer_reference_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "project.globalId"))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "project.tenantId", 128, pattern=_TENANT))
        _positive(self.optimistic_version, "project.optimisticVersion")
        object.__setattr__(self, "business_code", _text(self.business_code, "project.businessCode", 64, pattern=_CODE))
        object.__setattr__(self, "title", _text(self.title, "project.title", 200))
        if not isinstance(self.project_type, ProjectType):
            raise _problem("project.projectType", _("Select a supported Project type."))
        object.__setattr__(self, "owner_user_id", _email(self.owner_user_id, "project.ownerUserId"))
        object.__setattr__(self, "target_sop_date", _optional_date(self.target_sop_date, "project.targetSopDate"))
        object.__setattr__(
            self,
            "lifecycle_state",
            _text(self.lifecycle_state, "project.lifecycleState", 64, pattern=_KEY),
        )
        if not isinstance(self.template_ref, ExactVersionReference):
            raise _problem("project.templateRef", _("Select an exact Project Template version."))
        if not isinstance(self.work_policy_ref, ExactVersionReference):
            raise _problem(
                "project.workPolicyRef",
                _("Select an exact Project Work Policy version."),
            )
        raw_customer_keys = _tuple_of(
            self.customer_reference_keys,
            str,
            "project.customerReferenceKeys",
            MAX_PROJECT_CUSTOMER_REFERENCES,
        )
        customer_keys = tuple(
            sorted(
                _text(value, "project.customerReferenceKeys", 256)
                for value in raw_customer_keys
            )
        )
        _unique(customer_keys, "project.customerReferenceKeys")
        object.__setattr__(self, "customer_reference_keys", customer_keys)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "optimisticVersion": self.optimistic_version,
            "businessCode": self.business_code,
            "title": self.title,
            "projectType": self.project_type.value,
            "ownerUserId": self.owner_user_id,
            "targetSopDate": self.target_sop_date.isoformat() if self.target_sop_date else None,
            "targetSopState": "planned_only",
            "lifecycleState": self.lifecycle_state,
            "templateRef": self.template_ref.snapshot_payload(),
            "workPolicyRef": self.work_policy_ref.snapshot_payload(),
            "customerReferenceKeys": list(self.customer_reference_keys),
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class ProjectMemberSnapshot:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    user_id: str
    effective_from: date
    effective_to: date | None
    optimistic_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "member.globalId"))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "member.tenantId", 128, pattern=_TENANT))
        object.__setattr__(self, "project_global_id", _uuid(self.project_global_id, "member.projectGlobalId"))
        object.__setattr__(self, "user_id", _email(self.user_id, "member.userId"))
        object.__setattr__(self, "effective_from", _date(self.effective_from, "member.effectiveFrom"))
        object.__setattr__(self, "effective_to", _optional_date(self.effective_to, "member.effectiveTo"))
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise _problem("member.effectiveTo", _("The member effectivity interval is invalid."))
        _positive(self.optimistic_version, "member.optimisticVersion")

    def is_effective(self, on_date: date) -> bool:
        return self.effective_from <= on_date and (self.effective_to is None or on_date <= self.effective_to)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "userId": self.user_id,
            "effectiveFrom": self.effective_from.isoformat(),
            "effectiveTo": self.effective_to.isoformat() if self.effective_to else None,
            "optimisticVersion": self.optimistic_version,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class ProjectRoleSnapshot:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    member_global_id: UUID
    role_key: str
    effective_from: date
    effective_to: date | None
    optimistic_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "role.globalId"))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "role.tenantId", 128, pattern=_TENANT))
        object.__setattr__(self, "project_global_id", _uuid(self.project_global_id, "role.projectGlobalId"))
        object.__setattr__(self, "member_global_id", _uuid(self.member_global_id, "role.memberGlobalId"))
        object.__setattr__(self, "role_key", _text(self.role_key, "role.roleKey", 128, pattern=_KEY))
        object.__setattr__(self, "effective_from", _date(self.effective_from, "role.effectiveFrom"))
        object.__setattr__(self, "effective_to", _optional_date(self.effective_to, "role.effectiveTo"))
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise _problem("role.effectiveTo", _("The role effectivity interval is invalid."))
        _positive(self.optimistic_version, "role.optimisticVersion")

    def is_effective(self, on_date: date) -> bool:
        return self.effective_from <= on_date and (self.effective_to is None or on_date <= self.effective_to)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "memberGlobalId": str(self.member_global_id),
            "roleKey": self.role_key,
            "effectiveFrom": self.effective_from.isoformat(),
            "effectiveTo": self.effective_to.isoformat() if self.effective_to else None,
            "optimisticVersion": self.optimistic_version,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


@dataclass(frozen=True, slots=True)
class FrozenAcknowledgementSlot:
    slot_key: str
    group_key: str
    direction: AcknowledgementDirection
    member: ProjectMemberSnapshot
    role: ProjectRoleSnapshot

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_key", _text(self.slot_key, "slots.slotKey", 128, pattern=_KEY))
        object.__setattr__(self, "group_key", _text(self.group_key, "slots.groupKey", 128, pattern=_KEY))
        _enum(self.direction, AcknowledgementDirection, "slots.direction")
        if not isinstance(self.member, ProjectMemberSnapshot) or not isinstance(self.role, ProjectRoleSnapshot):
            raise _problem("slots", _("Select exact Project member and role assignments."))
        if (
            self.member.tenant_id != self.role.tenant_id
            or self.member.project_global_id != self.role.project_global_id
            or self.member.global_id != self.role.member_global_id
        ):
            raise _problem("slots", _("The Project member and role assignment do not match."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "slotKey": self.slot_key,
            "groupKey": self.group_key,
            "direction": self.direction.value,
            "member": self.member.snapshot_payload(),
            "memberSnapshotHash": self.member.snapshot_hash,
            "role": self.role.snapshot_payload(),
            "roleSnapshotHash": self.role.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class HandoverSourceReference:
    requirement_key: str
    kind: HandoverSourceKind
    global_id: UUID
    source_version: int
    snapshot_hash: str
    role: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requirement_key",
            _text(self.requirement_key, "manifest.requirementKey", 128, pattern=_KEY),
        )
        _enum(self.kind, HandoverSourceKind, "manifest.kind")
        object.__setattr__(self, "global_id", _uuid(self.global_id, "manifest.globalId"))
        _positive(self.source_version, "manifest.sourceVersion")
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "manifest.snapshotHash"))
        object.__setattr__(self, "role", _text(self.role, "manifest.role", 128, pattern=_KEY))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "requirementKey": self.requirement_key,
            "kind": self.kind.value,
            "globalId": str(self.global_id),
            "sourceVersion": self.source_version,
            "snapshotHash": self.snapshot_hash,
            "role": self.role,
        }


@dataclass(frozen=True, slots=True)
class ObservationSourceReference:
    kind: HandoverSourceKind
    global_id: UUID
    source_version: int
    snapshot_hash: str
    usage: ObservationReferenceUsage

    def __post_init__(self) -> None:
        _enum(self.kind, HandoverSourceKind, "observationReferences.kind")
        object.__setattr__(self, "global_id", _uuid(self.global_id, "observationReferences.globalId"))
        _positive(self.source_version, "observationReferences.sourceVersion")
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "observationReferences.snapshotHash"),
        )
        _enum(self.usage, ObservationReferenceUsage, "observationReferences.usage")

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "globalId": str(self.global_id),
            "sourceVersion": self.source_version,
            "snapshotHash": self.snapshot_hash,
            "usage": self.usage.value,
        }


@dataclass(frozen=True, slots=True)
class UnresolvedActionSnapshot:
    global_id: UUID
    source_version: int
    snapshot_hash: str
    kind: WorkItemKind
    state: str
    owner_user_id: str
    due_date: date

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "unresolvedActions.globalId"))
        _positive(self.source_version, "unresolvedActions.sourceVersion")
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "unresolvedActions.snapshotHash"))
        _enum(self.kind, WorkItemKind, "unresolvedActions.kind")
        object.__setattr__(self, "state", _text(self.state, "unresolvedActions.state", 64, pattern=_KEY))
        object.__setattr__(self, "owner_user_id", _email(self.owner_user_id, "unresolvedActions.ownerUserId"))
        object.__setattr__(self, "due_date", _date(self.due_date, "unresolvedActions.dueDate"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "sourceVersion": self.source_version,
            "snapshotHash": self.snapshot_hash,
            "kind": self.kind.value,
            "state": self.state,
            "ownerUserId": self.owner_user_id,
            "dueDate": self.due_date.isoformat(),
        }


def _validate_slot_binding(
    binding: FrozenAcknowledgementSlot,
    definition: AcknowledgementSlotDefinition,
    project: ProjectTransitionSnapshot,
    effective_date: date,
    enabled_user_ids: frozenset[str],
) -> None:
    if (
        binding.slot_key != definition.key
        or binding.group_key != definition.group_key
        or binding.direction is not definition.direction
        or binding.role.role_key not in definition.allowed_project_role_keys
    ):
        raise _problem(
            "slots",
            _("The frozen acknowledgement slot does not satisfy the policy."),
        )
    if (
        binding.member.tenant_id != project.tenant_id
        or binding.member.project_global_id != project.global_id
        or binding.member.user_id not in enabled_user_ids
        or not binding.member.is_effective(effective_date)
        or not binding.role.is_effective(effective_date)
    ):
        raise _problem(
            "slots",
            _(
                "The acknowledgement member and role must be enabled and currently effective for this Project."
            ),
        )


@dataclass(frozen=True, slots=True)
class HandoverPackageRevision:
    global_id: UUID
    handover_global_id: UUID
    handover_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    tenant_id: str
    project: ProjectTransitionSnapshot
    policy_ref: ExactVersionReference
    readiness_ref: ExactVersionReference | None
    slots: tuple[FrozenAcknowledgementSlot, ...]
    manifest: tuple[HandoverSourceReference, ...]
    unresolved_actions: tuple[UnresolvedActionSnapshot, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        stream_id = _uuid(self.handover_global_id, "handoverGlobalId")
        version = _positive(self.handover_version, "handoverVersion")
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if self.global_id != uuid5(stream_id, f"npi-handover-package-revision:{version}"):
            raise _problem(
                "globalId",
                _("The handover package revision identifier is not canonical."),
            )
        predecessor_id = _optional_uuid(self.predecessor_global_id, "predecessorGlobalId")
        predecessor_hash = _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash")
        if version == 1 and (predecessor_id is not None or predecessor_hash is not None):
            raise _problem(
                "predecessorGlobalId",
                _("The first handover revision cannot have a predecessor."),
            )
        if version > 1 and (predecessor_id is None or predecessor_hash is None):
            raise _problem(
                "predecessorGlobalId",
                _("Select the exact preceding handover revision."),
            )
        if version > 1 and predecessor_id != uuid5(
            stream_id,
            f"npi-handover-package-revision:{version - 1}",
        ):
            raise _problem(
                "predecessorGlobalId",
                _("Select the exact preceding revision from this handover stream."),
            )
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128, pattern=_TENANT))
        if not isinstance(self.project, ProjectTransitionSnapshot) or self.project.tenant_id != self.tenant_id:
            raise _problem("project", _("Select an exact same-tenant Project snapshot."))
        if not isinstance(self.policy_ref, ExactVersionReference):
            raise _problem("policyRef", _("Select an exact published policy version."))
        if self.readiness_ref is not None and not isinstance(self.readiness_ref, ExactVersionReference):
            raise _problem("readinessRef", _("Select an exact readiness-instance revision."))
        slots = _tuple_of(self.slots, FrozenAcknowledgementSlot, "slots", MAX_ACKNOWLEDGEMENT_SLOTS)
        manifest = _tuple_of(self.manifest, HandoverSourceReference, "manifest", MAX_MANIFEST_SOURCES)
        actions = _tuple_of(
            self.unresolved_actions,
            UnresolvedActionSnapshot,
            "unresolvedActions",
            MAX_UNRESOLVED_ACTIONS,
        )
        _unique(tuple(value.slot_key.casefold() for value in slots), "slots.slotKey")
        _unique(tuple((value.kind, value.global_id) for value in manifest), "manifest")
        _unique(tuple(value.global_id for value in actions), "unresolvedActions.globalId")
        if tuple(sorted(actions, key=lambda value: str(value.global_id))) != actions:
            raise _problem(
                "unresolvedActions",
                _("Unresolved actions must use canonical UUID order."),
            )
        if self.readiness_ref is not None and not any(
            value.kind is HandoverSourceKind.READINESS_INSTANCE_REVISION
            and value.global_id == self.readiness_ref.global_id
            and value.source_version == self.readiness_ref.version
            and value.snapshot_hash == self.readiness_ref.snapshot_hash
            for value in manifest
        ):
            raise _problem(
                "readinessRef",
                _("The readiness reference must match an exact manifest source."),
            )
        object.__setattr__(self, "slots", slots)
        object.__setattr__(self, "manifest", manifest)
        object.__setattr__(self, "unresolved_actions", actions)
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1000))
        object.__setattr__(self, "created_by_user_id", _email(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128, pattern=_KEY))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": PRODUCTION_TRANSITION_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "handoverGlobalId": str(self.handover_global_id),
            "handoverVersion": self.handover_version,
            "versionKeyHash": self.version_key_hash,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "tenantId": self.tenant_id,
            "project": self.project.snapshot_payload(),
            "projectSnapshotHash": self.project.snapshot_hash,
            "policyRef": self.policy_ref.snapshot_payload(),
            "readinessRef": self.readiness_ref.snapshot_payload() if self.readiness_ref else None,
            "slots": [value.snapshot_payload() for value in self.slots],
            "manifest": [value.snapshot_payload() for value in self.manifest],
            "unresolvedActionSelector": {
                "mode": UNRESOLVED_ACTION_SELECTOR["mode"],
                "kinds": list(UNRESOLVED_ACTION_SELECTOR["kinds"]),
            },
            "unresolvedActions": [value.snapshot_payload() for value in self.unresolved_actions],
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "handoverGlobalId": str(self.handover_global_id),
                "handoverVersion": self.handover_version,
            }
        )


def _validate_handover_inputs(
    *,
    project: ProjectTransitionSnapshot,
    policy: ProductionTransitionPolicyVersion,
    slots: tuple[FrozenAcknowledgementSlot, ...],
    manifest: tuple[HandoverSourceReference, ...],
    effective_date: date,
    enabled_user_ids: frozenset[str],
) -> None:
    if policy.publication_state is not PolicyPublicationState.PUBLISHED:
        raise ProductionTransitionPolicyPublishedRequired()
    if policy.tenant_id != project.tenant_id:
        raise _problem("policyRef", _("The published policy does not apply to this Project."))
    if not policy.applicability.applies_to(project):
        raise _problem("policyRef", _("The published policy does not apply to this Project."))
    slot_by_key = {value.slot_key: value for value in slots}
    if set(slot_by_key) != {value.key for value in policy.acknowledgement_slots}:
        raise _problem(
            "slots",
            _(
                "Freeze exactly one Project member and role for every required acknowledgement slot."
            ),
        )
    for definition in policy.acknowledgement_slots:
        _validate_slot_binding(slot_by_key[definition.key], definition, project, effective_date, enabled_user_ids)
    requirement_by_key = {value.key: value for value in policy.handover_requirements}
    if any(value.requirement_key not in requirement_by_key for value in manifest):
        raise _problem(
            "manifest.requirementKey",
            _("Select a handover requirement defined by this policy."),
        )
    for key, requirement in requirement_by_key.items():
        matches = [
            value
            for value in manifest
            if value.requirement_key == key and value.kind in requirement.accepted_source_kinds
        ]
        if len(matches) < requirement.minimum_count:
            raise _problem("manifest", _("Select the exact required handover objects."))
        if any(
            value.requirement_key == key and value.kind not in requirement.accepted_source_kinds
            for value in manifest
        ):
            raise _problem(
                "manifest.kind",
                _("Select only source kinds allowed by the handover requirement."),
            )
        if any(
            value.requirement_key == key and value.role != requirement.manifest_role
            for value in manifest
        ):
            raise _problem(
                "manifest.role",
                _("The manifest role must match the published handover requirement."),
            )


def create_handover_package_revision(
    *,
    handover_global_id: UUID,
    tenant_id: str,
    project: ProjectTransitionSnapshot,
    policy: ProductionTransitionPolicyVersion,
    readiness_ref: ExactVersionReference | None,
    slots: tuple[FrozenAcknowledgementSlot, ...],
    manifest: tuple[HandoverSourceReference, ...],
    server_unresolved_actions: tuple[UnresolvedActionSnapshot, ...],
    enabled_user_ids: frozenset[str],
    reason: str,
    created_by_user_id: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> HandoverPackageRevision:
    occurred_at = _datetime(created_at, "createdAt")
    _validate_handover_inputs(
        project=project,
        policy=policy,
        slots=slots,
        manifest=manifest,
        effective_date=occurred_at.date(),
        enabled_user_ids=frozenset(_email(value, "enabledUserIds") for value in enabled_user_ids),
    )
    stream_id = _uuid(handover_global_id, "handoverGlobalId")
    return HandoverPackageRevision(
        global_id=uuid5(stream_id, "npi-handover-package-revision:1"),
        handover_global_id=stream_id,
        handover_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        tenant_id=tenant_id,
        project=project,
        policy_ref=ExactVersionReference(policy.global_id, policy.policy_version, policy.snapshot_hash),
        readiness_ref=readiness_ref,
        slots=slots,
        manifest=manifest,
        unresolved_actions=tuple(server_unresolved_actions),
        reason=reason,
        created_by_user_id=created_by_user_id,
        created_at=occurred_at,
        request_id=request_id,
        trace_id=trace_id,
    )


def create_handover_package_successor(
    current: HandoverPackageRevision,
    *,
    project: ProjectTransitionSnapshot,
    policy: ProductionTransitionPolicyVersion,
    readiness_ref: ExactVersionReference | None,
    slots: tuple[FrozenAcknowledgementSlot, ...],
    manifest: tuple[HandoverSourceReference, ...],
    server_unresolved_actions: tuple[UnresolvedActionSnapshot, ...],
    enabled_user_ids: frozenset[str],
    reason: str,
    created_by_user_id: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> HandoverPackageRevision:
    if not isinstance(current, HandoverPackageRevision):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current handover revision."),
        )
    occurred_at = _datetime(created_at, "createdAt")
    _validate_handover_inputs(
        project=project,
        policy=policy,
        slots=slots,
        manifest=manifest,
        effective_date=occurred_at.date(),
        enabled_user_ids=frozenset(_email(value, "enabledUserIds") for value in enabled_user_ids),
    )
    version = current.handover_version + 1
    successor = HandoverPackageRevision(
        global_id=uuid5(current.handover_global_id, f"npi-handover-package-revision:{version}"),
        handover_global_id=current.handover_global_id,
        handover_version=version,
        predecessor_global_id=current.global_id,
        predecessor_snapshot_hash=current.snapshot_hash,
        tenant_id=current.tenant_id,
        project=project,
        policy_ref=ExactVersionReference(policy.global_id, policy.policy_version, policy.snapshot_hash),
        readiness_ref=readiness_ref,
        slots=slots,
        manifest=manifest,
        unresolved_actions=tuple(server_unresolved_actions),
        reason=reason,
        created_by_user_id=created_by_user_id,
        created_at=occurred_at,
        request_id=request_id,
        trace_id=trace_id,
    )
    validate_handover_successor(current, successor)
    return successor


def validate_handover_successor(
    current: HandoverPackageRevision,
    successor: HandoverPackageRevision,
) -> None:
    if (
        successor.handover_global_id != current.handover_global_id
        or successor.tenant_id != current.tenant_id
        or successor.project.global_id != current.project.global_id
        or successor.handover_version != current.handover_version + 1
        or successor.predecessor_global_id != current.global_id
        or successor.predecessor_snapshot_hash != current.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current handover revision."),
        )


@dataclass(frozen=True, slots=True)
class HandoverAcknowledgement:
    global_id: UUID
    handover_global_id: UUID
    package_revision_global_id: UUID
    package_version: int
    package_snapshot_hash: str
    slot_key: str
    actor_user_id: str
    member_global_id: UUID
    member_optimistic_version: int
    member_snapshot_hash: str
    role_global_id: UUID
    role_optimistic_version: int
    role_snapshot_hash: str
    acknowledged_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        package_id = _uuid(self.package_revision_global_id, "packageRevisionGlobalId")
        object.__setattr__(self, "slot_key", _text(self.slot_key, "slotKey", 128, pattern=_KEY))
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if self.global_id != uuid5(package_id, f"npi-handover-acknowledgement:{self.slot_key}"):
            raise _problem("globalId", _("The acknowledgement identifier is not canonical."))
        object.__setattr__(self, "handover_global_id", _uuid(self.handover_global_id, "handoverGlobalId"))
        _positive(self.package_version, "packageVersion")
        if package_id != uuid5(
            self.handover_global_id,
            f"npi-handover-package-revision:{self.package_version}",
        ):
            raise _problem(
                "packageRevisionGlobalId",
                _("Select the exact package revision from this handover stream."),
            )
        object.__setattr__(self, "package_snapshot_hash", _hash(self.package_snapshot_hash, "packageSnapshotHash"))
        object.__setattr__(self, "actor_user_id", _email(self.actor_user_id, "actorUserId"))
        object.__setattr__(self, "member_global_id", _uuid(self.member_global_id, "memberGlobalId"))
        _positive(self.member_optimistic_version, "memberOptimisticVersion")
        object.__setattr__(self, "member_snapshot_hash", _hash(self.member_snapshot_hash, "memberSnapshotHash"))
        object.__setattr__(self, "role_global_id", _uuid(self.role_global_id, "roleGlobalId"))
        _positive(self.role_optimistic_version, "roleOptimisticVersion")
        object.__setattr__(self, "role_snapshot_hash", _hash(self.role_snapshot_hash, "roleSnapshotHash"))
        object.__setattr__(self, "acknowledged_at", _datetime(self.acknowledged_at, "acknowledgedAt"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128, pattern=_KEY))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": PRODUCTION_TRANSITION_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "handoverGlobalId": str(self.handover_global_id),
            "packageRevisionGlobalId": str(self.package_revision_global_id),
            "packageVersion": self.package_version,
            "packageSnapshotHash": self.package_snapshot_hash,
            "slotKey": self.slot_key,
            "acknowledgementIntent": "acknowledge_exact_package_slot",
            "actorUserId": self.actor_user_id,
            "memberGlobalId": str(self.member_global_id),
            "memberOptimisticVersion": self.member_optimistic_version,
            "memberSnapshotHash": self.member_snapshot_hash,
            "roleGlobalId": str(self.role_global_id),
            "roleOptimisticVersion": self.role_optimistic_version,
            "roleSnapshotHash": self.role_snapshot_hash,
            "acknowledgedAt": _utc(self.acknowledged_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


def create_handover_acknowledgement(
    package: HandoverPackageRevision,
    *,
    slot_key: str,
    acknowledgement_intent: bool,
    actor_user_id: str,
    actor_user_enabled: bool,
    current_member: ProjectMemberSnapshot,
    current_role: ProjectRoleSnapshot,
    acknowledged_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> HandoverAcknowledgement:
    if acknowledgement_intent is not True:
        raise _problem(
            "acknowledgementIntent",
            _("Explicitly acknowledge this exact package slot."),
        )
    key = _text(slot_key, "slotKey", 128, pattern=_KEY)
    matches = [value for value in package.slots if value.slot_key == key]
    if len(matches) != 1:
        raise _problem("slotKey", _("Select one exact required acknowledgement slot."))
    binding = matches[0]
    actor = _email(actor_user_id, "actorUserId")
    occurred_at = _datetime(acknowledged_at, "acknowledgedAt")
    if actor != binding.member.user_id or not actor_user_enabled:
        raise _problem(
            "slotKey",
            _("Only the enabled member frozen for this slot can acknowledge it."),
        )
    if (
        current_member != binding.member
        or current_role != binding.role
        or current_member.snapshot_hash != binding.member.snapshot_hash
        or current_role.snapshot_hash != binding.role.snapshot_hash
        or not current_member.is_effective(occurred_at.date())
        or not current_role.is_effective(occurred_at.date())
    ):
        raise _problem(
            "slotKey",
            _("The frozen member or role changed; create a handover successor."),
        )
    return HandoverAcknowledgement(
        global_id=uuid5(package.global_id, f"npi-handover-acknowledgement:{key}"),
        handover_global_id=package.handover_global_id,
        package_revision_global_id=package.global_id,
        package_version=package.handover_version,
        package_snapshot_hash=package.snapshot_hash,
        slot_key=key,
        actor_user_id=actor,
        member_global_id=current_member.global_id,
        member_optimistic_version=current_member.optimistic_version,
        member_snapshot_hash=current_member.snapshot_hash,
        role_global_id=current_role.global_id,
        role_optimistic_version=current_role.optimistic_version,
        role_snapshot_hash=current_role.snapshot_hash,
        acknowledged_at=occurred_at,
        request_id=request_id,
        trace_id=trace_id,
    )


def derive_fully_acknowledged(
    package: HandoverPackageRevision,
    acknowledgements: Sequence[HandoverAcknowledgement],
) -> bool:
    exact: dict[str, HandoverAcknowledgement] = {}
    bindings = {value.slot_key: value for value in package.slots}
    for acknowledgement in acknowledgements:
        if not isinstance(acknowledgement, HandoverAcknowledgement):
            raise _problem("acknowledgements", _("Enter valid acknowledgement facts."))
        if (
            acknowledgement.handover_global_id != package.handover_global_id
            or acknowledgement.package_revision_global_id != package.global_id
            or acknowledgement.package_version != package.handover_version
            or acknowledgement.package_snapshot_hash != package.snapshot_hash
            or acknowledgement.slot_key not in bindings
        ):
            continue
        if acknowledgement.slot_key in exact and exact[acknowledgement.slot_key] != acknowledgement:
            raise _problem(
                "acknowledgements",
                _("Conflicting acknowledgement facts are not allowed."),
            )
        binding = bindings[acknowledgement.slot_key]
        if (
            acknowledgement.actor_user_id != binding.member.user_id
            or acknowledgement.member_global_id != binding.member.global_id
            or acknowledgement.member_optimistic_version != binding.member.optimistic_version
            or acknowledgement.member_snapshot_hash != binding.member.snapshot_hash
            or acknowledgement.role_global_id != binding.role.global_id
            or acknowledgement.role_optimistic_version != binding.role.optimistic_version
            or acknowledgement.role_snapshot_hash != binding.role.snapshot_hash
        ):
            raise _problem(
                "acknowledgements",
                _("The acknowledgement does not match its frozen actor slot."),
            )
        exact[acknowledgement.slot_key] = acknowledgement
    return bool(bindings) and set(exact) == set(bindings)


UNAVAILABLE_PROVIDER_REASON_CODES: Mapping[ObservationProviderKind, str] = MappingProxyType(
    {
        ObservationProviderKind.ACTUAL_SOP: "actual_sop_provider_unavailable",
        ObservationProviderKind.FIRST_BATCH_YIELD: "first_batch_yield_provider_unavailable",
        ObservationProviderKind.CUSTOMER_COMPLAINT: "customer_complaint_provider_unavailable",
        ObservationProviderKind.PRODUCTION_CYCLE_TIME: "production_cycle_time_provider_unavailable",
        ObservationProviderKind.TOOLING_STABILITY: "tooling_stability_provider_unavailable",
    }
)


@dataclass(frozen=True, slots=True)
class UnavailableObservationProvider:
    kind: ObservationProviderKind
    state: ObservationProviderState
    reason_code: str

    def __post_init__(self) -> None:
        _enum(self.kind, ObservationProviderKind, "providers.kind")
        _enum(self.state, ObservationProviderState, "providers.state")
        expected = UNAVAILABLE_PROVIDER_REASON_CODES[self.kind]
        if self.reason_code != expected:
            raise _problem(
                "providers.reasonCode",
                _("Select the closed unavailable reason for this provider."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "state": self.state.value,
            "reasonCode": self.reason_code,
            "sourceIdentity": None,
            "observedAt": None,
            "value": None,
            "unit": None,
        }


def unavailable_observation_providers() -> tuple[UnavailableObservationProvider, ...]:
    return tuple(
        UnavailableObservationProvider(
            kind=value,
            state=ObservationProviderState.UNAVAILABLE,
            reason_code=UNAVAILABLE_PROVIDER_REASON_CODES[value],
        )
        for value in MANDATORY_OBSERVATION_PROVIDER_KINDS
    )


@dataclass(frozen=True, slots=True)
class ObservationPeriodRevision:
    global_id: UUID
    observation_global_id: UUID
    observation_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    tenant_id: str
    project: ProjectTransitionSnapshot
    policy_ref: ExactVersionReference
    handover_package_ref: ExactVersionReference | None
    context_references: tuple[ObservationSourceReference, ...]
    retrospective_references: tuple[ObservationSourceReference, ...]
    providers: tuple[UnavailableObservationProvider, ...]
    observation_state: ObservationState
    technical_disposition: TechnicalDisposition
    retrospective_note: str | None
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        stream_id = _uuid(self.observation_global_id, "observationGlobalId")
        version = _positive(self.observation_version, "observationVersion")
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        if self.global_id != uuid5(stream_id, f"npi-observation-period-revision:{version}"):
            raise _problem(
                "globalId",
                _("The observation-period revision identifier is not canonical."),
            )
        predecessor_id = _optional_uuid(self.predecessor_global_id, "predecessorGlobalId")
        predecessor_hash = _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash")
        if version == 1 and (predecessor_id is not None or predecessor_hash is not None):
            raise _problem(
                "predecessorGlobalId",
                _("The first observation revision cannot have a predecessor."),
            )
        if version > 1 and (predecessor_id is None or predecessor_hash is None):
            raise _problem(
                "predecessorGlobalId",
                _("Select the exact preceding observation revision."),
            )
        if version > 1 and predecessor_id != uuid5(
            stream_id,
            f"npi-observation-period-revision:{version - 1}",
        ):
            raise _problem(
                "predecessorGlobalId",
                _("Select the exact preceding revision from this observation stream."),
            )
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128, pattern=_TENANT))
        if not isinstance(self.project, ProjectTransitionSnapshot) or self.project.tenant_id != self.tenant_id:
            raise _problem("project", _("Select an exact same-tenant Project snapshot."))
        if not isinstance(self.policy_ref, ExactVersionReference):
            raise _problem("policyRef", _("Select an exact published policy version."))
        if self.handover_package_ref is not None and not isinstance(self.handover_package_ref, ExactVersionReference):
            raise _problem(
                "handoverPackageRef",
                _("Select an exact handover-package revision."),
            )
        context = _tuple_of(
            self.context_references,
            ObservationSourceReference,
            "contextReferences",
            MAX_OBSERVATION_REFERENCES,
        )
        retrospective = _tuple_of(
            self.retrospective_references,
            ObservationSourceReference,
            "retrospectiveReferences",
            MAX_OBSERVATION_REFERENCES,
        )
        _unique(tuple((value.kind, value.global_id) for value in context), "contextReferences")
        _unique(tuple((value.kind, value.global_id) for value in retrospective), "retrospectiveReferences")
        if any(value.usage is not ObservationReferenceUsage.CONTEXT for value in context):
            raise _problem(
                "contextReferences.usage",
                _("Context references must use the context usage."),
            )
        if any(value.usage is not ObservationReferenceUsage.RETROSPECTIVE for value in retrospective):
            raise _problem(
                "retrospectiveReferences.usage",
                _("Retrospective references must use the retrospective usage."),
            )
        context_exact_by_identity = {
            (value.kind, value.global_id): (value.source_version, value.snapshot_hash)
            for value in context
        }
        if any(
            (value.kind, value.global_id) in context_exact_by_identity
            and context_exact_by_identity[(value.kind, value.global_id)]
            != (value.source_version, value.snapshot_hash)
            for value in retrospective
        ):
            raise _problem(
                "retrospectiveReferences",
                _("Repeated observation references must identify the same exact source version."),
            )
        providers = _tuple_of(
            self.providers,
            UnavailableObservationProvider,
            "providers",
            len(ObservationProviderKind),
        )
        if tuple(value.kind for value in providers) != MANDATORY_OBSERVATION_PROVIDER_KINDS:
            raise _problem(
                "providers",
                _(
                    "All five server-fixed unavailable providers are required in canonical order."
                ),
            )
        _enum(self.observation_state, ObservationState, "observationState")
        _enum(self.technical_disposition, TechnicalDisposition, "technicalDisposition")
        if (
            self.observation_state is not ObservationState.NOT_EVALUABLE
            or self.technical_disposition is not TechnicalDisposition.NOT_EVALUABLE
        ):
            raise _problem(
                "technicalDisposition",
                _("Unavailable mandatory providers require the not-evaluable disposition."),
            )
        object.__setattr__(self, "context_references", context)
        object.__setattr__(self, "retrospective_references", retrospective)
        object.__setattr__(self, "providers", providers)
        object.__setattr__(
            self,
            "retrospective_note",
            _optional_text(self.retrospective_note, "retrospectiveNote", 4000),
        )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1000))
        object.__setattr__(self, "created_by_user_id", _email(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128, pattern=_KEY))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": PRODUCTION_TRANSITION_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "observationGlobalId": str(self.observation_global_id),
            "observationVersion": self.observation_version,
            "versionKeyHash": self.version_key_hash,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "tenantId": self.tenant_id,
            "project": self.project.snapshot_payload(),
            "projectSnapshotHash": self.project.snapshot_hash,
            "policyRef": self.policy_ref.snapshot_payload(),
            "handoverPackageRef": self.handover_package_ref.snapshot_payload() if self.handover_package_ref else None,
            "contextReferences": [value.snapshot_payload() for value in self.context_references],
            "retrospectiveReferences": [value.snapshot_payload() for value in self.retrospective_references],
            "providers": [value.snapshot_payload() for value in self.providers],
            "observedStartDate": None,
            "observedEndDate": None,
            "observationState": self.observation_state.value,
            "technicalDisposition": self.technical_disposition.value,
            "authorityBoundary": "technical_observation_only",
            "retrospectiveNote": self.retrospective_note,
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "observationGlobalId": str(self.observation_global_id),
                "observationVersion": self.observation_version,
            }
        )


def _validate_observation_policy(
    policy: ProductionTransitionPolicyVersion,
    project: ProjectTransitionSnapshot,
) -> None:
    if policy.publication_state is not PolicyPublicationState.PUBLISHED:
        raise ProductionTransitionPolicyPublishedRequired()
    if policy.tenant_id != project.tenant_id:
        raise _problem("policyRef", _("The published policy does not apply to this Project."))
    if not policy.applicability.applies_to(project):
        raise _problem("policyRef", _("The published policy does not apply to this Project."))
    if {value.provider_kind for value in policy.observation_source_rules} != set(
        MANDATORY_OBSERVATION_PROVIDER_KINDS
    ):
        raise _problem(
            "policyRef",
            _("The published policy must retain all five mandatory observation providers."),
        )


def create_observation_period_revision(
    *,
    observation_global_id: UUID,
    tenant_id: str,
    project: ProjectTransitionSnapshot,
    policy: ProductionTransitionPolicyVersion,
    handover_package_ref: ExactVersionReference | None,
    context_references: tuple[ObservationSourceReference, ...],
    retrospective_references: tuple[ObservationSourceReference, ...],
    retrospective_note: str | None,
    reason: str,
    created_by_user_id: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> ObservationPeriodRevision:
    _validate_observation_policy(policy, project)
    stream_id = _uuid(observation_global_id, "observationGlobalId")
    return ObservationPeriodRevision(
        global_id=uuid5(stream_id, "npi-observation-period-revision:1"),
        observation_global_id=stream_id,
        observation_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        tenant_id=tenant_id,
        project=project,
        policy_ref=ExactVersionReference(policy.global_id, policy.policy_version, policy.snapshot_hash),
        handover_package_ref=handover_package_ref,
        context_references=context_references,
        retrospective_references=retrospective_references,
        providers=unavailable_observation_providers(),
        observation_state=ObservationState.NOT_EVALUABLE,
        technical_disposition=TechnicalDisposition.NOT_EVALUABLE,
        retrospective_note=retrospective_note,
        reason=reason,
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        request_id=request_id,
        trace_id=trace_id,
    )


def create_observation_period_successor(
    current: ObservationPeriodRevision,
    *,
    project: ProjectTransitionSnapshot,
    policy: ProductionTransitionPolicyVersion,
    handover_package_ref: ExactVersionReference | None,
    context_references: tuple[ObservationSourceReference, ...],
    retrospective_references: tuple[ObservationSourceReference, ...],
    retrospective_note: str | None,
    reason: str,
    created_by_user_id: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> ObservationPeriodRevision:
    if not isinstance(current, ObservationPeriodRevision):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current observation revision."),
        )
    _validate_observation_policy(policy, project)
    version = current.observation_version + 1
    successor = ObservationPeriodRevision(
        global_id=uuid5(current.observation_global_id, f"npi-observation-period-revision:{version}"),
        observation_global_id=current.observation_global_id,
        observation_version=version,
        predecessor_global_id=current.global_id,
        predecessor_snapshot_hash=current.snapshot_hash,
        tenant_id=current.tenant_id,
        project=project,
        policy_ref=ExactVersionReference(policy.global_id, policy.policy_version, policy.snapshot_hash),
        handover_package_ref=handover_package_ref,
        context_references=context_references,
        retrospective_references=retrospective_references,
        providers=unavailable_observation_providers(),
        observation_state=ObservationState.NOT_EVALUABLE,
        technical_disposition=TechnicalDisposition.NOT_EVALUABLE,
        retrospective_note=retrospective_note,
        reason=reason,
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        request_id=request_id,
        trace_id=trace_id,
    )
    validate_observation_successor(current, successor)
    return successor


def validate_observation_successor(
    current: ObservationPeriodRevision,
    successor: ObservationPeriodRevision,
) -> None:
    if (
        successor.observation_global_id != current.observation_global_id
        or successor.tenant_id != current.tenant_id
        or successor.project.global_id != current.project.global_id
        or successor.observation_version != current.observation_version + 1
        or successor.predecessor_global_id != current.global_id
        or successor.predecessor_snapshot_hash != current.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current observation revision."),
        )


def _record(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _problem(path, _("Enter a valid object."))
    return value


def _array(record: Mapping[str, object], key: str) -> tuple[object, ...]:
    value = record.get(key)
    if not isinstance(value, list):
        raise _problem(key, _("Enter a valid list."))
    return tuple(value)


def _string(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise _problem(key, _("Enter a valid value."))
    return value


def _optional_string(record: Mapping[str, object], key: str) -> str | None:
    value = record.get(key)
    if value is not None and not isinstance(value, str):
        raise _problem(key, _("Enter a valid value."))
    return value


def _integer(record: Mapping[str, object], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise _problem(key, _("Enter a valid integer."))
    return value


def _exact_ref_from_snapshot(value: object, path: str) -> ExactVersionReference:
    record = _record(value, path)
    return ExactVersionReference(
        global_id=UUID(_string(record, "globalId")),
        version=_integer(record, "version"),
        snapshot_hash=_string(record, "snapshotHash"),
    )


def _optional_exact_ref(value: object, path: str) -> ExactVersionReference | None:
    return None if value is None else _exact_ref_from_snapshot(value, path)


def _applicability_from_snapshot(value: object) -> ProductionTransitionApplicability:
    record = _record(value, "applicability")
    return ProductionTransitionApplicability(
        project_types=tuple(ProjectType(str(item)) for item in _array(record, "projectTypes")),
        project_global_ids=tuple(UUID(str(item)) for item in _array(record, "projectGlobalIds")),
        customer_reference_keys=tuple(str(item) for item in _array(record, "customerReferenceKeys")),
    )


def _project_from_snapshot(value: object) -> ProjectTransitionSnapshot:
    record = _record(value, "project")
    target_sop = _optional_string(record, "targetSopDate")
    if record.get("targetSopState") != "planned_only":
        raise _problem(
            "project.targetSopState",
            _("Target SOP must remain planned-only context."),
        )
    return ProjectTransitionSnapshot(
        global_id=UUID(_string(record, "globalId")),
        tenant_id=_string(record, "tenantId"),
        optimistic_version=_integer(record, "optimisticVersion"),
        business_code=_string(record, "businessCode"),
        title=_string(record, "title"),
        project_type=ProjectType(_string(record, "projectType")),
        owner_user_id=_string(record, "ownerUserId"),
        target_sop_date=date.fromisoformat(target_sop) if target_sop else None,
        lifecycle_state=_string(record, "lifecycleState"),
        template_ref=_exact_ref_from_snapshot(record.get("templateRef"), "project.templateRef"),
        work_policy_ref=_exact_ref_from_snapshot(record.get("workPolicyRef"), "project.workPolicyRef"),
        customer_reference_keys=tuple(str(item) for item in _array(record, "customerReferenceKeys")),
    )


def _member_from_snapshot(value: object) -> ProjectMemberSnapshot:
    record = _record(value, "member")
    effective_to = _optional_string(record, "effectiveTo")
    return ProjectMemberSnapshot(
        global_id=UUID(_string(record, "globalId")),
        tenant_id=_string(record, "tenantId"),
        project_global_id=UUID(_string(record, "projectGlobalId")),
        user_id=_string(record, "userId"),
        effective_from=date.fromisoformat(_string(record, "effectiveFrom")),
        effective_to=date.fromisoformat(effective_to) if effective_to else None,
        optimistic_version=_integer(record, "optimisticVersion"),
    )


def _role_from_snapshot(value: object) -> ProjectRoleSnapshot:
    record = _record(value, "role")
    effective_to = _optional_string(record, "effectiveTo")
    return ProjectRoleSnapshot(
        global_id=UUID(_string(record, "globalId")),
        tenant_id=_string(record, "tenantId"),
        project_global_id=UUID(_string(record, "projectGlobalId")),
        member_global_id=UUID(_string(record, "memberGlobalId")),
        role_key=_string(record, "roleKey"),
        effective_from=date.fromisoformat(_string(record, "effectiveFrom")),
        effective_to=date.fromisoformat(effective_to) if effective_to else None,
        optimistic_version=_integer(record, "optimisticVersion"),
    )


def _slot_from_snapshot(value: object) -> FrozenAcknowledgementSlot:
    record = _record(value, "slot")
    member = _member_from_snapshot(record.get("member"))
    role = _role_from_snapshot(record.get("role"))
    if _string(record, "memberSnapshotHash") != member.snapshot_hash:
        raise _problem(
            "slots.memberSnapshotHash",
            _("The frozen member hash does not match its projection."),
        )
    if _string(record, "roleSnapshotHash") != role.snapshot_hash:
        raise _problem(
            "slots.roleSnapshotHash",
            _("The frozen role hash does not match its projection."),
        )
    return FrozenAcknowledgementSlot(
        slot_key=_string(record, "slotKey"),
        group_key=_string(record, "groupKey"),
        direction=AcknowledgementDirection(_string(record, "direction")),
        member=member,
        role=role,
    )


def _source_from_snapshot(value: object) -> HandoverSourceReference:
    record = _record(value, "source")
    return HandoverSourceReference(
        requirement_key=_string(record, "requirementKey"),
        kind=HandoverSourceKind(_string(record, "kind")),
        global_id=UUID(_string(record, "globalId")),
        source_version=_integer(record, "sourceVersion"),
        snapshot_hash=_string(record, "snapshotHash"),
        role=_string(record, "role"),
    )


def _observation_source_from_snapshot(value: object) -> ObservationSourceReference:
    record = _record(value, "observationSource")
    return ObservationSourceReference(
        kind=HandoverSourceKind(_string(record, "kind")),
        global_id=UUID(_string(record, "globalId")),
        source_version=_integer(record, "sourceVersion"),
        snapshot_hash=_string(record, "snapshotHash"),
        usage=ObservationReferenceUsage(_string(record, "usage")),
    )


def _action_from_snapshot(value: object) -> UnresolvedActionSnapshot:
    record = _record(value, "unresolvedAction")
    return UnresolvedActionSnapshot(
        global_id=UUID(_string(record, "globalId")),
        source_version=_integer(record, "sourceVersion"),
        snapshot_hash=_string(record, "snapshotHash"),
        kind=WorkItemKind(_string(record, "kind")),
        state=_string(record, "state"),
        owner_user_id=_string(record, "ownerUserId"),
        due_date=date.fromisoformat(_string(record, "dueDate")),
    )


def _validate_schema_and_hashes(
    record: Mapping[str, object],
    *,
    project: ProjectTransitionSnapshot | None = None,
) -> None:
    if _integer(record, "schemaVersion") != PRODUCTION_TRANSITION_SCHEMA_VERSION:
        raise _problem("schemaVersion", _("Select a supported snapshot schema version."))
    if project is not None and _string(record, "projectSnapshotHash") != project.snapshot_hash:
        raise _problem(
            "projectSnapshotHash",
            _("The Project hash does not match its canonical projection."),
        )


def _require_exact_canonical_snapshot(
    supplied: Mapping[str, object],
    canonical: Mapping[str, object],
    path: str,
) -> None:
    if dict(supplied) != dict(canonical):
        raise _problem(
            path,
            _("The snapshot must contain exactly the canonical fields and values."),
        )


def policy_from_snapshot(value: object) -> ProductionTransitionPolicyVersion:
    record = _record(value, "policy")
    _validate_schema_and_hashes(record)
    selector = _record(record.get("unresolvedActionSelector"), "unresolvedActionSelector")
    if selector != {"mode": UNRESOLVED_ACTION_SELECTOR["mode"], "kinds": list(UNRESOLVED_ACTION_SELECTOR["kinds"])}:
        raise _problem(
            "unresolvedActionSelector",
            _("The unresolved-action selector is server-fixed."),
        )
    if record.get("authorityBoundary") != "npi_technical_configuration_only":
        raise _problem(
            "authorityBoundary",
            _("The policy cannot claim production or Gate authority."),
        )
    groups = tuple(
        ReceivingGroupDefinition(
            key=_string(_record(item, "receivingGroup"), "key"),
            title=_string(_record(item, "receivingGroup"), "title"),
        )
        for item in _array(record, "receivingGroups")
    )
    slots = tuple(
        AcknowledgementSlotDefinition(
            key=_string(item_record, "key"),
            group_key=_string(item_record, "groupKey"),
            direction=AcknowledgementDirection(_string(item_record, "direction")),
            allowed_project_role_keys=tuple(str(item) for item in _array(item_record, "allowedProjectRoleKeys")),
        )
        for item_record in (_record(item, "acknowledgementSlot") for item in _array(record, "acknowledgementSlots"))
    )
    requirements = tuple(
        HandoverObjectRequirement(
            key=_string(item_record, "key"),
            accepted_source_kinds=tuple(
                HandoverSourceKind(str(item)) for item in _array(item_record, "acceptedSourceKinds")
            ),
            manifest_role=_string(item_record, "manifestRole"),
            minimum_count=_integer(item_record, "minimumCount"),
        )
        for item_record in (_record(item, "handoverRequirement") for item in _array(record, "handoverRequirements"))
    )
    rules = tuple(
        ObservationSourceRule(
            provider_kind=ObservationProviderKind(_string(item_record, "providerKind")),
            unit=_optional_string(item_record, "unit"),
            comparator=(
                MetricComparator(_string(item_record, "comparator"))
                if item_record.get("comparator") is not None
                else None
            ),
            threshold=(
                _decimal(_string(item_record, "threshold"), "threshold")
                if item_record.get("threshold") is not None
                else None
            ),
            allowed_dispositions=tuple(
                TechnicalDisposition(str(item)) for item in _array(item_record, "allowedDispositions")
            ),
        )
        for item_record in (
            _record(item, "observationSourceRule")
            for item in _array(record, "observationSourceRules")
        )
    )
    result = ProductionTransitionPolicyVersion(
        global_id=UUID(_string(record, "globalId")),
        policy_global_id=UUID(_string(record, "policyGlobalId")),
        tenant_id=_string(record, "tenantId"),
        policy_code=_string(record, "policyCode"),
        policy_version=_integer(record, "policyVersion"),
        optimistic_version=_integer(record, "optimisticVersion"),
        title=_string(record, "title"),
        publication_state=PolicyPublicationState(_string(record, "publicationState")),
        prior_version_ref=_optional_exact_ref(record.get("priorVersionRef"), "priorVersionRef"),
        applicability=_applicability_from_snapshot(record.get("applicability")),
        receiving_groups=groups,
        acknowledgement_slots=slots,
        handover_requirements=requirements,
        observation_source_rules=rules,
        observation_window_days=_integer(record, "observationWindowDays"),
        changed_by_user_id=_string(record, "changedByUserId"),
        changed_at=datetime.fromisoformat(_string(record, "changedAt").replace("Z", "+00:00")),
        request_id=UUID(_string(record, "requestId")),
        trace_id=_string(record, "traceId"),
    )
    _require_exact_canonical_snapshot(record, result.snapshot_payload(), "policy")
    return result


def handover_package_from_snapshot(value: object) -> HandoverPackageRevision:
    record = _record(value, "handoverPackage")
    project = _project_from_snapshot(record.get("project"))
    _validate_schema_and_hashes(record, project=project)
    selector = _record(record.get("unresolvedActionSelector"), "unresolvedActionSelector")
    if selector != {"mode": UNRESOLVED_ACTION_SELECTOR["mode"], "kinds": list(UNRESOLVED_ACTION_SELECTOR["kinds"])}:
        raise _problem(
            "unresolvedActionSelector",
            _("The unresolved-action selector is server-fixed."),
        )
    predecessor_id = _optional_string(record, "predecessorGlobalId")
    result = HandoverPackageRevision(
        global_id=UUID(_string(record, "globalId")),
        handover_global_id=UUID(_string(record, "handoverGlobalId")),
        handover_version=_integer(record, "handoverVersion"),
        predecessor_global_id=UUID(predecessor_id) if predecessor_id else None,
        predecessor_snapshot_hash=_optional_string(record, "predecessorSnapshotHash"),
        tenant_id=_string(record, "tenantId"),
        project=project,
        policy_ref=_exact_ref_from_snapshot(record.get("policyRef"), "policyRef"),
        readiness_ref=_optional_exact_ref(record.get("readinessRef"), "readinessRef"),
        slots=tuple(_slot_from_snapshot(item) for item in _array(record, "slots")),
        manifest=tuple(_source_from_snapshot(item) for item in _array(record, "manifest")),
        unresolved_actions=tuple(_action_from_snapshot(item) for item in _array(record, "unresolvedActions")),
        reason=_string(record, "reason"),
        created_by_user_id=_string(record, "createdByUserId"),
        created_at=datetime.fromisoformat(_string(record, "createdAt").replace("Z", "+00:00")),
        request_id=UUID(_string(record, "requestId")),
        trace_id=_string(record, "traceId"),
    )
    _require_exact_canonical_snapshot(record, result.snapshot_payload(), "handoverPackage")
    return result


def acknowledgement_from_snapshot(value: object) -> HandoverAcknowledgement:
    record = _record(value, "acknowledgement")
    _validate_schema_and_hashes(record)
    if record.get("acknowledgementIntent") != "acknowledge_exact_package_slot":
        raise _problem(
            "acknowledgementIntent",
            _("The acknowledgement intent is invalid."),
        )
    result = HandoverAcknowledgement(
        global_id=UUID(_string(record, "globalId")),
        handover_global_id=UUID(_string(record, "handoverGlobalId")),
        package_revision_global_id=UUID(_string(record, "packageRevisionGlobalId")),
        package_version=_integer(record, "packageVersion"),
        package_snapshot_hash=_string(record, "packageSnapshotHash"),
        slot_key=_string(record, "slotKey"),
        actor_user_id=_string(record, "actorUserId"),
        member_global_id=UUID(_string(record, "memberGlobalId")),
        member_optimistic_version=_integer(record, "memberOptimisticVersion"),
        member_snapshot_hash=_string(record, "memberSnapshotHash"),
        role_global_id=UUID(_string(record, "roleGlobalId")),
        role_optimistic_version=_integer(record, "roleOptimisticVersion"),
        role_snapshot_hash=_string(record, "roleSnapshotHash"),
        acknowledged_at=datetime.fromisoformat(_string(record, "acknowledgedAt").replace("Z", "+00:00")),
        request_id=UUID(_string(record, "requestId")),
        trace_id=_string(record, "traceId"),
    )
    _require_exact_canonical_snapshot(record, result.snapshot_payload(), "acknowledgement")
    return result


def observation_from_snapshot(value: object) -> ObservationPeriodRevision:
    record = _record(value, "observation")
    project = _project_from_snapshot(record.get("project"))
    _validate_schema_and_hashes(record, project=project)
    if (
        record.get("observedStartDate") is not None
        or record.get("observedEndDate") is not None
        or record.get("authorityBoundary") != "technical_observation_only"
    ):
        raise _problem(
            "observedStartDate",
            _("Unavailable providers cannot retain observed dates or production authority."),
        )
    providers = tuple(
        UnavailableObservationProvider(
            kind=ObservationProviderKind(_string(provider, "kind")),
            state=ObservationProviderState(_string(provider, "state")),
            reason_code=_string(provider, "reasonCode"),
        )
        for provider in (_record(item, "provider") for item in _array(record, "providers"))
    )
    for provider, raw in zip(providers, _array(record, "providers"), strict=True):
        raw_record = _record(raw, "provider")
        if any(raw_record.get(key) is not None for key in ("sourceIdentity", "observedAt", "value", "unit")):
            raise _problem(
                "providers",
                _("Unavailable providers must remain identity-free and valueless."),
            )
    predecessor_id = _optional_string(record, "predecessorGlobalId")
    result = ObservationPeriodRevision(
        global_id=UUID(_string(record, "globalId")),
        observation_global_id=UUID(_string(record, "observationGlobalId")),
        observation_version=_integer(record, "observationVersion"),
        predecessor_global_id=UUID(predecessor_id) if predecessor_id else None,
        predecessor_snapshot_hash=_optional_string(record, "predecessorSnapshotHash"),
        tenant_id=_string(record, "tenantId"),
        project=project,
        policy_ref=_exact_ref_from_snapshot(record.get("policyRef"), "policyRef"),
        handover_package_ref=_optional_exact_ref(record.get("handoverPackageRef"), "handoverPackageRef"),
        context_references=tuple(
            _observation_source_from_snapshot(item) for item in _array(record, "contextReferences")
        ),
        retrospective_references=tuple(
            _observation_source_from_snapshot(item)
            for item in _array(record, "retrospectiveReferences")
        ),
        providers=providers,
        observation_state=ObservationState(_string(record, "observationState")),
        technical_disposition=TechnicalDisposition(_string(record, "technicalDisposition")),
        retrospective_note=_optional_string(record, "retrospectiveNote"),
        reason=_string(record, "reason"),
        created_by_user_id=_string(record, "createdByUserId"),
        created_at=datetime.fromisoformat(_string(record, "createdAt").replace("Z", "+00:00")),
        request_id=UUID(_string(record, "requestId")),
        trace_id=_string(record, "traceId"),
    )
    _require_exact_canonical_snapshot(record, result.snapshot_payload(), "observation")
    return result
