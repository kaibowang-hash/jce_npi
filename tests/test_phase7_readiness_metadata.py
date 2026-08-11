from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase7ReadinessMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_readiness_template",
        "npi_readiness_template_version",
        "npi_readiness_instance_revision",
        "npi_readiness_command_idempotency",
    )

    def load(self, folder: str) -> dict[str, object]:
        return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["fieldname"]: item for item in metadata["fields"]}

    def test_four_additive_doctypes_are_guarded_and_have_no_fixture_rows(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata["autoname"], "field:global_id")
                self.assertNotIn("fixtures", metadata)
                self.assertEqual(metadata["permissions"][0]["role"], "System Manager")
                self.assertEqual(metadata["permissions"][1]["role"], "NPI API User")
                self.assertEqual(metadata["permissions"][0].get("delete"), 0)
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
                self.assertIn("require_readiness_command_write()", source)
                self.assertIn("deny_readiness_history_delete(self)", source)
                ast.parse(source)

    def test_template_version_is_exact_and_published_history_is_immutable(self) -> None:
        fields = self.fields(self.load("npi_readiness_template_version"))
        for name in (
            "template_global_id",
            "template_version",
            "version_key_hash",
            "optimistic_version",
            "publication_state",
            "applicability_snapshot",
            "category_snapshot",
            "item_snapshot",
            "template_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        self.assertEqual(fields["global_id"].get("unique"), 1)
        self.assertEqual(fields["version_key_hash"].get("unique"), 1)
        source = (
            DOCTYPE_ROOT
            / "npi_readiness_template_version"
            / "npi_readiness_template_version.py"
        ).read_text(encoding="utf-8")
        self.assertIn('str(previous.publication_state) == "published"', source)
        self.assertIn("deny_readiness_history_update()", source)

    def test_instance_is_append_only_and_persists_derived_evaluation_not_score_fields(self) -> None:
        metadata = self.load("npi_readiness_instance_revision")
        fields = self.fields(metadata)
        for name in (
            "instance_global_id",
            "version_key_hash",
            "project_optimistic_version",
            "project_snapshot_hash",
            "template_revision_global_id",
            "template_version",
            "template_snapshot_hash",
            "instance_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "category_snapshot",
            "item_snapshot",
            "evaluation_snapshot",
            "instance_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        for forbidden in (
            "caller_score",
            "readiness_percentage",
            "gate_state",
            "gate_decision",
            "erp_quality_result",
            "run_at_rate_result",
        ):
            self.assertNotIn(forbidden, fields)
        self.assertEqual(metadata["permissions"][0].get("write"), 0)
        self.assertEqual(metadata["permissions"][1].get("write"), 0)

    def test_receipt_vocabulary_is_closed_without_activated_routes(self) -> None:
        fields = self.fields(self.load("npi_readiness_command_idempotency"))
        operations = str(fields["operation"]["options"]).splitlines()
        targets = str(fields["target_object_type"]["options"]).splitlines()
        self.assertEqual(
            operations,
            [
                "readiness_template.create",
                "readiness_template.edit",
                "readiness_template.publish",
                "readiness_instance.initialize",
                "readiness_instance.revise",
            ],
        )
        self.assertEqual(
            [value for value in targets if value],
            ["readiness_template", "readiness_template_version", "readiness_instance_revision"],
        )
        self.assertFalse((ROOT / "apps/npi_core/npi_core/readiness_api.py").exists())

    def test_metadata_validation_replays_exact_domain_snapshots(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/readiness/metadata_validation.py").read_text(encoding="utf-8")
        self.assertIn("template_from_snapshot", source)
        self.assertIn("instance_from_snapshot", source)
        self.assertIn("value.evaluation.snapshot_payload()", source)
        self.assertNotIn("insert_default", source)
        ast.parse(source)

    def test_new_metadata_sources_have_direct_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Select":
                    sources.update(value for value in str(field.get("options", "")).splitlines() if value)
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
                f"missing {language} readiness metadata translations",
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
                    self.assertIn(field.get("options"), doctype_names)


if __name__ == "__main__":
    unittest.main()
