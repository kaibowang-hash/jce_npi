from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from .config import ProjectionAdapterConfiguration
from .domain import (
    AdapterMode,
    ProjectionAvailability,
    ProjectionContractError,
    ProjectionKind,
    ProjectionReaderResult,
    ProjectionRefreshTarget,
)


class ProjectionAdapterReader(Protocol):
    """Seven closed read seams; no generic DocType or endpoint operation."""

    def read_customer_master(
        self, target: ProjectionRefreshTarget
    ) -> ProjectionReaderResult: ...

    def read_supplier_master(
        self, target: ProjectionRefreshTarget
    ) -> ProjectionReaderResult: ...

    def read_formal_item_master(
        self, target: ProjectionRefreshTarget
    ) -> ProjectionReaderResult: ...

    def read_tooling_procurement_cost(
        self, target: ProjectionRefreshTarget
    ) -> ProjectionReaderResult: ...

    def read_project_cost(
        self, target: ProjectionRefreshTarget
    ) -> ProjectionReaderResult: ...

    def read_formal_quality_status(
        self, target: ProjectionRefreshTarget
    ) -> ProjectionReaderResult: ...

    def read_tool_asset_status(
        self, target: ProjectionRefreshTarget
    ) -> ProjectionReaderResult: ...


class ProjectionReaderRegistry:
    def __init__(
        self,
        *,
        configuration: ProjectionAdapterConfiguration,
        reader: ProjectionAdapterReader | None = None,
    ) -> None:
        if not isinstance(configuration, ProjectionAdapterConfiguration):
            raise ProjectionContractError("Projection adapter configuration is invalid.")
        self.configuration = configuration
        if reader is None:
            if configuration.mode is AdapterMode.MOCK:
                reader = MockProjectionReader()
            elif configuration.mode is AdapterMode.SANDBOX:
                reader = NoNetworkSandboxProjectionReader(
                    environment_code=configuration.environment_code
                )
            else:
                raise ProjectionContractError(
                    "Synthetic projection proof requires an injected disposable reader."
                )
        self.reader = reader

    def read(self, target: ProjectionRefreshTarget) -> ProjectionReaderResult:
        if not isinstance(target, ProjectionRefreshTarget):
            raise ProjectionContractError("Projection refresh target is invalid.")
        if (
            self.configuration.mode is AdapterMode.SANDBOX
            and target.kind not in self.configuration.allowed_operations
        ):
            return _unavailable(
                target,
                mode=AdapterMode.SANDBOX,
                environment=self.configuration.environment_code,
                reason="operation_not_enabled",
            )
        if target.kind is ProjectionKind.CUSTOMER_MASTER:
            result = self.reader.read_customer_master(target)
        elif target.kind is ProjectionKind.SUPPLIER_MASTER:
            result = self.reader.read_supplier_master(target)
        elif target.kind is ProjectionKind.FORMAL_ITEM_MASTER:
            result = self.reader.read_formal_item_master(target)
        elif target.kind is ProjectionKind.TOOLING_PROCUREMENT_COST:
            result = self.reader.read_tooling_procurement_cost(target)
        elif target.kind is ProjectionKind.PROJECT_COST:
            result = self.reader.read_project_cost(target)
        elif target.kind is ProjectionKind.FORMAL_QUALITY_STATUS:
            result = self.reader.read_formal_quality_status(target)
        elif target.kind is ProjectionKind.TOOL_ASSET_STATUS:
            result = self.reader.read_tool_asset_status(target)
        else:  # pragma: no cover - enum/catalog construction guard
            raise AssertionError(target.kind)
        if (
            not isinstance(result, ProjectionReaderResult)
            or result.kind is not target.kind
            or result.source_object_id != target.source_object_id
            or result.adapter_mode is not self.configuration.mode
        ):
            raise ProjectionContractError(
                "Projection reader result does not match its server-resolved target."
            )
        return result


class MockProjectionReader:
    def _read(self, target: ProjectionRefreshTarget) -> ProjectionReaderResult:
        return _unavailable(
            target,
            mode=AdapterMode.MOCK,
            environment="mock",
            reason="provider_unavailable",
        )

    read_customer_master = _read
    read_supplier_master = _read
    read_formal_item_master = _read
    read_tooling_procurement_cost = _read
    read_project_cost = _read
    read_formal_quality_status = _read
    read_tool_asset_status = _read


class NoNetworkSandboxProjectionReader:
    """Frozen sandbox protocol seam while the live ERP field mapper is held."""

    def __init__(self, *, environment_code: str) -> None:
        self.environment_code = environment_code

    def _read(self, target: ProjectionRefreshTarget) -> ProjectionReaderResult:
        return _unavailable(
            target,
            mode=AdapterMode.SANDBOX,
            environment=self.environment_code,
            reason="sandbox_mapper_unavailable",
        )

    read_customer_master = _read
    read_supplier_master = _read
    read_formal_item_master = _read
    read_tooling_procurement_cost = _read
    read_project_cost = _read
    read_formal_quality_status = _read
    read_tool_asset_status = _read


class SyntheticProjectionReader:
    """Disposable deterministic proof; results can never become formal truth."""

    def __init__(
        self,
        results: Mapping[ProjectionKind, ProjectionReaderResult],
    ) -> None:
        if not isinstance(results, Mapping):
            raise ProjectionContractError("Synthetic projection results are invalid.")
        copied = dict(results)
        if any(
            not isinstance(kind, ProjectionKind)
            or not isinstance(result, ProjectionReaderResult)
            or result.kind is not kind
            or result.adapter_mode is not AdapterMode.SYNTHETIC
            or result.availability is not ProjectionAvailability.SYNTHETIC
            for kind, result in copied.items()
        ):
            raise ProjectionContractError(
                "Synthetic projection results must remain non-authoritative."
            )
        self.results = copied

    def _read(self, target: ProjectionRefreshTarget) -> ProjectionReaderResult:
        result = self.results.get(target.kind)
        if result is None:
            raise ProjectionContractError(
                "Synthetic projection proof requires one exact injected result."
            )
        if result.source_object_id != target.source_object_id:
            raise ProjectionContractError(
                "Synthetic projection result does not match its server-resolved source."
            )
        return result

    read_customer_master = _read
    read_supplier_master = _read
    read_formal_item_master = _read
    read_tooling_procurement_cost = _read
    read_project_cost = _read
    read_formal_quality_status = _read
    read_tool_asset_status = _read


def _unavailable(
    target: ProjectionRefreshTarget,
    *,
    mode: AdapterMode,
    environment: str,
    reason: str,
) -> ProjectionReaderResult:
    return ProjectionReaderResult(
        kind=target.kind,
        adapter_mode=mode,
        source_environment=environment,
        source_object_id=target.source_object_id,
        source_version=None,
        source_modified_at=None,
        availability=ProjectionAvailability.UNAVAILABLE,
        values=None,
        unavailable_reason_code=reason,
    )
