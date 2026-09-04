from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from .domain import EngineeringChangeIntegrationError, ExecutionProfileReference, SUMMARY_OPERATION, TargetMode, canonical_hash


_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{2,254}$")
_SECRET = re.compile(r"^secrets?/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_HOST = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ACTOR = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class IntegrationProfile:
    profile_id: str
    profile_version: int
    tenant_id: str
    project_global_id: str
    target_mode: TargetMode
    requester_user_ids: tuple[str, ...]
    service_actor_user_id: str
    signing_key_ids: tuple[str, ...] = ()
    adapter_resolver: str | None = None
    base_url: str | None = None
    allowed_hostnames: tuple[str, ...] = ()
    secret_reference: str | None = None
    response_authentication: str | None = None
    connect_timeout_seconds: int | None = None
    read_timeout_seconds: int | None = None
    disposable_runtime_marker: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.target_mode, TargetMode) or type(self.requester_user_ids) is not tuple or type(self.signing_key_ids) is not tuple:
            raise EngineeringChangeIntegrationError("Integration profile shape is invalid.")
        if _CODE.fullmatch(self.profile_id) is None or _TENANT.fullmatch(self.tenant_id) is None:
            raise EngineeringChangeIntegrationError("Integration profile identity is invalid.")
        if type(self.profile_version) is not int or self.profile_version < 1:
            raise EngineeringChangeIntegrationError("Integration profile version is invalid.")
        try:
            if str(UUID(self.project_global_id)) != self.project_global_id:
                raise ValueError
        except (TypeError, ValueError) as error:
            raise EngineeringChangeIntegrationError("Profile Project identity is invalid.") from error
        actors = (*self.requester_user_ids, self.service_actor_user_id)
        if not self.requester_user_ids or any(not isinstance(value, str) or value != value.strip() or _ACTOR.fullmatch(value) is None or value.casefold() in {"guest", "administrator"} for value in actors):
            raise EngineeringChangeIntegrationError("Profile actors are invalid.")
        if len({value.casefold() for value in self.requester_user_ids}) != len(self.requester_user_ids):
            raise EngineeringChangeIntegrationError("Profile requester allowlist is ambiguous.")
        if len(set(self.signing_key_ids)) != len(self.signing_key_ids) or any(
            not isinstance(value, str) or _KEY.fullmatch(value) is None
            for value in self.signing_key_ids
        ):
            raise EngineeringChangeIntegrationError("Profile signing keys are invalid.")
        if self.target_mode is TargetMode.DISABLED:
            if any((self.signing_key_ids, self.adapter_resolver, self.base_url, self.allowed_hostnames, self.secret_reference, self.response_authentication, self.connect_timeout_seconds, self.read_timeout_seconds, self.disposable_runtime_marker)):
                raise EngineeringChangeIntegrationError("Disabled profile must remain network-free.")
        elif self.target_mode is TargetMode.SYNTHETIC:
            if not self.signing_key_ids or not self.disposable_runtime_marker or _PATH.fullmatch(self.adapter_resolver or "") is None or self.base_url is not None or self.allowed_hostnames or self.secret_reference is not None or self.response_authentication is not None:
                raise EngineeringChangeIntegrationError("Synthetic profile is allowed only in disposable runtime.")
        else:
            self._validate_sandbox()
        self.reference

    def _validate_sandbox(self) -> None:
        if self.disposable_runtime_marker or not self.signing_key_ids or len(set(self.signing_key_ids)) != len(self.signing_key_ids) or _PATH.fullmatch(self.adapter_resolver or "") is None:
            raise EngineeringChangeIntegrationError("Sandbox profile activation is invalid.")
        if not isinstance(self.base_url, str):
            raise EngineeringChangeIntegrationError("Sandbox origin is required.")
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/") or parsed.port not in (None, 443):
            raise EngineeringChangeIntegrationError("Sandbox origin is invalid.")
        host = _sandbox_host(parsed.hostname)
        hosts = tuple(_sandbox_host(value) for value in self.allowed_hostnames)
        if host not in hosts or not hosts or len(set(hosts)) != len(hosts):
            raise EngineeringChangeIntegrationError("Sandbox host allowlist is invalid.")
        if _SECRET.fullmatch(self.secret_reference or "") is None or self.response_authentication != "hmac-sha256-v1":
            raise EngineeringChangeIntegrationError("Sandbox authentication profile is invalid.")
        if any(type(value) is not int or not 1 <= value <= 120 for value in (self.connect_timeout_seconds, self.read_timeout_seconds)):
            raise EngineeringChangeIntegrationError("Sandbox timeouts are invalid.")

    @property
    def snapshot(self) -> dict[str, object]:
        return {
            "schemaVersion": 1, "profileId": self.profile_id, "profileVersion": self.profile_version,
            "tenantId": self.tenant_id, "projectGlobalId": self.project_global_id,
            "targetMode": self.target_mode.value, "requesterUserIds": list(self.requester_user_ids),
            "serviceActorUserId": self.service_actor_user_id, "signingKeyIds": list(self.signing_key_ids),
            "allowedOperations": [] if self.target_mode is TargetMode.DISABLED else [SUMMARY_OPERATION],
            "adapterResolver": self.adapter_resolver, "baseUrl": self.base_url,
            "allowedHostnames": list(self.allowed_hostnames), "secretReference": self.secret_reference,
            "responseAuthentication": self.response_authentication,
            "connectTimeoutSeconds": self.connect_timeout_seconds, "readTimeoutSeconds": self.read_timeout_seconds,
            "disposableRuntimeMarker": self.disposable_runtime_marker,
        }

    @property
    def reference(self) -> ExecutionProfileReference:
        return ExecutionProfileReference(self.profile_id, self.profile_version, self.target_mode, canonical_hash(self.snapshot))

    def permits(self, actor: str) -> bool:
        return isinstance(actor, str) and actor.casefold() in {value.casefold() for value in self.requester_user_ids}


def _sandbox_host(value: object) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise EngineeringChangeIntegrationError("Sandbox hostname is invalid.")
    host = value.casefold().rstrip(".")
    if _HOST.fullmatch(host) is None or "sandbox" not in host.split("."):
        raise EngineeringChangeIntegrationError("Sandbox hostname is invalid.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise EngineeringChangeIntegrationError("Sandbox hostname cannot be an IP literal.")
