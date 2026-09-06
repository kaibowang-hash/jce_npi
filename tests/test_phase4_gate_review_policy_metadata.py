from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"


class GateReviewPolicyMetadataTest(unittest.TestCase):
    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {
            value["fieldname"]: value
            for value in metadata["fields"]  # type: ignore[index]
        }

    def test_policy_metadata_is_versioned_additive_and_admin_only(self) -> None:
        root = self.load("npi_gate_review_policy")
        version = self.load("npi_gate_review_policy_version")
        for metadata in (root, version):
            with self.subTest(doctype=metadata["name"]):
                self.assertEqual(metadata.get("custom"), 0)
                self.assertEqual(metadata.get("allow_rename"), 0)
                permissions = metadata["permissions"]  # type: ignore[index]
                self.assertEqual(
                    {permission["role"] for permission in permissions},
                    {"System Manager"},
                )
                self.assertTrue(
                    all(
                        not permission.get(operation)
                        for permission in permissions
                        for operation in ("delete", "export", "print", "email")
                    )
                )

        root_fields = self.fields(root)
        version_fields = self.fields(version)
        self.assertEqual(root.get("autoname"), "field:global_id")
        self.assertEqual(root_fields["global_id"].get("unique"), 1)
        self.assertEqual(root_fields["policy_code"].get("unique"), 1)
        self.assertEqual(version.get("autoname"), "field:version_key")
        self.assertEqual(version_fields["global_id"].get("unique"), 1)
        self.assertEqual(version_fields["version_key"].get("unique"), 1)
        self.assertEqual(
            version_fields["publication_state"].get("options"),
            "draft\npublished",
        )

    def test_version_persists_closed_policy_and_exact_template_snapshot(self) -> None:
        version = self.load("npi_gate_review_policy_version")
        fields = self.fields(version)
        for fieldname in (
            "gate_review_policy",
            "policy_global_id",
            "policy_code",
            "policy_version",
            "optimistic_version",
            "gate_template_global_id",
            "gate_template_version",
            "gate_template_snapshot_hash",
            "review_steps",
            "decision_authority_slot",
            "reopen_authority_slot",
            "exception_rules",
            "dependency_evaluators",
            "snapshot",
            "snapshot_hash",
            "published_at",
        ):
            self.assertIn(fieldname, fields)
        for fieldname in (
            "global_id",
            "policy_global_id",
            "policy_code",
            "version_key",
            "optimistic_version",
            "snapshot",
            "snapshot_hash",
            "published_at",
        ):
            self.assertEqual(fields[fieldname].get("read_only"), 1)
        for fieldname in (
            "review_steps",
            "exception_rules",
            "dependency_evaluators",
            "snapshot",
        ):
            self.assertEqual(fields[fieldname].get("fieldtype"), "JSON")

    def test_no_production_review_policy_fixture_is_declared(self) -> None:
        hooks = (ROOT / "apps/npi_core/npi_core/hooks.py").read_text(encoding="utf-8")
        self.assertNotIn('"NPI Gate Review Policy"', hooks)
        self.assertNotIn('"NPI Gate Review Policy Version"', hooks)


if __name__ == "__main__":
    unittest.main()
