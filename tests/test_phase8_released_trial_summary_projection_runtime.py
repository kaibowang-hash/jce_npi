from __future__ import annotations

import inspect
import unittest
from uuid import UUID

from tests.test_phase7_released_trial_summary_runtime_verifier import (
    RUNTIME_SHELL,
    load_verifier,
)


class Phase8ReleasedTrialSummaryProjectionRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.projection = inspect.getsource(
            cls.module.released_summary_projection_truth
        )
        cls.retained = inspect.getsource(cls.module.retained_truth)
        cls.fresh = inspect.getsource(cls.module.run_fresh)
        cls.replay = inspect.getsource(cls.module.run_replay_only)
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")

    def test_projection_uses_project_round_current_source_in_exact_order(self) -> None:
        projection = self.projection
        for fragment in (
            "FrappeReleasedTrialSummaryRepository",
            "ProjectFirstReleasedSummarySourceReader",
            "project_global_id=UUID(project_id)",
            'trial_round_global_id=UUID(str(current_summary.get("trialRoundGlobalId")))',
            'summary_revision_global_id=UUID(str(current_summary.get("globalId")))',
            'roles=frozenset({"System Manager"})',
            "tenant_id=trial_runtime.TENANT_ID",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, projection)
        self.assertLess(
            projection.index("FrappeReleasedTrialSummaryRepository("),
            projection.index("ProjectFirstReleasedSummarySourceReader("),
        )
        self.assertLess(
            projection.index("ProjectFirstReleasedSummarySourceReader("),
            projection.index("ContractHeldReleasedSummaryProjectionAdapter()"),
        )

    def test_projection_revalidates_all_immutable_identity_and_hash_fields(self) -> None:
        for field in (
            "projectGlobalId",
            "trialRoundGlobalId",
            "summaryRevisionGlobalId",
            "summaryGlobalId",
            "summaryVersion",
            "snapshotHash",
            "sourceManifestHash",
            "presentationProjectionHash",
            "redactionManifestHash",
        ):
            with self.subTest(field=field):
                self.assertGreaterEqual(self.projection.count(f'"{field}"'), 2)

    def test_projection_is_explicitly_unavailable_deterministic_and_safe(self) -> None:
        module = self.module
        self.assertEqual(UUID(module.P8_08_REQUEST_ID).version, 4)
        self.assertEqual(
            module.P8_08_TRACE_ID,
            f"p8-08-runtime-{module.FIXTURE_RUN_ID}",
        )
        for fragment in (
            '"sourceState": "current"',
            '"sourceFingerprint": descriptor.fingerprint',
            '"externalProjection": "unavailable"',
            '"unavailableReasonCode": "external_contract_held"',
            '"traceId": P8_08_TRACE_ID',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.projection)
        for forbidden in (
            ".insert(",
            ".save(",
            ".submit(",
            ".commit(",
            "enqueue(",
            "requests.",
            "urllib.",
            "socket.",
            "http://",
            "https://",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.projection)

    def test_projection_wraps_exact_source_read_with_zero_persistence_delta(self) -> None:
        projection = self.projection
        before = projection.index("before = target_persistence_context")
        repository = projection.index("repository = FrappeReleasedTrialSummaryRepository")
        adapter = projection.index("ContractHeldReleasedSummaryProjectionAdapter()")
        after = projection.index("after = target_persistence_context")
        equality = projection.index("require(after == before")
        self.assertLess(before, repository)
        self.assertLess(repository, adapter)
        self.assertLess(adapter, after)
        self.assertLess(after, equality)

    def test_retained_fresh_and_replay_processes_expose_the_same_safe_truth(self) -> None:
        self.assertIn("released_summary_projection_truth(", self.retained)
        self.assertIn('"projectionSource": projection_source', self.retained)
        for flow in (self.fresh, self.replay):
            with self.subTest(flow=flow.splitlines()[0]):
                self.assertIn(
                    'run_bench_fixture("retained_truth", {"project_id": project_id})',
                    flow,
                )
                self.assertIn('"projectionSource": retained["projectionSource"]', flow)

    def test_existing_disposable_runtime_lane_remains_fresh_then_replay_only(self) -> None:
        shell = self.shell
        fresh = shell.index("run_released_summary_runtime_verifier fresh")
        disabled = shell.index("run_released_summary_route_probe disabled", fresh)
        recovered = shell.index("run_released_summary_route_probe recovered", disabled)
        replay = shell.index("run_released_summary_runtime_verifier replay-only", recovered)
        self.assertLess(fresh, disabled)
        self.assertLess(disabled, recovered)
        self.assertLess(recovered, replay)
        self.assertNotIn("p8-08-runtime", shell)


if __name__ == "__main__":
    unittest.main()
