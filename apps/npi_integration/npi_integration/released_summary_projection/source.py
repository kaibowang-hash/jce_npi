from __future__ import annotations

from typing import Protocol
from uuid import UUID

from npi_core.trial.released_summary_domain import (
    released_trial_summary_from_snapshot,
    validate_released_trial_summary_successor,
)

from .domain import (
    ReleasedSummaryProjectionContractError,
    ReleasedSummarySourceDescriptor,
)


_WORKSPACE_KEYS = frozenset(
    {
        "projectGlobalId",
        "trialRound",
        "summaryRevisions",
        "currentSummaryRevisionGlobalId",
        "currentDecidedConclusion",
        "permissions",
        "controlledOutput",
        "holds",
    }
)
_MAX_REVISIONS = 10_000


class ReleasedSummaryWorkspaceRepository(Protocol):
    """Existing P7-07 Project-first repository boundary."""

    def summary_workspace(
        self,
        project_id: UUID,
        round_id: UUID,
    ) -> dict[str, object] | None: ...


class ReleasedSummarySourceConflict(ReleasedSummaryProjectionContractError):
    """Raised without disclosing a foreign, stale or malformed source value."""

    def __init__(self) -> None:
        super().__init__("Released summary source is not one exact current revision.")


class ProjectFirstReleasedSummarySourceReader:
    """Resolve one current P7-07 summary without copying its immutable domain."""

    def __init__(self, repository: ReleasedSummaryWorkspaceRepository) -> None:
        if not callable(getattr(repository, "summary_workspace", None)):
            raise ReleasedSummaryProjectionContractError(
                "Released summary source repository is invalid."
            )
        self._repository = repository

    def read_current_source(
        self,
        *,
        project_global_id: UUID,
        trial_round_global_id: UUID,
        summary_revision_global_id: UUID,
    ) -> ReleasedSummarySourceDescriptor | None:
        for name, value in (
            ("project_global_id", project_global_id),
            ("trial_round_global_id", trial_round_global_id),
            ("summary_revision_global_id", summary_revision_global_id),
        ):
            if not isinstance(value, UUID):
                raise ReleasedSummaryProjectionContractError(
                    f"{name} must be one exact UUID."
                )

        workspace = self._repository.summary_workspace(
            project_global_id,
            trial_round_global_id,
        )
        if workspace is None:
            return None
        return _current_descriptor(
            workspace,
            project_global_id=project_global_id,
            trial_round_global_id=trial_round_global_id,
            summary_revision_global_id=summary_revision_global_id,
        )


def _current_descriptor(
    workspace: object,
    *,
    project_global_id: UUID,
    trial_round_global_id: UUID,
    summary_revision_global_id: UUID,
) -> ReleasedSummarySourceDescriptor | None:
    if not isinstance(workspace, dict) or set(workspace) != _WORKSPACE_KEYS:
        raise ReleasedSummarySourceConflict()
    trial_round = workspace["trialRound"]
    if (
        workspace["projectGlobalId"] != str(project_global_id)
        or not isinstance(trial_round, dict)
        or trial_round.get("globalId") != str(trial_round_global_id)
    ):
        raise ReleasedSummarySourceConflict()

    revisions = workspace["summaryRevisions"]
    current_revision_id = workspace["currentSummaryRevisionGlobalId"]
    if not isinstance(revisions, list) or len(revisions) > _MAX_REVISIONS:
        raise ReleasedSummarySourceConflict()
    if not revisions:
        if current_revision_id is None:
            return None
        raise ReleasedSummarySourceConflict()
    if not isinstance(current_revision_id, str):
        raise ReleasedSummarySourceConflict()

    values = _parse_history(revisions)
    if (
        any(
            value.project_global_id != project_global_id
            or value.trial_round_global_id != trial_round_global_id
            for value in values
        )
        or len({value.summary_global_id for value in values}) != 1
        or len({value.global_id for value in values}) != len(values)
        or values[0].summary_version != 1
        or current_revision_id != str(values[-1].global_id)
        or values[-1].global_id != summary_revision_global_id
    ):
        raise ReleasedSummarySourceConflict()

    current = values[-1]
    return ReleasedSummarySourceDescriptor(
        project_global_id=current.project_global_id,
        summary_revision_global_id=current.global_id,
        summary_global_id=current.summary_global_id,
        trial_round_global_id=current.trial_round_global_id,
        summary_version=current.summary_version,
        snapshot_hash=current.snapshot_hash,
        source_manifest_hash=current.source_manifest_hash,
        presentation_projection_hash=current.presentation_projection_hash,
        redaction_manifest_hash=current.redaction_manifest_hash,
    )


def _parse_history(revisions: list[object]):
    try:
        values = tuple(released_trial_summary_from_snapshot(item) for item in revisions)
        for predecessor, successor in zip(values, values[1:], strict=False):
            validate_released_trial_summary_successor(predecessor, successor)
    except Exception as error:
        raise ReleasedSummarySourceConflict() from error
    return values
