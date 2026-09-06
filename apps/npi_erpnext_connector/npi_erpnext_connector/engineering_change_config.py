from __future__ import annotations


DISABLED_KEY = "npi_erp_engineering_change_receiver_disabled"


def receiver_is_disabled(configuration: object) -> bool:
    return not (
        hasattr(configuration, "get") and configuration.get(DISABLED_KEY) is False
    )
