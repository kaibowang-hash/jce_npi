from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from .domain import OPERATION, TrialSummaryDeliveryError, canonical_hash, parse_uuid
from npi_integration.project_publish.profile_inheritance import inherited_project_profile

SANDBOX_ENABLED_KEY = "npi_trial_summary_erp_sandbox_enabled"
SANDBOX_PROFILES_KEY = "npi_trial_summary_erp_sandbox_profiles"
SANDBOX_SECRETS_ENV = "NPI_TRIAL_SUMMARY_ERP_SANDBOX_SECRETS"

_PROFILE_KEYS = {
    "profileId",
    "profileVersion",
    "tenantId",
    "projectGlobalId",
    "environmentCode",
    "serviceActorUserId",
    "baseUrl",
    "allowedHostnames",
    "secretReference",
    "connectTimeoutSeconds",
    "readTimeoutSeconds",
}
_HOST = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)
_SECRET_REF = re.compile(r"^secrets?/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_NON_PRODUCTION = frozenset(
    {"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage"}
)
_PRODUCTION = frozenset({"prod", "production", "live"})


@dataclass(frozen=True, slots=True)
class TrialSummaryProfile:
    profile_id: str
    profile_version: int
    tenant_id: str
    project_global_id: str
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
            "projectGlobalId": self.project_global_id,
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


def load_profile(
    configuration: object,
    tenant_id: str,
    project_global_id: str,
) -> TrialSummaryProfile | None:
    if not (
        hasattr(configuration, "get")
        and configuration.get(SANDBOX_ENABLED_KEY) is True
    ):
        return None
    raw_profiles = configuration.get(SANDBOX_PROFILES_KEY)
    if (
        isinstance(raw_profiles, (str, bytes))
        or not isinstance(raw_profiles, Sequence)
        or not 1 <= len(raw_profiles) <= 32
    ):
        raise TrialSummaryDeliveryError("Trial Summary Sandbox profiles are invalid.")
    matches = [
        _profile(value)
        for value in raw_profiles
        if isinstance(value, Mapping)
        and value.get("tenantId") == tenant_id
        and value.get("projectGlobalId") == project_global_id
    ]
    if len(matches) > 1:
        raise TrialSummaryDeliveryError("Trial Summary Sandbox profile is ambiguous.")
    if matches:
        return matches[0]
    try:
        inherited = inherited_project_profile(
            raw_profiles, tenant_id, project_global_id, family="trial-summary"
        )
    except ValueError as error:
        raise TrialSummaryDeliveryError(str(error)) from error
    return _profile(inherited) if inherited is not None else None


def _profile(value: object) -> TrialSummaryProfile:
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise TrialSummaryDeliveryError("Trial Summary Sandbox profile shape is invalid.")
    profile_id = _text(value["profileId"], "profileId", 128)
    if type(value["profileVersion"]) is not int or value["profileVersion"] < 1:
        raise TrialSummaryDeliveryError("Trial Summary Sandbox profile version is invalid.")
    tenant_id = _text(value["tenantId"], "tenantId", 128)
    project_id = parse_uuid(value["projectGlobalId"], "projectGlobalId")
    environment = _text(value["environmentCode"], "environmentCode", 64).casefold()
    if environment in _PRODUCTION or environment not in _NON_PRODUCTION:
        raise TrialSummaryDeliveryError(
            "Trial Summary Sandbox environment must be explicitly non-production."
        )
    service_actor = _text(value["serviceActorUserId"], "serviceActorUserId", 254)
    if service_actor.casefold() in {"guest", "administrator"}:
        raise TrialSummaryDeliveryError("Trial Summary service actor is invalid.")
    base_url = _origin(value["baseUrl"])
    hosts = value["allowedHostnames"]
    if (
        isinstance(hosts, (str, bytes))
        or not isinstance(hosts, Sequence)
        or not 1 <= len(hosts) <= 8
    ):
        raise TrialSummaryDeliveryError("Trial Summary hostname allowlist is invalid.")
    allowed = tuple(_hostname(item) for item in hosts)
    if len(set(allowed)) != len(allowed) or urlsplit(base_url).hostname not in allowed:
        raise TrialSummaryDeliveryError("Trial Summary base URL is not allowlisted.")
    secret_reference = _text(value["secretReference"], "secretReference", 128)
    if _SECRET_REF.fullmatch(secret_reference) is None:
        raise TrialSummaryDeliveryError("Trial Summary credential reference is invalid.")
    timeouts = (value["connectTimeoutSeconds"], value["readTimeoutSeconds"])
    if any(type(item) is not int or not 1 <= item <= 120 for item in timeouts):
        raise TrialSummaryDeliveryError("Trial Summary timeout is invalid.")
    return TrialSummaryProfile(
        profile_id,
        value["profileVersion"],
        tenant_id,
        project_id,
        environment,
        service_actor,
        base_url,
        allowed,
        secret_reference,
        timeouts[0],
        timeouts[1],
    )


def _origin(value: object) -> str:
    if not isinstance(value, str):
        raise TrialSummaryDeliveryError("Trial Summary base URL is invalid.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise TrialSummaryDeliveryError("Trial Summary base URL is invalid.") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or port not in (None, 443)
    ):
        raise TrialSummaryDeliveryError("Trial Summary base URL must be one HTTPS origin.")
    _hostname(parsed.hostname)
    return value.rstrip("/")


def _hostname(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TrialSummaryDeliveryError("Trial Summary hostname is invalid.")
    normalized = value.casefold().rstrip(".")
    if _HOST.fullmatch(normalized) is None:
        raise TrialSummaryDeliveryError("Trial Summary hostname is invalid.")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise TrialSummaryDeliveryError("Trial Summary hostname cannot be an IP literal.")
    labels = set(normalized.split("."))
    if "localhost" in labels or labels & _PRODUCTION or not labels & _NON_PRODUCTION:
        raise TrialSummaryDeliveryError(
            "Trial Summary hostname must be explicitly non-production."
        )
    return normalized


def _text(value: object, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise TrialSummaryDeliveryError(f"Trial Summary {label} is invalid.")
    return value
