from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NpiProblem(Exception):
    status: int
    code: str
    title: str
    detail: str = ""
    retryable: bool = False
    field_errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self, trace_id: str) -> dict[str, Any]:
        problem: dict[str, Any] = {
            "type": f"urn:npi:problem:{self.code.lower()}",
            "title": self.title,
            "status": self.status,
            "code": self.code,
            "traceId": trace_id,
            "retryable": self.retryable,
        }
        if self.detail:
            problem["detail"] = self.detail
        if self.field_errors:
            problem["fieldErrors"] = self.field_errors
        return problem


class AuthenticationRequired(NpiProblem):
    def __init__(self) -> None:
        super().__init__(401, "AUTHENTICATION_REQUIRED", "Authentication is required.")


class PermissionDenied(NpiProblem):
    def __init__(self) -> None:
        super().__init__(403, "PERMISSION_DENIED", "You do not have permission to perform this action.")


class VersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(409, "VERSION_CONFLICT", "The object was changed by another user.")
