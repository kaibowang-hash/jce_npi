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
from tests.test_phase8_tool_asset_config import base as profile_base  # noqa: E402
from npi_integration.tool_asset_request.config import ToolAssetExecutionProfile  # noqa: E402
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

    def test_command_context_diagnostic_stages_are_unique_same_exception_and_read_only(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.tool_asset_request.diagnostics"
        )
        source_text = (
            ROOT
            / "apps/npi_integration/npi_integration/tool_asset_request/frappe_repository.py"
        ).read_text(encoding="utf-8")
        repository_codes = (
            "P805_TOOL_ASSET_CONTEXT_PROFILE_RESOLVE",
            "P805_TOOL_ASSET_CONTEXT_CREATE_SOURCE",
            "P805_TOOL_ASSET_CONTEXT_CREATE_PROFILE_BINDING",
            "P805_TOOL_ASSET_CONTEXT_CREATE_AUTHORITY",
            "P805_TOOL_ASSET_CONTEXT_CREATE_SANDBOX_GUARD",
            "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
            "P805_TOOL_ASSET_CONTEXT_CREATE_REQUEST_BUILD",
        )
        for code in repository_codes:
            with self.subTest(code=code):
                self.assertEqual(source_text.count(f'"{code}"'), 1)
                self.assertIn(code, diagnostics.TOOL_ASSET_CONTEXT_DIAGNOSTIC_CODES)

        project = types.SimpleNamespace(
            tenant_id="tenant-synthetic",
            global_id=uid(1),
        )
        expected = ToolAssetMappingExpectation(
            ToolAssetExecutionOperation.CREATE,
            source().source_stream_key_hash,
            0,
        )

        def configured_repository():
            repository = self.bare_repository()
            writes: list[str] = []
            repository._execution_source = lambda *_args, **_kwargs: source()
            repository._current_actor_member = lambda _project: object()
            repository._mapping_expectation = lambda *_args, **_kwargs: expected
            repository._new_uuid = lambda: uid(20)
            repository._now = lambda: NOW
            repository._diagnostic_writes = writes
            repository._insert_execution_request = (
                lambda *_args, **_kwargs: writes.append("request")
            )
            repository._insert_execution_outbox = (
                lambda *_args, **_kwargs: writes.append("outbox")
            )
            repository._append_execution_audit = (
                lambda *_args, **_kwargs: writes.append("audit")
            )
            return repository

        def configured_profile(mode: ToolAssetExecutionTargetMode):
            values = profile_base(mode)
            if mode is ToolAssetExecutionTargetMode.SYNTHETIC:
                values.update(
                    {
                        "environment_code": "disposable-test",
                        "allowed_operations": (
                            "create_tool_asset",
                            "update_tool_asset",
                        ),
                        "adapter_resolver": "npi_integration.synthetic_adapter",
                        "synthetic_test_only": True,
                        "disposable_runtime_marker": True,
                    }
                )
            elif mode is ToolAssetExecutionTargetMode.SANDBOX:
                values.update(
                    {
                        "environment_code": "sandbox",
                        "allowed_operations": (
                            "create_tool_asset",
                            "update_tool_asset",
                        ),
                        "adapter_resolver": "npi_integration.sandbox_adapter",
                        "base_url": "https://sandbox.erpnext.example.invalid",
                        "allowed_hostnames": (
                            "sandbox.erpnext.example.invalid",
                        ),
                        "secret_reference": "secrets/tool-asset-sandbox",
                        "response_authentication": "hmac-sha256-v1",
                        "connect_timeout_seconds": 5,
                        "read_timeout_seconds": 30,
                        "non_production_attested": True,
                    }
                )
            return ToolAssetExecutionProfile(**values)

        def invoke(repository, selected_profile):
            return repository._build_execution_request(
                project,
                uid(2),
                uid(3),
                uid(6),
                selected_profile,
                ToolAssetExecutionOperation.CREATE,
                idempotency_key_hash="a" * 64,
                lock=False,
            )

        original = RuntimeError("private command context value")
        cases = []

        repository = configured_repository()
        repository._execution_source = lambda *_args, **_kwargs: (_ for _ in ()).throw(original)
        cases.append(("P805_TOOL_ASSET_CONTEXT_CREATE_SOURCE", repository, configured_profile(ToolAssetExecutionTargetMode.SYNTHETIC), None))

        repository = configured_repository()
        mismatched = replace(
            configured_profile(ToolAssetExecutionTargetMode.SYNTHETIC),
            tenant_id="other-tenant",
        )
        cases.append(("P805_TOOL_ASSET_CONTEXT_CREATE_PROFILE_BINDING", repository, mismatched, "ToolAssetExecutionProfileUnavailable"))

        repository = configured_repository()
        repository._current_actor_member = lambda _project: None
        cases.append(("P805_TOOL_ASSET_CONTEXT_CREATE_AUTHORITY", repository, configured_profile(ToolAssetExecutionTargetMode.SYNTHETIC), "ToolAssetExecutionAuthorityUnavailable"))

        repository = configured_repository()
        cases.append(("P805_TOOL_ASSET_CONTEXT_CREATE_SANDBOX_GUARD", repository, configured_profile(ToolAssetExecutionTargetMode.SANDBOX), "ToolAssetExecutionApprovalUnavailable"))

        repository = configured_repository()
        repository._mapping_expectation = lambda *_args, **_kwargs: (_ for _ in ()).throw(original)
        cases.append(("P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING", repository, configured_profile(ToolAssetExecutionTargetMode.SYNTHETIC), None))

        repository = configured_repository()
        repository._new_uuid = lambda: (_ for _ in ()).throw(original)
        cases.append(("P805_TOOL_ASSET_CONTEXT_CREATE_REQUEST_BUILD", repository, configured_profile(ToolAssetExecutionTargetMode.SYNTHETIC), None))

        for code, repository, selected_profile, expected_type in cases:
            records: list[tuple[str, Exception]] = []
            with self.subTest(code=code), patch.object(
                diagnostics,
                "_record_context_failure",
                side_effect=lambda observed_code, error: records.append(
                    (observed_code, error)
                ),
            ):
                with self.assertRaises(Exception) as caught:
                    invoke(repository, selected_profile)
            self.assertEqual([value[0] for value in records], [code])
            self.assertIs(records[0][1], caught.exception)
            if expected_type is None:
                self.assertIs(caught.exception, original)
            else:
                self.assertEqual(type(caught.exception).__name__, expected_type)
            self.assertEqual(repository._diagnostic_writes, [])

        repository = configured_repository()
        repository._mapping_expectation = lambda *_args, **_kwargs: (_ for _ in ()).throw(original)
        records = []
        with patch.object(
            diagnostics,
            "_record_context_failure",
            side_effect=lambda code, error: records.append((code, error)),
        ):
            with self.assertRaises(RuntimeError) as caught:
                repository._build_execution_request(
                    project,
                    uid(2),
                    uid(3),
                    uid(6),
                    configured_profile(ToolAssetExecutionTargetMode.SYNTHETIC),
                    ToolAssetExecutionOperation.UPDATE,
                    idempotency_key_hash="a" * 64,
                    lock=False,
                )
        self.assertIs(caught.exception, original)
        self.assertEqual(records, [])
        self.assertEqual(repository._diagnostic_writes, [])

        repository = configured_repository()
        repository._authorized_project = lambda _project_id: project
        repository._master_for_project = lambda *_args: object()
        repository._tooling_set_for_project = lambda *_args: object()
        repository._read_execution_profile = lambda _project: (_ for _ in ()).throw(original)
        records = []
        with patch.object(
            diagnostics,
            "_record_context_failure",
            side_effect=lambda code, error: records.append((code, error)),
        ):
            with self.assertRaises(RuntimeError) as caught:
                repository.list_execution_requests(uid(1), uid(2), uid(3))
        self.assertIs(caught.exception, original)
        self.assertEqual(
            records,
            [("P805_TOOL_ASSET_CONTEXT_PROFILE_RESOLVE", original)],
        )
        self.assertEqual(repository._diagnostic_writes, [])

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

    def test_public_request_keeps_immutable_snapshot_and_projects_current_execution_truth(self) -> None:
        request = self.request(ToolAssetExecutionTargetMode.SYNTHETIC)
        snapshot = request.canonical_mapping()
        result_global_id = uid(31)
        row = types.SimpleNamespace(
            global_id=str(request.global_id),
            request_snapshot=snapshot,
            payload_hash=request.payload_hash,
            source_hash=request.source.source_hash,
            execution_state=ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED.value,
            optimistic_version=3,
            dispatch_allowed=0,
            outbox_event_id=str(uid(30)),
            target_idempotency_key_hash="b" * 64,
            semantic_effect_hash="c" * 64,
            result_global_id=str(result_global_id),
        )

        public = self.repository.FrappeToolAssetRequestRepository._execution_request_public(
            row
        )

        self.assertEqual(snapshot["state"], ToolAssetExecutionRequestState.QUEUED.value)
        self.assertEqual(
            public["request"]["state"],
            ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED.value,
        )
        self.assertEqual(public["request"]["optimisticVersion"], 3)
        self.assertEqual(public["request"]["payloadHash"], request.payload_hash)
        self.assertEqual(public["resultGlobalId"], str(result_global_id))
        self.assertEqual(snapshot, request.canonical_mapping())

    def test_detail_projects_bounded_empty_execution_truth_without_mutation(self) -> None:
        repository = self.bare_repository()
        request = self.request(ToolAssetExecutionTargetMode.SYNTHETIC)
        row = types.SimpleNamespace(
            global_id=str(request.global_id),
            request_snapshot=request.canonical_mapping(),
            payload_hash=request.payload_hash,
            source_hash=request.source.source_hash,
            execution_state=ToolAssetExecutionRequestState.QUEUED.value,
            optimistic_version=1,
            dispatch_allowed=1,
            outbox_event_id=str(uid(30)),
            target_idempotency_key_hash="b" * 64,
            semantic_effect_hash="c" * 64,
            result_global_id=None,
        )
        project = types.SimpleNamespace(
            tenant_id=request.source.tenant_id,
            global_id=request.source.project_global_id,
        )
        repository._authorized_project = lambda _identity: project
        repository._master_for_project = lambda *_args: object()
        repository._tooling_set_for_project = lambda *_args: object()
        repository._execution_request_for_scope = lambda *_args, **_kwargs: row
        repository._bounded_documents = lambda *_args, **_kwargs: ()
        repository._read_execution_profile = lambda _project: None
        repository._execution_permissions = lambda *_args: {
            "canView": True,
            "canCreate": False,
            "canUpdate": False,
        }

        detail = repository.execution_request_detail(
            request.source.project_global_id,
            request.source.tooling_master_global_id,
            request.source.tooling_set_global_id,
            request.global_id,
        )

        self.assertEqual(detail["attempts"], [])
        self.assertIsNone(detail["result"])
        self.assertEqual(detail["fieldResults"], [])
        self.assertIsNone(detail["mappingObservation"])
        self.assertIsNone(detail["currentMapping"])
        self.assertEqual(detail["request"]["state"], "queued")

    def test_non_authoritative_mapping_observation_withholds_all_asset_identity(self) -> None:
        repository = self.bare_repository()
        request = self.request(ToolAssetExecutionTargetMode.SYNTHETIC)
        result = {
            "globalId": str(uid(31)),
            "attemptGlobalId": str(uid(32)),
            "state": "synthetic_verified",
            "authority": "synthetic",
            "responseAuthenticated": False,
        }
        snapshot = {
            "schemaVersion": 2,
            "globalId": str(uid(33)),
            "tenantId": request.source.tenant_id,
            "projectGlobalId": str(request.source.project_global_id),
            "toolingSetGlobalId": str(request.source.tooling_set_global_id),
            "sourceStreamKeyHash": request.source.source_stream_key_hash,
            "requestGlobalId": str(request.global_id),
            "resultGlobalId": result["globalId"],
            "attemptGlobalId": result["attemptGlobalId"],
            "operation": request.operation.value,
            "sourceHash": request.source.source_hash,
            "mappingExpectationHash": self.repository.canonical_hash(
                request.mapping_expectation.canonical_mapping()
            ),
            "previousMappingVersion": 0,
            "previousFormalAssetId": None,
            "previousTargetVersion": None,
            "previousObservationHash": None,
            "observedFormalAssetId": None,
            "observedTargetVersion": None,
            "authority": "synthetic",
            "responseAuthenticated": False,
            "responseHash": "9" * 64,
            "disposition": "non_authoritative",
            "observedAt": NOW.isoformat().replace("+00:00", "Z"),
        }
        row = types.SimpleNamespace(
            global_id=snapshot["globalId"],
            tenant_id=snapshot["tenantId"],
            project_global_id=snapshot["projectGlobalId"],
            tooling_set_global_id=snapshot["toolingSetGlobalId"],
            source_stream_key_hash=snapshot["sourceStreamKeyHash"],
            request_global_id=snapshot["requestGlobalId"],
            result_global_id=snapshot["resultGlobalId"],
            attempt_global_id=snapshot["attemptGlobalId"],
            operation=snapshot["operation"],
            source_hash=snapshot["sourceHash"],
            mapping_expectation_hash=snapshot["mappingExpectationHash"],
            disposition="non_authoritative",
            authority="synthetic",
            response_authenticated=0,
            observation_snapshot=snapshot,
            observation_hash=self.repository.canonical_hash(snapshot),
        )
        repository._bounded_documents = lambda *_args, **_kwargs: (row,)
        project = types.SimpleNamespace(
            tenant_id=request.source.tenant_id,
            global_id=request.source.project_global_id,
        )

        observation, current = repository._execution_mapping_public(
            project, request, result
        )

        self.assertIsNone(current)
        self.assertIsNone(observation["previousFormalAssetId"])
        self.assertIsNone(observation["observedFormalAssetId"])
        row.observation_hash = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "observation is invalid"):
            repository._execution_mapping_public(project, request, result)


if __name__ == "__main__":
    unittest.main()
