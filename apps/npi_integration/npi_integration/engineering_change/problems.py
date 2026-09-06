from __future__ import annotations

from frappe import _

from npi_core.foundation.errors import NpiProblem


class EngineeringChangeIntegrationUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(503, "ENGINEERING_CHANGE_INTEGRATION_UNAVAILABLE", _("Engineering change integration is unavailable."), _("The Engineering Change integration profile is not active for this Project."), retryable=True)


class EngineeringChangeIntegrationConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(409, "ENGINEERING_CHANGE_INTEGRATION_CONFLICT", _("Engineering change integration conflict"), _("Refresh the Engineering Change and retry with its exact current version."))


class EngineeringChangeAuthenticationFailed(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            status=401,
            code="ENGINEERING_CHANGE_AUTHENTICATION_FAILED",
            title=_("Engineering change event authentication failed."),
            detail=_("The signed Engineering Change event could not be accepted."),
        )
