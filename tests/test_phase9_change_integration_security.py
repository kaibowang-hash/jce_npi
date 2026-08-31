from __future__ import annotations

import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "apps/npi_integration/npi_integration/engineering_change"
API = ROOT / "apps/npi_integration/npi_integration/engineering_change_api.py"


class Phase9ChangeIntegrationSecurityTest(unittest.TestCase):
    def load_guard(self):
        permission_error = type("PinnedPermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.PermissionError = permission_error
        frappe.flags = types.SimpleNamespace(existing_marker="retained")
        frappe.session = types.SimpleNamespace(user="service@example.invalid")
        roles = {
            "service@example.invalid": ["NPI API User", "System Manager"],
            "operator@example.invalid": ["NPI API User"],
        }
        frappe.get_roles = lambda user: roles.get(user, [])
        frappe.set_user = lambda user: setattr(frappe.session, "user", user)

        def throw(message, error=None):
            raise (error or permission_error)(message)

        frappe.throw = throw
        spec = importlib.util.spec_from_file_location(
            "p901_engineering_change_guard", PACKAGE / "frappe_validation.py"
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        guard = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"frappe": frappe, spec.name: guard}):
            spec.loader.exec_module(guard)
        return guard, frappe, permission_error

    def test_capabilities_are_actor_bound_exact_and_finally_restore_flags(self) -> None:
        guard, frappe, permission_error = self.load_guard()
        with guard.inbound_transaction_write(
            "service@example.invalid"
        ) as capability:
            self.assertTrue(getattr(frappe.flags, guard.INBOX_WRITE_FLAG))
            guard.assert_capability(
                capability, "NPI Engineering Change Inbox", "insert"
            )
            with self.assertRaises(permission_error):
                guard.assert_capability(
                    capability,
                    "NPI Engineering Change Summary Result",
                    "insert",
                )
        self.assertFalse(hasattr(frappe.flags, guard.INBOX_WRITE_FLAG))
        self.assertEqual(frappe.flags.existing_marker, "retained")
        setattr(frappe.flags, guard.INBOX_WRITE_FLAG, True)
        with self.assertRaises(permission_error):
            guard.require_inbox_write("insert")
        delattr(frappe.flags, guard.INBOX_WRITE_FLAG)
        frappe.session.user = "operator@example.invalid"
        with guard.summary_request_write("operator@example.invalid") as capability:
            guard.assert_capability(
                capability,
                "NPI Engineering Change Summary Request",
                "insert",
            )

    def test_guest_admin_wrong_roles_and_unbound_session_fail_closed(self) -> None:
        guard, frappe, permission_error = self.load_guard()
        for actor in ("Guest", "Administrator", "wrong@example.invalid"):
            with self.subTest(actor=actor), self.assertRaises(permission_error):
                with guard.service_actor_scope(actor):
                    pass
        with self.assertRaises(permission_error):
            with guard.inbound_transaction_write("operator@example.invalid"):
                pass
        frappe.session.user = "operator@example.invalid"
        with self.assertRaises(permission_error):
            with guard.summary_request_write("service@example.invalid"):
                pass

    def test_only_fixed_helpers_have_permission_bypass_and_no_direct_sql_or_raw_transport(self) -> None:
        files = [*PACKAGE.glob("*.py"), API]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for forbidden in (
            "frappe" + ".db" + ".sql",
            "requests.",
            "httpx.",
            "site_config",
            "Authorization",
            "raw_response",
            "raw_payload",
        ):
            self.assertNotIn(forbidden, combined)
        bypasses: list[tuple[str, str]] = []
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "ignore_permissions":
                    bypasses.append((path.name, ast.unparse(node.value)))
        self.assertEqual(bypasses, [])
        self.assertNotIn("frappe.client", combined)

    def test_runtime_defaults_are_synthetic_or_disabled_and_production_origin_is_absent(self) -> None:
        hooks = (ROOT / "apps/npi_integration/npi_integration/hooks.py").read_text(
            encoding="utf-8"
        )
        fixture = (PACKAGE / "runtime_fixture.py").read_text(encoding="utf-8")
        self.assertIn("runtime_fixture.resolve_profile", hooks)
        self.assertIn("TargetMode.SYNTHETIC", fixture)
        self.assertIn("disposable_runtime_marker=True", fixture)
        for source in (hooks, fixture):
            self.assertNotIn("JCE-Core", source)
            self.assertNotIn("jce.1", source)
            self.assertNotIn("core.whjichen.cn", source)


if __name__ == "__main__":
    unittest.main()
