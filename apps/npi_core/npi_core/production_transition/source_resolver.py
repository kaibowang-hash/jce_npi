from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.production_transition.domain import (
    HandoverSourceKind,
    HandoverSourceReference,
    ObservationReferenceUsage,
    ObservationSourceReference,
    PolicyPublicationState,
    ProductionTransitionPolicyVersion,
)
from npi_core.production_transition.request_validation import (
    ExactSourceSelection,
    ManifestSourceSelection,
)

try:
    from frappe import _
except ImportError:  # Keeps source resolution independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class SourceResolutionContext:
    """Server-owned scope established only after Project-first authorization."""

    tenant_id: str
    project_global_id: UUID


@dataclass(frozen=True, slots=True)
class ResolvedTransitionSource:
    """Exact current server truth returned by one closed repository seam."""

    kind: HandoverSourceKind
    global_id: UUID
    source_version: int
    snapshot_hash: str


class TransitionSourceRepository(Protocol):
    """Closed adapters for the nine governed NPI source kinds."""

    def load_readiness_instance_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_domain_work_item(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_released_document(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_release_baseline(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_file_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_tooling_capacity_scenario(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_trial_defect_revision(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_trial_review_reference(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...

    def load_trial_conclusion(
        self,
        context: SourceResolutionContext,
        global_id: UUID,
        *,
        for_update: bool,
    ) -> ResolvedTransitionSource | None: ...


SOURCE_LOADER_SEAMS: Mapping[HandoverSourceKind, str] = MappingProxyType(
    {
        HandoverSourceKind.READINESS_INSTANCE_REVISION: (
            "load_readiness_instance_revision"
        ),
        HandoverSourceKind.DOMAIN_WORK_ITEM: "load_domain_work_item",
        HandoverSourceKind.RELEASED_DOCUMENT: "load_released_document",
        HandoverSourceKind.RELEASE_BASELINE: "load_release_baseline",
        HandoverSourceKind.FILE_REVISION: "load_file_revision",
        HandoverSourceKind.TOOLING_CAPACITY_SCENARIO: (
            "load_tooling_capacity_scenario"
        ),
        HandoverSourceKind.TRIAL_DEFECT_REVISION: "load_trial_defect_revision",
        HandoverSourceKind.TRIAL_REVIEW_REFERENCE: "load_trial_review_reference",
        HandoverSourceKind.TRIAL_CONCLUSION: "load_trial_conclusion",
    }
)


def resolve_exact_source(
    selection: ExactSourceSelection | ManifestSourceSelection,
    *,
    context: SourceResolutionContext,
    repository: TransitionSourceRepository,
    for_update: bool = True,
    path: str = "source",
) -> ResolvedTransitionSource:
    """Resolve one selected identity and reject current-version drift."""

    _validate_context(context, path)
    kind, global_id, expected_version = _selection_identity(selection, path)
    if type(for_update) is not bool:
        raise RuntimeError("Production transition source lock mode is invalid.")
    loader_name = SOURCE_LOADER_SEAMS[kind]
    loader = getattr(repository, loader_name, None)
    if not callable(loader):
        raise RuntimeError("Production transition source repository is incomplete.")
    source = loader(context, global_id, for_update=for_update)
    if not _is_exact_source(source, kind, global_id, expected_version):
        raise _unavailable(path)
    assert isinstance(source, ResolvedTransitionSource)
    return source


def resolve_manifest_sources(
    selections: tuple[ManifestSourceSelection, ...],
    *,
    policy: ProductionTransitionPolicyVersion,
    context: SourceResolutionContext,
    repository: TransitionSourceRepository,
    for_update: bool = True,
) -> tuple[HandoverSourceReference, ...]:
    """Resolve Scheme A selections and inject each published requirement's role."""

    if (
        not isinstance(policy, ProductionTransitionPolicyVersion)
        or policy.publication_state is not PolicyPublicationState.PUBLISHED
    ):
        raise _field(
            "policyRef",
            _("Select an exact published policy version."),
        )
    requirements = {value.key: value for value in policy.handover_requirements}
    planned: list[
        tuple[ManifestSourceSelection, HandoverSourceKind, str, str]
    ] = []
    identities: set[tuple[HandoverSourceKind, UUID]] = set()
    counts: Counter[str] = Counter()
    for index, selection in enumerate(selections):
        path = f"manifestSources[{index}]"
        kind, global_id, _expected_version = _selection_identity(selection, path)
        if not isinstance(selection, ManifestSourceSelection):
            raise _unavailable(path)
        requirement = requirements.get(selection.requirement_key)
        if requirement is None:
            raise _field(
                f"{path}.requirementKey",
                _("Select a handover requirement defined by this policy."),
            )
        if kind not in requirement.accepted_source_kinds:
            raise _field(
                f"{path}.kind",
                _("Select only source kinds allowed by the handover requirement."),
            )
        identity = (kind, global_id)
        if identity in identities:
            raise _field("manifestSources", _("Values must be unique."))
        identities.add(identity)
        counts[requirement.key] += 1
        planned.append(
            (selection, kind, requirement.key, requirement.manifest_role)
        )
    if any(
        counts[requirement.key] < requirement.minimum_count
        for requirement in policy.handover_requirements
    ):
        raise _field(
            "manifestSources",
            _("Select the exact required handover objects."),
        )

    references = []
    for index, (selection, kind, requirement_key, manifest_role) in enumerate(
        planned
    ):
        source = resolve_exact_source(
            selection,
            context=context,
            repository=repository,
            for_update=for_update,
            path=f"manifestSources[{index}]",
        )
        references.append(
            HandoverSourceReference(
                requirement_key=requirement_key,
                kind=kind,
                global_id=source.global_id,
                source_version=source.source_version,
                snapshot_hash=source.snapshot_hash,
                role=manifest_role,
            )
        )
    return tuple(references)


def resolve_observation_sources(
    context_selections: tuple[ExactSourceSelection, ...],
    retrospective_selections: tuple[ExactSourceSelection, ...],
    *,
    context: SourceResolutionContext,
    repository: TransitionSourceRepository,
    for_update: bool = True,
) -> tuple[
    tuple[ObservationSourceReference, ...],
    tuple[ObservationSourceReference, ...],
]:
    """Resolve observation references once per identity and fix only their usage."""

    plans = (
        (
            "contextSources",
            context_selections,
            ObservationReferenceUsage.CONTEXT,
        ),
        (
            "retrospectiveSources",
            retrospective_selections,
            ObservationReferenceUsage.RETROSPECTIVE,
        ),
    )
    expected_by_identity: dict[tuple[HandoverSourceKind, UUID], int] = {}
    first_path_by_identity: dict[tuple[HandoverSourceKind, UUID], str] = {}
    validated: list[
        tuple[
            str,
            tuple[
                tuple[ExactSourceSelection, HandoverSourceKind, UUID], ...
            ],
            ObservationReferenceUsage,
        ]
    ] = []
    for list_path, selections, usage in plans:
        list_identities: set[tuple[HandoverSourceKind, UUID]] = set()
        items = []
        for index, selection in enumerate(selections):
            path = f"{list_path}[{index}]"
            kind, global_id, expected_version = _selection_identity(selection, path)
            if not isinstance(selection, ExactSourceSelection):
                raise _unavailable(path)
            identity = (kind, global_id)
            if identity in list_identities:
                raise _field(list_path, _("Values must be unique."))
            list_identities.add(identity)
            prior_version = expected_by_identity.get(identity)
            if prior_version is not None and prior_version != expected_version:
                raise _unavailable(path)
            expected_by_identity[identity] = expected_version
            first_path_by_identity.setdefault(identity, path)
            items.append((selection, kind, global_id))
        validated.append((list_path, tuple(items), usage))

    resolved_by_identity: dict[
        tuple[HandoverSourceKind, UUID], ResolvedTransitionSource
    ] = {}
    for _list_path, items, _usage in validated:
        for selection, kind, global_id in items:
            identity = (kind, global_id)
            if identity not in resolved_by_identity:
                resolved_by_identity[identity] = resolve_exact_source(
                    selection,
                    context=context,
                    repository=repository,
                    for_update=for_update,
                    path=first_path_by_identity[identity],
                )

    results = []
    for _list_path, items, usage in validated:
        results.append(
            tuple(
                ObservationSourceReference(
                    kind=kind,
                    global_id=resolved_by_identity[(kind, global_id)].global_id,
                    source_version=resolved_by_identity[
                        (kind, global_id)
                    ].source_version,
                    snapshot_hash=resolved_by_identity[
                        (kind, global_id)
                    ].snapshot_hash,
                    usage=usage,
                )
                for _selection, kind, global_id in items
            )
        )
    return results[0], results[1]


def _selection_identity(
    selection: object,
    path: str,
) -> tuple[HandoverSourceKind, UUID, int]:
    if not isinstance(selection, (ExactSourceSelection, ManifestSourceSelection)):
        raise _unavailable(path)
    try:
        kind = HandoverSourceKind(selection.kind)
    except (TypeError, ValueError):
        raise _unavailable(path) from None
    if (
        not isinstance(selection.global_id, UUID)
        or selection.global_id.int == 0
        or type(selection.expected_version) is not int
        or selection.expected_version < 1
    ):
        raise _unavailable(path)
    return kind, selection.global_id, selection.expected_version


def _validate_context(context: object, path: str) -> None:
    if (
        not isinstance(context, SourceResolutionContext)
        or not isinstance(context.tenant_id, str)
        or not context.tenant_id.strip()
        or not isinstance(context.project_global_id, UUID)
        or context.project_global_id.int == 0
    ):
        raise _unavailable(path)


def _is_exact_source(
    source: object,
    kind: HandoverSourceKind,
    global_id: UUID,
    expected_version: int,
) -> bool:
    return (
        isinstance(source, ResolvedTransitionSource)
        and source.kind is kind
        and source.global_id == global_id
        and type(source.source_version) is int
        and source.source_version == expected_version
        and isinstance(source.snapshot_hash, str)
        and _HASH.fullmatch(source.snapshot_hash) is not None
    )


def _unavailable(path: str) -> RequestValidationFailed:
    return _field(path, _("Select an exact source object."))


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
