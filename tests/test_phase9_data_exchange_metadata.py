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
    "npi_data_exchange_profile",
    "npi_data_exchange_export",
    "npi_retention_policy_version",
    "npi_retention_archive_record",
)


class Phase9DataExchangeMetadataTest(unittest.TestCase):
    def test_additive_doctypes_are_read_only_system_manager_history(self) -> None:
        for module in DOCTYPE_NAMES:
            metadata = json.loads((DOCTYPE_ROOT / module / f"{module}.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["allow_rename"], 0)
            self.assertEqual(metadata["read_only"], 1)
            self.assertEqual(metadata["permissions"], [{"role": "System Manager", "read": 1, "write": 0, "create": 1, "delete": 0, "export": 0, "print": 0, "email": 0}])
            self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))

    def test_controllers_require_scoped_write_hash_and_immutable_history(self) -> None:
        joined = ""
        for module in DOCTYPE_NAMES:
            source = (DOCTYPE_ROOT / module / f"{module}.py").read_text(encoding="utf-8")
            ast.parse(source)
            joined += source
            self.assertIn("require_data_exchange_write()", source)
            self.assertIn("deny_data_exchange_delete()", source)
            self.assertIn("get_doc_before_save()", source)
        self.assertIn("sha256_json(payload)", joined)

    def test_visible_sources_have_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        for module in DOCTYPE_NAMES:
            metadata = json.loads((DOCTYPE_ROOT / module / f"{module}.json").read_text(encoding="utf-8"))
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            sources.update(option for field in metadata["fields"] if field.get("fieldtype") == "Select" for option in str(field.get("options", "")).splitlines() if option)
        for path in tuple((APP_ROOT / "data_exchange").glob("*.py")) + (APP_ROOT / "data_exchange_api.py",):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            sources.update(str(node.args[0].value) for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str))
        catalogs = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as stream:
                catalogs[language] = {row[0]: row[1] for row in csv.reader(stream) if len(row) >= 2 and row[0]}
            self.assertFalse(sorted(source for source in sources if not catalogs[language].get(source)))
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
