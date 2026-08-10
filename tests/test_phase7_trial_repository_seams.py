from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRIAL_PATH = (
    ROOT
    / "apps/npi_core/npi_core/trial/frappe_repository.py"
)
WORK_PATH = (
    ROOT
    / "apps/npi_core/npi_core/project_work/frappe_repository.py"
)


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


class RepositoryAst:
    def __init__(self, path: Path, class_name: str) -> None:
        self.tree = ast.parse(path.read_text(encoding="utf-8"))
        self.class_node = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )

    def method(self, name: str) -> ast.FunctionDef:
        return next(
            node
            for node in self.class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )

    def calls(self, method_name: str, target: str) -> list[ast.Call]:
        return [
            node
            for node in ast.walk(self.method(method_name))
            if isinstance(node, ast.Call) and _qualified_name(node.func) == target
        ]


class Phase7TrialRepositorySeamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.trial = RepositoryAst(TRIAL_PATH, "FrappeTrialRepository")
        cls.work = RepositoryAst(WORK_PATH, "FrappeProjectWorkRepository")

    def test_commands_authorize_project_before_resolving_child_references(self) -> None:
        reference_calls = {
            "create_plan": "self._require_tooling",
            "create_plan_revision": "self._current_plan_revision",
            "create_round": "self._exact_plan_revision",
            "generate_actions": "self._exact_plan_revision",
        }
        for method_name, reference_call in reference_calls.items():
            with self.subTest(method=method_name):
                project = self.trial.calls(
                    method_name,
                    "self._locked_authorized_project",
                )
                reference = self.trial.calls(method_name, reference_call)
                self.assertEqual(len(project), 1)
                self.assertEqual(len(reference), 1)
                self.assertLess(project[0].lineno, reference[0].lineno)

    def test_replay_precedes_mutability_and_reference_validation(self) -> None:
        for method_name in (
            "create_plan",
            "create_plan_revision",
            "create_round",
            "generate_actions",
        ):
            with self.subTest(method=method_name):
                replay = self.trial.calls(method_name, "self._idempotency_replay")
                terminal = self.trial.calls(method_name, "require_mutable_project")
                self.assertEqual(len(replay), 1)
                self.assertEqual(len(terminal), 1)
                self.assertLess(replay[0].lineno, terminal[0].lineno)

    def test_receipt_is_inserted_before_writes_and_sealed_after_audit(self) -> None:
        writes = {
            "create_plan": "self._insert_plan_revision",
            "create_plan_revision": "self._insert_plan_revision",
            "create_round": "self._insert_round_event",
            "generate_actions": "work_repository.create_domain_work_items_in_parent_command",
        }
        for method_name, write_call in writes.items():
            with self.subTest(method=method_name):
                receipt = self.trial.calls(method_name, "self._insert_receipt")
                writes_found = self.trial.calls(method_name, write_call)
                audit = self.trial.calls(method_name, "self._append_audit")
                seal = self.trial.calls(method_name, "self._seal_receipt")
                self.assertEqual(len(receipt), 1)
                self.assertTrue(writes_found)
                self.assertEqual(len(audit), 1)
                self.assertEqual(len(seal), 1)
                self.assertLess(receipt[0].lineno, min(node.lineno for node in writes_found))
                self.assertLess(max(node.lineno for node in writes_found), audit[0].lineno)
                self.assertLess(audit[0].lineno, seal[0].lineno)

    def test_generate_actions_creates_work_before_immutable_links(self) -> None:
        work = self.trial.calls(
            "generate_actions",
            "work_repository.create_domain_work_items_in_parent_command",
        )
        links = self.trial.calls("generate_actions", "self._insert_work_link")
        self.assertEqual(len(work), 1)
        self.assertEqual(len(links), 1)
        self.assertLess(work[0].lineno, links[0].lineno)

    def test_parent_work_command_advances_project_once_without_second_receipt(self) -> None:
        method_name = "create_domain_work_items_in_parent_command"
        self.assertEqual(
            len(self.work.calls(method_name, "self._advance_project")),
            1,
        )
        self.assertEqual(
            self.work.calls(method_name, "self._insert_idempotency"),
            [],
        )
        self.assertEqual(
            self.work.calls(method_name, "self._seal_idempotency"),
            [],
        )
        inserts = self.work.calls(
            method_name,
            "self._insert_domain_work_item_document",
        )
        audits = self.work.calls(method_name, "self._append_audit")
        self.assertEqual(len(inserts), 1)
        self.assertEqual(len(audits), 1)

    def test_no_command_commits_or_swallows_failures(self) -> None:
        for method_name in (
            "create_plan",
            "create_plan_revision",
            "create_round",
            "generate_actions",
        ):
            method = self.trial.method(method_name)
            qualified = {
                _qualified_name(node.func)
                for node in ast.walk(method)
                if isinstance(node, ast.Call)
            }
            with self.subTest(method=method_name):
                self.assertNotIn("frappe.db.commit", qualified)
                self.assertNotIn("frappe.db.rollback", qualified)
                self.assertFalse(
                    any(
                        isinstance(node, ast.Try)
                        and any(
                            handler.type is None
                            or (
                                isinstance(handler.type, ast.Name)
                                and handler.type.id in {"Exception", "BaseException"}
                            )
                            for handler in node.handlers
                        )
                        for node in ast.walk(method)
                    )
                )


if __name__ == "__main__":
    unittest.main()
