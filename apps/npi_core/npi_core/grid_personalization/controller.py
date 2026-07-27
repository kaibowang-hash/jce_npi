from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

try:
    from frappe import _
except ImportError:

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation

from npi_core.grid_personalization.domain import (
    GridFilterSnapshot,
    PersonalGridPreference,
    expected_version,
)


@dataclass(frozen=True, slots=True)
class PersonalPreferenceLoad:
    preference: PersonalGridPreference
    source: str
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.source not in {"default", "stored"}:
            raise ValueError("The preference source is invalid.")
        if self.reason_code not in {None, "stored_preference_invalid"}:
            raise ValueError("The preference reason is invalid.")


class PersonalGridPreferenceRepository(Protocol):
    def load(self) -> PersonalPreferenceLoad: ...

    def accessible_project_ids(self) -> frozenset[UUID]: ...

    def save(
        self,
        preference: PersonalGridPreference,
        *,
        expected_version: int,
        changed_view_id: str,
    ) -> PersonalGridPreference: ...


class GridPersonalizationController:
    """Coordinate actor-bound preference validation and access filtering."""

    def __init__(self, repository: PersonalGridPreferenceRepository) -> None:
        self.repository = repository

    def get(self) -> dict[str, object]:
        loaded = self.repository.load()
        accessible = self.repository.accessible_project_ids()
        effective = loaded.preference.effective_for(accessible)
        return effective.response_dict(recovery_reason=loaded.reason_code)

    def put(
        self,
        *,
        expected_preference_version: object,
        table_schema_version: object,
        view_id: object,
        layout: object,
        filter_snapshot: object,
        save_filter: object,
        favorite_view_ids: object,
        recent_view_ids: object,
        default_project_id: object,
    ) -> dict[str, object]:
        parsed_expected_version = expected_version(expected_preference_version)
        loaded = self.repository.load()
        if loaded.preference.version != parsed_expected_version:
            from npi_core.foundation.errors import VersionConflict

            raise VersionConflict()

        from npi_core.grid_personalization.domain import TABLE_SCHEMA_VERSION

        if table_schema_version != TABLE_SCHEMA_VERSION:
            from npi_core.grid_personalization.domain import (
                GridPersonalizationValidationError,
            )

            raise GridPersonalizationValidationError(
                "tableSchemaVersion",
                _("Select the supported My Work table schema."),
            )

        accessible = self.repository.accessible_project_ids()
        submitted_filter = GridFilterSnapshot.parse(filter_snapshot)
        if (
            submitted_filter.project_id is not None
            and submitted_filter.project_id not in accessible
        ):
            from npi_core.grid_personalization.domain import (
                GridPersonalizationValidationError,
            )

            raise GridPersonalizationValidationError(
                "filter.projectId",
                _("Select a Project available in My Work."),
            )
        current = loaded.preference.effective_for(accessible)
        updated = current.update(
            view_id=view_id,
            layout=layout,
            filter_snapshot=filter_snapshot,
            save_filter=save_filter,
            favorite_view_ids=favorite_view_ids,
            recent_view_ids=recent_view_ids,
            default_project_id=default_project_id,
        )
        inaccessible = updated.referenced_project_ids() - accessible
        if inaccessible:
            from npi_core.grid_personalization.domain import (
                GridPersonalizationValidationError,
            )

            raise GridPersonalizationValidationError(
                (
                    "defaultProjectId"
                    if updated.default_project_id in inaccessible
                    else "filter.projectId"
                ),
                _("Select a Project available in My Work."),
            )
        saved = self.repository.save(
            updated,
            expected_version=parsed_expected_version,
            changed_view_id=str(view_id),
        )
        return saved.response_dict()
