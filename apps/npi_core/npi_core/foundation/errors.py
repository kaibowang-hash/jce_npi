from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from frappe import _
except ImportError:  # Keeps domain helpers testable before a bench is initialized.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


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
        super().__init__(
            401, "AUTHENTICATION_REQUIRED", _("Authentication is required.")
        )


class PermissionDenied(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "PERMISSION_DENIED",
            _("You do not have permission to perform this action."),
        )


class RequestValidationFailed(NpiProblem):
    def __init__(self, field_errors: list[dict[str, str]]) -> None:
        super().__init__(
            422,
            "VALIDATION_FAILED",
            _("Correct the highlighted fields and submit again."),
            field_errors=field_errors,
        )


class CsrfTokenInvalid(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "CSRF_TOKEN_INVALID",
            _("The request could not be verified."),
            retryable=True,
        )


class MalformedRequest(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            400,
            "MALFORMED_REQUEST",
            _("The request body is invalid."),
        )


class InternalServerError(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            500,
            "INTERNAL_SERVER_ERROR",
            _("The request could not be completed."),
            retryable=True,
        )


class ApiRouteNotFound(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "API_ROUTE_NOT_FOUND",
            _("The requested NPI API route was not found."),
        )


class VersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "VERSION_CONFLICT",
            _("The object was changed by another user."),
        )


class UnsupportedLanguage(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "LANGUAGE_NOT_SUPPORTED",
            _("The selected language is not supported."),
            field_errors=[
                {
                    "path": "language",
                    "message": _(
                        "Select English, Simplified Chinese, or Traditional Chinese."
                    ),
                }
            ],
        )


class LocalizationUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "LOCALIZATION_UNAVAILABLE",
            _("Localization resources are unavailable."),
        )


class TenantScopeUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "TENANT_SCOPE_UNAVAILABLE",
            _("Project tenant authorization is unavailable."),
        )


class CursorSigningUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "CURSOR_SIGNING_UNAVAILABLE",
            _("Secure pagination is unavailable."),
        )


class ProjectCollaborationRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "PROJECT_COLLABORATION_ROUTES_DISABLED",
            _("Project collaboration is temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


class DocumentRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DOCUMENT_ROUTES_DISABLED",
            _("Document and design revision is temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


class DocumentReleaseRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DOCUMENT_RELEASE_ROUTES_DISABLED",
            _("Document review and release is temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


class DocumentBaselineRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "DOCUMENT_BASELINE_ROUTES_DISABLED",
            _("Document baselines are temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


class EngineeringBomRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "EBOM_ROUTES_DISABLED",
            _("The EBOM workspace is temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )
