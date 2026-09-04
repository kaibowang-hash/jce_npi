from __future__ import annotations

import secrets
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from .foundation.errors import (
    AuthenticationRequired,
    CsrfTokenInvalid,
    ControlledPrintRoutesDisabled,
    DocumentBaselineRoutesDisabled,
    DocumentReleaseRoutesDisabled,
    DocumentRoutesDisabled,
    EngineeringBomRoutesDisabled,
    PublishRequestRoutesDisabled,
    ProjectCollaborationRoutesDisabled,
    ReportingRoutesDisabled,
    RequestValidationFailed,
    TenantScopeUnavailable,
    TrialRoutesDisabled,
    ToolingEngineeringControlsRoutesDisabled,
    ToolingAcceptanceAssetsRoutesDisabled,
    ToolingImportRoutesDisabled,
    ToolingExportRoutesDisabled,
    ToolingRoutesDisabled,
    ToolingManufacturingRoutesDisabled,
    ToolingRevisionRoutesDisabled,
    ToolingSetRoutesDisabled,
)
from .foundation.security import Principal, ProjectAccess

TRANSPORT_FIELDS = frozenset({"cmd"})
TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


def reporting_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P9-02 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p9_02_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_reporting_routes_enabled() -> None:
    if reporting_routes_are_disabled():
        raise ReportingRoutesDisabled()


def tooling_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P6-01 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_01_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_routes_enabled() -> None:
    """Keep P6-01 handlers closed unless the Site explicitly enables them."""

    if tooling_routes_are_disabled():
        raise ToolingRoutesDisabled()


def tooling_set_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P6-02 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_02_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_set_routes_enabled() -> None:
    """Keep only P6-02 Set/intake handlers closed unless explicitly enabled."""

    if tooling_set_routes_are_disabled():
        raise ToolingSetRoutesDisabled()


def tooling_revision_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P6-03 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_03_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_revision_routes_enabled() -> None:
    """Keep only P6-03 Revision handlers closed unless explicitly enabled."""

    if tooling_revision_routes_are_disabled():
        raise ToolingRevisionRoutesDisabled()


def tooling_manufacturing_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P6-04 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_04_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_manufacturing_routes_enabled() -> None:
    """Keep only P6-04 manufacturing handlers closed unless explicitly enabled."""

    if tooling_manufacturing_routes_are_disabled():
        raise ToolingManufacturingRoutesDisabled()


def tooling_engineering_controls_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P6-05 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_05_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_engineering_controls_routes_enabled() -> None:
    """Keep only P6-05 engineering-control handlers explicitly enabled."""

    if tooling_engineering_controls_routes_are_disabled():
        raise ToolingEngineeringControlsRoutesDisabled()


def tooling_acceptance_assets_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P6-06 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_06_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_acceptance_assets_routes_enabled() -> None:
    """Keep P6-06 evidence and Mock-request handlers explicitly enabled."""

    if tooling_acceptance_assets_routes_are_disabled():
        raise ToolingAcceptanceAssetsRoutesDisabled()


def tooling_import_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P6-07 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_07_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_import_routes_enabled() -> None:
    """Keep P6-07 import metadata handlers closed unless explicitly enabled."""

    if tooling_import_routes_are_disabled():
        raise ToolingImportRoutesDisabled()


def tooling_export_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P6-08 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p6_08_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_tooling_export_routes_enabled() -> None:
    """Keep P6-08 Tooling List/export handlers closed unless explicitly enabled."""

    if tooling_export_routes_are_disabled():
        raise ToolingExportRoutesDisabled()


def trial_routes_are_disabled() -> bool:
    """Read the independent Site-scoped P7-01 fail-closed route switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_01_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def require_trial_routes_enabled() -> None:
    """Keep P7-01 Trial planning handlers closed unless explicitly enabled."""

    if trial_routes_are_disabled():
        raise TrialRoutesDisabled()


def controlled_print_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P5-06 emergency switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p5_06_routes_disabled")
        if hasattr(configuration, "get")
        else False
    )
    return value is True


def require_controlled_print_routes_enabled() -> None:
    """Close only P5-06 handlers while retaining prior Phase 5 routes."""

    if controlled_print_routes_are_disabled():
        raise ControlledPrintRoutesDisabled()


def document_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P5-01 emergency switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p5_01_routes_disabled")
        if hasattr(configuration, "get")
        else False
    )
    return value is True


def require_document_routes_enabled() -> None:
    """Close P5-01 handlers even when generic Frappe routing is attempted."""

    if document_routes_are_disabled():
        raise DocumentRoutesDisabled()


def document_release_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P5-02 emergency switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p5_02_routes_disabled")
        if hasattr(configuration, "get")
        else False
    )
    return value is True


def require_document_release_routes_enabled() -> None:
    """Close P5-02 handlers without disabling retained P5-01 routes."""

    if document_release_routes_are_disabled():
        raise DocumentReleaseRoutesDisabled()


def document_baseline_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P5-03 emergency switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p5_03_routes_disabled")
        if hasattr(configuration, "get")
        else False
    )
    return value is True


def require_document_baseline_routes_enabled() -> None:
    """Close P5-03 handlers without disabling retained P5-01/P5-02 routes."""

    if document_baseline_routes_are_disabled():
        raise DocumentBaselineRoutesDisabled()


def engineering_bom_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P5-04 emergency switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p5_04_routes_disabled")
        if hasattr(configuration, "get")
        else False
    )
    return value is True


def require_engineering_bom_routes_enabled() -> None:
    """Close only P5-04 handlers while retaining earlier Phase 5 routes."""

    if engineering_bom_routes_are_disabled():
        raise EngineeringBomRoutesDisabled()


def publish_request_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P5-05 emergency switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p5_05_routes_disabled")
        if hasattr(configuration, "get")
        else False
    )
    return value is True


def require_publish_request_routes_enabled() -> None:
    """Close only P5-05 handlers while retaining P5-04 EBOM routes."""

    if publish_request_routes_are_disabled():
        raise PublishRequestRoutesDisabled()


def project_collaboration_routes_are_disabled() -> bool:
    """Read the exact Site-scoped P4-05 emergency switch."""

    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p4_05_routes_disabled")
        if hasattr(configuration, "get")
        else False
    )
    return value is True


def require_project_collaboration_routes_enabled() -> None:
    """Close P4-05 handlers even when generic Frappe routing is attempted."""

    if project_collaboration_routes_are_disabled():
        raise ProjectCollaborationRoutesDisabled()


def response_request_id() -> str:
    """Return a canonical response correlation ID without trusting bad input."""
    import frappe

    candidate = frappe.get_request_header("X-Request-ID")
    if isinstance(candidate, str):
        try:
            parsed = UUID(candidate)
        except (ValueError, AttributeError):
            pass
        else:
            if str(parsed) == candidate.casefold():
                return str(parsed)
    return str(uuid4())


def authenticated_user() -> str:
    """Return the current authenticated user without treating Guest as a user."""
    import frappe

    user_id = frappe.session.user
    if not user_id or user_id == "Guest":
        raise AuthenticationRequired()
    return user_id


def authenticated_principal(user_id: str | None = None) -> Principal:
    """Resolve a Frappe session into the configured Site tenant boundary."""
    import frappe

    actor = user_id or authenticated_user()
    tenant_id = configured_tenant_id()
    user_type = frappe.db.get_value("User", actor, "user_type")
    if user_type not in {"System User", "Website User"}:
        raise AuthenticationRequired()
    if authorization_projection_enforcement_enabled():
        enabled = frappe.db.get_value("User", actor, "enabled")
        if enabled != 1:
            raise AuthenticationRequired()
        return _projected_principal(actor, tenant_id, user_type)
    return Principal(
        user_id=actor,
        roles=frozenset(frappe.get_roles(actor)),
        is_external=user_type != "System User",
        tenant_id=tenant_id,
    )


def authorization_projection_enforcement_enabled() -> bool:
    """Activate ERP-owned interactive authorization only by explicit Site policy."""
    import frappe

    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p9_04_authorization_projection_enforced")
        if hasattr(configuration, "get")
        else None
    )
    return value is True


def _projected_principal(
    actor: str,
    tenant_id: str,
    user_type: str,
) -> Principal:
    import frappe

    hooks = frappe.get_hooks("npi_authorization_projection_resolver")
    values = [hooks] if isinstance(hooks, str) else list(hooks or ())
    if len(values) != 1 or not isinstance(values[0], str):
        raise AuthenticationRequired()
    resolver = frappe.get_attr(values[0])
    if not callable(resolver):
        raise AuthenticationRequired()
    now = datetime.now(UTC)
    try:
        projection = resolver(actor, tenant_id, now)
    except Exception as error:
        raise AuthenticationRequired() from error
    if not isinstance(projection, dict) or set(projection) != {
        "user_id",
        "tenant_id",
        "enabled",
        "expires_at",
        "roles",
        "project_access",
        "organization_scopes",
        "projection_hash",
    }:
        raise AuthenticationRequired()
    expires_at = projection["expires_at"]
    roles = projection["roles"]
    access = projection["project_access"]
    organizations = projection["organization_scopes"]
    projection_hash = projection["projection_hash"]
    if (
        projection["user_id"] != actor
        or projection["tenant_id"] != tenant_id
        or projection["enabled"] is not True
        or not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.astimezone(UTC) <= now
        or not isinstance(roles, (tuple, list))
        or any(not isinstance(role, str) or not role for role in roles)
        or tuple(sorted(set(roles))) != tuple(roles)
        or not isinstance(access, dict)
        or not isinstance(organizations, dict)
        or not isinstance(projection_hash, str)
        or re.fullmatch(r"[a-f0-9]{64}", projection_hash) is None
    ):
        raise AuthenticationRequired()
    try:
        project_access = {
            str(UUID(str(project_id))): ProjectAccess(value)
            for project_id, value in access.items()
        }
        organization_scopes = {
            str(kind): frozenset(str(reference) for reference in references)
            for kind, references in organizations.items()
        }
    except (TypeError, ValueError):
        raise AuthenticationRequired() from None
    if (
        any(not project_id for project_id in project_access)
        or any(
            not isinstance(project_id, str)
            or str(UUID(project_id)) != project_id.casefold()
            for project_id in access
        )
        or set(organization_scopes) != {"Company", "Customer", "Supplier"}
        or any(
            not isinstance(references, (tuple, list))
            or any(not isinstance(reference, str) or not reference for reference in references)
            or len(set(references)) != len(references)
            for references in organizations.values()
        )
    ):
        raise AuthenticationRequired()
    return Principal(
        user_id=actor,
        roles=frozenset(roles),
        project_access=project_access,
        is_external=user_type != "System User",
        tenant_id=tenant_id,
        organization_scopes=organization_scopes,
    )


def configured_tenant_id() -> str:
    """Return the explicit per-Site tenant identifier or fail closed."""
    import frappe

    configuration = getattr(frappe, "conf", None)
    tenant_id = (
        configuration.get("npi_tenant_id") if hasattr(configuration, "get") else None
    )
    if not isinstance(tenant_id, str) or TENANT_ID_PATTERN.fullmatch(tenant_id) is None:
        raise TenantScopeUnavailable()
    return tenant_id


def reject_unexpected_request_fields(
    allowed_fields: frozenset[str], request_fields: dict[str, Any]
) -> None:
    """Reject query/body fields outside an endpoint's explicit contract."""
    import frappe
    from frappe import _

    form_dict = getattr(getattr(frappe, "local", None), "form_dict", None)
    field_names = set(form_dict.keys()) if hasattr(form_dict, "keys") else set()
    field_names.update(request_fields)
    unexpected_fields = sorted(field_names - allowed_fields - TRANSPORT_FIELDS)
    if unexpected_fields:
        raise RequestValidationFailed(
            [
                {"path": field, "message": _("This field is not allowed.")}
                for field in unexpected_fields
            ]
        )


def require_request_fields(
    required_fields: frozenset[str], request_fields: dict[str, Any]
) -> None:
    """Require explicit request keys while preserving explicit null values."""
    import frappe
    from frappe import _

    form_dict = getattr(getattr(frappe, "local", None), "form_dict", None)
    field_names = set(form_dict.keys()) if hasattr(form_dict, "keys") else set()
    field_names.update(request_fields)
    missing_fields = sorted(required_fields - field_names)
    if missing_fields:
        raise RequestValidationFailed(
            [
                {"path": field, "message": _("This field is required.")}
                for field in missing_fields
            ]
        )


def require_csrf_token() -> None:
    """Fail closed when an unsafe BFF request lacks the session CSRF token."""
    import frappe
    from frappe.sessions import get_csrf_token

    expected_token = get_csrf_token()
    supplied_token = frappe.get_request_header("X-Frappe-CSRF-Token")
    if (
        not isinstance(expected_token, str)
        or not isinstance(supplied_token, str)
        or not secrets.compare_digest(supplied_token, expected_token)
    ):
        raise CsrfTokenInvalid()
