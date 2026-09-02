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
        self.assertEqual(value["task_id"], "P9-02")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(value["status"], "IN_PROGRESS_P9_02D_FINAL_GATE_AUTHORIZED")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P9-03")
        self.assertEqual(
            value["requirement_ids"],
            [
                "FR-SG-008",
                "FR-SG-009",
                "FR-CO-005",
                "FR-CO-007",
                "FR-RP-001",
                "FR-RP-002",
                "FR-RP-003",
                "FR-RP-004",
                "FR-RP-005",
                "FR-RP-006",
                "FR-RP-007",
                "INT-014",
            ],
        )
        self.assertEqual(
            value["base_checkpoint"],
            "ea6112fa04e08cee6920407df426efc685cea98b",
        )
        self.assertEqual(
            value["predecessor_product_checkpoint"],
            "a439043f96976c562edb8d4af69d51c709390043",
        )
        self.assertEqual(
            value["expected_state"],
            {
                "phase_status_current_task": "P9-02",
                "phase_status_execution_hold": "NONE",
                "phase_status_resumed_product_task": "P9-02",
                "active_goal_marker": "P9-02",
                "next_action_marker": "P9-02",
                "controller_marker": "P9-02C frontend candidate; P9-02D final gate pending",
            },
        )
        for invariant in (
            "CI_OPT_02_EXACT_SHA_EA6112FA_ORDINARY_33659491378_AND_LEVEL3_33660141866_PASS",
            "P9_02_PRODUCT_CODE_HELD_UNTIL_AUDIT_PLAN_EXACT_SHA_ORDINARY_PASS",
            "EVERY_CROSS_OBJECT_QUERY_IS_SERVER_SIDE_PERMISSION_FILTERED_AND_DETERMINISTICALLY_PAGED",
            "MISSING_STALE_PARTIAL_OR_UNAVAILABLE_ERP_TRUTH_NEVER_BECOMES_ZERO_HEALTHY_OR_SUCCESSFUL",
            "KPI_NAME_NUMERATOR_DENOMINATOR_SOURCE_TIMEZONE_AND_AVAILABILITY_ARE_FIXED_BEFORE_CALCULATION",
            "BI_DIRECTION_IS_READ_ONLY_WITH_NO_REVERSE_WRITE_OR_PRODUCTION_ETL_IN_P9_02",
            "ADMIN_CONFIGURATION_REUSES_OPERATION_SPECIFIC_VERSIONED_AUDITED_COMMANDS_NO_GENERIC_WRITER",
            "FR_CO_003_FR_CO_004_EXTERNAL_PORTALS_USER_APPROVED_POST_V1_2_DEFERRED",
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_REMAINS_REQUIRED_BEFORE_RELEASE_CLOSEOUT",
            "NO_PRODUCTION_ERPNEXT_CONTACT_DURING_P9_02_AUDIT_PLAN_TRANSITION",
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
                "implementation/evidence/delivery-pipeline-optimization-2/validation.md",
                "implementation/evidence/phase-9/p9-02-plan.md",
                "implementation/evidence/phase-9/p9-02-backend-validation.md",
                "contracts/data-ownership.yaml",
                "contracts/npi-api.openapi.yaml",
                "apps/npi_core/npi_core/bff.py",
                "apps/npi_core/npi_core/foundation/errors.py",
                "apps/npi_core/npi_core/request_security.py",
                "apps/npi_core/npi_core/project/domain.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_project_reference/npi_project_reference.json",
                "apps/npi_core/npi_core/reporting/__init__.py",
                "apps/npi_core/npi_core/reporting/domain.py",
                "apps/npi_core/npi_core/reporting/frappe_repository.py",
                "apps/npi_core/npi_core/reporting_api.py",
                "apps/npi_core/npi_core/collaboration/__init__.py",
                "apps/npi_core/npi_core/collaboration/domain.py",
                "apps/npi_core/npi_core/collaboration/frappe_validation.py",
                "apps/npi_core/npi_core/collaboration/frappe_repository.py",
                "apps/npi_core/npi_core/collaboration_api.py",
                "apps/npi_core/npi_core/hooks.py",
                "apps/npi_core/npi_core/project_work/frappe_repository.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_meeting_minute/__init__.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_meeting_minute/npi_meeting_minute.json",
                "apps/npi_core/npi_core/npi_core/doctype/npi_meeting_minute/npi_meeting_minute.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_meeting_work_link/__init__.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_meeting_work_link/npi_meeting_work_link.json",
                "apps/npi_core/npi_core/npi_core/doctype/npi_meeting_work_link/npi_meeting_work_link.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_collaboration_idempotency/__init__.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_collaboration_idempotency/npi_collaboration_idempotency.json",
                "apps/npi_core/npi_core/npi_core/doctype/npi_collaboration_idempotency/npi_collaboration_idempotency.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_internal_notification/__init__.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_internal_notification/npi_internal_notification.json",
                "apps/npi_core/npi_core/npi_core/doctype/npi_internal_notification/npi_internal_notification.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_notification_preference/__init__.py",
                "apps/npi_core/npi_core/npi_core/doctype/npi_notification_preference/npi_notification_preference.json",
                "apps/npi_core/npi_core/npi_core/doctype/npi_notification_preference/npi_notification_preference.py",
                "apps/npi_core/npi_core/translations/zh.csv",
                "apps/npi_core/npi_core/translations/zh-TW.csv",
                "frontend/src/domain/view-models.ts",
                "frontend/src/generated/catalogs.ts",
                "frontend/src/app/router.ts",
                "frontend/src/app/app.tsx",
                "frontend/src/app/app-shell.tsx",
                "frontend/src/api/reporting-data-source.ts",
                "frontend/src/api/collaboration-data-source.ts",
                "frontend/src/components/global-search-panel.tsx",
                "frontend/src/components/notification-center.tsx",
                "frontend/src/pages/portfolio-page.tsx",
                "frontend/src/pages/project-page.tsx",
                "frontend/src/pages/project-workspace.tsx",
                "frontend/src/pages/project-meeting-workspace.tsx",
                "frontend/src/styles/app.css",
                "frontend/tests/support/reporting-fixture.ts",
                "frontend/tests/support/collaboration-fixture.ts",
                "frontend/tests/unit/reporting-data-source.test.ts",
                "frontend/tests/unit/collaboration-data-source.test.ts",
                "frontend/tests/unit/portfolio-page.test.tsx",
                "frontend/tests/unit/project-meeting-workspace.test.tsx",
                "frontend/tests/unit/pages-and-shell.test.tsx",
                "frontend/tests/unit/project-page.test.tsx",
                "frontend/tests/unit/project-workspace.test.tsx",
                "frontend/tests/unit/router.test.tsx",
                "frontend/tests/e2e/p9-02-reporting-collaboration-live.spec.ts",
                "frontend/tests/e2e/p9-02-reporting-collaboration-live.spec.ts-snapshots/p9-02-portfolio-en-1366x768-100-darwin.png",
                "frontend/tests/e2e/p9-02-reporting-collaboration-live.spec.ts-snapshots/p9-02-portfolio-zh-1440x900-125-darwin.png",
                "frontend/tests/e2e/p9-02-reporting-collaboration-live.spec.ts-snapshots/p9-02-portfolio-zh-TW-1920x1080-150-darwin.png",
                "tests/test_phase9_reporting_api.py",
                "tests/test_phase9_reporting_contract.py",
                "tests/test_phase9_reporting_domain.py",
                "tests/test_phase9_reporting_repository.py",
                "tests/test_phase9_collaboration_domain.py",
                "tests/test_phase9_collaboration_repository.py",
                "tests/test_phase9_collaboration_api.py",
                "tests/test_phase9_collaboration_metadata.py",
                "tests/test_phase4_project_domain.py",
                "tests/test_phase4_project_contract.py",
                "tests/test_phase4_project_metadata.py",
                "tests/test_current_task_verifier.py",
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
                ["implementation/evidence/phase-9/p9-02-plan.md"],
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
