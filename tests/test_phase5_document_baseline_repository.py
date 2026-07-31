from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = (
    ROOT
    / "apps"
    / "npi_core"
    / "npi_core"
    / "documents"
    / "baseline_repository.py"
)
SOURCE = REPOSITORY_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _function(name: str) -> str:
    matches = [
        node
        for node in ast.walk(TREE)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name!r} function, found {len(matches)}")
    value = ast.get_source_segment(SOURCE, matches[0])
    if value is None:
        raise AssertionError(f"Unable to read {name!r}")
    return value


class DocumentBaselineRepositoryTest(unittest.TestCase):
    def test_create_authorizes_exact_actor_before_protected_member_resolution(
        self,
    ) -> None:
        value = _function("create_baseline")
        order = (
            "self._locked_baseline_project(project_id)",
            "self._current_actor_member(project)",
            "self._load_exact_baseline_policy(",
            "policy.permits_baseline(self.actor)",
            "self._baseline_replay(",
            "require_mutable_project(project)",
            "self._resolve_members(project, members)",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("ignore_" "permissions", value)

    def test_policy_options_require_transport_role_and_current_membership(
        self,
    ) -> None:
        value = _function("_published_baseline_policy_options")
        order = (
            "self.principal.is_external",
            '"NPI API User" not in self.principal.roles',
            "self._current_actor_member(project) is None",
            "self._load_exact_baseline_policy(",
            "policy.permits_baseline(self.actor)",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))

    def test_member_resolution_locks_and_revalidates_exact_release_evidence(
        self,
    ) -> None:
        resolve_members = _function("_resolve_members")
        resolve_input = _function("_resolve_member_input")
        validate_files = _function("_validate_released_files")
        self.assertIn("for revision_id in sorted(by_id, key=str)", resolve_members)
        self.assertIn("enumerate(preconditions, start=1)", resolve_members)
        for doctype in (
            "NPI Document Revision",
            "NPI Controlled Document",
            "NPI Document Revision Lifecycle",
            "NPI Document Lifecycle Event",
            "NPI Document Review Cycle",
        ):
            with self.subTest(doctype=doctype):
                self.assertIn(doctype, resolve_input)
        self.assertGreaterEqual(resolve_input.count("for_update=True"), 5)
        self.assertIn(
            "event.evidence_snapshot_hash != cycle.evidence.snapshot_hash",
            resolve_input,
        )
        self.assertIn(
            "lifecycle.release_snapshot_hash\n            "
            "!= precondition.expected_release_snapshot_hash",
            resolve_input,
        )
        self.assertIn("cycle.evidence", resolve_input)
        self.assertNotIn(
            "lifecycle.release_snapshot_hash != cycle.evidence.snapshot_hash",
            resolve_input,
        )
        self.assertIn("self._release_file_evidence(", validate_files)
        self.assertIn("int(file_revision.released or 0) != 1", validate_files)
        self.assertIn("_stable_file_evidence_matches(observed, expected)", validate_files)

    def test_live_file_comparison_keeps_stable_identity_and_content_closed(self) -> None:
        value = _function("_stable_file_evidence_matches")
        for field in (
            "association_global_id",
            "association_snapshot_hash",
            "file_revision_global_id",
            "file_document_global_id",
            "frappe_file_id",
            "frappe_content_hash",
            "file_name",
            "mime_type",
            "size_bytes",
            "sha256",
            "uploaded_by_user_id",
            "uploaded_at",
        ):
            with self.subTest(field=field):
                self.assertIn(f"observed.{field}", value)
                self.assertIn(f"expected.{field}", value)
        self.assertEqual(value.count('scan_state == "clean"'), 2)

    def test_write_order_seals_actor_bound_receipt_last(self) -> None:
        value = _function("create_baseline")
        order = (
            "self._insert_baseline_receipt(",
            "self._insert_baseline(project, baseline)",
            "self._insert_members(project, baseline_document, baseline)",
            "self._append_audit(",
            'response = {',
            "self._seal_baseline_receipt(",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        replay = _function("_baseline_replay")
        for fragment in (
            '"tenant_id"',
            '"project_global_id"',
            '"actor_user_id"',
            '"operation"',
            '"payload_hash"',
            '"response_hash"',
            '"sealed"',
            "sha256_json(response)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, replay)

    def test_public_response_is_url_and_storage_identity_free(self) -> None:
        value = _function("_baseline_response").casefold()
        for forbidden in (
            "file_url",
            "fileurl",
            "private_url",
            "download_url",
            "frappe_file_id",
            "frappe_content_hash",
            "storage_identity",
            "cookie",
            "credential",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, value)
        self.assertIn('"releaseSnapshotHash"', _function("_baseline_response"))
        self.assertIn('"files"', _function("_baseline_response"))


if __name__ == "__main__":
    unittest.main()
