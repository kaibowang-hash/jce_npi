from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/npi_core/npi_core"


class Phase9DataExchangeSecurityTest(unittest.TestCase):
    def test_backend_has_no_network_sql_generic_writer_or_production_escape(self) -> None:
        paths = tuple((APP / "data_exchange").glob("*.py")) + (APP / "data_exchange_api.py",)
        joined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for path in paths:
            ast.parse(path.read_text(encoding="utf-8"))
        for forbidden in (
            "requests.", "httpx.", "paramiko", "subprocess", "os.system",
            "frappe.db." + "sql", "ignore_permissions", "frappe.client." + "insert",
            "frappe.client." + "set_value", "bench console",
        ):
            self.assertNotIn(forbidden, joined)
        self.assertNotIn("doctype: Any", joined)
        self.assertIn("productionContact", joined)
        self.assertIn("genericWriterAvailable", joined)

    def test_fixed_adapters_private_files_and_default_disabled_switch_are_explicit(self) -> None:
        repository = (APP / "data_exchange/frappe_repository.py").read_text(encoding="utf-8")
        api = (APP / "data_exchange_api.py").read_text(encoding="utf-8")
        package = (APP / "data_exchange/export_package.py").read_text(encoding="utf-8")
        self.assertIn("_SOURCE_ADAPTERS", repository)
        self.assertIn("is_private=1", repository)
        self.assertIn('configuration.get("npi_p9_06_routes_disabled") is False', api)
        self.assertIn('startswith(("=", "+", "-", "@"))', package)
        self.assertIn("ZIP_STORED", package)

    def test_governed_write_scope_is_the_only_audit_append_boundary(self) -> None:
        source = (APP / "data_exchange/frappe_validation.py").read_text(encoding="utf-8")
        self.assertIn("frappe.flags.npi_audit_append = True", source)
        self.assertIn('delattr(frappe.flags, "npi_audit_append")', source)


if __name__ == "__main__":
    unittest.main()
