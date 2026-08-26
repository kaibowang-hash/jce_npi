from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
MODULE = ROOT / "apps/npi_integration/npi_integration/quality_link"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase8QualityLinkMetadataTest(unittest.TestCase):
    FOLDERS = ("npi_formal_quality_link_head", "npi_formal_quality_link_revision", "npi_formal_quality_link_command_idempotency")

    def load(self, folder: str) -> dict[str, object]:
        return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))

    def test_three_additive_doctypes_are_zero_row_read_only_and_no_business_crud(self) -> None:
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            self.assertEqual(metadata, self.load(folder), "metadata discovery must be idempotent across repeated migrate reads")
            self.assertEqual(metadata["autoname"], "field:global_id")
            self.assertEqual((metadata["allow_rename"], metadata["track_changes"], metadata["read_only"]), (0, 0, 1))
            self.assertNotIn("fixtures", metadata)
            self.assertNotIn("records", metadata)
            self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))
            for permission in metadata["permissions"]:
                for action in ("write", "create", "delete", "export", "print", "email"):
                    self.assertFalse(permission.get(action, 0))

    def test_links_resolve_and_controllers_are_guarded(self) -> None:
        names = {json.loads(path.read_text(encoding="utf-8"))["name"] for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT) for path in root.glob("*/*.json")}
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field["options"], names)
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
            self.assertIn("QualityLinkSupportDocument", source)
            ast.parse(source)
        base = (MODULE / "doctype_base.py").read_text(encoding="utf-8")
        guards = (MODULE / "frappe_validation.py").read_text(encoding="utf-8")
        for marker in ("require_quality_link_write(self.doctype, action)", "deny_quality_link_history_delete()", "assert_immutable_fields"):
            self.assertIn(marker, base)
        for marker in ("QualityLinkWriteCapability", "_CURRENT.reset(token)", "QUALITY_LINK_REVISION_WRITE_FLAG", "QUALITY_LINK_HEAD_WRITE_FLAG", "QUALITY_LINK_RECEIPT_WRITE_FLAG"):
            self.assertIn(marker, guards)

    def test_revision_append_head_plus_one_and_receipt_one_way_seal_are_explicit(self) -> None:
        revision = (DOCTYPE_ROOT / self.FOLDERS[1] / f"{self.FOLDERS[1]}.py").read_text(encoding="utf-8")
        head = (DOCTYPE_ROOT / self.FOLDERS[0] / f"{self.FOLDERS[0]}.py").read_text(encoding="utf-8")
        receipt = (DOCTYPE_ROOT / self.FOLDERS[2] / f"{self.FOLDERS[2]}.py").read_text(encoding="utf-8")
        self.assertIn("append_only = True", (MODULE / "doctype_base.py").read_text(encoding="utf-8"))
        self.assertIn("previous.optimistic_version + 1", head)
        self.assertIn("previous.revision_number + 1", head)
        self.assertIn("require_exact_parent", head)
        self.assertIn("require_exact_parent", revision)
        self.assertIn("previous.sealed or 0", receipt)
        self.assertIn("canonical_payload_hash(expected)", revision)
        self.assertIn("canonical_payload_hash(response)", receipt)

    def test_visible_sources_have_direct_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        paths = [
            MODULE / "frappe_validation.py",
            MODULE / "problems.py",
            ROOT / "apps/npi_integration/npi_integration/quality_link_api.py",
        ]
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(metadata["name"])
            sources.update(field["label"] for field in metadata["fields"])
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Select":
                    sources.update(item for item in field.get("options", "").splitlines() if item)
            paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            sources.update(node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str))
        catalogs = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as handle:
                catalogs[language] = {row[0]: row[1] for row in csv.reader(handle) if len(row) >= 2 and row[0]}
            self.assertFalse(sorted(source for source in sources if not catalogs[language].get(source)))
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_checkpoint_two_repository_uses_only_guarded_additive_records(self) -> None:
        repository = (MODULE / "frappe_repository.py").read_text(encoding="utf-8")
        guards = (MODULE / "frappe_validation.py").read_text(encoding="utf-8")
        for doctype, action in (
            ("NPI Formal Quality Link Revision", "insert"),
            ("NPI Formal Quality Link Head", "insert"),
            ("NPI Formal Quality Link Head", "save"),
            ("NPI Formal Quality Link Command Idempotency", "insert"),
            ("NPI Formal Quality Link Command Idempotency", "save"),
        ):
            self.assertIn(f'("{doctype}", "{action}")', guards)
        self.assertIn("with quality_link_command_write(", repository)
        self.assertIn("self._insert_receipt", repository)
        self.assertIn("self._insert_revision", repository)
        self.assertIn("self._insert_head", repository)
        self.assertIn("self._append_audit", repository)
        self.assertIn("self._seal_receipt", repository)
        self.assertNotIn("ignore_permissions", repository)


if __name__ == "__main__":
    unittest.main()
