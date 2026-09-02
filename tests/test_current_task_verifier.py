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
        self.assertEqual(value["task_id"], "P9-03")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(value["status"], "IN_PROGRESS_P9_03_FINAL_GATE_AUTHORIZED")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-04")
        self.assertEqual(
            value["requirement_ids"],
            ["NFR-PER-001", "NFR-PER-002", "NFR-AVL-001", "NFR-SCL-001"],
        )
        self.assertEqual(
            value["base_checkpoint"],
            "c845f93d27d29a692582599e4c5bdcec97693223",
        )
        self.assertEqual(
            value["predecessor_product_checkpoint"],
            "36cfe4cec8f31525e836c714236116704be066f3",
        )
        self.assertEqual(
            value["expected_state"],
            {
                "phase_status_current_task": "P9-03",
                "phase_status_execution_hold": "NONE",
                "phase_status_resumed_product_task": "P9-03",
                "active_goal_marker": "P9-03",
                "next_action_marker": "P9-03",
                "controller_marker": "P9-03 implementation candidate; final Level 3 pending",
            },
        )
        for invariant in (
            "P9_02_EXACT_SHA_36CFE4CE_ORDINARY_33687630510_AND_LEVEL3_33688112727_PASS",
            "P9_03_GOVERNANCE_EXACT_SHA_C845F93D_ORDINARY_33689961261_PASS",
            "PERFORMANCE_EVIDENCE_IS_NON_PRODUCTION_ENVIRONMENT_AND_FIXTURE_LABELLED_NOT_A_PRODUCTION_SLA",
            "COMMON_REQUEST_P95_TARGET_THREE_SECONDS_AND_METADATA_SEARCH_TARGET_FIVE_SECONDS",
            "MONOTONIC_CLOCK_FIXED_WARMUP_SAMPLE_COUNT_PERCENTILE_METHOD_PROVENANCE_AND_CHECKSUM_REQUIRED",
            "REPORTING_AND_SEARCH_OPTIMIZATION_MAY_BATCH_ONLY_EXISTING_AUTHORIZED_BOUNDED_READS",
            "FRONTEND_LOADING_MAY_DEFER_ONLY_ROUTE_OWNED_DATA_SOURCES_AND_UNSELECTED_LOCALE_CATALOGS",
            "PRODUCTION_AVAILABILITY_TARGET_REMAINS_IT_AND_BUSINESS_HELD_WITHOUT_ACCEPTED_MONITORING_FACTS",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
            "NO_PRODUCTION_ERPNEXT_OR_LAUNCHFLOW_CONTACT_DURING_P9_03_IMPLEMENTATION",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertTrue(
            {
                "apps/npi_core/npi_core/reporting/frappe_repository.py",
                "frontend/src/i18n/runtime.tsx",
                "frontend/scripts/verify-build-budget.mjs",
                "implementation/evidence/phase-9/p9-03-validation.md",
                "scripts/verify_reporting_collaboration_runtime.py",
                "tests/test_phase9_reporting_repository.py",
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
