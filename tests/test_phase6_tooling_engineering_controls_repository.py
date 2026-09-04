from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/npi_core/npi_core/tooling/engineering_controls_repository.py"
SOURCE = PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _method(name: str) -> str:
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(SOURCE, node) or ""
    raise AssertionError(f"missing method: {name}")


class Phase6ToolingEngineeringControlsRepositoryTest(unittest.TestCase):
    def test_query_authorizes_project_before_master_and_child_reads(self) -> None:
        source = _method("tooling_engineering_controls")
        project = source.index("self._authorized_project(project_id)")
        master = source.index("self._master_for_project(project, tooling_master_id)")
        defect = source.index("self._engineering_defects(project, tooling_master_id)")
        self.assertLess(project, master)
        self.assertLess(master, defect)

    def test_commands_lock_then_bind_actor_idempotency_before_references(self) -> None:
        for name in (
            "create_tooling_defect_revision",
            "create_tooling_process_profile_revision",
            "create_tooling_capacity_scenario_revision",
        ):
            with self.subTest(name=name):
                source = _method(name)
                lock = source.index("self._locked_authorized_project(project_id)")
                context = source.index("self._command_context(")
                master = source.index(
                    "self._master_for_project(project, tooling_master_id)"
                )
                self.assertLess(lock, context)
                self.assertLess(context, master)
                self.assertIn("idempotency_key_hash=idempotency_key_hash", source)

    def test_each_write_is_one_append_only_transaction_with_audit_and_seal(self) -> None:
        expectations = {
            "create_tooling_defect_revision": (
                "self._insert_engineering_defect(value)",
                'target_type="tooling_defect_revision"',
            ),
            "create_tooling_process_profile_revision": (
                "self._insert_engineering_process_profile(value)",
                'target_type="tooling_process_profile_revision"',
            ),
            "create_tooling_capacity_scenario_revision": (
                "self._insert_engineering_capacity_scenario(value)",
                'target_type="tooling_capacity_scenario_revision"',
            ),
        }
        for name, (insert_marker, target_marker) in expectations.items():
            with self.subTest(name=name):
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

    def test_exact_project_references_and_immutable_predecessors_are_revalidated(self) -> None:
        for marker in (
            "self._tooling_revision_for_project(",
            "self._active_member(project, supplied.global_id)",
            "self._file_revision_for_project(",
            "self._released_document_evidence(",
            "self._part_revision_for_project(",
            "self._applicabilities(project)",
            "self._tooling_sets_for_master(project, tooling_master_id)",
            "validate_tooling_defect_successor",
            "validate_process_profile_successor",
            "validate_capacity_scenario_successor",
        ):
            self.assertIn(marker, SOURCE)

    def test_all_persisted_collections_are_explicitly_bounded(self) -> None:
        self.assertIn("_MAX_DEFECT_REVISIONS = 1_000", SOURCE)
        self.assertIn("_MAX_PROCESS_PROFILE_REVISIONS = 500", SOURCE)
        self.assertIn("_MAX_CAPACITY_SCENARIO_REVISIONS = 500", SOURCE)
        for method_name in (
            "_engineering_defects",
            "_engineering_process_profiles",
            "_engineering_capacity_scenarios",
        ):
            self.assertIn("self._bounded_documents(", _method(method_name))

    def test_p6_defect_append_stops_after_the_shared_identity_enters_p7(self) -> None:
        source = _method("_defect_predecessor")
        self.assertIn('"NPI Trial Defect Revision"', source)
        self.assertIn('"defect_global_id": str(defect_id)', source)
        self.assertIn("limit_page_length=1", source)
        self.assertIn("if trial_successors:", source)
        self.assertIn("raise ToolingVersionConflict()", source)

    def test_trial_gate_lifecycle_and_erp_truth_are_not_written(self) -> None:
        for forbidden in (
            '"doctype": "NPI Trial',
            '"doctype": "NPI Gate',
            '"doctype": "NPI Tooling Lifecycle',
            '"doctype": "ERPNext',
            "requests.",
            "httpx.",
            ".db_set(",
            ".save(",
        ):
            self.assertNotIn(forbidden, SOURCE)
        query = _method("tooling_engineering_controls")
        self.assertIn('"state": "not_measured"', query)
        self.assertIn('"reasonCode": "trial_context_unavailable"', query)
        self.assertIn('"state": "unavailable"', query)
        self.assertIn("ToolingHealthUnavailable().snapshot_payload()", query)


if __name__ == "__main__":
    unittest.main()
