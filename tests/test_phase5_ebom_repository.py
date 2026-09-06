from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/npi_core/npi_core/ebom/frappe_repository.py"
SOURCE = PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def function(name: str) -> str:
    matches = [
        node
        for node in ast.walk(TREE)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name}, found {len(matches)}")
    value = ast.get_source_segment(SOURCE, matches[0])
    if value is None:
        raise AssertionError(f"Unable to read {name}")
    return value


class Phase5EngineeringBomRepositoryTest(unittest.TestCase):
    def test_scope_authorizes_project_before_protected_ebom_lookup(self) -> None:
        value = function("authorize_scope")
        self.assertLess(
            value.index("self._authorized_project(project_id)"),
            value.index("self._ebom_for_project(project, ebom_id"),
        )
        self.assertNotIn("ignore_" "permissions", SOURCE)
        self.assertNotIn("frappe.db." "sql", SOURCE)

    def test_create_checks_policy_actor_and_replay_before_mutability(self) -> None:
        value = function("create_ebom")
        order = (
            "self._locked_command_project(project_id)",
            "self._load_exact_policy(",
            'self._require_policy_actor(policy, "create")',
            "self._receipt_replay(",
            "require_mutable_project(project)",
            "create_engineering_bom_revision(",
            "self._insert_receipt(",
            '"doctype": "NPI Engineering BOM"',
            "self._insert_revision_bundle(",
            "root.save()",
            "self._append_audit(",
            "self._seal_receipt(",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        diagnostic_codes = (
            "P504_CREATE_PROJECT_LOCK",
            "P504_CREATE_POLICY_LOAD",
            "P504_CREATE_POLICY_AUTHORITY",
            "P504_CREATE_PAYLOAD_HASH",
            "P504_CREATE_IDEMPOTENCY_REPLAY",
            "P504_CREATE_PROJECT_MUTABILITY",
            "P504_CREATE_DOMAIN_BUILD",
            "P504_CREATE_TRANSACTION_SCOPE",
            "P504_CREATE_RECEIPT_INSERT",
            "P504_CREATE_ROOT_INSERT",
            "P504_CREATE_ROOT_PROJECTION_SAVE",
            "P504_CREATE_AUDIT_APPEND",
            "P504_CREATE_RESPONSE_BUILD",
            "P504_CREATE_RECEIPT_SEAL",
        )
        for code in diagnostic_codes:
            with self.subTest(code=code):
                self.assertEqual(value.count(code), 1)

    def test_revision_bundle_diagnostics_preserve_insert_order(self) -> None:
        value = function("_insert_revision_bundle")
        order = (
            "P504_CREATE_REVISION_INSERT",
            "P504_CREATE_LINE_INSERT",
            "P504_CREATE_LIFECYCLE_INSERT",
        )
        positions = [value.index(code) for code in order]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(value.count(".insert()"), 3)

    def test_successor_binds_exact_root_and_predecessor_before_append(self) -> None:
        value = function("create_revision")
        for fragment in (
            "expected_ebom_version",
            "predecessor_revision_id",
            "expected_predecessor_snapshot_hash",
            "self._require_root_policy(root, policy)",
            "self._require_root_version(root, expected_ebom_version)",
            "self._revision_for_root(",
            "predecessor=predecessor",
        ):
            self.assertIn(fragment, value)
        order = (
            "self._insert_receipt(",
            "self._insert_revision_bundle(",
            "root.save()",
            "self._append_audit(",
            "self._seal_receipt(",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))

    def test_lifecycle_receipt_event_projection_audit_and_seal_are_atomic_order(self) -> None:
        value = function("_transition")
        order = (
            "self._receipt_replay(",
            "require_mutable_project(project)",
            "self._require_root_version(root, expected_ebom_version)",
            "transition_engineering_bom(",
            "self._insert_receipt(",
            '"doctype": "NPI EBOM Lifecycle Event"',
            "lifecycle_row.save()",
            "self._append_audit(",
            "self._seal_receipt(",
        )
        positions = [value.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        diagnostic_codes = (
            "P504_TRANSITION_PROJECT_LOCK",
            "P504_TRANSITION_POLICY_LOAD",
            "P504_TRANSITION_POLICY_AUTHORITY",
            "P504_TRANSITION_PAYLOAD_HASH",
            "P504_TRANSITION_IDEMPOTENCY_REPLAY",
            "P504_TRANSITION_PROJECT_MUTABILITY",
            "P504_TRANSITION_ROOT_VERSION",
            "P504_TRANSITION_REVISION_LOAD",
            "P504_TRANSITION_REVISION_HASH",
            "P504_TRANSITION_LIFECYCLE_LOAD",
            "P504_TRANSITION_LIFECYCLE_VERSION",
            "P504_TRANSITION_DOMAIN_BUILD",
            "P504_TRANSITION_TRANSACTION_SCOPE",
            "P504_TRANSITION_RECEIPT_INSERT",
            "P504_TRANSITION_EVENT_INSERT",
            "P504_TRANSITION_LIFECYCLE_PROJECTION_SAVE",
            "P504_TRANSITION_AUDIT_APPEND",
            "P504_TRANSITION_RESPONSE_BUILD",
            "P504_TRANSITION_RECEIPT_SEAL",
        )
        for code in diagnostic_codes:
            with self.subTest(code=code):
                self.assertEqual(value.count(code), 1)
        for forbidden in ("commit()", "rollback()", "traceback", "cookie", "credential"):
            self.assertNotIn(forbidden, value.casefold())

    def test_receipt_replay_revalidates_actor_scope_payload_seal_and_hash(self) -> None:
        value = function("_receipt_replay")
        for fragment in (
            '"tenant_id"',
            '"project_global_id"',
            '"actor_user_id"',
            '"operation"',
            '"idempotency_key_hash"',
            '"payload_hash"',
            '"response_hash"',
            '"sealed"',
            "sha256_json(response)",
        ):
            self.assertIn(fragment, value)

    def test_compare_uses_only_two_explicit_same_root_revisions(self) -> None:
        value = function("compare")
        self.assertIn("from_revision_id", value)
        self.assertIn("to_revision_id", value)
        self.assertEqual(value.count("self._revision_for_root("), 2)
        self.assertIn("compare_engineering_bom_revisions(before, after)", value)
        self.assertNotIn('"latest"', value.casefold())

    def test_public_response_omits_authority_lists_and_storage_or_erp_truth(self) -> None:
        public = "\n".join(
            function(name)
            for name in (
                "_policy_response",
                "_ebom_summary",
                "_revision_response",
                "_event_response",
            )
        ).casefold()
        for forbidden in (
            "creator_user_ids",
            "reviewer_user_ids",
            "release_authority_user_ids",
            "file_url",
            "item_code",
            "mbom",
            "routing",
        ):
            self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()
