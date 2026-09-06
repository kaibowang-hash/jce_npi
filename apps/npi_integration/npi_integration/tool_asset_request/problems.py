from __future__ import annotations

from frappe import _

from npi_core.foundation.errors import NpiProblem


class ToolAssetExecutionUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TOOL_ASSET_EXECUTION_UNAVAILABLE",
            _("The exact Tool Asset execution request is unavailable."),
        )


class ToolAssetExecutionProfileUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "TOOL_ASSET_EXECUTION_PROFILE_UNAVAILABLE",
            _("The exact Tool Asset execution profile is unavailable."),
        )


class ToolAssetExecutionAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "TOOL_ASSET_EXECUTION_AUTHORITY_UNAVAILABLE",
            _("You are not authorized to request Tool Asset execution for this Project."),
        )


class ToolAssetExecutionApprovalUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOL_ASSET_EXECUTION_APPROVAL_UNAVAILABLE",
            _("Verified business approval is unavailable for Tool Asset execution."),
        )


class ToolAssetExecutionStateConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOL_ASSET_EXECUTION_STATE_CONFLICT",
            _("The Tooling source or Asset mapping changed. Reload it before continuing."),
        )


class ToolAssetExecutionIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOL_ASSET_EXECUTION_IDEMPOTENCY_CONFLICT",
            _(
                "The idempotency key was already used for a different Tool Asset operation or request."
            ),
        )


class ToolAssetExecutionStreamActive(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TOOL_ASSET_EXECUTION_STREAM_ACTIVE",
            _(
                "Another Tool Asset execution request is active for this physical Tooling Set."
            ),
        )


__all__ = [
    "ToolAssetExecutionApprovalUnavailable",
    "ToolAssetExecutionAuthorityUnavailable",
    "ToolAssetExecutionIdempotencyConflict",
    "ToolAssetExecutionProfileUnavailable",
    "ToolAssetExecutionStateConflict",
    "ToolAssetExecutionStreamActive",
    "ToolAssetExecutionUnavailable",
]
