from __future__ import annotations

import frappe

from npi_integration.trial_summary_publish.service import create_delivery_for_summary

SOURCE_DOCTYPE = "NPI Released Trial Summary Revision"
PAGE_SIZE = 100


def execute() -> None:
    """Create missing Outbox rows without contacting or enqueueing ERPNext."""

    start = 0
    while True:
        names = frappe.get_all(
            SOURCE_DOCTYPE,
            pluck="name",
            order_by="name asc",
            start=start,
            page_length=PAGE_SIZE,
        )
        if not names:
            return
        for name in names:
            create_delivery_for_summary(
                frappe.get_doc(SOURCE_DOCTYPE, str(name)),
                enqueue=False,
            )
        start += len(names)
