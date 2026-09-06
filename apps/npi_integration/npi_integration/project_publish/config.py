from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from .domain import OPERATION, ProjectPublishError, canonical_hash


ENABLED_KEY = "npi_project_publish_sandbox_enabled"
PROFILES_KEY = "npi_project_publish_sandbox_profiles"
# Project creation intentionally reuses the already deployed, least-privilege
# ERPNext command transport credential. Business attribution remains the
# actorUserId in each signed command; no second integration account is needed.
SECRETS_ENV = "NPI_ITEM_PUBLISH_SANDBOX_SECRETS"
_PROFILE_KEYS = {
    "profileId",
    "profileVersion",
    "tenantId",
    "environmentCode",
    "serviceActorUserId",
    "baseUrl",
    "allowedHostnames",
    "secretReference",
    "connectTimeoutSeconds",
    "readTimeoutSeconds",
}
_HOST = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$")
_SECRET_REF = re.compile(r"^secrets?/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_NON_PRODUCTION = frozenset({"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage"})


@dataclass(frozen=True, slots=True)
class ProjectPublishProfile:
    profile_id: str
    profile_version: int
    tenant_id: str
    environment_code: str
    service_actor_user_id: str
    base_url: str
    allowed_hostnames: tuple[str, ...]
    secret_reference: str
    connect_timeout_seconds: int
    read_timeout_seconds: int

    @property
    def snapshot(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "tenantId": self.tenant_id,
            "targetMode": "sandbox",
            "environmentCode": self.environment_code,
            "serviceActorUserId": self.service_actor_user_id,
            "allowedOperations": [OPERATION],
            "baseUrl": self.base_url,
            "allowedHostnames": list(self.allowed_hostnames),
            "secretReference": self.secret_reference,
            "responseAuthentication": "hmac-sha256-v1",
            "connectTimeoutSeconds": self.connect_timeout_seconds,
            "readTimeoutSeconds": self.read_timeout_seconds,
            "nonProductionAttested": True,
            "followRedirects": False,
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.snapshot)


def load_profile(configuration: object, tenant_id: str) -> ProjectPublishProfile | None:
    if not hasattr(configuration, "get") or configuration.get(ENABLED_KEY) is not True:
        return None
    values = configuration.get(PROFILES_KEY)
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not 1 <= len(values) <= 16:
        raise ProjectPublishError("Project publication profiles are invalid.")
    matches = [_profile(value) for value in values if isinstance(value, Mapping) and value.get("tenantId") == tenant_id]
    if len(matches) > 1:
        raise ProjectPublishError("Project publication profile is ambiguous.")
    return matches[0] if matches else None


def configured_environments(configuration: object) -> tuple[str, ...]:
    if not hasattr(configuration, "get") or configuration.get(ENABLED_KEY) is not True:
        return ()
    values = configuration.get(PROFILES_KEY)
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not 1 <= len(values) <= 16:
        raise ProjectPublishError("Project publication profiles are invalid.")
    environments = tuple(sorted({_profile(value).environment_code for value in values}))
    if len(environments) != 1:
        raise ProjectPublishError("Project publication environment is ambiguous.")
    return environments


def _profile(value: object) -> ProjectPublishProfile:
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise ProjectPublishError("Project publication profile shape is invalid.")
    profile_id = _text(value["profileId"], "profileId", 128)
    version = value["profileVersion"]
    if type(version) is not int or version < 1:
        raise ProjectPublishError("Project publication profile version is invalid.")
    tenant = _text(value["tenantId"], "tenantId", 128)
    environment = _text(value["environmentCode"], "environmentCode", 64).casefold()
    if environment not in _NON_PRODUCTION:
        raise ProjectPublishError("Project publication target must be non-production.")
    service_actor = _text(value["serviceActorUserId"], "serviceActorUserId", 254)
    if service_actor.casefold() in {"guest", "administrator"}:
        raise ProjectPublishError("Project publication service actor is invalid.")
    base_url = _origin(value["baseUrl"])
    hosts = value["allowedHostnames"]
    if isinstance(hosts, (str, bytes)) or not isinstance(hosts, Sequence) or not 1 <= len(hosts) <= 8:
        raise ProjectPublishError("Project publication hostname allowlist is invalid.")
    allowed = tuple(_hostname(item) for item in hosts)
    if len(set(allowed)) != len(allowed) or urlsplit(base_url).hostname not in allowed:
        raise ProjectPublishError("Project publication base URL is not allowlisted.")
    secret_reference = _text(value["secretReference"], "secretReference", 128)
    if _SECRET_REF.fullmatch(secret_reference) is None:
        raise ProjectPublishError("Project publication credential reference is invalid.")
    connect = value["connectTimeoutSeconds"]
    read = value["readTimeoutSeconds"]
    if any(type(item) is not int or not 1 <= item <= 120 for item in (connect, read)):
        raise ProjectPublishError("Project publication timeout is invalid.")
    return ProjectPublishProfile(profile_id, version, tenant, environment, service_actor, base_url, allowed, secret_reference, connect, read)


def _origin(value: object) -> str:
    if not isinstance(value, str):
        raise ProjectPublishError("Project publication base URL is invalid.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ProjectPublishError("Project publication base URL is invalid.") from error
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or parsed.path not in ("", "/") or port not in (None, 443):
        raise ProjectPublishError("Project publication base URL must be one HTTPS origin.")
    _hostname(parsed.hostname)
    return value.rstrip("/")


def _hostname(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectPublishError("Project publication hostname is invalid.")
    normalized = value.casefold().rstrip(".")
    if _HOST.fullmatch(normalized) is None:
        raise ProjectPublishError("Project publication hostname is invalid.")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise ProjectPublishError("Project publication hostname cannot be an IP literal.")
    labels = set(normalized.split("."))
    if "localhost" in labels or not labels & _NON_PRODUCTION:
        raise ProjectPublishError("Project publication hostname must be explicitly non-production.")
    return normalized


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ProjectPublishError(f"Project publication {label} is invalid.")
    return value
