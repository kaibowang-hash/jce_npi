from __future__ import annotations

import importlib
import inspect
import json
import sys
import types
import unittest
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.tool_asset_request.execution_domain import (  # noqa: E402
    ToolAssetApprovalState,
    ToolAssetBusinessApprovalReference,
    ToolAssetExecutionOperation,
    ToolAssetExecutionRequest,
    ToolAssetExecutionRequestState,
    ToolAssetExecutionTargetMode,
    ToolAssetMappingExpectation,
)
from tests.test_phase8_tool_asset_adapters import execution_profile  # noqa: E402
from tests.test_phase8_tool_asset_domain import NOW, profile, source, uid  # noqa: E402


class Phase8ToolAssetWorkerRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake = sys.modules.setdefault("frappe", types.ModuleType("frappe"))
        fake.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        fake._ = lambda value: value
        fake.flags = types.SimpleNamespace()
        fake.session = types.SimpleNamespace(user="worker@example.invalid")
        fake.PermissionError = type("PermissionError", (Exception,), {})
        fake.throw = lambda message, error=None: (_ for _ in ()).throw((error or RuntimeError)(message))
        fake.generate_hash = lambda length: "claim-token"
        fake.get_all = lambda *a, **k: []
        fake.db = types.SimpleNamespace(get_value=lambda *a, **k: None)
        cls.module = importlib.import_module("npi_integration.tool_asset_request.worker_repository")

    def test_deterministic_result_and_field_ids_bind_attempt_and_field(self):
        attempt = UUID(int=41)
        self.assertEqual(self.module.deterministic_tool_asset_result_id(attempt), self.module.deterministic_tool_asset_result_id(attempt))
        first = self.module.deterministic_tool_asset_field_result_id(attempt, "tooling_master_title")
        second = self.module.deterministic_tool_asset_field_result_id(attempt, "physical_set_serial")
        self.assertNotEqual(first, second)

    def test_database_datetimes_read_naive_as_utc_and_reject_invalid(self):
        naive = datetime(2026, 8, 24, 10)
        self.assertEqual(self.module._aware_utc(naive).tzinfo, UTC)
        self.assertEqual(self.module._aware_utc("2026-08-24 10:00:00").tzinfo, UTC)
        with self.assertRaises(RuntimeError):
            self.module._aware_utc("not-a-datetime")

    def test_result_persistence_normalizes_only_datetime_columns(self):
        observed_at = self.module._utc_text(NOW)
        db_observed_at = self.module._db_datetime(NOW)
        result = {
            "globalId": str(uid(51)),
            "requestGlobalId": str(uid(52)),
            "outboxEventId": str(uid(53)),
            "attemptGlobalId": str(uid(54)),
            "attemptNumber": 1,
            "operation": ToolAssetExecutionOperation.CREATE.value,
            "sourceHash": "a" * 64,
            "mappingExpectationHash": "b" * 64,
            "state": ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED.value,
            "authority": "synthetic",
            "responseAuthenticated": False,
            "responseHash": "c" * 64,
            "faultKind": "none",
            "fieldResultSetHash": "d" * 64,
            "formalAssetId": None,
            "targetVersion": None,
            "observedAt": observed_at,
        }
        field = {
            "globalId": str(uid(55)),
            "requestGlobalId": result["requestGlobalId"],
            "resultGlobalId": result["globalId"],
            "attemptGlobalId": result["attemptGlobalId"],
            "fieldCode": "tooling_master_title",
            "state": "verified",
            "authority": "synthetic",
            "responseAuthenticated": False,
            "responseHash": "e" * 64,
            "faultKind": "none",
            "observedAt": observed_at,
        }
        observation = {
            "globalId": str(uid(56)),
            "tenantId": "tenant-a",
            "projectGlobalId": str(uid(57)),
            "toolingSetGlobalId": str(uid(58)),
            "sourceStreamKeyHash": "f" * 64,
            "requestGlobalId": result["requestGlobalId"],
            "resultGlobalId": result["globalId"],
            "attemptGlobalId": result["attemptGlobalId"],
            "operation": result["operation"],
            "sourceHash": result["sourceHash"],
            "mappingExpectationHash": result["mappingExpectationHash"],
            "previousMappingVersion": 0,
            "previousFormalAssetId": None,
            "previousTargetVersion": None,
            "previousObservationHash": None,
            "observedFormalAssetId": None,
            "observedTargetVersion": None,
            "authority": "synthetic",
            "responseAuthenticated": False,
            "responseHash": result["responseHash"],
            "disposition": "observe_only",
            "observedAt": observed_at,
        }

        before_hashes = tuple(
            self.module.canonical_hash(value)
            for value in (result, field, observation)
        )
        persisted = (
            self.module._snake_result(result),
            self.module._snake_field(field),
            self.module._snake_observation(observation),
        )
        self.assertTrue(
            all(value["observed_at"] == db_observed_at for value in persisted)
        )
        self.assertNotIn("T", db_observed_at)
        self.assertNotIn("Z", db_observed_at)
        self.assertEqual(
            before_hashes,
            tuple(
                self.module.canonical_hash(value)
                for value in (result, field, observation)
            ),
        )
        self.assertTrue(
            all(value["observedAt"] == observed_at for value in (result, field, observation))
        )

        def pinned_frappe_v15_valid_value(fieldtype: str, value: object) -> object:
            if fieldtype == "JSON" and isinstance(value, dict):
                return json.dumps(value, separators=(",", ":"))
            if isinstance(value, datetime):
                return str(value)
            return value

        self.assertIsInstance(
            pinned_frappe_v15_valid_value("JSON", result),
            str,
        )
        self.assertEqual(
            pinned_frappe_v15_valid_value("Datetime", observed_at),
            observed_at,
        )
        self.assertEqual(
            pinned_frappe_v15_valid_value("Datetime", NOW),
            str(NOW),
        )

    def _attempt(self, *, started_at, finished_at=None):
        return types.SimpleNamespace(
            doctype="NPI Tool Asset Attempt",
            global_id=str(uid(41)),
            request_global_id=str(uid(42)),
            outbox_event_id=str(uid(43)),
            attempt_number=1,
            claim_token=str(uid(44)),
            operation=ToolAssetExecutionOperation.CREATE.value,
            target_idempotency_key_hash="a" * 64,
            source_hash="b" * 64,
            mapping_expectation_hash="c" * 64,
            profile_id="synthetic-tool-asset-v1",
            profile_version=1,
            profile_snapshot_hash="d" * 64,
            state="started",
            adapter_boundary_crossed=0,
            request_snapshot_hash="e" * 64,
            transport_disposition=None,
            response_hash=None,
            fault_kind=None,
            reconciliation_required=0,
            safe_error_code=None,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _boundary_claim(self):
        exact_profile = execution_profile(ToolAssetExecutionTargetMode.SYNTHETIC)
        claim = types.SimpleNamespace(
            service_actor_user_id=exact_profile.service_actor_user_id,
            trace_id="trace-p805-boundary-roundtrip",
            request_global_id=uid(42),
            attempt_number=1,
            request=types.SimpleNamespace(
                profile=exact_profile.reference,
                operation=ToolAssetExecutionOperation.CREATE,
            ),
        )
        return claim, exact_profile

    def test_attempt_snapshot_normalizes_db_string_naive_and_aware_datetimes(self):
        finished = NOW + timedelta(seconds=5)
        variants = (
            (
                self.module._db_datetime(NOW),
                self.module._db_datetime(finished),
            ),
            (NOW.replace(tzinfo=None), finished.replace(tzinfo=None)),
            (NOW, finished),
        )
        snapshots = []
        hashes = []
        for started_at, finished_at in variants:
            attempt = self._attempt(
                started_at=started_at,
                finished_at=finished_at,
            )
            self.module._set_attempt_snapshot(attempt)
            snapshots.append(dict(attempt.attempt_snapshot))
            hashes.append(attempt.attempt_hash)
        self.assertEqual(snapshots[1:], snapshots[:1] * 2)
        self.assertEqual(hashes[1:], hashes[:1] * 2)
        self.assertEqual(snapshots[0]["started_at"], self.module._db_datetime(NOW))
        self.assertEqual(
            snapshots[0]["finished_at"],
            self.module._db_datetime(finished),
        )

    def test_hydrated_boundary_preserves_attempt_outbox_audit_order(self):
        claim, exact_profile = self._boundary_claim()
        outbox = types.SimpleNamespace(
            doctype="NPI Outbox Message",
            adapter_boundary_crossed=0,
        )
        attempt = self._attempt(started_at=NOW.replace(tzinfo=None))
        events = []

        def save(document, **_kwargs):
            events.append(("save", document.doctype))
            return document

        with patch.object(
            self.module,
            "_required_current_claim",
            return_value=(outbox, attempt),
        ), patch.object(
            self.module,
            "tool_asset_claim_write",
            side_effect=lambda _actor: nullcontext(object()),
        ), patch.object(
            self.module,
            "save_tool_asset_support_document",
            side_effect=save,
        ), patch.object(
            self.module,
            "_append_worker_audit",
            side_effect=lambda **_kwargs: events.append(("audit", None)),
        ):
            sealed = self.module.FrappeToolAssetWorkerRepository().mark_adapter_boundary(
                claim,
                profile=exact_profile,
                now=NOW,
            )
        self.assertTrue(sealed)
        self.assertEqual(
            events,
            [
                ("save", "NPI Tool Asset Attempt"),
                ("save", "NPI Outbox Message"),
                ("audit", None),
            ],
        )
        self.assertEqual(attempt.adapter_boundary_crossed, 1)
        self.assertEqual(outbox.adapter_boundary_crossed, 1)
        self.assertIsInstance(attempt.attempt_snapshot["started_at"], str)

    def test_invalid_hydrated_boundary_datetime_fails_before_any_write(self):
        claim, exact_profile = self._boundary_claim()
        outbox = types.SimpleNamespace(
            doctype="NPI Outbox Message",
            adapter_boundary_crossed=0,
        )
        attempt = self._attempt(started_at=object())
        writes = []
        with patch.object(
            self.module,
            "_required_current_claim",
            return_value=(outbox, attempt),
        ), patch.object(
            self.module,
            "tool_asset_claim_write",
            side_effect=lambda _actor: nullcontext(object()),
        ), patch.object(
            self.module,
            "save_tool_asset_support_document",
            side_effect=lambda *_args, **_kwargs: writes.append("save"),
        ), patch.object(
            self.module,
            "_append_worker_audit",
            side_effect=lambda **_kwargs: writes.append("audit"),
        ), self.assertRaises(RuntimeError):
            self.module.FrappeToolAssetWorkerRepository().mark_adapter_boundary(
                claim,
                profile=exact_profile,
                now=NOW,
            )
        self.assertEqual(writes, [])

    def test_recovery_selects_pending_and_only_expired_processing_without_writes(self):
        now = datetime(2026, 8, 24, 10, tzinfo=UTC)
        rows = [
            {"event_id":str(UUID(int=1)), "state":"pending", "lease_expires_at":None},
            {"event_id":str(UUID(int=2)), "state":"processing", "lease_expires_at":now-timedelta(seconds=1)},
            {"event_id":str(UUID(int=3)), "state":"processing", "lease_expires_at":now+timedelta(seconds=1)},
        ]
        previous = sys.modules["frappe"].get_all
        sys.modules["frappe"].get_all = lambda *a, **k: rows
        try:
            self.assertEqual(self.module.FrappeToolAssetWorkerRepository().recoverable_outbox_event_ids(now=now), (UUID(int=1), UUID(int=2)))
        finally:
            sys.modules["frappe"].get_all = previous

    def test_claim_boundary_and_result_each_append_safe_audit(self):
        source = inspect.getsource(self.module)
        self.assertEqual(source.count("_append_worker_audit("), 4)  # one helper plus three contexts
        for marker in ("tool_asset_execution.claim", "tool_asset_execution.adapter_boundary", "tool_asset_execution.result.observe"):
            self.assertEqual(source.count(marker), 1)
        self.assertNotIn("exception_message", source)

    def test_fresh_claim_writes_attempt_outbox_then_live_request_before_audit(self):
        exact_source = source()
        expectation = ToolAssetMappingExpectation(
            ToolAssetExecutionOperation.CREATE,
            exact_source.source_stream_key_hash,
            0,
        )
        request = ToolAssetExecutionRequest(
            uid(20),
            exact_source,
            ToolAssetBusinessApprovalReference(ToolAssetApprovalState.UNAVAILABLE),
            expectation,
            profile(ToolAssetExecutionTargetMode.SYNTHETIC),
            ToolAssetExecutionRequestState.QUEUED,
            "engineer@example.invalid",
            uid(21),
            "trace-p805-worker-repository",
            "a" * 64,
            NOW,
        )
        outbox_id = uid(30)
        outbox = types.SimpleNamespace(
            doctype="NPI Outbox Message",
            event_id=str(outbox_id),
            state="pending",
            tenant_id=exact_source.tenant_id,
            project_global_id=str(exact_source.project_global_id),
            service_actor_user_id="worker@example.invalid",
            trace_id="trace-p805-worker-repository",
            tool_asset_request_global_id=str(request.global_id),
            tooling_set_global_id=str(exact_source.tooling_set_global_id),
            source_stream_key_hash=exact_source.source_stream_key_hash,
            source_hash=exact_source.source_hash,
            tool_asset_mapping_expectation_hash=self.module.canonical_hash(
                expectation.canonical_mapping()
            ),
            profile_snapshot_hash=request.profile.snapshot_hash,
            operation=request.operation.value,
            target_idempotency_key_hash="b" * 64,
            attempt_count=0,
            adapter_boundary_crossed=0,
            tool_asset_last_attempt_global_id=None,
            claim_token=None,
            claimed_at=None,
            lease_expires_at=None,
        )
        request_row = types.SimpleNamespace(
            doctype="NPI Tool Asset Request",
            global_id=str(request.global_id),
            payload_hash=request.payload_hash,
            execution_state=ToolAssetExecutionRequestState.QUEUED.value,
            optimistic_version=1,
            updated_at=NOW,
        )
        events: list[tuple[str, object]] = []

        def get_doc(mapping: dict[str, object]):
            return types.SimpleNamespace(**mapping)

        def insert_document(document: object, **_kwargs: object):
            events.append(("insert", getattr(document, "doctype", None)))
            return document

        def save_document(document: object, **_kwargs: object):
            events.append(
                (
                    "save",
                    (
                        getattr(document, "doctype", None),
                        getattr(document, "execution_state", None),
                        getattr(document, "optimistic_version", None),
                    ),
                )
            )
            return document

        route = self.module.ToolAssetExecutionRoute(
            exact_source.tenant_id,
            exact_source.project_global_id,
            "worker@example.invalid",
            "trace-p805-worker-repository",
        )
        with patch.object(
            self.module,
            "_required_outbox",
            return_value=outbox,
        ), patch.object(
            self.module,
            "_required_doc",
            return_value=request_row,
        ), patch.object(
            self.module,
            "_request_value",
            return_value=request,
        ), patch.object(
            self.module,
            "_require_tool_asset_outbox",
        ), patch.object(
            self.module,
            "_require_bindings",
        ), patch.object(
            self.module,
            "tool_asset_claim_write",
            side_effect=lambda _actor: nullcontext(object()),
        ), patch.object(
            self.module.frappe,
            "get_doc",
            side_effect=get_doc,
            create=True,
        ), patch.object(
            self.module,
            "insert_tool_asset_support_document",
            side_effect=insert_document,
        ), patch.object(
            self.module,
            "save_tool_asset_support_document",
            side_effect=save_document,
        ), patch.object(
            self.module,
            "_append_worker_audit",
            side_effect=lambda **_kwargs: events.append(("audit", "claim")),
        ):
            claim = self.module.FrappeToolAssetWorkerRepository().claim(
                outbox_id,
                now=NOW,
                expected_route=route,
            )

        self.assertIsNotNone(claim)
        self.assertEqual(
            events,
            [
                ("insert", "NPI Tool Asset Attempt"),
                ("save", ("NPI Outbox Message", None, None)),
                (
                    "save",
                    (
                        "NPI Tool Asset Request",
                        ToolAssetExecutionRequestState.PROCESSING.value,
                        2,
                    ),
                ),
                ("audit", "claim"),
            ],
        )
        self.assertEqual(
            request.canonical_mapping()["state"],
            ToolAssetExecutionRequestState.QUEUED.value,
        )
        self.assertEqual(request.canonical_mapping()["optimisticVersion"], 1)

    def test_terminal_replay_requires_result_and_released_guard_truth(self):
        source = inspect.getsource(self.module._require_terminal_truth)
        for marker in ("_require_bindings", "NPI Tool Asset Result", "result_global_id", "active_request_global_id", "last_request_global_id", "last_state"):
            self.assertIn(marker, source)

    def test_process_stage_contexts_preserve_claim_boundary_and_seal_order(self):
        source = inspect.getsource(self.module)
        claim = source[source.index("    def claim(") : source.index("    @staticmethod\n    def require_execution_profile")]
        boundary = source[source.index("    def mark_adapter_boundary(") : source.index("    def seal_result(")]
        seal = source[source.index("    def seal_result(") : source.index("    def recover_or_seal_result(")]

        def ordered(context: str, codes: tuple[str, ...]) -> None:
            positions = [context.index(f'"{code}"') for code in codes]
            self.assertEqual(positions, sorted(positions))

        ordered(
            claim,
            (
                "P805_TOOL_ASSET_PROCESS_CLAIM_OUTBOX",
                "P805_TOOL_ASSET_PROCESS_CLAIM_REQUEST",
                "P805_TOOL_ASSET_PROCESS_CLAIM_REQUEST_REBUILD",
                "P805_TOOL_ASSET_PROCESS_CLAIM_BINDINGS",
                "P805_TOOL_ASSET_PROCESS_CLAIM_COMMAND_BUILD",
                "P805_TOOL_ASSET_PROCESS_CLAIM_TRANSACTION",
                "P805_TOOL_ASSET_PROCESS_CLAIM_ATTEMPT_BUILD",
                "P805_TOOL_ASSET_PROCESS_CLAIM_ATTEMPT_INSERT",
                "P805_TOOL_ASSET_PROCESS_CLAIM_OUTBOX_SAVE",
                "P805_TOOL_ASSET_PROCESS_CLAIM_REQUEST_SAVE",
                "P805_TOOL_ASSET_PROCESS_CLAIM_AUDIT",
                "P805_TOOL_ASSET_PROCESS_CLAIM_RETURN",
            ),
        )
        ordered(
            boundary,
            (
                "P805_TOOL_ASSET_PROCESS_BOUNDARY_PROFILE",
                "P805_TOOL_ASSET_PROCESS_BOUNDARY_CURRENT_CLAIM",
                "P805_TOOL_ASSET_PROCESS_BOUNDARY_TRANSACTION",
                "P805_TOOL_ASSET_PROCESS_BOUNDARY_ATTEMPT_SAVE",
                "P805_TOOL_ASSET_PROCESS_BOUNDARY_OUTBOX_SAVE",
                "P805_TOOL_ASSET_PROCESS_BOUNDARY_AUDIT",
            ),
        )
        ordered(
            seal,
            (
                "P805_TOOL_ASSET_PROCESS_SEAL_PROFILE",
                "P805_TOOL_ASSET_PROCESS_SEAL_CURRENT_CLAIM",
                "P805_TOOL_ASSET_PROCESS_SEAL_REQUEST",
                "P805_TOOL_ASSET_PROCESS_SEAL_BINDINGS",
                "P805_TOOL_ASSET_PROCESS_SEAL_RESULT_LOOKUP",
                "P805_TOOL_ASSET_PROCESS_SEAL_PREPARE",
                "P805_TOOL_ASSET_PROCESS_SEAL_TRANSACTION",
                "P805_TOOL_ASSET_PROCESS_SEAL_RESULT_BUILD",
                "P805_TOOL_ASSET_PROCESS_SEAL_RESULT_INSERT",
                "P805_TOOL_ASSET_PROCESS_SEAL_FIELD_INSERT",
                "P805_TOOL_ASSET_PROCESS_SEAL_MAPPING",
                "P805_TOOL_ASSET_PROCESS_SEAL_ATTEMPT_SAVE",
                "P805_TOOL_ASSET_PROCESS_SEAL_REQUEST_SAVE",
                "P805_TOOL_ASSET_PROCESS_SEAL_OUTBOX_SAVE",
                "P805_TOOL_ASSET_PROCESS_SEAL_GUARD",
                "P805_TOOL_ASSET_PROCESS_SEAL_AUDIT",
                "P805_TOOL_ASSET_PROCESS_SEAL_OUTCOME",
            ),
        )


if __name__ == "__main__":
    unittest.main()
