from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
VALIDATION = ROOT / "apps/npi_core/npi_core/tooling/frappe_validation.py"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"

SYSTEM_MANAGER_ADMIN = {
    "role": "System Manager",
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "export": 0,
    "print": 0,
    "email": 0,
}
SYSTEM_MANAGER_APPEND = {**SYSTEM_MANAGER_ADMIN, "write": 0}
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


class Phase6ToolingMetadataTest(unittest.TestCase):
    FIELDS = {
        "npi_engineering_part": {
            "global_id", "tenant_id", "originating_project_global_id", "title",
            "current_revision_global_id", "current_revision_number",
            "current_revision_snapshot_hash", "optimistic_version",
        },
        "npi_engineering_part_revision": {
            "global_id", "engineering_part", "part_global_id", "tenant_id",
            "originating_project_global_id", "revision_number", "revision_key",
            "revision_label", "predecessor_global_id", "predecessor_snapshot_hash",
            "title", "reason", "created_by_user_id", "created_at", "request_id",
            "trace_id", "revision_snapshot", "snapshot_hash",
        },
        "npi_tooling_requirement": {
            "global_id", "tenant_id", "project_global_id", "requirement_kind",
            "title", "reason", "target_part_revision_global_id", "target_date",
            "created_by_user_id", "created_at", "request_id", "trace_id",
            "requirement_snapshot", "snapshot_hash",
        },
        "npi_tooling_master": {
            "global_id", "tenant_id", "originating_project_global_id", "title",
            "created_by_user_id", "created_at", "request_id", "trace_id",
            "master_snapshot", "snapshot_hash",
        },
        "npi_tooling_applicability": {
            "global_id", "relationship_global_id", "relationship_key_hash",
            "version_key", "tenant_id", "project_global_id",
            "tooling_master_global_id", "part_global_id",
            "part_revision_global_id", "product_source_system",
            "product_source_object_id", "model_source_system",
            "model_source_object_id", "applicability_version",
            "predecessor_global_id", "predecessor_snapshot_hash",
            "effective_from", "effective_to", "reason", "created_by_user_id",
            "created_at", "request_id", "trace_id", "applicability_snapshot",
            "snapshot_hash",
        },
        "npi_tooling_command_idempotency": {
            "global_id", "receipt_key", "tenant_id", "project_global_id",
            "actor_user_id", "operation", "idempotency_key_hash", "payload_hash",
            "target_object_type", "target_global_id", "response_payload",
            "response_hash", "sealed", "created_at", "updated_at",
        },
    }

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            field["fieldname"]: field
            for field in metadata["fields"]  # type: ignore[index]
        }

    def test_exact_additive_objects_and_fields(self) -> None:
        for folder, expected in self.FIELDS.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), expected)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)

    def test_history_objects_are_append_only_and_generic_export_is_denied(self) -> None:
        self.assertEqual(
            self.load("npi_engineering_part").get("permissions"),
            [SYSTEM_MANAGER_ADMIN],
        )
        for folder in (
            "npi_engineering_part_revision",
            "npi_tooling_requirement",
            "npi_tooling_master",
            "npi_tooling_applicability",
        ):
            metadata = self.load(folder)
            self.assertEqual(metadata.get("permissions"), [SYSTEM_MANAGER_APPEND, API_APPEND])
            self.assertEqual(metadata.get("read_only"), 1)
            self.assertTrue(
                all(field.get("read_only") == 1 for field in self.fields(metadata).values())
            )
        receipt = self.load("npi_tooling_command_idempotency")
        self.assertEqual(
            receipt.get("permissions"),
            [SYSTEM_MANAGER_ADMIN, {**API_APPEND, "write": 1}],
        )
        target_type = self.fields(receipt)["target_object_type"]
        self.assertEqual(
            str(target_type.get("options", "")).splitlines(),
            [
                "",
                "part",
                "part_revision",
                "tooling_requirement",
                "tooling_master",
                "tooling_applicability",
            ],
        )

    def test_metadata_does_not_invent_lifecycle_set_or_erp_truth(self) -> None:
        serialized = json.dumps(
            [self.load(folder) for folder in self.FIELDS],
            sort_keys=True,
        ).casefold()
        for forbidden in (
            "lifecycle_state", "asset_id", "asset_status", "set_count",
            "shot_count", "erpnext_endpoint", "credential", "secret",
            "approved", "released", "accepted",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("copy_or_additional_set", serialized)

    def test_applicability_is_versioned_effective_and_non_collapsing(self) -> None:
        fields = self.fields(self.load("npi_tooling_applicability"))
        for fieldname in (
            "relationship_global_id", "relationship_key_hash", "version_key",
            "tooling_master_global_id", "part_global_id",
            "part_revision_global_id", "applicability_version",
            "predecessor_global_id", "effective_from", "effective_to",
        ):
            self.assertIn(fieldname, fields)
        for fieldname in ("product_source_system", "model_source_system"):
            with self.subTest(fieldname=fieldname):
                self.assertEqual(
                    str(fields[fieldname].get("options", "")).splitlines(),
                    ["", "NPI_ONE", "ERPNEXT"],
                )
        self.assertNotIn("tooling_requirement_global_id", fields)
        self.assertNotIn("physical_set_count", fields)

    def test_all_controllers_require_closed_command_flag_and_deny_delete(self) -> None:
        validation = VALIDATION.read_text(encoding="utf-8")
        self.assertIn('TOOLING_COMMAND_WRITE_FLAG = "npi_tooling_command_write"', validation)
        self.assertIn("require_tooling_command_write", validation)
        self.assertIn("deny_tooling_history_delete", validation)
        for folder in self.FIELDS:
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
            self.assertIn("require_tooling_command_write()", source)
            self.assertIn("def on_trash", source)
            self.assertIn("deny_tooling_history_delete", source)

    def test_date_metadata_uses_the_shared_fail_closed_parser(self) -> None:
        for folder in ("npi_tooling_requirement", "npi_tooling_applicability"):
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
            self.assertIn("optional_date_text", source)
            self.assertNotIn("date.fromisoformat(str(self.", source)

    def test_part_projection_allows_revision_title_and_versions_pointer_once(self) -> None:
        source = (
            DOCTYPE_ROOT
            / "npi_engineering_part"
            / "npi_engineering_part.py"
        ).read_text(encoding="utf-8")
        identity = source.split("_IDENTITY_FIELDS = (", 1)[1].split(")\n", 1)[0]
        self.assertNotIn('"title"', identity)
        self.assertIn(
            'if previous.get("current_revision_global_id") in (None, "")',
            source,
        )
        self.assertIn("else previous_version + 1", source)
        self.assertIn(
            "self.current_revision_number != previous_number + 1",
            source,
        )

    def test_all_visible_sources_have_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        python_paths = [VALIDATION, VALIDATION.with_name("domain.py")]
        for folder in self.FIELDS:
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
            python_paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for path in python_paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    sources.add(node.args[0].value)
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
                f"missing {language} Tooling translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
