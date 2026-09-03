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
        self.assertEqual(value["task_id"], "P9-05")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(value["status"], "IN_PROGRESS_P9_05_FINAL_GATE")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-06")
        self.assertEqual(
            value["requirement_ids"],
            ["FR-RP-008", "NFR-DAT-001"],
        )
        self.assertEqual(
            value["base_checkpoint"],
            "fa82f3e3dcc7a9474ea51a1356130d5cbc02adee",
        )
        self.assertEqual(
            value["predecessor_product_checkpoint"],
            "fa82f3e3dcc7a9474ea51a1356130d5cbc02adee",
        )
        self.assertEqual(
            value["expected_state"],
            {
                "phase_status_current_task": "P9-05",
                "phase_status_execution_hold": "NONE",
                "phase_status_resumed_product_task": "P9-05",
                "active_goal_marker": "P9-05",
                "next_action_marker": "P9-05",
                "controller_marker": "P9-05 historical migration implementation candidate; exact-SHA ordinary and Level 3 required",
            },
        )
        for invariant in (
            "P9_04_EXACT_SHA_FA82F3E3_ORDINARY_33702330209_AND_LEVEL3_33702723201_PASS",
            "P9_05_GOVERNANCE_SHA_4D54FBEF_ORDINARY_33704386277_PASS_PRODUCT_CODE_AUTHORIZED",
            "HISTORICAL_MIGRATION_IS_OPERATION_SPECIFIC_NON_PRODUCTION_REHEARSAL_NOT_A_GENERIC_WRITER",
            "SOURCE_IS_ONE_AUTHORIZED_CLEAN_PRIVATE_FILE_REVISION_WITH_EXACT_BYTES_HASH_SCHEMA_VERSION_AND_MANIFEST_HASH",
            "REQUIRED_UNIQUE_ENUM_REFERENCE_VERSION_AND_OWNERSHIP_VALIDATION_PRECEDES_ANY_MUTATION",
            "PREVIEW_IS_IMMUTABLE_NON_MUTATING_AND_REPORTS_CREATE_LINK_SKIP_BLOCKED_AND_EXACT_DIFFERENCES",
            "PARTIAL_ROWS_REMAIN_PARTIAL_CORRECTION_IS_FAILURE_ONLY_AND_ANY_SUCCESSOR_REENTERS_FULL_PREVIEW_VALIDATION",
            "ROLLBACK_ONLY_CHANGES_EXACT_UNCHANGED_NON_PROJECT_BINDINGS_ALL_TARGETS_RETAINED_OTHERWISE_FORWARD_CORRECTION",
            "ERP_OWNED_TRUTH_REMAINS_REFERENCE_ONLY_AND_NO_PRODUCTION_ERP_FACT_DELTA_IS_NEEDED_FOR_P9_05",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertTrue(
            {
                "implementation/evidence/phase-9/p9-04-validation.md",
                "implementation/evidence/phase-9/p9-05-plan.md",
                "implementation/evidence/phase-9/p9-05-validation.md",
                "implementation/phase-9-requirement-anchor.md",
                "apps/npi_core/npi_core/historical_migration/frappe_repository.py",
                "frontend/src/pages/historical-migration-workspace.tsx",
                "scripts/verify_historical_migration_runtime.py",
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
