from __future__ import annotations

from dataclasses import dataclass

from .domain import QualityLinkContractError


@dataclass(frozen=True, slots=True)
class QualityLinkConfiguration:
    """Checkpoint-1 configuration: deliberately disabled and network-free."""

    enabled: bool = False
    authority_policy_ref: str | None = None
    freshness_policy_ref: str | None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise QualityLinkContractError("Quality link enablement must be boolean.")
        if self.enabled or self.authority_policy_ref is not None or self.freshness_policy_ref is not None:
            raise QualityLinkContractError(
                "Formal quality linking remains disabled until authority and freshness policies are approved."
            )


def default_quality_link_configurations() -> tuple[QualityLinkConfiguration, ...]:
    """Install no profile or default business row."""

    return ()
