from __future__ import annotations

import importlib
import inspect
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]


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

    def test_terminal_replay_requires_result_and_released_guard_truth(self):
        source = inspect.getsource(self.module._require_terminal_truth)
        for marker in ("_require_bindings", "NPI Tool Asset Result", "result_global_id", "active_request_global_id", "last_request_global_id", "last_state"):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
