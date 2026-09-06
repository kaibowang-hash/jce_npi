from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_VERIFIER = ROOT / "scripts" / "verify_gate_evidence_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"


class Phase4GateEvidenceRuntimeVerifierTest(unittest.TestCase):
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

    def test_fixture_namespace_is_caller_owned_and_validated(self) -> None:
        validator = self.functions["validated_fixture_run_id"]
        self.assertIn("return uuid4().hex", validator)
        self.assertIn('r"[a-f0-9]{32}"', validator)
        self.assertIn("CALLER_SUPPLIED_FIXTURE_RUN_ID", self.source)
        self.assertIn("NPI_GATE_EVIDENCE_RUNTIME_RUN_ID", self.source)
        self.assertIn(
            'FIXTURE_NAMESPACE = f"r{FIXTURE_REVISION}-{FIXTURE_RUN_ID}"',
            self.source,
        )

        environment = os.environ.copy()
        environment["NPI_GATE_EVIDENCE_RUNTIME_RUN_ID"] = (
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
        environment["NPI_GATE_EVIDENCE_RUNTIME_RUN_ID"] = "NOT-A-RUN-ID"
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
        fixture_validation_calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "validate_local_fixture_inputs"
        ]
        self.assertTrue(fixture_validation_calls)
        self.assertTrue(
            all(len(node.args) == 3 for node in fixture_validation_calls)
        )

    def test_absence_is_proven_before_any_fixture_write(self) -> None:
        main = self.functions["main"]
        self.assertIn("verify_fresh_fixture_namespace(", main)
        first_write = main.index("create_internal_user(")
        self.assertLess(
            main.index("verify_fresh_fixture_namespace("),
            first_write,
        )
        preflight = self.functions["verify_fresh_fixture_namespace"]
        self.assertIn("result.status == 404", preflight)
        self.assertIn("get_resource(", preflight)
        self.assertIn("list_resources(", preflight)
        self.assertIn("actor_key_hash(", preflight)

    def test_private_file_fixture_is_real_guarded_and_tenant_safe(self) -> None:
        site_guard = self.functions["_validated_runtime_site"]
        self.assertIn("npi_runtime_disposable_marker", site_guard)
        self.assertIn("SELECT DATABASE(), CURRENT_USER(), @@port", site_guard)
        seed = self.functions["seed_private_file_revisions"]
        insert = self.functions["_insert_file_revision"]
        scan = self.functions["observe_private_file_scan"]
        self.assertIn("save_file(", insert)
        self.assertIn("FILE_REVISION_COMMAND_FLAG", insert)
        self.assertIn('"other-runtime-tenant"', seed)
        self.assertIn("wrong_tenant_rejected", seed)
        self.assertIn("frappe.db.rollback()", seed)
        self.assertIn("FILE_SCAN_RESULT_FLAG", scan)
        self.assertIn("revision.save()", scan)

    def test_internal_fixture_users_have_only_minimum_desk_identity(self) -> None:
        create_user = self.functions["create_internal_user"]
        self.assertIn('"roles": [{"role": "Desk User"}]', create_user)
        self.assertIn('"System Manager" not in roles', create_user)
        self.assertIn("delete_disposable_user(", create_user)

    def test_runtime_covers_exact_history_security_and_live_scan(self) -> None:
        main = self.functions["main"]
        for required_call in (
            "verify_disabled_template_rule(",
            "freeze_requirements(",
            "attach_evidence(",
            "run_bench_fixture(",
            "validate_gate_workspace(",
            "verify_append_only_guards(",
            "verify_persistence(",
            "assert_failed_command_absent(",
        ):
            self.assertIn(required_call, main)
        for evidence in (
            '"wbs_item"',
            '"file_revision"',
            '"EVIDENCE_SOURCE_UNAVAILABLE"',
            '"VERSION_CONFLICT"',
            '"IDEMPOTENCY_KEY_CONFLICT"',
            '"GATE_REQUIREMENTS_ALREADY_FROZEN"',
            '"infected"',
            '"/private/files/"',
        ):
            self.assertIn(evidence, self.source)
        self.assertNotIn("ERPNext", self.source)
        self.assertNotIn("erpnext", self.source.casefold())
        self.assertEqual(main.count("expected_status=201"), 2)

    def test_bench_fixture_entrypoint_is_allowlisted_and_site_guarded(self) -> None:
        runner = self.functions["run_bench_fixture"]
        local = self.functions["run_local_bench_fixture"]
        self.assertIn('"--bench-fixture"', runner)
        self.assertIn('"--fixture-kwargs"', runner)
        self.assertNotIn('"execute"', runner)
        self.assertIn('cwd=BENCH_PATH / "sites"', runner)
        self.assertIn('"observe_private_file_scan":', local)
        self.assertIn('"seed_private_file_revisions":', local)
        self.assertIn("frappe.init(", local)
        self.assertIn('frappe.set_user("Administrator")', local)
        self.assertIn("frappe.db.rollback()", local)
        self.assertIn("_validated_runtime_site()", self.source)

    def test_runtime_shell_supports_focused_and_default_p4_03_verification(
        self,
    ) -> None:
        self.assertIn("--gate-evidence-only", self.shell)
        self.assertIn("gate_evidence_runtime_run_id=", self.shell)
        self.assertIn(
            'export NPI_GATE_EVIDENCE_RUNTIME_RUN_ID="${gate_evidence_runtime_run_id}"',
            self.shell,
        )
        self.assertIn("run_gate_evidence_runtime_verifier", self.shell)
        self.assertIn(
            'python "${repo_root}/scripts/verify_gate_evidence_runtime.py"',
            self.shell,
        )
        self.assertGreater(
            self.shell.index("run_gate_evidence_runtime_verifier"),
            self.shell.index("run_site_guard"),
        )

    def test_bounded_cleanup_does_not_delete_controlled_history(self) -> None:
        main = self.functions["main"]
        disabled_guard = self.functions["verify_disabled_template_rule"]
        append_only = self.functions["verify_append_only_guards"]
        cleanup_users = self.functions["cleanup_runtime_users"]
        self.assertIn('{"enabled": 0}', cleanup_users)
        self.assertIn("delete_disposable_user(", cleanup_users)
        self.assertIn("controlled_history_retained", main)
        self.assertIn("retained_projects", main)
        self.assertIn("delete_resource(", disabled_guard)
        self.assertIn("get_resource(", disabled_guard)
        self.assertIn("delete_resource(", append_only)
        self.assertIn("status in {403, 417}", append_only)
        self.assertNotIn(
            'delete_resource(\n                cleanup,\n                arguments.base_url,\n                "NPI Gate Evidence Reference"',
            main,
        )


if __name__ == "__main__":
    unittest.main()
