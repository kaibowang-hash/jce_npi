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
        self.assertEqual(value["task_id"], "P8-06")
        self.assertEqual(value["task_kind"], "product")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P8-07")
        self.assertIn(
            "P8_06_CHECKPOINT_3_PRODUCT_AUTHORIZED_ONLY_AFTER_THIS_TRANSITION_PASSES_EXACT_SHA_ORDINARY_CI",
            value["frozen_invariants"],
        )
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_CHECKPOINT_3_PRODUCT_AUTHORIZATION_TRANSITION",
        )
        self.assertIn(
            "P8_06_CHECKPOINT_2_EXACT_SHA_9983A8D0B6FF87D6BC8A9891C428F1790B83D91F_ORDINARY_32964612981_PASSED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_05_LEVEL_3_EXACT_SHA_F9C358018823F3AF20ACA38EFB53F8FCBD13D406_ORDINARY_32937395289_FINAL_32938622250_PASSED",
            value["frozen_invariants"],
        )
        self.assertEqual(value["requirement_ids"], ["INT-007", "FR-TR-006", "FR-NP-006"])
        self.assertIn(
            "implementation/evidence/phase-8/p8-06-domain-metadata-checkpoint.md",
            value["allowed_paths"],
        )
        self.assertIn(
            "P8_06_CHECKPOINT_3_IS_READ_ONLY_LINK_CURRENTNESS_AND_DRIFT_WITHOUT_A_NEW_ROUTE_OR_WRITE",
            value["frozen_invariants"],
        )
        self.assertEqual(len(value["allowed_paths"]), 20)
        self.assertIn(
            "apps/npi_integration/npi_integration/quality_link/domain.py",
            value["allowed_paths"],
        )
        self.assertIn(
            "apps/npi_integration/npi_integration/quality_link/frappe_repository.py",
            value["allowed_paths"],
        )
        self.assertIn(
            "apps/npi_integration/npi_integration/quality_link_api.py",
            value["allowed_paths"],
        )
        self.assertIn("contracts/npi-api.openapi.yaml", value["allowed_paths"])
        self.assertNotIn("apps/npi_core/npi_core/bff.py", value["allowed_paths"])
        self.assertNotIn(
            "apps/npi_core/npi_core/readiness/frappe_repository.py",
            value["allowed_paths"],
        )
        self.assertNotIn("implementation/backlog.yaml", value["allowed_paths"])
        self.assertNotIn("contracts/integration-event.schema.json", value["allowed_paths"])
        self.assertFalse(
            any(
                any(token in path for token in ("outbox", "worker.py", "adapters.py", "runtime"))
                for path in value["allowed_paths"]
            )
        )
        self.assertFalse(any("*" in path for path in value["allowed_paths"]))
        self.assertNotIn("apps/erpnext/**", value["allowed_paths"])
        affected_modules = {
            module
            for command in value["affected_checks"]["level_1"]
            for module in command
            if isinstance(module, str) and module.startswith("tests.")
        }
        self.assertIn(
            "tests.test_phase7_readiness_repository",
            affected_modules,
        )
        self.assertIn(
            "tests.test_phase7_readiness_repository_seams",
            affected_modules,
        )
        self.assertNotIn(
            "tests.test_phase7_readiness_source_resolver",
            affected_modules,
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
