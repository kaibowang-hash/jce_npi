from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/npi_core/npi_core/tooling/manufacturing_repository.py"
SOURCE = PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _method(name: str) -> str:
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(SOURCE, node) or ""
    raise AssertionError(f"missing method: {name}")


class Phase6ToolingManufacturingRepositoryTest(unittest.TestCase):
    def test_queries_authorize_project_before_master_and_child_resolution(self) -> None:
        collection = _method("tooling_manufacturing_plans")
        detail = _method("tooling_manufacturing_plan_detail")
        for source in (collection, detail):
            self.assertLess(
                source.index("self._authorized_project(project_id)"),
                source.index("self._master_for_project(project, tooling_master_id)"),
            )
        self.assertLess(
            detail.index("self._master_for_project(project, tooling_master_id)"),
            detail.index("self._manufacturing_plan_for_project("),
        )

    def test_commands_lock_then_bind_idempotency_before_references(self) -> None:
        for name in (
            "create_tooling_manufacturing_plan",
            "create_tooling_manufacturing_milestone_observation",
        ):
            source = _method(name)
            lock = source.index("self._locked_authorized_project(project_id)")
            context = source.index("self._command_context(")
            master = source.index("self._master_for_project(project, tooling_master_id)")
            self.assertLess(lock, context)
            self.assertLess(context, master)
            self.assertIn("idempotency_key_hash=idempotency_key_hash", source)

    def test_each_write_is_one_append_only_transaction_with_audit_and_seal(self) -> None:
        expectations = {
            "create_tooling_manufacturing_plan": (
                "self._insert_manufacturing_plan(plan)",
                'target_type="tooling_manufacturing_plan_revision"',
            ),
            "create_tooling_manufacturing_milestone_observation": (
                "self._insert_milestone_observation(observation)",
                'target_type="tooling_manufacturing_milestone_observation"',
            ),
        }
        for name, (insert_marker, target_marker) in expectations.items():
            source = _method(name)
            transaction = source.index("with tooling_command_write():")
            receipt = source.index("self._insert_receipt(", transaction)
            insert = source.index(insert_marker, receipt)
            audit = source.index("self._append_audit(", insert)
            seal = source.index("self._seal_receipt(", audit)
            self.assertLess(receipt, insert)
            self.assertLess(insert, audit)
            self.assertLess(audit, seal)
            self.assertIn(target_marker, source[seal:])
            self.assertNotIn(".commit(", source)
            self.assertNotIn(".rollback(", source)

    def test_exact_members_release_files_and_predecessors_are_revalidated(self) -> None:
        for marker in (
            '"NPI Project Member"',
            '"NPI Document Revision Lifecycle"',
            '"NPI Document Lifecycle Event"',
            'str(getattr(lifecycle, "current_state", "")) != "released"',
            'str(event.event_type) != "released"',
            "self._file_revision_for_project(",
            "validate_manufacturing_plan_successor",
            "validate_milestone_observation_successor",
        ):
            self.assertIn(marker, SOURCE)

    def test_erp_boundary_is_injected_read_only_and_unavailable_by_default(self) -> None:
        source = _method("_procurement_cost_projection")
        self.assertIn("if reader is None:", source)
        self.assertIn("return ToolingProcurementCostUnavailable()", source)
        self.assertIn("reader.read_tooling_procurement_cost(", source)
        self.assertIn("procurement_cost_projection_from_snapshot(snapshot)", source)
        combined = SOURCE.casefold()
        for forbidden in (
            "requests.",
            "httpx.",
            "supplier portal",
            "purchase order insert",
            "erpnext credential",
        ):
            self.assertNotIn(forbidden, combined)

    def test_all_persisted_collections_are_explicitly_bounded(self) -> None:
        self.assertIn("_MAX_PLANS = 200", SOURCE)
        self.assertIn("_MAX_OBSERVATIONS = 1_000", SOURCE)
        self.assertIn("_MAX_MEMBERS = 500", SOURCE)
        self.assertIn("_MAX_LIFECYCLES = 2", SOURCE)
        for method_name in (
            "_manufacturing_plans",
            "_manufacturing_observations",
            "_released_document_evidence",
        ):
            self.assertIn("self._bounded_documents(", _method(method_name))


if __name__ == "__main__":
    unittest.main()
