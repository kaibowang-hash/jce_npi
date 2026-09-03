from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from npi_erpnext_connector.domain import AuthorizationSenderError, SenderPolicy


DISABLED_KEY = "npi_erp_authorization_sender_disabled"
BASE_URL_KEY = "npi_erp_authorization_target_base_url"
ROLE_MAP_KEY = "npi_erp_authorization_role_map"
PROJECT_MAP_KEY = "npi_erp_authorization_project_map"
PROJECT_ACCESS_KEY = "npi_erp_authorization_project_access_by_role"
TTL_KEY = "npi_erp_authorization_ttl_seconds"
TOKEN_ENV = "NPI_ERP_AUTHORIZATION_TOKEN"
ENDPOINT_PATH = "/api/npi/v1/integration/erpnext/user-authorization"


@dataclass(frozen=True, slots=True)
class SenderProfile:
    base_url: str
    policy: SenderPolicy

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}{ENDPOINT_PATH}"


def sender_is_disabled(configuration: object) -> bool:
    return not (
        hasattr(configuration, "get")
        and configuration.get(DISABLED_KEY) is False
    )


def load_profile(configuration: object) -> SenderProfile:
    if sender_is_disabled(configuration):
        raise AuthorizationSenderError("Authorization sender is disabled.")
    if not hasattr(configuration, "get"):
        raise AuthorizationSenderError("Authorization sender configuration is unavailable.")
    base_url = _base_url(configuration.get(BASE_URL_KEY))
    policy = SenderPolicy.from_mapping(
        {
            "roleMap": configuration.get(ROLE_MAP_KEY),
            "projectMap": configuration.get(PROJECT_MAP_KEY, {}),
            "projectAccessByRole": configuration.get(PROJECT_ACCESS_KEY, {}),
            "ttlSeconds": configuration.get(TTL_KEY),
        }
    )
    return SenderProfile(base_url, policy)


def _base_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048 or value.endswith("/"):
        raise AuthorizationSenderError("LaunchFlow base URL is invalid.")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.port not in {None, 443}
    ):
        raise AuthorizationSenderError("LaunchFlow base URL must be an HTTPS origin.")
    return value[:-1] if value.endswith("/") else value
