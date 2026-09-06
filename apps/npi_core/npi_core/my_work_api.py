from __future__ import annotations

import re
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.my_work.domain import (
    MyWorkPriority,
    MyWorkPriorityScheme,
    MyWorkView,
)
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_project_collaboration_routes_enabled,
    response_request_id,
)


_QUERY_FIELDS = frozenset(
    {
        "view",
        "projectId",
        "priorityScheme",
        "priorityValue",
        "search",
        "cursor",
        "limit",
    }
)
_CURSOR_PATTERN = re.compile(r"^[A-Za-z0-9._~:-]{1,500}$")


class MyWorkRepositoryLike(Protocol):
    def query(
        self,
        *,
        view: MyWorkView,
        project_global_id: UUID | None,
        priority: MyWorkPriority | None,
        search: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, object]: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> MyWorkRepositoryLike:
    from npi_core.my_work.frappe_repository import FrappeMyWorkRepository

    return FrappeMyWorkRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_work(
    view: Any = None,
    projectId: Any = None,
    priorityScheme: Any = None,
    priorityValue: Any = None,
    search: Any = None,
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Return the authenticated actor's closed, read-only My Work page."""

    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_project_collaboration_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        if principal.is_external:
            raise PermissionDenied()
        reject_unexpected_request_fields(_QUERY_FIELDS, request_fields)
        request_id = success_headers["X-Request-ID"]
        trace_id = current_trace_id.get()
        if trace_id is None:
            raise RuntimeError("The My Work query has no trace identity.")
        repository = _repository_factory(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        response = repository.query(
            view=_view(view),
            project_global_id=_optional_uuid(projectId, "projectId"),
            priority=_priority(priorityScheme, priorityValue),
            search=_optional_search(search),
            cursor=_optional_cursor(cursor),
            limit=_limit(limit),
        )
        success_headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


def _view(value: object) -> MyWorkView:
    if not isinstance(value, str):
        raise _field_problem("view", _("Select a supported value."))
    try:
        return MyWorkView(value)
    except ValueError as error:
        raise _field_problem(
            "view",
            _("Select a supported value."),
        ) from error


def _optional_uuid(value: object, path: str) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid global ID.")) from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise _field_problem(path, _("Enter a valid global ID."))
    return parsed


def _priority(
    scheme: object,
    value: object,
) -> MyWorkPriority | None:
    if scheme in (None, "") and value in (None, ""):
        return None
    if not isinstance(scheme, str) or not isinstance(value, str):
        raise _field_problem(
            "priorityScheme",
            _("Select a supported value."),
        )
    try:
        return MyWorkPriority(
            MyWorkPriorityScheme(scheme),
            value,
        )
    except (ValueError, TypeError) as error:
        raise _field_problem(
            "priorityScheme",
            _("Select a supported value."),
        ) from error


def _optional_search(value: object) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise _field_problem("search", _("Enter a valid value."))
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > 140
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise _field_problem("search", _("Enter a valid value."))
    return normalized


def _optional_cursor(value: object) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or _CURSOR_PATTERN.fullmatch(value) is None:
        raise _field_problem("cursor", _("Enter a valid cursor."))
    return value


def _limit(value: object) -> int:
    if value in (None, ""):
        return 50
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,2}", value) is not None:
        parsed = int(value)
    else:
        raise _field_problem("limit", _("Enter a positive integer."))
    if parsed < 1 or parsed > 100:
        raise _field_problem("limit", _("Enter a positive integer."))
    return parsed


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
