from __future__ import annotations

from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:
    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


def erp_source_id(value: object, path: str) -> str:
    """Preserve the authoritative ERP name, including spaces and Unicode."""
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise RequestValidationFailed([
            {"path": path, "message": _("Enter a valid value.")}
        ])
    return value


def require_erp_catalog_reference(kind: str, source_key: str, path: str) -> None:
    """Validate new choices when ERP master-data integration is activated.

    Installations without this integration retain the governed-reference flow.
    An activated integration never falls back on missing/stale catalog data.
    """
    import frappe

    if getattr(frappe, "conf", {}).get("npi_erp_master_data_routes_disabled") is not False:
        return
    from npi_core.request_security import authenticated_principal
    from npi_integration.master_data.selection import require_catalog_choice

    require_catalog_choice(authenticated_principal(), kind, source_key, path)
