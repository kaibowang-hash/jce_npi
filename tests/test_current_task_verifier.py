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
        self.assertEqual(value["task_id"], "CI-OPT-02")
        self.assertEqual(value["task_kind"], "delivery_infrastructure")
        self.assertEqual(value["status"], "IN_PROGRESS_CI_OPT_02_IMPLEMENTATION")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-02")
        self.assertEqual(value["requirement_ids"], [])
        self.assertEqual(
            value["base_checkpoint"],
            "a439043f96976c562edb8d4af69d51c709390043",
        )
        self.assertEqual(
            value["predecessor_product_checkpoint"],
            "a439043f96976c562edb8d4af69d51c709390043",
        )
        self.assertEqual(
            value["expected_state"],
            {
                "phase_status_current_task": "CI-OPT-02",
                "phase_status_execution_hold": "CI_OPT_02",
                "phase_status_resumed_product_task": "P9-02",
                "active_goal_marker": "CI-OPT-02",
                "next_action_marker": "CI-OPT-02",
                "controller_marker": "P9-01 Level 3 PASS; CI-OPT-02 implementation active",
            },
        )
        for invariant in (
            "P9_01_PRODUCT_SHA_A439043F_ORDINARY_33638920721_AND_LEVEL3_33640546810_PASS",
            "DELIVERY_ONLY_ZERO_PRODUCT_REQUIREMENTS",
            "DIAGNOSTIC_ALLOWLIST_EXACT_DENY_AND_UNKNOWN_FALL_BACK_TO_FULL_CI",
            "DIAGNOSTIC_RUN_ALWAYS_REPOSITORY_SECRET_AND_CONTROLLED_SITE",
            "DIAGNOSTIC_FAST_PATH_NEVER_MERGE_RELEASE_OR_LEVEL3_EVIDENCE",
            "NONVISUAL_PLAYWRIGHT_WORKERS_FOUR_VISUAL_WORKERS_TWO_RETRIES_ZERO",
            "MUTABLE_FRAPPE_SITE_CACHE_FORBIDDEN",
            "THREE_STABLE_RUNS_AND_P50_P95_REQUIRED_BEFORE_ACCEPTANCE",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
            "NO_PRODUCTION_ERPNEXT_CONTACT",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertEqual(
            set(value["allowed_paths"]),
            {
                ".github/workflows/ci.yml",
                "frontend/package.json",
                "implementation/ACTIVE_EXECUTION_GOAL.md",
                "implementation/AUTOPILOT_CONTROLLER.md",
                "implementation/CURRENT_TASK.json",
                "implementation/NEXT_ACTION.md",
                "implementation/PHASE_STATUS.yaml",
                "implementation/evidence/delivery-pipeline-optimization-2/plan.md",
                "implementation/evidence/delivery-pipeline-optimization-2/validation.md",
                "scripts/verify_devcontainer.py",
                "scripts/verify_prior_gate.py",
                "tests/test_current_task_verifier.py",
                "tests/test_devcontainer_verifier.py",
                "tests/test_prior_gate_verifier.py",
                "tests/test_v1_2_reconciliation.py",
            },
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

    def test_delivery_task_rejects_product_requirement_claim(self) -> None:
        changed = {**self.manifest, "requirement_ids": ["FR-TR-001"]}
        with self.assertRaisesRegex(CurrentTaskError, "must not claim"):
            validate_current_task(self.write_manifest(changed), check_git=False)

    def test_state_or_resume_drift_fails_closed(self) -> None:
        for key, value in (
            ("status", "PASS"),
            ("completion_gate", "LEVEL_1"),
            ("authorized_next_task", "p9-02"),
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
                ["implementation/evidence/delivery-pipeline-optimization-2/plan.md"],
                ["apps/npi_core/npi_core/trial/domain.py"],
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
            return_value=("apps/npi_core/npi_core/change_control/domain.py",),
        ):
            with self.assertRaisesRegex(CurrentTaskError, "outside"):
                validate_current_task(check_git=True)


if __name__ == "__main__":
    unittest.main()
