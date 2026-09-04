from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
FOLDER = "npi_released_trial_summary_revision"
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


class Phase7ReleasedTrialSummaryMetadataTest(unittest.TestCase):
    def load(self, folder: str = FOLDER) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["fieldname"]: item for item in metadata["fields"]}

    def test_additive_doctype_is_append_only_guarded_and_has_no_fixture_or_authority(self) -> None:
        metadata = self.load()
        self.assertEqual(metadata["autoname"], "field:global_id")
        self.assertEqual(metadata["read_only"], 1)
        self.assertEqual(metadata["permissions"], [SYSTEM_MANAGER_APPEND, API_APPEND])
        self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))
        self.assertNotIn("fixtures", metadata)
        source_path = DOCTYPE_ROOT / FOLDER / f"{FOLDER}.py"
        source = source_path.read_text(encoding="utf-8")
        for marker in (
            "canonical_trial_identity(self)",
            "require_trial_command_write()",
            "deny_trial_history_update()",
            "deny_trial_history_delete(self)",
            "validate_released_summary_document(self)",
        ):
            self.assertIn(marker, source)
        ast.parse(source)

    def test_metadata_freezes_exact_lineage_projection_redaction_and_hashes(self) -> None:
        fields = self.fields(self.load())
        for name in (
            "summary_global_id",
            "version_key_hash",
            "project_global_id",
            "trial_plan_global_id",
            "trial_round_global_id",
            "summary_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "trial_round_optimistic_version",
            "trial_round_snapshot_hash",
            "trial_plan_revision_global_id",
            "trial_plan_revision_snapshot_hash",
            "conclusion_revision_global_id",
            "conclusion_version",
            "conclusion_snapshot_hash",
            "source_manifest",
            "source_manifest_hash",
            "presentation_projection",
            "presentation_projection_hash",
            "redaction_manifest",
            "redaction_manifest_hash",
            "summary_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        self.assertEqual(fields["version_key_hash"].get("unique"), 1)
        self.assertEqual(fields["global_id"].get("unique"), 1)
        for forbidden in (
            "approved_by",
            "customer_signature",
            "external_event",
            "erpnext_id",
            "print_format",
            "retention_period",
        ):
            self.assertNotIn(forbidden, fields)

    def test_only_decided_states_and_existing_exact_link_targets_are_allowed(self) -> None:
        fields = self.fields(self.load())
        self.assertEqual(fields["conclusion_state"]["options"], "approved\nrejected")
        doctype_names = {
            str(json.loads(path.read_text(encoding="utf-8"))["name"])
            for path in DOCTYPE_ROOT.glob("*/*.json")
        }
        for field in fields.values():
            if field.get("fieldtype") == "Link":
                self.assertIn(field["options"], doctype_names)

    def test_existing_trial_receipt_adds_only_two_closed_summary_operations(self) -> None:
        receipt = self.load("npi_trial_command_idempotency")
        fields = self.fields(receipt)
        operations = str(fields["operation"]["options"]).splitlines()
        targets = str(fields["target_object_type"]["options"]).splitlines()
        self.assertIn("released_trial_summary.retain", operations)
        self.assertIn("released_trial_summary.revise", operations)
        self.assertIn("released_trial_summary_revision", targets)
        source = (
            DOCTYPE_ROOT
            / "npi_trial_command_idempotency"
            / "npi_trial_command_idempotency.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(source.count('"released_trial_summary_revision"'), 2)

    def test_metadata_sources_have_direct_symmetric_chinese_translations(self) -> None:
        metadata = self.load()
        sources = {str(metadata["name"])}
        sources.update(str(field["label"]) for field in metadata["fields"])
        sources.update(
            option
            for field in metadata["fields"]
            if field.get("fieldtype") == "Select"
            for option in str(field.get("options", "")).splitlines()
            if option
        )
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} Released Trial Summary metadata translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
