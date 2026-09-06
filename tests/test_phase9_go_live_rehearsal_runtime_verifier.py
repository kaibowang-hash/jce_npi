from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_go_live_rehearsal.sh"
SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
VERIFIER = ROOT / "scripts" / "verify_go_live_rehearsal.py"


class GoLiveRehearsalRuntimeContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = RUNNER.read_text(encoding="utf-8")
        cls.shell = SHELL.read_text(encoding="utf-8")
        cls.verifier = VERIFIER.read_text(encoding="utf-8")

    def test_gate_invokes_one_fixed_rehearsal_only_in_projection_level_3(self) -> None:
        self.assertEqual(self.shell.count('bash "${repo_root}/scripts/run_go_live_rehearsal.sh"'), 1)
        invocation = self.shell[self.shell.rindex('if [[ "${verification_mode}" == "--projection-only"') :]
        self.assertIn("stop_runtime_server", invocation)
        self.assertIn('NPI_DOCUMENT_RUNTIME_RUN_ID="${document_runtime_run_id}"', invocation)
        self.assertNotIn("JCE-Core", invocation)
        self.assertNotIn("ssh ", invocation)

    def test_runner_has_no_dynamic_target_or_production_transport(self) -> None:
        for literal in (
            'site_name="npi.localhost"',
            'database_name="npi_one_runtime"',
            'runtime_marker="npi-one-local-runtime-disposable-v1"',
            'if [[ "$#" -ne 0 ]]',
            "accepts no caller-selected target or command",
            "mktemp -d",
            "chmod 0700",
            "trap cleanup EXIT",
        ):
            self.assertIn(literal, self.runner)
        for prohibited in ("JCE-Core", "ssh ", "http://", "https://", "curl "):
            self.assertNotIn(prohibited, self.runner)

    def test_rehearsal_helpers_run_from_the_fixed_bench(self) -> None:
        self.assertIn(
            'run_verifier() {\n  local mode="$1"\n  shift\n  (\n    cd "${bench_path}/sites"',
            self.runner,
        )

    def test_real_backup_restore_and_forward_fix_are_ordered(self) -> None:
        markers = (
            "run_verifier prepare",
            "run_verifier capture-tree",
            'bench --site "${site_name}" backup',
            "run_verifier backup-inventory",
            "run_verifier post-backup",
            'mv -- "${public_files}" "${quarantined_public}"',
            'bench --site "${site_name}" restore',
            "run_verifier verify-restore",
            "run_verifier verify-tree",
            'bench --site "${site_name}" migrate',
            "run_verifier forward-fix",
            "run_verifier result",
            "run_verifier finalize",
        )
        positions = [self.runner.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        for literal in (
            "--with-files",
            "--compress",
            "--backup-path-db",
            "--backup-path-files",
            "--backup-path-private-files",
            "--backup-path-conf",
            "--with-public-files",
            "--with-private-files",
        ):
            self.assertIn(literal, self.runner)
        self.assertNotIn("--force", self.runner)

    def test_fixture_is_specific_bounded_and_redacted(self) -> None:
        for literal in (
            '"productionContact": False',
            '"go-live-rehearsal-manifest.v1"',
            '"go-live-recovery-result.v1"',
            '"ToDo"',
            '"pre"',
            '"post"',
            "MAX_TREE_FILES",
            "MAX_TREE_BYTES",
            "configKeySha256",
            "schemaTreeSha256",
            "appTreeSha256",
        ):
            self.assertIn(literal, self.verifier)
        for prohibited in ("JCE-Core", "ssh ", "frappe.db" + ".sql"):
            self.assertNotIn(prohibited, self.verifier)

    def test_backup_and_child_output_do_not_leak_on_failure(self) -> None:
        self.assertGreaterEqual(self.runner.count(">/dev/null 2>/dev/null"), 4)
        self.assertIn('database_root_password=""', self.runner)
        self.assertIn('chmod 0600', self.runner)
        self.assertIn('rm -rf -- "${rehearsal_dir}"', self.runner)


if __name__ == "__main__":
    unittest.main()
