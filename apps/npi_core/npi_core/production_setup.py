from __future__ import annotations

import frappe


def enforce_production_auth_settings() -> None:
    """Disable public signup for the production LaunchFlow Site."""

    frappe.db.set_single_value("Website Settings", "disable_signup", 1)
    frappe.db.commit()
