from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol
from uuid import UUID

from npi_core.controlled_print.domain import (
    ControlledPrintContext,
    ControlledPrintSourceReference,
    ControlledPrintStateConflict,
    ControlledPrintUnavailable,
    PrintCopyState,
    PrintDeliveryMode,
    freeze_controlled_print_source,
    sha256_json,
)


@dataclass(frozen=True, slots=True)
class ResolvedControlledPrintSource:
    """Exact server-owned source truth, frozen before template resolution."""

    project_global_id: UUID
    project_type_key: str
    gate_key: str | None
    reference: ControlledPrintSourceReference
    snapshot: Mapping[str, object]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_global_id, UUID)
            or self.project_global_id.version != 4
        ):
            raise RuntimeError(
                "Controlled print source returned an invalid Project identity."
            )
        if not isinstance(self.project_type_key, str) or not self.project_type_key:
            raise RuntimeError(
                "Controlled print source returned an invalid Project type."
            )
        if self.gate_key is not None and (
            not isinstance(self.gate_key, str) or not self.gate_key
        ):
            raise RuntimeError(
                "Controlled print source returned an invalid Gate identity."
            )
        if not isinstance(self.reference, ControlledPrintSourceReference):
            raise RuntimeError("Controlled print source returned an invalid reference.")
        frozen = freeze_controlled_print_source(self.snapshot)
        if sha256_json(frozen) != self.reference.source_snapshot_hash:
            raise RuntimeError(
                "Controlled print source returned a mismatched snapshot hash."
            )
        object.__setattr__(self, "snapshot", frozen)

    def context(
        self,
        *,
        tenant_id: str,
        language: str,
    ) -> ControlledPrintContext:
        return ControlledPrintContext(
            tenant_id=tenant_id,
            project_global_id=self.project_global_id,
            source_object_type=self.reference.source_object_type,
            project_type_key=self.project_type_key,
            gate_key=self.gate_key,
            source_state=self.reference.source_state,
            language=language,
            delivery_mode=PrintDeliveryMode.CONTROLLED_PDF,
            copy_state=PrintCopyState.NOT_NUMBERED,
        )


class ControlledPrintSourceAdapter(Protocol):
    """Closed server-code adapter; browser data can never supply an implementation."""

    source_object_type: str

    def resolve_exact(
        self,
        *,
        project_global_id: UUID,
        source_global_id: UUID,
    ) -> ResolvedControlledPrintSource | None: ...


class ControlledPrintSourceRegistry:
    """Immutable source-adapter registry with no production adapter by default."""

    def __init__(
        self,
        adapters: Sequence[ControlledPrintSourceAdapter] = (),
    ) -> None:
        registered: dict[str, ControlledPrintSourceAdapter] = {}
        for adapter in adapters:
            source_kind = getattr(adapter, "source_object_type", None)
            if not isinstance(source_kind, str) or not source_kind:
                raise ValueError(
                    "Controlled print adapters require a source object type."
                )
            if source_kind in registered:
                raise ValueError("Controlled print source object types must be unique.")
            registered[source_kind] = adapter
        self._adapters = MappingProxyType(registered)

    @property
    def source_object_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def resolve_exact(
        self,
        *,
        project_global_id: UUID,
        source_object_type: str,
        source_global_id: UUID,
        expected_source_version: int,
    ) -> ResolvedControlledPrintSource:
        adapter = self._adapters.get(source_object_type)
        if adapter is None:
            raise ControlledPrintUnavailable()
        source = adapter.resolve_exact(
            project_global_id=project_global_id,
            source_global_id=source_global_id,
        )
        if source is None:
            raise ControlledPrintUnavailable()
        if (
            source.project_global_id != project_global_id
            or source.reference.source_object_type != source_object_type
            or source.reference.source_global_id != source_global_id
        ):
            raise RuntimeError(
                "Controlled print adapter escaped its exact source scope."
            )
        if source.reference.source_version != expected_source_version:
            raise ControlledPrintStateConflict()
        return source


def default_controlled_print_source_registry() -> ControlledPrintSourceRegistry:
    """Return the intentionally empty foundation registry.

    Exact production source adapters are added only with their approved domain form.
    """

    return ControlledPrintSourceRegistry()
