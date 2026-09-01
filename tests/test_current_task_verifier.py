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
        self.assertEqual(value["task_id"], "P9-01")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(
            value["status"], "IN_PROGRESS_P9_01D_IMPLEMENTATION_GATE"
        )
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-02")
        self.assertEqual(
            value["expected_state"]["controller_marker"],
            "P9-01D summary lifecycle ordering repair Level 1 PASS; exact-SHA ordinary CI pending",
        )
        self.assertIn("FR-CH-001", value["requirement_ids"])
        self.assertIn("FR-CH-010", value["requirement_ids"])
        self.assertIn("INT-008", value["requirement_ids"])
        self.assertNotIn("FR-RP-001", value["requirement_ids"])
        self.assertEqual(
            value["base_checkpoint"],
            "0c11b1f378b1c962b6d05739f3c1f3cad18ad389",
        )
        for invariant in (
            "P9_00_EXACT_SHA_065803AE_ORDINARY_33345162833_ALL_FOUR_JOBS_PASS",
            "P9_01_AUDIT_ONLY_PRODUCT_CODE_AUTHORIZED_FALSE_UNTIL_PLAN_EXACT_SHA_ORDINARY_PASS",
            "ERPNEXT_OWNS_FORMAL_ECR_ECO_ECN_IDENTIFIER_EXECUTION_STATUS_AND_TRANSACTION_EFFECTIVE_TRUTH",
            "NPI_ONE_OWNS_ENGINEERING_IMPACT_ASSESSMENT_AFFECTED_VERSION_REVALIDATION_TASK_EVIDENCE_AND_GATE_EFFECTS",
            "CURRENT_ARCHITECTURE_DATA_OWNERSHIP_OPENAPI_EVENTS_AND_P8_01_THROUGH_P8_09_REMAIN_DEFAULT_CORRECT",
            "NO_PROVEN_DIFFERENCE_MEANS_DIRECT_MATCH_NO_CHANGE_AND_NO_ADJUSTMENT_TASK",
            "P9_01_FACT_DELTA_LIMITED_TO_EXACT_ECR_ECO_ECN_DECLARATIVE_METADATA_NO_BUSINESS_ROWS_OR_TARGET_METHODS",
            "P9_01_PRODUCTION_FACT_RESULT_FE112A15_ACCEPTED_ECR_PRESENT_ECO_ECN_ABSENT",
            "P9_01A_ONLY_AFTER_PLAN_EXACT_SHA_ORDINARY_PASS",
            "P9_01A_REUSES_EXISTING_BASELINE_DOCUMENT_EBOM_TOOLING_TRIAL_GATE_AND_PROJECT_WORK_IDENTITIES",
            "P9_01A_ERP_FORMAL_ID_STATUS_AND_EFFECTIVITY_FIELDS_ARE_OBSERVATION_OWNED_NOT_CALLER_EDITABLE",
            "P9_01A_EXACT_SHA_CF24E863_ORDINARY_33353974303_ALL_FOUR_JOBS_PASS",
            "P9_01B_GOVERNANCE_EXACT_SHA_07B869BC_ORDINARY_33354760251_ALL_FOUR_JOBS_PASS",
            "P9_01B_PROJECT_FIRST_COMMAND_QUERY_API_ONLY_INT008_AND_UI_REMAIN_OUT_OF_SCOPE",
            "P9_01B_EVERY_SUCCESSOR_BINDS_EXACT_CURRENT_REVISION_VERSION_AND_SNAPSHOT_HASH",
            "P9_01B_COMMANDS_ARE_CSRF_ACTOR_IDEMPOTENCY_AUDIT_AND_SINGLE_TRANSACTION_BOUND",
            "P9_01B_FORMAL_CHANGE_FIELDS_ARE_LINK_OBSERVATION_OWNED_AND_NEVER_CALLER_EDITABLE",
            "P9_01B_EXACT_SHA_73A7282D_ORDINARY_33357104386_ALL_FOUR_JOBS_PASS",
            "P9_01C_GOVERNANCE_EXACT_SHA_83F35DDE_ORDINARY_33358374034_ALL_FOUR_JOBS_PASS",
            "P9_01C_EXACT_SIGNED_ERP_ENGINEERING_CHANGE_V1_INBOX_AND_FORMAL_OBSERVATION_ONLY",
            "P9_01C_EXACT_CHANGE_IMPLEMENTATION_SUMMARY_V1_REQUEST_OUTBOX_ATTEMPT_RESULT_ONLY",
            "P9_01C_OPERATION_SPECIFIC_PERSISTENCE_DOES_NOT_REUSE_PROJECT_INBOX_OR_SHARED_OUTBOX_CONTROLLER",
            "P9_01C_DUPLICATE_REORDER_CONFLICT_PARTIAL_429_5XX_TIMEOUT_AFTER_COMMIT_REMAIN_EXPLICIT",
            "P9_01C_UNCERTAIN_OR_PARTIAL_RESULT_NEVER_AUTOMATICALLY_REDISPATCHED",
            "P9_01C_EXACT_SHA_0C11B1F3_ORDINARY_33363140068_ALL_FOUR_JOBS_PASS",
            "P9_01D_GOVERNANCE_EXACT_SHA_0E46D2D2_ORDINARY_33364478666_ALL_FOUR_JOBS_PASS",
            "P9_01D_PROJECT_TAB_ONLY_NO_NEW_TOP_LEVEL_NAVIGATION",
            "P9_01D_EXISTING_PROJECT_FIRST_API_AND_OPERATION_SPECIFIC_INTEGRATION_SEAMS_ONLY",
            "P9_01D_ERP_OBSERVATION_FIELDS_REMAIN_READ_ONLY_AND_NPI_IMPACT_EVIDENCE_REMAINS_NPI_OWNED",
            "P9_01D_DISPOSABLE_SITE_RUNTIME_VISUAL_I18N_ACCESSIBILITY_AND_SECURITY_LEVEL_3_REQUIRED",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
        ):
            self.assertIn(invariant, value["frozen_invariants"])
        self.assertEqual(
            set(value["allowed_paths"]),
            {
                "implementation/ACTIVE_EXECUTION_GOAL.md",
                "implementation/AUTOPILOT_CONTROLLER.md",
                "implementation/CURRENT_TASK.json",
                "implementation/NEXT_ACTION.md",
                "implementation/PHASE_STATUS.yaml",
                "implementation/evidence/phase-9/p9-01-plan.md",
                "implementation/evidence/phase-9/p9-01-integration-checkpoint.md",
                "implementation/evidence/phase-9/p9-01-ui-checkpoint.md",
                "apps/npi_core/npi_core/change_control/frappe_validation.py",
                "apps/npi_core/npi_core/change_control/frappe_repository.py",
                "apps/npi_core/npi_core/change_control_api.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_engineering_change/npi_engineering_change.py",
                "apps/npi_integration/npi_integration/engineering_change_api.py",
                "apps/npi_integration/npi_integration/engineering_change/frappe_repository.py",
                "apps/npi_integration/npi_integration/engineering_change/runtime_fixture.py",
                "apps/npi_core/npi_core/translations/zh-TW.csv",
                "apps/npi_core/npi_core/translations/zh.csv",
                "frontend/src/api/change-control-data-source.ts",
                "frontend/src/api/integration-operations-data-source.ts",
                "frontend/src/app/app.tsx",
                "frontend/src/generated/catalogs.ts",
                "frontend/src/pages/execution-page.tsx",
                "frontend/src/pages/project-change-workspace.tsx",
                "frontend/src/pages/project-page.tsx",
                "frontend/src/pages/project-workspace.tsx",
                "frontend/src/styles/app.css",
                "frontend/tests/e2e/p9-01-change-control-live.spec.ts",
                "frontend/tests/e2e/p9-01-change-control-live.spec.ts-snapshots/p9-01-change-control-en-1366x768-100-linux.png",
                "frontend/tests/e2e/p9-01-change-control-live.spec.ts-snapshots/p9-01-change-control-zh-1440x900-125-linux.png",
                "frontend/tests/e2e/p9-01-change-control-live.spec.ts-snapshots/p9-01-change-control-zh-TW-1920x1080-150-linux.png",
                "frontend/tests/e2e/p5-01-documents-live.spec.ts-snapshots/p5-01-documents-en-1366x768-100-linux.png",
                "frontend/tests/e2e/p5-01-documents-live.spec.ts-snapshots/p5-01-documents-zh-1440x900-125-linux.png",
                "frontend/tests/e2e/p5-01-documents-live.spec.ts-snapshots/p5-01-documents-zh-TW-1920x1080-150-linux.png",
                "frontend/tests/e2e/p5-04-ebom-live.spec.ts-snapshots/p5-04-ebom-workspace-en-1366x768-100-linux.png",
                "frontend/tests/e2e/p5-04-ebom-live.spec.ts-snapshots/p5-04-ebom-workspace-zh-1440x900-125-linux.png",
                "frontend/tests/e2e/p5-04-ebom-live.spec.ts-snapshots/p5-04-ebom-workspace-zh-TW-1920x1080-150-linux.png",
                "frontend/tests/e2e/p5-06-controlled-print-live.spec.ts-snapshots/p5-06-controlled-print-en-1366x768-100-linux.png",
                "frontend/tests/e2e/p5-06-controlled-print-live.spec.ts-snapshots/p5-06-controlled-print-zh-1440x900-125-linux.png",
                "frontend/tests/e2e/p5-06-controlled-print-live.spec.ts-snapshots/p5-06-controlled-print-zh-TW-1920x1080-150-linux.png",
                "frontend/tests/e2e/p7-06-production-transition-live.spec.ts-snapshots/p7-06-production-transition-en-1366x768-100-linux.png",
                "frontend/tests/e2e/p7-06-production-transition-live.spec.ts-snapshots/p7-06-production-transition-zh-1440x900-125-linux.png",
                "frontend/tests/e2e/p7-06-production-transition-live.spec.ts-snapshots/p7-06-production-transition-zh-TW-1920x1080-150-linux.png",
                "frontend/tests/e2e/p8-03-item-publish-live.spec.ts-snapshots/p8-03-item-inactive-en-1366x768-100-linux.png",
                "frontend/tests/support/change-control-fixture.ts",
                "frontend/tests/support/integration-operations-fixture.ts",
                "frontend/tests/unit/change-control-data-source.test.ts",
                "frontend/tests/unit/execution-page.test.tsx",
                "frontend/tests/unit/integration-operations-data-source.test.ts",
                "frontend/tests/unit/project-change-workspace.test.tsx",
                "frontend/tests/unit/project-workspace.test.tsx",
                "scripts/verify-frappe-runtime.sh",
                "scripts/verify_engineering_change_runtime.py",
                "scripts/verify_integration_operations_runtime.py",
                "tests/test_current_task_verifier.py",
                "tests/test_phase8_item_publish_security.py",
                "tests/test_phase9_change_control_api.py",
                "tests/test_phase9_change_control_metadata.py",
                "tests/test_phase9_change_control_repository.py",
                "tests/test_phase9_change_integration_api.py",
                "tests/test_phase9_change_integration_repository.py",
                "tests/test_phase9_change_integration_worker.py",
                "tests/test_phase8_integration_operations_runtime_verifier.py",
                "tests/test_phase9_change_control_runtime_verifier.py",
            },
        )
        self.assertEqual(len(value["allowed_paths"]), 63)
        self.assertFalse(any("*" in path for path in value["allowed_paths"]))
        self.assertFalse(
            any(path.startswith(".github/") for path in value["allowed_paths"])
        )
        self.assertEqual(
            sum(path.startswith("scripts/") for path in value["allowed_paths"]),
            3,
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
