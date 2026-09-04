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
        self.assertEqual(value["task_id"], "PA-09-DESK-BOOT-HOTFIX")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(value["status"], "IN_PROGRESS")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "COMPLETE")
        self.assertEqual(value["requirement_ids"], ["NFR-MNT-001"])
        self.assertEqual(
            value["base_checkpoint"],
            "238d72413bfd80c3fa0fdbfb058a8e54dd25e5af",
        )
        self.assertEqual(
            value["predecessor_product_checkpoint"],
            "003597014d18cc35d74caf695e8f201e52f1306a",
        )
        self.assertEqual(
            value["expected_state"],
            {
                "phase_status_current_task": "PA-09-DESK-BOOT-HOTFIX",
                "phase_status_execution_hold": "NONE",
                "phase_status_resumed_product_task": "COMPLETE",
                "active_goal_marker": "PA-09-DESK-BOOT-HOTFIX",
                "next_action_marker": "PA-09-DESK-BOOT-HOTFIX",
                "controller_marker": "PA-09 production Frappe Desk boot hotfix active; exact-SHA ordinary CI required before deployment",
            },
        )
        for invariant in (
            "FRAPPE_DESK_REMAINS_ADMINISTRATION_AND_SUPPORT_ONLY",
            "NPI_REACT_BFF_TRANSLATION_CATALOGS_AND_PLACEHOLDERS_REMAIN_UNCHANGED",
            "SUPPORTED_EXTEND_BOOTINFO_HOOK_ONLY_NO_FRAPPE_CORE_PATCH",
            "FILTER_ONLY_DOUBLE_CURLY_MESSAGES_FROM_DESK_BOOT",
            "NO_SCHEMA_PERMISSION_AUTHENTICATION_OR_ERP_INTEGRATION_CHANGE",
            "PRODUCTION_DEPLOYMENT_REMAINS_INCREMENTAL_AND_BACKED_UP",
            "EXACT_SHA_ORDINARY_CI_BEFORE_DEPLOYMENT_AND_LEVEL_3_RELEASE_GATE_REQUIRED",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertTrue(
            {
                "apps/npi_core/npi_core/hooks.py",
                "implementation/evidence/production-activation/pa-09-frappe-desk-boot-hotfix.md",
                "tests/test_frappe_desk_boot.py",
                "tests/test_current_task_verifier.py",
            }.issubset(set(value["allowed_paths"]))
        )
        self.assertFalse([path for path in value["allowed_paths"] if "*" in path])

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
