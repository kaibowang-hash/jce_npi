from __future__ import annotations

import frappe


def execute() -> None:
    for doctype in (
        "npi_erp_master_snapshot",
        "npi_erp_master_catalog_head",
        "npi_erp_master_catalog_entry",
    ):
        frappe.reload_doc("npi_integration", "doctype", doctype, force=True)
