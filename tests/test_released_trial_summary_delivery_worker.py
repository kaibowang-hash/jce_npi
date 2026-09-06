from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for app in (ROOT / "apps/npi_core", ROOT / "apps/npi_integration"):
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))

from npi_integration.trial_summary_publish.domain import TargetObservation


class ReleasedTrialSummaryDeliveryWorkerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.trial_summary_publish.frappe_validation",
        "npi_integration.trial_summary_publish.service",
        "npi_integration.trial_summary_publish.worker",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.enqueued: list[dict[str, object]] = []
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.enqueue = lambda path, **values: self.enqueued.append(
            {"path": path, **values}
        )
        sys.modules["frappe"] = frappe
        self.worker = importlib.import_module(
            "npi_integration.trial_summary_publish.worker"
        )
        self.claim = self.worker.Claim(
            "00000000-0000-4000-8000-000000000101",
            "00000000-0000-4000-8000-000000000102",
            1,
            "00000000-0000-4000-8000-000000000103",
            "publish",
            "TENANT-TEST",
            "00000000-0000-4000-8000-000000000104",
            "engineer@example.invalid",
            "1" * 64,
            "2" * 64,
            {},
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def observation(
        status: int,
        *,
        authenticated: bool = True,
        valid: bool = True,
        found: bool | None = None,
    ) -> TargetObservation:
        return TargetObservation(
            status,
            "3" * 64,
            authenticated,
            valid,
            (
                "00000000-0000-4000-8000-000000000105"
                if status < 300 and found is not False
                else None
            ),
            7 if status < 300 and found is not False else None,
            False,
            None if status < 300 else "TRIAL_SUMMARY_TARGET_ERROR",
            found,
        )

    def capture_publish(
        self,
        observation: TargetObservation,
        *,
        attempt_number: int = 1,
    ) -> dict[str, object]:
        captured: dict[str, object] = {}
        claim = self.worker.Claim(
            *(
                self.claim.delivery_global_id,
                self.claim.attempt_global_id,
                attempt_number,
                self.claim.claim_token,
                self.claim.kind,
                self.claim.tenant_id,
                self.claim.project_global_id,
                self.claim.actor_user_id,
                self.claim.source_hash,
                self.claim.target_idempotency_key_hash,
                self.claim.source,
            )
        )
        with patch.object(
            self.worker,
            "_complete",
            side_effect=lambda _claim, **values: captured.update(values),
        ):
            self.worker._complete_publish_observation(claim, observation)
        return captured

    def test_publish_fault_matrix_preserves_safe_retry_boundary(self) -> None:
        self.assertEqual(
            self.capture_publish(self.observation(200))["delivery_state"],
            "succeeded",
        )
        self.assertEqual(
            self.capture_publish(self.observation(429))["delivery_state"],
            "failed_retryable",
        )
        self.assertEqual(
            self.capture_publish(
                self.observation(503),
                attempt_number=self.worker.MAX_AUTOMATIC_ATTEMPTS,
            )["delivery_state"],
            "failed_final",
        )
        self.assertEqual(
            self.capture_publish(self.observation(422))["delivery_state"],
            "failed_final",
        )
        self.assertEqual(
            self.capture_publish(
                self.observation(200, authenticated=False, valid=False)
            )["delivery_state"],
            "uncertain",
        )

    def test_reconciliation_present_absent_conflict_and_unverified_are_closed(self) -> None:
        for observation, expected_attempt, expected_delivery in (
            (self.observation(200, found=True), "reconciled_present", "succeeded"),
            (self.observation(200, found=False), "reconciled_absent", "pending"),
            (self.observation(409), "failed_final", "failed_final"),
            (
                self.observation(200, authenticated=False, valid=False),
                "uncertain",
                "uncertain",
            ),
        ):
            with self.subTest(delivery_state=expected_delivery):
                captured: dict[str, object] = {}
                with patch.object(
                    self.worker,
                    "_complete",
                    side_effect=lambda _claim, **values: captured.update(values),
                ):
                    self.worker._complete_reconcile_observation(
                        self.claim,
                        observation,
                    )
                self.assertEqual(captured["attempt_state"], expected_attempt)
                self.assertEqual(captured["delivery_state"], expected_delivery)
        self.assertEqual(len(self.enqueued), 1)
        self.assertEqual(
            self.enqueued[0]["delivery_global_id"],
            self.claim.delivery_global_id,
        )

    def test_exception_after_boundary_is_always_uncertain(self) -> None:
        captured: dict[str, object] = {}
        with patch.object(
            self.worker,
            "_complete",
            side_effect=lambda _claim, **values: captured.update(values),
        ):
            self.worker._complete_uncertain(self.claim, TimeoutError("private target"))
        self.assertEqual(captured["attempt_state"], "uncertain")
        self.assertEqual(captured["delivery_state"], "uncertain")
        self.assertEqual(
            captured["error_code"],
            "TRIAL_SUMMARY_ADAPTER_OUTCOME_UNCERTAIN",
        )
        self.assertNotIn("private target", str(captured))


if __name__ == "__main__":
    unittest.main()
