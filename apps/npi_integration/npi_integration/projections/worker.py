from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from .domain import (
    ProjectionApplyOutcome,
    ProjectionReaderResult,
    ProjectionRefreshTarget,
)
from .readers import ProjectionReaderRegistry


MAX_PROJECT_REFRESH_TARGETS = 200


class ProjectionRefreshRepository(Protocol):
    def enumerate_refresh_targets(
        self, project_global_id: UUID
    ) -> Sequence[ProjectionRefreshTarget]: ...

    def apply_observation(
        self,
        *,
        project_global_id: UUID,
        target: ProjectionRefreshTarget,
        result: ProjectionReaderResult,
        event_id: UUID,
        received_at: datetime,
        correlation_id: UUID,
    ) -> ProjectionApplyOutcome: ...


@dataclass(frozen=True, slots=True)
class ProjectionRefreshBatch:
    project_global_id: UUID
    outcomes: tuple[ProjectionApplyOutcome, ...]


def refresh_project_projections(
    *,
    repository: ProjectionRefreshRepository,
    registry: ProjectionReaderRegistry,
    project_global_id: UUID,
    clock: Callable[[], datetime] | None = None,
    uuid_factory: Callable[[], UUID] | None = None,
) -> ProjectionRefreshBatch:
    """Run one bounded internal refresh; no scheduling or transport is hidden here."""

    now = (clock or (lambda: datetime.now(UTC)))()
    new_uuid = uuid_factory or uuid4
    correlation_id = new_uuid()
    targets = tuple(repository.enumerate_refresh_targets(project_global_id))
    if len(targets) > MAX_PROJECT_REFRESH_TARGETS:
        raise ValueError("ERP projection refresh scope exceeds its safe bound.")
    identities = {
        (
            target.context.tenant_id,
            target.context.project_global_id,
            target.context.scope_kind,
            target.context.scope_global_id,
            target.kind,
            target.source_object_id,
        )
        for target in targets
    }
    if len(identities) != len(targets):
        raise ValueError("ERP projection refresh targets are ambiguous.")
    outcomes = []
    for target in targets:
        result = registry.read(target)
        outcomes.append(
            repository.apply_observation(
                project_global_id=project_global_id,
                target=target,
                result=result,
                event_id=new_uuid(),
                received_at=now,
                correlation_id=correlation_id,
            )
        )
    return ProjectionRefreshBatch(project_global_id, tuple(outcomes))
