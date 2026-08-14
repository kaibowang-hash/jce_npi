from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.production_transition.domain import (
    AcknowledgementDirection,
    AcknowledgementSlotDefinition,
    HandoverObjectRequirement,
    HandoverSourceKind,
    MetricComparator,
    ObservationProviderKind,
    ObservationSourceRule,
    ProductionTransitionApplicability,
    ReceivingGroupDefinition,
    TechnicalDisposition,
)
from npi_core.project.domain import ProjectType

try:
    from frappe import _
except ImportError:  # Keeps the closed request boundary independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


HANDOVER_SOURCE_KINDS = frozenset(
    {
        "readiness_instance_revision",
        "domain_work_item",
        "released_document",
        "release_baseline",
        "file_revision",
        "tooling_capacity_scenario",
        "trial_defect_revision",
        "trial_review_reference",
        "trial_conclusion",
    }
)
MANDATORY_EXTERNAL_PROVIDER_ORDER = (
    "actual_sop",
    "first_batch_yield",
    "customer_complaint",
    "production_cycle_time",
    "tooling_stability",
)
MANDATORY_EXTERNAL_PROVIDER_KINDS = frozenset(MANDATORY_EXTERNAL_PROVIDER_ORDER)
MAX_EXACT_SOURCES = 1_000
MAX_POLICY_COLLECTION = 100
MAX_SLOT_ROLE_KEYS = 100
MAX_APPLICABILITY_REFERENCES = 1_000

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")
_EXACT_SOURCE_FIELDS = frozenset({"kind", "globalId", "expectedVersion"})
_MANIFEST_SOURCE_FIELDS = _EXACT_SOURCE_FIELDS | frozenset({"requirementKey"})


@dataclass(frozen=True, slots=True)
class PolicyDefinitionRequest:
    """Closed, domain-compatible policy values without server-owned metadata."""

    applicability: ProductionTransitionApplicability
    receiving_groups: tuple[ReceivingGroupDefinition, ...]
    acknowledgement_slots: tuple[AcknowledgementSlotDefinition, ...]
    handover_requirements: tuple[HandoverObjectRequirement, ...]
    observation_source_rules: tuple[ObservationSourceRule, ...]
    observation_window_days: int


@dataclass(frozen=True, slots=True)
class CreatePolicyRequest:
    policy_code: str
    title: str
    definition: PolicyDefinitionRequest


@dataclass(frozen=True, slots=True)
class EditPolicyRequest:
    expected_optimistic_version: int
    title: str
    definition: PolicyDefinitionRequest


@dataclass(frozen=True, slots=True)
class PublishPolicyRequest:
    expected_optimistic_version: int
    expected_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class NextPolicyVersionRequest:
    expected_published_version: int
    expected_published_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class PolicyReferenceRequest:
    policy_global_id: UUID
    policy_version: int
    policy_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class SlotAssignmentSelection:
    slot_key: str
    member_global_id: UUID
    member_expected_version: int
    role_assignment_global_id: UUID
    role_expected_version: int


@dataclass(frozen=True, slots=True)
class HandoverContentRequest:
    expected_project_version: int
    policy: PolicyReferenceRequest
    slot_assignments: tuple[SlotAssignmentSelection, ...]
    manifest_sources: tuple[ManifestSourceSelection, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ReviseHandoverRequest:
    expected_revision_global_id: UUID
    expected_snapshot_hash: str
    content: HandoverContentRequest


@dataclass(frozen=True, slots=True)
class HandoverReferenceRequest:
    handover_global_id: UUID
    handover_version: int
    handover_revision_global_id: UUID
    handover_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class ExactSourceSelection:
    """One observation identity; its usage, projection and hash remain server-owned."""

    kind: str
    global_id: UUID
    expected_version: int


@dataclass(frozen=True, slots=True)
class ManifestSourceSelection:
    """One requirement-bound handover identity without caller role or source truth."""

    requirement_key: str
    kind: str
    global_id: UUID
    expected_version: int


@dataclass(frozen=True, slots=True)
class AcknowledgementIntent:
    """The only actor-independent acknowledgement values accepted from a caller."""

    expected_revision_global_id: UUID
    expected_snapshot_hash: str
    slot_key: str
    intent: str


@dataclass(frozen=True, slots=True)
class ObservationRevisionRequest:
    """Exact predecessor plus NPI review context; external actuals are not accepted."""

    expected_revision_global_id: UUID | None
    expected_snapshot_hash: str | None
    context_sources: tuple[ExactSourceSelection, ...]
    retrospective_sources: tuple[ExactSourceSelection, ...]
    retrospective_note: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class CreateObservationRequest:
    expected_project_version: int
    policy: PolicyReferenceRequest
    handover: HandoverReferenceRequest | None
    context_sources: tuple[ExactSourceSelection, ...]
    retrospective_sources: tuple[ExactSourceSelection, ...]
    retrospective_note: str | None
    reason: str


def closed_payload(
    value: object,
    path: str,
    allowed: frozenset[str],
    required: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Return a mapping only when supplied and required fields are closed."""

    if not isinstance(value, Mapping):
        raise _field(path, _("Enter a valid object."))
    required_fields = allowed if required is None else required
    unexpected = sorted(
        (name for name in value if not isinstance(name, str) or name not in allowed),
        key=str,
    )
    if unexpected:
        raise RequestValidationFailed(
            [
                {
                    "path": _child_path(path, str(name)),
                    "message": _("This field is not allowed."),
                }
                for name in unexpected
            ]
        )
    missing = sorted(required_fields - set(value))
    if missing:
        raise RequestValidationFailed(
            [
                {
                    "path": _child_path(path, name),
                    "message": _("This field is required."),
                }
                for name in missing
            ]
        )
    return dict(value)


def parse_policy_definition(
    value: object,
    path: str = "definition",
) -> PolicyDefinitionRequest:
    """Parse every caller-owned policy field and reject server-owned authority."""

    fields = frozenset(
        {
            "applicability",
            "receivingGroups",
            "acknowledgementSlots",
            "handoverRequirements",
            "observationSourceRules",
            "observationWindowDays",
        }
    )
    record = closed_payload(value, path, fields)
    return PolicyDefinitionRequest(
        applicability=_parse_applicability(
            record["applicability"],
            _child_path(path, "applicability"),
        ),
        receiving_groups=_parse_receiving_groups(
            record["receivingGroups"],
            _child_path(path, "receivingGroups"),
        ),
        acknowledgement_slots=_parse_acknowledgement_slots(
            record["acknowledgementSlots"],
            _child_path(path, "acknowledgementSlots"),
        ),
        handover_requirements=_parse_handover_requirements(
            record["handoverRequirements"],
            _child_path(path, "handoverRequirements"),
        ),
        observation_source_rules=_parse_observation_source_rules(
            record["observationSourceRules"],
            _child_path(path, "observationSourceRules"),
        ),
        observation_window_days=_bounded_positive(
            record["observationWindowDays"],
            _child_path(path, "observationWindowDays"),
            3_650,
        ),
    )


def parse_create_policy_request(
    value: object,
    path: str = "request",
) -> CreatePolicyRequest:
    record = closed_payload(
        value,
        path,
        frozenset({"policyCode", "title", "definition"}),
    )
    return CreatePolicyRequest(
        policy_code=_code(record["policyCode"], _child_path(path, "policyCode")),
        title=_text(record["title"], _child_path(path, "title"), 200),
        definition=parse_policy_definition(
            record["definition"],
            _child_path(path, "definition"),
        ),
    )


def parse_edit_policy_request(
    value: object,
    path: str = "request",
) -> EditPolicyRequest:
    record = closed_payload(
        value,
        path,
        frozenset({"expectedOptimisticVersion", "title", "definition"}),
    )
    return EditPolicyRequest(
        expected_optimistic_version=_positive(
            record["expectedOptimisticVersion"],
            _child_path(path, "expectedOptimisticVersion"),
        ),
        title=_text(record["title"], _child_path(path, "title"), 200),
        definition=parse_policy_definition(
            record["definition"],
            _child_path(path, "definition"),
        ),
    )


def parse_publish_policy_request(
    value: object,
    path: str = "request",
) -> PublishPolicyRequest:
    record = closed_payload(
        value,
        path,
        frozenset({"expectedOptimisticVersion", "expectedSnapshotHash"}),
    )
    return PublishPolicyRequest(
        expected_optimistic_version=_positive(
            record["expectedOptimisticVersion"],
            _child_path(path, "expectedOptimisticVersion"),
        ),
        expected_snapshot_hash=_hash(
            record["expectedSnapshotHash"],
            _child_path(path, "expectedSnapshotHash"),
        ),
    )


def parse_next_policy_version_request(
    value: object,
    path: str = "request",
) -> NextPolicyVersionRequest:
    record = closed_payload(
        value,
        path,
        frozenset({"expectedPublishedVersion", "expectedPublishedSnapshotHash"}),
    )
    return NextPolicyVersionRequest(
        expected_published_version=_positive(
            record["expectedPublishedVersion"],
            _child_path(path, "expectedPublishedVersion"),
        ),
        expected_published_snapshot_hash=_hash(
            record["expectedPublishedSnapshotHash"],
            _child_path(path, "expectedPublishedSnapshotHash"),
        ),
    )


def parse_policy_ref(
    value: object,
    path: str = "policy",
) -> PolicyReferenceRequest:
    record = closed_payload(
        value,
        path,
        frozenset({"policyGlobalId", "policyVersion", "policySnapshotHash"}),
    )
    return PolicyReferenceRequest(
        policy_global_id=_uuid(
            record["policyGlobalId"],
            _child_path(path, "policyGlobalId"),
        ),
        policy_version=_positive(
            record["policyVersion"],
            _child_path(path, "policyVersion"),
        ),
        policy_snapshot_hash=_hash(
            record["policySnapshotHash"],
            _child_path(path, "policySnapshotHash"),
        ),
    )


def parse_slot_assignments(
    value: object,
    path: str = "slotAssignments",
) -> tuple[SlotAssignmentSelection, ...]:
    records = _bounded_sequence(value, path, minimum=2, maximum=MAX_POLICY_COLLECTION)
    fields = frozenset(
        {
            "slotKey",
            "memberGlobalId",
            "memberExpectedVersion",
            "roleAssignmentGlobalId",
            "roleExpectedVersion",
        }
    )
    parsed: list[SlotAssignmentSelection] = []
    for index, item in enumerate(records):
        item_path = f"{path}[{index}]"
        record = closed_payload(item, item_path, fields)
        parsed.append(
            SlotAssignmentSelection(
                slot_key=_key(record["slotKey"], _child_path(item_path, "slotKey")),
                member_global_id=_uuid(
                    record["memberGlobalId"],
                    _child_path(item_path, "memberGlobalId"),
                ),
                member_expected_version=_positive(
                    record["memberExpectedVersion"],
                    _child_path(item_path, "memberExpectedVersion"),
                ),
                role_assignment_global_id=_uuid(
                    record["roleAssignmentGlobalId"],
                    _child_path(item_path, "roleAssignmentGlobalId"),
                ),
                role_expected_version=_positive(
                    record["roleExpectedVersion"],
                    _child_path(item_path, "roleExpectedVersion"),
                ),
            )
        )
    slot_keys = tuple(item.slot_key.casefold() for item in parsed)
    if len(set(slot_keys)) != len(slot_keys):
        raise _field(path, _("Values must be unique."))
    return tuple(parsed)


def parse_handover_content_request(
    value: object,
    path: str = "request",
) -> HandoverContentRequest:
    record = closed_payload(
        value,
        path,
        frozenset(
            {
                "expectedProjectVersion",
                "policy",
                "slotAssignments",
                "manifestSources",
                "reason",
            }
        ),
    )
    return HandoverContentRequest(
        expected_project_version=_positive(
            record["expectedProjectVersion"],
            _child_path(path, "expectedProjectVersion"),
        ),
        policy=parse_policy_ref(record["policy"], _child_path(path, "policy")),
        slot_assignments=parse_slot_assignments(
            record["slotAssignments"],
            _child_path(path, "slotAssignments"),
        ),
        manifest_sources=parse_manifest_source_selections(
            record["manifestSources"],
            _child_path(path, "manifestSources"),
        ),
        reason=_text(record["reason"], _child_path(path, "reason"), 1_000),
    )


def parse_create_handover_request(
    value: object,
    path: str = "request",
) -> HandoverContentRequest:
    return parse_handover_content_request(value, path)


def parse_handover_revision_request(
    value: object,
    path: str = "request",
) -> ReviseHandoverRequest:
    record = closed_payload(
        value,
        path,
        frozenset({"expectedRevisionGlobalId", "expectedSnapshotHash", "content"}),
    )
    return ReviseHandoverRequest(
        expected_revision_global_id=_uuid(
            record["expectedRevisionGlobalId"],
            _child_path(path, "expectedRevisionGlobalId"),
        ),
        expected_snapshot_hash=_hash(
            record["expectedSnapshotHash"],
            _child_path(path, "expectedSnapshotHash"),
        ),
        content=parse_handover_content_request(
            record["content"],
            _child_path(path, "content"),
        ),
    )


parse_revise_handover_request = parse_handover_revision_request


def parse_exact_source_selection(
    value: object,
    path: str = "source",
) -> ExactSourceSelection:
    """Accept only one closed registry tuple without a caller projection or hash."""

    record = closed_payload(value, path, _EXACT_SOURCE_FIELDS)
    kind = _closed_value(
        record["kind"],
        _child_path(path, "kind"),
        HANDOVER_SOURCE_KINDS,
    )
    return ExactSourceSelection(
        kind=kind,
        global_id=_uuid(record["globalId"], _child_path(path, "globalId")),
        expected_version=_positive(
            record["expectedVersion"],
            _child_path(path, "expectedVersion"),
        ),
    )


def parse_manifest_source_selection(
    value: object,
    path: str = "source",
) -> ManifestSourceSelection:
    """Accept a policy requirement plus exact source tuple, but no role or hash."""

    record = closed_payload(value, path, _MANIFEST_SOURCE_FIELDS)
    kind = _closed_value(
        record["kind"],
        _child_path(path, "kind"),
        HANDOVER_SOURCE_KINDS,
    )
    return ManifestSourceSelection(
        requirement_key=_key(
            record["requirementKey"],
            _child_path(path, "requirementKey"),
        ),
        kind=kind,
        global_id=_uuid(record["globalId"], _child_path(path, "globalId")),
        expected_version=_positive(
            record["expectedVersion"],
            _child_path(path, "expectedVersion"),
        ),
    )


def parse_manifest_source_selections(
    value: object,
    path: str = "manifestSources",
) -> tuple[ManifestSourceSelection, ...]:
    """Parse bounded handover selections without double-counting one exact source."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) < 1
        or len(value) > MAX_EXACT_SOURCES
    ):
        raise _field(path, _("Enter a valid bounded list."))
    parsed = tuple(
        parse_manifest_source_selection(item, f"{path}[{index}]")
        for index, item in enumerate(value)
    )
    identities = tuple((item.kind, item.global_id) for item in parsed)
    if len(set(identities)) != len(identities):
        raise _field(path, _("Values must be unique."))
    return parsed


def parse_exact_source_selections(
    value: object,
    path: str = "sources",
) -> tuple[ExactSourceSelection, ...]:
    """Parse a bounded, duplicate-free ordered exact-source selection."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > MAX_EXACT_SOURCES
    ):
        raise _field(path, _("Enter a valid bounded list."))
    parsed = tuple(
        parse_exact_source_selection(item, f"{path}[{index}]")
        for index, item in enumerate(value)
    )
    identities = tuple((item.kind, item.global_id) for item in parsed)
    if len(set(identities)) != len(identities):
        raise _field(path, _("Values must be unique."))
    return parsed


def parse_acknowledgement_intent(
    value: object,
    path: str = "acknowledgement",
) -> AcknowledgementIntent:
    """Reject caller actor, time, signature, approval and derived completion truth."""

    fields = frozenset(
        {
            "expectedRevisionGlobalId",
            "expectedSnapshotHash",
            "slotKey",
            "intent",
        }
    )
    record = closed_payload(value, path, fields)
    intent = _closed_value(
        record["intent"],
        _child_path(path, "intent"),
        frozenset({"acknowledge"}),
    )
    return AcknowledgementIntent(
        expected_revision_global_id=_uuid(
            record["expectedRevisionGlobalId"],
            _child_path(path, "expectedRevisionGlobalId"),
        ),
        expected_snapshot_hash=_hash(
            record["expectedSnapshotHash"],
            _child_path(path, "expectedSnapshotHash"),
        ),
        slot_key=_key(record["slotKey"], _child_path(path, "slotKey")),
        intent=intent,
    )


def parse_handover_ref(
    value: object,
    path: str = "handover",
) -> HandoverReferenceRequest:
    record = closed_payload(
        value,
        path,
        frozenset(
            {
                "handoverGlobalId",
                "handoverVersion",
                "handoverRevisionGlobalId",
                "handoverSnapshotHash",
            }
        ),
    )
    return HandoverReferenceRequest(
        handover_global_id=_uuid(
            record["handoverGlobalId"],
            _child_path(path, "handoverGlobalId"),
        ),
        handover_version=_positive(
            record["handoverVersion"],
            _child_path(path, "handoverVersion"),
        ),
        handover_revision_global_id=_uuid(
            record["handoverRevisionGlobalId"],
            _child_path(path, "handoverRevisionGlobalId"),
        ),
        handover_snapshot_hash=_hash(
            record["handoverSnapshotHash"],
            _child_path(path, "handoverSnapshotHash"),
        ),
    )


def parse_create_observation_request(
    value: object,
    path: str = "request",
) -> CreateObservationRequest:
    fields = frozenset(
        {
            "expectedProjectVersion",
            "policy",
            "handover",
            "contextSources",
            "retrospectiveSources",
            "retrospectiveNote",
            "reason",
        }
    )
    record = closed_payload(value, path, fields)
    evidence = _parse_observation_evidence(record, path)
    return CreateObservationRequest(
        expected_project_version=_positive(
            record["expectedProjectVersion"],
            _child_path(path, "expectedProjectVersion"),
        ),
        policy=parse_policy_ref(record["policy"], _child_path(path, "policy")),
        handover=(
            parse_handover_ref(record["handover"], _child_path(path, "handover"))
            if record["handover"] is not None
            else None
        ),
        context_sources=evidence.context_sources,
        retrospective_sources=evidence.retrospective_sources,
        retrospective_note=evidence.retrospective_note,
        reason=evidence.reason,
    )


parse_observation_create_request = parse_create_observation_request


def parse_observation_revision_request(
    value: object,
    *,
    successor: bool,
    path: str = "observation",
) -> ObservationRevisionRequest:
    """Parse an observation create/successor without accepting external truth."""

    predecessor_fields = frozenset(
        {"expectedRevisionGlobalId", "expectedSnapshotHash"}
    )
    fields = predecessor_fields | frozenset(
        {"contextSources", "retrospectiveSources", "retrospectiveNote", "reason"}
    )
    required = frozenset(
        {"contextSources", "retrospectiveSources", "retrospectiveNote", "reason"}
    ) | (
        predecessor_fields if successor else frozenset()
    )
    record = closed_payload(value, path, fields, required)
    if not successor and predecessor_fields & set(record):
        raise _field(path, _("This field is not allowed."))
    evidence = _parse_observation_evidence(record, path)
    return ObservationRevisionRequest(
        expected_revision_global_id=(
            _uuid(
                record["expectedRevisionGlobalId"],
                _child_path(path, "expectedRevisionGlobalId"),
            )
            if successor
            else None
        ),
        expected_snapshot_hash=(
            _hash(
                record["expectedSnapshotHash"],
                _child_path(path, "expectedSnapshotHash"),
            )
            if successor
            else None
        ),
        context_sources=evidence.context_sources,
        retrospective_sources=evidence.retrospective_sources,
        retrospective_note=evidence.retrospective_note,
        reason=evidence.reason,
    )


def _parse_observation_evidence(
    record: Mapping[str, object],
    path: str,
) -> ObservationRevisionRequest:
    retrospective_note = record["retrospectiveNote"]
    if retrospective_note is not None and (
        not isinstance(retrospective_note, str)
        or len(retrospective_note.strip()) > 4_000
    ):
        raise _field(
            _child_path(path, "retrospectiveNote"),
            _("Enter a valid value."),
        )
    reason = _text(record["reason"], _child_path(path, "reason"), 1_000)
    context_sources = parse_exact_source_selections(
        record["contextSources"],
        _child_path(path, "contextSources"),
    )
    retrospective_sources = parse_exact_source_selections(
        record["retrospectiveSources"],
        _child_path(path, "retrospectiveSources"),
    )
    context_versions = {
        (source.kind, source.global_id): source.expected_version
        for source in context_sources
    }
    if any(
        context_versions.get((source.kind, source.global_id), source.expected_version)
        != source.expected_version
        for source in retrospective_sources
    ):
        raise _field(
            _child_path(path, "retrospectiveSources"),
            _("Enter a valid value."),
        )
    return ObservationRevisionRequest(
        expected_revision_global_id=None,
        expected_snapshot_hash=None,
        context_sources=context_sources,
        retrospective_sources=retrospective_sources,
        retrospective_note=(
            retrospective_note.strip()
            if isinstance(retrospective_note, str)
            else None
        ),
        reason=reason,
    )


def assert_mandatory_provider_kinds(value: object, path: str = "providers") -> None:
    """Require the server-fixed provider set when validating internal assemblies."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise _field(path, _("Enter a valid bounded list."))
    actual = tuple(value)
    if actual != MANDATORY_EXTERNAL_PROVIDER_ORDER:
        raise _field(path, _("Select all required values exactly once."))


def _parse_applicability(
    value: object,
    path: str,
) -> ProductionTransitionApplicability:
    record = closed_payload(
        value,
        path,
        frozenset({"projectTypes", "projectGlobalIds", "customerReferenceKeys"}),
    )
    project_type_values = _bounded_sequence(
        record["projectTypes"],
        _child_path(path, "projectTypes"),
        minimum=1,
        maximum=20,
    )
    project_types: list[ProjectType] = []
    for index, item in enumerate(project_type_values):
        try:
            project_types.append(ProjectType(item))
        except (TypeError, ValueError) as error:
            raise _field(
                f"{_child_path(path, 'projectTypes')}[{index}]",
                _("Select a supported value."),
            ) from error
    if len(set(project_types)) != len(project_types):
        raise _field(_child_path(path, "projectTypes"), _("Values must be unique."))
    project_id_values = _bounded_sequence(
        record["projectGlobalIds"],
        _child_path(path, "projectGlobalIds"),
        maximum=MAX_APPLICABILITY_REFERENCES,
    )
    project_ids = tuple(
        _uuid(item, f"{_child_path(path, 'projectGlobalIds')}[{index}]")
        for index, item in enumerate(project_id_values)
    )
    if len(set(project_ids)) != len(project_ids):
        raise _field(
            _child_path(path, "projectGlobalIds"),
            _("Values must be unique."),
        )
    customer_key_values = _bounded_sequence(
        record["customerReferenceKeys"],
        _child_path(path, "customerReferenceKeys"),
        maximum=MAX_APPLICABILITY_REFERENCES,
    )
    customer_keys = tuple(
        _text(
            item,
            f"{_child_path(path, 'customerReferenceKeys')}[{index}]",
            256,
        )
        for index, item in enumerate(customer_key_values)
    )
    if len(set(customer_keys)) != len(customer_keys):
        raise _field(
            _child_path(path, "customerReferenceKeys"),
            _("Values must be unique."),
        )
    return ProductionTransitionApplicability(
        project_types=tuple(project_types),
        project_global_ids=project_ids,
        customer_reference_keys=customer_keys,
    )


def _parse_receiving_groups(
    value: object,
    path: str,
) -> tuple[ReceivingGroupDefinition, ...]:
    records = _bounded_sequence(value, path, maximum=MAX_POLICY_COLLECTION)
    parsed: list[ReceivingGroupDefinition] = []
    for index, item in enumerate(records):
        item_path = f"{path}[{index}]"
        record = closed_payload(item, item_path, frozenset({"key", "title"}))
        parsed.append(
            ReceivingGroupDefinition(
                key=_key(record["key"], _child_path(item_path, "key")),
                title=_text(record["title"], _child_path(item_path, "title"), 200),
            )
        )
    _require_unique_keys(parsed, path)
    return tuple(parsed)


def _parse_acknowledgement_slots(
    value: object,
    path: str,
) -> tuple[AcknowledgementSlotDefinition, ...]:
    records = _bounded_sequence(value, path, maximum=MAX_POLICY_COLLECTION)
    fields = frozenset(
        {"key", "groupKey", "direction", "allowedProjectRoleKeys"}
    )
    parsed: list[AcknowledgementSlotDefinition] = []
    for index, item in enumerate(records):
        item_path = f"{path}[{index}]"
        record = closed_payload(item, item_path, fields)
        direction_value = record["direction"]
        try:
            direction = AcknowledgementDirection(direction_value)
        except (TypeError, ValueError) as error:
            raise _field(
                _child_path(item_path, "direction"),
                _("Select a supported value."),
            ) from error
        role_values = _bounded_sequence(
            record["allowedProjectRoleKeys"],
            _child_path(item_path, "allowedProjectRoleKeys"),
            minimum=1,
            maximum=MAX_SLOT_ROLE_KEYS,
        )
        role_keys = tuple(
            _key(
                role,
                f"{_child_path(item_path, 'allowedProjectRoleKeys')}[{role_index}]",
            )
            for role_index, role in enumerate(role_values)
        )
        if len(set(role_keys)) != len(role_keys):
            raise _field(
                _child_path(item_path, "allowedProjectRoleKeys"),
                _("Values must be unique."),
            )
        parsed.append(
            AcknowledgementSlotDefinition(
                key=_key(record["key"], _child_path(item_path, "key")),
                group_key=_key(
                    record["groupKey"],
                    _child_path(item_path, "groupKey"),
                ),
                direction=direction,
                allowed_project_role_keys=role_keys,
            )
        )
    _require_unique_keys(parsed, path)
    return tuple(parsed)


def _parse_handover_requirements(
    value: object,
    path: str,
) -> tuple[HandoverObjectRequirement, ...]:
    records = _bounded_sequence(value, path, maximum=MAX_POLICY_COLLECTION)
    fields = frozenset(
        {"key", "acceptedSourceKinds", "manifestRole", "minimumCount"}
    )
    parsed: list[HandoverObjectRequirement] = []
    for index, item in enumerate(records):
        item_path = f"{path}[{index}]"
        record = closed_payload(item, item_path, fields)
        kind_values = _bounded_sequence(
            record["acceptedSourceKinds"],
            _child_path(item_path, "acceptedSourceKinds"),
            minimum=1,
            maximum=len(HandoverSourceKind),
        )
        kinds: list[HandoverSourceKind] = []
        for kind_index, kind_value in enumerate(kind_values):
            try:
                kinds.append(HandoverSourceKind(kind_value))
            except (TypeError, ValueError) as error:
                raise _field(
                    f"{_child_path(item_path, 'acceptedSourceKinds')}[{kind_index}]",
                    _("Select a supported value."),
                ) from error
        if len(set(kinds)) != len(kinds):
            raise _field(
                _child_path(item_path, "acceptedSourceKinds"),
                _("Values must be unique."),
            )
        parsed.append(
            HandoverObjectRequirement(
                key=_key(record["key"], _child_path(item_path, "key")),
                accepted_source_kinds=tuple(kinds),
                manifest_role=_key(
                    record["manifestRole"],
                    _child_path(item_path, "manifestRole"),
                ),
                minimum_count=_bounded_positive(
                    record["minimumCount"],
                    _child_path(item_path, "minimumCount"),
                    MAX_EXACT_SOURCES,
                ),
            )
        )
    _require_unique_keys(parsed, path)
    return tuple(parsed)


def _parse_observation_source_rules(
    value: object,
    path: str,
) -> tuple[ObservationSourceRule, ...]:
    records = _bounded_sequence(value, path, minimum=5, maximum=5)
    canonical_order = (
        ObservationProviderKind.ACTUAL_SOP,
        ObservationProviderKind.CUSTOMER_COMPLAINT,
        ObservationProviderKind.FIRST_BATCH_YIELD,
        ObservationProviderKind.PRODUCTION_CYCLE_TIME,
        ObservationProviderKind.TOOLING_STABILITY,
    )
    fields = frozenset(
        {"providerKind", "unit", "comparator", "threshold", "allowedDispositions"}
    )
    result: list[ObservationSourceRule] = []
    for index, (item, expected_kind) in enumerate(zip(records, canonical_order)):
        item_path = f"{path}[{index}]"
        record = closed_payload(item, item_path, fields)
        if record["providerKind"] != expected_kind.value:
            raise _field(
                _child_path(item_path, "providerKind"),
                _("Select all required values exactly once."),
            )
        dispositions = _parse_dispositions(
            record["allowedDispositions"],
            _child_path(item_path, "allowedDispositions"),
        )
        if expected_kind is ObservationProviderKind.ACTUAL_SOP:
            if any(record[field] is not None for field in ("unit", "comparator", "threshold")):
                raise _field(item_path, _("This field is not allowed."))
            result.append(
                ObservationSourceRule(
                    provider_kind=expected_kind,
                    allowed_dispositions=dispositions,
                )
            )
            continue
        comparator_value = record["comparator"]
        try:
            comparator = MetricComparator(comparator_value)
        except (TypeError, ValueError) as error:
            raise _field(
                _child_path(item_path, "comparator"),
                _("Select a supported value."),
            ) from error
        result.append(
            ObservationSourceRule(
                provider_kind=expected_kind,
                unit=_text(record["unit"], _child_path(item_path, "unit"), 32),
                comparator=comparator,
                threshold=_decimal(
                    record["threshold"],
                    _child_path(item_path, "threshold"),
                ),
                allowed_dispositions=dispositions,
            )
        )
    return tuple(result)


def _parse_dispositions(
    value: object,
    path: str,
) -> tuple[TechnicalDisposition, ...]:
    values = _bounded_sequence(value, path, minimum=1, maximum=4)
    result: list[TechnicalDisposition] = []
    for index, item in enumerate(values):
        try:
            result.append(TechnicalDisposition(item))
        except (TypeError, ValueError) as error:
            raise _field(
                f"{path}[{index}]",
                _("Select a supported value."),
            ) from error
    if len(set(result)) != len(result) or TechnicalDisposition.NOT_EVALUABLE not in result:
        raise _field(path, _("Select all required values exactly once."))
    return tuple(result)


def _require_unique_keys(values: Sequence[object], path: str) -> None:
    keys = tuple(str(getattr(value, "key")).casefold() for value in values)
    if len(set(keys)) != len(keys):
        raise _field(path, _("Values must be unique."))


def _bounded_sequence(
    value: object,
    path: str,
    *,
    minimum: int = 0,
    maximum: int,
) -> tuple[object, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) < minimum
        or len(value) > maximum
    ):
        raise _field(path, _("Enter a valid bounded list."))
    return tuple(value)


def _closed_value(value: object, path: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _field(path, _("Select a supported value."))
    return value


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != value.casefold():
        raise _field(path, _("Enter a valid global ID."))
    return parsed


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(path, _("Enter a positive integer."))
    return value


def _bounded_positive(value: object, path: str, maximum: int) -> int:
    parsed = _positive(value, path)
    if parsed > maximum:
        raise _field(path, _("Enter a valid value."))
    return parsed


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field(path, _("Enter a valid SHA-256 hash."))
    return value


def _key(value: object, path: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise _field(path, _("Enter a valid value."))
    return value


def _code(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid value."))
    normalized = value.strip()
    if _CODE.fullmatch(normalized) is None:
        raise _field(path, _("Enter a valid value."))
    return normalized


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field(path, _("Enter a valid value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field(path, _("Enter a valid value."))
    return normalized


def _decimal(value: object, path: str) -> Decimal:
    if not isinstance(value, str) or _DECIMAL.fullmatch(value) is None:
        raise _field(path, _("Enter a valid decimal value."))
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise _field(path, _("Enter a valid decimal value.")) from error
    if not result.is_finite():
        raise _field(path, _("Enter a valid decimal value."))
    return result.normalize()


def _child_path(path: str, field_name: str) -> str:
    return f"{path}.{field_name}" if path else field_name


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
