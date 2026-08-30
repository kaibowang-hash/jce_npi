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
        self.assertEqual(
            value["task_id"], "P8-07F-CURRENT-RUNTIME-GOVERNANCE"
        )
        self.assertEqual(value["task_kind"], "delivery_infrastructure")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P8-07F-FACTS")
        self.assertIn(
            "P8_07F_ACCEPTED_FACTS_EXACT_SHA_CFD0930553FC40029D18518A8E3CD3481FA0A5D8_ORDINARY_33299326296_PASSED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_CURRENT_RUNTIME_GOVERNANCE_ZERO_SSH_ZERO_CONNECTOR_ZERO_SITE_ZERO_EXTERNAL_STATE",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_FACTS_EXPANSION_REQUIRES_THIS_TRANSITION_EXACT_SHA_ORDINARY_AND_LEVEL_3_PASS",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_CURRENT_TRACKED_WORKTREE_IS_AUTHORIZED_CANDIDATE_CURRENT_SOURCE_TRUTH_WITH_HEAD_AND_DIFF_PROVENANCE",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_TWO_STOPPED_RELEVANT_DOCTYPE_CANDIDATES_AUTHORIZED_FOR_READ_ONLY_STRUCTURAL_SUMMARY_NO_RAW_PERSISTENCE",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_RUNTIME_METADATA_AUTHORIZED_ONLY_THROUGH_FIXED_APPLICATION_LAYER_READ_OPERATIONS",
            value["frozen_invariants"],
        )
        self.assertIn(
            "NO_DIRECT_SQL_BENCH_CONSOLE_GENERIC_METHOD_CALLER_SELECTED_DOCTYPE_FIELDS_FILTERS_ORDER_OR_PAGINATION",
            value["frozen_invariants"],
        )
        self.assertIn(
            "CURRENT_SOURCE_OPERATION_REJECTS_SYMLINK_BINARY_MULTI_PATH_DELETE_TRUNCATED_MALFORMED_OR_OVERSIZE_INPUT",
            value["frozen_invariants"],
        )
        self.assertIn(
            "RUNTIME_METADATA_OUTPUT_EXCLUDES_SCRIPT_TEXT_ENDPOINT_HEADERS_PRINCIPALS_SECRETS_AND_BUSINESS_ROWS",
            value["frozen_invariants"],
        )
        self.assertIn(
            "JCE_CORE_FIXED_TRANSPORT_REDACTION_PROVENANCE_CHECKSUM_BOUNDED_OUTPUT_AND_FAIL_CLOSED_STOPS_RETAINED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_BLOCKS_COMPLETION_ON_UNRESOLVED_DRIFT",
            value["frozen_invariants"],
        )
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_AWAITING_EXACT_SHA_ORDINARY_AND_LEVEL_3",
        )
        self.assertEqual(value["requirement_ids"], [])
        self.assertIn(
            "AGENTS.md",
            value["allowed_paths"],
        )
        self.assertIn(
            "implementation/evidence/phase-8/p8-07f-current-runtime-governance-transition.md",
            value["allowed_paths"],
        )
        self.assertEqual(
            value["base_checkpoint"],
            "cfd0930553fc40029d18518a8e3cd3481fa0a5d8",
        )
        self.assertEqual(len(value["allowed_paths"]), 17)
        self.assertEqual(
            set(value["allowed_paths"]),
            {
                "AGENTS.md",
                "implementation/ACTIVE_EXECUTION_GOAL.md",
                "implementation/AUTOPILOT_CONTROLLER.md",
                "implementation/BLOCKERS.md",
                "implementation/CURRENT_TASK.json",
                "implementation/NEXT_ACTION.md",
                "implementation/PHASE_STATUS.yaml",
                "implementation/QUALITY_GATE.md",
                "implementation/REQUIRED_INPUTS.md",
                "implementation/REQUIREMENT_TRACEABILITY.csv",
                "implementation/RISK_REGISTER.md",
                "implementation/evidence/phase-8/p8-07f-current-runtime-governance-transition.md",
                "implementation/evidence/phase-8/p8-07f-production-fact-reconciliation-plan.md",
                "scripts/reconcile_v1_2_traceability.py",
                "scripts/verify_v1_2_reconciliation.py",
                "tests/test_current_task_verifier.py",
                "tests/test_v1_2_reconciliation.py",
            },
        )
        self.assertNotIn("implementation/backlog.yaml", value["allowed_paths"])
        self.assertFalse(any("*" in path for path in value["allowed_paths"]))
        self.assertFalse(
            any(
                path.startswith(("apps/", "frontend/", "contracts/", ".github/"))
                for path in value["allowed_paths"]
            )
        )
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
