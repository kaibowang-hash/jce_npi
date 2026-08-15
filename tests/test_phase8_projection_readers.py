from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.projections.config import ProjectionAdapterConfiguration
from npi_integration.projections.domain import (
    AdapterMode,
    ApplicationDisposition,
    ProjectionApplyOutcome,
    ProjectionAvailability,
    ProjectionContext,
    ProjectionContractError,
    ProjectionKind,
    ProjectionReaderResult,
    ProjectionRefreshTarget,
    ProjectionScopeKind,
)
from npi_integration.projections.readers import (
    ProjectionReaderRegistry,
    SyntheticProjectionReader,
)
from npi_integration.projections.worker import (
    MAX_PROJECT_REFRESH_TARGETS,
    refresh_project_projections,
)
from tests.test_phase8_projection_domain import scope, uid, values


NOW = datetime(2026, 8, 16, 7, 0, tzinfo=UTC)


def target(kind: ProjectionKind, *, source: str | None = None) -> ProjectionRefreshTarget:
    selected_scope = scope(kind)
    return ProjectionRefreshTarget(
        context=ProjectionContext(
            tenant_id="tenant-synthetic",
            project_global_id=uid(1),
            scope_kind=selected_scope,
            scope_global_id=(
                uid(1) if selected_scope is ProjectionScopeKind.PROJECT else uid(2)
            ),
        ),
        kind=kind,
        source_object_id=source or f"SOURCE-{kind.value}",
    )


def unavailable(
    selected: ProjectionRefreshTarget,
    *,
    mode: AdapterMode = AdapterMode.MOCK,
    environment: str = "mock",
) -> ProjectionReaderResult:
    return ProjectionReaderResult(
        kind=selected.kind,
        adapter_mode=mode,
        source_environment=environment,
        source_object_id=selected.source_object_id,
        source_version=None,
        source_modified_at=None,
        availability=ProjectionAvailability.UNAVAILABLE,
        values=None,
        unavailable_reason_code="provider_unavailable",
    )


class NamedReader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def _read(self, method: str, selected: ProjectionRefreshTarget) -> ProjectionReaderResult:
        self.calls.append(method)
        return unavailable(selected)

    def read_customer_master(self, selected: ProjectionRefreshTarget) -> ProjectionReaderResult:
        return self._read("read_customer_master", selected)

    def read_supplier_master(self, selected: ProjectionRefreshTarget) -> ProjectionReaderResult:
        return self._read("read_supplier_master", selected)

    def read_formal_item_master(self, selected: ProjectionRefreshTarget) -> ProjectionReaderResult:
        return self._read("read_formal_item_master", selected)

    def read_tooling_procurement_cost(
        self, selected: ProjectionRefreshTarget
    ) -> ProjectionReaderResult:
        return self._read("read_tooling_procurement_cost", selected)

    def read_project_cost(self, selected: ProjectionRefreshTarget) -> ProjectionReaderResult:
        return self._read("read_project_cost", selected)

    def read_formal_quality_status(
        self, selected: ProjectionRefreshTarget
    ) -> ProjectionReaderResult:
        return self._read("read_formal_quality_status", selected)

    def read_tool_asset_status(self, selected: ProjectionRefreshTarget) -> ProjectionReaderResult:
        return self._read("read_tool_asset_status", selected)


class FakeRepository:
    def __init__(self, targets: tuple[ProjectionRefreshTarget, ...]) -> None:
        self.targets = targets
        self.applied: list[dict[str, object]] = []

    def enumerate_refresh_targets(self, project_global_id: UUID):
        self.enumerated_project = project_global_id
        return self.targets

    def apply_observation(self, **values: object) -> ProjectionApplyOutcome:
        self.applied.append(values)
        return ProjectionApplyOutcome(
            observation_global_id=values["event_id"],
            disposition=ApplicationDisposition.UNAVAILABLE_CURRENT,
            head_optimistic_version=len(self.applied),
        )


class Phase8ProjectionReaderTest(unittest.TestCase):
    def test_registry_dispatches_exactly_seven_named_operations(self) -> None:
        reader = NamedReader()
        registry = ProjectionReaderRegistry(
            configuration=ProjectionAdapterConfiguration(),
            reader=reader,
        )
        for kind in ProjectionKind:
            result = registry.read(target(kind))
            self.assertIs(result.kind, kind)
            self.assertIs(result.availability, ProjectionAvailability.UNAVAILABLE)
        self.assertEqual(
            reader.calls,
            [
                "read_customer_master",
                "read_supplier_master",
                "read_formal_item_master",
                "read_tooling_procurement_cost",
                "read_project_cost",
                "read_formal_quality_status",
                "read_tool_asset_status",
            ],
        )

    def test_mock_and_frozen_sandbox_reader_are_explicitly_unavailable(self) -> None:
        selected = target(ProjectionKind.CUSTOMER_MASTER)
        mock = ProjectionReaderRegistry(configuration=ProjectionAdapterConfiguration())
        self.assertEqual(mock.read(selected).unavailable_reason_code, "provider_unavailable")
        sandbox_configuration = ProjectionAdapterConfiguration(
            mode=AdapterMode.SANDBOX,
            enabled=True,
            base_url="https://erp.sandbox.example.test",
            allowed_hostnames=("erp.sandbox.example.test",),
            allowed_operations=(ProjectionKind.CUSTOMER_MASTER,),
            secret_reference="secrets/erp-sandbox-read",
            environment_code="sandbox",
            non_production_attested=True,
        )
        sandbox = ProjectionReaderRegistry(configuration=sandbox_configuration)
        result = sandbox.read(selected)
        self.assertIs(result.adapter_mode, AdapterMode.SANDBOX)
        self.assertEqual(result.unavailable_reason_code, "sandbox_mapper_unavailable")
        blocked = sandbox.read(target(ProjectionKind.SUPPLIER_MASTER))
        self.assertEqual(blocked.unavailable_reason_code, "operation_not_enabled")

    def test_synthetic_results_stay_non_authoritative_and_exact(self) -> None:
        selected = target(ProjectionKind.CUSTOMER_MASTER)
        result = ProjectionReaderResult(
            kind=selected.kind,
            adapter_mode=AdapterMode.SYNTHETIC,
            source_environment="disposable-test",
            source_object_id=selected.source_object_id,
            source_version="synthetic-v1",
            source_modified_at=NOW,
            availability=ProjectionAvailability.SYNTHETIC,
            values=values(selected.kind),
        )
        configuration = ProjectionAdapterConfiguration(
            mode=AdapterMode.SYNTHETIC,
            environment_code="disposable-test",
            synthetic_test_only=True,
        )
        registry = ProjectionReaderRegistry(
            configuration=configuration,
            reader=SyntheticProjectionReader({selected.kind: result}),
        )
        self.assertIs(registry.read(selected).availability, ProjectionAvailability.SYNTHETIC)
        with self.assertRaises(ProjectionContractError):
            registry.read(target(selected.kind, source="ANOTHER-SOURCE"))
        with self.assertRaises(ProjectionContractError):
            SyntheticProjectionReader(
                {
                    selected.kind: unavailable(
                        selected,
                        mode=AdapterMode.SYNTHETIC,
                        environment="disposable-test",
                    )
                }
            )

    def test_bounded_worker_reuses_one_correlation_and_distinct_event_ids(self) -> None:
        targets = tuple(target(kind) for kind in ProjectionKind)
        repository = FakeRepository(targets)
        generated = iter(uid(value) for value in range(100, 108))
        batch = refresh_project_projections(
            repository=repository,
            registry=ProjectionReaderRegistry(configuration=ProjectionAdapterConfiguration()),
            project_global_id=uid(1),
            clock=lambda: NOW,
            uuid_factory=lambda: next(generated),
        )
        self.assertEqual(batch.project_global_id, uid(1))
        self.assertEqual(len(batch.outcomes), 7)
        self.assertEqual({value["correlation_id"] for value in repository.applied}, {uid(100)})
        self.assertEqual(
            [value["event_id"] for value in repository.applied],
            [uid(value) for value in range(101, 108)],
        )
        self.assertTrue(all(value["received_at"] == NOW for value in repository.applied))

    def test_worker_rejects_ambiguous_or_oversized_server_targets(self) -> None:
        selected = target(ProjectionKind.CUSTOMER_MASTER)
        registry = ProjectionReaderRegistry(configuration=ProjectionAdapterConfiguration())
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            refresh_project_projections(
                repository=FakeRepository((selected, selected)),
                registry=registry,
                project_global_id=uid(1),
            )
        oversized = tuple(
            target(ProjectionKind.CUSTOMER_MASTER, source=f"CUSTOMER-{index}")
            for index in range(MAX_PROJECT_REFRESH_TARGETS + 1)
        )
        with self.assertRaisesRegex(ValueError, "safe bound"):
            refresh_project_projections(
                repository=FakeRepository(oversized),
                registry=registry,
                project_global_id=uid(1),
            )


if __name__ == "__main__":
    unittest.main()
