from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.item_publish.adapters import (
    ItemAdapterRegistry,
    ItemAdapterRegistration,
    ItemAdapterResponse,
)
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_OPERATION,
    ItemTargetMode,
)
from tests.test_phase8_item_publish_adapters import command, profile, response


NOW = datetime(2026, 8, 16, 15, 45, tzinfo=UTC)
OUTBOX_ID = UUID("00000000-0000-4000-8000-000000008361")


class StubFinalFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class StubOutcome:
    def __init__(self, state: str = "synthetic_verified") -> None:
        self.outbox_event_id = OUTBOX_ID
        self.request_global_id = command().request_global_id
        self.state = state
        self.disposition = state
        self.result_global_id = UUID(int=8362)
        self.mapping_advanced = False


class StubDatabase:
    def __init__(self, owner: "Phase8ItemPublishWorkerTest") -> None:
        self.owner = owner
        self.fail_commit_number: int | None = None

    def commit(self) -> None:
        self.owner.events.append("commit")
        if self.fail_commit_number == self.owner.events.count("commit"):
            raise RuntimeError("injected private commit failure")

    def rollback(self) -> None:
        self.owner.events.append("rollback")


class StubRepository:
    def __init__(self, owner: "Phase8ItemPublishWorkerTest") -> None:
        self.owner = owner
        synthetic = profile(ItemTargetMode.SYNTHETIC)
        self.claim_value = types.SimpleNamespace(
            outbox_event_id=OUTBOX_ID,
            request_global_id=command().request_global_id,
            tenant_id=synthetic.tenant_id,
            project_global_id=UUID(synthetic.project_global_id),
            trace_id="trace-p803-item-worker",
            claim_token=UUID(int=8363),
            lease_expires_at=NOW + timedelta(minutes=5),
            command=command(),
            profile_reference=synthetic.reference,
            expired_recovery=False,
            recovered_after_adapter_boundary=False,
        )
        self.profile_failure: Exception | None = None
        self.boundary_value = True
        self.recoverable: tuple[UUID, ...] = ()
        self.results: list[object] = []

    def claim(self, event_id: UUID, *, now: datetime):
        self.owner.events.append("claim")
        return self.claim_value

    def require_execution_profile(self, claim, value):
        self.owner.events.append("profile")
        if self.profile_failure is not None:
            raise self.profile_failure
        return value

    def mark_adapter_boundary(self, claim, *, profile, now: datetime) -> bool:
        self.owner.events.append("boundary")
        return self.boundary_value

    def seal_result(self, claim, *, profile, result, now: datetime):
        self.owner.events.append("seal")
        self.results.append(result)
        return StubOutcome(result.observation.state.value)

    def recoverable_outbox_event_ids(self, *, now: datetime):
        self.owner.events.append("recoverable")
        return self.recoverable


class RecoveryRepository(StubRepository):
    def recover_or_seal_result(self, claim, *, profile, result, now):
        self.owner.events.append("recover")
        self.results.append(result)
        return StubOutcome(result.observation.state.value)


class SealFailureRecoveryRepository(RecoveryRepository):
    def seal_result(self, claim, *, profile, result, now):
        self.owner.events.append("seal")
        self.results.append(result)
        raise RuntimeError("injected local seal failure")


class Phase8ItemPublishWorkerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_integration.item_publish.worker_repository",
        "npi_integration.item_publish.worker",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        self.enqueued: list[dict[str, object]] = []
        self.diagnostics: list[dict[str, object]] = []
        frappe = types.ModuleType("frappe")
        frappe.db = StubDatabase(self)
        frappe.enqueue = lambda path, **kwargs: self.enqueued.append(
            {"path": path, **kwargs}
        )
        frappe.get_hooks = lambda _name: []
        frappe.get_attr = lambda _path: None
        sys.modules["frappe"] = frappe
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: self.diagnostics.append(values)
        sys.modules["npi_core.api"] = api
        repository_module = types.ModuleType(
            "npi_integration.item_publish.worker_repository"
        )
        repository_module.FrappeItemPublishWorkerRepository = StubRepository
        repository_module.ItemPublishWorkerFinalFailure = StubFinalFailure
        repository_module.ItemPublishWorkerOutcome = StubOutcome
        sys.modules[repository_module.__name__] = repository_module
        self.module = importlib.import_module("npi_integration.item_publish.worker")
        self.repository = StubRepository(self)
        self.synthetic = profile(ItemTargetMode.SYNTHETIC)
        self.adapter_calls = 0

        def adapter(value) -> ItemAdapterResponse:
            self.events.append("adapter")
            self.adapter_calls += 1
            return response()

        self.registry = ItemAdapterRegistry(
            (
                ItemAdapterRegistration(
                    str(self.synthetic.adapter_resolver),
                    ItemTargetMode.SYNTHETIC,
                    ITEM_PUBLISH_OPERATION,
                    adapter,
                ),
            )
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def execute(self):
        return self.module._execute_worker(
            outbox_event_id=OUTBOX_ID,
            repository=self.repository,
            profile_resolver=lambda _tenant, _project: self.synthetic,
            registry_resolver=lambda: self.registry,
            clock=lambda: NOW,
        )

    def test_claim_and_boundary_commit_before_single_adapter_call_and_result_commit(self) -> None:
        outcome = self.execute()
        self.assertEqual(outcome.state, "synthetic_verified")
        self.assertEqual(
            self.events,
            [
                "claim",
                "commit",
                "profile",
                "boundary",
                "commit",
                "adapter",
                "seal",
                "commit",
            ],
        )
        self.assertEqual(self.adapter_calls, 1)

    def test_missing_profile_or_registry_fails_before_boundary_without_adapter(self) -> None:
        self.repository.profile_failure = StubFinalFailure(
            "ITEM_PUBLISH_EXECUTION_PROFILE_UNAVAILABLE"
        )
        outcome = self.execute()
        self.assertEqual(outcome.state, "failed_final")
        self.assertEqual(
            self.events,
            ["claim", "commit", "profile", "rollback", "seal", "commit"],
        )
        self.assertEqual(self.adapter_calls, 0)

    def test_exception_after_boundary_is_uncertain_and_not_retried(self) -> None:
        def failing_adapter(_value):
            self.events.append("adapter")
            self.adapter_calls += 1
            raise TimeoutError("private synthetic response body")

        self.registry = ItemAdapterRegistry(
            (
                ItemAdapterRegistration(
                    str(self.synthetic.adapter_resolver),
                    ItemTargetMode.SYNTHETIC,
                    ITEM_PUBLISH_OPERATION,
                    failing_adapter,
                ),
            )
        )
        outcome = self.execute()
        self.assertEqual(outcome.state, "uncertain_after_timeout")
        self.assertEqual(self.adapter_calls, 1)
        self.assertTrue(self.repository.results[-1].reconciliation_required)
        self.assertNotIn("private synthetic", repr(self.diagnostics))

    def test_expired_crossed_boundary_seals_uncertain_without_second_call(self) -> None:
        self.repository.claim_value.recovered_after_adapter_boundary = True
        outcome = self.execute()
        self.assertEqual(outcome.state, "uncertain_after_timeout")
        self.assertEqual(
            self.events,
            ["claim", "commit", "seal", "commit"],
        )
        self.assertEqual(self.adapter_calls, 0)

    def test_boundary_commit_failure_never_calls_adapter(self) -> None:
        sys.modules["frappe"].db.fail_commit_number = 2
        with self.assertRaisesRegex(RuntimeError, "commit failure"):
            self.execute()
        self.assertEqual(self.adapter_calls, 0)
        self.assertEqual(
            self.events,
            ["claim", "commit", "profile", "boundary", "commit", "rollback"],
        )

    def test_result_commit_failure_remains_ambiguous_after_durable_boundary(self) -> None:
        sys.modules["frappe"].db.fail_commit_number = 3
        with self.assertRaisesRegex(RuntimeError, "commit failure"):
            self.execute()
        self.assertEqual(self.adapter_calls, 1)
        self.assertEqual(
            self.events,
            [
                "claim",
                "commit",
                "profile",
                "boundary",
                "commit",
                "adapter",
                "seal",
                "commit",
                "rollback",
            ],
        )

    def test_result_commit_failure_recovers_once_without_redispatch(self) -> None:
        self.repository = RecoveryRepository(self)
        sys.modules["frappe"].db.fail_commit_number = 3
        outcome = self.execute()
        self.assertEqual(outcome.state, "synthetic_verified")
        self.assertEqual(self.adapter_calls, 1)
        self.assertEqual(
            self.events,
            [
                "claim",
                "commit",
                "profile",
                "boundary",
                "commit",
                "adapter",
                "seal",
                "commit",
                "rollback",
                "recover",
                "commit",
            ],
        )

    def test_seal_failure_rolls_back_then_recovers_without_redispatch(self) -> None:
        self.repository = SealFailureRecoveryRepository(self)
        outcome = self.execute()
        self.assertEqual(outcome.state, "synthetic_verified")
        self.assertEqual(self.adapter_calls, 1)
        self.assertEqual(
            self.events,
            [
                "claim",
                "commit",
                "profile",
                "boundary",
                "commit",
                "adapter",
                "seal",
                "rollback",
                "recover",
                "commit",
            ],
        )

    def test_recovery_enqueues_only_bounded_repository_candidates(self) -> None:
        self.repository.recoverable = (UUID(int=8371), UUID(int=8372))
        self.module.FrappeItemPublishWorkerRepository = lambda: self.repository
        self.assertEqual(self.module.recover_item_publish_outbox_messages(), 2)
        self.assertEqual(len(self.enqueued), 2)
        self.assertTrue(all(item["queue"] == "short" for item in self.enqueued))
        self.assertTrue(all(item["deduplicate"] is True for item in self.enqueued))
        self.assertTrue(
            all(item["enqueue_after_commit"] is False for item in self.enqueued)
        )


if __name__ == "__main__":
    unittest.main()
