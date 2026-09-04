from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid5


SCHEMA_VERSION = 1
OPERATION = "replace_user_authorization"
SOURCE_SYSTEM = "ERPNEXT"
TARGET_SYSTEM = "NPI_ONE"
OBJECT_TYPE = "UserAuthorizationProjection"
MAX_ROLES = 32
MAX_PROJECT_SCOPES = 256
MAX_ORGANIZATION_SCOPES = 256
MIN_TTL_SECONDS = 300
MAX_TTL_SECONDS = 86_400
EVENT_NAMESPACE = UUID("9fef7070-1c92-445c-a2d1-4ec68eb0af85")
REQUEST_NAMESPACE = UUID("41547ac0-e9e4-4571-9cae-c4d72e54ff57")
_EMAIL = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
_ROLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./:&()-]{0,127}$")
_REFERENCE = re.compile(r"^[^\s\x00-\x1f\x7f]{1,255}$")


class AuthorizationSenderError(ValueError):
    """Raised when sender policy or source truth is not contract-safe."""


class MappingIncomplete(AuthorizationSenderError):
    """Raised when an enabled source cannot be represented without guessing."""


class ProjectAccess(StrEnum):
    VIEW = "view"
    CONTRIBUTE = "contribute"
    APPROVE = "approve"
    ADMINISTER = "administer"


_ACCESS_RANK = {
    ProjectAccess.VIEW: 0,
    ProjectAccess.CONTRIBUTE: 1,
    ProjectAccess.APPROVE: 2,
    ProjectAccess.ADMINISTER: 3,
}


class OrganizationScopeKind(StrEnum):
    COMPANY = "Company"
    CUSTOMER = "Customer"
    SUPPLIER = "Supplier"


@dataclass(frozen=True, slots=True, order=True)
class SourcePermission:
    kind: str
    reference_key: str

    def __post_init__(self) -> None:
        if self.kind not in {"Project", *(kind.value for kind in OrganizationScopeKind)}:
            raise AuthorizationSenderError("User Permission kind is unsupported.")
        _reference(self.reference_key, "User Permission reference")


@dataclass(frozen=True, slots=True)
class SourceUser:
    source_subject_id: str
    target_user_id: str
    enabled: bool
    user_type: str
    roles: tuple[str, ...]
    permissions: tuple[SourcePermission, ...]

    def __post_init__(self) -> None:
        target = _email(self.target_user_id)
        if self.source_subject_id != target:
            raise MappingIncomplete(
                "ERPNext User name and canonical email identity do not match."
            )
        if type(self.enabled) is not bool or self.user_type not in {
            "System User",
            "Website User",
        }:
            raise AuthorizationSenderError("ERPNext User state is invalid.")
        if tuple(sorted(set(self.roles))) != self.roles:
            raise AuthorizationSenderError("ERPNext roles must be unique and sorted.")
        for role in self.roles:
            _role(role, "ERPNext role")
        if tuple(sorted(set(self.permissions))) != self.permissions:
            raise AuthorizationSenderError(
                "ERPNext User Permissions must be unique and sorted."
            )


@dataclass(frozen=True, slots=True)
class SenderPolicy:
    role_map: Mapping[str, str]
    project_map: Mapping[str, UUID]
    project_access_by_role: Mapping[str, ProjectAccess]
    ttl_seconds: int

    @classmethod
    def from_mapping(cls, value: object) -> SenderPolicy:
        source = _closed(
            value,
            {"roleMap", "projectMap", "projectAccessByRole", "ttlSeconds"},
        )
        role_map = _string_map(source["roleMap"], "roleMap")
        if not role_map or len(role_map) > 128:
            raise AuthorizationSenderError("Role mapping is required and bounded.")
        for source_role, target_role in role_map.items():
            _role(source_role, "ERPNext role")
            _role(target_role, "LaunchFlow role")

        raw_project_map = _string_map(source["projectMap"], "projectMap")
        if len(raw_project_map) > MAX_PROJECT_SCOPES:
            raise AuthorizationSenderError("Project mapping is too large.")
        project_map: dict[str, UUID] = {}
        for source_project, target_project in raw_project_map.items():
            _reference(source_project, "ERPNext Project")
            project_map[source_project] = _canonical_uuid(
                target_project,
                "LaunchFlow Project",
            )

        raw_access_map = _string_map(
            source["projectAccessByRole"],
            "projectAccessByRole",
        )
        access_map: dict[str, ProjectAccess] = {}
        for source_role, access in raw_access_map.items():
            _role(source_role, "ERPNext role")
            if source_role not in role_map:
                raise AuthorizationSenderError(
                    "Project access role must also exist in role mapping."
                )
            try:
                access_map[source_role] = ProjectAccess(access)
            except ValueError as error:
                raise AuthorizationSenderError(
                    "Project access mapping is invalid."
                ) from error

        ttl_seconds = source["ttlSeconds"]
        if (
            type(ttl_seconds) is not int
            or ttl_seconds < MIN_TTL_SECONDS
            or ttl_seconds > MAX_TTL_SECONDS
        ):
            raise AuthorizationSenderError("Projection validity window is invalid.")
        return cls(role_map, project_map, access_map, ttl_seconds)


@dataclass(frozen=True, slots=True)
class AuthorizationSnapshot:
    source_subject_id: str
    target_user_id: str
    enabled: bool
    roles: tuple[str, ...]
    project_access: tuple[tuple[str, str], ...]
    organization_scopes: tuple[tuple[str, str], ...]

    def mapping(self) -> dict[str, object]:
        return {
            "sourceSubjectId": self.source_subject_id,
            "targetUserId": self.target_user_id,
            "enabled": self.enabled,
            "roles": list(self.roles),
            "projectAccess": [
                {"projectId": project_id, "access": access}
                for project_id, access in self.project_access
            ],
            "organizationScopes": [
                {"kind": kind, "referenceKey": reference}
                for kind, reference in self.organization_scopes
            ],
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.mapping())


@dataclass(frozen=True, slots=True)
class AuthorizationEvent:
    event: Mapping[str, object]
    request_id: UUID
    snapshot_hash: str

    @property
    def event_id(self) -> UUID:
        return UUID(str(self.event["eventId"]))

    @property
    def trace_id(self) -> str:
        return str(self.event["traceId"])

    @property
    def expires_at(self) -> datetime:
        return datetime.strptime(
            str(self.event["expiresAt"]),
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=UTC)

    @property
    def event_hash(self) -> str:
        return canonical_hash(self.event)


def project_source_user(source: SourceUser, policy: SenderPolicy) -> AuthorizationSnapshot:
    mapped_roles = tuple(
        sorted({policy.role_map[role] for role in source.roles if role in policy.role_map})
    )
    is_enabled = (
        source.enabled
        and source.user_type == "System User"
        and bool(mapped_roles)
    )
    if not is_enabled:
        return AuthorizationSnapshot(
            source.source_subject_id,
            source.target_user_id,
            False,
            (),
            (),
            (),
        )
    if len(mapped_roles) > MAX_ROLES:
        raise AuthorizationSenderError("Mapped LaunchFlow roles are too large.")

    project_permissions = tuple(
        permission for permission in source.permissions if permission.kind == "Project"
    )
    access_values = tuple(
        policy.project_access_by_role[role]
        for role in source.roles
        if role in policy.project_access_by_role
    )
    if project_permissions and not access_values:
        raise MappingIncomplete(
            "Project User Permissions exist without an approved access mapping."
        )
    access = (
        max(access_values, key=_ACCESS_RANK.__getitem__).value
        if access_values
        else None
    )
    project_access: list[tuple[str, str]] = []
    for permission in project_permissions:
        project_id = policy.project_map.get(permission.reference_key)
        if project_id is None:
            raise MappingIncomplete(
                "ERPNext Project permission has no approved LaunchFlow Project mapping."
            )
        project_access.append((str(project_id), str(access)))
    project_access.sort()
    if len(project_access) > MAX_PROJECT_SCOPES:
        raise AuthorizationSenderError("Mapped Project access is too large.")

    organization_scopes = tuple(
        sorted(
            (permission.kind, permission.reference_key)
            for permission in source.permissions
            if permission.kind in {kind.value for kind in OrganizationScopeKind}
        )
    )
    if len(organization_scopes) > MAX_ORGANIZATION_SCOPES:
        raise AuthorizationSenderError("Mapped organization access is too large.")
    return AuthorizationSnapshot(
        source.source_subject_id,
        source.target_user_id,
        True,
        mapped_roles,
        tuple(project_access),
        organization_scopes,
    )


def build_event(
    snapshot: AuthorizationSnapshot,
    *,
    source_version: int,
    issued_at: datetime,
    ttl_seconds: int,
) -> AuthorizationEvent:
    if type(source_version) is not int or not 1 <= source_version <= 2_147_483_647:
        raise AuthorizationSenderError("Source version is invalid.")
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise AuthorizationSenderError("Issued time must be timezone aware.")
    if not MIN_TTL_SECONDS <= ttl_seconds <= MAX_TTL_SECONDS:
        raise AuthorizationSenderError("Projection validity window is invalid.")
    issued = issued_at.astimezone(UTC).replace(microsecond=0)
    expires = issued + timedelta(seconds=ttl_seconds)
    identity = f"{snapshot.source_subject_id}:{source_version}:{snapshot.snapshot_hash}"
    event_id = uuid5(EVENT_NAMESPACE, identity)
    request_id = uuid5(REQUEST_NAMESPACE, identity)
    trace_id = f"erp-auth-{event_id.hex}"
    payload = {
        "sourceSubjectId": snapshot.source_subject_id,
        "targetUserId": snapshot.target_user_id,
        "sourceVersion": source_version,
        "enabled": snapshot.enabled,
        "roles": list(snapshot.roles),
        "projectAccess": [
            {"projectId": project_id, "access": access}
            for project_id, access in snapshot.project_access
        ],
        "organizationScopes": [
            {"kind": kind, "referenceKey": reference}
            for kind, reference in snapshot.organization_scopes
        ],
        "issuedAt": _utc_text(issued),
        "expiresAt": _utc_text(expires),
    }
    event = {
        "schemaVersion": SCHEMA_VERSION,
        "operation": OPERATION,
        "sourceSystem": SOURCE_SYSTEM,
        "targetSystem": TARGET_SYSTEM,
        "objectType": OBJECT_TYPE,
        "eventId": str(event_id),
        **payload,
        "traceId": trace_id,
        "payloadHash": canonical_hash(payload),
    }
    return AuthorizationEvent(event, request_id, snapshot.snapshot_hash)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _closed(value: object, keys: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AuthorizationSenderError("Sender policy shape is invalid.")
    return value


def _string_map(value: object, name: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise AuthorizationSenderError(f"{name} must be an object.")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise AuthorizationSenderError(f"{name} entries must be strings.")
        if key in result:
            raise AuthorizationSenderError(f"{name} entries must be unique.")
        result[key] = item
    return result


def _email(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 254
        or value != value.casefold()
        or _EMAIL.fullmatch(value) is None
    ):
        raise MappingIncomplete("ERPNext User email is not a canonical lowercase identity.")
    return value


def _role(value: object, name: str) -> str:
    if not isinstance(value, str) or _ROLE.fullmatch(value) is None:
        raise AuthorizationSenderError(f"{name} is invalid.")
    return value


def _reference(value: object, name: str) -> str:
    if not isinstance(value, str) or _REFERENCE.fullmatch(value) is None:
        raise AuthorizationSenderError(f"{name} is invalid.")
    return value


def _canonical_uuid(value: object, name: str) -> UUID:
    try:
        result = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise AuthorizationSenderError(f"{name} is invalid.") from error
    if result.int == 0 or str(result) != str(value).casefold():
        raise AuthorizationSenderError(f"{name} is invalid.")
    return result


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
