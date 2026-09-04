from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from .domain import AdapterMode, ProjectionContractError, ProjectionKind


_SECRET_REFERENCE_PATTERN = re.compile(
    r"^secrets?/[A-Za-z0-9][A-Za-z0-9._-]{0,119}$"
)
_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)
_NON_PRODUCTION_LABELS = frozenset(
    {"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage"}
)
_PRODUCTION_LABELS = frozenset({"prod", "production", "live"})


class ProjectionConfigurationState(StrEnum):
    DISABLED = "disabled"
    ENABLED_NON_PRODUCTION = "enabled_non_production"
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"


@dataclass(frozen=True, slots=True)
class ProjectionAdapterConfiguration:
    mode: AdapterMode = AdapterMode.MOCK
    enabled: bool = False
    base_url: str | None = None
    allowed_hostnames: tuple[str, ...] = ()
    allowed_operations: tuple[ProjectionKind, ...] = ()
    secret_reference: str | None = None
    environment_code: str = "mock"
    non_production_attested: bool = False
    follow_redirects: bool = False
    synthetic_test_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.mode, AdapterMode):
            raise ProjectionContractError("Adapter mode is unsupported.")
        if type(self.enabled) is not bool or type(self.non_production_attested) is not bool:
            raise ProjectionContractError("Adapter enablement flags must be boolean.")
        if type(self.follow_redirects) is not bool or type(self.synthetic_test_only) is not bool:
            raise ProjectionContractError("Adapter safety flags must be boolean.")
        if type(self.allowed_hostnames) is not tuple or type(self.allowed_operations) is not tuple:
            raise ProjectionContractError("Adapter allowlists must be immutable tuples.")
        if self.follow_redirects:
            raise ProjectionContractError("Projection adapters cannot follow redirects.")
        if self.mode is AdapterMode.MOCK:
            self._validate_mock()
        elif self.mode is AdapterMode.SYNTHETIC:
            self._validate_synthetic()
        else:
            self._validate_sandbox()

    @property
    def state(self) -> ProjectionConfigurationState:
        if self.mode is AdapterMode.MOCK:
            return ProjectionConfigurationState.DISABLED
        if self.mode is AdapterMode.SYNTHETIC:
            return ProjectionConfigurationState.SYNTHETIC_TEST_ONLY
        return ProjectionConfigurationState.ENABLED_NON_PRODUCTION

    def _validate_mock(self) -> None:
        if (
            self.enabled
            or self.base_url is not None
            or self.allowed_hostnames
            or self.allowed_operations
            or self.secret_reference is not None
            or self.environment_code != "mock"
            or self.non_production_attested
            or self.synthetic_test_only
        ):
            raise ProjectionContractError(
                "Mock projection mode must remain disabled and network-free."
            )

    def _validate_synthetic(self) -> None:
        if (
            self.enabled
            or not self.synthetic_test_only
            or self.base_url is not None
            or self.allowed_hostnames
            or self.allowed_operations
            or self.secret_reference is not None
            or self.non_production_attested
            or self.environment_code != "disposable-test"
        ):
            raise ProjectionContractError(
                "Synthetic projection mode is allowed only for disposable, network-free proof."
            )

    def _validate_sandbox(self) -> None:
        if not self.enabled or not self.non_production_attested or self.synthetic_test_only:
            raise ProjectionContractError(
                "Sandbox projection mode requires explicit non-production enablement."
            )
        if not isinstance(self.base_url, str):
            raise ProjectionContractError("Sandbox base URL is required.")
        try:
            parsed = urlsplit(self.base_url)
            port = parsed.port
        except ValueError as error:
            raise ProjectionContractError("Sandbox base URL is invalid.") from error
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
            raise ProjectionContractError(
                "Sandbox base URL must be one HTTPS origin without user info, path, query or redirect."
            )
        hostname = _sandbox_hostname(parsed.hostname)
        if (
            not isinstance(self.environment_code, str)
            or self.environment_code != self.environment_code.strip()
        ):
            raise ProjectionContractError("Sandbox environment code is invalid.")
        environment = self.environment_code.casefold()
        if (
            environment in _PRODUCTION_LABELS
            or environment not in _NON_PRODUCTION_LABELS
        ):
            raise ProjectionContractError(
                "Sandbox host and environment must be explicitly non-production."
            )
        normalized_hosts = tuple(
            _sandbox_hostname(value)
            for value in self.allowed_hostnames
        )
        if (
            not normalized_hosts
            or len(set(normalized_hosts)) != len(normalized_hosts)
            or hostname not in normalized_hosts
        ):
            raise ProjectionContractError(
                "Sandbox hostname must match the exact configured allowlist."
            )
        if (
            not self.allowed_operations
            or any(not isinstance(value, ProjectionKind) for value in self.allowed_operations)
            or len(set(self.allowed_operations)) != len(self.allowed_operations)
        ):
            raise ProjectionContractError(
                "Sandbox projection operations must use a non-empty exact allowlist."
            )
        if (
            not isinstance(self.secret_reference, str)
            or _SECRET_REFERENCE_PATTERN.fullmatch(self.secret_reference) is None
        ):
            raise ProjectionContractError(
                "Sandbox credentials must use a separately resolved secret reference."
            )


def _sandbox_hostname(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProjectionContractError("Sandbox hostname is invalid.")
    normalized = value.casefold().rstrip(".")
    if _HOST_PATTERN.fullmatch(normalized) is None:
        raise ProjectionContractError("Sandbox hostname is invalid.")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise ProjectionContractError("Sandbox hostname cannot be an IP literal.")
    labels = set(normalized.split("."))
    if (
        "localhost" in labels
        or labels & _PRODUCTION_LABELS
        or not (labels & _NON_PRODUCTION_LABELS)
    ):
        raise ProjectionContractError(
            "Sandbox hostname must be explicitly non-production."
        )
    return normalized
