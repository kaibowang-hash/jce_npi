from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_released_trial_summary_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    module_name = "verify_released_trial_summary_runtime_contract"
    saved = sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, VERIFIER)
    if spec is None or spec.loader is None:
        raise AssertionError("Released-summary runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": FIXTURE_RUN_ID},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
        if saved is not None:
            sys.modules[module_name] = saved
    return module


class Phase7ReleasedTrialSummaryRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_is_disposable_and_has_no_production_host(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.SOURCE_KIND, "released_trial_summary")
        self.assertEqual(module.RUNTIME_MARKER, "npi-one-local-runtime-disposable-v1")
        self.assertEqual(UUID(module.REGISTRY_ID).version, 4)
        self.assertEqual(UUID(module.MAPPING_ID).version, 4)
        self.assertNotEqual(module.REGISTRY_ID, module.MAPPING_ID)
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("ignore_mandatory", self.source)
        self.assertNotIn("ignore_validate", self.source)

    def test_summary_and_controlled_print_payloads_are_closed(self) -> None:
        module = self.module
        summary = {
            "globalId": "10000000-0000-4000-8000-000000000001",
            "summaryVersion": 3,
        }
        self.assertEqual(
            module.controlled_print_payload(summary),
            {
                "sourceKind": "released_trial_summary",
                "sourceGlobalId": summary["globalId"],
                "sourceVersion": 3,
                "language": "en",
            },
        )
        retained = module.retain_payload(
            {"optimisticVersion": 12, "snapshotHash": "a" * 64},
            {
                "globalId": "20000000-0000-4000-8000-000000000002",
                "conclusionVersion": 8,
                "snapshotHash": "b" * 64,
            },
            reason="exact reason",
        )
        self.assertEqual(
            set(retained),
            {
                "expectedRoundOptimisticVersion",
                "expectedRoundSnapshotHash",
                "conclusionRevisionGlobalId",
                "expectedConclusionVersion",
                "expectedConclusionSnapshotHash",
                "reason",
            },
        )
        serialized = str(retained | module.controlled_print_payload(summary)).casefold()
        for forbidden in ("template", "watermark", "copystate", "actor", "tenant"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_recursive_redaction_rejects_sensitive_keys_paths_and_production_values(self) -> None:
        module = self.module
        module.require_safe_payload(
            {"facts": [{"value": "safe business value"}]},
            "safe",
        )
        for value in (
            {"password": "value"},
            {"facts": [{"fileUrl": "value"}]},
            {"facts": [{"value": "/private/files/secret.pdf"}]},
            {"facts": [{"value": module.production_transition_runtime.POLICY_SENTINEL}]},
        ):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    module.require_safe_payload(value, "unsafe")

    def test_protected_source_context_excludes_only_trial_receipts(self) -> None:
        module = self.module
        context = {
            "downstreamCounts": {
                "project:NPI Engineering Project": 1,
                "trial:NPI Trial Round": 1,
                "trial:NPI Trial Command Idempotency": 46,
            },
            "downstreamDigests": {
                "project:NPI Engineering Project": "a" * 64,
                "trial:NPI Trial Round": "b" * 64,
                "trial:NPI Trial Command Idempotency": "c" * 64,
            },
            "projectOptimisticVersion": 2,
            "sourcePreparationAuditCounts": {"trialReopen": 3},
            "sourcePreparationAuditDigests": {"trialReopen": "d" * 64},
        }
        with patch.object(module, "_require_disposable_site"), patch.object(
            module.readiness_runtime,
            "readiness_persistence_context",
            return_value=context,
        ):
            result = module.protected_source_context(
                fixture_run_id=FIXTURE_RUN_ID,
                project_id="project",
            )
        self.assertIn("trial:NPI Trial Round", result["counts"])
        self.assertNotIn("trial:NPI Trial Command Idempotency", result["counts"])
        self.assertEqual(result["sourcePreparationAuditCounts"], {"trialReopen": 3})

    def test_cumulative_context_keeps_all_non_intentional_domains(self) -> None:
        module = self.module
        downstream = {
            "project:NPI Engineering Project": {"count": 1, "digest": "a"},
            "work:NPI Domain Work Item": {"count": 1, "digest": "b"},
            "tooling:NPI Tooling Master": {"count": 1, "digest": "c"},
            "trial:NPI Trial Round": {"count": 1, "digest": "d"},
            "trial:NPI Trial Conclusion Revision": {"count": 5, "digest": "e"},
            "trial:NPI Trial Actual Revision": {"count": 2, "digest": "f"},
            "audit:non-p706": {"count": 10, "digest": "g"},
            "NPI Outbox Message": {"count": 0, "digest": "h"},
        }
        with patch.object(module, "_require_disposable_site"), patch.object(
            module.production_transition_runtime,
            "production_transition_persistence_context",
            return_value={
                "downstreamSnapshot": downstream,
                "transitionGlobalSnapshot": {"global": True},
                "transitionSnapshot": {"scoped": True},
            },
        ):
            result = module.cumulative_protected_context(
                fixture_run_id=FIXTURE_RUN_ID,
                project_id="project",
            )
        kept = result["downstreamSnapshot"]
        self.assertIn("project:NPI Engineering Project", kept)
        self.assertIn("work:NPI Domain Work Item", kept)
        self.assertIn("tooling:NPI Tooling Master", kept)
        self.assertIn("trial:NPI Trial Actual Revision", kept)
        self.assertIn("NPI Outbox Message", kept)
        self.assertNotIn("trial:NPI Trial Round", kept)
        self.assertNotIn("trial:NPI Trial Conclusion Revision", kept)
        self.assertNotIn("audit:non-p706", kept)

    def test_summary_command_requires_exact_replay_header(self) -> None:
        module = self.module
        response = module.HttpResult(
            201,
            {
                "X-Request-ID": "request",
                "Cache-Control": "private, no-store",
                "Idempotency-Replayed": "true",
            },
            {"safe": True},
        )
        with patch.object(
            module,
            "summary_request",
            return_value=response,
        ):
            result = module.summary_command(
                object(),
                "http://127.0.0.1:8003",
                "csrf",
                "/summary",
                {"safe": True},
                "key",
                replayed=True,
            )
        self.assertIs(result, response)

    def test_submission_sources_continue_current_then_frozen_p705_scope(self) -> None:
        module = self.module
        old_comparison = {
            "globalId": "10000000-0000-4000-8000-000000000001",
            "snapshotHash": "a" * 64,
        }
        current_comparison = {
            "globalId": "10000000-0000-4000-8000-000000000002",
            "snapshotHash": "b" * 64,
        }
        old_reference = {
            "globalId": "20000000-0000-4000-8000-000000000001",
            "snapshotHash": "c" * 64,
            "comparisonSnapshot": old_comparison,
        }
        current_reference = {
            "globalId": "20000000-0000-4000-8000-000000000002",
            "snapshotHash": "d" * 64,
            "comparisonSnapshot": current_comparison,
        }
        workspace = {
            "comparisonSnapshots": [old_comparison, current_comparison],
            "reviewReferenceRevisions": [old_reference, current_reference],
            "conclusionRevisions": [
                {
                    "comparisonSnapshot": old_comparison,
                    "reviewReferences": [
                        {
                            "globalId": old_reference["globalId"],
                            "snapshotHash": old_reference["snapshotHash"],
                        }
                    ],
                }
            ],
        }
        with patch.object(
            module.readiness_runtime,
            "current_controlled_reference",
            return_value=current_reference,
        ):
            self.assertEqual(
                module._submission_sources(workspace),
                (current_comparison, [current_reference]),
            )
        with patch.object(
            module.readiness_runtime,
            "current_controlled_reference",
            return_value=None,
        ):
            self.assertEqual(
                module._submission_sources(workspace),
                (old_comparison, [old_reference]),
            )

    def test_fresh_flow_orders_approved_print_before_rejected_successor(self) -> None:
        fresh = self.source.split("def run_fresh", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("REOPEN_APPROVED_KEY", fresh)
        self.assertIn('state="analysis"', fresh)
        self.assertIn("round_version=10", fresh)
        self.assertLess(fresh.index("DECIDE_APPROVED_KEY"), fresh.index("RETAIN_KEY"))
        self.assertLess(fresh.index("RETAIN_KEY"), fresh.index("PRINT_KEY"))
        self.assertLess(fresh.index("PRINT_KEY"), fresh.index("DECIDE_REJECTED_KEY"))
        self.assertLess(fresh.index("DECIDE_REJECTED_KEY"), fresh.index("REVISE_KEY"))
        for fragment in (
            "STALE_REVISE_KEY",
            "NOOP_REVISE_KEY",
            "_verify_idor_and_no_write",
            "cumulative_after == cumulative_before",
            "post_revision_pdf.content == first_pdf.content",
            "update.status in {403, 417}",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, fresh)
        self.assertIn('"NPI Trial Round Lifecycle Event": 17', self.source)
        self.assertIn('"NPI Trial Command Idempotency": 46', self.source)

    def test_cross_process_replay_reuses_both_summary_receipts_and_pdf(self) -> None:
        replay = self.source.split("def run_replay_only", 1)[1].split("\ndef ", 1)[0]
        for fragment in (
            "released_trial_summary.retain",
            "released_trial_summary.revise",
            "RETAIN_KEY",
            "REVISE_KEY",
            "PRINT_KEY",
            "retainedOutputHash",
            "retainedOutputSize",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, replay)

    def test_main_validates_administrator_and_both_disposable_users(self) -> None:
        module = self.module
        base_url = "http://127.0.0.1:8003"
        with patch.object(
            sys,
            "argv",
            [
                str(VERIFIER),
                "--base-url",
                base_url,
                "--route-disable-probe",
                "disabled",
            ],
        ), patch.dict(
            os.environ,
            {module.document_runtime.FIXTURE_RUN_ID_ENV: FIXTURE_RUN_ID},
            clear=False,
        ), patch.object(
            module,
            "secret_from_environment",
            return_value="fixture-secret",
        ), patch.object(
            module,
            "validate_local_fixture_inputs",
            return_value=base_url,
        ) as validate_inputs, patch.object(
            module,
            "login",
            return_value=object(),
        ), patch.object(
            module,
            "route_disable_probe",
            return_value={"routeMode": "disabled"},
        ), patch("builtins.print"):
            module.main()

        self.assertEqual(
            validate_inputs.call_args_list,
            [
                call(base_url, "Administrator", module.ACTOR_USER),
                call(base_url, "Administrator", module.UNRELATED_USER),
            ],
        )

    def test_shell_orders_p707_after_p706_and_restores_independent_switch(self) -> None:
        shell = self.shell
        self.assertLess(
            shell.index("run_production_transition_runtime_verifier replay-only"),
            shell.index("run_released_summary_runtime_verifier fresh"),
        )
        self.assertLess(
            shell.index("run_released_summary_runtime_verifier fresh"),
            shell.index("run_released_summary_route_probe disabled"),
        )
        self.assertLess(
            shell.index("run_released_summary_route_probe recovered"),
            shell.index("run_released_summary_runtime_verifier replay-only"),
        )
        for fragment in (
            "npi_p7_07_routes_disabled",
            "released_summary_route_disable_original_state",
            "restore_released_summary_route_switch",
            "verify_released_summary_runtime_log_redaction",
            "P7-07 route-disable switch to absent",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, shell)

    def test_ci_preflight_and_runtime_scope_are_p707_exact(self) -> None:
        workflow = self.workflow
        self.assertIn("tests.test_phase7_released_trial_summary_runtime_verifier", workflow)
        self.assertIn("scope=p5-01-through-p7-07", workflow)
        self.assertIn("predecessor_scope=p5-01-through-p7-06", workflow)
        self.assertIn(
            "P7-07 Released Trial Summary",
            workflow,
        )
        runtime_job = workflow.split("\n  document_runtime:\n", 1)[1]
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertIn("docker compose down --volumes", runtime_job)


if __name__ == "__main__":
    unittest.main()
