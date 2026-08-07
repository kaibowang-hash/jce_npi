from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/npi_core/npi_core/tooling/frappe_repository.py"
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


class Phase6ToolingRepositoryTest(unittest.TestCase):
    def test_scope_authorizes_project_before_protected_master_resolution(self) -> None:
        value = function("authorize_scope")
        self.assertLess(
            value.index("self._authorized_project(project_id)"),
            value.index("self._master_for_project(project, tooling_master_id)"),
        )
        lowered = SOURCE.casefold()
        for forbidden in (
            "ignore_" "permissions",
            "frappe.db." "sql",
            "commit()",
            "rollback()",
            "http://",
            "https://",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_every_command_locks_project_and_seals_one_atomic_order(self) -> None:
        command_shapes = {
            "create_part": (
                "self._insert_receipt(",
                '"doctype": "NPI Engineering Part"',
                "self._insert_part_revision(",
                "root.save()",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_part_revision": (
                "self._insert_receipt(",
                "self._insert_part_revision(",
                "root.save()",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_requirement": (
                "self._insert_receipt(",
                "self._insert_requirement(",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_master": (
                "self._insert_receipt(",
                "self._insert_master(",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
            "create_applicability": (
                "self._insert_receipt(",
                "self._insert_applicability(",
                "self._append_audit(",
                "response = self._cockpit_for(project)",
                "self._seal_receipt(",
            ),
        }
        for name, atomic_order in command_shapes.items():
            with self.subTest(name=name):
                value = function(name)
                self.assertLess(
                    value.index("self._locked_authorized_project(project_id)"),
                    value.index("self._command_context("),
                )
                self.assertIn("with tooling_command_write():", value)
                positions = [value.index(fragment) for fragment in atomic_order]
                self.assertEqual(positions, sorted(positions))

    def test_reference_commands_replay_before_mutable_reference_resolution(self) -> None:
        requirement = function("create_requirement")
        self.assertLess(
            requirement.index("self._command_context("),
            requirement.index("self._part_revision_for_project("),
        )
        applicability = function("create_applicability")
        replay = applicability.index("self._command_context(")
        for fragment in (
            "self._same_tenant_master(",
            "self._part_revision_for_project(",
            "self._require_project_reference(project, product)",
            "self._require_project_reference(project, model)",
            "self._applicabilities(project)",
        ):
            self.assertLess(replay, applicability.index(fragment))

    def test_part_successor_uses_exact_version_current_predecessor_and_projection(self) -> None:
        value = function("create_part_revision")
        for fragment in (
            "int(root.optimistic_version) != expected_version",
            "require_current=True",
            "part.advance(revision)",
            "predecessor_global_id=part.current_revision_global_id",
            "predecessor_snapshot_hash=part.current_revision_snapshot_hash",
            "root.current_revision_global_id = str(advanced.current_revision_global_id)",
            "int(root.optimistic_version) != advanced.optimistic_version",
        ):
            self.assertIn(fragment, value)

    def test_applicability_binds_exact_scope_successor_and_effectivity(self) -> None:
        value = function("create_applicability")
        for fragment in (
            "self._same_tenant_master(project, tooling_master_id)",
            "require_current=True",
            "previous.applicability_version != expected_version",
            "validate_applicability_successor(previous, applicability)",
            "ensure_no_effectivity_overlap(applicability, retained)",
            "value.relationship_key_hash == applicability.relationship_key_hash",
        ):
            self.assertIn(fragment, value)
        reference = function("_require_project_reference")
        self.assertIn("len(matches) != 1", reference)
        self.assertIn("row.source_system", reference)
        self.assertIn("row.source_object_id", reference)

    def test_receipt_replay_revalidates_instance_actor_scope_payload_and_seal(self) -> None:
        value = function("_receipt_replay")
        for fragment in (
            '"tenant_id"',
            '"project_global_id"',
            '"actor_user_id": self.actor',
            '"operation"',
            '"idempotency_key_hash"',
            '"payload_hash"',
            '"target_object_type"',
            '"target_global_id"',
            '"response_hash"',
            '"sealed"',
            "sha256_json(response)",
            "for_update=True",
        ):
            self.assertIn(fragment, value)
        self.assertNotIn("frappe.session.user", value)

    def test_public_projection_is_bounded_and_keeps_downstream_unavailable(self) -> None:
        cockpit = function("_cockpit_response")
        for fragment in (
            '"lifecycle": self._unavailable("lifecycle_policy_unavailable")',
            '"revision": self._unavailable("tooling_revision_not_delivered")',
            '"physicalSet": self._unavailable("physical_set_not_delivered")',
            '"trial": self._unavailable("trial_not_delivered")',
            '"erp": self._unavailable("erp_projection_unavailable")',
        ):
            self.assertIn(fragment, cockpit)
        for forbidden in (
            "lifecycleState",
            "setCount",
            "assetId",
            "shotCount",
            "credential",
            "erpnextEndpoint",
        ):
            self.assertNotIn(forbidden, cockpit)
        bounded = function("_bounded_documents")
        self.assertIn("limit_page_length=maximum + 1", bounded)
        self.assertIn("if len(names) > maximum", bounded)


if __name__ == "__main__":
    unittest.main()
