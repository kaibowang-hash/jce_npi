from __future__ import annotations

from frappe import _

from npi_core.foundation.errors import NpiProblem


class IntegrationOperationsUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "INTEGRATION_OPERATION_NOT_FOUND",
            _("The integration operation is unavailable."),
        )


class IntegrationOperationConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "INTEGRATION_OPERATION_CONFLICT",
            _("The integration operation changed before the action was applied."),
            retryable=True,
        )


class IntegrationOperationsRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "INTEGRATION_OPERATIONS_ROUTES_DISABLED",
            _("Integration operations are temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )
