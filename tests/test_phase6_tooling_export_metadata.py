from __future__ import annotations

import ast
import csv
import importlib
import json
import sys
import types
import unittest
from datetime import UTC, datetime
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
            "require_datetime_snapshot_projection",
        ):
            self.assertIn(marker, controller)

    def test_preference_datetime_projection_compares_the_same_utc_instant(self) -> None:
        controller = (
            DOCTYPE_ROOT
            / "npi_tooling_list_preference"
            / "npi_tooling_list_preference.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(controller)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id
            in {"require_snapshot_projection", "require_datetime_snapshot_projection"}
        ]
        projections = {
            call.func.id: ast.unparse(call.args[2])
            for call in calls
            if len(call.args) == 3 and isinstance(call.func, ast.Name)
        }
        self.assertIn(
            "('last_changed_at', 'lastChangedAt')",
            projections["require_datetime_snapshot_projection"],
        )
        self.assertNotIn("last_changed_at", projections["require_snapshot_projection"])

    def test_package_create_diagnostic_stages_are_closed(self) -> None:
        validation = (
            ROOT / "apps/npi_core/npi_core/tooling/export_frappe_validation.py"
        ).read_text(encoding="utf-8")
        package = (
            DOCTYPE_ROOT
            / "npi_tooling_export_package"
            / "npi_tooling_export_package.py"
        ).read_text(encoding="utf-8")
        receipt = (
            DOCTYPE_ROOT
            / "npi_tooling_export_command_idempotency"
            / "npi_tooling_export_command_idempotency.py"
        ).read_text(encoding="utf-8")
        expected = {
            "P608_PACKAGE_COMMAND_CONTEXT",
            "P608_PACKAGE_RECEIPT_INSERT",
            "P608_PACKAGE_FILE_SAVE",
            "P608_PACKAGE_INSERT",
            "P608_PACKAGE_AUDIT_APPEND",
            "P608_PACKAGE_RECEIPT_SEAL",
            "P608_PACKAGE_TIME_PROJECTION",
            "P608_PACKAGE_EXPIRY",
            "P608_PACKAGE_PARENT",
            "P608_PACKAGE_RECEIPT_INITIAL_STATE",
            "P608_PACKAGE_RECEIPT_RESPONSE",
            "P608_PACKAGE_TRANSACTION_LIFECYCLE",
        }
        for code in expected:
            self.assertIn(code, validation)
        for code in (
            "P608_PACKAGE_TIME_PROJECTION",
            "P608_PACKAGE_EXPIRY",
            "P608_PACKAGE_PARENT",
        ):
            self.assertIn(code, package)
        for code in (
            "P608_PACKAGE_RECEIPT_INITIAL_STATE",
            "P608_PACKAGE_RECEIPT_RESPONSE",
        ):
            self.assertIn(code, receipt)
        self.assertIn("record_safe_diagnostic(", validation)
        self.assertNotIn("str(error)", validation)

    def test_package_datetime_projection_compares_the_same_utc_instant(self) -> None:
        module_names = (
            "frappe",
            "frappe.utils",
            "npi_core.documents.frappe_validation",
            "npi_core.tooling.export_frappe_validation",
        )
        saved = {name: sys.modules.get(name) for name in module_names}
        for name in module_names:
            sys.modules.pop(name, None)

        class ValidationError(Exception):
            pass

        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.PermissionError = PermissionError
        frappe.ValidationError = ValidationError
        frappe.parse_json = json.loads

        def throw(message: str, error_type: type[Exception]) -> None:
            raise error_type(message)

        frappe.throw = throw
        utils = types.ModuleType("frappe.utils")

        def get_datetime(value: object) -> datetime:
            if isinstance(value, datetime):
                return value
            text = str(value)
            return datetime.fromisoformat(
                text[:-1] + "+00:00" if text.endswith("Z") else text
            )

        utils.get_datetime = get_datetime
        sys.modules["frappe"] = frappe
        sys.modules["frappe.utils"] = utils
        try:
            validation = importlib.import_module(
                "npi_core.tooling.export_frappe_validation"
            )
            document = types.SimpleNamespace(
                generated_at="2026-08-10 04:05:06.000000",
                expires_at=datetime(2026, 8, 10, 5, 5, 6, tzinfo=UTC),
            )
            snapshot = {
                "generatedAt": "2026-08-10T04:05:06Z",
                "expiresAt": "2026-08-10T05:05:06Z",
            }
            validation.require_datetime_snapshot_projection(
                document,
                snapshot,
                (("generated_at", "generatedAt"), ("expires_at", "expiresAt")),
            )
            snapshot["expiresAt"] = "2026-08-10T05:05:07Z"
            with self.assertRaises(ValidationError):
                validation.require_datetime_snapshot_projection(
                    document,
                    snapshot,
                    (("generated_at", "generatedAt"), ("expires_at", "expiresAt")),
                )
        finally:
            for name in module_names:
                sys.modules.pop(name, None)
                if saved[name] is not None:
                    sys.modules[name] = saved[name]

    def test_checkpoint_two_exposes_only_the_four_fixed_live_routes(self) -> None:
        openapi = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for schema in (
            "ToolingListViewId", "ToolingListFilterSnapshot", "ToolingListRow",
            "ToolingListPreferenceSnapshot", "ToolingExportRequest", "ToolingExportPackage",
        ):
            self.assertIn(f"    {schema}:\n", openapi)
        for path in (
            "/projects/{projectId}/tooling-list:",
            "/projects/{projectId}/tooling-list/preferences/{viewId}:",
            "/projects/{projectId}/tooling-exports:",
            "/projects/{projectId}/tooling-exports/{packageId}:content:",
        ):
            self.assertEqual(openapi.count(f"  {path}\n"), 1)
        for command in (
            "npi_core.tooling_export_api.get_tooling_list",
            "npi_core.tooling_export_api.get_tooling_list_preference",
            "npi_core.tooling_export_api.set_tooling_list_preference",
            "npi_core.tooling_export_api.create_tooling_export_package",
            "npi_core.tooling_export_api.download_tooling_export_package",
        ):
            self.assertIn(command, bff)
        self.assertIn("tooling_export_routes_are_disabled", bff)
        self.assertNotIn("/tooling-exports/{packageId}/content", openapi)
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
            ROOT / "apps/npi_core/npi_core/tooling/export_repository.py",
            ROOT / "apps/npi_core/npi_core/tooling_export_api.py",
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
