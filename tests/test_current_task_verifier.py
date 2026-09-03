from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_current_task import (
    MANIFEST,
    CurrentTaskError,
    load_manifest,
    validate_allowed_paths,
    validate_check_commands,
    validate_current_task,
)


class CurrentTaskVerifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def write_manifest(self, value: object) -> Path:
        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        )
        with temporary:
            json.dump(value, temporary)
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return Path(temporary.name)

    def test_repository_manifest_and_state_pass(self) -> None:
        value = validate_current_task(check_git=False)
        self.assertEqual(value["task_id"], "P9-07")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_P9_07_IMPLEMENTATION_CANDIDATE_EXACT_SHA_GATES_REQUIRED",
        )
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-08")
        self.assertEqual(
            value["requirement_ids"],
            ["NFR-BCP-001", "NFR-MNT-001"],
        )
        self.assertEqual(
            value["base_checkpoint"],
            "8f5c2292dab6aa48f82c8aade37f3938b023699d",
        )
        self.assertEqual(
            value["predecessor_product_checkpoint"],
            "8f5c2292dab6aa48f82c8aade37f3938b023699d",
        )
        self.assertEqual(
            value["expected_state"],
            {
                "phase_status_current_task": "P9-07",
                "phase_status_execution_hold": "NONE",
                "phase_status_resumed_product_task": "P9-07",
                "active_goal_marker": "P9-07",
                "next_action_marker": "P9-07",
                "controller_marker": "P9-07 implementation candidate; exact-SHA ordinary and Level 3 required",
            },
        )
        for invariant in (
            "P9_06_EXACT_SHA_8F5C2292_ORDINARY_33719574371_AND_LEVEL3_33719982252_PASS",
            "P9_06_RUNTIME_JOB_100538152787_ARTIFACT_9880193608_PRODUCTION_CONTACT_FALSE",
            "FIXED_REPOSITORY_BENCH_NPI_LOCALHOST_NPI_ONE_RUNTIME_AND_DISPOSABLE_MARKER_ONLY",
            "RELEASE_MANIFEST_BINDS_EXACT_GIT_FRAPPE_APP_SCHEMA_AND_CONFIG_KEY_FINGERPRINTS_WITHOUT_VALUES_OR_SECRETS",
            "BACKUP_USES_ONLY_SYNTHETIC_DATABASE_PUBLIC_AND_PRIVATE_FILE_CANARIES_AND_TEMPORARY_0700_STORAGE",
            "RESTORE_REQUIRES_PRE_BACKUP_CANARIES_PRESENT_AND_POST_BACKUP_CANARIES_ABSENT",
            "FORWARD_FIX_RERUNS_MIGRATIONS_AND_COMPLETES_CUMULATIVE_GATE_AFTER_RESTORE",
            "NO_PRODUCTION_ERPNEXT_LAUNCHFLOW_OR_EXTERNAL_CONTACT_AND_NO_NEW_ERP_FACT_DEPENDENCY_FOR_P9_07",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertTrue(
            {
                "implementation/evidence/phase-9/p9-06-validation.md",
                "implementation/evidence/phase-9/p9-07-plan.md",
                "implementation/phase-9-requirement-anchor.md",
                "docs/GO_LIVE_AND_RECOVERY_RUNBOOK.md",
                "scripts/run_go_live_rehearsal.sh",
                "scripts/verify_go_live_rehearsal.py",
            }.issubset(set(value["allowed_paths"]))
        )
        self.assertFalse(any("*" in path for path in value["allowed_paths"]))

    def test_manifest_rejects_duplicate_or_unknown_keys(self) -> None:
        source = MANIFEST.read_text(encoding="utf-8")
        duplicate = source.replace(
            '"schema_version": 1,',
            '"schema_version": 1, "schema_version": 1,',
            1,
        )
        path = self.write_manifest({})
        path.write_text(duplicate, encoding="utf-8")
        with self.assertRaisesRegex(CurrentTaskError, "duplicate manifest key"):
            load_manifest(path)
        with self.assertRaisesRegex(CurrentTaskError, "keys drifted"):
            load_manifest(self.write_manifest({**self.manifest, "extra": True}))

    def test_product_task_rejects_missing_or_unknown_requirement(self) -> None:
        changed = {**self.manifest, "requirement_ids": []}
        with self.assertRaisesRegex(CurrentTaskError, "freeze at least one"):
            validate_current_task(self.write_manifest(changed), check_git=False)
        changed = {**self.manifest, "requirement_ids": ["FR-NOT-REAL"]}
        with self.assertRaisesRegex(CurrentTaskError, "unknown Requirement"):
            validate_current_task(self.write_manifest(changed), check_git=False)

    def test_state_or_resume_drift_fails_closed(self) -> None:
        for key, value in (
            ("status", "PASS"),
            ("completion_gate", "LEVEL_1"),
            ("authorized_next_task", "p9-04"),
            ("base_checkpoint", "short"),
        ):
            with self.subTest(key=key):
                changed = {**self.manifest, key: value}
                with self.assertRaises(CurrentTaskError):
                    validate_current_task(self.write_manifest(changed), check_git=False)

    def test_allowed_paths_reject_escape_and_out_of_scope_change(self) -> None:
        with self.assertRaisesRegex(CurrentTaskError, "unsafe allowed path"):
            validate_allowed_paths(["../*"], [])
        with self.assertRaisesRegex(CurrentTaskError, "outside"):
            validate_allowed_paths(
                ["implementation/evidence/phase-9/p9-03-plan.md"],
                ["apps/npi_core/npi_core/reporting/frappe_repository.py"],
            )

    def test_check_commands_reject_shell_control_and_snapshot_updates(self) -> None:
        safe = self.manifest["affected_checks"]
        validate_check_commands(safe)
        for command in (
            ["python", "-c", "print('unsafe arbitrary source')"],
            ["npm", "run", "test:visual", "--update-snapshots=all"],
            ["bash", "scripts/verify.sh", "&&", "true"],
        ):
            changed = json.loads(json.dumps(safe))
            changed["level_1"] = [command]
            with self.subTest(command=command), self.assertRaises(CurrentTaskError):
                validate_check_commands(changed)

    def test_git_path_validation_is_invoked_for_normal_check(self) -> None:
        with patch(
            "scripts.verify_current_task.changed_paths",
            return_value=("apps/npi_core/npi_core/unrelated.py",),
        ):
            with self.assertRaisesRegex(CurrentTaskError, "outside"):
                validate_current_task(check_git=True)


if __name__ == "__main__":
    unittest.main()
