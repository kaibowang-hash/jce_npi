from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed, VersionConflict
from npi_integration.authorization_projection.domain import (
    AuthorizationProjectionEvent,
    AuthorizationProjectionError,
    OrganizationScopeKind,
    canonical_hash,
    canonical_json,
    projection_id_for,
    utc_text,
)
from npi_integration.authorization_projection.frappe_validation import (
    authorization_projection_write,
    insert_projection_audit,
    insert_projection_document,
    save_projection_document,
)


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    projection_id: UUID
    source_version: int
    state: str
    projection_hash: str
    exact_replay: bool


class FrappeAuthorizationProjectionRepository:
    def __init__(
        self,
        *,
        actor: str,
        tenant_id: str,
        request_id: UUID,
        now: datetime,
    ) -> None:
        self.actor = actor
        self.tenant_id = tenant_id
        self.request_id = request_id
        self.now = _aware_utc(now)

    def apply(self, event: AuthorizationProjectionEvent) -> ApplyOutcome:
        allowed_roles, max_ttl = _projection_policy()
        _validate_event_policy(
            event,
            now=self.now,
            allowed_roles=allowed_roles,
            max_ttl=max_ttl,
        )
        _require_target_user(event)
        projection_id = event.projection_id(self.tenant_id)
        existing = _locked_projection(projection_id)
        if existing is not None:
            replay = _classify_existing(existing, event)
            if replay is not None:
                return replay
        state = "enabled" if event.enabled else "disabled"
        values = {
            "global_id": str(projection_id),
            "projection_key_hash": event.projection_key_hash(self.tenant_id),
            "tenant_id": self.tenant_id,
            "source_subject_hash": event.source_subject_hash,
            "target_user_id": event.target_user_id,
            "source_version": event.source_version,
            "state": state,
            "roles": canonical_json(list(event.roles)),
            "project_access": canonical_json(
                [scope.mapping() for scope in event.project_scopes]
            ),
            "organization_scopes": canonical_json(
                [scope.mapping() for scope in event.organization_scopes]
            ),
            "source_event_id": str(event.event_id),
            "source_event_hash": event.event_hash,
            "projection_hash": event.projection_hash,
            "issued_at": utc_text(event.issued_at),
            "expires_at": utc_text(event.expires_at),
            "applied_at": utc_text(self.now),
            "source_trace_id": event.trace_id,
            "request_id": str(self.request_id),
        }
        prior_hash = str(getattr(existing, "projection_hash", "")) or None
        with authorization_projection_write(self.actor) as capability:
            if existing is None:
                projection = frappe.get_doc(
                    {"doctype": "NPI Authorization Projection", **values}
                )
                insert_projection_document(projection, capability=capability)
                result = "created" if event.enabled else "disabled"
            else:
                existing.update(values)
                save_projection_document(existing, capability=capability)
                result = "replaced" if event.enabled else "disabled"
            audit = frappe.get_doc(
                {
                    "doctype": "NPI Audit Event",
                    "event_id": str(event.event_id),
                    "global_id": str(projection_id),
                    "object_version": event.source_version,
                    "actor": self.actor,
                    "trace_id": event.trace_id,
                    "operation": "replace_user_authorization_projection",
                    "result": result,
                    "input_summary": {
                        "projectionHash": event.projection_hash,
                        "eventHash": event.event_hash,
                        "priorProjectionHash": prior_hash,
                        "enabled": event.enabled,
                        "roleCount": len(event.roles),
                        "projectScopeCount": len(event.project_scopes),
                        "organizationScopeCount": len(event.organization_scopes),
                    },
                }
            )
            insert_projection_audit(audit, capability=capability)
        return ApplyOutcome(
            projection_id=projection_id,
            source_version=event.source_version,
            state=state,
            projection_hash=event.projection_hash,
            exact_replay=False,
        )


def resolve_authorization_projection(
    user_id: str,
    tenant_id: str,
    now: datetime,
) -> dict[str, object] | None:
    """Return one validated current projection to the core principal resolver."""

    projection_id = _projection_id(tenant_id, user_id)
    row = frappe.db.get_value(
        "NPI Authorization Projection",
        str(projection_id),
        [
            "global_id",
            "projection_key_hash",
            "tenant_id",
            "source_subject_hash",
            "target_user_id",
            "source_version",
            "state",
            "roles",
            "project_access",
            "organization_scopes",
            "issued_at",
            "expires_at",
            "projection_hash",
        ],
        as_dict=True,
    )
    if not row:
        return None
    try:
        roles = _json_list(row.get("roles"))
        project_scopes = _json_list(row.get("project_access"))
        organization_scopes = _json_list(row.get("organization_scopes"))
        source_version = int(row.get("source_version"))
        state = str(row.get("state"))
        expires_at = _stored_utc(row.get("expires_at"))
        issued_at = _stored_utc(row.get("issued_at"))
        source_subject_hash = str(row.get("source_subject_hash"))
        expected_hash = canonical_hash(
            {
                "sourceSubjectHash": source_subject_hash,
                "targetUserId": user_id,
                "sourceVersion": source_version,
                "enabled": state == "enabled",
                "roles": roles,
                "projectAccess": project_scopes,
                "organizationScopes": organization_scopes,
                "issuedAt": utc_text(issued_at),
                "expiresAt": utc_text(expires_at),
            }
        )
        if (
            str(row.get("global_id")) != str(projection_id)
            or str(row.get("projection_key_hash"))
            != _projection_key_hash(tenant_id, user_id)
            or str(row.get("tenant_id")) != tenant_id
            or str(row.get("target_user_id")) != user_id
            or source_version < 1
            or state not in {"enabled", "disabled"}
            or str(row.get("projection_hash")) != expected_hash
        ):
            return None
        allowed_roles, _max_ttl = _projection_policy()
        role_set = tuple(str(role) for role in roles)
        if (
            tuple(sorted(set(role_set))) != role_set
            or not set(role_set).issubset(allowed_roles)
        ):
            return None
        project_access = _project_access(project_scopes)
        organizations = _organization_access(organization_scopes)
    except (AttributeError, TypeError, ValueError, AuthorizationProjectionError):
        return None
    current = _aware_utc(now)
    if state != "enabled" or expires_at <= current:
        return None
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "enabled": True,
        "expires_at": expires_at,
        "roles": role_set,
        "project_access": project_access,
        "organization_scopes": organizations,
        "projection_hash": expected_hash,
    }


def _classify_existing(
    existing: Any,
    event: AuthorizationProjectionEvent,
) -> ApplyOutcome | None:
    existing_event_id = str(getattr(existing, "source_event_id", ""))
    existing_event_hash = str(getattr(existing, "source_event_hash", ""))
    if existing_event_id == str(event.event_id):
        if existing_event_hash != event.event_hash:
            raise VersionConflict()
        return ApplyOutcome(
            projection_id=UUID(str(existing.global_id)),
            source_version=int(existing.source_version),
            state=str(existing.state),
            projection_hash=str(existing.projection_hash),
            exact_replay=True,
        )
    if (
        str(getattr(existing, "source_subject_hash", ""))
        != event.source_subject_hash
        or str(getattr(existing, "target_user_id", "")) != event.target_user_id
        or event.source_version <= int(getattr(existing, "source_version", 0))
        or event.issued_at < _stored_utc(getattr(existing, "issued_at", None))
    ):
        raise VersionConflict()
    return None


def _validate_event_policy(
    event: AuthorizationProjectionEvent,
    *,
    now: datetime,
    allowed_roles: frozenset[str],
    max_ttl: timedelta,
) -> None:
    if not set(event.roles).issubset(allowed_roles):
        raise PermissionDenied()
    if event.issued_at > now + timedelta(minutes=5) or event.expires_at <= now:
        raise RequestValidationFailed(
            [
                {
                    "path": "expiresAt",
                    "message": _("Enter a current authorization window."),
                }
            ]
        )
    if event.expires_at - event.issued_at > max_ttl:
        raise RequestValidationFailed(
            [
                {
                    "path": "expiresAt",
                    "message": _("Enter an allowed authorization window."),
                }
            ]
        )


def _projection_policy() -> tuple[frozenset[str], timedelta]:
    configuration = getattr(frappe, "conf", None)
    roles = (
        configuration.get("npi_p9_04_authorization_role_allowlist")
        if hasattr(configuration, "get")
        else None
    )
    ttl = (
        configuration.get("npi_p9_04_authorization_max_ttl_seconds")
        if hasattr(configuration, "get")
        else None
    )
    if (
        not isinstance(roles, (list, tuple))
        or not roles
        or any(not isinstance(role, str) or not role for role in roles)
        or tuple(sorted(set(roles))) != tuple(roles)
        or type(ttl) is not int
        or ttl < 300
        or ttl > 86_400
    ):
        raise RuntimeError("Authorization projection policy is unavailable.")
    return frozenset(roles), timedelta(seconds=ttl)


def _require_target_user(event: AuthorizationProjectionEvent) -> None:
    record = frappe.db.get_value(
        "User",
        event.target_user_id,
        ["enabled", "user_type"],
        as_dict=True,
    )
    enabled = record.get("enabled") if hasattr(record, "get") else None
    user_type = record.get("user_type") if hasattr(record, "get") else None
    if (
        not record
        or user_type != "System User"
        or (event.enabled and int(enabled or 0) != 1)
    ):
        raise PermissionDenied()


def _locked_projection(projection_id: UUID) -> Any | None:
    try:
        return frappe.get_doc(
            "NPI Authorization Projection",
            str(projection_id),
            for_update=True,
        )
    except frappe.DoesNotExistError:
        return None


def _projection_id(tenant_id: str, user_id: str) -> UUID:
    return projection_id_for(tenant_id, user_id)


def _projection_key_hash(tenant_id: str, user_id: str) -> str:
    return canonical_hash({"tenantId": tenant_id, "targetUserId": user_id})


def _json_list(value: object) -> list[object]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError("Projection JSON is invalid.")
    return value


def _project_access(value: list[object]) -> dict[str, str]:
    result: dict[str, str] = {}
    allowed = {"view", "contribute", "approve", "administer"}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"projectId", "access"}:
            raise ValueError("Project access is invalid.")
        project_id = str(UUID(str(item["projectId"])))
        access = str(item["access"])
        if project_id in result or access not in allowed:
            raise ValueError("Project access is invalid.")
        result[project_id] = access
    return result


def _organization_access(value: list[object]) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {
        kind.value: [] for kind in OrganizationScopeKind
    }
    for item in value:
        if not isinstance(item, dict) or set(item) != {"kind", "referenceKey"}:
            raise ValueError("Organization access is invalid.")
        kind = OrganizationScopeKind(item["kind"]).value
        reference = str(item["referenceKey"])
        if not reference or reference in result[kind]:
            raise ValueError("Organization access is invalid.")
        result[kind].append(reference)
    return {kind: tuple(values) for kind, values in result.items()}


def _stored_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    else:
        raise ValueError("Stored projection time is invalid.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Server time must be timezone-aware.")
    return value.astimezone(UTC)
