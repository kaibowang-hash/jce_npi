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
        self.assertEqual(value["task_id"], "P8-09")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_AUDIT",
        )
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-00")
        self.assertEqual(value["requirement_ids"], ["FR-BR-002"])
        self.assertEqual(
            value["base_checkpoint"],
            "1e0f3facfa31f382b469df4b8084a3c64231674b",
        )
        for invariant in (
            "P8_08_FINAL_CHECKPOINT_1E0F3FAC_ORDINARY_33330200775_LEVEL_3_33330886346_ALL_SIX_JOBS_PASS",
            "P8_08_INTERNAL_READ_ONLY_RELEASED_SUMMARY_PROJECTION_SEAM_TECHNICAL_PASS",
            "P8_08_REUSES_P7_07_EXACT_IMMUTABLE_PROJECT_TRIAL_ROUND_SOURCE",
            "P8_08_EXTERNAL_PROJECTION_REMAINS_EXPLICITLY_UNAVAILABLE_EXTERNAL_CONTRACT_HELD",
            "P8_09_PRESENTATION_ONLY_APPROVED_JCE_CORE_TEXT_AND_EXACT_CORE_PNG",
            "ERPNEXT_TECHNICAL_CODE_REMAINS_STABLE_IN_API_EVENT_SCHEMA_PERSISTENCE_AND_ROUTING",
            "P8_09_PRODUCT_CODE_AUTHORIZED_FALSE_UNTIL_AUDIT_PLAN_EXACT_SHA_ORDINARY_AND_SEPARATE_ACTIVATION_PASS",
            "DR_REC_009_EXTERNAL_EVENT_PAYLOAD_REDACTION_CONSUMER_MAPPING_AND_RECEIPT_REMAIN_HELD",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertEqual(
            set(value["allowed_paths"]),
            {
                "implementation/ACTIVE_EXECUTION_GOAL.md",
                "implementation/AUTOPILOT_CONTROLLER.md",
                "implementation/BLOCKERS.md",
                "implementation/CURRENT_TASK.json",
                "implementation/NEXT_ACTION.md",
                "implementation/PHASE_STATUS.yaml",
                "implementation/REQUIREMENT_TRACEABILITY.csv",
                "implementation/phase-8-requirement-anchor.md",
                "implementation/evidence/phase-8/p8-08-plan.md",
                "implementation/evidence/phase-8/p8-08-validation.md",
                "implementation/evidence/phase-8/p8-09-plan.md",
                "scripts/reconcile_v1_2_traceability.py",
                "scripts/verify_v1_2_reconciliation.py",
                "tests/test_current_task_verifier.py",
                "tests/test_v1_2_reconciliation.py",
            },
        )
        self.assertEqual(len(value["allowed_paths"]), 15)
        self.assertFalse(any("*" in path for path in value["allowed_paths"]))
        self.assertFalse(
            any(path.startswith(("frontend/", "contracts/", ".github/")) for path in value["allowed_paths"])
        )
        self.assertEqual(
            sum(path.startswith("apps/") for path in value["allowed_paths"]),
            0,
        )
        self.assertEqual(
            sum(path.startswith("scripts/") for path in value["allowed_paths"]),
            2,
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
