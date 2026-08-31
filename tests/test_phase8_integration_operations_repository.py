from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

ROOT = Path(__file__).resolve().parents[1]
PROJECT = UUID("00000000-0000-5000-8000-00000000d711")
OPERATION = UUID("00000000-0000-4000-8000-00000000d712")
SOURCE = UUID("00000000-0000-4000-8000-00000000d713")
WORK = UUID("00000000-0000-4000-8000-00000000d714")
TENANT = "tenant-p807"


class AttrDict(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: object) -> None:
        self[name] = value


class Phase8IntegrationOperationsRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.documents.frappe_repository",
        "npi_core.foundation.audit",
        "npi_core.foundation.security",
        "npi_core.project_controls.terminal_guard",
        "npi_integration.inbound_project.frappe_validation",
        "npi_integration.item_publish.frappe_validation",
        "npi_integration.mbom_publish.frappe_validation",
        "npi_integration.tool_asset_request.execution_frappe_validation",
        "npi_integration.integration_operations.frappe_validation",
        "npi_integration.integration_operations.problems",
        "npi_integration.integration_operations.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[object] = []
        self.diagnostics: list[dict[str, object]] = []
        self.saved_rows: list[tuple[str, dict[str, object]]] = []
        self.enqueued: list[dict[str, object]] = []

        frappe = types.ModuleType("frappe")
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.session = types.SimpleNamespace(user="operator@example.invalid")
        frappe.flags = types.SimpleNamespace()
        frappe.get_all = lambda *_args, **_kwargs: []
        frappe.get_doc = lambda *_args, **_kwargs: None
        frappe.db = types.SimpleNamespace(get_value=lambda *_args, **_kwargs: None)

        def enqueue(path: str, **values: object) -> None:
            self.events.append("enqueue")
            self.enqueued.append({"path": path, **values})

        frappe.enqueue = enqueue
        self.frappe = frappe
        sys.modules["frappe"] = frappe

        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: self.diagnostics.append(values)
        sys.modules[api.__name__] = api

        base = types.ModuleType("npi_core.documents.frappe_repository")

        class FrappeDocumentRepository:
            def __init__(self, *, principal, request_id: str, trace_id: str) -> None:
                self.principal = principal
                self.actor = principal.user_id
                self.request_id = request_id
                self.trace_id = trace_id

        base.FrappeDocumentRepository = FrappeDocumentRepository
        base._database_datetime = lambda value: value
        sys.modules[base.__name__] = base

        audit = types.ModuleType("npi_core.foundation.audit")
        audit.create_audit_event = lambda **values: types.SimpleNamespace(
            event_id=UUID("00000000-0000-4000-8000-00000000d719"),
            global_id=values["global_id"],
            object_version=values["object_version"],
            actor=values["actor"],
            trace_id=values["trace_id"],
            operation=values["operation"],
            result=values["result"],
            input_summary=values["input_summary"],
        )
        sys.modules[audit.__name__] = audit
        security = types.ModuleType("npi_core.foundation.security")
        security.Principal = object
        sys.modules[security.__name__] = security
        terminal = types.ModuleType("npi_core.project_controls.terminal_guard")
        terminal.require_mutable_project = lambda _project: self.events.append("mutable")
        sys.modules[terminal.__name__] = terminal

        self._install_owner_validation(
            "npi_integration.inbound_project.frappe_validation",
            scope_name="inbound_project_manual_replay_write",
            save_name="save_inbound_project_replay_document",
        )
        self._install_owner_validation(
            "npi_integration.item_publish.frappe_validation",
            scope_name="item_manual_replay_write",
            actor_scope_name="item_service_actor_scope",
            save_name="save_item_support_document",
        )
        self._install_owner_validation(
            "npi_integration.mbom_publish.frappe_validation",
            scope_name="mbom_manual_replay_write",
            actor_scope_name="mbom_service_actor_scope",
            save_name="save_mbom_support_document",
        )
        self._install_owner_validation(
            "npi_integration.tool_asset_request.execution_frappe_validation",
            scope_name="tool_asset_manual_replay_write",
            actor_scope_name="tool_asset_service_actor_scope",
            save_name="save_tool_asset_support_document",
        )

        central = types.ModuleType(
            "npi_integration.integration_operations.frappe_validation"
        )
        central.INTEGRATION_OPERATIONS_SUPPORT_WRITES = frozenset(
            {
                ("NPI Integration Action Receipt", "insert"),
                ("NPI Integration Reconciliation Observation", "insert"),
            }
        )

        @contextmanager
        def central_scope(**values: object):
            self.events.append(("central-capability", values))
            yield "central-capability"

        central.integration_operations_write_capability = central_scope
        central.insert_integration_operations_support_document = (
            lambda document, *, capability: self.events.append(
                ("central-insert", document, capability)
            )
            or document
        )
        sys.modules[central.__name__] = central
        problems = types.ModuleType("npi_integration.integration_operations.problems")
        problems.IntegrationOperationConflict = type(
            "IntegrationOperationConflict",
            (RuntimeError,),
            {},
        )
        sys.modules[problems.__name__] = problems

        self.module = importlib.import_module(
            "npi_integration.integration_operations.frappe_repository"
        )
        principal = types.SimpleNamespace(
            user_id="operator@example.invalid",
            tenant_id=TENANT,
            roles=frozenset({"System Manager", "NPI API User"}),
            is_external=False,
        )
        self.repository = self.module.FrappeIntegrationOperationsRepository(
            principal=principal,
            request_id="request-p807-repository",
            trace_id="trace-p807-repository",
        )
        self.project = AttrDict(
            global_id=str(PROJECT),
            tenant_id=TENANT,
            owner_user_id="owner@example.invalid",
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def _install_owner_validation(
        self,
        module_name: str,
        *,
        scope_name: str,
        save_name: str,
        actor_scope_name: str | None = None,
    ) -> None:
        module = types.ModuleType(module_name)

        @contextmanager
        def scope(*args: object, **kwargs: object):
            self.events.append((scope_name, args, kwargs))
            yield f"{scope_name}-capability"

        def save(document: AttrDict, *, capability: object):
            self.events.append((save_name, document.doctype, capability))
            self.saved_rows.append((document.doctype, copy_mapping(document)))
            return document

        setattr(module, scope_name, scope)
        setattr(module, save_name, save)
        if actor_scope_name:
            setattr(module, actor_scope_name, scope)
        sys.modules[module_name] = module

    def operation(self, kind: str = "publish_item"):
        enum_kind = self.module.IntegrationOperationKind(kind)
        return self.module.IntegrationOperationReference(
            tenant_id=TENANT,
            project_global_id=PROJECT,
            operation_kind=enum_kind,
            operation_global_id=OPERATION,
            source_global_id=SOURCE,
            operation_version=3,
            raw_state="failed_retryable",
            shared_state=self.module.IntegrationViewState.FAILED_RETRYABLE,
            source_snapshot_hash="a" * 64,
            target_idempotency_key_hash="b" * 64,
        )

    def test_project_list_and_logical_dlq_are_derived_and_bounded(self) -> None:
        operation = self.operation()
        row = AttrDict(doctype="NPI Item Publish Request")
        with patch.multiple(
            self.repository,
            create=True,
            _authorized_project=lambda _project: self.project,
            _can_administer_project=lambda *_args: True,
            _project_operations=lambda *_args, **_kwargs: [
                (operation, row, "2026-08-28T00:00:00.000000Z")
            ],
            _replay_boundaries=lambda *_args: (False, False, False),
        ):
            result = self.repository.list_operations(
                PROJECT,
                operation_kind=None,
                shared_state=None,
                cursor=None,
                limit=50,
            )
            dlq = self.repository.list_operations(
                PROJECT,
                operation_kind=None,
                shared_state=None,
                cursor=None,
                limit=50,
                logical_dlq=True,
            )
        self.assertEqual(result["projectGlobalId"], str(PROJECT))
        self.assertEqual(result["items"], dlq["items"])
        item = result["items"][0]
        self.assertTrue(item["logicalDlq"])
        self.assertTrue(item["replayEligible"])
        self.assertEqual(item["sourceSnapshotHash"], "a" * 64)
        self.assertEqual(item["targetIdempotencyKeyHash"], "b" * 64)
        self.assertNotIn("payload", repr(item).casefold())

    def test_collection_diagnostics_are_exact_innermost_and_response_neutral(self) -> None:
        trace_id = "trace-" + "b" * 32
        error = RuntimeError("withheld business detail")
        with self.assertRaises(RuntimeError) as raised:
            with self.module.integration_operations_collection_diagnostics(
                trace_id,
                active=True,
            ):
                with self.module.integration_operations_collection_step(
                    "P807_COLLECTION_API_REPOSITORY"
                ):
                    with self.module.integration_operations_collection_step(
                        "P807_COLLECTION_ITEM_VALUE"
                    ):
                        raise error
        self.assertIs(raised.exception, error)
        self.assertEqual(
            self.diagnostics,
            [
                {
                    "code": "P807_COLLECTION_ITEM_VALUE",
                    "title": "NPI integration operations collection stage failed",
                    "exception_type": "RuntimeError",
                    "trace_id": trace_id,
                }
            ],
        )
        self.assertFalse(
            hasattr(self.frappe.flags, self.module._COLLECTION_DIAGNOSTIC_FLAG)
        )
        self.assertNotIn("withheld business detail", repr(self.diagnostics))

        self.diagnostics.clear()
        with self.assertRaises(RuntimeError):
            with self.module.integration_operations_collection_diagnostics(
                "wrong-trace",
                active=True,
            ):
                with self.module.integration_operations_collection_step(
                    "P807_COLLECTION_ITEM_VALUE"
                ):
                    raise RuntimeError("withheld")
        self.assertEqual(self.diagnostics, [])

    def test_action_diagnostics_are_exact_innermost_and_response_neutral(self) -> None:
        trace_id = "trace-" + "c" * 32
        error = RuntimeError("withheld business detail")
        with self.assertRaises(RuntimeError) as raised:
            with self.module.integration_operations_action_diagnostics(
                trace_id,
                active=True,
            ):
                with self.module.integration_operations_action_step(
                    "P807_ACTION_API_REPOSITORY"
                ):
                    with self.module.integration_operations_action_step(
                        "P807_ACTION_REPOSITORY_PROJECT"
                    ):
                        raise error
        self.assertIs(raised.exception, error)
        self.assertEqual(
            self.diagnostics,
            [
                {
                    "code": "P807_ACTION_REPOSITORY_PROJECT",
                    "title": "NPI integration operation action stage failed",
                    "exception_type": "RuntimeError",
                    "trace_id": trace_id,
                }
            ],
        )
        self.assertFalse(
            hasattr(self.frappe.flags, self.module._ACTION_DIAGNOSTIC_FLAG)
        )
        self.assertNotIn("withheld business detail", repr(self.diagnostics))

        self.diagnostics.clear()
        with self.assertRaises(RuntimeError):
            with self.module.integration_operations_action_diagnostics(
                "wrong-trace",
                active=True,
            ):
                with self.module.integration_operations_action_step(
                    "P807_ACTION_REPOSITORY_PROJECT"
                ):
                    raise RuntimeError("withheld")
        self.assertEqual(self.diagnostics, [])

    def test_collection_diagnostic_code_contract_matches_api_and_repository(self) -> None:
        api_source = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/api.py"
        ).read_text(encoding="utf-8")
        repository_source = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/frappe_repository.py"
        ).read_text(encoding="utf-8")
        codes = self.module.INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_CODES
        self.assertEqual(len(codes), 58)
        self.assertTrue(
            all(
                api_source.count(f'"{code}"')
                + repository_source.count(f'"{code}"')
                == 2
                for code in codes
            )
        )
        self.assertNotIn("str(error)", repository_source)
        self.assertNotIn("repr(error)", repository_source)

    def test_action_diagnostic_code_contract_matches_api_and_repository(self) -> None:
        api_source = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/api.py"
        ).read_text(encoding="utf-8")
        repository_source = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/frappe_repository.py"
        ).read_text(encoding="utf-8")
        codes = self.module.INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_CODES
        self.assertEqual(len(codes), 22)
        self.assertTrue(
            all(
                api_source.count(f'"{code}"')
                + repository_source.count(f'"{code}"')
                == 2
                for code in codes
            )
        )
        self.assertNotIn("str(error)", repository_source)
        self.assertNotIn("repr(error)", repository_source)

    def test_mock_only_item_validation_is_not_an_erp_operation(self) -> None:
        spec = self.module._SPECS[self.module.IntegrationOperationKind.PUBLISH_ITEM]
        row = AttrDict(
            name=str(OPERATION),
            tenant_id=TENANT,
            project_global_id=str(PROJECT),
            state="validated_mock",
            optimistic_version=1,
            selected_publish_node_global_id=str(SOURCE),
            source_hash="a" * 64,
            target_idempotency_key_hash=None,
        )

        self.assertIsNone(self.repository._operation_value(self.project, spec, row))

        row.state = "queued"
        with self.assertRaisesRegex(Exception, "targetIdempotencyKeyHash is invalid"):
            self.repository._operation_value(self.project, spec, row)

        row.target_idempotency_key_hash = "b" * 64
        operation = self.repository._operation_value(self.project, spec, row)
        self.assertIsNotNone(operation)
        self.assertEqual(operation.raw_state, "queued")
        self.assertEqual(operation.target_idempotency_key_hash, "b" * 64)

    def test_action_permission_projection_matches_command_authority(self) -> None:
        operation = self.operation()
        row = AttrDict(doctype="NPI Item Publish Request")
        with patch.multiple(
            self.repository,
            create=True,
            _authorized_project=lambda _project: self.project,
            _can_administer_project=lambda *_args: True,
            _project_operations=lambda *_args, **_kwargs: [
                (operation, row, "2026-08-28T00:00:00.000000Z")
            ],
            _replay_boundaries=lambda *_args: (False, False, False),
        ):
            self.assertTrue(self.repository.authorize_scope(PROJECT, administer=True))
            self.assertTrue(
                self.repository.list_operations(
                    PROJECT,
                    operation_kind=None,
                    shared_state=None,
                    cursor=None,
                    limit=50,
                )["permissions"]["act"]
            )
            self.repository.principal.roles = frozenset({"System Manager"})
            self.assertFalse(self.repository.authorize_scope(PROJECT, administer=True))
            self.assertFalse(
                self.repository.list_operations(
                    PROJECT,
                    operation_kind=None,
                    shared_state=None,
                    cursor=None,
                    limit=50,
                )["permissions"]["act"]
            )

    def test_replay_and_reconciliation_actions_are_atomic_distinct_and_audited(self) -> None:
        operation = self.operation()
        row = AttrDict(doctype="NPI Item Publish Request")
        receipts = []
        with patch.multiple(
            self.repository,
            create=True,
            _locked_authorized_project=lambda _project: self.project,
            _action_replay=lambda *_args, **_kwargs: None,
            _operation_for_project=lambda *_args, **_kwargs: (
                operation,
                row,
                "2026-08-28T00:00:00.000000Z",
            ),
            _requeue_failed_retryable=lambda *_args: self.events.append("requeue")
            or WORK,
            _insert_action_receipt=lambda value: receipts.append(value)
            or self.events.append("receipt"),
            _append_action_audit=lambda _value: self.events.append("audit"),
            _enqueue_replay=lambda *_args: self.events.append("enqueue"),
        ):
            replay = self.repository.request_action(
                PROJECT,
                operation_kind=operation.operation_kind,
                operation_id=OPERATION,
                action_kind=self.module.IntegrationActionKind.REPLAY,
                expected_raw_state="failed_retryable",
                expected_version=3,
                action_idempotency_key_hash="c" * 64,
            )
        self.assertFalse(replay.replayed)
        self.assertEqual(
            self.events,
            ["mutable", "requeue", "receipt", "audit", "enqueue"],
        )
        receipt = receipts[0]
        self.assertEqual(receipt.operation, operation)
        self.assertEqual(receipt.outcome_reference_global_id, WORK)
        self.assertEqual(receipt.action_idempotency_key_hash, "c" * 64)
        self.assertEqual(receipt.response_hash, self.module.canonical_hash(replay.response))

        self.events.clear()
        receipts.clear()
        with patch.multiple(
            self.repository,
            create=True,
            _locked_authorized_project=lambda _project: self.project,
            _action_replay=lambda *_args, **_kwargs: None,
            _operation_for_project=lambda *_args, **_kwargs: (
                operation,
                row,
                "2026-08-28T00:00:00.000000Z",
            ),
            _requeue_failed_retryable=lambda *_args: self.fail("must not requeue"),
            _insert_action_receipt=lambda value: receipts.append(value)
            or self.events.append("receipt"),
            _append_action_audit=lambda _value: self.events.append("audit"),
            _enqueue_replay=lambda *_args: self.fail("must not enqueue"),
        ):
            reconciliation = self.repository.request_action(
                PROJECT,
                operation_kind=operation.operation_kind,
                operation_id=OPERATION,
                action_kind=self.module.IntegrationActionKind.REQUEST_RECONCILIATION,
                expected_raw_state="failed_retryable",
                expected_version=3,
                action_idempotency_key_hash="d" * 64,
            )
        self.assertEqual(self.events, ["mutable", "receipt", "audit"])
        self.assertIsNone(reconciliation.response["outcomeReferenceGlobalId"])
        self.assertEqual(
            reconciliation.response["outcomeState"],
            "reconciliation_requested",
        )

    def test_exact_action_replay_returns_sealed_response_without_mutation(self) -> None:
        sealed = {
            "actionGlobalId": "00000000-0000-4000-8000-00000000d715",
            "operationGlobalId": str(OPERATION),
            "outcomeState": "replay_requested",
            "outcomeReferenceGlobalId": str(WORK),
        }
        with patch.multiple(
            self.repository,
            create=True,
            _locked_authorized_project=lambda _project: self.project,
            _action_replay=lambda *_args, **_kwargs: sealed,
            _operation_for_project=lambda *_args, **_kwargs: self.fail(
                "must not resolve or mutate an exact action replay"
            ),
        ):
            outcome = self.repository.request_action(
                PROJECT,
                operation_kind=self.module.IntegrationOperationKind.PUBLISH_ITEM,
                operation_id=OPERATION,
                action_kind=self.module.IntegrationActionKind.REPLAY,
                expected_raw_state="failed_retryable",
                expected_version=3,
                action_idempotency_key_hash="e" * 64,
            )
        self.assertTrue(outcome.replayed)
        self.assertEqual(outcome.response, sealed)
        self.assertEqual(self.events, [])

    def test_persisted_action_replay_is_exact_locked_and_integrity_checked(self) -> None:
        operation = self.operation()
        response = {
            "actionGlobalId": "00000000-0000-4000-8000-00000000d715",
            "operationGlobalId": str(OPERATION),
            "outcomeState": "replay_requested",
            "outcomeReferenceGlobalId": str(WORK),
        }
        row = AttrDict(
            tenant_id=TENANT,
            project_global_id=str(PROJECT),
            operation_kind=operation.operation_kind.value,
            operation_global_id=str(OPERATION),
            action_kind="replay",
            actor_user_id=self.repository.actor,
            request_hash="f" * 64,
            response_snapshot=response,
            response_hash=self.module.canonical_hash(response),
        )
        get_doc_calls: list[tuple[object, ...]] = []

        def get_doc(*args: object, **kwargs: object):
            get_doc_calls.append((*args, kwargs))
            return row

        self.frappe.get_all = lambda *_args, **_kwargs: ["receipt-name"]
        self.frappe.get_doc = get_doc
        replay = self.repository._action_replay(
            self.project,
            operation_kind=operation.operation_kind,
            operation_id=OPERATION,
            action_kind=self.module.IntegrationActionKind.REPLAY,
            action_idempotency_key_hash="e" * 64,
            request_hash="f" * 64,
        )
        self.assertEqual(replay, response)
        self.assertEqual(
            get_doc_calls,
            [
                (
                    "NPI Integration Action Receipt",
                    "receipt-name",
                    {"for_update": True},
                )
            ],
        )

        row.request_hash = "0" * 64
        with self.assertRaises(self.module.IntegrationOperationConflict):
            self.repository._action_replay(
                self.project,
                operation_kind=operation.operation_kind,
                operation_id=OPERATION,
                action_kind=self.module.IntegrationActionKind.REPLAY,
                action_idempotency_key_hash="e" * 64,
                request_hash="f" * 64,
            )
        row.request_hash = "f" * 64
        row.response_hash = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "integrity"):
            self.repository._action_replay(
                self.project,
                operation_kind=operation.operation_kind,
                operation_id=OPERATION,
                action_kind=self.module.IntegrationActionKind.REPLAY,
                action_idempotency_key_hash="e" * 64,
                request_hash="f" * 64,
            )

    def test_item_replay_preserves_immutable_request_and_target_identity(self) -> None:
        operation = self.operation("publish_item")
        row = AttrDict(
            doctype="NPI Item Publish Request",
            name=str(OPERATION),
            service_actor_user_id="service@example.invalid",
            source_hash="a" * 64,
            source_stream_key_hash="f" * 64,
            target_idempotency_key_hash="b" * 64,
            result_global_id=str(WORK),
            optimistic_version=3,
            updated_at="old",
        )
        outbox = retryable_outbox(
            "NPI Outbox Message",
            result_field="result_global_id",
        )
        attempt = retryable_attempt()
        result = retryable_result()
        guard = active_retryable_guard(row)
        self.frappe.db.get_value = lambda *_args, **_kwargs: guard.name
        self.frappe.get_doc = lambda *_args, **_kwargs: guard
        with patch.multiple(
            self.repository,
            _outbox=lambda *_args, **_kwargs: outbox,
            _last_attempt=lambda *_args, **_kwargs: attempt,
            _result=lambda *_args, **_kwargs: result,
        ):
            reference = self.repository._requeue_item(operation, row)
        self.assertEqual(reference, UUID(str(outbox.event_id)))
        self.assertEqual(row.state, "queued")
        self.assertIsNone(row.result_global_id)
        self.assertEqual(row.optimistic_version, 4)
        self.assertEqual(row.source_hash, "a" * 64)
        self.assertEqual(row.target_idempotency_key_hash, "b" * 64)
        assert_outbox_reset(self, outbox, "result_global_id")
        self.assertEqual(guard.active_request_global_id, str(OPERATION))
        self.assertEqual(guard.active_target_idempotency_key_hash, "b" * 64)

    def test_retryable_stream_guard_requires_the_owner_canonical_binding(self) -> None:
        row = AttrDict(
            name=str(OPERATION),
            source_stream_key_hash="f" * 64,
            target_idempotency_key_hash="b" * 64,
        )
        guard = AttrDict(
            name="guard-p807",
            active_request_global_id=str(OPERATION),
            active_target_idempotency_key_hash="b" * 64,
            active_state="failed_retryable",
            last_request_global_id=None,
            last_target_idempotency_key_hash=None,
            last_state=None,
        )
        self.frappe.db.get_value = lambda *_args, **_kwargs: guard.name
        self.frappe.get_doc = lambda *_args, **_kwargs: guard

        self.assertIs(
            self.repository._stream_guard(
                "NPI Item Publish Stream Guard",
                row,
                lock=True,
                active_retryable=True,
            ),
            guard,
        )
        with self.assertRaises(self.module.IntegrationOperationConflict):
            self.repository._stream_guard(
                "NPI MBOM Publish Stream Guard",
                row,
                lock=True,
            )

        guard.active_request_global_id = None
        guard.active_target_idempotency_key_hash = None
        guard.active_state = None
        guard.last_request_global_id = str(OPERATION)
        guard.last_target_idempotency_key_hash = "b" * 64
        guard.last_state = "failed_retryable"
        self.assertIs(
            self.repository._stream_guard(
                "NPI MBOM Publish Stream Guard",
                row,
                lock=True,
            ),
            guard,
        )
        with self.assertRaises(self.module.IntegrationOperationConflict):
            self.repository._stream_guard(
                "NPI Item Publish Stream Guard",
                row,
                lock=True,
                active_retryable=True,
            )

        for field, wrong_value in (
            ("last_target_idempotency_key_hash", "c" * 64),
            ("last_state", "failed_final"),
            ("active_state", "failed_retryable"),
        ):
            with self.subTest(field=field):
                original = guard[field]
                guard[field] = wrong_value
                with self.assertRaises(self.module.IntegrationOperationConflict):
                    self.repository._stream_guard(
                        "NPI Tool Asset Stream Guard",
                        row,
                        lock=True,
                    )
                guard[field] = original

    def test_mbom_and_tool_replay_reset_only_exact_owned_work(self) -> None:
        for kind, method_name, request_state in (
            ("publish_mbom", "_requeue_mbom", "state"),
            ("create_tool_asset", "_requeue_tool_asset", "execution_state"),
            ("update_tool_asset", "_requeue_tool_asset", "execution_state"),
        ):
            with self.subTest(kind=kind):
                self.events.clear()
                self.saved_rows.clear()
                operation = self.operation(kind)
                row = AttrDict(
                    doctype=(
                        "NPI MBOM Publish Request"
                        if kind == "publish_mbom"
                        else "NPI Tool Asset Request"
                    ),
                    name=str(OPERATION),
                    source_hash="a" * 64,
                    target_idempotency_key_hash="b" * 64,
                    source_stream_key_hash="f" * 64,
                    service_actor_user_id="service@example.invalid",
                    result_global_id=str(WORK),
                    optimistic_version=3,
                    updated_at="old",
                    operation=kind,
                )
                row[request_state] = "failed_retryable"
                outbox = retryable_outbox(
                    "NPI Outbox Message",
                    result_field=(
                        "mbom_result_global_id"
                        if kind == "publish_mbom"
                        else "tool_asset_result_global_id"
                    ),
                )
                outbox.service_actor_user_id = "service@example.invalid"
                guard = retryable_guard(row)
                nodes = [
                    AttrDict(
                        doctype="NPI MBOM Publish Node",
                        name=str(WORK),
                        state="failed_retryable",
                        result_global_id=str(WORK),
                        optimistic_version=1,
                        updated_at="old",
                    )
                ]
                patches = {
                    "_outbox": lambda *_args, **_kwargs: outbox,
                    "_last_attempt": lambda *_args, **_kwargs: retryable_attempt(),
                    "_result": lambda *_args, **_kwargs: retryable_result(),
                    "_stream_guard": lambda *_args, **_kwargs: guard,
                }
                if kind == "publish_mbom":
                    patches["_mbom_nodes"] = lambda *_args, **_kwargs: nodes
                with patch.multiple(self.repository, **patches):
                    reference = getattr(self.repository, method_name)(operation, row)
                self.assertEqual(reference, UUID(str(outbox.event_id)))
                self.assertEqual(row[request_state], "queued")
                self.assertIsNone(row.result_global_id)
                self.assertEqual(row.source_hash, "a" * 64)
                self.assertEqual(row.target_idempotency_key_hash, "b" * 64)
                result_field = (
                    "mbom_result_global_id"
                    if kind == "publish_mbom"
                    else "tool_asset_result_global_id"
                )
                assert_outbox_reset(self, outbox, result_field)
                if kind == "publish_mbom":
                    self.assertEqual(nodes[0].state, "queued")
                    self.assertIsNone(nodes[0].result_global_id)

    def test_inbound_replay_preserves_signed_source_and_project_containment(self) -> None:
        operation = self.operation("receive_project_submission")
        row = AttrDict(
            doctype="NPI Inbox Message",
            name=str(OPERATION),
            state="failed_retryable",
            disposition="failed_retryable",
            project_global_id=str(PROJECT),
            event_snapshot={"opaque": "retained"},
            canonical_event_hash="a" * 64,
            source_key_hash="b" * 64,
            claim_token=str(WORK),
            claimed_at="old",
            lease_expires_at="old",
            last_error_code="TARGET_UNAVAILABLE",
            last_error_at="old",
            project_result_hash=None,
        )
        reference = self.repository._requeue_inbound(operation, row)
        self.assertEqual(reference, OPERATION)
        self.assertEqual(row.state, "pending")
        self.assertEqual(row.disposition, "pending")
        self.assertIsNone(row.claim_token)
        self.assertIsNone(row.last_error_code)
        self.assertEqual(row.project_global_id, str(PROJECT))
        self.assertEqual(row.event_snapshot, {"opaque": "retained"})
        self.assertEqual(row.canonical_event_hash, "a" * 64)
        self.assertEqual(row.source_key_hash, "b" * 64)

    def test_retryable_boundary_rejects_crossed_uncertain_or_authenticated_truth(self) -> None:
        outbox = retryable_outbox("NPI Outbox Message", result_field="result_global_id")
        attempt = retryable_attempt()
        result = retryable_result()
        self.assertTrue(self.module._safe_retryable_boundary(outbox, attempt, result))
        for value, field in (
            (outbox, "adapter_boundary_crossed"),
            (attempt, "adapter_boundary_crossed"),
            (attempt, "reconciliation_required"),
            (result, "response_authenticated"),
        ):
            with self.subTest(field=field):
                value[field] = 1
                self.assertFalse(
                    self.module._safe_retryable_boundary(outbox, attempt, result)
                )
                value[field] = 0
        result.authority = "authoritative_sandbox"
        self.assertFalse(self.module._safe_retryable_boundary(outbox, attempt, result))
        result.authority = "none"
        result.state = "uncertain_after_timeout"
        self.assertFalse(self.module._safe_retryable_boundary(outbox, attempt, result))

    def test_enqueue_is_fixed_after_commit_and_source_has_no_transport_or_sql(self) -> None:
        for kind, expected_path, argument in (
            (
                "receive_project_submission",
                "npi_integration.inbound_project.worker.process_inbox_message",
                "receipt_id",
            ),
            (
                "publish_item",
                "npi_integration.item_publish.worker.process_outbox_message",
                "outbox_event_id",
            ),
            (
                "publish_mbom",
                "npi_integration.mbom_publish.worker.process_outbox_message",
                "outbox_event_id",
            ),
            (
                "create_tool_asset",
                "npi_integration.tool_asset_request.worker.process_outbox_message",
                "outbox_event_id",
            ),
            (
                "update_tool_asset",
                "npi_integration.tool_asset_request.worker.process_outbox_message",
                "outbox_event_id",
            ),
        ):
            with self.subTest(kind=kind):
                self.enqueued.clear()
                self.repository._enqueue_replay(
                    self.module.IntegrationOperationKind(kind),
                    WORK,
                    OPERATION,
                )
                queued = self.enqueued[0]
                self.assertEqual(queued["path"], expected_path)
                self.assertTrue(queued["enqueue_after_commit"])
                self.assertTrue(queued["deduplicate"])
                self.assertEqual(queued[argument], str(WORK))
                self.assertEqual(
                    queued["job_id"],
                    f"integration-replay-{OPERATION}",
                )
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/integration_operations/frappe_repository.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "requests.",
            "httpx.",
            "urllib.request",
            "frappe.db." + "sql",
            "credential",
            "authorization",
            "target_request",
            "target_response",
            "ignore_permissions",
        ):
            self.assertNotIn(forbidden, source.casefold())


def copy_mapping(value: AttrDict) -> dict[str, object]:
    return {key: item for key, item in value.items()}


def retryable_outbox(doctype: str, *, result_field: str) -> AttrDict:
    value = AttrDict(
        doctype=doctype,
        event_id=str(WORK),
        state="failed_retryable",
        disposition="failed_retryable",
        claim_token=str(WORK),
        claimed_at="old",
        lease_expires_at="old",
        adapter_boundary_crossed=0,
        attempt_count=1,
        last_attempt_global_id=str(WORK),
        mbom_last_attempt_global_id=str(WORK),
        tool_asset_last_attempt_global_id=str(WORK),
        last_error_code="TARGET_UNAVAILABLE",
        last_error_at="old",
        payload={"immutable": "retained"},
        source_hash="a" * 64,
        target_idempotency_key_hash="b" * 64,
    )
    value[result_field] = str(WORK)
    return value


def retryable_attempt() -> AttrDict:
    return AttrDict(
        adapter_boundary_crossed=0,
        reconciliation_required=0,
    )


def retryable_result() -> AttrDict:
    return AttrDict(
        state="failed_retryable",
        authority="none",
        response_authenticated=0,
    )


def retryable_guard(row: AttrDict) -> AttrDict:
    return AttrDict(
        doctype=(
            "NPI Item Publish Stream Guard"
            if row.doctype == "NPI Item Publish Request"
            else "NPI MBOM Publish Stream Guard"
            if row.doctype == "NPI MBOM Publish Request"
            else "NPI Tool Asset Stream Guard"
        ),
        active_request_global_id=None,
        active_target_idempotency_key_hash=None,
        active_state=None,
        last_request_global_id=row.name,
        last_state="failed_retryable",
        optimistic_version=3,
        updated_at="old",
    )


def active_retryable_guard(row: AttrDict) -> AttrDict:
    return AttrDict(
        doctype="NPI Item Publish Stream Guard",
        name="guard-p807-active",
        active_request_global_id=row.name,
        active_target_idempotency_key_hash=row.target_idempotency_key_hash,
        active_state="failed_retryable",
        last_request_global_id=None,
        last_target_idempotency_key_hash=None,
        last_state=None,
        optimistic_version=3,
        updated_at="old",
    )


def assert_outbox_reset(
    owner: unittest.TestCase,
    outbox: AttrDict,
    result_field: str,
) -> None:
    owner.assertEqual(outbox.state, "pending")
    owner.assertEqual(outbox.disposition, "pending")
    owner.assertIsNone(outbox.claim_token)
    owner.assertFalse(outbox.adapter_boundary_crossed)
    owner.assertIsNone(outbox.last_error_code)
    owner.assertIsNone(outbox[result_field])
    owner.assertEqual(outbox.attempt_count, 1)
    owner.assertEqual(outbox.payload, {"immutable": "retained"})
    owner.assertEqual(outbox.source_hash, "a" * 64)
    owner.assertEqual(outbox.target_idempotency_key_hash, "b" * 64)


if __name__ == "__main__":
    unittest.main()
