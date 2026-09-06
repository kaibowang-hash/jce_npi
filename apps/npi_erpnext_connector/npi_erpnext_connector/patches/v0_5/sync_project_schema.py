from __future__ import annotations

import frappe


def execute() -> None:
    sync_project_schema()


def sync_project_schema() -> None:
    for doctype in (
        "npi_erp_project_delivery",
        "npi_erp_project_mapping",
    ):
        frappe.reload_doc(
            "npi_erpnext_connector",
            "doctype",
            doctype,
            force=True,
        )
