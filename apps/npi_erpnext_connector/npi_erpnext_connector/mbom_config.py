from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


MBOM_DISABLED_KEY = "npi_erp_connector_mbom_disabled"
MBOM_PROFILE_KEY = "npi_erp_connector_mbom_profile"


class MbomConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MbomReceiverProfile:
    company: str
    custom_temporary_bom_value: str | None


def mbom_receiver_is_disabled(configuration: object) -> bool:
    return not (
        hasattr(configuration, "get")
        and configuration.get(MBOM_DISABLED_KEY) is False
    )


def load_mbom_profile(configuration: object) -> MbomReceiverProfile:
    if mbom_receiver_is_disabled(configuration):
        raise MbomConfigurationError("ERPNext MBOM receiver is disabled.")
    if not hasattr(configuration, "get"):
        raise MbomConfigurationError("ERPNext MBOM configuration is unavailable.")
    value = configuration.get(MBOM_PROFILE_KEY)
    allowed_keys = {"company", "customTemporaryBomValue"}
    if (
        not isinstance(value, Mapping)
        or "company" not in value
        or not set(value).issubset(allowed_keys)
    ):
        raise MbomConfigurationError("ERPNext MBOM profile shape is invalid.")
    company = value["company"]
    if (
        not isinstance(company, str)
        or not company
        or company != company.strip()
        or len(company) > 140
    ):
        raise MbomConfigurationError("ERPNext MBOM company is invalid.")
    custom_temporary_bom_value = value.get("customTemporaryBomValue")
    if custom_temporary_bom_value not in {None, "Yes", "No"}:
        raise MbomConfigurationError(
            "ERPNext MBOM custom temporary BOM value is invalid."
        )
    return MbomReceiverProfile(company, custom_temporary_bom_value)
