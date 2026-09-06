from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"

SYSTEM_MANAGER = {
    "role": "System Manager",
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "export": 0,
    "print": 0,
    "email": 0,
}
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
API_TRANSITION = {**API_APPEND, "write": 1}


class Phase5DocumentMetadataTest(unittest.TestCase):
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

    def test_document_foundation_contains_exact_separated_objects(self) -> None:
        expected_fields = {
            "npi_document_policy": {
                "global_id",
                "tenant_id",
                "policy_key",
                "policy_key_hash",
                "title",
                "enabled",
                "optimistic_version",
            },
            "npi_document_policy_version": {
                "global_id",
                "document_policy",
                "tenant_id",
                "policy_global_id",
                "policy_key",
                "policy_version",
                "version_key",
                "title",
                "publication_state",
                "document_types",
                "confidentiality_keys",
                "allowed_mime_types",
                "preview_mime_types",
                "maximum_file_bytes",
                "lock_lease_minutes",
                "policy_snapshot",
                "snapshot_hash",
                "published_at",
                "optimistic_version",
            },
            "npi_controlled_document": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "document_number",
                "document_number_key",
                "document_type_key",
                "title",
                "confidentiality_key",
                "current_revision_global_id",
                "current_revision_major",
                "current_revision_minor",
                "current_revision_snapshot_hash",
                "current_lock_global_id",
                "current_lock_version",
                "current_lock_holder_user_id",
                "current_lock_expires_at",
                "optimistic_version",
                "created_by_user_id",
                "created_at",
            },
            "npi_document_revision": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "controlled_document",
                "document_global_id",
                "major",
                "minor",
                "revision_key",
                "reason",
                "effective_date",
                "predecessor_revision_global_id",
                "lock_global_id",
                "lock_version",
                "revision_state",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "revision_snapshot",
                "snapshot_hash",
                "optimistic_version",
                "created_by_user_id",
                "created_at",
                "request_id",
                "trace_id",
            },
            "npi_document_revision_file": {
                "global_id",
                "association_key",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "document_revision",
                "document_revision_global_id",
                "file_revision",
                "file_revision_global_id",
                "file_document_global_id",
                "file_revision_number",
                "file_optimistic_version",
                "display_file_name",
                "frappe_file_id",
                "frappe_content_hash",
                "file_name",
                "mime_type",
                "size_bytes",
                "sha256",
                "scan_state",
                "scan_observed_at",
                "is_private",
                "released",
                "file_role",
                "provenance",
                "connector_state",
                "connector_reason_code",
                "file_revision_source_snapshot",
                "association_snapshot",
                "snapshot_hash",
                "optimistic_version",
                "created_by_user_id",
                "created_at",
                "request_id",
                "trace_id",
            },
            "npi_document_relationship": {
                "global_id",
                "relationship_key",
                "tenant_id",
                "project_global_id",
                "controlled_document",
                "document_global_id",
                "relationship_kind",
                "project_reference_type",
                "target_source_system",
                "target_reference_global_id",
                "target_identity",
                "target_version",
                "target_snapshot",
                "snapshot_hash",
                "optimistic_version",
                "created_by_user_id",
                "created_at",
                "request_id",
                "trace_id",
            },
            "npi_document_lock_event": {
                "global_id",
                "event_key",
                "tenant_id",
                "project_global_id",
                "controlled_document",
                "document_global_id",
                "lock_global_id",
                "lock_version",
                "event_type",
                "holder_user_id",
                "acquired_at",
                "expires_at",
                "actor_user_id",
                "occurred_at",
                "prior_event_global_id",
                "closure_reason",
                "request_id",
                "trace_id",
                "event_snapshot",
                "snapshot_hash",
            },
            "npi_document_share_grant": {
                "global_id",
                "grant_key",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "document_revision_global_id",
                "document_revision_snapshot_hash",
                "revision_file_global_id",
                "revision_file_snapshot_hash",
                "file_revision_global_id",
                "share_label",
                "share_label_hash",
                "expires_at",
                "share_state",
                "retrieval_state",
                "retrieval_reason_code",
                "grant_snapshot",
                "snapshot_hash",
                "closed_at",
                "closed_by_user_id",
                "closure_reason",
                "optimistic_version",
                "created_by_user_id",
                "created_at",
                "request_id",
                "trace_id",
            },
            "npi_document_command_idempotency": {
                "record_id",
                "actor",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "operation",
                "actor_key_hash",
                "payload_hash",
                "request_id",
                "trace_id",
                "created_at",
                "response_snapshot",
                "response_sealed",
            },
        }
        for folder, expected in expected_fields.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), expected)
                self.assertEqual(metadata.get("allow_rename"), 0)

    def test_history_and_command_tables_are_api_controlled(self) -> None:
        append_only = {
            "npi_document_revision",
            "npi_document_revision_file",
            "npi_document_relationship",
            "npi_document_lock_event",
        }
        transition = {
            "npi_controlled_document",
            "npi_document_share_grant",
            "npi_document_command_idempotency",
        }
        for folder in sorted(append_only | transition):
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata.get("read_only"), 1)
                expected_api = API_APPEND if folder in append_only else API_TRANSITION
                self.assertEqual(
                    metadata.get("permissions"),
                    [SYSTEM_MANAGER, expected_api],
                )
                self.assertTrue(
                    all(
                        field.get("read_only") == 1
                        for field in self.fields(metadata).values()
                    )
                )

    def test_policy_administration_has_no_default_rows_or_production_rules(
        self,
    ) -> None:
        policy = self.load("npi_document_policy")
        version = self.load("npi_document_policy_version")
        self.assertEqual(policy.get("permissions"), [SYSTEM_MANAGER])
        self.assertEqual(version.get("permissions"), [SYSTEM_MANAGER])
        self.assertIsNone(version.get("read_only"))
        fields = self.fields(version)
        for fieldname in (
            "global_id",
            "tenant_id",
            "policy_global_id",
            "policy_key",
            "version_key",
            "policy_snapshot",
            "snapshot_hash",
            "published_at",
            "optimistic_version",
        ):
            self.assertEqual(fields[fieldname].get("read_only"), 1)
        self.assertEqual(
            self.fields(version)["publication_state"].get("options"),
            "draft\npublished",
        )
        for metadata in (policy, version):
            self.assertNotIn("fixtures", metadata)
            self.assertNotIn("records", metadata)

    def test_exact_file_identity_and_unavailable_external_foundation(self) -> None:
        association = self.fields(self.load("npi_document_revision_file"))
        self.assertEqual(association["file_revision"].get("fieldtype"), "Link")
        self.assertEqual(
            association["file_revision"].get("options"),
            "NPI File Revision",
        )
        self.assertEqual(
            association["connector_state"].get("options"),
            "unavailable\nfailed",
        )
        share = self.fields(self.load("npi_document_share_grant"))
        self.assertEqual(share["retrieval_state"].get("options"), "unavailable")
        forbidden = {
            "url",
            "file_url",
            "token",
            "secret",
            "password",
            "external_url",
            "access_token",
        }
        for folder in (
            "npi_document_revision_file",
            "npi_document_share_grant",
            "npi_document_command_idempotency",
        ):
            with self.subTest(folder=folder):
                self.assertTrue(forbidden.isdisjoint(self.fields(self.load(folder))))

    def test_search_indexes_cover_tenant_project_document_and_reverse_lookup(
        self,
    ) -> None:
        for folder in (
            "npi_document_revision",
            "npi_document_revision_file",
            "npi_document_relationship",
            "npi_document_lock_event",
            "npi_document_share_grant",
        ):
            with self.subTest(folder=folder):
                fields = self.fields(self.load(folder))
                for fieldname in ("tenant_id", "project_global_id"):
                    self.assertEqual(fields[fieldname].get("search_index"), 1)
                if "document_global_id" in fields:
                    self.assertEqual(
                        fields["document_global_id"].get("search_index"),
                        1,
                    )


if __name__ == "__main__":
    unittest.main()
