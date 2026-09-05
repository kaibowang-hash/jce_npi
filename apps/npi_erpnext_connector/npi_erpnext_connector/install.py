from __future__ import annotations

import frappe

from npi_erpnext_connector.patches.v0_4.sync_tool_asset_schema import (
    sync_tool_asset_schema,
)


_CONNECTOR_DOCTYPES = (
    "npi_erp_authorization_delivery",
    "npi_erp_item_mapping",
    "npi_erp_item_operation_receipt",
    "npi_erp_mbom_mapping",
    "npi_erp_mbom_operation_receipt",
    "npi_erp_tool_asset_mapping",
    "npi_erp_tool_asset_operation_receipt",
    "npi_erp_project_delivery",
    "npi_erp_project_mapping",
    "npi_erp_trial_summary",
    "npi_erp_trial_summary_fact",
)


def after_install() -> None:
    """Close a Frappe 16 first-install module-map gap with bounded reloads."""

    sync_tool_asset_schema(reload_support_doctypes=False)
    for doctype in _CONNECTOR_DOCTYPES:
        frappe.reload_doc(
            "npi_erpnext_connector",
            "doctype",
            doctype,
            force=True,
        )
