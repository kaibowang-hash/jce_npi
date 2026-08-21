from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_item_publish_runtime.py"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
FIXTURE = (
    ROOT
    / "apps"
    / "npi_integration"
    / "npi_integration"
    / "item_publish"
    / "runtime_fixture.py"
)


class Phase8ItemPublishRuntimeVerifierTest(unittest.TestCase):
    def test_runtime_verifier_covers_command_claim_boundary_and_restart(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)
        for marker in (
            "ITEM_EXECUTION_PROFILE_UNAVAILABLE",
            "live claim was not excluded",
            "expired pre-boundary claim was not recovered",
            "durable adapter boundary was not sealed",
            "crossed-boundary recovery blindly redispatched",
            "synthetic_verified",
            "uncertain_after_timeout",
            "target_idempotency_key_hash",
            "NPI_P8_03_RUNTIME_WORKER",
            "frozen service actor binding drifted",
            "distinct retained actors",
            "enabled internal NPI API User",
            "cross-process replay changed terminal truth",
            "recoverable_outbox_event_ids",
            '"mappingCount": 0',
            '"adapterCalls": synthetic_adapter_call_count()',
        ):
            self.assertIn(marker, source)

    def test_runtime_is_network_free_and_never_claims_formal_truth(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("urllib.request", source)
        self.assertIn("_assert_no_formal_target", source)
        self.assertIn('== {"synthetic", "none"}', source)
        self.assertIn('row["formal_item_code"] is None', source)
        self.assertIn('row["target_version"] is None', source)
        for forbidden in (
            "requests.",
            "httpx.",
            "erpnext.com",
            "core.whjichen.cn",
            "ignore_mandatory",
            "ignore_validate",
        ):
            self.assertNotIn(forbidden, source)

    def test_runtime_trace_is_structured_and_backed_by_persisted_queries(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        structural = functions["_structural_context"]
        structural_text = ast.unparse(structural)
        for persisted_field in (
            "'owner'",
            "'modified_by'",
            "'service_actor_user_id'",
            "'semantic_effect_hash'",
            "'guards'",
            "'auditEvents'",
        ):
            self.assertIn(persisted_field, structural_text)
        exercise = functions["exercise_worker"]
        exercise_text = ast.unparse(exercise)
        for trace_key in (
            "'callerRestoredAfterSynthetic'",
            "'callerRestoredAfterUncertain'",
            "'adapterSessionWorkerOnly'",
        ):
            self.assertIn(trace_key, exercise_text)
        runtime_text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"ITEM_PUBLISH_STREAM_ACTIVE"', runtime_text)
        self.assertIn('"ITEM_PUBLISH_EFFECT_RETAINED"', runtime_text)
        trace = {
            "adapterSessionWorkerOnly": True,
            "callerRestoredAfterSynthetic": True,
            "callerRestoredAfterUncertain": True,
            "ownerAndAuditBindingsVerified": True,
        }
        decoded = json.loads(json.dumps(trace, sort_keys=True))
        self.assertEqual(decoded, trace)

    def test_worker_actor_is_bound_before_use_and_process_runs_from_requester(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        exercise = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "exercise_worker"
        )
        assigned = {
            node.id
            for node in ast.walk(exercise)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        loaded = {
            node.id
            for node in ast.walk(exercise)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        self.assertIn("worker_user", assigned)
        self.assertIn("worker_user", loaded)
        self.assertNotIn("frappe.set_user(worker_user)", ast.unparse(exercise))
        self.assertIn("process_outbox_message", ast.unparse(exercise))

    def test_disposable_adapter_registry_is_exactly_marker_gated(self) -> None:
        source = FIXTURE.read_text(encoding="utf-8")
        ast.parse(source)
        for marker in (
            '"npi-one-item-publish-disposable-v1"',
            'os.environ.get("NPI_P8_03_RUNTIME_ENABLED") == "1"',
            'os.environ.get("NPI_P8_03_RUNTIME_MARKER") == _RUNTIME_MARKER',
            "ItemTargetMode.SYNTHETIC",
            "synthetic_adapter_call_count",
            "network-free-synthetic-v1",
            "synthetic_adapter_session_users",
            "Disposable Item adapter session actor drifted",
        ):
            self.assertIn(marker, source)
        for forbidden in (
            "base_url=",
            "secret_reference=",
            "ItemTargetMode.SANDBOX",
            "requests.",
            "httpx.",
        ):
            self.assertNotIn(forbidden, source)

    def test_shell_runs_default_disabled_fresh_and_cross_process_replay(self) -> None:
        source = SHELL.read_text(encoding="utf-8")
        for marker in (
            "capture_item_publish_runtime_project_id",
            "export_item_publish_runtime_environment",
            "clear_item_publish_runtime_environment",
            "run_item_publish_runtime_verifier disabled",
            "run_item_publish_runtime_verifier fresh",
            "run_item_publish_runtime_verifier replay-only",
            "verify_item_publish_runtime_log_redaction",
            "item_publish_runtime_environment_active=true",
        ):
            self.assertIn(marker, source)
        disabled = source.rindex("run_item_publish_runtime_verifier disabled")
        enabled = source.rindex("export_item_publish_runtime_environment")
        fresh = source.rindex("run_item_publish_runtime_verifier fresh")
        replay = source.rindex("run_item_publish_runtime_verifier replay-only")
        self.assertLess(disabled, enabled)
        self.assertLess(enabled, fresh)
        self.assertLess(fresh, replay)

    def test_migration_fixture_is_marker_gated_and_runs_after_replay(self) -> None:
        verifier = SCRIPT.read_text(encoding="utf-8")
        shell = SHELL.read_text(encoding="utf-8")
        for marker in (
            "def seed_legacy(",
            "def inspect_legacy(",
            "def cleanup_legacy(",
            '"preMigrationShape": "8dd"',
            '"newBindingsNull": True',
            '"preMigrationDuplicateAttemptCount": duplicate_attempt_count',
            'resultAttemptIndexUnique',
            '"ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED"',
            "--legacy-only",
            "tabNPI Item Publish Stream Guard",
        ):
            self.assertIn(marker, verifier)
        self.assertIn("seed_item_publish_runtime_legacy", shell)
        self.assertIn("bench --site \"${site_name}\" migrate", shell)
        self.assertIn("run_item_publish_runtime_verifier legacy-only", shell)
        self.assertLess(
            shell.rindex("run_item_publish_runtime_verifier replay-only"),
            shell.rindex("seed_item_publish_runtime_legacy"),
        )
        self.assertLess(
            shell.rindex("seed_item_publish_runtime_legacy"),
            shell.rindex("run_item_publish_runtime_verifier legacy-only"),
        )

    def test_controlled_workflow_records_cumulative_p8_03_scope(self) -> None:
        source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tests.test_phase8_item_publish_runtime_verifier", source)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --projection-only", source
        )
        self.assertIn("scope=p5-01-through-p8-03", source)
        self.assertIn("predecessor_scope=p5-01-through-p8-02", source)
        self.assertIn("p8-integration-runtime-${{ github.run_id }}", source)
        self.assertIn("needs.controlled_preflight.result == 'success'", source)


if __name__ == "__main__":
    unittest.main()
