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
        self.assertEqual(value["task_id"], "P8-07")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P8-08")
        self.assertIn(
            "P8_07_AUDIT_PLAN_EXACT_SHA_2E573FA1757F7D9306F17BB47CB62C59E8493B7F_ORDINARY_33139628396_PASSED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07_CHECKPOINT_1_EXACT_SHA_D45D1D560FEDFED9D9791A5C08CCF9C1402F7EF8_ORDINARY_33142594763_PASSED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07_CHECKPOINT_2_EXACT_SHA_F7CF7C7EA490C10ACFC044AAEF236945E5118F01_ORDINARY_33187660221_PASSED",
            value["frozen_invariants"],
        )
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_CHECKPOINT_3_AWAITING_PRODUCT_CI",
        )
        self.assertIn(
            "P8_06_LEVEL_3_EXACT_SHA_547421A059911DF6AEB90BBBF06E837F77A3E5E0_ORDINARY_33131533806_FINAL_33132296565_PASSED",
            value["frozen_invariants"],
        )
        self.assertEqual(
            value["requirement_ids"],
            ["FR-RP-009", "UX-016", "NFR-INT-001"],
        )
        self.assertIn(
            "apps/npi_integration/npi_integration/integration_operations/**",
            value["allowed_paths"],
        )
        self.assertIn(
            "implementation/evidence/phase-8/p8-07-*.md",
            value["allowed_paths"],
        )
        self.assertIn(
            "PRODUCTION_READ_ONLY_FACT_CHECK_REMAINS_QUEUED_NOT_EFFECTIVE_AND_CONTACT_PROHIBITED",
            value["frozen_invariants"],
        )
        self.assertEqual(
            value["base_checkpoint"],
            "6a82568329e2ec46eae02df76a9d697e26cdf61e",
        )
        self.assertIn(
            "LOGICAL_DLQ_IS_A_DERIVED_CLASSIFICATION_NOT_A_SECOND_MUTABLE_COPY_OF_BUSINESS_TRUTH",
            value["frozen_invariants"],
        )
        self.assertEqual(len(value["allowed_paths"]), 74)
        self.assertIn(".gitleaksignore", value["allowed_paths"])
        self.assertIn("scripts/verify_devcontainer.py", value["allowed_paths"])
        self.assertIn("tests/test_devcontainer_verifier.py", value["allowed_paths"])
        self.assertIn(
            "apps/npi_integration/npi_integration/integration_operations/**",
            value["allowed_paths"],
        )
        self.assertIn(
            "frontend/src/pages/execution-page.tsx",
            value["allowed_paths"],
        )
        self.assertIn(
            "frontend/src/pages/execution-prototype-page.tsx",
            value["allowed_paths"],
        )
        self.assertIn("frontend/src/app/app-shell.tsx", value["allowed_paths"])
        self.assertIn("frontend/src/app/router.ts", value["allowed_paths"])
        self.assertIn(
            "frontend/tests/unit/pages-and-shell.test.tsx",
            value["allowed_paths"],
        )
        self.assertIn(
            "frontend/tests/unit/router.test.tsx",
            value["allowed_paths"],
        )
        self.assertIn(
            "implementation/evidence/phase-8/p8-07-*.md",
            value["allowed_paths"],
        )
        self.assertNotIn("implementation/backlog.yaml", value["allowed_paths"])
        self.assertTrue(
            any(path.startswith("apps/") for path in value["allowed_paths"])
        )
        self.assertTrue(
            any(path.startswith("frontend/") for path in value["allowed_paths"])
        )
        self.assertTrue(
            any(path.startswith("contracts/") for path in value["allowed_paths"])
        )
        self.assertFalse(any(path == "**" for path in value["allowed_paths"]))
        self.assertNotIn("apps/erpnext/**", value["allowed_paths"])
        affected_modules = {
            module
            for command in value["affected_checks"]["level_1"]
            for module in command
            if isinstance(module, str) and module.startswith("tests.")
        }
        self.assertEqual(
            affected_modules,
            {
                "tests.test_current_task_verifier",
                "tests.test_devcontainer_verifier",
                "tests.test_phase8_inbound_project_metadata",
                "tests.test_phase8_integration_operations_api",
                "tests.test_phase8_integration_operations_contract",
                "tests.test_phase8_integration_operations_domain",
                "tests.test_phase8_integration_operations_metadata",
                "tests.test_phase8_integration_operations_repository",
                "tests.test_phase8_integration_operations_security",
                "tests.test_phase8_item_publish_security",
                "tests.test_phase8_mbom_publish_security",
                "tests.test_phase8_tool_asset_security",
                "tests.test_v1_2_reconciliation",
            },
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
                ["scripts/verify_current_task.py"],
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
