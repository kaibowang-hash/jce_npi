from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
from enum import StrEnum
from typing import Mapping, Sequence
from uuid import UUID, uuid5

from npi_core.foundation.concurrency import next_version
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.project.domain import ProjectType

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_CATEGORIES = 100
MAX_ITEMS = 1_000
MAX_REQUIREMENTS = 20
MAX_SOURCES = 100
SCORE_FORMULA_VERSION = "readiness-score.v1"


class ReadinessPublicationState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ReadinessBlockingLevel(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    NONE = "none"


class ReadinessCompletionRule(StrEnum):
    CONFIRMATION = "confirmation"
    EXACT_EVIDENCE = "exact_evidence"
    EXACT_SOURCE_RESULT = "exact_source_result"


class ReadinessItemState(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class ReadinessSourceState(StrEnum):
    SATISFIED = "satisfied"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class ReadinessSourceKind(StrEnum):
    PROJECT = "project"
    DOMAIN_WORK_ITEM = "domain_work_item"
    RELEASED_DOCUMENT = "released_document"
    RELEASE_BASELINE = "release_baseline"
    FILE_REVISION = "file_revision"
    TOOLING_CAPACITY_SCENARIO = "tooling_capacity_scenario"
    TRIAL_INPUT_LOCK = "trial_input_lock"
    TRIAL_ACTUAL = "trial_actual"
    TRIAL_SAMPLE = "trial_sample"
    TRIAL_CAVITY_RESULT = "trial_cavity_result"
    TRIAL_DEFECT = "trial_defect"
    TRIAL_DEFECT_VERIFICATION = "trial_defect_verification"
    TRIAL_COMPARISON = "trial_comparison"
    TRIAL_REVIEW_REFERENCE = "trial_review_reference"
    TRIAL_CONCLUSION = "trial_conclusion"
    CONTROLLED_QUALITY_RESULT = "controlled_quality_result"
    ERP_MATERIAL_SPECIFICATION = "erp_material_specification"
    ERP_QUALITY_RESULT = "erp_quality_result"
    ERP_RUN_AT_RATE = "erp_run_at_rate"
    ERP_HR_QUALIFICATION = "erp_hr_qualification"
    ERP_SUPPLIER_EXECUTION = "erp_supplier_execution"


EXTERNAL_SOURCE_KINDS = frozenset(
    {
        ReadinessSourceKind.ERP_MATERIAL_SPECIFICATION,
        ReadinessSourceKind.ERP_QUALITY_RESULT,
        ReadinessSourceKind.ERP_RUN_AT_RATE,
        ReadinessSourceKind.ERP_HR_QUALIFICATION,
        ReadinessSourceKind.ERP_SUPPLIER_EXECUTION,
    }
)
QUALITY_RESULT_KINDS = frozenset(
    {
        ReadinessSourceKind.CONTROLLED_QUALITY_RESULT,
        ReadinessSourceKind.ERP_QUALITY_RESULT,
    }
)


class ReadinessTemplateImmutable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "READINESS_TEMPLATE_IMMUTABLE",
            _("A published NPI Readiness Template version cannot be changed."),
        )


class ReadinessVersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "READINESS_VERSION_CONFLICT",
            _("The NPI readiness record was changed by another user."),
        )


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
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


def _text(value: object, path: str, maximum: int, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum or (pattern and pattern.fullmatch(normalized) is None):
        raise _problem(path, _("Enter a valid value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, path, maximum)


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid snapshot hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _enum(value: object, expected: type[StrEnum], path: str):
    if not isinstance(value, expected):
        raise _problem(path, _("Select a supported value."))
    return value


def _date(value: object, path: str) -> date:
    if type(value) is not date:
        raise _problem(path, _("Enter a valid date."))
    return value


def _datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a valid timestamp."))
    return value.astimezone(UTC)


def _email(value: object, path: str) -> str:
    normalized = _text(value, path, 254).casefold()
    if _EMAIL.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid user ID."))
    return normalized


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


@dataclass(frozen=True, slots=True)
class ReadinessApplicabilitySelector:
    project_types: tuple[ProjectType, ...] = ()
    customer_reference_keys: tuple[str, ...] = ()
    industry_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        project_types = _tuple_of(self.project_types, ProjectType, "applicability.projectTypes", 20)
        customer_keys = tuple(
            sorted(_text(value, "applicability.customerReferenceKeys", 256) for value in self.customer_reference_keys)
        )
        industry_keys = tuple(
            sorted(_text(value, "applicability.industryKeys", 128, pattern=_KEY) for value in self.industry_keys)
        )
        _unique(project_types, "applicability.projectTypes")
        _unique(customer_keys, "applicability.customerReferenceKeys")
        _unique(industry_keys, "applicability.industryKeys")
        object.__setattr__(self, "project_types", tuple(sorted(project_types, key=str)))
        object.__setattr__(self, "customer_reference_keys", customer_keys)
        object.__setattr__(self, "industry_keys", industry_keys)

    def applies_to(self, context: ReadinessProjectSnapshot) -> bool:
        return (
            (not self.project_types or context.project_type in self.project_types)
            and (
                not self.customer_reference_keys
                or bool(set(self.customer_reference_keys) & set(context.customer_reference_keys))
            )
            and (not self.industry_keys or context.industry_key in self.industry_keys)
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "projectTypes": [value.value for value in self.project_types],
            "customerReferenceKeys": list(self.customer_reference_keys),
            "industryKeys": list(self.industry_keys),
        }


@dataclass(frozen=True, slots=True)
class ReadinessCategoryDefinition:
    key: str
    title: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _text(self.key, "categories.key", 128, pattern=_KEY))
        object.__setattr__(self, "title", _text(self.title, "categories.title", 200))

    def snapshot_payload(self) -> dict[str, object]:
        return {"key": self.key, "title": self.title}


@dataclass(frozen=True, slots=True)
class ReadinessEvidenceRequirement:
    key: str
    accepted_source_kinds: tuple[ReadinessSourceKind, ...]
    minimum_count: int = 1
    unavailable_blocks: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _text(self.key, "evidenceRequirements.key", 128, pattern=_KEY))
        kinds = _tuple_of(
            self.accepted_source_kinds,
            ReadinessSourceKind,
            "evidenceRequirements.acceptedSourceKinds",
            30,
        )
        if not kinds:
            raise _problem("evidenceRequirements.acceptedSourceKinds", _("Select at least one supported source kind."))
        _unique(kinds, "evidenceRequirements.acceptedSourceKinds")
        object.__setattr__(self, "accepted_source_kinds", tuple(sorted(kinds, key=str)))
        minimum = _positive(self.minimum_count, "evidenceRequirements.minimumCount")
        if minimum > MAX_SOURCES:
            raise _problem("evidenceRequirements.minimumCount", _("Enter a supported evidence count."))
        if type(self.unavailable_blocks) is not bool:
            raise _problem("evidenceRequirements.unavailableBlocks", _("Select a valid true or false value."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "acceptedSourceKinds": [value.value for value in self.accepted_source_kinds],
            "minimumCount": self.minimum_count,
            "unavailableBlocks": self.unavailable_blocks,
        }


@dataclass(frozen=True, slots=True)
class ReadinessItemDefinition:
    key: str
    title: str
    category_key: str
    weight: int
    required: bool
    blocking_level: ReadinessBlockingLevel
    gate_key: str
    completion_rule: ReadinessCompletionRule
    applicability: ReadinessApplicabilitySelector
    evidence_requirements: tuple[ReadinessEvidenceRequirement, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _text(self.key, "items.key", 128, pattern=_KEY))
        object.__setattr__(self, "title", _text(self.title, "items.title", 240))
        object.__setattr__(self, "category_key", _text(self.category_key, "items.categoryKey", 128, pattern=_KEY))
        _positive(self.weight, "items.weight")
        if type(self.required) is not bool:
            raise _problem("items.required", _("Select a valid true or false value."))
        _enum(self.blocking_level, ReadinessBlockingLevel, "items.blockingLevel")
        object.__setattr__(self, "gate_key", _text(self.gate_key, "items.gateKey", 128, pattern=_KEY))
        _enum(self.completion_rule, ReadinessCompletionRule, "items.completionRule")
        if not isinstance(self.applicability, ReadinessApplicabilitySelector):
            raise _problem("items.applicability", _("Enter a valid applicability selector."))
        requirements = _tuple_of(
            self.evidence_requirements,
            ReadinessEvidenceRequirement,
            "items.evidenceRequirements",
            MAX_REQUIREMENTS,
        )
        _unique(tuple(value.key.casefold() for value in requirements), "items.evidenceRequirements")
        if self.completion_rule is not ReadinessCompletionRule.CONFIRMATION and not requirements:
            raise _problem("items.evidenceRequirements", _("Add at least one evidence requirement."))
        object.__setattr__(self, "evidence_requirements", requirements)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "categoryKey": self.category_key,
            "weight": self.weight,
            "required": self.required,
            "blockingLevel": self.blocking_level.value,
            "gateKey": self.gate_key,
            "completionRule": self.completion_rule.value,
            "applicability": self.applicability.snapshot_payload(),
            "evidenceRequirements": [value.snapshot_payload() for value in self.evidence_requirements],
        }


@dataclass(frozen=True, slots=True)
class ReadinessTemplateVersion:
    global_id: UUID
    template_global_id: UUID
    template_code: str
    template_version: int
    optimistic_version: int
    title: str
    publication_state: ReadinessPublicationState
    applicability: ReadinessApplicabilitySelector
    categories: tuple[ReadinessCategoryDefinition, ...]
    items: tuple[ReadinessItemDefinition, ...]
    changed_by_user_id: str
    changed_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "globalId")
        _uuid(self.template_global_id, "templateGlobalId")
        expected = uuid5(self.template_global_id, f"npi-readiness-template-version:{self.template_version}")
        if self.global_id != expected:
            raise _problem("globalId", _("The template version identity is invalid."))
        object.__setattr__(self, "template_code", _text(self.template_code, "templateCode", 64, pattern=_CODE))
        _positive(self.template_version, "templateVersion")
        _positive(self.optimistic_version, "optimisticVersion")
        object.__setattr__(self, "title", _text(self.title, "title", 200))
        _enum(self.publication_state, ReadinessPublicationState, "publicationState")
        if not isinstance(self.applicability, ReadinessApplicabilitySelector):
            raise _problem("applicability", _("Enter a valid applicability selector."))
        if not self.applicability.project_types:
            raise _problem("applicability.projectTypes", _("Select at least one project type."))
        categories = _tuple_of(self.categories, ReadinessCategoryDefinition, "categories", MAX_CATEGORIES)
        items = _tuple_of(self.items, ReadinessItemDefinition, "items", MAX_ITEMS)
        _unique(tuple(value.key.casefold() for value in categories), "categories")
        _unique(tuple(value.key.casefold() for value in items), "items")
        category_keys = {value.key for value in categories}
        if any(value.category_key not in category_keys for value in items):
            raise _problem("items.categoryKey", _("Select a category from this template."))
        if any(
            value.applicability.project_types
            and not set(value.applicability.project_types).issubset(self.applicability.project_types)
            for value in items
        ):
            raise _problem("items.applicability.projectTypes", _("Item project types must be allowed by the template."))
        object.__setattr__(self, "categories", categories)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "changed_by_user_id", _email(self.changed_by_user_id, "changedByUserId"))
        object.__setattr__(self, "changed_at", _datetime(self.changed_at, "changedAt"))
        _uuid(self.request_id, "requestId")
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))
        if self.publication_state is ReadinessPublicationState.PUBLISHED:
            self._require_publishable()

    @classmethod
    def create_draft(
        cls,
        *,
        template_global_id: UUID,
        template_code: str,
        template_version: int,
        title: str,
        applicability: ReadinessApplicabilitySelector,
        categories: tuple[ReadinessCategoryDefinition, ...],
        items: tuple[ReadinessItemDefinition, ...],
        changed_by_user_id: str,
        changed_at: datetime,
        request_id: UUID,
        trace_id: str,
    ) -> ReadinessTemplateVersion:
        return cls(
            global_id=uuid5(template_global_id, f"npi-readiness-template-version:{template_version}"),
            template_global_id=template_global_id,
            template_code=template_code,
            template_version=template_version,
            optimistic_version=1,
            title=title,
            publication_state=ReadinessPublicationState.DRAFT,
            applicability=applicability,
            categories=categories,
            items=items,
            changed_by_user_id=changed_by_user_id,
            changed_at=changed_at,
            request_id=request_id,
            trace_id=trace_id,
        )

    def edit_draft(self, *, expected_version: int, **changes: object) -> ReadinessTemplateVersion:
        if self.publication_state is ReadinessPublicationState.PUBLISHED:
            raise ReadinessTemplateImmutable()
        try:
            updated = next_version(self.optimistic_version, expected_version)
        except Exception as error:
            raise ReadinessVersionConflict() from error
        allowed = {
            "title",
            "applicability",
            "categories",
            "items",
            "changed_by_user_id",
            "changed_at",
            "request_id",
            "trace_id",
        }
        if set(changes) - allowed:
            raise _problem("template", _("Enter only supported template changes."))
        return replace(self, optimistic_version=updated, **changes)

    def publish(
        self,
        *,
        expected_version: int,
        changed_by_user_id: str,
        changed_at: datetime,
        request_id: UUID,
        trace_id: str,
    ) -> ReadinessTemplateVersion:
        if self.publication_state is ReadinessPublicationState.PUBLISHED:
            raise ReadinessTemplateImmutable()
        self._require_publishable()
        try:
            updated = next_version(self.optimistic_version, expected_version)
        except Exception as error:
            raise ReadinessVersionConflict() from error
        return replace(
            self,
            optimistic_version=updated,
            publication_state=ReadinessPublicationState.PUBLISHED,
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
    ) -> ReadinessTemplateVersion:
        if self.publication_state is not ReadinessPublicationState.PUBLISHED:
            raise _problem("templateVersion", _("Publish the current template version before creating a revision."))
        return ReadinessTemplateVersion.create_draft(
            template_global_id=self.template_global_id,
            template_code=self.template_code,
            template_version=self.template_version + 1,
            title=self.title,
            applicability=self.applicability,
            categories=self.categories,
            items=self.items,
            changed_by_user_id=changed_by_user_id,
            changed_at=changed_at,
            request_id=request_id,
            trace_id=trace_id,
        )

    def _require_publishable(self) -> None:
        if not self.categories or not self.items:
            raise _problem("items", _("Add at least one readiness category and item before publishing."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "templateGlobalId": str(self.template_global_id),
            "templateCode": self.template_code,
            "templateVersion": self.template_version,
            "optimisticVersion": self.optimistic_version,
            "title": self.title,
            "publicationState": self.publication_state.value,
            "applicability": self.applicability.snapshot_payload(),
            "categories": [value.snapshot_payload() for value in self.categories],
            "items": [value.snapshot_payload() for value in self.items],
            "changedByUserId": self.changed_by_user_id,
            "changedAt": _utc(self.changed_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return _sha256(self.snapshot_payload())

    @property
    def version_key_hash(self) -> str:
        return _sha256({"templateGlobalId": str(self.template_global_id), "templateVersion": self.template_version})


@dataclass(frozen=True, slots=True)
class ReadinessExactReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "reference.globalId")
        _positive(self.version, "reference.version")
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "reference.snapshotHash"))

    def snapshot_payload(self) -> dict[str, object]:
        return {"globalId": str(self.global_id), "version": self.version, "snapshotHash": self.snapshot_hash}


@dataclass(frozen=True, slots=True)
class ReadinessProjectSnapshot:
    global_id: UUID
    optimistic_version: int
    snapshot_hash: str
    project_type: ProjectType
    customer_reference_keys: tuple[str, ...]
    industry_key: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "project.globalId")
        _positive(self.optimistic_version, "project.optimisticVersion")
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "project.snapshotHash"))
        if not isinstance(self.project_type, ProjectType):
            raise _problem("project.projectType", _("Select a supported project type."))
        keys = tuple(sorted(_text(value, "project.customerReferenceKeys", 256) for value in self.customer_reference_keys))
        _unique(keys, "project.customerReferenceKeys")
        object.__setattr__(self, "customer_reference_keys", keys)
        object.__setattr__(self, "industry_key", _text(self.industry_key, "project.industryKey", 128, pattern=_KEY))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "optimisticVersion": self.optimistic_version,
            "snapshotHash": self.snapshot_hash,
            "projectType": self.project_type.value,
            "customerReferenceKeys": list(self.customer_reference_keys),
            "industryKey": self.industry_key,
        }


@dataclass(frozen=True, slots=True)
class ReadinessMemberReference:
    global_id: UUID
    user_id: str
    optimistic_version: int

    def __post_init__(self) -> None:
        _uuid(self.global_id, "owner.globalId")
        object.__setattr__(self, "user_id", _email(self.user_id, "owner.userId"))
        _positive(self.optimistic_version, "owner.optimisticVersion")

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "userId": self.user_id,
            "optimisticVersion": self.optimistic_version,
        }


@dataclass(frozen=True, slots=True)
class ReadinessGateReference:
    global_id: UUID
    gate_key: str
    optimistic_version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "gate.globalId")
        object.__setattr__(self, "gate_key", _text(self.gate_key, "gate.gateKey", 128, pattern=_KEY))
        _positive(self.optimistic_version, "gate.optimisticVersion")
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "gate.snapshotHash"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "gateKey": self.gate_key,
            "optimisticVersion": self.optimistic_version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ReadinessSourceReference:
    requirement_key: str
    kind: ReadinessSourceKind
    state: ReadinessSourceState
    global_id: UUID | None
    source_version: int | None
    snapshot_hash: str | None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_key", _text(self.requirement_key, "sources.requirementKey", 128, pattern=_KEY))
        _enum(self.kind, ReadinessSourceKind, "sources.kind")
        _enum(self.state, ReadinessSourceState, "sources.state")
        object.__setattr__(self, "global_id", _optional_uuid(self.global_id, "sources.globalId"))
        if self.state is ReadinessSourceState.UNAVAILABLE:
            if self.global_id is not None or self.source_version is not None or self.snapshot_hash is not None:
                raise _problem("sources", _("Unavailable sources cannot claim an exact source identity."))
            if self.kind not in EXTERNAL_SOURCE_KINDS:
                raise _problem("sources.kind", _("Only an unavailable external provider may omit source identity."))
            object.__setattr__(self, "reason_code", _text(self.reason_code, "sources.reasonCode", 128, pattern=_KEY))
        else:
            if self.global_id is None:
                raise _problem("sources.globalId", _("Select an exact source object."))
            _positive(self.source_version, "sources.sourceVersion")
            object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "sources.snapshotHash"))
            object.__setattr__(self, "reason_code", _optional_text(self.reason_code, "sources.reasonCode", 128))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "requirementKey": self.requirement_key,
            "kind": self.kind.value,
            "state": self.state.value,
            "globalId": str(self.global_id) if self.global_id else None,
            "sourceVersion": self.source_version,
            "snapshotHash": self.snapshot_hash,
            "reasonCode": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class ReadinessItemSnapshot:
    global_id: UUID
    item_version: int
    definition: ReadinessItemDefinition
    applicable: bool
    gate: ReadinessGateReference
    owner: ReadinessMemberReference | None
    due_date: date | None
    state: ReadinessItemState
    confirmation_value: str | None
    sources: tuple[ReadinessSourceReference, ...]

    def __post_init__(self) -> None:
        _uuid(self.global_id, "items.globalId")
        _positive(self.item_version, "items.itemVersion")
        if not isinstance(self.definition, ReadinessItemDefinition):
            raise _problem("items.definition", _("Enter a valid readiness item definition."))
        if type(self.applicable) is not bool:
            raise _problem("items.applicable", _("Select a valid true or false value."))
        if not isinstance(self.gate, ReadinessGateReference) or self.gate.gate_key != self.definition.gate_key:
            raise _problem("items.gate", _("Select the exact Gate for this readiness item."))
        _enum(self.state, ReadinessItemState, "items.state")
        sources = _tuple_of(self.sources, ReadinessSourceReference, "items.sources", MAX_SOURCES)
        _unique(
            tuple((value.requirement_key, value.kind, value.global_id, value.source_version) for value in sources),
            "items.sources",
        )
        known_requirements = {value.key for value in self.definition.evidence_requirements}
        if any(value.requirement_key not in known_requirements for value in sources):
            raise _problem("items.sources.requirementKey", _("Select an evidence requirement from this item."))
        object.__setattr__(self, "sources", tuple(sorted(sources, key=lambda value: (value.requirement_key, value.kind.value, str(value.global_id or "")))))
        object.__setattr__(self, "confirmation_value", _optional_text(self.confirmation_value, "items.confirmationValue", 4_000))
        if not self.applicable:
            if self.state is not ReadinessItemState.NOT_APPLICABLE or self.owner is not None or self.due_date is not None:
                raise _problem("items.state", _("A non-applicable readiness item must remain not applicable."))
            if self.confirmation_value is not None or self.sources:
                raise _problem("items", _("A non-applicable readiness item cannot retain completion evidence."))
            return
        if self.state is ReadinessItemState.NOT_APPLICABLE:
            raise _problem("items.state", _("An applicable readiness item cannot be marked not applicable."))
        if not isinstance(self.owner, ReadinessMemberReference):
            raise _problem("items.owner", _("Select an enabled Project member."))
        if self.due_date is None:
            raise _problem("items.dueDate", _("Enter a due date."))
        _date(self.due_date, "items.dueDate")
        if self.state is ReadinessItemState.COMPLETE:
            if self.definition.completion_rule is ReadinessCompletionRule.CONFIRMATION and not self.confirmation_value:
                raise _problem("items.confirmationValue", _("Enter a confirmation before completing this item."))
            if not self.requirements_satisfied:
                raise _problem("items.sources", _("Resolve every required evidence source before completing this item."))
        if self.state is ReadinessItemState.FAILED and not any(value.state is ReadinessSourceState.FAILED for value in self.sources):
            raise _problem("items.sources", _("Bind the exact failed source before marking this item failed."))

    @property
    def requirements_satisfied(self) -> bool:
        for requirement in self.definition.evidence_requirements:
            count = sum(
                1
                for value in self.sources
                if value.requirement_key == requirement.key
                and value.kind in requirement.accepted_source_kinds
                and value.state is ReadinessSourceState.SATISFIED
            )
            if count < requirement.minimum_count:
                return False
        return True

    @property
    def has_failed_quality_result(self) -> bool:
        return any(value.kind in QUALITY_RESULT_KINDS and value.state is ReadinessSourceState.FAILED for value in self.sources)

    @property
    def has_required_unavailable_source(self) -> bool:
        for requirement in self.definition.evidence_requirements:
            values = tuple(value for value in self.sources if value.requirement_key == requirement.key)
            satisfied = sum(value.state is ReadinessSourceState.SATISFIED for value in values)
            if (
                requirement.unavailable_blocks
                and satisfied < requirement.minimum_count
                and any(value.state is ReadinessSourceState.UNAVAILABLE for value in values)
            ):
                return True
        return False

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "itemVersion": self.item_version,
            "definition": self.definition.snapshot_payload(),
            "applicable": self.applicable,
            "gate": self.gate.snapshot_payload(),
            "owner": self.owner.snapshot_payload() if self.owner else None,
            "dueDate": self.due_date.isoformat() if self.due_date else None,
            "state": self.state.value,
            "confirmationValue": self.confirmation_value,
            "sources": [value.snapshot_payload() for value in self.sources],
        }


@dataclass(frozen=True, slots=True)
class ReadinessScore:
    category_key: str | None
    earned_weight: int
    applicable_weight: int
    basis_points: int | None
    state: str

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "categoryKey": self.category_key,
            "earnedWeight": self.earned_weight,
            "applicableWeight": self.applicable_weight,
            "basisPoints": self.basis_points,
            "state": self.state,
        }


class ReadinessBlockerCode(StrEnum):
    INCOMPLETE_P0 = "incomplete_p0"
    FAILED_MANDATORY_QUALITY = "failed_mandatory_quality"
    REQUIRED_SOURCE_UNAVAILABLE = "required_source_unavailable"


@dataclass(frozen=True, slots=True)
class ReadinessBlocker:
    code: ReadinessBlockerCode
    item_global_id: UUID
    item_key: str
    gate: ReadinessGateReference

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "itemGlobalId": str(self.item_global_id),
            "itemKey": self.item_key,
            "gate": self.gate.snapshot_payload(),
        }


@dataclass(frozen=True, slots=True)
class ReadinessEvaluation:
    formula_version: str
    category_scores: tuple[ReadinessScore, ...]
    total_score: ReadinessScore
    blockers: tuple[ReadinessBlocker, ...]
    ready: bool

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "formulaVersion": self.formula_version,
            "categoryScores": [value.snapshot_payload() for value in self.category_scores],
            "totalScore": self.total_score.snapshot_payload(),
            "blockers": [value.snapshot_payload() for value in self.blockers],
            "ready": self.ready,
        }


def _score(items: Sequence[ReadinessItemSnapshot], category_key: str | None) -> ReadinessScore:
    applicable = tuple(
        item
        for item in items
        if item.applicable and (category_key is None or item.definition.category_key == category_key)
    )
    denominator = sum(item.definition.weight for item in applicable)
    earned = sum(item.definition.weight for item in applicable if item.state is ReadinessItemState.COMPLETE)
    if denominator == 0:
        return ReadinessScore(category_key, 0, 0, None, "not_applicable")
    basis_points = int(
        (Decimal(earned) * Decimal(10_000) / Decimal(denominator)).quantize(
            Decimal("1"), rounding=ROUND_HALF_EVEN
        )
    )
    return ReadinessScore(category_key, earned, denominator, basis_points, "scored")


def evaluate_readiness(
    categories: Sequence[ReadinessCategoryDefinition],
    items: Sequence[ReadinessItemSnapshot],
) -> ReadinessEvaluation:
    blockers: list[ReadinessBlocker] = []
    for item in items:
        if not item.applicable:
            continue
        if item.definition.blocking_level is ReadinessBlockingLevel.P0 and item.state is not ReadinessItemState.COMPLETE:
            blockers.append(ReadinessBlocker(ReadinessBlockerCode.INCOMPLETE_P0, item.global_id, item.definition.key, item.gate))
        if item.has_failed_quality_result:
            blockers.append(ReadinessBlocker(ReadinessBlockerCode.FAILED_MANDATORY_QUALITY, item.global_id, item.definition.key, item.gate))
        if item.has_required_unavailable_source:
            blockers.append(ReadinessBlocker(ReadinessBlockerCode.REQUIRED_SOURCE_UNAVAILABLE, item.global_id, item.definition.key, item.gate))
    ordered_blockers = tuple(sorted(blockers, key=lambda value: (value.gate.gate_key, value.item_key, value.code.value)))
    required_complete = all(
        not item.applicable or not item.definition.required or item.state is ReadinessItemState.COMPLETE
        for item in items
    )
    return ReadinessEvaluation(
        SCORE_FORMULA_VERSION,
        tuple(_score(items, category.key) for category in categories),
        _score(items, None),
        ordered_blockers,
        required_complete and not ordered_blockers,
    )


@dataclass(frozen=True, slots=True)
class ReadinessInstanceRevision:
    global_id: UUID
    instance_global_id: UUID
    tenant_id: str
    project: ReadinessProjectSnapshot
    template_revision: ReadinessExactReference
    instance_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    categories: tuple[ReadinessCategoryDefinition, ...]
    items: tuple[ReadinessItemSnapshot, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        _uuid(self.global_id, "globalId")
        _uuid(self.instance_global_id, "instanceGlobalId")
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, "tenantId", 128, pattern=_KEY))
        if not isinstance(self.project, ReadinessProjectSnapshot):
            raise _problem("project", _("Enter an exact Project snapshot."))
        if not isinstance(self.template_revision, ReadinessExactReference):
            raise _problem("templateRevision", _("Select an exact published readiness template version."))
        _positive(self.instance_version, "instanceVersion")
        object.__setattr__(self, "predecessor_global_id", _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"))
        object.__setattr__(self, "predecessor_snapshot_hash", _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"))
        if (self.instance_version == 1) != (self.predecessor_global_id is None and self.predecessor_snapshot_hash is None):
            raise _problem("predecessorGlobalId", _("Select the exact predecessor readiness revision."))
        categories = _tuple_of(self.categories, ReadinessCategoryDefinition, "categories", MAX_CATEGORIES)
        items = _tuple_of(self.items, ReadinessItemSnapshot, "items", MAX_ITEMS)
        if not categories or not items:
            raise _problem("items", _("Freeze at least one readiness category and item."))
        _unique(tuple(value.key.casefold() for value in categories), "categories")
        _unique(tuple(value.definition.key.casefold() for value in items), "items")
        category_keys = {value.key for value in categories}
        if any(value.definition.category_key not in category_keys for value in items):
            raise _problem("items.categoryKey", _("Select a category from this instance."))
        for item in items:
            expected = uuid5(self.instance_global_id, f"npi-readiness-item:{item.definition.key.casefold()}")
            if item.global_id != expected:
                raise _problem("items.globalId", _("The readiness item identity is invalid."))
            if item.applicable != item.definition.applicability.applies_to(self.project):
                raise _problem("items.applicable", _("Readiness item applicability does not match the frozen Project context."))
        object.__setattr__(self, "categories", categories)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "created_by_user_id", _email(self.created_by_user_id, "createdByUserId"))
        object.__setattr__(self, "created_at", _datetime(self.created_at, "createdAt"))
        _uuid(self.request_id, "requestId")
        object.__setattr__(self, "trace_id", _text(self.trace_id, "traceId", 128))

    @property
    def evaluation(self) -> ReadinessEvaluation:
        return evaluate_readiness(self.categories, self.items)

    @property
    def version_key_hash(self) -> str:
        return _sha256({"instanceGlobalId": str(self.instance_global_id), "instanceVersion": self.instance_version})

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "instanceGlobalId": str(self.instance_global_id),
            "tenantId": self.tenant_id,
            "project": self.project.snapshot_payload(),
            "templateRevision": self.template_revision.snapshot_payload(),
            "instanceVersion": self.instance_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "categories": [value.snapshot_payload() for value in self.categories],
            "items": [value.snapshot_payload() for value in self.items],
            "evaluation": self.evaluation.snapshot_payload(),
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "versionKeyHash": self.version_key_hash,
        }

    @property
    def snapshot_hash(self) -> str:
        return _sha256(self.snapshot_payload())


def initialize_readiness_instance(
    *,
    global_id: UUID,
    instance_global_id: UUID,
    tenant_id: str,
    project: ReadinessProjectSnapshot,
    template: ReadinessTemplateVersion,
    gates: Mapping[str, ReadinessGateReference],
    assignments: Mapping[str, tuple[ReadinessMemberReference, date]],
    created_by_user_id: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> ReadinessInstanceRevision:
    if template.publication_state is not ReadinessPublicationState.PUBLISHED:
        raise _problem("templateRevision", _("Select an exact published readiness template version."))
    if not template.applicability.applies_to(project):
        raise _problem("templateRevision", _("The readiness template does not apply to this Project."))
    if set(gates) != {value.gate_key for value in template.items}:
        raise _problem("gates", _("Resolve every configured Gate exactly once."))
    if set(assignments) != {value.key for value in template.items if value.applicability.applies_to(project)}:
        raise _problem("assignments", _("Assign every applicable readiness item exactly once."))
    items: list[ReadinessItemSnapshot] = []
    for definition in template.items:
        applicable = definition.applicability.applies_to(project)
        owner, due = assignments[definition.key] if applicable else (None, None)
        items.append(
            ReadinessItemSnapshot(
                global_id=uuid5(instance_global_id, f"npi-readiness-item:{definition.key.casefold()}"),
                item_version=1,
                definition=definition,
                applicable=applicable,
                gate=gates[definition.gate_key],
                owner=owner,
                due_date=due,
                state=ReadinessItemState.NOT_STARTED if applicable else ReadinessItemState.NOT_APPLICABLE,
                confirmation_value=None,
                sources=(),
            )
        )
    return ReadinessInstanceRevision(
        global_id=global_id,
        instance_global_id=instance_global_id,
        tenant_id=tenant_id,
        project=project,
        template_revision=ReadinessExactReference(template.global_id, template.template_version, template.snapshot_hash),
        instance_version=1,
        predecessor_global_id=None,
        predecessor_snapshot_hash=None,
        categories=template.categories,
        items=tuple(items),
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        request_id=request_id,
        trace_id=trace_id,
    )


def revise_readiness_item(
    current: ReadinessInstanceRevision,
    *,
    global_id: UUID,
    expected_instance_version: int,
    item_key: str,
    owner: ReadinessMemberReference,
    due_date: date,
    state: ReadinessItemState,
    confirmation_value: str | None,
    sources: tuple[ReadinessSourceReference, ...],
    created_by_user_id: str,
    created_at: datetime,
    request_id: UUID,
    trace_id: str,
) -> ReadinessInstanceRevision:
    if current.instance_version != expected_instance_version:
        raise ReadinessVersionConflict()
    key = _text(item_key, "itemKey", 128, pattern=_KEY)
    index = next((position for position, value in enumerate(current.items) if value.definition.key == key), None)
    if index is None:
        raise _problem("itemKey", _("Select a readiness item from this instance."))
    selected = current.items[index]
    if not selected.applicable:
        raise _problem("itemKey", _("A non-applicable readiness item cannot be revised."))
    successor = ReadinessItemSnapshot(
        global_id=selected.global_id,
        item_version=selected.item_version + 1,
        definition=selected.definition,
        applicable=True,
        gate=selected.gate,
        owner=owner,
        due_date=due_date,
        state=state,
        confirmation_value=confirmation_value,
        sources=sources,
    )
    items = list(current.items)
    items[index] = successor
    return ReadinessInstanceRevision(
        global_id=global_id,
        instance_global_id=current.instance_global_id,
        tenant_id=current.tenant_id,
        project=current.project,
        template_revision=current.template_revision,
        instance_version=current.instance_version + 1,
        predecessor_global_id=current.global_id,
        predecessor_snapshot_hash=current.snapshot_hash,
        categories=current.categories,
        items=tuple(items),
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        request_id=request_id,
        trace_id=trace_id,
    )


def validate_readiness_successor(current: ReadinessInstanceRevision, successor: ReadinessInstanceRevision) -> None:
    if (
        successor.instance_global_id != current.instance_global_id
        or successor.tenant_id != current.tenant_id
        or successor.project != current.project
        or successor.template_revision != current.template_revision
        or successor.instance_version != current.instance_version + 1
        or successor.predecessor_global_id != current.global_id
        or successor.predecessor_snapshot_hash != current.snapshot_hash
        or successor.categories != current.categories
    ):
        raise _problem("predecessorGlobalId", _("Select the exact current readiness revision."))
    changed = [
        (before, after)
        for before, after in zip(current.items, successor.items, strict=True)
        if before != after
    ]
    if len(current.items) != len(successor.items) or len(changed) != 1:
        raise _problem("items", _("A readiness successor must revise exactly one item."))
    before, after = changed[0]
    if (
        before.global_id != after.global_id
        or before.definition != after.definition
        or before.applicable != after.applicable
        or before.gate != after.gate
        or after.item_version != before.item_version + 1
    ):
        raise _problem("items", _("A readiness successor cannot change frozen item identity or policy."))


def template_from_snapshot(value: object) -> ReadinessTemplateVersion:
    record = _record(value, "template")
    return ReadinessTemplateVersion(
        global_id=UUID(_string(record, "globalId")),
        template_global_id=UUID(_string(record, "templateGlobalId")),
        template_code=_string(record, "templateCode"),
        template_version=_integer(record, "templateVersion"),
        optimistic_version=_integer(record, "optimisticVersion"),
        title=_string(record, "title"),
        publication_state=ReadinessPublicationState(_string(record, "publicationState")),
        applicability=_applicability_from_snapshot(record.get("applicability")),
        categories=tuple(_category_from_snapshot(item) for item in _array(record, "categories")),
        items=tuple(_item_definition_from_snapshot(item) for item in _array(record, "items")),
        changed_by_user_id=_string(record, "changedByUserId"),
        changed_at=_timestamp(record, "changedAt"),
        request_id=UUID(_string(record, "requestId")),
        trace_id=_string(record, "traceId"),
    )


def instance_from_snapshot(value: object) -> ReadinessInstanceRevision:
    record = _record(value, "instance")
    result = ReadinessInstanceRevision(
        global_id=UUID(_string(record, "globalId")),
        instance_global_id=UUID(_string(record, "instanceGlobalId")),
        tenant_id=_string(record, "tenantId"),
        project=_project_from_snapshot(record.get("project")),
        template_revision=_exact_from_snapshot(record.get("templateRevision")),
        instance_version=_integer(record, "instanceVersion"),
        predecessor_global_id=_uuid_or_none(record.get("predecessorGlobalId")),
        predecessor_snapshot_hash=_string_or_none(record.get("predecessorSnapshotHash")),
        categories=tuple(_category_from_snapshot(item) for item in _array(record, "categories")),
        items=tuple(_item_from_snapshot(item) for item in _array(record, "items")),
        created_by_user_id=_string(record, "createdByUserId"),
        created_at=_timestamp(record, "createdAt"),
        request_id=UUID(_string(record, "requestId")),
        trace_id=_string(record, "traceId"),
    )
    if record.get("evaluation") != result.evaluation.snapshot_payload() or record.get("versionKeyHash") != result.version_key_hash:
        raise _problem("evaluation", _("The stored readiness evaluation is not derived from the exact item snapshot."))
    return result


def _applicability_from_snapshot(value: object) -> ReadinessApplicabilitySelector:
    record = _record(value, "applicability")
    return ReadinessApplicabilitySelector(
        tuple(ProjectType(str(item)) for item in _array(record, "projectTypes")),
        tuple(str(item) for item in _array(record, "customerReferenceKeys")),
        tuple(str(item) for item in _array(record, "industryKeys")),
    )


def _category_from_snapshot(value: object) -> ReadinessCategoryDefinition:
    record = _record(value, "category")
    return ReadinessCategoryDefinition(_string(record, "key"), _string(record, "title"))


def _requirement_from_snapshot(value: object) -> ReadinessEvidenceRequirement:
    record = _record(value, "evidenceRequirement")
    return ReadinessEvidenceRequirement(
        _string(record, "key"),
        tuple(ReadinessSourceKind(str(item)) for item in _array(record, "acceptedSourceKinds")),
        _integer(record, "minimumCount"),
        _boolean(record, "unavailableBlocks"),
    )


def _item_definition_from_snapshot(value: object) -> ReadinessItemDefinition:
    record = _record(value, "itemDefinition")
    return ReadinessItemDefinition(
        key=_string(record, "key"),
        title=_string(record, "title"),
        category_key=_string(record, "categoryKey"),
        weight=_integer(record, "weight"),
        required=_boolean(record, "required"),
        blocking_level=ReadinessBlockingLevel(_string(record, "blockingLevel")),
        gate_key=_string(record, "gateKey"),
        completion_rule=ReadinessCompletionRule(_string(record, "completionRule")),
        applicability=_applicability_from_snapshot(record.get("applicability")),
        evidence_requirements=tuple(_requirement_from_snapshot(item) for item in _array(record, "evidenceRequirements")),
    )


def _project_from_snapshot(value: object) -> ReadinessProjectSnapshot:
    record = _record(value, "project")
    return ReadinessProjectSnapshot(
        UUID(_string(record, "globalId")),
        _integer(record, "optimisticVersion"),
        _string(record, "snapshotHash"),
        ProjectType(_string(record, "projectType")),
        tuple(str(item) for item in _array(record, "customerReferenceKeys")),
        _string(record, "industryKey"),
    )


def _exact_from_snapshot(value: object) -> ReadinessExactReference:
    record = _record(value, "reference")
    return ReadinessExactReference(UUID(_string(record, "globalId")), _integer(record, "version"), _string(record, "snapshotHash"))


def _gate_from_snapshot(value: object) -> ReadinessGateReference:
    record = _record(value, "gate")
    return ReadinessGateReference(UUID(_string(record, "globalId")), _string(record, "gateKey"), _integer(record, "optimisticVersion"), _string(record, "snapshotHash"))


def _member_from_snapshot(value: object) -> ReadinessMemberReference | None:
    if value is None:
        return None
    record = _record(value, "owner")
    return ReadinessMemberReference(UUID(_string(record, "globalId")), _string(record, "userId"), _integer(record, "optimisticVersion"))


def _source_from_snapshot(value: object) -> ReadinessSourceReference:
    record = _record(value, "source")
    return ReadinessSourceReference(
        requirement_key=_string(record, "requirementKey"),
        kind=ReadinessSourceKind(_string(record, "kind")),
        state=ReadinessSourceState(_string(record, "state")),
        global_id=_uuid_or_none(record.get("globalId")),
        source_version=_integer_or_none(record.get("sourceVersion")),
        snapshot_hash=_string_or_none(record.get("snapshotHash")),
        reason_code=_string_or_none(record.get("reasonCode")),
    )


def _item_from_snapshot(value: object) -> ReadinessItemSnapshot:
    record = _record(value, "item")
    due = _string_or_none(record.get("dueDate"))
    return ReadinessItemSnapshot(
        global_id=UUID(_string(record, "globalId")),
        item_version=_integer(record, "itemVersion"),
        definition=_item_definition_from_snapshot(record.get("definition")),
        applicable=_boolean(record, "applicable"),
        gate=_gate_from_snapshot(record.get("gate")),
        owner=_member_from_snapshot(record.get("owner")),
        due_date=date.fromisoformat(due) if due else None,
        state=ReadinessItemState(_string(record, "state")),
        confirmation_value=_string_or_none(record.get("confirmationValue")),
        sources=tuple(_source_from_snapshot(item) for item in _array(record, "sources")),
    )


def _record(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _problem(path, _("Enter a valid object."))
    return value


def _array(record: dict[str, object], key: str) -> list[object]:
    value = record.get(key)
    if not isinstance(value, list):
        raise _problem(key, _("Enter a valid list."))
    return value


def _string(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise _problem(key, _("Enter a value."))
    return value


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _problem("snapshot", _("Enter a valid value."))
    return value


def _integer(record: dict[str, object], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise _problem(key, _("Enter a positive integer."))
    return value


def _integer_or_none(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise _problem("snapshot", _("Enter a positive integer."))
    return value


def _boolean(record: dict[str, object], key: str) -> bool:
    value = record.get(key)
    if type(value) is not bool:
        raise _problem(key, _("Select a valid true or false value."))
    return value


def _uuid_or_none(value: object) -> UUID | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _problem("snapshot", _("Enter a valid global ID."))
    return UUID(value)


def _timestamp(record: dict[str, object], key: str) -> datetime:
    value = _string(record, key).replace("Z", "+00:00")
    return datetime.fromisoformat(value)
