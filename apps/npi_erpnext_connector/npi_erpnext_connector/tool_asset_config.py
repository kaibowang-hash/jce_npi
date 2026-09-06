from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from npi_erpnext_connector.tool_asset_contract import (
    CREATE_OPERATION,
    UPDATE_OPERATION,
)

CREATE_DISABLED_KEY = "npi_erp_connector_tool_asset_create_disabled"
UPDATE_DISABLED_KEY = "npi_erp_connector_tool_asset_update_disabled"
PROFILE_KEY = "npi_erp_connector_tool_asset_profile"
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?$")


class ToolAssetConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ToolAssetReceiverProfile:
    company: str
    location: str
    item_code: str
    purchase_date_source: str
    purchase_amount: Decimal


def operation_is_disabled(configuration: object, operation: str) -> bool:
    key = {
        CREATE_OPERATION: CREATE_DISABLED_KEY,
        UPDATE_OPERATION: UPDATE_DISABLED_KEY,
    }.get(operation)
    return key is None or not (
        hasattr(configuration, "get") and configuration.get(key) is False
    )


def load_tool_asset_profile(configuration: object) -> ToolAssetReceiverProfile:
    if not hasattr(configuration, "get"):
        raise ToolAssetConfigurationError(
            "ERPNext Tool Asset configuration is unavailable."
        )
    value = configuration.get(PROFILE_KEY)
    keys = {
        "company",
        "location",
        "itemCode",
        "purchaseDateSource",
        "purchaseAmount",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ToolAssetConfigurationError(
            "ERPNext Tool Asset profile shape is invalid."
        )
    for key in ("company", "location", "itemCode"):
        field = value[key]
        if (
            not isinstance(field, str)
            or not field
            or field != field.strip()
            or len(field) > 140
        ):
            raise ToolAssetConfigurationError(
                f"ERPNext Tool Asset {key} is invalid."
            )
    if value["purchaseDateSource"] != "acceptedAt":
        raise ToolAssetConfigurationError(
            "ERPNext Tool Asset purchase date policy is invalid."
        )
    raw_amount = value["purchaseAmount"]
    if (
        not isinstance(raw_amount, str)
        or _AMOUNT.fullmatch(raw_amount) is None
    ):
        raise ToolAssetConfigurationError(
            "ERPNext Tool Asset purchase amount is invalid."
        )
    try:
        purchase_amount = Decimal(raw_amount)
    except InvalidOperation as error:
        raise ToolAssetConfigurationError(
            "ERPNext Tool Asset purchase amount is invalid."
        ) from error
    if purchase_amount <= 0:
        raise ToolAssetConfigurationError(
            "ERPNext Tool Asset purchase amount is invalid."
        )
    return ToolAssetReceiverProfile(
        str(value["company"]),
        str(value["location"]),
        str(value["itemCode"]),
        "acceptedAt",
        purchase_amount,
    )
