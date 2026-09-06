from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_VERIFIER = ROOT / "scripts/verify_project_work_runtime.py"


class Phase4ProjectWorkRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RUNTIME_VERIFIER.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.functions = {
            node.name: ast.get_source_segment(cls.source, node) or ""
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_fixture_identity_uses_a_fresh_process_run_namespace(self) -> None:
        validator = self.functions["validated_fixture_run_id"]
        self.assertIn("return uuid4().hex", validator)
        self.assertIn('r"[a-f0-9]{32}"', validator)
        self.assertIn("CALLER_SUPPLIED_FIXTURE_RUN_ID", self.source)
        self.assertIn("NPI_PROJECT_WORK_RUNTIME_RUN_ID", self.source)
        self.assertIn(
            'FIXTURE_NAMESPACE = f"r{FIXTURE_REVISION}-{FIXTURE_RUN_ID}"',
            self.source,
        )
        self.assertIn("FIXTURE_NAMESPACE", self.functions["fixture_id"])
        self.assertIn("FIXTURE_NAMESPACE", self.functions["business_code"])
        self.assertIn("len(POLICY_KEY) <= 64", self.source)
        self.assertIn("len(GUARD_POLICY_KEY) <= 64", self.source)

    def test_caller_run_id_is_validated_before_argument_processing(self) -> None:
        environment = os.environ.copy()
        environment["NPI_PROJECT_WORK_RUNTIME_RUN_ID"] = (
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

        environment["NPI_PROJECT_WORK_RUNTIME_RUN_ID"] = "NOT-A-RUN-ID"
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

        environment.pop("NPI_PROJECT_WORK_RUNTIME_RUN_ID", None)
        environment["NPI_RUNTIME_ADMINISTRATOR_PASSWORD"] = "unused"
        unnamed_replay = subprocess.run(
            [
                sys.executable,
                str(RUNTIME_VERIFIER),
                "--base-url",
                "http://127.0.0.1:1",
                "--replay-only",
            ],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(unnamed_replay.returncode, 0)
        self.assertIn(
            "--replay-only requires NPI_PROJECT_WORK_RUNTIME_RUN_ID",
            unnamed_replay.stderr,
        )
        self.assertNotIn("Connection refused", unnamed_replay.stderr)

    def test_main_requires_an_empty_namespace_before_writing(self) -> None:
        main = self.functions["main"]
        preflight = self.functions["verify_fresh_fixture_namespace"]
        self.assertIn("verify_fresh_fixture_namespace(", main)
        self.assertNotIn("classify_fixture_state(", main)
        self.assertIn("result.status == 404", preflight)
        self.assertIn("project_idempotency == []", preflight)
        self.assertIn("work_idempotency == []", preflight)

    def test_first_success_and_replay_evidence_are_distinct(self) -> None:
        fresh = self.functions["require_fresh_command_success"]
        replay = self.functions["require_sealed_command_replay"]
        execute = self.functions["execute_success_with_replay"]
        concurrency = self.functions["verify_true_concurrency"]
        project = self.functions["ensure_project"]

        self.assertIn('Idempotency-Replayed") == "false"', fresh)
        self.assertIn('Idempotency-Replayed") == "true"', replay)
        self.assertIn("result.body == expected_body", replay)
        self.assertIn("require_fresh_command_success(", execute)
        self.assertIn("require_sealed_command_replay(", execute)
        self.assertIn("require_fresh_command_success(", concurrency)
        self.assertIn("require_sealed_command_replay(", concurrency)
        self.assertIn('Idempotency-Replayed") == "false"', project)

    def test_baseline_expectation_uses_the_domain_uuid_order(self) -> None:
        verifier = self.functions["verify_baseline_hash"]
        self.assertIn("sorted(", verifier)
        self.assertIn("expected_items", verifier)
        self.assertIn("key=lambda item: item[0]", verifier)

    def test_runtime_rejects_a_tampered_domain_work_cursor(self) -> None:
        verifier = self.functions["verify_domain_queries"]
        self.assertIn('cursor=f"{cursor[:-1]}{replacement}"', verifier)
        self.assertIn(
            'validate_problem(tampered, 422, "VALIDATION_FAILED")',
            verifier,
        )
        self.assertIn('"path": "cursor"', verifier)

    def test_replay_only_requires_a_complete_caller_named_namespace(self) -> None:
        main = self.functions["main"]
        replay = self.functions["verify_cross_process_replay"]
        self.assertIn('"--replay-only"', main)
        self.assertIn("CALLER_SUPPLIED_FIXTURE_RUN_ID is not None", main)
        self.assertIn("verify_cross_process_replay(", main)
        replay_branch = main.index("if arguments.replay_only:")
        fixture_setup = main.index(
            "fixture_password = secret_from_environment("
        )
        self.assertLess(replay_branch, fixture_setup)
        self.assertIn("return", main[replay_branch:fixture_setup])
        self.assertIn("classify_fixture_state(", replay)
        self.assertIn('"project:main": "compatible-complete"', replay)
        self.assertIn('"project:cycle": "compatible-complete"', replay)
        self.assertIn('"project:guard": "compatible-complete"', replay)
        self.assertIn(
            '"project:concurrency": "compatible-complete"',
            replay,
        )
        self.assertIn(
            "fixture_states == expected_states",
            replay,
        )

    def test_replay_only_compares_the_command_to_sealed_persistence(self) -> None:
        replay = self.functions["verify_cross_process_replay"]
        self.assertIn('"NPI Project Work Idempotency"', replay)
        self.assertIn('"response_json"', replay)
        self.assertIn('"response_sealed"', replay)
        self.assertIn("normalized_command_payload(", replay)
        self.assertIn("work_command(", replay)
        self.assertIn("require_sealed_command_replay(", replay)
        self.assertIn("sealed_response", replay)
        self.assertIn("retained_after == idempotency_rows", replay)
        self.assertIn("after_context.body == before_context.body", replay)
        for mutation in (
            "ensure_synthetic_template(",
            "ensure_runtime_user(",
            "ensure_work_policy(",
            "ensure_project(",
            "create_resource(",
            "update_resource(",
            "delete_resource(",
        ):
            self.assertNotIn(mutation, replay)

    def test_runtime_shell_uses_one_namespace_across_two_processes(self) -> None:
        runtime_shell = (
            ROOT / "scripts" / "verify-frappe-runtime.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("project_work_runtime_run_id=", runtime_shell)
        self.assertIn(
            'export NPI_PROJECT_WORK_RUNTIME_RUN_ID="${project_work_runtime_run_id}"',
            runtime_shell,
        )
        fresh = "run_project_work_runtime_verifier fresh"
        replay = "run_project_work_runtime_verifier replay-only"
        self.assertIn(fresh, runtime_shell)
        self.assertIn(replay, runtime_shell)
        self.assertLess(runtime_shell.index(fresh), runtime_shell.index(replay))


if __name__ == "__main__":
    unittest.main()
