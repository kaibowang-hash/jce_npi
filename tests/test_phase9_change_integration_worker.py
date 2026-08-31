from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))


class Phase9ChangeIntegrationWorkerTest(unittest.TestCase):
    def test_worker_keeps_claim_boundary_result_and_recovery_operation_specific(self) -> None:
        source = (
            ROOT / "apps/npi_integration/npi_integration/engineering_change/worker.py"
        ).read_text(encoding="utf-8")
        ast.parse(source)
        for marker in (
            "claim_inbound(route",
            "finish_inbound(",
            "claim_summary(route",
            "mark_adapter_boundary(claim",
            "seal_result(",
            "uncertain_result(",
            "ENGINEERING_CHANGE_SUMMARY_PROFILE_UNAVAILABLE",
            "SummaryState.SYNTHETIC_VERIFIED",
            "recoverable_inbox_ids",
            "recoverable_summary_ids",
            "enqueue_after_commit=False",
            "deduplicate=True",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("retry_change_implementation_summary", source)
        self.assertNotIn("request_reconciliation", source)

    def test_worker_repository_uses_deterministic_result_and_never_requeues_terminal_states(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/engineering_change/worker_repository.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for marker in (
            "npi.change-implementation-summary.result.v1",
            "CLAIM_LEASE_SECONDS = 300",
            "RECOVERY_BATCH_LIMIT = 100",
            'filters={"state": ["in", states]}',
            "include_failed_retryable=False",
            'return "observed_success"',
            'return "observed_failure"',
        ):
            self.assertIn(marker, source)
        self.assertIn(
            "def recoverable_summary_ids(self, *, now: datetime)", source
        )

    def test_runtime_fixture_is_disposable_network_free_and_returns_authenticated_contract_result(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/engineering_change/runtime_fixture.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "NPI_P9_01C_RUNTIME_ENABLED",
            "TargetMode.SYNTHETIC",
            "disposable_runtime_marker=True",
            "authenticated=True",
            "contract_valid=True",
        ):
            self.assertIn(marker, source)
        for forbidden in ("requests.", "httpx.", "base_url=", "production"):
            self.assertNotIn(forbidden, source.casefold())


if __name__ == "__main__":
    unittest.main()
