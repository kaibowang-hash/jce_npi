from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from npi_erpnext_connector.master_data_domain import MasterDataSenderError


DISABLED_KEY = "npi_erp_master_data_sender_disabled"
BASE_URL_KEY = "npi_erp_master_data_target_base_url"
ENVIRONMENT_KEY = "npi_erp_master_data_source_environment"
TOKEN_ENV = "NPI_ERP_AUTHORIZATION_TOKEN"
ENDPOINT_PATH = "/api/npi/v1/integration/erpnext/master-data"
_TEST_ENVIRONMENTS = {"sandbox", "test", "testing", "qa", "staging", "stage"}


@dataclass(frozen=True, slots=True)
class MasterDataSenderProfile:
    base_url: str
    environment_code: str

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}{ENDPOINT_PATH}"


def master_data_sender_is_disabled(configuration: object) -> bool:
    return not (
        hasattr(configuration, "get") and configuration.get(DISABLED_KEY) is False
    )


def load_master_data_profile(configuration: object) -> MasterDataSenderProfile:
    if master_data_sender_is_disabled(configuration):
        raise MasterDataSenderError("ERPNext master data sender is disabled.")
    if not hasattr(configuration, "get"):
        raise MasterDataSenderError(
            "ERPNext master data sender configuration is unavailable."
        )
    environment = configuration.get(ENVIRONMENT_KEY)
    if (
        not isinstance(environment, str)
        or environment != environment.casefold()
        or environment not in _TEST_ENVIRONMENTS
    ):
        raise MasterDataSenderError("ERPNext master data source must be non-production.")
    return MasterDataSenderProfile(_base_url(configuration.get(BASE_URL_KEY)), environment)


def _base_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048 or value.endswith("/"):
        raise MasterDataSenderError("LaunchFlow base URL is invalid.")
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
        raise MasterDataSenderError("LaunchFlow base URL must be an HTTPS origin.")
    return value
