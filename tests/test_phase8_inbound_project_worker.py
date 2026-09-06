from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.inbound_project.domain import ClaimLease


NOW = datetime(2026, 8, 16, 8, 0, tzinfo=UTC)
RECEIPT_ID = UUID(int=801)
EVENT_ID = UUID(int=802)
PROJECT_ID = UUID(int=803)


class StubFinalFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class StubOutcome:
    def __init__(
        self,
        *,
        receipt_id: UUID = RECEIPT_ID,
        state: str = "succeeded",
        disposition: str = "project_created",
        project_global_id: UUID | None = PROJECT_ID,
        replayed: bool = False,
    ) -> None:
        self.receipt_id = receipt_id
        self.state = state
        self.disposition = disposition
        self.project_global_id = project_global_id
        self.replayed = replayed


class StubDatabase:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.fail_commit_number: int | None = None

    def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit_number == self.events.count("commit"):
            raise RuntimeError("Injected commit failure")

    def rollback(self) -> None:
        self.events.append("rollback")


class StubRepository:
    def __init__(self) -> None:
        self.claim_value = types.SimpleNamespace(
            receipt_id=RECEIPT_ID,
            event_id=EVENT_ID,
            source_key_hash="a" * 64,
            trace_id="trace-worker-801",
            lease=ClaimLease(
                token=UUID(int=804),
                claimed_at=NOW,
                expires_at=NOW + timedelta(minutes=5),
                attempt_count=1,
            ),
        )
        self.process_value: object = StubOutcome()
        self.calls: list[tuple[str, object]] = []
        self.recoverable: tuple[UUID, ...] = ()

    def claim(self, receipt_id: UUID, *, now: datetime):
        self.calls.append(("claim", receipt_id))
        return self.claim_value

    def process_claim(self, claim, *, profile, now: datetime):
        self.calls.append(("process", profile))
        if isinstance(self.process_value, Exception):
            raise self.process_value
        return self.process_value

    def mark_failure(
        self,
        claim,
        *,
        code: str,
        retryable: bool,
        now: datetime,
    ) -> bool:
        self.calls.append(("failure", (code, retryable)))
        return True

    def recoverable_receipt_ids(self, *, now: datetime):
        self.calls.append(("recoverable", now))
        return self.recoverable


class Phase8InboundProjectWorkerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.inbound_project.worker_repository",
        "npi_integration.inbound_project.worker",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.database = StubDatabase()
        self.enqueued: list[dict[str, object]] = []
        self.logged: list[dict[str, object]] = []
        frappe = types.ModuleType("frappe")
        frappe.db = self.database
        frappe.enqueue = lambda path, **kwargs: self.enqueued.append(
            {"path": path, **kwargs}
        )
        frappe.get_hooks = lambda _name: []
        frappe.get_attr = lambda _path: None
        frappe.logger = lambda _name: types.SimpleNamespace(error=lambda _value: None)
        frappe.log_error = lambda **values: self.logged.append(values)
        sys.modules["frappe"] = frappe

        repository_module = types.ModuleType(
            "npi_integration.inbound_project.worker_repository"
        )
        repository_module.FrappeInboundProjectWorkerRepository = StubRepository
        repository_module.InboundProjectFinalFailure = StubFinalFailure
        repository_module.InboundProjectWorkerOutcome = StubOutcome
        sys.modules[repository_module.__name__] = repository_module
        self.module = importlib.import_module("npi_integration.inbound_project.worker")
        self.repository = StubRepository()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def execute(self):
        return self.module._execute_worker(
            receipt_id=RECEIPT_ID,
            repository=self.repository,
            profile_resolver=lambda: "synthetic-profile",
            clock=lambda: NOW,
        )

    def test_claim_commits_before_project_transaction_and_success_commits_once(self) -> None:
        outcome = self.execute()
        self.assertEqual(outcome.project_global_id, PROJECT_ID)
        self.assertEqual(self.database.events, ["commit", "commit"])
        self.assertEqual(
            [name for name, _value in self.repository.calls],
            ["claim", "process"],
        )

    def test_live_or_terminal_receipt_is_not_claimed(self) -> None:
        self.repository.claim_value = None
        self.assertIsNone(self.execute())
        self.assertEqual(self.database.events, ["rollback"])
        self.assertEqual(len(self.repository.calls), 1)

    def test_final_and_unexpected_failures_are_sealed_after_project_rollback(self) -> None:
        for error, expected in (
            (StubFinalFailure("INBOUND_PROJECT_OWNER_UNAVAILABLE"), (False, "failed_final")),
            (RuntimeError("synthetic local fault"), (True, "failed_retryable")),
        ):
            with self.subTest(error=type(error).__name__):
                self.database.events.clear()
                self.repository.calls.clear()
                self.repository.process_value = error
                outcome = self.execute()
                retryable, state = expected
                self.assertEqual(outcome.state, state)
                self.assertEqual(
                    self.database.events,
                    ["commit", "rollback", "commit"],
                )
                failure = next(
                    value for name, value in self.repository.calls if name == "failure"
                )
                self.assertEqual(failure[1], retryable)

    def test_ambiguous_result_commit_never_overwrites_with_failure(self) -> None:
        self.database.fail_commit_number = 2
        with self.assertRaises(RuntimeError):
            self.execute()
        self.assertEqual(self.database.events, ["commit", "commit", "rollback"])
        self.assertNotIn("failure", [name for name, _value in self.repository.calls])

    def test_recovery_enqueues_only_repository_bounded_candidates(self) -> None:
        self.repository.recoverable = (UUID(int=901), UUID(int=902))
        self.module.FrappeInboundProjectWorkerRepository = lambda: self.repository
        self.assertEqual(self.module.recover_inbound_project_receipts(), 2)
        self.assertEqual(len(self.enqueued), 2)
        self.assertEqual(
            {item["receipt_id"] for item in self.enqueued},
            {str(UUID(int=901)), str(UUID(int=902))},
        )
        self.assertTrue(all(item["queue"] == "short" for item in self.enqueued))
        self.assertTrue(
            all(item["enqueue_after_commit"] is False for item in self.enqueued)
        )
        self.assertTrue(all(item["deduplicate"] is True for item in self.enqueued))


if __name__ == "__main__":
    unittest.main()
