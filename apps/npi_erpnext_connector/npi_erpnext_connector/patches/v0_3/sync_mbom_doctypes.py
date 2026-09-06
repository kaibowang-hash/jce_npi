from __future__ import annotations

import frappe


_MBOM_DOCTYPES = (
    "npi_erp_mbom_mapping",
    "npi_erp_mbom_operation_receipt",
)


def execute() -> None:
    for doctype in _MBOM_DOCTYPES:
        frappe.reload_doc(
            "npi_erpnext_connector",
            "doctype",
            doctype,
            force=True,
        )
