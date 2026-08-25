from __future__ import annotations

import importlib
import inspect
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


if __name__ == "__main__":
    unittest.main()
