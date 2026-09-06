from __future__ import annotations

import frappe


def execute() -> None:
    for doctype in (
        "npi_erp_project_publish_mapping",
        "npi_erp_project_publish_receipt",
    ):
        frappe.reload_doc("npi_erpnext_connector", "doctype", doctype, force=True)
