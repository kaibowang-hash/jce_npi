from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.readiness.domain import (
    EXTERNAL_SOURCE_KINDS,
    ReadinessSourceKind,
    ReadinessSourceReference,
    ReadinessSourceState,
)
from npi_core.readiness.request_validation import ReadinessSourceRequest

try:
    from frappe import _
except ImportError:  # Keeps exact-source resolution independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_REASON_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EXTERNAL_UNAVAILABLE_REASON_CODES = {
    ReadinessSourceKind.ERP_MATERIAL_SPECIFICATION: (
        "erp_material_specification_provider_unavailable"
    ),
    ReadinessSourceKind.ERP_QUALITY_RESULT: "erp_quality_result_provider_unavailable",
    ReadinessSourceKind.ERP_RUN_AT_RATE: "erp_run_at_rate_provider_unavailable",
    ReadinessSourceKind.ERP_HR_QUALIFICATION: "erp_hr_qualification_provider_unavailable",
    ReadinessSourceKind.ERP_SUPPLIER_EXECUTION: "erp_supplier_execution_provider_unavailable",
}


@dataclass(frozen=True, slots=True)
class SourceResolutionContext:
    """Server-owned Project containment established before source resolution."""

    tenant_id: str
    project_global_id: UUID


@dataclass(frozen=True, slots=True)
class ExactSourceQuery:
    """The complete source identity; repositories must never substitute a latest row."""

    kind: ReadinessSourceKind
    global_id: UUID
    source_version: int
    snapshot_hash: str


@dataclass(frozen=True, slots=True)
class ExactSourceObservation:
    """One repository-resolved exact fact with an explicit existing disposition."""

    tenant_id: str
    project_global_id: UUID
    kind: ReadinessSourceKind
    global_id: UUID
    source_version: int
    snapshot_hash: str
    disposition: ReadinessSourceState | None
    reason_code: str | None = None


class ExactSourceRepository(Protocol):
    """Adapter seam for existing Project/Work/Document/Tooling/Trial/File repositories.

    Implementations resolve only the supplied exact query and may expose a
    disposition only when the governed source already records it explicitly.
    """

    def get_exact_source(
        self,
        context: SourceResolutionContext,
        query: ExactSourceQuery,
    ) -> ExactSourceObservation | None: ...

    def authorize_exact_source(
        self,
        context: SourceResolutionContext,
        source: ExactSourceObservation,
    ) -> None: ...


def resolve_source(
    request: ReadinessSourceRequest,
    *,
    context: SourceResolutionContext,
    repository: ExactSourceRepository,
    path: str = "source",
) -> ReadinessSourceReference:
    """Resolve one source without accepting caller state or inferring report success."""

    _validate_context(context, path)
    if request.kind in EXTERNAL_SOURCE_KINDS:
        if (
            request.global_id is not None
            or request.source_version is not None
            or request.snapshot_hash is not None
        ):
            raise _unavailable(path)
        return ReadinessSourceReference(
            requirement_key=request.requirement_key,
            kind=request.kind,
            state=ReadinessSourceState.UNAVAILABLE,
            global_id=None,
            source_version=None,
            snapshot_hash=None,
            reason_code=EXTERNAL_UNAVAILABLE_REASON_CODES[request.kind],
        )

    if (
        not isinstance(request.global_id, UUID)
        or type(request.source_version) is not int
        or request.source_version < 1
        or not isinstance(request.snapshot_hash, str)
    ):
        raise _unavailable(path)
    query = ExactSourceQuery(
        kind=request.kind,
        global_id=request.global_id,
        source_version=request.source_version,
        snapshot_hash=request.snapshot_hash,
    )
    source = repository.get_exact_source(context, query)
    if not _is_exact_observation(source, context, query):
        raise _unavailable(path)
    assert isinstance(source, ExactSourceObservation)
    repository.authorize_exact_source(context, source)
    if not isinstance(source.disposition, ReadinessSourceState):
        raise _unavailable(path)
    if source.disposition not in (
        ReadinessSourceState.SATISFIED,
        ReadinessSourceState.FAILED,
    ):
        raise _unavailable(path)
    if source.reason_code is not None and (
        not isinstance(source.reason_code, str)
        or _REASON_CODE.fullmatch(source.reason_code) is None
    ):
        raise _unavailable(path)
    return ReadinessSourceReference(
        requirement_key=request.requirement_key,
        kind=request.kind,
        state=source.disposition,
        global_id=source.global_id,
        source_version=source.source_version,
        snapshot_hash=source.snapshot_hash,
        reason_code=source.reason_code,
    )


def resolve_sources(
    requests: tuple[ReadinessSourceRequest, ...],
    *,
    context: SourceResolutionContext,
    repository: ExactSourceRepository,
) -> tuple[ReadinessSourceReference, ...]:
    """Resolve a previously validated source list in the same deterministic order."""

    return tuple(
        resolve_source(
            request,
            context=context,
            repository=repository,
            path=f"sources[{index}]",
        )
        for index, request in enumerate(requests)
    )


def _validate_context(context: SourceResolutionContext, path: str) -> None:
    if (
        not isinstance(context.tenant_id, str)
        or not context.tenant_id.strip()
        or not isinstance(context.project_global_id, UUID)
    ):
        raise _unavailable(path)


def _is_exact_observation(
    source: object,
    context: SourceResolutionContext,
    query: ExactSourceQuery,
) -> bool:
    return (
        isinstance(source, ExactSourceObservation)
        and source.tenant_id == context.tenant_id
        and source.project_global_id == context.project_global_id
        and source.kind is query.kind
        and source.global_id == query.global_id
        and type(source.source_version) is int
        and source.source_version == query.source_version
        and source.snapshot_hash == query.snapshot_hash
    )


def _unavailable(path: str) -> RequestValidationFailed:
    # The same response covers missing, drifted, cross-Project and ambiguous facts.
    return RequestValidationFailed(
        [{"path": path, "message": _("Select an exact source object.")}]
    )
