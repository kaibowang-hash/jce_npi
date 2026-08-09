from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
OBJECTS = (
    "npi_tooling_list_preference",
    "npi_tooling_export_package",
    "npi_tooling_export_command_idempotency",
)


def _load(folder: str) -> dict[str, object]:
    return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))


def _fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["fieldname"]: item for item in metadata["fields"]}  # type: ignore[index]


class Phase6ToolingExportMetadataTests(unittest.TestCase):
    def test_additive_objects_are_guarded_and_install_no_business_rows(self) -> None:
        for folder in OBJECTS:
            with self.subTest(folder=folder):
                metadata = _load(folder)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(all(item.get("read_only") == 1 for item in _fields(metadata).values()))
                for permission in metadata["permissions"]:  # type: ignore[index]
                    self.assertEqual(permission.get("delete"), 0)
                    self.assertEqual(permission.get("export"), 0)
                    self.assertEqual(permission.get("print"), 0)
                controller = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
                self.assertIn("require_tooling_export_write()", controller)
                self.assertIn("deny_tooling_export_delete", controller)

    def test_preference_and_receipt_have_narrow_mutation_models(self) -> None:
        preference = _fields(_load("npi_tooling_list_preference"))
        self.assertEqual(preference["grid_id"]["options"], "tooling-list")
        self.assertEqual(
            str(preference["view_id"]["options"]).splitlines(),
            [
                "all", "missing_applicability", "single_part", "shared_parts",
                "missing_physical_set", "single_physical_set", "multiple_physical_sets",
                "missing_design_revision", "has_design_revision", "customer_owned_set",
            ],
        )
        receipt = _fields(_load("npi_tooling_export_command_idempotency"))
        self.assertEqual(
            str(receipt["operation"]["options"]).splitlines(),
            ["tooling_export_package.create", "tooling_export_package.download"],
        )
        self.assertNotIn("idempotency_key", receipt)
        self.assertIn("idempotency_key_hash", receipt)
        controller = (
            DOCTYPE_ROOT
            / "npi_tooling_export_command_idempotency"
            / "npi_tooling_export_command_idempotency.py"
        ).read_text(encoding="utf-8")
        self.assertIn("previous.sealed", controller)
        self.assertIn("complete sealed response", controller)

    def test_package_metadata_is_private_immutable_bounded_and_url_free(self) -> None:
        fields = _fields(_load("npi_tooling_export_package"))
        self.assertEqual(fields["mime_type"]["label"], "Media Type")
        self.assertEqual(fields["frappe_file_id"]["options"], "File")
        self.assertNotIn("file_url", fields)
        controller = (
            DOCTYPE_ROOT / "npi_tooling_export_package" / "npi_tooling_export_package.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "MAX_TOOLING_EXPORT_OBJECTS",
            "TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY",
            "TOOLING_OBJECT_PACKAGE_MIME_TYPE",
            "validate_immutable_snapshot",
            "validate_package_expiry",
        ):
            self.assertIn(marker, controller)

    def test_checkpoint_one_adds_schemas_but_no_live_routes(self) -> None:
        openapi = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for schema in (
            "ToolingListViewId", "ToolingListFilterSnapshot", "ToolingListRow",
            "ToolingListPreferenceSnapshot", "ToolingExportRequest", "ToolingExportPackage",
        ):
            self.assertIn(f"    {schema}:\n", openapi)
        self.assertNotIn("  /projects/{projectGlobalId}/tooling-exports", openapi)
        self.assertNotIn("tooling-exports", bff)
        self.assertNotIn("tooling-list-preference", bff)
        for object_name in (
            "ToolingListPreference",
            "ToolingExportPackage",
            "ToolingExportCommandIdempotency",
        ):
            self.assertIn(f"  {object_name}:\n", ownership)
        self.assertIn("conflict: NEVER_INCLUDE_IN_PACKAGE", ownership)
        self.assertIn("conflict: ONE_WAY_SEAL", ownership)

    def test_all_visible_sources_have_direct_symmetric_translations(self) -> None:
        sources: set[str] = set()
        python_paths = [
            ROOT / "apps/npi_core/npi_core/tooling/export_domain.py",
            ROOT / "apps/npi_core/npi_core/tooling/export_rendering.py",
            ROOT / "apps/npi_core/npi_core/tooling/export_frappe_validation.py",
        ]
        for folder in OBJECTS:
            metadata = _load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(item["label"]) for item in metadata["fields"])  # type: ignore[index]
            sources.update(
                option
                for item in metadata["fields"]  # type: ignore[index]
                if item.get("fieldtype") == "Select"
                for option in str(item.get("options", "")).splitlines()
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
        rendering = ast.parse(python_paths[1].read_text(encoding="utf-8"))
        for node in ast.walk(rendering):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name)
                and target.id in {"CSV_SOURCE_STRINGS", "README_SOURCE_STRINGS"}
                for target in node.targets
            ):
                sources.update(
                    item.value
                    for item in node.value.elts  # type: ignore[union-attr]
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
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
                f"missing {language} P6-08 translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
