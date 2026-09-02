from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.collaboration.domain import MeetingDraft, preference_email_kinds
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.project_api import ProjectUnavailable
from npi_core.reporting.domain import page_size
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_reporting_routes_enabled,
    response_request_id,
)


_CREATE_MEETING_FIELDS = frozenset(
    {
        "expectedProjectVersion",
        "templateRef",
        "title",
        "occurredAt",
        "attendeeUserIds",
        "sections",
        "items",
    }
)
_FEED_FIELDS = frozenset({"unreadOnly", "cursor", "limit"})
_MARK_READ_FIELDS = frozenset({"expectedVersion"})
_PREFERENCE_FIELDS = frozenset({"expectedVersion", "emailKinds"})


class NotificationUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(404, "NOTIFICATION_UNAVAILABLE", _("The notification is unavailable."))


class CollaborationRepositoryLike(Protocol):
    def list_meetings(self, project_id: UUID) -> dict[str, object] | None: ...

    def create_meeting(
        self,
        project_id: UUID,
        *,
        expected_project_version: int,
        idempotency_key: str,
        draft: MeetingDraft,
    ): ...

    def notification_feed(self, *, unread_only: bool, cursor: object | None, limit: int) -> dict[str, object]: ...

    def mark_notification_read(
        self,
        notification_id: UUID,
        *,
        expected_version: int,
        idempotency_key: str,
    ): ...

    def notification_preference(self) -> dict[str, object]: ...

    def set_notification_preference(
        self,
        *,
        expected_version: int,
        email_kinds: tuple,
        idempotency_key: str,
    ): ...


def _repository_factory(*, principal: Principal, request_id: str, trace_id: str) -> CollaborationRepositoryLike:
    from npi_core.collaboration.frappe_repository import FrappeCollaborationRepository

    return FrappeCollaborationRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_meetings(**request_fields: Any) -> dict[str, Any] | None:
    return _read_call(
        frozenset(),
        request_fields,
        lambda repository: _required_project_response(
            repository.list_meetings(_route_uuid("project_id"))
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_project_meeting(
    expectedProjectVersion: Any = None,
    templateRef: Any = None,
    title: Any = None,
    occurredAt: Any = None,
    attendeeUserIds: Any = None,
    sections: Any = None,
    items: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        _CREATE_MEETING_FIELDS,
        request_fields,
        lambda repository, key: _required_project_outcome(
            repository.create_meeting(
                _route_uuid("project_id"),
                expected_project_version=_positive_integer(
                    expectedProjectVersion, "expectedProjectVersion", allow_zero=False
                ),
                idempotency_key=key,
                draft=MeetingDraft.parse(
                    template_ref_value=templateRef,
                    title_value=title,
                    occurred_at_value=occurredAt,
                    attendee_values=attendeeUserIds,
                    section_values=sections,
                    item_values=items,
                ),
            )
        ),
        success_status=201,
        require_system_manager=True,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_notifications(
    unreadOnly: Any = None,
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _read_call(
        _FEED_FIELDS,
        request_fields,
        lambda repository: repository.notification_feed(
            unread_only=_query_boolean(unreadOnly, default=False),
            cursor=cursor,
            limit=page_size(_optional_integer(limit)),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def mark_notification_read(
    expectedVersion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        _MARK_READ_FIELDS,
        request_fields,
        lambda repository, key: _required_notification_outcome(
            repository.mark_notification_read(
                _route_uuid("notification_id"),
                expected_version=_positive_integer(expectedVersion, "expectedVersion", allow_zero=False),
                idempotency_key=key,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_notification_preference(**request_fields: Any) -> dict[str, Any] | None:
    return _read_call(
        frozenset(),
        request_fields,
        lambda repository: repository.notification_preference(),
    )


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def set_notification_preference(
    expectedVersion: Any = None,
    emailKinds: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command_call(
        _PREFERENCE_FIELDS,
        request_fields,
        lambda repository, key: repository.set_notification_preference(
            expected_version=_positive_integer(expectedVersion, "expectedVersion", allow_zero=True),
            email_kinds=preference_email_kinds(emailKinds),
            idempotency_key=key,
        ).response,
    )


def _read_call(allowed: frozenset[str], fields: dict[str, Any], operation):
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, object]:
        repository, request_id = _context(allowed, fields, command=False)
        headers["X-Request-ID"] = request_id
        return operation(repository)

    return frappe_domain_call(handle, cache_control="private, no-store", response_headers=headers)


def _command_call(
    allowed: frozenset[str],
    fields: dict[str, Any],
    operation,
    *,
    success_status: int = 200,
    require_system_manager: bool = False,
):
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, object]:
        repository, request_id = _context(
            allowed,
            fields,
            command=True,
            require_system_manager=require_system_manager,
        )
        headers["X-Request-ID"] = request_id
        key = actor_idempotency_key_hash(
            authenticated_user(), frappe.get_request_header("Idempotency-Key")
        )
        return operation(repository, key)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=success_status,
        response_headers=headers,
    )


def _context(
    allowed: frozenset[str],
    fields: dict[str, Any],
    *,
    command: bool,
    require_system_manager: bool = False,
):
    require_reporting_routes_enabled()
    actor = authenticated_user()
    if command:
        require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or (
        require_system_manager and "System Manager" not in principal.roles
    ):
        raise PermissionDenied()
    reject_unexpected_request_fields(allowed, fields)
    request_id = response_request_id()
    trace_id = current_trace_id.get() or request_id
    return _repository_factory(principal=principal, request_id=request_id, trace_id=trace_id), request_id


def _required_project_response(value):
    if value is None:
        raise ProjectUnavailable()
    return value


def _required_project_outcome(value):
    if value is None:
        raise ProjectUnavailable()
    return value.response


def _required_notification_outcome(value):
    if value is None:
        raise NotificationUnavailable()
    return value.response


def _route_uuid(name: str) -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    value = route_params.get(name) if hasattr(route_params, "get") else None
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise RequestValidationFailed([{"path": name, "message": _("Enter a valid identifier.")}]) from None


def _positive_integer(value: object, path: str, *, allow_zero: bool) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise RequestValidationFailed([{"path": path, "message": _("Enter a valid integer.")}])
    minimum = 0 if allow_zero else 1
    if parsed < minimum:
        raise RequestValidationFailed([{"path": path, "message": _("Enter a valid integer.")}])
    return parsed


def _optional_integer(value: object) -> int | None:
    if value is None or value == "":
        return None
    return _positive_integer(value, "limit", allow_zero=False)


def _query_boolean(value: object, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if value is True or value == "true" or value == "1" or value == 1:
        return True
    if value is False or value == "false" or value == "0" or value == 0:
        return False
    raise RequestValidationFailed([{"path": "unreadOnly", "message": _("Select true or false.")}])
