from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = (
    ROOT / "apps/npi_core/npi_core/project_work/frappe_repository.py"
)


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


class ProjectWorkRepositorySeamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REPOSITORY_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def method(self, name: str) -> ast.FunctionDef:
        matches = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        self.assertEqual(len(matches), 1, f"Expected one repository method {name}.")
        return matches[0]

    def calls(self, method_name: str, qualified_name: str) -> list[ast.Call]:
        return [
            node
            for node in ast.walk(self.method(method_name))
            if isinstance(node, ast.Call)
            and _qualified_name(node.func) == qualified_name
        ]

    def test_commands_record_explicit_result_semantics(self) -> None:
        expected = {
            "configure_team": ("project.team.configure", "updated"),
            "apply_work_plan": ("project.work_plan.apply", "updated"),
            "capture_plan_baseline": (
                "project.plan_baseline.capture",
                "created",
            ),
            "create_domain_work_item": (
                "project.domain_work_item.create",
                "created",
            ),
        }
        for method_name, (operation, result) in expected.items():
            with self.subTest(method=method_name):
                calls = self.calls(method_name, "self._append_audit")
                self.assertEqual(len(calls), 1)
                keywords = {
                    keyword.arg: keyword.value
                    for keyword in calls[0].keywords
                    if keyword.arg is not None
                }
                self.assertEqual(
                    ast.literal_eval(keywords["operation"]),
                    operation,
                )
                self.assertEqual(ast.literal_eval(keywords["result"]), result)

    def test_every_write_command_locks_and_reloads_the_project_first(
        self,
    ) -> None:
        command_names = (
            "configure_team",
            "apply_work_plan",
            "capture_plan_baseline",
            "create_domain_work_item",
        )
        for method_name in command_names:
            with self.subTest(method=method_name):
                lock_calls = self.calls(
                    method_name,
                    "self._locked_authorized_project",
                )
                self.assertEqual(len(lock_calls), 1)
                mutating_boundary_calls = [
                    *self.calls(method_name, "self._idempotency_replay"),
                    *self.calls(method_name, "self._require_project_version"),
                ]
                self.assertTrue(mutating_boundary_calls)
                self.assertLess(
                    lock_calls[0].lineno,
                    min(call.lineno for call in mutating_boundary_calls),
                )
                direct_authorization = self.calls(
                    method_name,
                    "self._authorized_project",
                )
                self.assertEqual(direct_authorization, [])

        lock_helper = self.method("_locked_authorized_project")
        get_value_calls = [
            node
            for node in ast.walk(lock_helper)
            if isinstance(node, ast.Call)
            and _qualified_name(node.func) == "frappe.db.get_value"
        ]
        self.assertEqual(get_value_calls, [])
        locked_load_calls = [
            node
            for node in ast.walk(lock_helper)
            if isinstance(node, ast.Call)
            and _qualified_name(node.func) == "frappe.get_doc"
        ]
        self.assertEqual(len(locked_load_calls), 1)
        keywords = {
            keyword.arg: keyword.value
            for keyword in locked_load_calls[0].keywords
            if keyword.arg is not None
        }
        self.assertIn("for_update", keywords)
        self.assertIs(ast.literal_eval(keywords["for_update"]), True)

    def test_idempotency_replay_uses_a_current_locking_read(self) -> None:
        replay = self.method("_idempotency_replay")
        reads = [
            node
            for node in ast.walk(replay)
            if isinstance(node, ast.Call)
            and _qualified_name(node.func) == "frappe.db.get_value"
        ]
        self.assertEqual(len(reads), 1)
        keywords = {
            keyword.arg: keyword.value
            for keyword in reads[0].keywords
            if keyword.arg is not None
        }
        self.assertIn("for_update", keywords)
        self.assertIs(ast.literal_eval(keywords["for_update"]), True)

    def test_domain_work_item_bound_is_checked_before_domain_build_and_write(
        self,
    ) -> None:
        method = self.method("create_domain_work_item")
        count_calls = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and _qualified_name(node.func) == "frappe.db.count"
        ]
        build_calls = self.calls(
            "create_domain_work_item",
            "self._prepare_domain_work_item",
        )
        insert_calls = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "insert"
        ]
        self.assertEqual(len(count_calls), 1)
        self.assertEqual(len(build_calls), 1)
        self.assertTrue(insert_calls)
        self.assertLess(count_calls[0].lineno, build_calls[0].lineno)
        self.assertLess(build_calls[0].lineno, min(call.lineno for call in insert_calls))
        comparisons = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Compare)
            and any(isinstance(operator, ast.GtE) for operator in node.ops)
            and any(
                isinstance(comparator, ast.Constant)
                and comparator.value == 10000
                for comparator in node.comparators
            )
        ]
        self.assertTrue(comparisons)

    def test_domain_factories_and_baseline_comparison_are_not_reimplemented(
        self,
    ) -> None:
        self.assertEqual(
            len(
                self.calls(
                    "_prepare_domain_work_item",
                    "build_domain_work_item",
                )
            ),
            1,
        )
        self.assertEqual(
            len(self.calls("capture_plan_baseline", "build_wbs_baseline")),
            1,
        )
        self.assertEqual(
            len(
                self.calls(
                    "_baseline_comparison",
                    "compare_domain_wbs_baseline",
                )
            ),
            1,
        )

    def test_context_and_relation_ids_use_project_scoped_lookup(self) -> None:
        calls = self.calls(
            "_prepare_domain_work_item",
            "self._require_related_project_document",
        )
        doctypes = {
            ast.literal_eval(call.args[0])
            for call in calls
            if call.args and isinstance(call.args[0], ast.Constant)
        }
        self.assertEqual(
            doctypes,
            {
                "NPI Gate Shell",
                "NPI WBS Item",
                "NPI Domain Work Item",
            },
        )
        helper = self.method("_require_related_project_document")
        helper_source = ast.get_source_segment(self.source, helper) or ""
        self.assertIn("document.get(project_field)", helper_source)
        self.assertIn("str(project_id)", helper_source)
        self.assertIn("_field_problem", helper_source)


if __name__ == "__main__":
    unittest.main()
