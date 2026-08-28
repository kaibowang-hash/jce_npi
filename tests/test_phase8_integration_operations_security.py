from __future__ import annotations

import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "apps/npi_integration/npi_integration/integration_operations"


class Phase8IntegrationOperationsSecurityTest(unittest.TestCase):
    def load_guard(self):
        permission_error = type("PinnedPermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.PermissionError = permission_error
        frappe.flags = types.SimpleNamespace(existing_marker="retained")
        frappe.session = types.SimpleNamespace(user="service@example.invalid")
        roles = {"service@example.invalid": ["NPI API User", "System Manager"]}
        frappe.get_roles = lambda user: roles.get(user, [])

        def throw(message, error=None):
            raise (error or permission_error)(message)

        frappe.throw = throw
        spec = importlib.util.spec_from_file_location(
            "p807_integration_operations_guard",
            PACKAGE / "frappe_validation.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        guard = importlib.util.module_from_spec(spec)
        with patch.dict(
            sys.modules,
            {"frappe": frappe, spec.name: guard},
        ):
            spec.loader.exec_module(guard)
        return guard, frappe, permission_error

    def test_capability_is_actor_bound_exact_and_finally_restored(self) -> None:
        guard, frappe, permission_error = self.load_guard()
        allowed = frozenset({("NPI Integration Action Receipt", "insert")})
        with guard.integration_operations_write_capability(
            service_actor_user_id="service@example.invalid",
            scope="project:00000000-0000-4000-8000-000000000001",
            allowed=allowed,
        ) as capability:
            self.assertEqual(capability.actor, frappe.session.user)
            self.assertTrue(
                getattr(frappe.flags, guard.ACTION_RECEIPT_WRITE_FLAG)
            )
            guard.require_integration_operations_write(
                "NPI Integration Action Receipt",
                "insert",
            )
            with self.assertRaises(permission_error):
                guard.require_integration_operations_write(
                    "NPI Integration Action Receipt",
                    "save",
                )
            with self.assertRaises(permission_error):
                guard.require_integration_operations_write(
                    "NPI Integration Reconciliation Observation",
                    "insert",
                )
        self.assertFalse(hasattr(frappe.flags, guard.ACTION_RECEIPT_WRITE_FLAG))
        self.assertEqual(frappe.flags.existing_marker, "retained")
        with self.assertRaises(permission_error):
            guard.require_integration_operations_write(
                "NPI Integration Action Receipt",
                "insert",
            )

    def test_wrong_actor_role_scope_and_support_set_fail_closed(self) -> None:
        guard, frappe, permission_error = self.load_guard()
        allowed = frozenset({("NPI Integration Action Receipt", "insert")})
        for actor in (
            "Administrator",
            "Guest",
            "wrong@example.invalid",
            " service@example.invalid",
        ):
            with self.subTest(actor=actor), self.assertRaises(permission_error):
                with guard.integration_operations_write_capability(
                    service_actor_user_id=actor,
                    scope="project:exact",
                    allowed=allowed,
                ):
                    pass
        frappe.get_roles = lambda _user: ["System Manager"]
        with self.assertRaises(permission_error):
            with guard.integration_operations_write_capability(
                service_actor_user_id="service@example.invalid",
                scope="project:exact",
                allowed=allowed,
            ):
                pass
        frappe.get_roles = lambda _user: ["NPI API User"]
        for invalid_allowed in (
            frozenset(),
            frozenset({("NPI Integration Action Receipt", "save")}),
            frozenset({("Caller Selected DocType", "insert")}),
        ):
            with self.subTest(allowed=invalid_allowed), self.assertRaises(ValueError):
                with guard.integration_operations_write_capability(
                    service_actor_user_id="service@example.invalid",
                    scope="project:exact",
                    allowed=invalid_allowed,
                ):
                    pass
        for scope in ("", " project:exact", "x" * 161):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                with guard.integration_operations_write_capability(
                    service_actor_user_id="service@example.invalid",
                    scope=scope,
                    allowed=allowed,
                ):
                    pass

    def test_checkpoint_one_has_no_route_repository_queue_adapter_or_permission_bypass(self) -> None:
        files = list(PACKAGE.glob("*.py"))
        self.assertEqual(
            {path.name for path in files},
            {"__init__.py", "domain.py", "doctype_base.py", "frappe_validation.py"},
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for forbidden in (
            "@frappe.whitelist",
            "requests.",
            "httpx.",
            "enqueue(",
            "enqueue_after_commit",
            "ignore_permissions",
            "frappe.get_doc",
            "frappe" + ".db" + ".sql",
            ".insert(",
            ".save(",
            "endpoint",
        ):
            self.assertNotIn(forbidden, combined)
        for path in files:
            ast.parse(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
