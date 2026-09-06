from __future__ import annotations

RECEIVER_DISABLED_KEY = "npi_erp_trial_summary_receiver_disabled"


def receiver_is_disabled(configuration: object) -> bool:
    """Fail closed unless the operation-specific switch is exactly false."""

    return not (
        hasattr(configuration, "get")
        and configuration.get(RECEIVER_DISABLED_KEY) is False
    )
