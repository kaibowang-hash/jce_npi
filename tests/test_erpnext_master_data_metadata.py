from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ERP = ROOT / "apps/npi_erpnext_connector/npi_erpnext_connector"
NPI = ROOT / "apps/npi_integration/npi_integration"


class ERPNextMasterDataMetadataTest(unittest.TestCase):
    def test_routes_hooks_jobs_and_migrations_are_complete(self) -> None:
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text()
        self.assertIn(
            '("PUT", "/api/npi/v1/integration/erpnext/master-data")', bff
        )
        self.assertIn(
            '("GET", "/api/npi/v1/integration/erpnext/master-data")', bff
        )
        hooks = (ERP / "hooks.py").read_text()
        for doctype in ("Customer", "Supplier", "Item Group", "Item"):
            self.assertIn(f'"{doctype}": {{', hooks)
        self.assertIn("recover_master_data_deliveries", hooks)
        self.assertIn("reconcile_master_catalogs", hooks)
        self.assertIn("patches.v0_6.sync_master_data_schema", (ERP / "patches.txt").read_text())
        self.assertIn("patches.v0_3.sync_master_data_schema", (NPI / "patches.txt").read_text())

    def test_support_doctypes_are_read_only_and_non_exportable(self) -> None:
        paths = (
            NPI / "npi_integration/doctype/npi_erp_master_snapshot/npi_erp_master_snapshot.json",
            NPI / "npi_integration/doctype/npi_erp_master_catalog_head/npi_erp_master_catalog_head.json",
            NPI / "npi_integration/doctype/npi_erp_master_catalog_entry/npi_erp_master_catalog_entry.json",
            ERP / "npi_erpnext_connector/doctype/npi_erp_master_data_delivery/npi_erp_master_data_delivery.json",
        )
        for path in paths:
            metadata = json.loads(path.read_text())
            self.assertEqual(metadata["read_only"], 1)
            self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))
            for permission in metadata["permissions"]:
                self.assertEqual(permission.get("write"), 0)
                self.assertEqual(permission.get("create"), 0)
                self.assertEqual(permission.get("delete"), 0)
                self.assertEqual(permission.get("export"), 0)
                if permission["role"] == "NPI API User":
                    self.assertEqual(
                        permission.get("read"),
                        0,
                        "Raw DocType reads must not bypass the scoped BFF route.",
                    )

    def test_transport_and_receiver_have_no_generic_writer_or_database_escape(self) -> None:
        source = "\n".join(
            path.read_text()
            for path in (
                ERP / "master_data_repository.py",
                ERP / "master_data_transport.py",
                NPI / "master_data_api.py",
                NPI / "master_data/frappe_repository.py",
            )
        )
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.client." + "insert",
            "frappe.client." + "save",
            "verify=False",
            "http://",
            "doctype = request",
        ):
            self.assertNotIn(forbidden, source)

    def test_connector_remains_python_310_compatible(self) -> None:
        for path in ERP.glob("master_data*.py"):
            tree = ast.parse(path.read_text())
            self.assertFalse(
                any(
                    isinstance(node, ast.ClassDef)
                    and any(
                        isinstance(base, ast.Name) and base.id == "StrEnum"
                        for base in node.bases
                    )
                    for node in ast.walk(tree)
                ),
                path,
            )

    def test_contract_and_ownership_are_declared(self) -> None:
        schema = json.loads(
            (ROOT / "contracts/erp-master-data-snapshot.v1.schema.json").read_text()
        )
        self.assertEqual(schema["properties"]["operation"]["const"], "replace_master_catalog")
        ownership = (ROOT / "contracts/data-ownership.yaml").read_text()
        self.assertIn("  ItemGroup:\n    owner_system: ERPNEXT", ownership)
        self.assertIn("  ERPMasterCatalogSnapshot:", ownership)
        openapi = (ROOT / "contracts/npi-api.openapi.yaml").read_text()
        self.assertIn("  /integration/erpnext/master-data:", openapi)
        self.assertIn("    ERPMasterSnapshotEvent:", openapi)

    def test_runbook_and_frappe_translations_cover_activation_and_rollback(self) -> None:
        runbook = (ROOT / "docs/ERPNEXT_MASTER_DATA_SYNC_RUNBOOK.md").read_text()
        for marker in (
            "NPI_ERP_AUTHORIZATION_TOKEN",
            "npi_erp_master_data_routes_disabled",
            "npi_erp_master_data_sender_disabled",
            "reconcile_master_catalogs",
            "Frappe/ERPNext majors 15 and 16",
            "Rollback order",
        ):
            self.assertIn(marker, runbook)
        required_sources = (
            "NPI ERP Master Catalog Entry",
            "NPI ERP Master Catalog Head",
            "NPI ERP Master Snapshot",
            "ERPNext master data synchronization is temporarily unavailable.",
            "Exact Master Data Snapshot",
        )
        for locale in ("zh", "zh-TW"):
            catalog = (NPI / f"translations/{locale}.csv").read_text()
            connector_catalog = (ERP / f"translations/{locale}.csv").read_text()
            for source in required_sources:
                self.assertIn(f'"{source}",', catalog)
            self.assertIn('"NPI ERP Master Data Delivery",', connector_catalog)
            self.assertIn(
                '"Master data sender is disabled.",', connector_catalog
            )


if __name__ == "__main__":
    unittest.main()
