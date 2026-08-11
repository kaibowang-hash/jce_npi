from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = (
    ROOT / "apps/npi_core/npi_core/trial/review_repository.py"
).read_text(encoding="utf-8")
API = (ROOT / "apps/npi_core/npi_core/trial_api.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")


class Phase7TrialReviewRepositorySeamsTest(unittest.TestCase):
    def test_review_repository_reuses_project_first_quality_boundary(self) -> None:
        self.assertIn(
            "class FrappeTrialReviewRepository(FrappeTrialQualityRepository):",
            REPOSITORY,
        )
        for marker in (
            "self._locked_authorized_project(project_id)",
            "self._execution_round(project, round_id, for_update=True)",
            "self._exact_member(",
            "self._is_internal_system_manager()",
            "policy.snapshot_hash != snapshot_hash",
            "trial_round.snapshot_hash != round_hash",
        ):
            self.assertIn(marker, REPOSITORY)

    def test_every_review_command_uses_atomic_receipt_target_audit_boundary(self) -> None:
        for operation in (
            "trial_round.begin_analysis",
            "trial_comparison.create",
            "trial_review_reference.create",
            "trial_review_reference.revise",
            "trial_conclusion.submit",
            "trial_conclusion.decide",
            "trial_conclusion.reopen",
        ):
            self.assertIn(operation, REPOSITORY)
        for marker in (
            "with trial_command_write():",
            "self._insert_receipt(",
            "insert(target)",
            "self._insert_round_event(lifecycle_event)",
            "self._save_round(round_document, trial_round)",
            "self._append_audit(",
            "self._seal_receipt(",
        ):
            self.assertIn(marker, REPOSITORY)
        for forbidden in (
            "frappe.db.set_value",
            "frappe.db." + "sql",
            ".delete()",
            "enqueue(",
            "outbox",
            "erpnext",
        ):
            self.assertNotIn(forbidden, REPOSITORY.casefold())

    def test_routes_are_independently_default_closed(self) -> None:
        for source in (API, ROUTER):
            self.assertIn("npi_p7_04_routes_disabled", source)
            self.assertIn("return value is not False", source)
        self.assertIn("trial_review_routes_disabled", ROUTER)
        self.assertNotIn(
            'configuration.get("npi_p7_03_routes_disabled")\n        if hasattr(configuration, "get")\n        else None\n    )\n    return value is not False and command in {\n        "npi_core.trial_api.get_trial_review_workspace"',
            ROUTER,
        )


if __name__ == "__main__":
    unittest.main()
