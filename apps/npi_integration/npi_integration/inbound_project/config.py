from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from .domain import (
    PROJECT_SOURCE_EVENT_TYPES,
    ProjectSourceContractError,
    ProjectSourceEventType,
    ProjectSourceObjectType,
    canonical_json_hash,
)


_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_SECRET_REFERENCE_PATTERN = re.compile(
    r"^secrets?/[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$"
)
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_NON_PRODUCTION_LABELS = frozenset(
    {"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage", "disposable-test"}
)
_PRODUCTION_LABELS = frozenset({"prod", "production", "live"})
_PROJECT_TYPES = frozenset({"customer_owned_tool", "new_tool", "tool_change"})


class BusinessCodeMode(StrEnum):
    SOURCE_DOCUMENT_ID = "source_document_id"


@dataclass(frozen=True, slots=True)
class WebhookKeyDescriptor:
    key_id: str
    secret_reference: str
    valid_from: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key_id", _identifier(self.key_id, "key_id"))
        if (
            not isinstance(self.secret_reference, str)
            or _SECRET_REFERENCE_PATTERN.fullmatch(self.secret_reference) is None
        ):
            raise ProjectSourceContractError(
                "Webhook keys must use an opaque secret reference."
            )
        start = _aware_utc(self.valid_from, "valid_from")
        end = (
            _aware_utc(self.valid_until, "valid_until")
            if self.valid_until is not None
            else None
        )
        if end is not None and end < start:
            raise ProjectSourceContractError("Webhook key validity is invalid.")
        object.__setattr__(self, "valid_from", start)
        object.__setattr__(self, "valid_until", end)

    def is_valid_at(self, signed_at: datetime) -> bool:
        moment = _aware_utc(signed_at, "signed_at")
        return self.valid_from <= moment and (
            self.valid_until is None or moment <= self.valid_until
        )


@dataclass(frozen=True, slots=True)
class ProjectIntakePolicy:
    source_object_type: ProjectSourceObjectType
    template_global_id: UUID
    template_version: int
    project_type: str
    owner_user_id: str
    business_code_mode: BusinessCodeMode = BusinessCodeMode.SOURCE_DOCUMENT_ID

    @classmethod
    def from_snapshot(cls, value: object) -> ProjectIntakePolicy:
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "source_object_type",
            "template_global_id",
            "template_version",
            "project_type",
            "owner_user_id",
            "business_code_mode",
        }:
            raise ProjectSourceContractError("Policy snapshot is invalid.")
        if value["schema_version"] != 1:
            raise ProjectSourceContractError("Policy snapshot version is unsupported.")
        try:
            source_object_type = ProjectSourceObjectType(value["source_object_type"])
            business_code_mode = BusinessCodeMode(value["business_code_mode"])
        except (TypeError, ValueError) as error:
            raise ProjectSourceContractError("Policy snapshot is invalid.") from error
        return cls(
            source_object_type=source_object_type,
            template_global_id=_uuid(
                value["template_global_id"], "template_global_id"
            ),
            template_version=_positive(
                value["template_version"], "template_version"
            ),
            project_type=value["project_type"],
            owner_user_id=value["owner_user_id"],
            business_code_mode=business_code_mode,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.source_object_type, ProjectSourceObjectType):
            raise ProjectSourceContractError("Policy source object type is unsupported.")
        object.__setattr__(
            self,
            "template_global_id",
            _uuid(self.template_global_id, "template_global_id"),
        )
        object.__setattr__(
            self,
            "template_version",
            _positive(self.template_version, "template_version"),
        )
        if self.project_type not in _PROJECT_TYPES:
            raise ProjectSourceContractError("Policy project type is unsupported.")
        object.__setattr__(
            self,
            "owner_user_id",
            _actor(self.owner_user_id, "owner_user_id"),
        )
        if self.business_code_mode is not BusinessCodeMode.SOURCE_DOCUMENT_ID:
            raise ProjectSourceContractError("Policy business-code mode is unsupported.")

    def snapshot(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "source_object_type": self.source_object_type.value,
            "template_global_id": str(self.template_global_id),
            "template_version": self.template_version,
            "project_type": self.project_type,
            "owner_user_id": self.owner_user_id,
            "business_code_mode": self.business_code_mode.value,
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_json_hash(self.snapshot())


@dataclass(frozen=True, slots=True)
class InboundProjectProfile:
    profile_id: str
    version: int
    tenant_id: str
    environment_code: str
    non_production_attested: bool
    enabled: bool
    trusted_tls_termination: bool
    service_actor_user_id: str
    allowed_event_types: tuple[ProjectSourceEventType, ...]
    keys: tuple[WebhookKeyDescriptor, ...]
    policies: tuple[ProjectIntakePolicy, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _identifier(self.profile_id, "profile_id"))
        object.__setattr__(self, "version", _positive(self.version, "profile.version"))
        if (
            not isinstance(self.tenant_id, str)
            or _TENANT_PATTERN.fullmatch(self.tenant_id) is None
        ):
            raise ProjectSourceContractError("Profile tenant is invalid.")
        if type(self.enabled) is not bool or type(self.non_production_attested) is not bool:
            raise ProjectSourceContractError("Profile enablement flags must be boolean.")
        if type(self.trusted_tls_termination) is not bool:
            raise ProjectSourceContractError("Profile TLS setting must be boolean.")
        environment = _identifier(self.environment_code, "environment_code").casefold()
        if (
            self.environment_code != environment
            or environment in _PRODUCTION_LABELS
            or environment not in _NON_PRODUCTION_LABELS
            or not self.non_production_attested
        ):
            raise ProjectSourceContractError(
                "Inbound profiles must be explicitly non-production."
            )
        actor = _actor(self.service_actor_user_id, "service_actor_user_id")
        if actor.casefold() in {"guest", "administrator"}:
            raise ProjectSourceContractError(
                "Inbound profile service actor must be a scoped internal user."
            )
        if type(self.allowed_event_types) is not tuple or not self.allowed_event_types:
            raise ProjectSourceContractError("Profile event allowlist is invalid.")
        if (
            any(not isinstance(value, ProjectSourceEventType) for value in self.allowed_event_types)
            or len(set(self.allowed_event_types)) != len(self.allowed_event_types)
            or set(self.allowed_event_types) != set(PROJECT_SOURCE_EVENT_TYPES)
        ):
            raise ProjectSourceContractError("Profile event allowlist is invalid.")
        if type(self.keys) is not tuple or not self.keys:
            raise ProjectSourceContractError("Profile key set is invalid.")
        if (
            any(not isinstance(value, WebhookKeyDescriptor) for value in self.keys)
            or len({value.key_id for value in self.keys}) != len(self.keys)
        ):
            raise ProjectSourceContractError("Profile key IDs must be unique.")
        if type(self.policies) is not tuple or not self.policies:
            raise ProjectSourceContractError("Profile policy set is invalid.")
        if (
            any(not isinstance(value, ProjectIntakePolicy) for value in self.policies)
            or len({value.source_object_type for value in self.policies}) != len(self.policies)
        ):
            raise ProjectSourceContractError("Profile policies must be unique by source type.")
        required_objects = {
            PROJECT_SOURCE_EVENT_TYPES[event_type]
            for event_type in self.allowed_event_types
        }
        if required_objects != {policy.source_object_type for policy in self.policies}:
            raise ProjectSourceContractError(
                "Profile policies must exactly cover the event allowlist."
            )

    @property
    def policy_by_object_type(self) -> MappingProxyType[ProjectSourceObjectType, ProjectIntakePolicy]:
        return MappingProxyType(
            {policy.source_object_type: policy for policy in self.policies}
        )

    def key_at(self, key_id: str, signed_at: datetime) -> WebhookKeyDescriptor:
        matches = [
            key
            for key in self.keys
            if key.key_id == key_id and key.is_valid_at(signed_at)
        ]
        if len(matches) != 1:
            raise KeyError("Webhook key unavailable.")
        return matches[0]

    def resolve_secret(
        self,
        key_id: str,
        signed_at: datetime,
        resolver: Callable[[str], bytes],
    ) -> bytes:
        if not self.enabled or not callable(resolver):
            raise KeyError("Webhook profile unavailable.")
        key = self.key_at(key_id, signed_at)
        secret = resolver(key.secret_reference)
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise KeyError("Webhook secret unavailable.")
        return secret

    def snapshot(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "profile_id": self.profile_id,
            "profile_version": self.version,
            "source_system": "ERPNEXT",
            "target_system": "NPI_ONE",
            "tenant_id": self.tenant_id,
            "environment_code": self.environment_code,
            "non_production_attested": self.non_production_attested,
            "enabled": self.enabled,
            "trusted_tls_termination": self.trusted_tls_termination,
            "service_actor_user_id": self.service_actor_user_id,
            "allowed_event_types": [value.value for value in self.allowed_event_types],
            "keys": [
                {
                    "key_id": key.key_id,
                    "valid_from": key.valid_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "valid_until": (
                        key.valid_until.strftime("%Y-%m-%dT%H:%M:%SZ")
                        if key.valid_until is not None
                        else None
                    ),
                }
                for key in self.keys
            ],
            "policies": [policy.snapshot() for policy in self.policies],
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_json_hash(self.snapshot())


def _identifier(value: object, path: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _actor(value: object, path: str) -> str:
    if not isinstance(value, str) or _ACTOR_PATTERN.fullmatch(value) is None:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _positive(value: object, path: str) -> int:
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        raise ProjectSourceContractError(f"{path} is invalid.")
    return value


def _uuid(value: object, path: str) -> UUID:
    try:
        result = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ProjectSourceContractError(f"{path} is invalid.") from error
    if isinstance(value, str) and str(result) != value:
        raise ProjectSourceContractError(f"{path} must be canonical.")
    return result


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ProjectSourceContractError(f"{path} must be timezone-aware.")
    return value.astimezone(UTC)
