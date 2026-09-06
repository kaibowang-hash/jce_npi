from __future__ import annotations

import importlib
import sys
import types
import unittest


sys.path.insert(0, "apps/npi_core")


class Configuration(dict[str, object]):
    def __getattr__(self, key: str) -> object:
        return self[key]


class Phase5EngineeringBomSecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_frappe = sys.modules.get("frappe")
        self.saved_security = sys.modules.get("npi_core.request_security")
        sys.modules.pop("npi_core.request_security", None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.conf = Configuration()
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.security = importlib.import_module("npi_core.request_security")

    def tearDown(self) -> None:
        if self.saved_frappe is None:
            sys.modules.pop("frappe", None)
        else:
            sys.modules["frappe"] = self.saved_frappe
        if self.saved_security is None:
            sys.modules.pop("npi_core.request_security", None)
        else:
            sys.modules["npi_core.request_security"] = self.saved_security

    def test_only_literal_true_disables_p5_04_routes(self) -> None:
        for value in (None, False, 0, 1, "true"):
            with self.subTest(value=value):
                if value is None:
                    self.frappe.conf.pop("npi_p5_04_routes_disabled", None)
                else:
                    self.frappe.conf["npi_p5_04_routes_disabled"] = value
                self.assertFalse(
                    self.security.engineering_bom_routes_are_disabled()
                )
                self.security.require_engineering_bom_routes_enabled()

        self.frappe.conf["npi_p5_04_routes_disabled"] = True
        self.assertTrue(self.security.engineering_bom_routes_are_disabled())
        with self.assertRaises(
            self.security.EngineeringBomRoutesDisabled
        ) as caught:
            self.security.require_engineering_bom_routes_enabled()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(caught.exception.code, "EBOM_ROUTES_DISABLED")
        self.assertTrue(caught.exception.retryable)


if __name__ == "__main__":
    unittest.main()
