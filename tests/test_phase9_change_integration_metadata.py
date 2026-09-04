from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "apps/npi_integration/npi_integration/engineering_change"
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
TRANSLATIONS = ROOT / "apps/npi_integration/npi_integration/translations"


class Phase9ChangeIntegrationMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_engineering_change_inbox",
        "npi_engineering_change_summary_request",
        "npi_engineering_change_summary_outbox",
        "npi_engineering_change_summary_attempt",
        "npi_engineering_change_summary_result",
    )

    @staticmethod
    def load(folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def test_five_additive_support_doctypes_are_read_only_and_install_no_rows(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata["read_only"], 1)
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["track_changes"], 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(
                    all(field.get("read_only") == 1 for field in metadata["fields"])
                )
                self.assertTrue(
                    any(field.get("unique") == 1 for field in metadata["fields"])
                )
                for permission in metadata["permissions"]:
                    self.assertFalse(permission.get("delete", 0))
                    for action in ("export", "print", "email", "share"):
                        self.assertFalse(permission.get(action, 0))

    def test_links_resolve_only_to_owned_project_change_or_support_documents(self) -> None:
        names = {
            json.loads(path.read_text(encoding="utf-8"))["name"]
            for root in (
                DOCTYPE_ROOT,
                ROOT / "apps/npi_core/npi_core/npi_core/doctype",
            )
            for path in root.glob("*/*.json")
        }
        for folder in self.FOLDERS:
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field["options"], names)
        self.assertEqual(
            next(
                field
                for field in self.load("npi_engineering_change_inbox")["fields"]
                if field["fieldname"] == "change_global_id"
            )["options"],
            "NPI Engineering Change",
        )

    def test_controllers_are_flag_guarded_append_only_and_keep_attempt_transition_exact(self) -> None:
        markers = {
            "npi_engineering_change_inbox": ("require_inbox_write",),
            "npi_engineering_change_summary_request": ("require_request_write",),
            "npi_engineering_change_summary_outbox": ("require_outbox_write",),
            "npi_engineering_change_summary_attempt": (
                "require_attempt_write",
                'str(previous.state) != "started"',
            ),
            "npi_engineering_change_summary_result": ("require_result_write",),
        }
        for folder, expected in markers.items():
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                encoding="utf-8"
            )
            ast.parse(source)
            self.assertIn("deny_history_delete", source)
            for marker in expected:
                self.assertIn(marker, source)
        validation = (PACKAGE / "frappe_validation.py").read_text(encoding="utf-8")
        for marker in (
            "ChangeIntegrationWriteCapability",
            "_CURRENT.reset(token)",
            "NPI API User",
            "System Manager",
            'actor.casefold() in {"guest", "administrator"}',
        ):
            self.assertIn(marker, validation)

    def test_every_new_metadata_label_and_controller_message_has_direct_translations(self) -> None:
        sources: set[str] = set()
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            sources.update(
                _translation_literals(
                    ast.parse(
                        (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(
                            encoding="utf-8"
                        )
                    )
                )
            )
        for path in (
            PACKAGE / "frappe_validation.py",
            PACKAGE / "problems.py",
            ROOT / "apps/npi_integration/npi_integration/engineering_change_api.py",
        ):
            sources.update(
                _translation_literals(ast.parse(path.read_text(encoding="utf-8")))
            )
        for locale in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{locale}.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                catalog = {row[0]: row[1] for row in csv.reader(stream) if row}
            missing = sorted(source for source in sources if not catalog.get(source))
            self.assertEqual(missing, [], f"{locale} missing: {missing}")


def _translation_literals(tree: ast.AST) -> set[str]:
    return {
        str(node.args[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }


if __name__ == "__main__":
    unittest.main()
