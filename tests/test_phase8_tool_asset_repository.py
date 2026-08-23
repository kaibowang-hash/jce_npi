from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from tests.test_phase8_tool_asset_domain import NOW, profile, source, uid  # noqa: E402
from npi_integration.tool_asset_request.execution_domain import (  # noqa: E402
    ToolAssetApprovalState,
    ToolAssetBusinessApprovalReference,
    ToolAssetExecutionOperation,
    ToolAssetExecutionRequest,
    ToolAssetExecutionRequestState,
    ToolAssetExecutionTargetMode,
    ToolAssetMappingExpectation,
)


class Phase8ToolAssetRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module_names = (
            "frappe",
            "npi_core.tooling.frappe_repository",
            "npi_core.project_controls.terminal_guard",
            "npi_integration.tool_asset_request.frappe_validation",
            "npi_integration.tool_asset_request.execution_frappe_validation",
            "npi_integration.tool_asset_request.frappe_repository",
        )
        cls.saved_modules = {
            name: sys.modules.get(name) for name in cls.module_names
        }
        for name in cls.module_names:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user="engineer@example.invalid")
        frappe.db = types.SimpleNamespace(get_value=lambda *_args, **_kwargs: None)
        sys.modules["frappe"] = frappe

        parent = types.ModuleType("npi_core.tooling.frappe_repository")
        parent.FrappeToolingRepository = object
        sys.modules["npi_core.tooling.frappe_repository"] = parent
        terminal = types.ModuleType("npi_core.project_controls.terminal_guard")
        terminal.require_mutable_project = lambda _project: None
        sys.modules["npi_core.project_controls.terminal_guard"] = terminal
        legacy_validation = types.ModuleType(
            "npi_integration.tool_asset_request.frappe_validation"
        )

        @contextmanager
        def legacy_write():
            yield

        legacy_validation.tool_asset_request_write = legacy_write
        sys.modules[
            "npi_integration.tool_asset_request.frappe_validation"
        ] = legacy_validation
        sys.modules.pop(
            "npi_integration.tool_asset_request.frappe_repository", None
        )
        cls.repository = importlib.import_module(
            "npi_integration.tool_asset_request.frappe_repository"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        for name in cls.module_names:
            sys.modules.pop(name, None)
            if cls.saved_modules[name] is not None:
                sys.modules[name] = cls.saved_modules[name]

    @staticmethod
    def request(
        mode: ToolAssetExecutionTargetMode = ToolAssetExecutionTargetMode.MOCK,
    ) -> ToolAssetExecutionRequest:
        value = source()
        expectation = ToolAssetMappingExpectation(
            ToolAssetExecutionOperation.CREATE,
            value.source_stream_key_hash,
            0,
        )
        return ToolAssetExecutionRequest(
            uid(20),
            value,
            ToolAssetBusinessApprovalReference(ToolAssetApprovalState.UNAVAILABLE),
            expectation,
            profile(mode),
            (
                ToolAssetExecutionRequestState.VALIDATED_MOCK
                if mode is ToolAssetExecutionTargetMode.MOCK
                else ToolAssetExecutionRequestState.QUEUED
            ),
            "engineer@example.invalid",
            uid(21),
            "trace-p805-repository",
            "a" * 64,
            NOW,
        )

    def bare_repository(self):
        value = object.__new__(self.repository.FrappeToolAssetRequestRepository)
        value.actor = "engineer@example.invalid"
        value.request_id = str(uid(21))
        value.trace_id = "trace-p805-repository"
        return value

    def test_exact_source_resolves_and_locks_every_containment_edge(self) -> None:
        repository = self.bare_repository()
        project = types.SimpleNamespace(tenant_id="tenant-synthetic", global_id=uid(1))
        master = types.SimpleNamespace(global_id=uid(2), title="Synthetic Tooling Master", snapshot_hash="1" * 64)
        tooling_set = types.SimpleNamespace(
            global_id=uid(3),
            physical_serial="SET-SYNTHETIC-001",
            snapshot_hash="2" * 64,
            requirement_kind=types.SimpleNamespace(value="new_tool"),
        )
        binding = types.SimpleNamespace(
            global_id=uid(4),
            tooling_revision_global_id=uid(5),
            snapshot_hash="3" * 64,
        )
        revision = types.SimpleNamespace(
            global_id=uid(5),
            revision_number=2,
            revision_label="R2",
            snapshot_hash="4" * 64,
        )
        acceptance = types.SimpleNamespace(
            global_id=uid(6),
            acceptance_global_id=uid(7),
            acceptance_version=1,
            predecessor_global_id=None,
            predecessor_snapshot_hash=None,
            snapshot_hash="5" * 64,
            tooling_set_global_id=uid(3),
            tooling_set_snapshot_hash="2" * 64,
            set_revision_binding_global_id=uid(4),
            set_revision_binding_snapshot_hash="3" * 64,
            tooling_revision_global_id=uid(5),
            tooling_revision_number=2,
            tooling_revision_snapshot_hash="4" * 64,
            tooling_master_snapshot_hash="1" * 64,
            created_at=NOW,
        )
        repository._master_for_project = lambda *_args: master
        repository._tooling_set_for_project = lambda *_args: tooling_set
        repository._binding_for_set = lambda *_args: binding
        repository._tooling_revision_for_project = lambda *_args, **_kwargs: revision
        repository._acceptance_revision_for_project = lambda *_args: acceptance
        locks: list[tuple[str, object]] = []
        repository._lock_exact_execution_parent = (
            lambda doctype, identity, _expected: locks.append((doctype, identity))
        )

        observed = repository._execution_source(
            project, uid(2), uid(3), uid(6), lock=True
        )

        self.assertEqual(observed, source())
        self.assertEqual(
            [doctype for doctype, _identity in locks],
            [
                "NPI Tooling Master",
                "NPI Tooling Set",
                "NPI Tooling Set Revision Binding",
                "NPI Tooling Revision",
                "NPI Tooling Acceptance Evidence Revision",
            ],
        )

    def test_create_and_update_mapping_preconditions_use_server_projection(self) -> None:
        repository = self.bare_repository()
        project = types.SimpleNamespace(tenant_id="tenant-synthetic", global_id=uid(1))
        source_value = source()
        repository._mapping_head = lambda *_args, **_kwargs: None
        repository._asset_projection = lambda *_args: types.SimpleNamespace(
            public_dict=lambda: {"state": "unavailable"}
        )
        create = repository._mapping_expectation(
            project,
            uid(2),
            source_value,
            ToolAssetExecutionOperation.CREATE,
            lock=True,
        )
        self.assertEqual(create.mapping_version, 0)

        head = types.SimpleNamespace(
            mapping_version=2,
            formal_asset_id="ASSET-SANDBOX-1",
            target_version="2",
            current_observation_hash="8" * 64,
        )
        repository._mapping_head = lambda *_args, **_kwargs: head
        repository._asset_projection = lambda *_args: types.SimpleNamespace(
            public_dict=lambda: {
                "state": "available",
                "toolingSetGlobalId": str(uid(3)),
                "mappingVersion": 2,
                "formalAssetId": "ASSET-SANDBOX-1",
                "targetVersion": "2",
            }
        )
        update = repository._mapping_expectation(
            project,
            uid(2),
            source_value,
            ToolAssetExecutionOperation.UPDATE,
            lock=True,
        )
        self.assertEqual(update.formal_asset_id, "ASSET-SANDBOX-1")
        repository._asset_projection = lambda *_args: types.SimpleNamespace(
            public_dict=lambda: {"state": "available", "toolingSetGlobalId": str(uid(30))}
        )
        with self.assertRaises(Exception) as caught:
            repository._mapping_expectation(
                project,
                uid(2),
                source_value,
                ToolAssetExecutionOperation.UPDATE,
                lock=True,
            )
        self.assertEqual(
            getattr(caught.exception, "code", None),
            "TOOL_ASSET_EXECUTION_STATE_CONFLICT",
        )

    def test_atomic_execution_write_order_and_mock_zero_dispatch(self) -> None:
        repository = self.bare_repository()
        project = types.SimpleNamespace(tenant_id="tenant-synthetic", global_id=uid(1))
        repository._locked_authorized_project = lambda _project_id: project
        repository._execution_receipt = lambda _key: None
        repository._required_execution_profile = lambda _project: types.SimpleNamespace(
            target_mode=ToolAssetExecutionTargetMode.SYNTHETIC
        )
        value = self.request(ToolAssetExecutionTargetMode.SYNTHETIC)
        repository._build_execution_request = lambda *_args, **_kwargs: value
        repository._new_uuid = lambda: uid(30)
        events: list[str] = []
        guard = types.SimpleNamespace(active_request_global_id=None)
        repository._locked_execution_stream_guard = lambda *_args, **_kwargs: (
            events.append("guard") or guard
        )
        repository._insert_execution_request = lambda *_args, **_kwargs: events.append("request")
        repository._insert_execution_outbox = lambda *_args, **_kwargs: events.append("outbox")
        repository._activate_execution_stream_guard = lambda *_args, **_kwargs: events.append("activate")
        repository._append_execution_audit = lambda *_args, **_kwargs: events.append("audit")
        repository._insert_execution_receipt = lambda *_args, **_kwargs: events.append("receipt")

        @contextmanager
        def transaction(_actor: str):
            events.append("begin")
            try:
                yield object()
            finally:
                events.append("end")

        with patch.object(
            self.repository,
            "tool_asset_request_transaction_write",
            transaction,
        ):
            outcome = repository._create_execution_request(
                uid(1),
                uid(2),
                uid(3),
                ToolAssetExecutionOperation.CREATE,
                acceptance_revision_id=uid(6),
                expected_source_hash=value.source.source_hash,
                expected_approval_hash=self.repository.canonical_hash(
                    value.approval.canonical_mapping()
                ),
                expected_mapping_expectation_hash=self.repository.canonical_hash(
                    value.mapping_expectation.canonical_mapping()
                ),
                expected_profile_snapshot_hash=value.profile.snapshot_hash,
                idempotency_key_hash=value.idempotency_key_hash,
                acknowledgement="fixed",
            )
        self.assertEqual(
            events,
            ["begin", "guard", "request", "outbox", "activate", "audit", "receipt", "end"],
        )
        self.assertTrue(outcome.should_enqueue)

        events.clear()
        mock = self.request()
        repository._required_execution_profile = lambda _project: types.SimpleNamespace(
            target_mode=ToolAssetExecutionTargetMode.MOCK
        )
        repository._build_execution_request = lambda *_args, **_kwargs: mock
        with patch.object(
            self.repository,
            "tool_asset_request_transaction_write",
            transaction,
        ):
            outcome = repository._create_execution_request(
                uid(1), uid(2), uid(3), ToolAssetExecutionOperation.CREATE,
                acceptance_revision_id=uid(6),
                expected_source_hash=mock.source.source_hash,
                expected_approval_hash=self.repository.canonical_hash(mock.approval.canonical_mapping()),
                expected_mapping_expectation_hash=self.repository.canonical_hash(mock.mapping_expectation.canonical_mapping()),
                expected_profile_snapshot_hash=mock.profile.snapshot_hash,
                idempotency_key_hash=mock.idempotency_key_hash,
                acknowledgement="fixed",
            )
        self.assertEqual(events, ["begin", "request", "audit", "receipt", "end"])
        self.assertFalse(outcome.should_enqueue)
        self.assertIsNone(outcome.outbox_event_id)

    def test_same_idempotency_key_cannot_cross_operation(self) -> None:
        repository = self.bare_repository()
        project = types.SimpleNamespace(tenant_id="tenant-synthetic", global_id=uid(1))
        receipt = types.SimpleNamespace(
            receipt_key="r" * 64,
            schema_version=2,
            tenant_id="tenant-synthetic",
            project_global_id=str(uid(1)),
            actor_user_id="engineer@example.invalid",
            operation="create_tool_asset",
            idempotency_key_hash="a" * 64,
            payload_hash="b" * 64,
            request_global_id=None,
        )
        outcome = repository._execution_replay_or_conflict(
            project,
            receipt,
            receipt_key="r" * 64,
            operation=ToolAssetExecutionOperation.UPDATE,
            idempotency_key_hash="a" * 64,
            command_hash="b" * 64,
        )
        self.assertEqual(
            getattr(outcome.problem, "code", None),
            "TOOL_ASSET_EXECUTION_IDEMPOTENCY_CONFLICT",
        )

    def test_database_mapping_datetime_is_utc_and_invalid_is_closed(self) -> None:
        expected = datetime(2026, 8, 24, 2, 0, tzinfo=UTC)
        self.assertEqual(
            self.repository._datetime_value("2026-08-24 02:00:00"), expected
        )
        self.assertEqual(
            self.repository._datetime_value("2026-08-24T10:00:00+08:00"), expected
        )
        with self.assertRaises((RuntimeError, ValueError)):
            self.repository._datetime_value(None)

    def test_request_capability_binds_ignore_permissions_to_exact_actor_and_doctype(self) -> None:
        validation = importlib.import_module(
            "npi_integration.tool_asset_request.execution_frappe_validation"
        )
        frappe = sys.modules["frappe"]
        frappe.db.get_value = lambda doctype, identity, field: (
            1 if (doctype, identity, field) == ("User", frappe.session.user, "enabled") else None
        )
        frappe.get_roles = lambda identity: (
            ["NPI API User"] if identity == frappe.session.user else []
        )
        calls: list[tuple[str, bool]] = []

        class Document:
            def __init__(self, doctype: str) -> None:
                self.doctype = doctype

            def insert(self, *, ignore_permissions: bool = False):
                calls.append((self.doctype, ignore_permissions))
                return self

        request = Document("NPI Tool Asset Request")
        audit = Document("NPI Audit Event")
        with validation.tool_asset_request_transaction_write(
            frappe.session.user
        ) as capability:
            validation.insert_tool_asset_support_document(
                request, capability=capability
            )
            validation.insert_tool_asset_audit_document(
                audit, capability=capability
            )
            with self.assertRaisesRegex(RuntimeError, "outside"):
                validation.insert_tool_asset_support_document(
                    Document("NPI Tool Asset Attempt"), capability=capability
                )
        self.assertEqual(
            calls,
            [
                ("NPI Tool Asset Request", True),
                ("NPI Audit Event", True),
            ],
        )
        with self.assertRaisesRegex(RuntimeError, "out of scope"):
            validation.insert_tool_asset_support_document(
                request, capability=capability
            )

    def test_request_and_outbox_persist_exact_versioned_snapshots_without_target_config(self) -> None:
        repository = self.bare_repository()
        value = self.request(ToolAssetExecutionTargetMode.SYNTHETIC)
        project = types.SimpleNamespace(
            tenant_id=value.source.tenant_id,
            global_id=value.source.project_global_id,
        )
        captured: list[dict[str, object]] = []

        def get_doc(mapping: dict[str, object]):
            captured.append(mapping.copy())
            return types.SimpleNamespace(**mapping)

        capability = object()
        with (
            patch.object(sys.modules["frappe"], "get_doc", get_doc, create=True),
            patch.object(
                self.repository,
                "insert_tool_asset_support_document",
                lambda document, *, capability: document,
            ),
        ):
            repository._insert_execution_request(
                value,
                outbox_event_id=uid(30),
                target_idempotency_key_hash="b" * 64,
                semantic_effect_hash="c" * 64,
                capability=capability,
            )
            repository._service_actor_for_profile = (
                lambda _project, _reference: "worker@example.invalid"
            )
            repository._insert_execution_outbox(
                project,
                value,
                event_id=uid(30),
                target_idempotency_key_hash="b" * 64,
                semantic_effect_hash="c" * 64,
                capability=capability,
            )

        request_row, outbox_row = captured
        self.assertEqual(request_row["schema_version"], 2)
        self.assertEqual(request_row["source_snapshot"], value.source.canonical_mapping())
        self.assertEqual(request_row["approval_snapshot"]["state"], "unavailable")
        self.assertEqual(request_row["request_snapshot"], value.canonical_mapping())
        self.assertEqual(outbox_row["schema_version"], 3)
        self.assertEqual(outbox_row["operation"], "create_tool_asset")
        self.assertEqual(outbox_row["payload"]["request"], value.canonical_mapping())
        self.assertEqual(
            outbox_row["payload_hash"],
            self.repository.canonical_hash(outbox_row["payload"]),
        )
        self.assertEqual(outbox_row["service_actor_user_id"], "worker@example.invalid")
        serialized = repr(captured).casefold()
        for forbidden in ("endpoint", "credential", "password", "api_key"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
