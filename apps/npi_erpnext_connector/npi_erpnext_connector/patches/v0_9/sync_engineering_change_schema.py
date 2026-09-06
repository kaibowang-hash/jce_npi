from __future__ import annotations

import frappe


def execute() -> None:
    frappe.reload_doc(
        "npi_erpnext_connector",
        "doctype",
        "npi_erp_change_implementation_summary",
        force=True,
    )
