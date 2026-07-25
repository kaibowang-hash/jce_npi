from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_VERIFIER = ROOT / "scripts" / "verify_gate_review_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"


class Phase4GateReviewRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RUNTIME_VERIFIER.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.functions = {
            node.name: ast.get_source_segment(cls.source, node) or ""
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")

    def test_fixture_namespace_is_caller_owned_and_shared_with_prerequisites(
        self,
    ) -> None:
        validator = self.functions["validated_fixture_run_id"]
        self.assertIn("return uuid4().hex", validator)
        self.assertIn('r"[a-f0-9]{32}"', validator)
        self.assertIn("CALLER_SUPPLIED_FIXTURE_RUN_ID", self.source)
        self.assertIn("NPI_GATE_REVIEW_RUNTIME_RUN_ID", self.source)
        self.assertIn(
            'FIXTURE_NAMESPACE = f"r{FIXTURE_REVISION}-{FIXTURE_RUN_ID}"',
            self.source,
        )
        self.assertIn(
            'os.environ.setdefault("NPI_GATE_EVIDENCE_RUNTIME_RUN_ID", FIXTURE_RUN_ID)',
            self.source,
        )

        environment = os.environ.copy()
        environment["NPI_GATE_REVIEW_RUNTIME_RUN_ID"] = (
            "0123456789abcdef0123456789abcdef"
        )
        accepted = subprocess.run(
            [sys.executable, str(RUNTIME_VERIFIER), "--help"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        environment["NPI_GATE_REVIEW_RUNTIME_RUN_ID"] = "NOT-A-RUN-ID"
        rejected = subprocess.run(
            [sys.executable, str(RUNTIME_VERIFIER), "--help"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "must be exactly 32 lowercase hexadecimal characters",
            rejected.stderr,
        )

    def test_schema_probe_requires_migrated_history_and_unique_actor_key(
        self,
    ) -> None:
        schema = self.functions["verify_runtime_schema"]
        for doctype in (
            "NPI Gate Review Cycle",
            "NPI Gate Review Record",
            "NPI Gate Review Exception",
            "NPI Gate Decision Snapshot",
            "NPI Gate Review Event",
            "NPI Gate Review Idempotency",
        ):
            self.assertIn(f'"{doctype}"', schema)
        self.assertIn("frappe.db.table_exists(", schema)
        self.assertIn('"actor_key_hash"', schema)
        self.assertIn('"Non_unique"', schema)
        self.assertIn('"closure_action_version"', schema)
        self.assertIn('"closure_action_snapshot_hash"', schema)
        self.assertIn(
            '{"active", "decided", "invalidated", "superseded"}',
            schema,
        )

    def test_failed_start_proves_real_transaction_rollback(self) -> None:
        rollback = self.functions["verify_transaction_rollback"]
        self.assertIn('"_insert_cycle"', rollback)
        self.assertIn("repository.start_review(", rollback)
        self.assertIn("frappe.db.rollback()", rollback)
        self.assertIn('"NPI Gate Review Idempotency"', rollback)
        self.assertIn('"NPI Gate Review Cycle"', rollback)
        self.assertIn("receipt is None", rollback)
        self.assertIn("cycles == []", rollback)
        main = self.functions["main"]
        self.assertLess(
            main.index('"verify_transaction_rollback"'),
            main.index("started = start_review("),
        )

    def test_runtime_covers_all_review_commands_and_exact_authority(self) -> None:
        main = self.functions["main"]
        for required_call in (
            "start_review(",
            "submit_review(",
            "request_exception(",
            "decide_exception(",
            "decide_gate(",
            "reopen_gate(",
        ):
            self.assertIn(required_call, main)
        self.assertIn("role_only_denied = submit_review(", main)
        self.assertIn("manager_transport_denied = submit_review(", main)
        self.assertIn(
            'validate_problem(role_only_denied, 403, "PERMISSION_DENIED")', main
        )
        self.assertIn(
            'validate_problem(manager_transport_denied, 403, "PERMISSION_DENIED")',
            main,
        )
        self.assertIn('"NPI API User"', self.functions["enable_transport_role"])
        self.assertNotIn("System Manager", self.functions["review_bindings"])

    def test_runtime_workspace_requires_closed_action_projections(self) -> None:
        workspace = self.functions["require_workspace"]
        self.assertIn('"decisionReadiness"', workspace)
        self.assertIn('"exceptionRequestOptions"', workspace)
        self.assertIn('{"allowedOutcomes", "blockedReasons"}', workspace)
        self.assertIn('{"outcome", "code"}', workspace)
        for code in (
            "REVIEW_CYCLE_CLOSED",
            "GATE_INPUT_CHANGED",
            "DECISION_AUTHORITY_REQUIRED",
            "REVIEWS_INCOMPLETE",
            "FILE_EVIDENCE_UNSAFE",
            "GATE_BLOCKED",
            "REQUIRED_P0_EVIDENCE_MISSING",
            "REQUIRED_EVIDENCE_MISSING",
            "EXCEPTION_NOT_REQUIRED",
            "APPROVED_EXCEPTION_REQUIRED",
        ):
            self.assertIn(f'"{code}"', workspace)
        for field in (
            "requirementGlobalId",
            "requirementKey",
            "kind",
            "maximumValidityDays",
            "closureActionGlobalIds",
        ):
            self.assertIn(f'"{field}"', workspace)
        self.assertIn('"allowedOutcomes"', workspace)
        self.assertIn('{"approved", "rejected"}', workspace)
        self.assertIn('"detail"', workspace)
        self.assertIn('"lineageHash"', workspace)
        self.assertIn('"inputSnapshot"', workspace)

    def test_actor_bound_replay_conflict_and_nondisclosure_are_explicit(
        self,
    ) -> None:
        main = self.functions["main"]
        self.assertIn("require_replay(", main)
        self.assertIn('"IDEMPOTENCY_KEY_CONFLICT"', main)
        self.assertIn("verify_review_receipt(", main)
        self.assertIn("REVIEW_KEY", main)
        self.assertIn("reconcile_gate_review_command(", main)
        self.assertIn("require_command_receipt(", main)
        reconciliation = self.functions["reconcile_gate_review_command"]
        self.assertIn("review-command-receipts", reconciliation)
        self.assertIn("idempotency_key=idempotency_key", reconciliation)
        self.assertIn("same_unavailable_problem(", main)
        self.assertIn("cross_unavailable", main)
        self.assertIn("wrong_tenant_unavailable", main)
        self.assertIn('"other-runtime-tenant"', self.source)
        persistence = self.functions["verify_persisted_review_history"]
        self.assertIn(
            "actor_key_hash(\n                    evidence_runtime.REVIEWER_USER,\n                    REVIEW_KEY,",
            persistence,
        )

    def test_real_source_mutations_prove_decided_and_active_lineage(self) -> None:
        refresh = self.functions["trigger_dependency_refresh"]
        self.assertIn('"npi_project_work_command_write"', refresh)
        self.assertIn("source.save()", refresh)
        self.assertIn("evaluate_gate_review_dependency(", refresh)
        self.assertIn('expected_event_type in {"invalidated", "refreshed"}', refresh)
        self.assertIn('"invalidated" if expected_old_state == "decided"', refresh)
        self.assertIn("prior_decision_snapshot_global_id", refresh)
        self.assertIn("GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR", refresh)
        self.assertIn('event.action_global_id in (None, "")', refresh)
        self.assertIn('payload.get("actionGlobalId") is None', refresh)
        self.assertNotIn('frappe.get_doc(\n        "NPI Domain Work Item"', refresh)
        main = self.functions["main"]
        self.assertIn('initial_body["blockers"] == []', main)
        self.assertIn(
            'refreshed_workspace["blockers"] == initial_body["blockers"] == []',
            main,
        )
        self.assertIn('value["impactActionGlobalId"] is None', main)
        self.assertEqual(
            main.count(
                '= run_bench_fixture(\n            "trigger_dependency_refresh"'
            ),
            2,
        )
        self.assertIn('"expected_event_type": "invalidated"', main)
        self.assertIn('"expected_event_type": "refreshed"', main)

    def test_closure_action_drift_is_invalidated_idempotently_then_rolled_back(
        self,
    ) -> None:
        drift = self.functions["verify_closure_action_drift_rollback"]
        self.assertIn('"npi_project_work_command_write"', drift)
        self.assertIn("action.save()", drift)
        self.assertIn(
            "evaluate_gate_review_work_item_dependency(**worker_values) is True",
            drift,
        )
        self.assertIn(
            "evaluate_gate_review_work_item_dependency(**worker_values) is False",
            drift,
        )
        self.assertIn(
            'str(changed_gate.review_state) == "requires_review"',
            drift,
        )
        self.assertIn(
            'str(changed_prior.state) == "invalidated"',
            drift,
        )
        self.assertIn('str(successor.trigger) == "dependency_change"', drift)
        self.assertIn(
            'changed_workspace["gate"]["downstreamDecisionCurrent"] is False', drift
        )
        self.assertIn("frappe.db.rollback()", drift)
        self.assertIn(
            'restored_workspace["gate"]["downstreamDecisionCurrent"] is True',
            drift,
        )
        self.assertIn('"duplicateWorkerNoOp": True', drift)
        self.assertIn('"gateInputVersionDelta": 1', drift)
        self.assertIn('"gateOptimisticVersionDelta": 1', drift)

        main = self.functions["main"]
        call_index = main.index(
            "closure_action_drift = run_bench_fixture(\n"
            '            "verify_closure_action_drift_rollback"'
        )
        self.assertGreater(call_index, main.index("first_decision_id ="))
        self.assertLess(call_index, main.index("reopened = reopen_gate("))
        self.assertIn(
            '"closureActionDriftRollback": closure_action_drift',
            main,
        )

    def test_file_delete_hook_proves_commit_and_rollback_transactions(self) -> None:
        deletion = self.functions["verify_file_delete_transactions"]
        self.assertIn('frappe.get_doc("File", file_id).delete(', deletion)
        self.assertIn("force=True", deletion)
        self.assertNotIn('patch.object(frappe, "enqueue"', deletion)
        self.assertIn(
            'patch.object(\n        background_jobs,\n        "get_queue"', deletion
        )
        self.assertIn("class FakePublisherQueue:", deletion)
        self.assertIn('queue_requests.count(("short", True)) == 1', deletion)
        self.assertIn("published_jobs == []", deletion)
        self.assertIn("frappe.db.rollback()", deletion)
        self.assertIn("frappe.db.commit()", deletion)
        self.assertIn(
            'published["function"] is background_jobs.execute_job',
            deletion,
        )
        self.assertIn('queue_arguments["method"] == worker_path', deletion)
        self.assertIn("evaluate_gate_review_dependency(**committed_job)", deletion)
        self.assertIn(
            "gate_after_commit.latest_decision_snapshot_global_id",
            deletion,
        )
        self.assertIn(
            "gate_after_commit.latest_decision_snapshot_hash",
            deletion,
        )
        self.assertIn('str(prior_after_commit.state) == "superseded"', deletion)
        self.assertIn('str(event.event_type) == "refreshed"', deletion)
        self.assertIn('payload.get("schemaVersion") == 2', deletion)
        self.assertIn('"rollbackNoSuccessor": True', deletion)

        main = self.functions["main"]
        self.assertIn('"seed_private_file_revisions"', main)
        self.assertIn("evidence_runtime.FILE_ATTACH_KEY", main)
        self.assertIn('"verify_file_delete_transactions"', main)
        self.assertIn('"fileDeleteDependencyRefresh": file_delete', main)
        self.assertGreater(
            main.index(
                "file_delete = run_bench_fixture(\n"
                '            "verify_file_delete_transactions"'
            ),
            main.index(
                "persisted = run_bench_fixture(\n"
                '            "verify_persisted_review_history"'
            ),
        )

    def test_requires_review_blocks_commands_until_explicit_revalidation(
        self,
    ) -> None:
        rejection = self.functions["verify_requires_review_command_rejections"]
        self.assertIn('str(gate.review_state) == "requires_review"', rejection)
        self.assertIn(".submit_review(", rejection)
        self.assertIn(".request_exception(", rejection)
        self.assertIn(".decide_gate(", rejection)
        self.assertIn("except VersionConflict:", rejection)
        self.assertIn("frappe.db.rollback()", rejection)
        self.assertIn("not accepted and not unexpected", rejection)
        main = self.functions["main"]
        self.assertGreater(
            main.index(
                "requires_review_rejections = run_bench_fixture(\n"
                '            "verify_requires_review_command_rejections"'
            ),
            main.index(
                'refreshed_workspace["gate"]["reviewState"] == "requires_review"'
            ),
        )

    def test_history_is_hash_sealed_immutable_and_cleanup_is_bounded(self) -> None:
        persistence = self.functions["verify_persisted_review_history"]
        self.assertIn('exception_request.get("schemaVersion") == 2', persistence)
        self.assertIn('"closureActionRef"', persistence)
        self.assertIn("exception.closure_action_version", persistence)
        self.assertIn("exception.closure_action_snapshot_hash", persistence)
        self.assertIn(
            '["invalidated", "invalidated", "superseded", "active"]',
            persistence,
        )
        self.assertIn(
            '["exception_decided", "reopened", "invalidated", "refreshed"]',
            persistence,
        )
        self.assertIn("canonical_hash(json_value(payload))", persistence)
        immutable = self.functions["verify_immutable_history"]
        self.assertIn("update_resource(", immutable)
        self.assertIn("delete_resource(", immutable)
        self.assertIn("update.status in {403, 417}", immutable)
        self.assertIn("deletion.status in {403, 417}", immutable)
        self.assertIn('"gate.review.history.delete_attempt"', immutable)
        self.assertIn('"NPI Audit Event"', immutable)
        self.assertIn("prior_event_ids", immutable)
        self.assertIn("delete_audits", immutable)
        self.assertIn('str(delete_audit["result"]) == "denied"', immutable)
        self.assertIn(
            'json_value(delete_audit["input_summary"])',
            immutable,
        )
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "verify_immutable_history"
        ]
        self.assertEqual(len(calls), 1)
        targets = calls[0].args[3]
        self.assertIsInstance(targets, ast.List)
        assert isinstance(targets, ast.List)
        self.assertTrue(
            all(
                isinstance(target, ast.Tuple) and len(target.elts) == 4
                for target in targets.elts
            )
        )
        self.assertEqual(
            {
                target.elts[0].value
                for target in targets.elts
                if isinstance(target, ast.Tuple)
                and isinstance(target.elts[0], ast.Constant)
            },
            {
                "NPI Gate Review Record",
                "NPI Gate Review Exception",
                "NPI Gate Decision Snapshot",
                "NPI Gate Review Cycle",
                "NPI Gate Review Event",
                "NPI Gate Review Idempotency",
            },
        )
        main = self.functions["main"]
        self.assertIn("cleanup_runtime_users(", main)
        self.assertIn("controlled_history_retained or retained_projects", main)
        self.assertNotIn(
            'delete_resource(\n                cleanup,\n                arguments.base_url,\n                "NPI Gate Review',
            main,
        )

    def test_bench_entrypoint_is_allowlisted_and_site_guarded(self) -> None:
        runner = self.functions["run_bench_fixture"]
        local = self.functions["run_local_bench_fixture"]
        self.assertIn('"--bench-fixture"', runner)
        self.assertIn('"--fixture-kwargs"', runner)
        self.assertNotIn('"execute"', runner)
        self.assertIn('cwd=BENCH_PATH / "sites"', runner)
        self.assertIn('"verify_runtime_schema":', local)
        self.assertIn('"verify_transaction_rollback":', local)
        self.assertIn('"trigger_dependency_refresh":', local)
        self.assertIn('"verify_closure_action_drift_rollback":', local)
        self.assertIn(
            '"verify_closure_action_drift_rollback",',
            self.source,
        )
        self.assertIn("frappe.init(", local)
        self.assertIn('frappe.set_user("Administrator")', local)
        self.assertIn("frappe.db.rollback()", local)
        self.assertIn("_validated_runtime_site()", self.source)

    def test_runtime_shell_supports_focused_and_composed_modes(self) -> None:
        self.assertIn("--gate-evidence-only", self.shell)
        self.assertIn("--gate-review-only", self.shell)
        self.assertIn("gate_review_runtime_run_id=", self.shell)
        self.assertIn(
            'export NPI_GATE_REVIEW_RUNTIME_RUN_ID="${gate_review_runtime_run_id}"',
            self.shell,
        )
        self.assertIn("run_gate_review_runtime_verifier", self.shell)
        self.assertIn(
            'python "${repo_root}/scripts/verify_gate_review_runtime.py"',
            self.shell,
        )
        self.assertGreater(
            self.shell.index("run_gate_review_runtime_verifier"),
            self.shell.index("run_site_guard"),
        )
        self.assertIn(
            '"${verification_mode}" == "all" ||\n'
            '      "${verification_mode}" == "--gate-review-only"',
            self.shell,
        )


if __name__ == "__main__":
    unittest.main()
