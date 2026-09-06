from __future__ import annotations

import frappe

_DOCTYPES = (
    "npi_erp_trial_summary",
    "npi_erp_trial_summary_fact",
)


def execute() -> None:
    for doctype in _DOCTYPES:
        frappe.reload_doc(
            "npi_erpnext_connector",
            "doctype",
            doctype,
            force=True,
        )
