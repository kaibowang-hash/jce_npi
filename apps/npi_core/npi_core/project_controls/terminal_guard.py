from __future__ import annotations

from npi_core.foundation.errors import NpiProblem

try:
    from frappe import _
except ImportError:

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


class ProjectHistoryLocked(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PROJECT_HISTORY_LOCKED",
            _("A cancelled or completed Project is protected history."),
        )


def require_mutable_project(project) -> None:
    if str(getattr(project, "lifecycle_state", "")) in {
        "cancelled",
        "completed",
    }:
        raise ProjectHistoryLocked()
