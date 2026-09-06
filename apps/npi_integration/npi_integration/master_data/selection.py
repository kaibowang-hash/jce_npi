from __future__ import annotations

from datetime import UTC, datetime

from frappe import _

from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_integration.master_data.domain import MasterCatalogKind
from npi_integration.master_data.frappe_repository import catalog_collection


def require_catalog_choice(principal, kind: str, source_key: str, path: str) -> dict:
    from npi_integration.master_data_api import _allowed_source_keys

    if principal.is_external:
        raise PermissionDenied()
    selected_kind = MasterCatalogKind(kind)
    allowed = _allowed_source_keys(principal, selected_kind)
    page = catalog_collection(
        tenant_id=str(principal.tenant_id), kind=selected_kind,
        query=None, limit=1, offset=0,
        allowed_source_keys=frozenset({source_key}) if allowed is None or source_key in allowed else frozenset(),
    )
    synchronized = page["lastSynchronizedAt"]
    age = (datetime.now(UTC) - datetime.fromisoformat(synchronized.replace("Z", "+00:00"))).total_seconds() if synchronized else None
    rows = page["items"]
    if age is None or not -300 <= age <= 86400 or len(rows) != 1 or not rows[0]["enabled"] or rows[0]["sourceKey"] != source_key:
        raise RequestValidationFailed([{
            "path": path,
            "message": _("Select an available ERPNext record after refreshing the choices."),
        }])
    return rows[0]
