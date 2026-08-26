from __future__ import annotations

import ast
import copy
import importlib
import json
import os
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.projections.domain import (
    AdapterMode,
    ApplicationDisposition,
    ProjectionAvailability,
    ProjectionContext,
    ProjectionKind,
    ProjectionReaderResult,
    ProjectionRefreshTarget,
    ProjectionScopeKind,
)
from tests.test_phase8_projection_domain import uid, values


PROJECT_ID = uid(1)
REQUEST_ID = str(uid(90))
NOW = datetime(2026, 8, 16, 8, 0, tzinfo=UTC)
REPOSITORY_PATH = (
    ROOT
    / "apps/npi_integration/npi_integration/projections/frappe_repository.py"
)


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeDocument(AttrDict):
    def __init__(self, owner: "Phase8ProjectionRepositoryTest", values: dict[str, Any]):
        super().__init__(values)
        object.__setattr__(self, "_owner", owner)

    def insert(self):
        name = self.get("name")
        if name is None:
            name = (
                self.get("event_id")
                if self.get("doctype") == "NPI Audit Event"
                else self.get("global_id") or self.get("event_id")
            )
        if name is None:
            raise AssertionError(f"Fake {self.get('doctype')} document has no identity")
        self.name = str(name)
        self._owner.events.append(("insert", str(self.doctype), self.name))
        if self._owner.fail_on == ("insert", str(self.doctype)):
            raise RuntimeError(f"Injected failure at insert {self.doctype}")
        bucket = self._owner.documents.setdefault(str(self.doctype), {})
        if self.name in bucket:
            raise self._owner.frappe.DuplicateEntryError()
        bucket[self.name] = self
        return self

    def save(self):
        self._owner.events.append(("save", str(self.doctype), str(self.name)))
        if self._owner.fail_on == ("save", str(self.doctype)):
            raise RuntimeError(f"Injected failure at save {self.doctype}")
        self._owner.documents.setdefault(str(self.doctype), {})[str(self.name)] = self
        return self


class StubDocumentRepository:
    def __init__(self, *, principal, request_id: str, trace_id: str) -> None:
        self.principal = principal
        self.request_id = request_id
        self.trace_id = trace_id
        self.actor = principal.user_id

    def _can_view_project(self, project: object, project_id: UUID) -> bool:
        return bool(
            not self.principal.is_external
            and self.principal.tenant_id == str(project.tenant_id)
            and str(project.global_id) == str(project_id)
            and (
                "System Manager" in self.principal.roles
                or str(project.owner_user_id).casefold() == self.actor.casefold()
            )
        )

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        result: str,
        summary: dict[str, object],
    ) -> None:
        self._test_owner.frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(uid(900 + len(self._test_owner.events))),
                "global_id": str(global_id),
                "object_version": object_version,
                "actor": self.actor,
                "trace_id": self.trace_id,
                "operation": operation,
                "result": result,
                "input_summary": summary,
            }
        ).insert()


class Phase8ProjectionRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.documents.frappe_repository",
        "npi_core.tooling.acceptance_repository",
        "npi_integration.projections.frappe_validation",
        "npi_integration.projections.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.documents: dict[str, dict[str, FakeDocument]] = {}
        self.events: list[tuple[str, str, str]] = []
        self.locked: list[tuple[str, str]] = []
        self.fail_on: tuple[str, str] | None = None
        self.safe_diagnostics: list[dict[str, object]] = []
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        self.frappe.get_doc = self.get_doc
        self.frappe.get_all = self.get_all
        sys.modules["frappe"] = self.frappe
        api_module = types.ModuleType("npi_core.api")
        api_module.record_safe_diagnostic = lambda **values: self.safe_diagnostics.append(
            values
        )
        sys.modules["npi_core.api"] = api_module
        base_module = types.ModuleType("npi_core.documents.frappe_repository")
        base_module.FrappeDocumentRepository = StubDocumentRepository
        sys.modules["npi_core.documents.frappe_repository"] = base_module
        self.module = importlib.import_module(
            "npi_integration.projections.frappe_repository"
        )
        self.acceptance_repository = importlib.import_module(
            "npi_core.tooling.acceptance_repository"
        )
        self.security = importlib.import_module("npi_core.foundation.security")
        self.project = self.add(
            "NPI Engineering Project",
            {
                "global_id": str(PROJECT_ID),
                "tenant_id": "TENANT-A",
                "owner_user_id": "owner@example.invalid",
                "references": [],
            },
        )
        self.repository = self.repository_for()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved_modules[name] is not None:
                sys.modules[name] = self.saved_modules[name]

    def repository_for(
        self,
        *,
        user_id: str = "admin@example.invalid",
        roles: frozenset[str] = frozenset({"System Manager"}),
        tenant_id: str = "TENANT-A",
        external: bool = False,
    ):
        repository = self.module.FrappeProjectionRepository(
            principal=self.security.Principal(
                user_id=user_id,
                roles=roles,
                tenant_id=tenant_id,
                is_external=external,
            ),
            request_id=REQUEST_ID,
            trace_id="trace-p8-01-repository",
            freshness_policies={
                kind: (f"disposable-{kind.value}-policy-v1", 3_600)
                for kind in ProjectionKind
            },
        )
        repository._test_owner = self
        return repository

    def add(self, doctype: str, values: dict[str, Any]) -> FakeDocument:
        return FakeDocument(self, {"doctype": doctype, **values}).insert()

    def get_doc(self, doctype_or_values, name: str | None = None, **kwargs: Any):
        if isinstance(doctype_or_values, dict):
            return FakeDocument(self, dict(doctype_or_values))
        if kwargs.get("for_update"):
            self.locked.append((str(doctype_or_values), str(name)))
        document = self.documents.get(str(doctype_or_values), {}).get(str(name))
        if document is None:
            raise self.frappe.DoesNotExistError()
        return document

    def get_all(
        self,
        doctype: str,
        *,
        filters: dict[str, Any],
        pluck: str | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        limit_page_length: int | None = None,
    ):
        documents = [
            document
            for document in self.documents.get(doctype, {}).values()
            if all(str(document.get(field)) == str(expected) for field, expected in filters.items())
        ]
        if order_by:
            clauses = [part.strip().split() for part in order_by.split(",")]
            for clause in reversed(clauses):
                field = clause[0]
                reverse = len(clause) > 1 and clause[1].casefold() == "desc"
                documents.sort(
                    key=lambda item: (item.get(field) is None, str(item.get(field))),
                    reverse=reverse,
                )
        if limit_page_length is not None:
            documents = documents[:limit_page_length]
        if pluck:
            return [document.get(pluck) for document in documents]
        if fields:
            return [
                AttrDict({field: document.get(field) for field in fields})
                for document in documents
            ]
        return documents

    def target(self, *, source: str = "CUSTOMER-SANDBOX-001") -> ProjectionRefreshTarget:
        return ProjectionRefreshTarget(
            context=ProjectionContext(
                tenant_id="TENANT-A",
                project_global_id=PROJECT_ID,
                scope_kind=ProjectionScopeKind.PROJECT,
                scope_global_id=PROJECT_ID,
            ),
            kind=ProjectionKind.CUSTOMER_MASTER,
            source_object_id=source,
        )

    def result(
        self,
        selected: ProjectionRefreshTarget,
        *,
        modified_at: datetime = NOW,
        version: str = "opaque-v1",
        availability: ProjectionAvailability = ProjectionAvailability.AVAILABLE,
    ) -> ProjectionReaderResult:
        return ProjectionReaderResult(
            kind=selected.kind,
            adapter_mode=AdapterMode.SANDBOX,
            source_environment="sandbox",
            source_object_id=selected.source_object_id,
            source_version=(version if availability is ProjectionAvailability.AVAILABLE else None),
            source_modified_at=(
                modified_at
                if availability is ProjectionAvailability.AVAILABLE
                else None
            ),
            availability=availability,
            values=(
                values(selected.kind)
                if availability is ProjectionAvailability.AVAILABLE
                else None
            ),
            unavailable_reason_code=(
                None if availability is ProjectionAvailability.AVAILABLE else "provider_unavailable"
            ),
        )

    def apply(
        self,
        selected: ProjectionRefreshTarget,
        result: ProjectionReaderResult,
        *,
        event_id: UUID,
    ):
        return self.repository.apply_observation(
            project_global_id=PROJECT_ID,
            target=selected,
            result=result,
            event_id=event_id,
            received_at=NOW + timedelta(minutes=1),
            correlation_id=uid(80),
        )

    def snapshot(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {
            doctype: {name: copy.deepcopy(dict(document)) for name, document in rows.items()}
            for doctype, rows in self.documents.items()
        }

    def restore(self, snapshot: dict[str, dict[str, dict[str, Any]]]) -> None:
        self.documents = {
            doctype: {
                name: FakeDocument(self, dict(values))
                for name, values in rows.items()
            }
            for doctype, rows in snapshot.items()
        }

    def seed_confirmed_projection(
        self,
        *,
        kind: ProjectionKind,
        scope_kind: ProjectionScopeKind,
        scope_id: UUID,
        projected_values: dict[str, object],
        index: int,
    ) -> None:
        observation_id = uid(300 + index)
        source_object_id = f"SOURCE-CONSUMER-{index}"
        common = {
            "tenant_id": "TENANT-A",
            "project_global_id": str(PROJECT_ID),
            "scope_kind": scope_kind.value,
            "scope_global_id": str(scope_id),
            "projection_kind": kind.value,
            "source_object_type": self.module.PROJECTION_DEFINITIONS[kind].source_object_type,
            "source_object_id": source_object_id,
        }
        self.add(
            "NPI ERP Projection Observation",
            {
                "global_id": str(observation_id),
                **common,
                "source_version": f"opaque-consumer-v{index}",
                "source_modified_at": NOW,
                "received_at": NOW + timedelta(minutes=1),
                "payload": json.dumps({"values": projected_values}),
                "payload_hash": "a" * 64,
                "observation_hash": "b" * 64,
                "disposition": ApplicationDisposition.APPLIED_CURRENT.value,
            },
        )
        self.add(
            "NPI ERP Projection Head",
            {
                "global_id": str(uid(400 + index)),
                **common,
                "current_observation": str(observation_id),
                "last_refresh_observation": str(observation_id),
                "availability": ProjectionAvailability.AVAILABLE.value,
                "freshness": "fresh",
            },
        )

    def test_project_first_authorization_redacts_external_and_hides_idor(self) -> None:
        self.assertIsNotNone(self.repository.authorize_project(PROJECT_ID))
        missing = self.repository.authorize_project(uid(999))
        wrong_tenant = self.repository_for(tenant_id="TENANT-B").authorize_project(PROJECT_ID)
        absent_membership = self.repository_for(
            user_id="member@example.invalid", roles=frozenset()
        ).authorize_project(PROJECT_ID)
        self.assertIsNone(missing)
        self.assertIsNone(wrong_tenant)
        self.assertIsNone(absent_membership)
        external = self.repository_for(external=True).authorize_project(PROJECT_ID)
        self.assertIsNotNone(external)
        response = self.repository_for(external=True).project_collection(external, kind=None)
        self.assertEqual(response["accessState"], "redacted")
        self.assertEqual(response["items"], [])
        self.assertEqual(response["permissions"], {"view": False, "edit": False, "refresh": False})

    def test_scope_enumeration_and_secondary_containment_are_server_owned(self) -> None:
        self.project.references = [
            AttrDict(
                reference_type="customer",
                source_system="ERPNEXT",
                source_object_id="CUSTOMER-SANDBOX-001",
            ),
            AttrDict(
                reference_type="customer",
                source_system="OTHER",
                source_object_id="MUST-NOT-ENUMERATE",
            ),
        ]
        enumerated = self.repository.enumerate_refresh_targets(PROJECT_ID)
        self.assertEqual(len(enumerated), 1)
        self.assertIs(enumerated[0].kind, ProjectionKind.CUSTOMER_MASTER)
        self.assertEqual(enumerated[0].source_object_id, "CUSTOMER-SANDBOX-001")

        tooling_master_id = uid(120)
        self.add(
            "NPI Tooling Master",
            {
                "global_id": str(tooling_master_id),
                "tenant_id": "TENANT-A",
                "originating_project_global_id": str(PROJECT_ID),
            },
        )

        def supplier_target(scope_id: UUID) -> ProjectionRefreshTarget:
            return ProjectionRefreshTarget(
                context=ProjectionContext(
                    tenant_id="TENANT-A",
                    project_global_id=PROJECT_ID,
                    scope_kind=ProjectionScopeKind.TOOLING_MASTER,
                    scope_global_id=scope_id,
                ),
                kind=ProjectionKind.SUPPLIER_MASTER,
                source_object_id="SUPPLIER-SANDBOX-001",
            )

        exact = supplier_target(tooling_master_id)
        result = ProjectionReaderResult(
            kind=exact.kind,
            adapter_mode=AdapterMode.SANDBOX,
            source_environment="sandbox",
            source_object_id=exact.source_object_id,
            source_version="opaque-supplier-v1",
            source_modified_at=NOW,
            availability=ProjectionAvailability.AVAILABLE,
            values=values(exact.kind),
        )
        outcome = self.apply(exact, result, event_id=uid(121))
        self.assertIs(outcome.disposition, ApplicationDisposition.APPLIED_CURRENT)
        with self.assertRaisesRegex(ValueError, "secondary scope"):
            self.apply(supplier_target(uid(122)), result, event_id=uid(123))
        cross_project = self.add(
            "NPI Tooling Master",
            {
                "global_id": str(uid(124)),
                "tenant_id": "TENANT-A",
                "originating_project_global_id": str(uid(999)),
            },
        )
        with self.assertRaisesRegex(ValueError, "secondary scope"):
            self.apply(
                supplier_target(UUID(str(cross_project.global_id))),
                result,
                event_id=uid(125),
            )

    def test_exact_replay_reorder_conflict_and_unavailable_preserve_truth(self) -> None:
        selected = self.target()
        first = self.apply(selected, self.result(selected), event_id=uid(10))
        replay = self.apply(selected, self.result(selected), event_id=uid(10))
        older = self.apply(
            selected,
            self.result(selected, modified_at=NOW - timedelta(minutes=1), version="opaque-old"),
            event_id=uid(11),
        )
        unavailable = self.apply(
            selected,
            self.result(selected, availability=ProjectionAvailability.UNAVAILABLE),
            event_id=uid(12),
        )
        conflict = self.apply(
            selected,
            self.result(selected, modified_at=NOW + timedelta(minutes=1), version="opaque-v2"),
            event_id=uid(12),
        )
        self.assertIs(first.disposition, ApplicationDisposition.APPLIED_CURRENT)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.head_optimistic_version, 1)
        self.assertIs(older.disposition, ApplicationDisposition.SUPERSEDED)
        self.assertIs(unavailable.disposition, ApplicationDisposition.UNAVAILABLE_CURRENT)
        self.assertIs(conflict.disposition, ApplicationDisposition.CONFLICTED)
        heads = list(self.documents["NPI ERP Projection Head"].values())
        self.assertEqual(len(heads), 1)
        head = heads[0]
        self.assertEqual(head.current_observation, str(first.observation_global_id))
        self.assertEqual(head.availability, ProjectionAvailability.UNAVAILABLE.value)
        self.assertEqual(head.optimistic_version, 4)
        response = self.repository.project_collection(
            self.repository.authorize_project(PROJECT_ID), kind=None
        )
        self.assertIsNotNone(response["items"][0]["currentTruth"])
        self.assertEqual(
            response["items"][0]["currentTruth"]["headGlobalId"],
            str(head.global_id),
        )
        self.assertEqual(
            response["items"][0]["currentTruth"]["headOptimisticVersion"],
            4,
        )
        self.assertEqual(
            response["items"][0]["currentTruth"]["headHash"],
            str(head.head_hash),
        )
        self.assertEqual(response["items"][0]["availability"], "unavailable")
        self.assertGreaterEqual(len(self.locked), 4)

    def test_each_transaction_failure_retries_to_one_complete_effect(self) -> None:
        stages = (
            ("insert", "NPI ERP Projection Observation"),
            ("insert", "NPI ERP Projection Head"),
            ("insert", "NPI Audit Event"),
        )
        for index, stage in enumerate(stages, start=1):
            with self.subTest(stage=stage):
                selected = self.target(source=f"CUSTOMER-FAIL-{index}")
                before = self.snapshot()
                self.fail_on = stage
                with self.assertRaises(RuntimeError):
                    self.apply(selected, self.result(selected), event_id=uid(20 + index))
                self.restore(before)
                self.fail_on = None
                outcome = self.apply(
                    selected, self.result(selected), event_id=uid(20 + index)
                )
                self.assertIs(outcome.disposition, ApplicationDisposition.APPLIED_CURRENT)
                matching_heads = [
                    row
                    for row in self.documents["NPI ERP Projection Head"].values()
                    if row.source_object_id == selected.source_object_id
                ]
                matching_observations = [
                    row
                    for row in self.documents["NPI ERP Projection Observation"].values()
                    if row.source_object_id == selected.source_object_id
                ]
                self.assertEqual(len(matching_heads), 1)
                self.assertEqual(len(matching_observations), 1)

    def test_confirmed_fresh_cost_and_asset_consumers_parse_closed_typed_truth(self) -> None:
        tooling_master_id = uid(20)
        tooling_set_id = uid(30)
        self.add(
            "NPI Tooling Set",
            {
                "global_id": str(tooling_set_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "tooling_master_global_id": str(tooling_master_id),
            },
        )
        self.seed_confirmed_projection(
            kind=ProjectionKind.TOOLING_PROCUREMENT_COST,
            scope_kind=ProjectionScopeKind.TOOLING_MASTER,
            scope_id=tooling_master_id,
            projected_values=values(ProjectionKind.TOOLING_PROCUREMENT_COST),
            index=1,
        )
        self.seed_confirmed_projection(
            kind=ProjectionKind.TOOL_ASSET_STATUS,
            scope_kind=ProjectionScopeKind.TOOLING_SET,
            scope_id=tooling_set_id,
            projected_values=values(ProjectionKind.TOOL_ASSET_STATUS),
            index=2,
        )
        reader = self.module.FrappeProjectionConsumerReader()
        cost = reader.read_tooling_procurement_cost(
            project_global_id=PROJECT_ID,
            tooling_master_global_id=tooling_master_id,
        )
        asset = reader.read_tool_asset_status(
            project_global_id=PROJECT_ID,
            tooling_master_global_id=tooling_master_id,
        )
        self.assertEqual(cost["state"], "available")
        self.assertEqual(cost["observedAt"], "2026-08-16T08:00:00Z")
        self.assertEqual(cost["summaries"][0]["amount"], "1200.5")
        self.assertEqual(asset["state"], "available")
        self.assertEqual(asset["toolingSetGlobalId"], str(tooling_set_id))
        self.assertEqual(asset["observedAt"], "2026-08-16T08:00:00Z")
        parsed_asset = self.acceptance_repository._asset_projection_from_snapshot(asset)
        self.assertEqual(parsed_asset.public_dict(), asset)
        unavailable_asset = self.acceptance_repository._asset_projection_from_snapshot(
            {
                "sourceSystem": "ERPNEXT",
                "editableIn": "ERPNEXT",
                "state": "unavailable",
                "reasonCode": "erp_asset_projection_unavailable",
                "mappingCardinality": "zero_or_one_per_physical_set",
            }
        )
        self.assertEqual(unavailable_asset.state, "unavailable")
        with self.assertRaisesRegex(RuntimeError, "not closed"):
            self.acceptance_repository._asset_projection_from_snapshot(
                {**asset, "secret": "must-not-escape"}
            )

    def test_consumers_reject_stale_unavailable_ambiguous_and_open_payloads(self) -> None:
        reader = self.module.FrappeProjectionConsumerReader()
        self.assertIsNone(
            reader.read_tooling_procurement_cost(
                project_global_id=PROJECT_ID,
                tooling_master_global_id=uid(20),
            )
        )
        opened = values(ProjectionKind.TOOLING_PROCUREMENT_COST)
        opened["secret"] = "must-not-escape"
        self.seed_confirmed_projection(
            kind=ProjectionKind.TOOLING_PROCUREMENT_COST,
            scope_kind=ProjectionScopeKind.TOOLING_MASTER,
            scope_id=uid(20),
            projected_values=opened,
            index=5,
        )
        with self.assertRaisesRegex(ValueError, "not closed"):
            reader.read_tooling_procurement_cost(
                project_global_id=PROJECT_ID,
                tooling_master_global_id=uid(20),
            )
        head = next(iter(self.documents["NPI ERP Projection Head"].values()))
        head.freshness = "stale"
        self.assertIsNone(
            reader.read_tooling_procurement_cost(
                project_global_id=PROJECT_ID,
                tooling_master_global_id=uid(20),
            )
        )

    def test_repository_source_has_one_atomic_guard_and_no_transport_or_commit(self) -> None:
        source = REPOSITORY_PATH.read_text(encoding="utf-8")
        ast.parse(source)
        apply_source = source[
            source.index("    def apply_observation(") : source.index(
                "    def _candidate_freshness("
            )
        ]
        self.assertLess(
            apply_source.index("_optional_locked_doc("),
            apply_source.index("existing_event_rows ="),
        )
        self.assertLess(
            apply_source.index("with projection_repository_write():"),
            apply_source.index("frappe.get_doc(observation_values).insert()"),
        )
        self.assertLess(
            apply_source.index("frappe.get_doc(observation_values).insert()"),
            apply_source.index("self._append_audit("),
        )
        combined = source.casefold()
        for forbidden in (
            "requests" + ".",
            "httpx" + ".",
            "urllib." + "request",
            "socket" + ".",
            "frappe.db" + ".sql",
            "frappe.db" + ".commit",
            "frappe.db" + ".rollback",
            "enqueue(",
            "scheduler_events",
            "delete_doc",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn("limit_page_length=MAX_PROJECT_PROJECTION_HEADS + 1", source)
        self.assertIn("availability\": ProjectionAvailability.AVAILABLE.value", source)
        self.assertIn("freshness\": ProjectionFreshness.FRESH.value", source)

    def test_prepare_projection_diagnostic_is_exact_inner_and_default_off(self) -> None:
        trace_id = "trace-0123456789abcdef0123456789abcdef"
        error = RuntimeError("private-value")
        with (
            self.assertRaises(RuntimeError) as disabled,
            self.module.quality_link_prepare_projection_diagnostics(trace_id),
            self.module.quality_link_prepare_projection_step(
                "P806_QUALITY_PROJECTION_TRANSACTION"
            ),
        ):
            raise error
        self.assertIs(disabled.exception, error)
        self.assertEqual(self.safe_diagnostics, [])

        with (
            patch.dict(
                os.environ,
                {
                    self.module._QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_ENV:
                    self.module.QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_SCOPE
                },
                clear=False,
            ),
            self.assertRaises(RuntimeError) as active,
            self.module.quality_link_prepare_projection_diagnostics(trace_id),
            self.module.quality_link_prepare_projection_step(
                "P806_QUALITY_PROJECTION_TRANSACTION"
            ),
            self.module.quality_link_prepare_projection_step(
                "P806_QUALITY_PROJECTION_OBSERVATION_INSERT"
            ),
        ):
            raise error
        self.assertIs(active.exception, error)
        self.assertEqual(
            self.safe_diagnostics,
            [
                {
                    "code": "P806_QUALITY_PROJECTION_OBSERVATION_INSERT",
                    "title": "NPI formal quality projection preparation failed",
                    "exception_type": "RuntimeError",
                    "trace_id": trace_id,
                }
            ],
        )
        self.assertNotIn("private-value", json.dumps(self.safe_diagnostics))
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                self.module._QUALITY_LINK_PREPARE_PROJECTION_DIAGNOSTIC_FLAG,
            )
        )


if __name__ == "__main__":
    unittest.main()
