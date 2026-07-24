from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"


class Phase4GateEvidenceMetadataTest(unittest.TestCase):
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

    def test_file_revision_adds_nullable_project_and_stable_file_identity(self) -> None:
        metadata = self.load("npi_file_revision")
        fields = self.fields(metadata)
        self.assertEqual(metadata.get("autoname"), "field:global_id")
        self.assertEqual(metadata.get("allow_rename"), 0)
        self.assertEqual(metadata.get("read_only"), 1)
        self.assertNotEqual(
            fields["global_id"].get("unique"),
            1,
            "the legacy populated column must not gain a migration-time unique index",
        )

        additive_identity = {
            "tenant_id",
            "project_global_id",
            "document_global_id",
            "revision_key",
            "frappe_file_id",
            "frappe_content_hash",
            "file_name",
            "mime_type",
            "size_bytes",
            "is_private",
            "scan_observed_at",
            "optimistic_version",
        }
        self.assertTrue(additive_identity.issubset(fields))
        for fieldname in additive_identity:
            self.assertNotEqual(
                fields[fieldname].get("reqd"),
                1,
                f"{fieldname} must remain nullable for legacy migration",
            )
            self.assertEqual(fields[fieldname].get("read_only"), 1)

        self.assertEqual(fields["revision_key"].get("unique"), 1)
        self.assertEqual(fields["frappe_file_id"].get("fieldtype"), "Link")
        self.assertEqual(fields["frappe_file_id"].get("options"), "File")
        self.assertEqual(
            fields["scan_state"].get("options"),
            "pending\nclean\ninfected\nfailed",
        )

    def test_gate_evidence_is_append_only_exact_metadata_without_url(self) -> None:
        metadata = self.load("npi_gate_evidence_reference")
        fields = self.fields(metadata)
        expected = {
            "global_id",
            "reference_key",
            "tenant_id",
            "project_global_id",
            "gate_global_id",
            "requirement_global_id",
            "requirement_key",
            "evidence_kind",
            "source_object_type",
            "source_global_id",
            "source_version",
            "source_hash",
            "source_snapshot",
            "created_by",
            "created_at",
            "optimistic_version",
        }
        self.assertEqual(set(fields), expected)
        self.assertEqual(metadata.get("autoname"), "field:global_id")
        self.assertEqual(metadata.get("allow_rename"), 0)
        self.assertEqual(metadata.get("read_only"), 1)
        self.assertEqual(fields["reference_key"].get("unique"), 1)
        self.assertEqual(fields["source_snapshot"].get("fieldtype"), "JSON")
        self.assertEqual(
            fields["evidence_kind"].get("options"),
            "wbs_item\nfile_revision",
        )
        self.assertNotIn("url", " ".join(fields).casefold())
        self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
        self.assertEqual(
            metadata["permissions"],  # type: ignore[index]
            [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "export": 0,
                    "print": 0,
                    "email": 0,
                }
            ],
        )

    def test_controllers_use_sha256_and_controlled_write_flags_only(self) -> None:
        sources = [
            (
                ROOT / "apps/npi_core/npi_core/controlled_evidence_validation.py"
            ).read_text(encoding="utf-8"),
            (DOCTYPE_ROOT / "npi_file_revision/npi_file_revision.py").read_text(
                encoding="utf-8"
            ),
            (
                DOCTYPE_ROOT
                / "npi_gate_evidence_reference/npi_gate_evidence_reference.py"
            ).read_text(encoding="utf-8"),
        ]
        combined = "\n".join(sources)
        self.assertIn("npi_file_revision_command_write", combined)
        self.assertIn("npi_file_scan_result_write", combined)
        self.assertIn("npi_gate_evidence_command_write", combined)
        self.assertIn("hashlib.sha256", combined)
        self.assertIn("frappe_content_hash", combined)
        self.assertIn("usedforsecurity=False", combined)
        self.assertNotIn("ignore_" + "permissions", combined)
        self.assertNotIn("frappe.db." + "sql", combined)


if __name__ == "__main__":
    unittest.main()
