from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/npi_core/npi_core/tooling/revision_repository.py"
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


class Phase6ToolingRevisionRepositoryTest(unittest.TestCase):
    def test_queries_authorize_project_before_revision_part_chain_or_binding(self) -> None:
        for name, protected in (
            ("tooling_revisions", "self._master_for_project("),
            ("tooling_revision_detail", "self._master_for_project("),
            ("part_controlled_specification", "self._part_revision_for_project("),
            ("tooling_process_chain_detail", "self._process_chain_revision_for_project("),
        ):
            with self.subTest(name=name):
                value = function(name)
                self.assertLess(
                    value.index("self._authorized_project(project_id)"),
                    value.index(protected),
                )

    def test_every_mutation_replays_before_resolving_protected_references(self) -> None:
        cases = {
            "create_tooling_revision": "self._master_for_project(",
            "create_part_controlled_specification": "self._part_revision_for_project(",
            "create_tooling_process_chain_revision": "self._process_chain_revisions(",
            "create_tooling_set_revision_binding": "self._master_for_project(",
        }
        for name, protected in cases.items():
            with self.subTest(name=name):
                value = function(name)
                self.assertLess(
                    value.index("self._locked_authorized_project(project_id)"),
                    value.index("self._command_context("),
                )
                self.assertLess(value.index("self._command_context("), value.index(protected))

    def test_every_mutation_has_one_receipt_insert_audit_response_and_seal_order(self) -> None:
        for name in (
            "create_tooling_revision",
            "create_part_controlled_specification",
            "create_tooling_process_chain_revision",
            "create_tooling_set_revision_binding",
        ):
            with self.subTest(name=name):
                value = function(name)
                self.assertIn("with tooling_command_write():", value)
                positions = [
                    value.index("self._insert_receipt("),
                    value.index("self._append_audit("),
                    value.index("response ="),
                    value.index("self._seal_receipt("),
                ]
                self.assertEqual(positions, sorted(positions))

    def test_revision_current_tip_effectivity_and_document_provenance_fail_closed(self) -> None:
        create = function("create_tooling_revision")
        self.assertIn("expected_version != current[-1].revision_number", create)
        self.assertIn("validate_tooling_revision_successor", create)
        applicability = function("_current_effective_applicability")
        for fragment in (
            "value.tooling_master_global_id == tooling_master_id",
            "max(item.applicability_version for item in relationship)",
            "value.effective_from > today",
            "today >= value.effective_to",
        ):
            self.assertIn(fragment, applicability)
        document = function("_document_revision_reference")
        for fragment in ("row.tenant_id", "row.project_global_id", "row.snapshot_hash"):
            self.assertIn(fragment, document)

    def test_part_chain_and_set_binding_are_exact_append_only_boundaries(self) -> None:
        part = function("create_part_controlled_specification")
        self.assertIn("require_current=True", part)
        self.assertIn("_part_specification_for_revision", part)
        chain = function("create_tooling_process_chain_revision")
        self.assertIn("validate_process_chain_successor", chain)
        self.assertIn("expected_version != current[-1].chain_version", chain)
        binding = function("create_tooling_set_revision_binding")
        self.assertIn("self._binding_for_set(project, tooling_set)", binding)
        self.assertNotIn(".save()", binding)
        self.assertNotIn("NPI Tooling Set\"", function("_insert_set_revision_binding"))

    def test_bounded_projections_keep_lifecycle_supplier_erp_trial_and_impact_unavailable(self) -> None:
        for name, maximum in (
            ("_tooling_revisions_for_master", "_MAX_REVISIONS"),
            ("_part_specification_for_revision", "_MAX_PART_SPECIFICATIONS"),
            ("_process_chain_revisions", "_MAX_PROCESS_CHAIN_REVISIONS"),
            ("_binding_for_set", "_MAX_BINDINGS"),
        ):
            self.assertIn(f"maximum={maximum}", function(name))
        combined = "\n".join(
            function(name)
            for name in (
                "_tooling_revision_collection",
                "_tooling_revision_detail_response",
                "_part_specification_context",
                "_process_chain_collection",
            )
        )
        for reason in (
            "lifecycle_policy_unavailable",
            "formal_supplier_unavailable",
            "erp_projection_unavailable",
            "combined_trial_not_delivered",
            "automatic_impact_not_delivered",
        ):
            self.assertIn(reason, combined)
        lowered = SOURCE.casefold()
        for forbidden in (
            "ignore_" "permissions",
            "frappe.db." "sql",
            "commit()",
            "rollback()",
            "http://",
            "https://",
            "erpnextendpoint",
            "credential",
        ):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
