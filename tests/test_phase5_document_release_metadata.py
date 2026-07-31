from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
RELEASE_REPOSITORY = (
    ROOT / "apps/npi_core/npi_core/documents/release_repository.py"
)

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


class Phase5DocumentReleaseMetadataTest(unittest.TestCase):
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

    def test_release_foundation_contains_exact_separated_objects(self) -> None:
        expected = {
            "npi_document_release_policy": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "policy_key",
                "policy_key_hash",
                "title",
                "enabled",
                "optimistic_version",
            },
            "npi_document_release_policy_version": {
                "global_id",
                "document_release_policy",
                "tenant_id",
                "project_global_id",
                "policy_global_id",
                "policy_key",
                "policy_version",
                "version_key",
                "title",
                "publication_state",
                "submitter_user_ids",
                "reviewer_assignments",
                "required_approval_count",
                "release_authority_user_ids",
                "supersede_authority_user_ids",
                "obsolete_authority_user_ids",
                "confirmation_method",
                "required_scan_state",
                "require_live_private_identity",
                "require_sha256_match",
                "supersede_requires_released_successor",
                "supersede_requires_later_revision",
                "supersede_requires_successor_effective_date",
                "policy_snapshot",
                "snapshot_hash",
                "published_at",
                "optimistic_version",
            },
            "npi_document_revision_lifecycle": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "document_revision",
                "revision_global_id",
                "current_state",
                "lifecycle_version",
                "active_cycle_global_id",
                "approved_cycle_global_id",
                "approved_event_global_id",
                "release_event_global_id",
                "release_snapshot_hash",
                "replacement_revision_global_id",
                "replacement_effective_date",
                "terminal_event_global_id",
                "last_event_global_id",
                "updated_by_user_id",
                "updated_at",
                "request_id",
                "trace_id",
            },
            "npi_document_review_cycle": {
                "global_id",
                "cycle_key",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "document_revision",
                "revision_global_id",
                "cycle_number",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "review_evidence",
                "evidence_snapshot_hash",
                "reviewer_assignments",
                "required_approval_count",
                "prior_rejected_cycle_global_id",
                "submitted_by_user_id",
                "submitted_at",
                "request_id",
                "trace_id",
                "cycle_snapshot",
                "snapshot_hash",
            },
            "npi_document_confirmation": {
                "global_id",
                "confirmation_key",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "document_revision",
                "revision_global_id",
                "review_cycle",
                "cycle_global_id",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "evidence_snapshot_hash",
                "confirmation_type",
                "actor_user_id",
                "authority_slot",
                "confirmation_method",
                "confirmation_intent",
                "confirmed",
                "reason",
                "confirmed_at",
                "request_id",
                "trace_id",
                "confirmation_evidence",
                "evidence_hash",
            },
            "npi_document_lifecycle_event": {
                "global_id",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "document_revision",
                "revision_global_id",
                "event_type",
                "from_state",
                "to_state",
                "from_version",
                "to_version",
                "review_cycle",
                "cycle_global_id",
                "policy_global_id",
                "policy_version",
                "policy_snapshot_hash",
                "evidence_snapshot_hash",
                "confirmation_hashes",
                "replacement_revision_global_id",
                "replacement_effective_date",
                "actor_user_id",
                "occurred_at",
                "request_id",
                "trace_id",
                "event_snapshot",
                "event_hash",
            },
        }
        for folder, fields in expected.items():
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(set(self.fields(metadata)), fields)
                self.assertEqual(metadata.get("allow_rename"), 0)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)

    def test_policy_is_admin_only_and_history_is_api_controlled(self) -> None:
        for folder in (
            "npi_document_release_policy",
            "npi_document_release_policy_version",
        ):
            self.assertEqual(self.load(folder).get("permissions"), [SYSTEM_MANAGER])
        for folder in (
            "npi_document_review_cycle",
            "npi_document_confirmation",
            "npi_document_lifecycle_event",
        ):
            metadata = self.load(folder)
            self.assertEqual(
                metadata.get("permissions"),
                [{**SYSTEM_MANAGER, "write": 0}, API_APPEND],
            )
            self.assertTrue(
                all(
                    field.get("read_only") == 1
                    for field in self.fields(metadata).values()
                )
            )
        lifecycle = self.load("npi_document_revision_lifecycle")
        self.assertEqual(
            lifecycle.get("permissions"),
            [SYSTEM_MANAGER, API_TRANSITION],
        )

    def test_state_family_and_safeguards_are_closed(self) -> None:
        lifecycle = self.fields(self.load("npi_document_revision_lifecycle"))
        self.assertEqual(
            lifecycle["current_state"].get("options"),
            "draft\nin_review\napproved\nreleased\nsuperseded\nobsolete",
        )
        version = self.fields(
            self.load("npi_document_release_policy_version")
        )
        self.assertEqual(
            version["confirmation_method"].get("default"),
            "authenticated_session_confirmation",
        )
        self.assertEqual(version["required_scan_state"].get("default"), "clean")
        for fieldname in (
            "require_live_private_identity",
            "require_sha256_match",
            "supersede_requires_released_successor",
            "supersede_requires_later_revision",
            "supersede_requires_successor_effective_date",
        ):
            self.assertEqual(version[fieldname].get("default"), "1")
            self.assertEqual(version[fieldname].get("read_only"), 1)

    def test_file_delete_protection_precedes_dependency_evaluation(self) -> None:
        hooks = (ROOT / "apps/npi_core/npi_core/hooks.py").read_text(
            encoding="utf-8"
        )
        protection = (
            '"npi_core.documents.release_frappe.'
            'protect_released_document_file"'
        )
        dependency = (
            '"npi_core.gate_review.frappe_repository."'
            '\n                "queue_gate_review_file_dependency_evaluation"'
        )
        self.assertIn(protection, hooks)
        self.assertIn(dependency, hooks)
        self.assertLess(hooks.index(protection), hooks.index(dependency))
        source = (
            ROOT
            / "apps/npi_core/npi_core/documents/release_frappe.py"
        ).read_text(encoding="utf-8")
        self.assertIn('{"frappe_file_id": file_id, "released": 1}', source)
        self.assertNotIn("ignore_" "permissions", source)

    def test_independent_release_switch_and_write_scope_exist(self) -> None:
        security = (ROOT / "apps/npi_core/npi_core/request_security.py").read_text(
            encoding="utf-8"
        )
        validation = (
            ROOT / "apps/npi_core/npi_core/documents/frappe_validation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("npi_p5_02_routes_disabled", security)
        self.assertIn("require_document_release_routes_enabled", security)
        self.assertIn("npi_document_release_command_write", validation)
        self.assertIn("require_document_release_command_write", validation)

    def test_ownership_keeps_projection_and_history_separate(self) -> None:
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text(
            encoding="utf-8"
        )
        for object_name in (
            "DocumentReleasePolicyVersion:",
            "DocumentReviewCycle:",
            "DocumentConfirmation:",
            "DocumentLifecycleEvent:",
            "DocumentRevisionLifecycle:",
        ):
            self.assertIn(object_name, ownership)
        self.assertIn("APPEND_EVENT_AND_VERSION_CONFLICT", ownership)
        self.assertIn("IMMUTABLE_SNAPSHOT", ownership)

    def test_repository_preserves_exact_authority_locks_and_file_truth(
        self,
    ) -> None:
        source = RELEASE_REPOSITORY.read_text(encoding="utf-8")
        self.assertIn("class FrappeDocumentReleaseRepository", source)
        self.assertIn("for_update=True", source)
        self.assertIn("self._can_view_project(project, project_id)", source)
        self.assertNotIn("_can_administer_project", source)
        for marker in (
            "release_policy_value",
            "review_cycle_value",
            "confirmation_value",
            "lifecycle_event_value",
            "has_live_private_file_identity",
            'str(file_revision.scan_state) != "clean"',
            "hashlib.sha256(content).hexdigest()",
            "file_document.is_private",
            "file_document.is_remote_file",
            "file_document.content_hash",
            "_association_matches_live_file",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("ignore_" + "permissions", source)
        self.assertNotIn("frappe.db." + "sql", source)

    def test_repository_transaction_order_is_closed_for_each_command(
        self,
    ) -> None:
        source = RELEASE_REPOSITORY.read_text(encoding="utf-8")
        tree = ast.parse(source)

        def method(name: str) -> str:
            node = next(
                value
                for value in ast.walk(tree)
                if isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef))
                and value.name == name
            )
            return ast.get_source_segment(source, node) or ""

        sequences = {
            "_submit_review": (
                "_insert_idempotency",
                "_insert_review_cycle",
                "_insert_lifecycle_event",
                "_save_lifecycle",
                "_append_release_audit",
                "_seal_idempotency",
            ),
            "confirm_review": (
                "_insert_idempotency",
                "_insert_confirmation",
                "_insert_lifecycle_event",
                "_save_lifecycle",
                "_append_release_audit",
                "_seal_idempotency",
            ),
            "release_revision": (
                "_insert_idempotency",
                "_mark_file_revisions_released",
                "_insert_confirmation",
                "_insert_lifecycle_event",
                "_save_lifecycle",
                "_append_release_audit",
                "_seal_idempotency",
            ),
            "_terminate_revision": (
                "_insert_idempotency",
                "_insert_confirmation",
                "_insert_lifecycle_event",
                "_save_lifecycle",
                "_append_release_audit",
                "_seal_idempotency",
            ),
        }
        for name, sequence in sequences.items():
            with self.subTest(name=name):
                body = method(name)
                self.assertIn("_controlled_document_write_scope()", body)
                self.assertIn("document_release_command_write()", body)
                offsets = [body.index(marker) for marker in sequence]
                self.assertEqual(offsets, sorted(offsets))

    def test_controller_evidence_chain_distinguishes_review_and_release(
        self,
    ) -> None:
        confirmation = (
            DOCTYPE_ROOT
            / "npi_document_confirmation"
            / "npi_document_confirmation.py"
        ).read_text(encoding="utf-8")
        event = (
            DOCTYPE_ROOT
            / "npi_document_lifecycle_event"
            / "npi_document_lifecycle_event.py"
        ).read_text(encoding="utf-8")
        self.assertIn("DocumentConfirmationType.REVIEW_APPROVE", confirmation)
        self.assertIn('"current_state": "approved"', confirmation)
        self.assertIn('"current_state": "released"', confirmation)
        self.assertIn(
            '"release_snapshot_hash": self.evidence_snapshot_hash',
            confirmation,
        )
        self.assertIn("review_events = {", event)
        self.assertIn('"NPI Document Confirmation"', event)
        self.assertIn(
            '"evidence_snapshot_hash": self.evidence_snapshot_hash',
            event,
        )

    def test_document_receipt_accepts_only_closed_release_operations(self) -> None:
        source = (
            DOCTYPE_ROOT
            / "npi_document_command_idempotency"
            / "npi_document_command_idempotency.py"
        ).read_text(encoding="utf-8")
        for operation in (
            "document.review.submit",
            "document.review.resubmit",
            "document.review.approve",
            "document.review.reject",
            "document.release",
            "document.supersede",
            "document.obsolete",
        ):
            self.assertEqual(source.count(f'"{operation}"'), 1)


if __name__ == "__main__":
    unittest.main()
