from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .project_domain import ProjectSenderError


DISABLED_KEY = "npi_erp_project_sender_disabled"
BASE_URL_KEY = "npi_erp_project_target_base_url"
ENVIRONMENT_KEY = "npi_erp_project_target_environment"
SERVICE_ACTOR_KEY = "npi_erp_project_service_actor_id"
SIGNING_KEY_ID_KEY = "npi_erp_project_signing_key_id"
SIGNING_SECRET_ENV = "NPI_ERP_PROJECT_SIGNING_SECRET"
STATUS_TOKEN_ENV = "NPI_ERP_AUTHORIZATION_TOKEN"
EVENT_PATH = "/api/npi/v1/integration/erpnext/project-source-events"
STATUS_PATH = "/api/npi/v1/integration/erpnext/project-source-receipts"
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ACTOR = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_TEST_ENVIRONMENTS = {"sandbox", "test", "testing", "qa", "staging", "stage"}


@dataclass(frozen=True, slots=True)
class ProjectSenderProfile:
    base_url: str
    environment_code: str
    service_actor_id: str
    signing_key_id: str

    @property
    def event_endpoint(self) -> str:
        return f"{self.base_url}{EVENT_PATH}"

    @property
    def status_endpoint(self) -> str:
        return f"{self.base_url}{STATUS_PATH}"


def project_sender_is_disabled(configuration: object) -> bool:
    return not (
        hasattr(configuration, "get") and configuration.get(DISABLED_KEY) is False
    )


def load_project_sender_profile(configuration: object) -> ProjectSenderProfile:
    if project_sender_is_disabled(configuration):
        raise ProjectSenderError("ERPNext Project sender is disabled.")
    if not hasattr(configuration, "get"):
        raise ProjectSenderError("ERPNext Project sender configuration is unavailable.")
    base_url = _base_url(configuration.get(BASE_URL_KEY))
    environment = configuration.get(ENVIRONMENT_KEY)
    service_actor = configuration.get(SERVICE_ACTOR_KEY)
    signing_key_id = configuration.get(SIGNING_KEY_ID_KEY)
    if (
        not isinstance(environment, str)
        or environment != environment.casefold()
        or environment not in _TEST_ENVIRONMENTS
    ):
        raise ProjectSenderError("ERPNext Project target must be non-production.")
    if not isinstance(service_actor, str) or _ACTOR.fullmatch(service_actor) is None:
        raise ProjectSenderError("ERPNext Project service actor is invalid.")
    if not isinstance(signing_key_id, str) or _KEY_ID.fullmatch(signing_key_id) is None:
        raise ProjectSenderError("ERPNext Project signing key ID is invalid.")
    return ProjectSenderProfile(
        base_url=base_url,
        environment_code=environment,
        service_actor_id=service_actor,
        signing_key_id=signing_key_id,
    )


def _base_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048 or value.endswith("/"):
        raise ProjectSenderError("LaunchFlow base URL is invalid.")
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
        raise ProjectSenderError("LaunchFlow base URL must be an HTTPS origin.")
    return value
