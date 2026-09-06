from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .domain import ReleasedSummaryProjectionContractError


class ReleasedSummaryProjectionConfigurationState(StrEnum):
    DISABLED_CONTRACT_HELD = "disabled_contract_held"


@dataclass(frozen=True, slots=True)
class ReleasedSummaryProjectionConfiguration:
    """The only approved checkpoint-1 configuration is disabled and network-free."""

    enabled: bool = False
    external_contract_approved: bool = False
    profile_reference: None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool or type(self.external_contract_approved) is not bool:
            raise ReleasedSummaryProjectionContractError(
                "Released summary projection enablement flags must be boolean."
            )
        if self.enabled or self.external_contract_approved or self.profile_reference is not None:
            raise ReleasedSummaryProjectionContractError(
                "Released summary projection must remain disabled while the "
                "external contract is held."
            )

    @property
    def state(self) -> ReleasedSummaryProjectionConfigurationState:
        return ReleasedSummaryProjectionConfigurationState.DISABLED_CONTRACT_HELD
