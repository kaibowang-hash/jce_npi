from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from .domain import (
    MBOM_PUBLISH_OPERATION,
    MbomExecutionProfileReference,
    MbomPublishContractError,
    MbomTargetMode,
    canonical_hash,
)


_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)
_PATH_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{2,254}$")
_SECRET_REFERENCE_PATTERN = re.compile(r"^secrets?/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_NON_PRODUCTION_LABELS = frozenset(
    {"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage"}
)
_PRODUCTION_LABELS = frozenset({"prod", "production", "live"})
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class MbomExecutionProfile:
    profile_id: str
    profile_version: int
    tenant_id: str
    project_global_id: str
    target_mode: MbomTargetMode
    environment_code: str
    requester_user_ids: tuple[str, ...]
    service_actor_user_id: str
    projection_policy_id: str
    projection_policy_version: int
    projection_policy_hash: str
    allowed_operations: tuple[str, ...] = ()
    adapter_resolver: str | None = None
    base_url: str | None = None
    allowed_hostnames: tuple[str, ...] = ()
    secret_reference: str | None = None
    response_authentication: str | None = None
    connect_timeout_seconds: int | None = None
    read_timeout_seconds: int | None = None
    non_production_attested: bool = False
    synthetic_test_only: bool = False
    follow_redirects: bool = False
    disposable_runtime_marker: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.target_mode, MbomTargetMode):
            raise MbomPublishContractError("MBOM execution profile target mode is unsupported.")
        if type(self.requester_user_ids) is not tuple or type(self.allowed_operations) is not tuple:
            raise MbomPublishContractError("MBOM execution profile allowlists must be immutable tuples.")
        if type(self.allowed_hostnames) is not tuple:
            raise MbomPublishContractError("MBOM execution host allowlist must be an immutable tuple.")
        for value in (
            self.non_production_attested,
            self.synthetic_test_only,
            self.follow_redirects,
            self.disposable_runtime_marker,
        ):
            if type(value) is not bool:
                raise MbomPublishContractError("MBOM execution profile safety flags must be boolean.")
        if self.follow_redirects:
            raise MbomPublishContractError("MBOM execution adapters cannot follow redirects.")
        if (
            not isinstance(self.tenant_id, str)
            or self.tenant_id != self.tenant_id.strip()
            or _TENANT_PATTERN.fullmatch(self.tenant_id) is None
        ):
            raise MbomPublishContractError("MBOM execution tenant identity is invalid.")
        try:
            project = UUID(self.project_global_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise MbomPublishContractError(
                "MBOM execution Project identity must be a canonical UUID."
            ) from error
        if str(project) != self.project_global_id:
            raise MbomPublishContractError("MBOM execution Project identity must be a canonical UUID.")
        for value, label, pattern in (
            (self.profile_id, "profile identity", _CODE_PATTERN),
            (self.environment_code, "environment code", _CODE_PATTERN),
            (self.projection_policy_id, "projection policy identity", _CODE_PATTERN),
            (self.projection_policy_hash, "projection policy hash", _HASH_PATTERN),
        ):
            if not isinstance(value, str) or value != value.strip() or pattern.fullmatch(value) is None:
                raise MbomPublishContractError(f"MBOM execution {label} is invalid.")
        for value, label in (
            (self.profile_version, "profile version"),
            (self.projection_policy_version, "projection policy version"),
        ):
            if type(value) is not int or not 1 <= value <= 2_147_483_647:
                raise MbomPublishContractError(f"MBOM execution {label} is invalid.")
        if not self.requester_user_ids or len(self.requester_user_ids) > 100:
            raise MbomPublishContractError("MBOM execution requester allowlist is invalid.")
        actors = (*self.requester_user_ids, self.service_actor_user_id)
        if any(
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 254
            or value.casefold() in {"guest", "administrator"}
            for value in actors
        ):
            raise MbomPublishContractError("MBOM execution actors must be scoped internal users.")
        if len({value.casefold() for value in self.requester_user_ids}) != len(self.requester_user_ids):
            raise MbomPublishContractError("MBOM execution requester allowlist is invalid.")
        self.reference
        if self.target_mode is MbomTargetMode.MOCK:
            self._validate_mock()
        elif self.target_mode is MbomTargetMode.SYNTHETIC:
            self._validate_synthetic()
        else:
            self._validate_sandbox()

    @property
    def snapshot(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "tenantId": self.tenant_id,
            "projectGlobalId": self.project_global_id,
            "targetMode": self.target_mode.value,
            "environmentCode": self.environment_code,
            "requesterUserIds": list(self.requester_user_ids),
            "serviceActorUserId": self.service_actor_user_id,
            "projectionPolicyId": self.projection_policy_id,
            "projectionPolicyVersion": self.projection_policy_version,
            "projectionPolicyHash": self.projection_policy_hash,
            "allowedOperations": list(self.allowed_operations),
            "adapterResolver": self.adapter_resolver,
            "baseUrl": self.base_url,
            "allowedHostnames": list(self.allowed_hostnames),
            "secretReference": self.secret_reference,
            "responseAuthentication": self.response_authentication,
            "connectTimeoutSeconds": self.connect_timeout_seconds,
            "readTimeoutSeconds": self.read_timeout_seconds,
            "nonProductionAttested": self.non_production_attested,
            "syntheticTestOnly": self.synthetic_test_only,
            "followRedirects": False,
            "disposableRuntimeMarker": self.disposable_runtime_marker,
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.snapshot)

    @property
    def reference(self) -> MbomExecutionProfileReference:
        return MbomExecutionProfileReference(
            profile_id=self.profile_id,
            profile_version=self.profile_version,
            target_mode=self.target_mode,
            environment_code=self.environment_code,
            projection_policy_id=self.projection_policy_id,
            projection_policy_version=self.projection_policy_version,
            projection_policy_hash=self.projection_policy_hash,
            snapshot_hash=self.snapshot_hash,
        )

    def permits(self, actor_user_id: str) -> bool:
        if not isinstance(actor_user_id, str):
            return False
        return actor_user_id.casefold() in {
            value.casefold() for value in self.requester_user_ids
        }

    def _validate_mock(self) -> None:
        if (
            self.environment_code != "mock"
            or self.allowed_operations
            or self.adapter_resolver is not None
            or self.base_url is not None
            or self.allowed_hostnames
            or self.secret_reference is not None
            or self.response_authentication is not None
            or self.connect_timeout_seconds is not None
            or self.read_timeout_seconds is not None
            or self.non_production_attested
            or self.synthetic_test_only
            or self.disposable_runtime_marker
        ):
            raise MbomPublishContractError("Mock MBOM execution profile must remain disabled and network-free.")

    def _validate_synthetic(self) -> None:
        if (
            self.environment_code != "disposable-test"
            or self.allowed_operations != (MBOM_PUBLISH_OPERATION,)
            or not self.synthetic_test_only
            or not self.disposable_runtime_marker
            or self.adapter_resolver is None
            or _PATH_PATTERN.fullmatch(self.adapter_resolver) is None
            or self.base_url is not None
            or self.allowed_hostnames
            or self.secret_reference is not None
            or self.response_authentication is not None
            or self.connect_timeout_seconds is not None
            or self.read_timeout_seconds is not None
            or self.non_production_attested
        ):
            raise MbomPublishContractError(
                "Synthetic MBOM execution is allowed only for disposable network-free proof."
            )

    def _validate_sandbox(self) -> None:
        if (
            self.synthetic_test_only
            or self.disposable_runtime_marker
            or not self.non_production_attested
            or self.allowed_operations != (MBOM_PUBLISH_OPERATION,)
        ):
            raise MbomPublishContractError("Sandbox MBOM execution requires exact non-production enablement.")
        if self.adapter_resolver is None or _PATH_PATTERN.fullmatch(self.adapter_resolver) is None:
            raise MbomPublishContractError("Sandbox MBOM adapter resolver is invalid.")
        if not isinstance(self.base_url, str):
            raise MbomPublishContractError("Sandbox MBOM base URL is required.")
        try:
            parsed = urlsplit(self.base_url)
            port = parsed.port
        except ValueError as error:
            raise MbomPublishContractError("Sandbox MBOM base URL is invalid.") from error
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
            raise MbomPublishContractError("Sandbox MBOM base URL must be one HTTPS origin.")
        hostname = _sandbox_hostname(parsed.hostname)
        normalized_hosts = tuple(_sandbox_hostname(value) for value in self.allowed_hostnames)
        if (
            not normalized_hosts
            or len(set(normalized_hosts)) != len(normalized_hosts)
            or hostname not in normalized_hosts
        ):
            raise MbomPublishContractError("Sandbox MBOM hostname must match its exact allowlist.")
        environment = self.environment_code.casefold()
        if environment in _PRODUCTION_LABELS or environment not in _NON_PRODUCTION_LABELS:
            raise MbomPublishContractError("Sandbox MBOM environment must be explicitly non-production.")
        if (
            not isinstance(self.secret_reference, str)
            or _SECRET_REFERENCE_PATTERN.fullmatch(self.secret_reference) is None
        ):
            raise MbomPublishContractError("Sandbox MBOM credential must use an opaque secret reference.")
        if self.response_authentication not in {"hmac-sha256-v1", "detached-signature-v1"}:
            raise MbomPublishContractError("Sandbox MBOM response authentication is invalid.")
        for value in (self.connect_timeout_seconds, self.read_timeout_seconds):
            if type(value) is not int or not 1 <= value <= 120:
                raise MbomPublishContractError("Sandbox MBOM timeout is invalid.")


def _sandbox_hostname(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise MbomPublishContractError("Sandbox MBOM hostname is invalid.")
    normalized = value.casefold().rstrip(".")
    if _HOST_PATTERN.fullmatch(normalized) is None:
        raise MbomPublishContractError("Sandbox MBOM hostname is invalid.")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise MbomPublishContractError("Sandbox MBOM hostname cannot be an IP literal.")
    labels = set(normalized.split("."))
    if "localhost" in labels or labels & _PRODUCTION_LABELS or not labels & _NON_PRODUCTION_LABELS:
        raise MbomPublishContractError("Sandbox MBOM hostname must be explicitly non-production.")
    return normalized
