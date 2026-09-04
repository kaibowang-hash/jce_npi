from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
APP_ROOT = ROOT / "apps/npi_core/npi_core"
TRANSLATIONS = APP_ROOT / "translations"
DOCTYPE_NAMES = (
    "npi_historical_migration_batch",
    "npi_historical_migration_preview",
    "npi_historical_migration_job",
    "npi_historical_migration_target_binding",
)


class Phase9HistoricalMigrationMetadataTest(unittest.TestCase):
    def test_four_additive_doctypes_have_closed_system_manager_permissions(self) -> None:
        for module in DOCTYPE_NAMES:
            metadata = json.loads((DOCTYPE_ROOT / module / f"{module}.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["allow_rename"], 0)
            self.assertEqual(metadata["permissions"][0]["role"], "System Manager")
            for permission in metadata["permissions"]:
                for action in ("delete", "export", "print", "email"):
                    self.assertFalse(permission.get(action, 0), (module, action))
            self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))

    def test_controllers_enforce_scoped_writes_immutable_evidence_and_hashes(self) -> None:
        sources = []
        for module in DOCTYPE_NAMES:
            path = DOCTYPE_ROOT / module / f"{module}.py"
            source = path.read_text(encoding="utf-8")
            ast.parse(source)
            sources.append(source)
            self.assertIn("require_historical_migration_write()", source)
            self.assertIn("deny_historical_migration_delete()", source)
        joined = "\n".join(sources)
        self.assertIn("sha256_json(snapshot) != self.snapshot_hash", joined)
        self.assertIn("cannot move backward", joined)

    def test_repository_and_api_have_no_generic_doctype_or_direct_sql_boundary(self) -> None:
        paths = (
            APP_ROOT / "historical_migration_api.py",
            APP_ROOT / "historical_migration/frappe_repository.py",
            APP_ROOT / "historical_migration/bundle.py",
        )
        joined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for path in paths:
            ast.parse(path.read_text(encoding="utf-8"))
        self.assertNotIn("frappe.db" + ".sql", joined)
        self.assertNotIn("frappe.client." + "insert", joined)
        self.assertNotIn("frappe.client." + "set_value", joined)
        self.assertIn("Operation-specific P9-05 repository", joined)
        self.assertIn('"System Manager"', joined)
        self.assertIn("npi_p9_05_non_production_rehearsal", joined)

    def test_visible_sources_have_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        for module in DOCTYPE_NAMES:
            directory = DOCTYPE_ROOT / module
            metadata = json.loads((directory / f"{module}.json").read_text(encoding="utf-8"))
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            sources.update(
                option
                for field in metadata["fields"]
                if field.get("fieldtype") == "Select"
                for option in str(field.get("options", "")).splitlines()
                if option
            )
        for path in (APP_ROOT / "historical_migration").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            sources.update(
                str(node.args[0].value)
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_" and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
            )
        catalogs = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as stream:
                catalogs[language] = {row[0]: row[1] for row in csv.reader(stream) if len(row) >= 2 and row[0]}
            self.assertFalse(sorted(source for source in sources if not catalogs[language].get(source)))
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
