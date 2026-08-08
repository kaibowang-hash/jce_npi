from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_DOCTYPE = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
INTEGRATION_DOCTYPE = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase6ToolingAcceptanceMetadataTest(unittest.TestCase):
    OBJECTS = {
        "npi_tooling_acceptance_evidence_revision": CORE_DOCTYPE,
        "npi_tool_asset_request": INTEGRATION_DOCTYPE,
        "npi_tool_asset_command_idempotency": INTEGRATION_DOCTYPE,
    }

    @staticmethod
    def load(root: Path, folder: str) -> dict[str, object]:
        return json.loads((root / folder / f"{folder}.json").read_text(encoding="utf-8"))

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {value["fieldname"]: value for value in metadata["fields"]}  # type: ignore[index]

    def test_three_additive_objects_are_guarded_and_install_no_rows(self) -> None:
        for folder, root in self.OBJECTS.items():
            with self.subTest(folder=folder):
                metadata = self.load(root, folder)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertEqual(metadata.get("read_only"), 1)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(all(field.get("read_only") == 1 for field in self.fields(metadata).values()))
        request_fields = self.fields(self.load(INTEGRATION_DOCTYPE, "npi_tool_asset_request"))
        self.assertEqual(request_fields["target_mode"].get("options"), "mock")
        self.assertEqual(request_fields["request_state"].get("options"), "draft")
        self.assertEqual(request_fields["business_approval_state"].get("options"), "unavailable")
        self.assertEqual(request_fields["dispatch_state"].get("options"), "prohibited")
        self.assertEqual(request_fields["target_result_state"].get("options"), "not_requested")
        for forbidden in (
            "formal_asset_id", "asset_state", "location", "shot_count",
            "maintenance_due", "endpoint", "credential", "secret", "outbox",
        ):
            self.assertNotIn(forbidden, request_fields)

    def test_controllers_require_closed_writes_exact_dependencies_and_immutability(self) -> None:
        acceptance = (CORE_DOCTYPE / "npi_tooling_acceptance_evidence_revision" / "npi_tooling_acceptance_evidence_revision.py").read_text(encoding="utf-8")
        request = (INTEGRATION_DOCTYPE / "npi_tool_asset_request" / "npi_tool_asset_request.py").read_text(encoding="utf-8")
        receipt = (INTEGRATION_DOCTYPE / "npi_tool_asset_command_idempotency" / "npi_tool_asset_command_idempotency.py").read_text(encoding="utf-8")
        for marker in (
            "require_tooling_command_write()", "deny_tooling_history_update()",
            "deny_tooling_history_delete", '"NPI Tooling Master"', '"NPI Tooling Set"',
            '"NPI Tooling Set Revision Binding"', '"NPI Tooling Revision"',
            '"NPI File Revision"', '"scan_state": "clean"', '"is_private": 1',
            "validate_acceptance_successor",
        ):
            self.assertIn(marker, acceptance)
        for marker in (
            "require_tool_asset_request_write()", "deny_tool_asset_history_update()",
            "deny_tool_asset_history_delete", '"NPI Tooling Master"', '"NPI Tooling Set"',
            '"NPI Tooling Set Revision Binding"', '"NPI Tooling Revision"',
            '"NPI Tooling Acceptance Evidence Revision"',
        ):
            self.assertIn(marker, request)
        self.assertIn("TOOL_ASSET_OPERATION", receipt)
        self.assertIn("A sealed Tool Asset command receipt cannot be changed.", receipt)

    def test_receipts_add_only_exact_acceptance_and_asset_operation_pairs(self) -> None:
        core = self.fields(self.load(CORE_DOCTYPE, "npi_tooling_command_idempotency"))
        self.assertEqual(str(core["operation"].get("options", "")).splitlines()[-1], "tooling_acceptance_evidence.create")
        self.assertEqual(str(core["target_object_type"].get("options", "")).splitlines()[-1], "tooling_acceptance_evidence_revision")
        source = (CORE_DOCTYPE / "npi_tooling_command_idempotency" / "npi_tooling_command_idempotency.py").read_text(encoding="utf-8")
        self.assertIn('"tooling_acceptance_evidence.create": "tooling_acceptance_evidence_revision"', source)
        asset = self.fields(self.load(INTEGRATION_DOCTYPE, "npi_tool_asset_command_idempotency"))
        self.assertEqual(asset["request_global_id"].get("options"), "NPI Tool Asset Request")

    def test_all_new_visible_sources_have_direct_symmetric_translations(self) -> None:
        sources: set[str] = set()
        python_paths = [
            ROOT / "apps/npi_core/npi_core/tooling/acceptance_domain.py",
            ROOT / "apps/npi_integration/npi_integration/tool_asset_request/domain.py",
            ROOT / "apps/npi_integration/npi_integration/tool_asset_request/frappe_validation.py",
        ]
        for folder, root in self.OBJECTS.items():
            metadata = self.load(root, folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            python_paths.append(root / folder / f"{folder}.py")
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
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} P6-06 translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
