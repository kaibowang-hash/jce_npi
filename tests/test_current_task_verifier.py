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
        self.assertEqual(value["task_id"], "P8-08")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_CHECKPOINT_1_ACTIVATION_AWAITS_EXACT_SHA_ORDINARY",
        )
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P8-09")
        self.assertEqual(value["requirement_ids"], ["FR-INT-015"])
        self.assertEqual(
            value["base_checkpoint"],
            "d560fdf218f415a14b6cf5bef0baa436da4725cc",
        )
        for invariant in (
            "P8_07F_FINAL_CHECKPOINT_D8ABA505_ORDINARY_33317964484_LEVEL_3_33318628754_ALL_SIX_JOBS_PASS",
            "P8_07F_BOUNDED_COMPATIBILITY_RECONCILIATION_PRODUCT_ZERO_PRODUCTION_WRITE_ZERO_COMPLETE",
            "P8_07F_GOVERNANCE_CLOSEOUT_216AC604_ORDINARY_33320025714_ALL_FOUR_JOBS_PASS",
            "P8_08_AUDIT_PLAN_D560FDF2_ORDINARY_33320787112_ALL_FOUR_JOBS_PASS",
            "P8_08_PRODUCT_CODE_AUTHORIZED_FALSE_UNTIL_AUDIT_PLAN_EXACT_SHA_ORDINARY_AND_SEPARATE_CHECKPOINT_1_TRANSITION_PASS",
            "P8_08_REUSES_P7_07_EXACT_IMMUTABLE_SOURCE_PRESENTATION_AND_REDACTION_WITHOUT_DOMAIN_DUPLICATION",
            "P8_08_CHECKPOINT_1_EXACT_FIVE_PRODUCT_TEST_PATHS_AUTHORIZED_ONLY_AFTER_ACTIVATION_SHA_ORDINARY_PASS",
            "DR_REC_009_EXTERNAL_EVENT_PAYLOAD_REDACTION_CONSUMER_MAPPING_AND_RECEIPT_REMAIN_HELD",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertEqual(
            set(value["allowed_paths"]),
            {
                "apps/npi_integration/npi_integration/released_summary_projection/__init__.py",
                "apps/npi_integration/npi_integration/released_summary_projection/config.py",
                "apps/npi_integration/npi_integration/released_summary_projection/domain.py",
                "apps/npi_integration/npi_integration/released_summary_projection/readers.py",
                "implementation/ACTIVE_EXECUTION_GOAL.md",
                "implementation/AUTOPILOT_CONTROLLER.md",
                "implementation/CURRENT_TASK.json",
                "implementation/NEXT_ACTION.md",
                "implementation/PHASE_STATUS.yaml",
                "implementation/evidence/phase-8/p8-08-plan.md",
                "tests/test_current_task_verifier.py",
                "tests/test_phase8_released_trial_summary_projection_domain.py",
            },
        )
        self.assertEqual(len(value["allowed_paths"]), 12)
        self.assertFalse(any("*" in path for path in value["allowed_paths"]))
        self.assertFalse(
            any(path.startswith(("frontend/", "contracts/", ".github/")) for path in value["allowed_paths"])
        )
        self.assertEqual(
            sum(path.startswith("apps/") for path in value["allowed_paths"]),
            4,
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

    def test_delivery_task_rejects_product_requirement_claim(self) -> None:
        changed = {
            **self.manifest,
            "task_kind": "delivery_infrastructure",
            "completion_gate": "LEVEL_3",
            "requirement_ids": ["FR-TR-001"],
        }
        with self.assertRaisesRegex(CurrentTaskError, "must not claim"):
            validate_current_task(self.write_manifest(changed), check_git=False)

    def test_state_or_resume_drift_fails_closed(self) -> None:
        for key, value in (
            ("status", "PASS"),
            ("completion_gate", "LEVEL_1"),
            ("authorized_next_task", "p7-03"),
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
                ["implementation/evidence/phase-8/p8-08-plan.md"],
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
            return_value=("docs/ARCHITECTURE.md",),
        ):
            with self.assertRaisesRegex(CurrentTaskError, "outside"):
                validate_current_task(check_git=True)


if __name__ == "__main__":
    unittest.main()
