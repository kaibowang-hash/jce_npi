from __future__ import annotations

from frappe import _

from npi_core.foundation.errors import NpiProblem


class ItemPublishUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "ITEM_PUBLISH_REQUEST_UNAVAILABLE",
            _("The exact Item publish request is unavailable."),
        )


class ItemExecutionProfileUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "ITEM_EXECUTION_PROFILE_UNAVAILABLE",
            _("The exact Item execution profile is unavailable."),
        )


class ItemPublishAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "ITEM_PUBLISH_AUTHORITY_UNAVAILABLE",
            _("You are not authorized to request Item execution for this Project."),
        )


class ItemPublishStateConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "ITEM_PUBLISH_STATE_CONFLICT",
            _("The Item publish source or mapping changed. Reload it before continuing."),
        )


class ItemPublishIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "ITEM_PUBLISH_IDEMPOTENCY_CONFLICT",
            _(
                "The idempotency key was already used for a different Item publish request."
            ),
        )


class ItemPublishSourceConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "SOURCE_ENGINEERING_ITEM_CONFLICT",
            _("Repeated engineering identity contains conflicting Item fields."),
        )


__all__ = [
    "ItemExecutionProfileUnavailable",
    "ItemPublishAuthorityUnavailable",
    "ItemPublishIdempotencyConflict",
    "ItemPublishSourceConflict",
    "ItemPublishStateConflict",
    "ItemPublishUnavailable",
]
