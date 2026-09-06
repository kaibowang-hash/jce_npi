from __future__ import annotations

from frappe import _

from npi_core.foundation.errors import NpiProblem


class FormalQualityLinkUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "FORMAL_QUALITY_LINK_UNAVAILABLE",
            _("The exact formal quality link is unavailable."),
        )


class FormalQualityLinkAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "FORMAL_QUALITY_LINK_AUTHORITY_UNAVAILABLE",
            _("You are not authorized to link this formal quality reference."),
        )


class FormalQualityLinkSourceConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "FORMAL_QUALITY_LINK_SOURCE_CONFLICT",
            _("The quality source changed. Reload it before linking formal quality."),
        )


class FormalQualityProjectionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "FORMAL_QUALITY_PROJECTION_CONFLICT",
            _("The formal quality observation changed. Reload it before linking."),
        )


class FormalQualityLinkHeadConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "FORMAL_QUALITY_LINK_HEAD_CONFLICT",
            _("The formal quality link changed. Reload it before continuing."),
        )


class FormalQualityLinkIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "FORMAL_QUALITY_LINK_IDEMPOTENCY_CONFLICT",
            _("The idempotency key was already used for a different formal quality link command."),
        )


__all__ = [
    "FormalQualityLinkAuthorityUnavailable",
    "FormalQualityLinkHeadConflict",
    "FormalQualityLinkIdempotencyConflict",
    "FormalQualityLinkSourceConflict",
    "FormalQualityLinkUnavailable",
    "FormalQualityProjectionConflict",
]
