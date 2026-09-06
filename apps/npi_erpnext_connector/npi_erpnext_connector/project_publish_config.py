from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


ENABLED_KEY = "npi_erp_project_publish_receiver_enabled"
PROFILE_KEY = "npi_erp_project_publish_receiver_profile"
_PROFILE_KEYS = {"profileId", "profileVersion", "environmentCode", "company", "namingSeries"}
_NON_PRODUCTION = {"sandbox", "test", "testing", "qa", "staging", "stage", "development", "dev"}


class ProjectReceiverConfigurationError(ValueError):
    """Raised when the Project receiver profile is unavailable or unsafe."""


@dataclass(frozen=True, slots=True)
class ProjectReceiverProfile:
    profile_id: str
    profile_version: int
    environment_code: str
    company: str
    naming_series: str


def receiver_is_disabled(configuration: object) -> bool:
    return not (hasattr(configuration, "get") and configuration.get(ENABLED_KEY) is True)


def load_receiver_profile(configuration: object) -> ProjectReceiverProfile:
    if receiver_is_disabled(configuration):
        raise ProjectReceiverConfigurationError("ERP Project receiver is disabled.")
    value = configuration.get(PROFILE_KEY)
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise ProjectReceiverConfigurationError("ERP Project receiver profile is invalid.")
    profile_id = _text(value["profileId"], "profileId", 128)
    version = value["profileVersion"]
    if type(version) is not int or version < 1:
        raise ProjectReceiverConfigurationError("ERP Project receiver profile version is invalid.")
    environment = _text(value["environmentCode"], "environmentCode", 64).casefold()
    if environment not in _NON_PRODUCTION:
        raise ProjectReceiverConfigurationError("ERP Project receiver must be non-production.")
    company = _text(value["company"], "company", 140)
    naming_series = _text(value["namingSeries"], "namingSeries", 140)
    if not naming_series.startswith("PROJ-"):
        raise ProjectReceiverConfigurationError("ERP Project naming series is invalid.")
    return ProjectReceiverProfile(profile_id, version, environment, company, naming_series)


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ProjectReceiverConfigurationError(f"ERP Project receiver {label} is invalid.")
    return value
