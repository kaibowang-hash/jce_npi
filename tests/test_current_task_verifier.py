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
        self.assertEqual(value["task_id"], "PA-08-DEPLOYMENT")
        self.assertEqual(value["task_kind"], "delivery_infrastructure")
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_DEPLOYED_FINAL_GATES_PENDING",
        )
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "COMPLETE")
        self.assertEqual(value["requirement_ids"], [])
        self.assertEqual(
            value["base_checkpoint"],
            "6b274f05be58fc52839b6f14a055b662d607787e",
        )
        self.assertEqual(
            value["predecessor_product_checkpoint"],
            "6b274f05be58fc52839b6f14a055b662d607787e",
        )
        self.assertEqual(
            value["expected_state"],
            {
                "phase_status_current_task": "PA-08-DEPLOYMENT",
                "phase_status_execution_hold": "FINAL_EXACT_SHA_ORDINARY_AND_LEVEL_3_REQUIRED_AFTER_DEPLOYMENT",
                "phase_status_resumed_product_task": "COMPLETE",
                "active_goal_marker": "PA-08-DEPLOYMENT",
                "next_action_marker": "PA-08-DEPLOYMENT",
                "controller_marker": "PA-08 exact release deployed and healthy; final evidence ordinary CI and Level 3 required",
            },
        )
        for invariant in (
            "P9_08_AND_PHASE_9_TECHNICAL_IMPLEMENTATION_REMAIN_COMPLETE",
            "PRODUCTION_DEPLOYMENT_IS_INCREMENTAL_WITH_NAMED_VOLUMES_PRESERVED",
            "ENCRYPTED_FULL_BACKUP_VERIFIED_BEFORE_MIGRATION_OR_IMAGE_SWITCH",
            "EXACT_SHA_BACKEND_AND_SPA_IMAGES_SWITCH_TOGETHER",
            "NPI_ERPNEXT_CONNECTOR_NEVER_INSTALLED_ON_LAUNCHFLOW",
            "PRODUCTION_ENVIRONMENT_MARKER_AND_PUBLIC_SELF_SIGNUP_DISABLED",
            "ERP_AUTHORIZATION_INGRESS_AND_REAL_ERP_ADAPTERS_REMAIN_DISABLED",
            "EXACT_SHA_ORDINARY_CI_AND_LEVEL_3_RELEASE_GATE_REQUIRED",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertTrue(
            {
                ".dockerignore",
                "apps/npi_core/npi_core/production_setup.py",
                "deploy/production/**",
                "implementation/evidence/production-activation/pa-08-aws-deployment.md",
                "tests/test_production_deployment.py",
                "tests/test_current_task_verifier.py",
            }.issubset(set(value["allowed_paths"]))
        )
        self.assertEqual(
            [path for path in value["allowed_paths"] if "*" in path],
            [
                "deploy/production/**",
                "frontend/tests/e2e/*-snapshots/*-linux.png",
            ],
        )

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
        changed = {**self.manifest, "task_kind": "product", "requirement_ids": []}
        with self.assertRaisesRegex(CurrentTaskError, "freeze at least one"):
            validate_current_task(self.write_manifest(changed), check_git=False)
        changed = {
            **self.manifest,
            "task_kind": "product",
            "requirement_ids": ["FR-NOT-REAL"],
        }
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

    def test_terminal_status_requires_level_3_and_complete_next_task(self) -> None:
        for key, value in (
            ("completion_gate", "LEVEL_2"),
            ("authorized_next_task", "P9-09"),
        ):
            with self.subTest(key=key):
                changed = {**self.manifest, key: value}
                changed["status"] = "IMPLEMENTATION_COMPLETE"
                with self.assertRaisesRegex(CurrentTaskError, "IMPLEMENTATION_COMPLETE"):
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
