from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .config import ReleasedSummaryProjectionConfiguration
from .domain import (
    ExternalProjectionState,
    ReleasedSummaryProjectionContractError,
    ReleasedSummaryProjectionResult,
    ReleasedSummarySourceDescriptor,
    ReleasedSummarySourceState,
    UnavailableReason,
)


class ReleasedSummarySourceReader(Protocol):
    """Project-first source reader implemented only by checkpoint 2."""

    def read_current_source(
        self,
        *,
        project_global_id: UUID,
        summary_revision_global_id: UUID,
    ) -> ReleasedSummarySourceDescriptor | None: ...


class ReleasedSummaryProjectionAdapter(Protocol):
    def project(
        self,
        source: ReleasedSummarySourceDescriptor,
        *,
        trace_id: str,
    ) -> ReleasedSummaryProjectionResult: ...


class ContractHeldReleasedSummaryProjectionAdapter:
    """Network-free seam while DR-REC-009 and the external profile remain held."""

    def __init__(
        self,
        configuration: ReleasedSummaryProjectionConfiguration | None = None,
    ) -> None:
        self.configuration = configuration or ReleasedSummaryProjectionConfiguration()
        if not isinstance(self.configuration, ReleasedSummaryProjectionConfiguration):
            raise ReleasedSummaryProjectionContractError(
                "Released summary projection configuration is invalid."
            )

    def project(
        self,
        source: ReleasedSummarySourceDescriptor,
        *,
        trace_id: str,
    ) -> ReleasedSummaryProjectionResult:
        if not isinstance(source, ReleasedSummarySourceDescriptor):
            raise ReleasedSummaryProjectionContractError(
                "Released summary projection source is invalid."
            )
        return ReleasedSummaryProjectionResult(
            source_state=ReleasedSummarySourceState.CURRENT,
            external_projection_state=ExternalProjectionState.UNAVAILABLE,
            unavailable_reason=UnavailableReason.EXTERNAL_CONTRACT_HELD,
            trace_id=trace_id,
            source=source,
        )

    def source_unavailable(self, *, trace_id: str) -> ReleasedSummaryProjectionResult:
        return ReleasedSummaryProjectionResult(
            source_state=ReleasedSummarySourceState.UNAVAILABLE,
            external_projection_state=ExternalProjectionState.UNAVAILABLE,
            unavailable_reason=UnavailableReason.SOURCE_UNAVAILABLE,
            trace_id=trace_id,
        )

    def source_conflict(self, *, trace_id: str) -> ReleasedSummaryProjectionResult:
        return ReleasedSummaryProjectionResult(
            source_state=ReleasedSummarySourceState.CONFLICT,
            external_projection_state=ExternalProjectionState.UNAVAILABLE,
            unavailable_reason=UnavailableReason.SOURCE_CONFLICT,
            trace_id=trace_id,
        )
