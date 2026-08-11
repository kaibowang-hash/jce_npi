from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
SYSTEM_MANAGER_APPEND = {
    "role": "System Manager",
    "read": 1,
    "write": 0,
    "create": 1,
    "delete": 0,
    "export": 0,
    "print": 0,
    "email": 0,
}
API_APPEND = {
    "role": "NPI API User",
    "read": 0,
    "write": 0,
    "create": 1,
    "delete": 0,
    "export": 0,
    "print": 0,
    "email": 0,
}


class Phase7TrialReviewMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_trial_conclusion_policy_version",
        "npi_trial_round_comparison_snapshot",
        "npi_trial_review_reference_revision",
        "npi_trial_conclusion_revision",
    )

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["fieldname"]: item for item in metadata["fields"]}

    def test_four_additive_doctypes_are_append_only_and_have_no_fixture_rows(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata["autoname"], "field:global_id")
                self.assertEqual(metadata["read_only"], 1)
                self.assertEqual(
                    metadata["permissions"],
                    [SYSTEM_MANAGER_APPEND, API_APPEND],
                )
                self.assertTrue(
                    all(field.get("read_only") == 1 for field in metadata["fields"])
                )
                self.assertNotIn("fixtures", metadata)
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                    encoding="utf-8"
                )
                for marker in (
                    "canonical_trial_identity(self)",
                    "require_trial_command_write()",
                    "deny_trial_history_update()",
                    "deny_trial_history_delete(self)",
                ):
                    self.assertIn(marker, source)
                ast.parse(source)

    def test_policy_metadata_is_exact_versioned_and_does_not_seed_authority(self) -> None:
        metadata = self.load("npi_trial_conclusion_policy_version")
        fields = self.fields(metadata)
        for name in (
            "policy_global_id",
            "version_key_hash",
            "trial_plan_revision_global_id",
            "trial_plan_revision_snapshot_hash",
            "policy_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "required_parameter_snapshot",
            "required_dimension_snapshot",
            "required_reference_kind_snapshot",
            "authority_binding_snapshot",
            "policy_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        self.assertEqual(fields["version_key_hash"].get("unique"), 1)
        self.assertEqual(fields["global_id"].get("unique"), 1)
        source = (
            ROOT / "apps/npi_core/npi_core/trial/review_metadata_validation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("policy_from_snapshot", source)
        self.assertNotIn("insert_default_policy", source)

    def test_comparison_persists_only_exact_derived_snapshots(self) -> None:
        fields = self.fields(self.load("npi_trial_round_comparison_snapshot"))
        for name in (
            "policy_revision_global_id",
            "policy_revision_snapshot_hash",
            "source_snapshot",
            "input_comparison_snapshot",
            "metric_comparison_snapshot",
            "defect_trend_snapshot",
            "formal_erp_quality",
            "comparison_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        self.assertEqual(fields["formal_erp_quality"].get("options"), "unavailable")
        for forbidden in ("formal_quality_result", "yield_value", "cycle_time_value"):
            self.assertNotIn(forbidden, fields)

    def test_reference_binds_exact_product_tooling_set_and_file_without_approval(self) -> None:
        fields = self.fields(self.load("npi_trial_review_reference_revision"))
        for global_id_field, hash_field in (
            ("comparison_snapshot_global_id", "comparison_snapshot_hash"),
            ("part_revision_global_id", "part_revision_snapshot_hash"),
            ("tooling_revision_global_id", "tooling_revision_snapshot_hash"),
            ("tooling_set_global_id", "tooling_set_snapshot_hash"),
            ("file_revision_global_id", "file_revision_snapshot_hash"),
        ):
            self.assertIn(global_id_field, fields)
            self.assertIn(hash_field, fields)
        self.assertEqual(fields["approval_authority"].get("options"), "unavailable")
        self.assertNotIn("approved_by", fields)
        self.assertNotIn("customer_signature", fields)

    def test_conclusion_is_an_immutable_successor_with_proposal_only_effects(self) -> None:
        fields = self.fields(self.load("npi_trial_conclusion_revision"))
        for name in (
            "conclusion_global_id",
            "version_key_hash",
            "trial_round_optimistic_version",
            "trial_round_snapshot_hash",
            "conclusion_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "policy_revision_global_id",
            "policy_revision_snapshot_hash",
            "comparison_snapshot_global_id",
            "comparison_snapshot_hash",
            "review_reference_snapshot",
            "blocker_snapshot",
            "summary_input_snapshot",
            "proposed_next_work_snapshot",
            "external_effect_snapshot",
            "conclusion_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        for forbidden in (
            "gate_global_id",
            "work_item_global_id",
            "tooling_lifecycle_state",
            "formal_quality_result",
            "customer_signature",
        ):
            self.assertNotIn(forbidden, fields)

    def test_receipt_vocabulary_is_ready_but_routes_remain_absent(self) -> None:
        receipt = self.load("npi_trial_command_idempotency")
        fields = self.fields(receipt)
        operations = str(fields["operation"]["options"]).splitlines()
        targets = str(fields["target_object_type"]["options"]).splitlines()
        for operation in (
            "trial_round.begin_analysis",
            "trial_comparison.create",
            "trial_review_reference.create",
            "trial_review_reference.revise",
            "trial_conclusion.submit",
            "trial_conclusion.decide",
            "trial_conclusion.reopen",
        ):
            self.assertIn(operation, operations)
        for target in (
            "trial_round_lifecycle_event",
            "trial_round_comparison_snapshot",
            "trial_review_reference_revision",
            "trial_conclusion_revision",
        ):
            self.assertIn(target, targets)
        self.assertNotIn(
            "trial_conclusion_policy_version",
            targets,
            "Checkpoint 1 must not create a production policy command surface.",
        )

    def test_new_doctype_sources_have_direct_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Select":
                    sources.update(
                        option
                        for option in str(field.get("options", "")).splitlines()
                        if option
                    )
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(
                encoding="utf-8",
                newline="",
            ) as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} Trial review metadata translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_every_new_link_target_is_a_real_repository_doctype(self) -> None:
        doctype_names = {
            str(json.loads(path.read_text(encoding="utf-8"))["name"])
            for path in DOCTYPE_ROOT.glob("*/*.json")
        }
        for folder in self.FOLDERS:
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(
                        field.get("options"),
                        doctype_names,
                        f"unresolved Link target in {folder}.{field['fieldname']}",
                    )


if __name__ == "__main__":
    unittest.main()
