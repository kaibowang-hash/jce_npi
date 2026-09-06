from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
QUALITY_VALIDATION = (
    ROOT / "apps/npi_core/npi_core/trial/quality_metadata_validation.py"
).read_text(encoding="utf-8")

APPEND_PERMISSIONS = [
    {
        "role": "System Manager",
        "read": 1,
        "write": 0,
        "create": 1,
        "delete": 0,
        "export": 0,
        "print": 0,
        "email": 0,
    },
    {
        "role": "NPI API User",
        "read": 0,
        "write": 0,
        "create": 1,
        "delete": 0,
        "export": 0,
        "print": 0,
        "email": 0,
    },
]


class Phase7TrialQualityMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_trial_cavity_result_revision": {
            "global_id", "cavity_result_global_id", "version_key_hash", "tenant_id",
            "project_global_id", "trial_round", "trial_round_global_id",
            "input_lock_revision", "input_lock_revision_global_id",
            "input_lock_revision_snapshot_hash", "sample_batch_revision",
            "sample_batch_revision_global_id", "sample_batch_revision_snapshot_hash",
            "tooling_revision", "tooling_revision_global_id",
            "tooling_revision_snapshot_hash", "tooling_set", "tooling_set_global_id",
            "tooling_set_snapshot_hash", "cavity_global_id", "result_version",
            "predecessor_global_id", "predecessor_snapshot_hash",
            "measurement_snapshot", "evidence_snapshot", "reason",
            "created_by_user_id", "created_at", "request_id", "trace_id",
            "cavity_result_snapshot", "snapshot_hash",
        },
        "npi_trial_defect_revision": {
            "global_id", "defect_global_id", "version_key_hash", "tenant_id",
            "project_global_id", "tooling_master", "tooling_master_global_id",
            "trial_round", "trial_round_global_id", "trial_round_optimistic_version",
            "trial_round_snapshot_hash", "input_lock_revision",
            "input_lock_revision_global_id", "input_lock_revision_snapshot_hash",
            "tooling_revision", "tooling_revision_global_id",
            "tooling_revision_snapshot_hash", "tooling_set", "tooling_set_global_id",
            "tooling_set_snapshot_hash", "cavity_global_id", "sample_batch_revision",
            "sample_batch_revision_global_id", "sample_batch_revision_snapshot_hash",
            "defect_version", "predecessor_kind", "predecessor_global_id",
            "predecessor_snapshot_hash", "business_code", "title", "description",
            "category_key", "location", "severity", "blocking", "state",
            "root_cause_state", "root_cause", "responsible_member",
            "responsible_member_global_id", "occurrence_count", "action_snapshot",
            "evidence_snapshot", "external_effect_snapshot", "reason",
            "created_by_user_id", "created_at", "request_id", "trace_id",
            "trial_defect_snapshot", "snapshot_hash",
        },
        "npi_trial_defect_verification_revision": {
            "global_id", "verification_global_id", "version_key_hash",
            "attempt_sequence", "tenant_id", "project_global_id", "defect_global_id",
            "defect_revision", "defect_revision_global_id",
            "defect_revision_snapshot_hash", "action_global_id", "target_round",
            "target_round_global_id", "target_round_optimistic_version",
            "target_round_snapshot_hash", "verification_round",
            "verification_round_global_id", "verification_round_optimistic_version",
            "verification_round_snapshot_hash", "cavity_result_revision",
            "cavity_result_revision_global_id", "cavity_result_revision_snapshot_hash",
            "verifier_member", "verifier_member_global_id", "result", "finding",
            "observed_at", "evidence_snapshot", "created_by_user_id", "created_at",
            "request_id", "trace_id", "verification_snapshot", "snapshot_hash",
        },
    }

    @staticmethod
    def load(folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            field["fieldname"]: field
            for field in metadata["fields"]  # type: ignore[index]
        }

    def test_exact_three_additive_objects_are_append_only(self) -> None:
        for folder, expected_fields in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                fields = self.fields(metadata)
                self.assertEqual(set(fields), expected_fields)
                self.assertEqual(metadata.get("read_only"), 1)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertEqual(metadata.get("permissions"), APPEND_PERMISSIONS)
                self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                controller = (
                    DOCTYPE_ROOT / folder / f"{folder}.py"
                ).read_text(encoding="utf-8")
                self.assertIn("require_trial_command_write()", controller)
                self.assertIn("deny_trial_history_update()", controller)
                self.assertIn("deny_trial_history_delete(self)", controller)

    def test_metadata_keeps_exact_parent_hashes_and_independent_verifier(self) -> None:
        for marker in (
            '"NPI Trial Input Lock Revision"',
            '"NPI Trial Sample Batch Revision"',
            '"NPI Tooling Revision"',
            '"NPI Tooling Set"',
            '"NPI Trial Evidence Reference"',
            '"NPI Tooling Defect Revision"',
            '"NPI Trial Defect Revision"',
            '"NPI Trial Defect Verification Revision"',
            "validate_trial_defect_verification(defect, cavity_result, value)",
            '"current_state": "running"',
            '"result": "pass"',
        ):
            self.assertIn(marker, QUALITY_VALIDATION)
        self.assertIn("SINGLE_LOGICAL_DEFECT_NO_FORK", (
            ROOT / "contracts/data-ownership.yaml"
        ).read_text(encoding="utf-8"))

    def test_cross_round_defect_keeps_predecessor_evidence_exact(self) -> None:
        start = QUALITY_VALIDATION.index("def validate_trial_defect_document")
        end = QUALITY_VALIDATION.index("def normalize_verification_identity", start)
        defect_validation = QUALITY_VALIDATION[start:end]
        predecessor = defect_validation.index("predecessor = require_exact_parent")
        evidence = defect_validation.index("_require_quality_evidence(", predecessor)
        self.assertLess(predecessor, evidence)
        self.assertIn(
            "if isinstance(predecessor_value, TrialDefectRevision)",
            defect_validation,
        )
        self.assertIn(
            "if retained_evidence.get(item.global_id) != item.snapshot_hash:\n"
            '            filters["trial_round_global_id"] = str(round_global_id)',
            QUALITY_VALIDATION,
        )

    def test_metadata_does_not_create_external_or_approval_truth(self) -> None:
        serialized = json.dumps(
            [self.load(folder) for folder in self.FIELDS],
            sort_keys=True,
        ).casefold()
        for forbidden in (
            "ncr_global_id",
            "quality_inspection_id",
            "gate_result",
            "tooling_lifecycle_state",
            "work_item_state",
            "approved_result",
            "file_url",
            "erpnext_endpoint",
            "credential",
            "secret",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
