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


def authorize_project(
    principal: Principal | None,
    project_id: str,
    required: ProjectAccess,
    *,
    project_tenant_id: str | None = None,
) -> None:
    if principal is None or not principal.user_id or principal.user_id == "Guest":
        raise AuthenticationRequired()
    if project_tenant_id and principal.tenant_id != project_tenant_id:
        raise PermissionDenied()
    granted = principal.project_access.get(project_id)
    if granted is None or ACCESS_RANK[granted] < ACCESS_RANK[required]:
        raise PermissionDenied()
    if principal.is_external and required in {ProjectAccess.APPROVE, ProjectAccess.ADMINISTER}:
        raise PermissionDenied()
