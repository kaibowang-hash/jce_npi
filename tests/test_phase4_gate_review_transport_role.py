from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS_PATH = ROOT / "apps/npi_core/npi_core/hooks.py"
FIXTURES_ROOT = ROOT / "apps/npi_core/npi_core/fixtures"
ROLE_FIXTURE_PATH = FIXTURES_ROOT / "role.json"

EXPECTED_FIXTURE_HOOK = [
    {
        "doctype": "Role",
        "filters": [["role_name", "=", "NPI API User"]],
    }
]
EXPECTED_ROLE_FIXTURE = [
    {
        "doctype": "Role",
        "name": "NPI API User",
        "role_name": "NPI API User",
        "desk_access": 0,
        "disabled": 0,
        "is_custom": 0,
    }
]


def _literal_assignment(path: Path, name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one literal {name} assignment.")
    return ast.literal_eval(matches[0])


class Phase4GateReviewTransportRoleTest(unittest.TestCase):
    def test_hook_exports_only_the_exact_transport_role(self) -> None:
        self.assertEqual(
            _literal_assignment(HOOKS_PATH, "fixtures"),
            EXPECTED_FIXTURE_HOOK,
        )

    def test_fixture_contains_only_the_non_desk_transport_role(self) -> None:
        self.assertEqual(
            sorted(path.name for path in FIXTURES_ROOT.iterdir() if path.is_file()),
            ["role.json"],
        )
        records = json.loads(ROLE_FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(records, EXPECTED_ROLE_FIXTURE)
        self.assertIs(type(records[0]["desk_access"]), int)
        self.assertEqual(records[0]["desk_access"], 0)

    def test_fixture_cannot_assign_users_or_install_business_policy(self) -> None:
        records = json.loads(ROLE_FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual({record["doctype"] for record in records}, {"Role"})

        serialized = json.dumps(records, ensure_ascii=False).casefold()
        for prohibited in (
            '"doctype": "has role"',
            '"doctype": "user"',
            '"roles"',
            '"users"',
            "gate review policy",
            "gate template",
            "project template",
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, serialized)


if __name__ == "__main__":
    unittest.main()
