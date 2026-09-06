from __future__ import annotations

import frappe


def execute() -> None:
    frappe.reload_doc(
        "npi_erpnext_connector",
        "doctype",
        "npi_erp_master_data_delivery",
        force=True,
    )
