from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from npi_core.controlled_print.domain import (
    ControlledPrintContext,
    ControlledPrintMappingUnavailable,
    ControlledPrintRegistryVersion,
    resolve_controlled_print_mapping,
)
from npi_core.controlled_print.source_registry import ControlledPrintSourceRegistry


@dataclass(frozen=True, slots=True)
class AuthorizedControlledPrintProject:
    global_id: UUID
    tenant_id: str
    project_type_key: str


class ControlledPrintCapabilityRepository(Protocol):
    def authorize_project(
        self,
        project_global_id: UUID,
    ) -> AuthorizedControlledPrintProject | None: ...

    def published_mapping_candidates(
        self,
        context: ControlledPrintContext,
        *,
        at: datetime,
    ) -> Sequence[ControlledPrintRegistryVersion]: ...


class ControlledPrintCapabilityService:
    """Resolve capability only after the opaque Project authorization boundary."""

    def __init__(
        self,
        *,
        repository: ControlledPrintCapabilityRepository,
        source_registry: ControlledPrintSourceRegistry,
        actor_user_id: str,
    ) -> None:
        self._repository = repository
        self._source_registry = source_registry
        self._actor_user_id = actor_user_id

    def capability(
        self,
        *,
        project_global_id: UUID,
        source_object_type: str,
        source_global_id: UUID,
        expected_source_version: int,
        language: str,
        at: datetime,
    ) -> dict[str, object] | None:
        project = self._repository.authorize_project(project_global_id)
        if project is None:
            return None
        source = self._source_registry.resolve_exact(
            project_global_id=project_global_id,
            source_object_type=source_object_type,
            source_global_id=source_global_id,
            expected_source_version=expected_source_version,
        )
        if source.project_type_key != project.project_type_key:
            raise RuntimeError(
                "Controlled print source Project type does not match its Project."
            )
        context = source.context(
            tenant_id=project.tenant_id,
            language=language,
        )
        try:
            mapping = resolve_controlled_print_mapping(
                self._repository.published_mapping_candidates(context, at=at),
                context,
                at=at,
            )
        except ControlledPrintMappingUnavailable:
            return _capability_response(
                context=context,
                source_global_id=source_global_id,
                source_version=expected_source_version,
                mapping=None,
                authorized=False,
            )
        authorized = mapping.authorizes(self._actor_user_id)
        return _capability_response(
            context=context,
            source_global_id=source_global_id,
            source_version=expected_source_version,
            mapping=mapping,
            authorized=authorized,
        )


def _capability_response(
    *,
    context: ControlledPrintContext,
    source_global_id: UUID,
    source_version: int,
    mapping: ControlledPrintRegistryVersion | None,
    authorized: bool,
) -> dict[str, object]:
    available = bool(mapping is not None and authorized)
    return {
        "available": available,
        "sourceKind": context.source_object_type,
        "sourceGlobalId": str(source_global_id),
        "sourceVersion": source_version,
        "language": context.language,
        "deliveryMode": context.delivery_mode.value if available else None,
        "copyState": context.copy_state.value if available else None,
        "registry": mapping.public_reference() if available and mapping else None,
        "permissions": {
            "create": available,
            "download": available,
        },
    }
