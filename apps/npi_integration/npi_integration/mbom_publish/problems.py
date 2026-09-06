from __future__ import annotations

from frappe import _

from npi_core.foundation.errors import NpiProblem


class MbomPublishUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "MBOM_PUBLISH_REQUEST_UNAVAILABLE",
            _("The exact MBOM publish request is unavailable."),
        )


class MbomExecutionProfileUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "MBOM_EXECUTION_PROFILE_UNAVAILABLE",
            _("The exact MBOM execution profile is unavailable."),
        )


class MbomPublishAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "MBOM_PUBLISH_AUTHORITY_UNAVAILABLE",
            _("You are not authorized to request MBOM execution for this Project."),
        )


class MbomPublishStateConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "MBOM_PUBLISH_STATE_CONFLICT",
            _("The MBOM source or mapping changed. Reload it before continuing."),
        )


class MbomPublishIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "MBOM_PUBLISH_IDEMPOTENCY_CONFLICT",
            _("The idempotency key was already used for a different MBOM publish request."),
        )


class MbomPublishStreamActive(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "MBOM_PUBLISH_STREAM_ACTIVE",
            _("Another MBOM publish request is active for this source stream."),
        )


class MbomPublishEffectRetained(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "MBOM_PUBLISH_EFFECT_RETAINED",
            _("This exact MBOM publish effect was already retained and cannot be replayed."),
        )


class MbomPublishReconciliationRequired(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "MBOM_PUBLISH_RECONCILIATION_REQUIRED",
            _("The MBOM source stream requires reconciliation before another request can be queued."),
        )


__all__ = [
    "MbomExecutionProfileUnavailable",
    "MbomPublishAuthorityUnavailable",
    "MbomPublishEffectRetained",
    "MbomPublishIdempotencyConflict",
    "MbomPublishReconciliationRequired",
    "MbomPublishStateConflict",
    "MbomPublishStreamActive",
    "MbomPublishUnavailable",
]
