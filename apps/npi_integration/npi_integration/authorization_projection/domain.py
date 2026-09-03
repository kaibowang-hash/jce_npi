from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
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
PROJECTION_NAMESPACE = UUID("e9f58a77-e1cf-4c72-9d3d-b8d871c56255")
_IDENTIFIER = re.compile(r"^[^\s\x00-\x1f\x7f]{1,255}$")
_ROLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./:&()-]{0,127}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_TRACE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HASH = re.compile(r"^[a-f0-9]{64}$")


class AuthorizationProjectionError(ValueError):
    """Raised when an authorization replacement is not exactly contract-shaped."""


class OrganizationScopeKind(StrEnum):
    COMPANY = "Company"
    CUSTOMER = "Customer"
    SUPPLIER = "Supplier"


class ProjectAccess(StrEnum):
    VIEW = "view"
    CONTRIBUTE = "contribute"
    APPROVE = "approve"
    ADMINISTER = "administer"


@dataclass(frozen=True, slots=True, order=True)
class ProjectScope:
    project_id: UUID
    access: ProjectAccess

    @classmethod
    def from_mapping(cls, value: object) -> ProjectScope:
        source = _closed(value, {"projectId", "access"})
        try:
            return cls(
                project_id=_uuid(source["projectId"]),
                access=ProjectAccess(source["access"]),
            )
        except (TypeError, ValueError) as error:
            raise AuthorizationProjectionError("Project scope is invalid.") from error

    def mapping(self) -> dict[str, str]:
        return {"projectId": str(self.project_id), "access": self.access.value}


@dataclass(frozen=True, slots=True, order=True)
class OrganizationScope:
    kind: OrganizationScopeKind
    reference_key: str

    @classmethod
    def from_mapping(cls, value: object) -> OrganizationScope:
        source = _closed(value, {"kind", "referenceKey"})
        try:
            kind = OrganizationScopeKind(source["kind"])
        except (TypeError, ValueError) as error:
            raise AuthorizationProjectionError(
                "Organization scope kind is invalid."
            ) from error
        return cls(
            kind=kind,
            reference_key=_identifier(source["referenceKey"], "referenceKey"),
        )

    def mapping(self) -> dict[str, str]:
        return {"kind": self.kind.value, "referenceKey": self.reference_key}


@dataclass(frozen=True, slots=True)
class AuthorizationProjectionEvent:
    event_id: UUID
    source_subject_id: str
    target_user_id: str
    source_version: int
    enabled: bool
    roles: tuple[str, ...]
    project_scopes: tuple[ProjectScope, ...]
    organization_scopes: tuple[OrganizationScope, ...]
    issued_at: datetime
    expires_at: datetime
    trace_id: str
    payload_hash: str

    @classmethod
    def from_mapping(cls, value: object) -> AuthorizationProjectionEvent:
        source = _closed(
            value,
            {
                "schemaVersion",
                "operation",
                "sourceSystem",
                "targetSystem",
                "objectType",
                "eventId",
                "sourceSubjectId",
                "targetUserId",
                "sourceVersion",
                "enabled",
                "roles",
                "projectAccess",
                "organizationScopes",
                "issuedAt",
                "expiresAt",
                "traceId",
                "payloadHash",
            },
        )
        if (
            source["schemaVersion"] != SCHEMA_VERSION
            or source["operation"] != OPERATION
            or source["sourceSystem"] != SOURCE_SYSTEM
            or source["targetSystem"] != TARGET_SYSTEM
            or source["objectType"] != OBJECT_TYPE
        ):
            raise AuthorizationProjectionError(
                "Authorization projection contract is unsupported."
            )
        roles = _roles(source["roles"])
        project_scopes = _project_scopes(source["projectAccess"])
        organization_scopes = _organization_scopes(source["organizationScopes"])
        enabled = _boolean(source["enabled"])
        if not enabled and (roles or project_scopes or organization_scopes):
            raise AuthorizationProjectionError(
                "A disabled authorization projection must have no grants."
            )
        issued_at = _utc(source["issuedAt"], "issuedAt")
        expires_at = _utc(source["expiresAt"], "expiresAt")
        if expires_at <= issued_at:
            raise AuthorizationProjectionError(
                "Authorization projection expiry is invalid."
            )
        event = cls(
            event_id=_uuid(source["eventId"]),
            source_subject_id=_identifier(
                source["sourceSubjectId"], "sourceSubjectId"
            ),
            target_user_id=_identifier(source["targetUserId"], "targetUserId"),
            source_version=_positive(source["sourceVersion"], "sourceVersion"),
            enabled=enabled,
            roles=roles,
            project_scopes=project_scopes,
            organization_scopes=organization_scopes,
            issued_at=issued_at,
            expires_at=expires_at,
            trace_id=_pattern(source["traceId"], _TRACE, "traceId"),
            payload_hash=_pattern(source["payloadHash"], _HASH, "payloadHash"),
        )
        if event.payload_hash != canonical_hash(event.payload_mapping()):
            raise AuthorizationProjectionError(
                "Authorization projection payload hash does not match."
            )
        return event

    @property
    def source_subject_hash(self) -> str:
        return hashlib.sha256(self.source_subject_id.encode()).hexdigest()

    def projection_key_hash(self, tenant_id: str) -> str:
        tenant = _pattern(tenant_id, _TENANT, "tenantId")
        return canonical_hash(
            {"tenantId": tenant, "targetUserId": self.target_user_id}
        )

    def projection_id(self, tenant_id: str) -> UUID:
        return projection_id_for(tenant_id, self.target_user_id)

    def payload_mapping(self) -> dict[str, object]:
        return {
            "sourceSubjectId": self.source_subject_id,
            "targetUserId": self.target_user_id,
            "sourceVersion": self.source_version,
            "enabled": self.enabled,
            "roles": list(self.roles),
            "projectAccess": [scope.mapping() for scope in self.project_scopes],
            "organizationScopes": [
                scope.mapping() for scope in self.organization_scopes
            ],
            "issuedAt": utc_text(self.issued_at),
            "expiresAt": utc_text(self.expires_at),
        }

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "operation": OPERATION,
            "sourceSystem": SOURCE_SYSTEM,
            "targetSystem": TARGET_SYSTEM,
            "objectType": OBJECT_TYPE,
            "eventId": str(self.event_id),
            **self.payload_mapping(),
            "traceId": self.trace_id,
            "payloadHash": self.payload_hash,
        }

    @property
    def event_hash(self) -> str:
        return canonical_hash(self.canonical_mapping())

    @property
    def projection_hash(self) -> str:
        return canonical_hash(
            {
                "sourceSubjectHash": self.source_subject_hash,
                "targetUserId": self.target_user_id,
                "sourceVersion": self.source_version,
                "enabled": self.enabled,
                "roles": list(self.roles),
                "projectAccess": [scope.mapping() for scope in self.project_scopes],
                "organizationScopes": [
                    scope.mapping() for scope in self.organization_scopes
                ],
                "issuedAt": utc_text(self.issued_at),
                "expiresAt": utc_text(self.expires_at),
            }
        )


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def projection_id_for(tenant_id: str, user_id: str) -> UUID:
    tenant = _pattern(tenant_id, _TENANT, "tenantId")
    target = _identifier(user_id, "targetUserId")
    key_hash = canonical_hash({"tenantId": tenant, "targetUserId": target})
    return uuid5(PROJECTION_NAMESPACE, key_hash)


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _closed(value: object, keys: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AuthorizationProjectionError(
            "Authorization projection shape is invalid."
        )
    return value


def _roles(value: object) -> tuple[str, ...]:
    items = _sequence(value, "roles", MAX_ROLES)
    roles = tuple(_pattern(item, _ROLE, "roles") for item in items)
    if tuple(sorted(set(roles))) != roles:
        raise AuthorizationProjectionError("Authorization roles must be unique and sorted.")
    return roles


def _project_scopes(value: object) -> tuple[ProjectScope, ...]:
    scopes = tuple(
        ProjectScope.from_mapping(item)
        for item in _sequence(value, "projectAccess", MAX_PROJECT_SCOPES)
    )
    if tuple(sorted(set(scopes))) != scopes:
        raise AuthorizationProjectionError(
            "Project authorization scopes must be unique and sorted."
        )
    return scopes


def _organization_scopes(value: object) -> tuple[OrganizationScope, ...]:
    scopes = tuple(
        OrganizationScope.from_mapping(item)
        for item in _sequence(
            value,
            "organizationScopes",
            MAX_ORGANIZATION_SCOPES,
        )
    )
    if tuple(sorted(set(scopes))) != scopes:
        raise AuthorizationProjectionError(
            "Organization authorization scopes must be unique and sorted."
        )
    return scopes


def _sequence(value: object, name: str, maximum: int) -> Sequence[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > maximum
    ):
        raise AuthorizationProjectionError(f"{name} is invalid.")
    return value


def _identifier(value: object, name: str) -> str:
    return _pattern(value, _IDENTIFIER, name)


def _pattern(value: object, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise AuthorizationProjectionError(f"{name} is invalid.")
    return value


def _uuid(value: object) -> UUID:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise AuthorizationProjectionError("eventId is invalid.") from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise AuthorizationProjectionError("eventId is invalid.")
    return parsed


def _positive(value: object, name: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise AuthorizationProjectionError(f"{name} is invalid.")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise AuthorizationProjectionError("enabled is invalid.")
    return value


def _utc(value: object, name: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise AuthorizationProjectionError(f"{name} is invalid.")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise AuthorizationProjectionError(f"{name} is invalid.") from error
    return parsed
