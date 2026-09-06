from __future__ import annotations

import frappe


_DOCTYPES = (
    "npi_erp_project_publish_request",
    "npi_erp_project_publish_attempt",
    "npi_erp_project_publish_result",
)


def execute() -> None:
    for doctype in _DOCTYPES:
        frappe.reload_doc("npi_integration", "doctype", doctype, force=True)
    from npi_integration.project_publish.service import create_request_for_project

    rows = frappe.get_all(
        "NPI Engineering Project",
        fields=["name"],
        order_by="creation asc, name asc",
        page_length=10_001,
    )
    if len(rows) > 10_000:
        raise RuntimeError("Engineering Project publication backfill exceeds its fixed bound.")
    for row in rows:
        create_request_for_project(
            frappe.get_doc("NPI Engineering Project", str(row["name"])),
            enqueue=False,
        )
