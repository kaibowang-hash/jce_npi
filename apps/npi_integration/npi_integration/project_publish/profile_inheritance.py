from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence


def inherited_project_profile(
    values: Sequence[object],
    tenant_id: str,
    project_global_id: str,
    *,
    family: str,
) -> dict[str, object] | None:
    """Derive one exact Project profile only from one bound tenant template."""

    if not _project_is_bound(tenant_id, project_global_id):
        return None
    candidates = [
        dict(value)
        for value in values
        if isinstance(value, Mapping) and value.get("tenantId") == tenant_id
    ]
    if not candidates:
        return None
    frozen = {
        json.dumps(
            {
                key: value
                for key, value in candidate.items()
                if key not in {"profileId", "projectGlobalId"}
            },
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for candidate in candidates
    }
    if len(frozen) != 1:
        raise ValueError("Project execution profile templates are ambiguous.")
    result = dict(candidates[0])
    digest = hashlib.sha256(
        f"{family}:{tenant_id}:{project_global_id}".encode("utf-8")
    ).hexdigest()[:32]
    result["profileId"] = f"{family}-inherited-{digest}"
    result["projectGlobalId"] = project_global_id
    return result


def _project_is_bound(tenant_id: str, project_global_id: str) -> bool:
    try:
        import frappe

        if frappe.db.exists(
            "NPI ERP Project Publish Request",
            {
                "tenant_id": tenant_id,
                "project_global_id": project_global_id,
                "state": "succeeded",
            },
        ):
            return True
        return bool(
            frappe.db.exists(
                "NPI Project Source Binding",
                {
                    "tenant_id": tenant_id,
                    "bound_project_global_id": project_global_id,
                    "source_system": "ERPNEXT",
                    "target_system": "NPI_ONE",
                    "source_object_type": "Project",
                    "stream_state": "bound",
                },
            )
        )
    except (ImportError, AttributeError):
        return False
