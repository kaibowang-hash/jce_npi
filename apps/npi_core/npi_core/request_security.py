from __future__ import annotations

import secrets
import re
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
    RequestValidationFailed,
    TenantScopeUnavailable,
    ToolingRoutesDisabled,
    ToolingSetRoutesDisabled,
)
from .foundation.security import Principal

TRANSPORT_FIELDS = frozenset({"cmd"})
TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


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
    return Principal(
        user_id=actor,
        roles=frozenset(frappe.get_roles(actor)),
        is_external=user_type != "System User",
        tenant_id=tenant_id,
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
