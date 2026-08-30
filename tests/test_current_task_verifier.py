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
            "IN_PROGRESS_CHECKPOINT_1_VISUAL_BASELINE_REPAIR_AWAITS_EXACT_SHA_ORDINARY",
        )
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-00")
        self.assertEqual(value["requirement_ids"], ["FR-BR-002"])
        self.assertEqual(
            value["base_checkpoint"],
            "5c6793b3406ded8257b927ad89fbd9dba67bab4c",
        )
        for invariant in (
            "P8_08_FINAL_CHECKPOINT_1E0F3FAC_ORDINARY_33330200775_LEVEL_3_33330886346_ALL_SIX_JOBS_PASS",
            "P8_08_GOVERNANCE_CLOSEOUT_45F6A4D5_ORDINARY_33332397724_ALL_FOUR_JOBS_PASS",
            "P8_09_AUDIT_PLAN_5C6793B3_ORDINARY_33333259174_ALL_FOUR_JOBS_PASS",
            "P8_08_INTERNAL_READ_ONLY_RELEASED_SUMMARY_PROJECTION_SEAM_TECHNICAL_PASS",
            "P8_08_REUSES_P7_07_EXACT_IMMUTABLE_PROJECT_TRIAL_ROUND_SOURCE",
            "P8_08_EXTERNAL_PROJECTION_REMAINS_EXPLICITLY_UNAVAILABLE_EXTERNAL_CONTRACT_HELD",
            "P8_09_PRESENTATION_ONLY_APPROVED_JCE_CORE_TEXT_AND_EXACT_CORE_PNG",
            "ERPNEXT_TECHNICAL_CODE_REMAINS_STABLE_IN_API_EVENT_SCHEMA_PERSISTENCE_AND_ROUTING",
            "P8_09_CHECKPOINT_1_ACTIVATION_F92F2A02_ORDINARY_33334024759_ALL_FOUR_JOBS_PASS_PRODUCT_CODE_AUTHORIZED_TRUE",
            "P8_09_TEST_MANIFEST_EXPANSION_66F5A3A9_ORDINARY_33335381357_ALL_FOUR_JOBS_PASS",
            "P8_09_PRODUCT_F7F8DFFE_ORDINARY_33336799864_REPOSITORY_FRONTEND_SECRET_PASS_VISUAL_EXACT_THREE_BASELINE_DELTA",
            "P8_09_VISUAL_MANIFEST_EXPANSION_E3FAD564_ORDINARY_33337516645_REPOSITORY_FRONTEND_SECRET_PASS_VISUAL_REPEATS_ONLY_EXACT_THREE_AUTHORIZED_BASELINE_DELTAS",
            "P8_09_REUSES_EXISTING_DISPLAY_BRAND_AND_SOURCE_SYSTEM_IDENTITY_SEAMS_WITHOUT_GENERALIZATION",
            "P8_09_EXACT_CORE_PNG_SHA256_0C7182882022CF190925C90F0004C77AACA4DD513B86CCD0F23EFB30171E0E42",
            "P8_09_CHECKPOINT_1_EXACT_TWENTY_NINE_PRODUCT_TEST_VISUAL_AND_GOVERNANCE_PATHS",
            "P8_09_EXACT_FOUR_NEW_LINUX_VISUAL_BASELINES_PLUS_THREE_EVIDENCED_TOOLING_BASELINE_UPDATES_ONLY",
            "P8_09_LEVEL_1_FRONTEND_1086_UNIT_458_NONVISUAL_E2E_FOUR_LINUX_VISUAL_AND_STATIC_GATES_PASS",
            "P8_09_TOOLING_BASELINE_REPAIR_LOCAL_THREE_OF_THREE_AND_FULL_GOVERNED_VISUAL_135_OF_135_PASS",
            "DR_REC_009_EXTERNAL_EVENT_PAYLOAD_REDACTION_CONSUMER_MAPPING_AND_RECEIPT_REMAIN_HELD",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertEqual(
            set(value["allowed_paths"]),
            {
                "apps/npi_core/npi_core/translations/zh-TW.csv",
                "apps/npi_core/npi_core/translations/zh.csv",
                "contracts/terminology-allowlist.yaml",
                "frontend/scripts/verify-display-brand.mjs",
                "frontend/src/components/primitives.tsx",
                "frontend/src/components/worklist.tsx",
                "frontend/src/generated/catalogs.ts",
                "frontend/src/i18n/copy.ts",
                "frontend/src/styles/app.css",
                "frontend/src/ui-adapters/display-brand.tsx",
                "frontend/tests/e2e/display-brand.spec.ts",
                "frontend/tests/e2e/display-brand.spec.ts-snapshots/p8-09-jce-core-dark-en-1440x900-100-linux.png",
                "frontend/tests/e2e/display-brand.spec.ts-snapshots/p8-09-jce-core-identity-en-1366x768-100-linux.png",
                "frontend/tests/e2e/display-brand.spec.ts-snapshots/p8-09-jce-core-identity-zh-1440x900-125-linux.png",
                "frontend/tests/e2e/display-brand.spec.ts-snapshots/p8-09-jce-core-identity-zh-TW-1920x1080-150-linux.png",
                "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts-snapshots/r1-06-p0-normal-tooling-en-1440x900-100-linux.png",
                "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts-snapshots/r1-06-p0-normal-tooling-zh-1440x900-100-linux.png",
                "frontend/tests/e2e/r1-06-p0-visual-governance.spec.ts-snapshots/r1-06-p0-normal-tooling-zh-TW-1440x900-100-linux.png",
                "frontend/tests/unit/display-brand.test.tsx",
                "frontend/tests/unit/field-attachment-primitives.test.tsx",
                "frontend/tests/unit/formatters-and-copy.test.ts",
                "frontend/tests/unit/primitives-and-objects.test.tsx",
                "implementation/ACTIVE_EXECUTION_GOAL.md",
                "implementation/AUTOPILOT_CONTROLLER.md",
                "implementation/CURRENT_TASK.json",
                "implementation/NEXT_ACTION.md",
                "implementation/PHASE_STATUS.yaml",
                "implementation/evidence/phase-8/p8-09-plan.md",
                "tests/test_current_task_verifier.py",
            },
        )
        self.assertEqual(len(value["allowed_paths"]), 29)
        self.assertFalse(any("*" in path for path in value["allowed_paths"]))
        self.assertFalse(
            any(path.startswith(".github/") for path in value["allowed_paths"])
        )
        self.assertEqual(
            sum(path.startswith("apps/") for path in value["allowed_paths"]),
            2,
        )
        self.assertEqual(
            sum(path.startswith("frontend/") for path in value["allowed_paths"]),
            19,
        )
        self.assertEqual(
            sum(path.startswith("contracts/") for path in value["allowed_paths"]),
            1,
        )
        self.assertEqual(
            sum(path.startswith("scripts/") for path in value["allowed_paths"]),
            0,
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
