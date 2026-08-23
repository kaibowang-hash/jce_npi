from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from .execution_domain import (
    TOOL_ASSET_EXECUTION_OPERATIONS,
    ToolAssetExecutionContractError,
    ToolAssetExecutionProfileReference,
    ToolAssetExecutionTargetMode,
    canonical_hash,
)


_HOST = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$")
_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{2,254}$")
_SECRET = re.compile(r"^secrets?/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_NON_PRODUCTION = frozenset({"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage"})
_PRODUCTION = frozenset({"prod", "production", "live"})


@dataclass(frozen=True, slots=True)
class ToolAssetExecutionProfile:
    profile_id: str
    profile_version: int
    tenant_id: str
    project_global_id: str
    target_mode: ToolAssetExecutionTargetMode
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
        if not isinstance(self.target_mode, ToolAssetExecutionTargetMode):
            raise ToolAssetExecutionContractError("Tool Asset profile target mode is unsupported.")
        if type(self.requester_user_ids) is not tuple or type(self.allowed_operations) is not tuple or type(self.allowed_hostnames) is not tuple:
            raise ToolAssetExecutionContractError("Tool Asset profile allowlists must be immutable tuples.")
        if any(type(value) is not bool for value in (self.non_production_attested, self.synthetic_test_only, self.follow_redirects, self.disposable_runtime_marker)):
            raise ToolAssetExecutionContractError("Tool Asset profile safety flags must be boolean.")
        if self.follow_redirects:
            raise ToolAssetExecutionContractError("Tool Asset adapters cannot follow redirects.")
        if not isinstance(self.tenant_id, str) or self.tenant_id != self.tenant_id.strip() or _TENANT.fullmatch(self.tenant_id) is None:
            raise ToolAssetExecutionContractError("Tool Asset profile tenant is invalid.")
        try:
            UUID(self.project_global_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise ToolAssetExecutionContractError("Tool Asset profile Project is invalid.") from error
        if type(self.profile_version) is not int or self.profile_version < 1 or type(self.projection_policy_version) is not int or self.projection_policy_version < 1:
            raise ToolAssetExecutionContractError("Tool Asset profile versions must be positive.")
        if not self.profile_id or not self.environment_code or not self.projection_policy_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", self.profile_id):
            raise ToolAssetExecutionContractError("Tool Asset profile identity is invalid.")
        if not re.fullmatch(r"[a-f0-9]{64}", self.projection_policy_hash):
            raise ToolAssetExecutionContractError("Tool Asset projection policy hash is invalid.")
        if not self.requester_user_ids or len(set(self.requester_user_ids)) != len(self.requester_user_ids) or not all(_actor(value) for value in (*self.requester_user_ids, self.service_actor_user_id)):
            raise ToolAssetExecutionContractError("Tool Asset profile actors are invalid.")
        if self.target_mode is ToolAssetExecutionTargetMode.MOCK:
            self._validate_mock()
        elif self.target_mode is ToolAssetExecutionTargetMode.SYNTHETIC:
            self._validate_synthetic()
        else:
            self._validate_sandbox()

    @property
    def snapshot(self) -> dict[str, object]:
        return {
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
            "responseAuthentication": self.response_authentication,
            "connectTimeoutSeconds": self.connect_timeout_seconds,
            "readTimeoutSeconds": self.read_timeout_seconds,
            "nonProductionAttested": self.non_production_attested,
            "syntheticTestOnly": self.synthetic_test_only,
            "followRedirects": self.follow_redirects,
            "disposableRuntimeMarker": self.disposable_runtime_marker,
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.snapshot)

    @property
    def reference(self) -> ToolAssetExecutionProfileReference:
        return ToolAssetExecutionProfileReference(
            profile_id=self.profile_id,
            profile_version=self.profile_version,
            target_mode=self.target_mode,
            environment_code=self.environment_code,
            projection_policy_id=self.projection_policy_id,
            projection_policy_version=self.projection_policy_version,
            projection_policy_hash=self.projection_policy_hash,
            snapshot_hash=self.snapshot_hash,
        )

    def permits(self, actor_user_id: str, operation: str | None = None) -> bool:
        if not isinstance(actor_user_id, str):
            return False
        return actor_user_id.casefold() in {value.casefold() for value in self.requester_user_ids} and (operation is None or operation in self.allowed_operations)

    def _validate_mock(self) -> None:
        if self.allowed_operations or self.adapter_resolver is not None or self.base_url is not None or self.allowed_hostnames or self.secret_reference is not None or self.response_authentication is not None or self.connect_timeout_seconds is not None or self.read_timeout_seconds is not None or self.non_production_attested or self.synthetic_test_only or self.disposable_runtime_marker:
            raise ToolAssetExecutionContractError("Mock Tool Asset profile must remain disabled and network-free.")

    def _validate_synthetic(self) -> None:
        if not _operation_allowlist(self.allowed_operations) or self.adapter_resolver is None or _PATH.fullmatch(self.adapter_resolver) is None or not self.synthetic_test_only or not self.disposable_runtime_marker or self.base_url is not None or self.allowed_hostnames or self.secret_reference is not None or self.response_authentication is not None or self.connect_timeout_seconds is not None or self.read_timeout_seconds is not None or self.non_production_attested:
            raise ToolAssetExecutionContractError("Synthetic Tool Asset profile is allowed only for disposable network-free proof.")

    def _validate_sandbox(self) -> None:
        if self.synthetic_test_only or self.disposable_runtime_marker or not self.non_production_attested or not _operation_allowlist(self.allowed_operations):
            raise ToolAssetExecutionContractError("Sandbox Tool Asset profile requires exact non-production enablement.")
        if self.adapter_resolver is None or _PATH.fullmatch(self.adapter_resolver) is None or not isinstance(self.base_url, str):
            raise ToolAssetExecutionContractError("Sandbox Tool Asset adapter configuration is invalid.")
        try:
            parsed = urlsplit(self.base_url)
            port = parsed.port
        except ValueError as error:
            raise ToolAssetExecutionContractError("Sandbox Tool Asset base URL is invalid.") from error
        if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or parsed.path not in ("", "/") or port not in (None, 443):
            raise ToolAssetExecutionContractError("Sandbox Tool Asset base URL must be one HTTPS origin.")
        hostname = _sandbox_hostname(parsed.hostname)
        hosts = tuple(_sandbox_hostname(value) for value in self.allowed_hostnames)
        if not hosts or len(set(hosts)) != len(hosts) or hostname not in hosts:
            raise ToolAssetExecutionContractError("Sandbox Tool Asset hostname must match its exact allowlist.")
        environment = self.environment_code.casefold()
        if environment in _PRODUCTION or environment not in _NON_PRODUCTION:
            raise ToolAssetExecutionContractError("Sandbox Tool Asset environment must be explicitly non-production.")
        if not isinstance(self.secret_reference, str) or _SECRET.fullmatch(self.secret_reference) is None or self.response_authentication not in {"hmac-sha256-v1", "detached-signature-v1"}:
            raise ToolAssetExecutionContractError("Sandbox Tool Asset credential or response authentication is invalid.")
        if any(type(value) is not int or not 1 <= value <= 120 for value in (self.connect_timeout_seconds, self.read_timeout_seconds)):
            raise ToolAssetExecutionContractError("Sandbox Tool Asset timeout is invalid.")


def default_tool_asset_execution_profiles() -> tuple[ToolAssetExecutionProfile, ...]:
    """No executable Tool Asset profile is installed by default."""

    return ()


def _actor(value: object) -> bool:
    return isinstance(value, str) and value == value.strip() and re.fullmatch(r"[^\s\x00-\x1f\x7f]{1,254}", value) is not None


def _operation_allowlist(values: tuple[str, ...]) -> bool:
    return bool(values) and len(values) == len(set(values)) and set(values) <= set(TOOL_ASSET_EXECUTION_OPERATIONS)


def _sandbox_hostname(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ToolAssetExecutionContractError("Sandbox Tool Asset hostname is invalid.")
    normalized = value.casefold().rstrip(".")
    if _HOST.fullmatch(normalized) is None:
        raise ToolAssetExecutionContractError("Sandbox Tool Asset hostname is invalid.")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise ToolAssetExecutionContractError("Sandbox Tool Asset hostname cannot be an IP literal.")
    labels = set(normalized.split("."))
    if "localhost" in labels or labels & _PRODUCTION or not labels & _NON_PRODUCTION:
        raise ToolAssetExecutionContractError("Sandbox Tool Asset hostname must be explicitly non-production.")
    return normalized
