from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

RECEIVER_DISABLED_KEY = "npi_erp_connector_disabled"
ITEM_PROFILE_KEY = "npi_erp_connector_item_profile"
_NAMING_SERIES = re.compile(r"^[A-Za-z0-9._:/#-]{1,140}$")
_FIELDNAME = re.compile(r"^custom_[a-z][a-z0-9_]{1,62}$")
_SOURCE_ATTRIBUTE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}$")


class ItemConfigurationError(ValueError):
    """Raised when the Site has no exact approved Item execution profile."""


@dataclass(frozen=True, slots=True)
class ItemReceiverProfile:
    item_group: str
    erp_naming_series: str
    uom_map: Mapping[str, str]
    attribute_field_map: Mapping[str, str]
    ignored_attributes: tuple[str, ...]

    def target_uom(self, source_uom: str) -> str:
        value = self.uom_map.get(source_uom)
        if value is None:
            raise ItemConfigurationError(
                "Engineering UOM has no approved ERPNext mapping."
            )
        return value

    def attribute_values(
        self, attributes: tuple[tuple[str, str], ...]
    ) -> dict[str, str]:
        source = dict(attributes)
        declared = set(self.attribute_field_map) | set(self.ignored_attributes)
        if set(source) != declared:
            raise ItemConfigurationError(
                "Engineering Item attributes do not match the approved mapping."
            )
        return {
            fieldname: source[key]
            for key, fieldname in self.attribute_field_map.items()
        }


def receiver_is_disabled(configuration: object) -> bool:
    return not (
        hasattr(configuration, "get")
        and configuration.get(RECEIVER_DISABLED_KEY) is False
    )


def load_item_profile(configuration: object) -> ItemReceiverProfile:
    if receiver_is_disabled(configuration):
        raise ItemConfigurationError("ERPNext integration receiver is disabled.")
    if not hasattr(configuration, "get"):
        raise ItemConfigurationError(
            "ERPNext integration configuration is unavailable."
        )
    value = configuration.get(ITEM_PROFILE_KEY)
    if not isinstance(value, Mapping) or set(value) != {
        "itemGroup",
        "erpNamingSeries",
        "uomMap",
        "attributeFieldMap",
        "ignoredAttributes",
    }:
        raise ItemConfigurationError("ERPNext Item profile shape is invalid.")
    item_group = _text(value["itemGroup"], "itemGroup", 140)
    naming_series = value["erpNamingSeries"]
    if (
        not isinstance(naming_series, str)
        or _NAMING_SERIES.fullmatch(naming_series) is None
    ):
        raise ItemConfigurationError("ERPNext Item naming series is invalid.")
    uom_map = _string_map(value["uomMap"], "uomMap", maximum=128)
    attribute_map = _string_map(
        value["attributeFieldMap"],
        "attributeFieldMap",
        maximum=64,
        allow_empty=True,
    )
    if any(_SOURCE_ATTRIBUTE.fullmatch(key) is None for key in attribute_map):
        raise ItemConfigurationError("ERPNext Item attribute source is invalid.")
    if any(
        _FIELDNAME.fullmatch(fieldname) is None for fieldname in attribute_map.values()
    ):
        raise ItemConfigurationError(
            "ERPNext Item attribute target must be an explicit Custom Field."
        )
    raw_ignored = value["ignoredAttributes"]
    if (
        isinstance(raw_ignored, (str, bytes))
        or not isinstance(raw_ignored, Sequence)
        or len(raw_ignored) > 64
        or any(
            not isinstance(item, str) or _SOURCE_ATTRIBUTE.fullmatch(item) is None
            for item in raw_ignored
        )
    ):
        raise ItemConfigurationError("ERPNext ignored Item attributes are invalid.")
    ignored = tuple(sorted(raw_ignored))
    if len(set(ignored)) != len(ignored) or set(ignored) & set(attribute_map):
        raise ItemConfigurationError("ERPNext Item attribute mapping is ambiguous.")
    return ItemReceiverProfile(
        item_group, naming_series, uom_map, attribute_map, ignored
    )


def _string_map(
    value: object,
    label: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> dict[str, str]:
    minimum = 0 if allow_empty else 1
    if not isinstance(value, Mapping) or not minimum <= len(value) <= maximum:
        raise ItemConfigurationError(f"ERPNext {label} is invalid.")
    result: dict[str, str] = {}
    for key, item in value.items():
        result[_text(key, label, 140)] = _text(item, label, 140)
    return result


def _text(value: object, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise ItemConfigurationError(f"ERPNext {label} is invalid.")
    return value
