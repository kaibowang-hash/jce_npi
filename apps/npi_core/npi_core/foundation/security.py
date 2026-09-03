from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .errors import AuthenticationRequired, PermissionDenied


class ProjectAccess(StrEnum):
    VIEW = "view"
    CONTRIBUTE = "contribute"
    APPROVE = "approve"
    ADMINISTER = "administer"


ACCESS_RANK = {
    ProjectAccess.VIEW: 1,
    ProjectAccess.CONTRIBUTE: 2,
    ProjectAccess.APPROVE: 3,
    ProjectAccess.ADMINISTER: 4,
}


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    project_access: dict[str, ProjectAccess] = field(default_factory=dict)
    is_external: bool = False
    tenant_id: str | None = None
    organization_scopes: dict[str, frozenset[str]] = field(default_factory=dict)


def authorize_project(
    principal: Principal | None,
    project_id: str,
    required: ProjectAccess,
    *,
    project_tenant_id: str | None = None,
) -> None:
    _require_authenticated(principal)
    if project_tenant_id:
        authorize_tenant(principal, project_tenant_id)
    assert principal is not None
    granted = principal.project_access.get(project_id)
    if granted is None or ACCESS_RANK[granted] < ACCESS_RANK[required]:
        raise PermissionDenied()
    if principal.is_external and required in {ProjectAccess.APPROVE, ProjectAccess.ADMINISTER}:
        raise PermissionDenied()


def authorize_tenant(principal: Principal | None, tenant_id: str) -> None:
    _require_authenticated(principal)
    assert principal is not None
    if not tenant_id or principal.tenant_id != tenant_id:
        raise PermissionDenied()


def authorize_organization(
    principal: Principal | None,
    kind: str,
    reference: str,
) -> None:
    """Require one exact ERP-owned Company, Customer, or Supplier grant."""
    _require_authenticated(principal)
    assert principal is not None
    if (
        kind not in {"Company", "Customer", "Supplier"}
        or not reference
        or reference not in principal.organization_scopes.get(kind, frozenset())
    ):
        raise PermissionDenied()


def _require_authenticated(principal: Principal | None) -> None:
    if principal is None or not principal.user_id or principal.user_id == "Guest":
        raise AuthenticationRequired()
