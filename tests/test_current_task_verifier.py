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
        self.assertEqual(value["task_id"], "P8-07F-FACTS")
        self.assertEqual(value["task_kind"], "delivery_infrastructure")
        self.assertEqual(value["completion_gate"], "LEVEL_3")
        self.assertEqual(value["authorized_next_task"], "P8-08")
        self.assertIn(
            "P8_07F_CURRENT_RUNTIME_GOVERNANCE_FCCF62FE_ORDINARY_33304191319_LEVEL_3_33304710306_PASSED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_CURRENT_RUNTIME_GOVERNANCE_ZERO_SSH_ZERO_CONNECTOR_ZERO_SITE_ZERO_EXTERNAL_STATE",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_FACTS_EXPANDED_ACTIVATION_C879FBCE_ORDINARY_33306873040_AND_PARENT_REPAIR_085E9124_ORDINARY_33307715636_PASSED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "P8_07F_REMAINING_CONNECTION_REQUIRES_FIXED_SITE_FACT_COLLECTOR_EXACT_SHA_ORDINARY_PASS",
            value["frozen_invariants"],
        )
        self.assertIn(
            "CURRENT_FILE_OPERATION_REQUIRES_CACHED_EXACT_TRACKED_PATH_SAFE_MODE_HEAD_AND_CURRENT_GIT_OBJECT_SINGLE_FILE_DIFF_AND_PRIVATE_RECONSTRUCTION",
            value["frozen_invariants"],
        )
        self.assertIn(
            "CURRENT_SOURCE_OPERATION_REJECTS_SYMLINK_BINARY_RENAME_COPY_MODE_CHANGE_MULTI_PATH_DELETE_TRUNCATED_MALFORMED_OR_OVERSIZE_INPUT",
            value["frozen_invariants"],
        )
        self.assertIn(
            "FIXED_RUNTIME_METADATA_FAMILIES_ONLY_NO_CALLER_SELECTED_METHOD_DOCTYPE_FIELDS_FILTERS_ORDER_OR_PAGINATION",
            value["frozen_invariants"],
        )
        self.assertIn(
            "RUNTIME_METADATA_USES_FRAPPE_APPLICATION_LAYER_GET_LIST_EXACT_JSON_PAGE_200_MAX_25_AND_FAIL_CLOSED_SHAPE",
            value["frozen_invariants"],
        )
        self.assertIn(
            "RUNTIME_METADATA_OUTPUT_EXCLUDES_SCRIPT_TEXT_ENDPOINT_HEADERS_PRINCIPALS_SECRETS_AND_BUSINESS_ROWS",
            value["frozen_invariants"],
        )
        self.assertIn(
            "FIXED_SITE_FACT_FAMILIES_SYSTEM_LOCALE_AND_FILE_URL_SHAPES_USE_ONLY_FRAPPE_GET_VALUE_AND_GET_COUNT",
            value["frozen_invariants"],
        )
        self.assertIn(
            "CLIENT_SCRIPT_V15_FIELDS_EXCLUDE_NONEXISTENT_SCRIPT_TYPE_AND_HASH_SCRIPT_TEXT",
            value["frozen_invariants"],
        )
        self.assertIn(
            "PROTECTED_MULTILINE_DOCTYPE_JSON_SCALARS_ARE_HASHED_NOT_EMITTED",
            value["frozen_invariants"],
        )
        self.assertIn(
            "USER_EXPANDED_RUNTIME_READ_AUTHORITY_DOES_NOT_REQUIRE_SQL_CONSOLE_OR_GENERIC_EXECUTE",
            value["frozen_invariants"],
        )
        self.assertIn(
            "ALL_PRODUCTION_READS_USE_FIXED_TRANSPORT_REMOTE_ALLOWLIST_REDACTION_PROVENANCE_CHECKSUM_BOUNDED_OUTPUT_AND_FAIL_CLOSED_STOPS",
            value["frozen_invariants"],
        )
        self.assertIn(
            "FINAL_FULL_PRODUCTION_ERPNEXT_LAUNCHFLOW_READ_ONLY_RECONCILIATION_BLOCKS_COMPLETION_ON_UNRESOLVED_DRIFT",
            value["frozen_invariants"],
        )
        self.assertEqual(
            value["status"],
            "IN_PROGRESS_AWAITING_FIXED_SITE_FACT_COLLECTOR_EXACT_SHA_ORDINARY_THEN_REMAINING_COLLECTION",
        )
        self.assertEqual(value["requirement_ids"], [])
        self.assertIn(
            "scripts/collect_erpnext_production_facts.py",
            value["allowed_paths"],
        )
        self.assertIn(
            "implementation/evidence/phase-8/p8-07f-current-runtime-governance-transition.md",
            value["allowed_paths"],
        )
        self.assertEqual(
            value["base_checkpoint"],
            "fccf62feaba2d3ed092efcd06174f16f66193540",
        )
        self.assertEqual(len(value["allowed_paths"]), 28)
        self.assertEqual(
            set(value["allowed_paths"]),
            {
                "docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md",
                "docs/ERPNEXT_PRODUCTION_FACT_INVENTORY.md",
                "docs/LAUNCHFLOW_ERPNEXT_INTEGRATION_BLUEPRINT.md",
                "docs/LAUNCHFLOW_ERPNEXT_COMPATIBILITY_GAP_DECISIONS.md",
                "docs/specification/SPEC_INDEX.md",
                "implementation/ACTIVE_EXECUTION_GOAL.md",
                "implementation/AUTOPILOT_CONTROLLER.md",
                "implementation/BLOCKERS.md",
                "implementation/CURRENT_TASK.json",
                "implementation/DECISION_LOG.md",
                "implementation/NEXT_ACTION.md",
                "implementation/PHASE_STATUS.yaml",
                "implementation/QUALITY_GATE.md",
                "implementation/REQUIRED_INPUTS.md",
                "implementation/REQUIREMENT_TRACEABILITY.csv",
                "implementation/RISK_REGISTER.md",
                "implementation/ROADMAP.md",
                "implementation/phase-8-requirement-anchor.md",
                "implementation/evidence/phase-8/p8-07-production-fact-governance-transition.md",
                "implementation/evidence/phase-8/p8-07f-current-runtime-governance-transition.md",
                "implementation/evidence/phase-8/p8-07f-production-fact-reconciliation-plan.md",
                "implementation/evidence/phase-8/p8-07f-production-fact-reconciliation-validation.md",
                "scripts/collect_erpnext_production_facts.py",
                "scripts/reconcile_v1_2_traceability.py",
                "scripts/verify_v1_2_reconciliation.py",
                "tests/test_erpnext_production_fact_collector.py",
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
                "tests.test_erpnext_production_fact_collector",
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
