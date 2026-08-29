from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    response_request_id,
)

from .domain import (
    IntegrationActionKind,
    IntegrationOperationKind,
    IntegrationViewState,
)
from .problems import (
    IntegrationOperationsRoutesDisabled,
    IntegrationOperationsUnavailable,
)


_RAW_STATE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")
_LIST_FIELDS = frozenset({"operationKind", "sharedState", "cursor", "limit"})
_ACTION_FIELDS = frozenset({"expectedRawState", "expectedVersion"})
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200
INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_HEADER = (
    "X-NPI-P807-Collection-Diagnostic"
)
INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_SCOPE = (
    "p8-07-integration-operations-collection-v1"
)
INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_HEADER = (
    "X-NPI-P807-Action-Diagnostic"
)
INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_SCOPE = (
    "p8-07-integration-operations-uncertain-replay-v1"
)
INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES = (
    "P807_ACTION_ENTRY_OPERATION_KIND",
    "P807_ACTION_ENTRY_ACTION_KIND",
    "P807_ACTION_ENTRY_REQUEST_FIELDS",
    "P807_ACTION_ENTRY_METHOD",
    "P807_ACTION_ENTRY_QUERY",
    "P807_ACTION_ENTRY_ROUTE",
    "P807_ACTION_ENTRY_FORM",
    "P807_ACTION_ENTRY_COMMAND",
    "P807_ACTION_ENTRY_EXPECTED_RAW_STATE",
    "P807_ACTION_ENTRY_EXPECTED_VERSION",
    "P807_ACTION_ENTRY_RUNTIME_SHAPE",
)
_COLLECTION_DIAGNOSTIC_ACTIVE: ContextVar[bool] = ContextVar(
    "p807_integration_operations_collection_api_diagnostic",
    default=False,
)
_ACTION_DIAGNOSTIC_ACTIVE: ContextVar[bool] = ContextVar(
    "p807_integration_operations_action_api_diagnostic",
    default=False,
)
_FORBIDDEN_RESPONSE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "payload",
        "rawbody",
        "rawpayload",
        "requestbody",
        "responsebody",
        "secret",
        "targetrequest",
        "targetresponse",
        "token",
    }
)


class _Repository(Protocol):
    def authorize_scope(
        self,
        project_id: UUID,
        *,
        administer: bool = False,
    ) -> bool: ...

    def list_operations(self, project_id: UUID, **values: Any) -> dict[str, Any] | None: ...

    def operation_detail(self, project_id: UUID, **values: Any) -> dict[str, Any] | None: ...

    def request_action(self, project_id: UUID, **values: Any) -> Any | None: ...


@contextmanager
def integration_operations_collection_diagnostics(
    trace_id: str | None,
    *,
    active: bool,
) -> Iterator[None]:
    """Bind one exact, response-neutral collection diagnostic request."""

    token = _COLLECTION_DIAGNOSTIC_ACTIVE.set(active)
    try:
        if active:
            from .frappe_repository import (
                integration_operations_collection_diagnostics as server_scope,
            )

            with server_scope(trace_id, active=True):
                yield
        else:
            yield
    finally:
        _COLLECTION_DIAGNOSTIC_ACTIVE.reset(token)


@contextmanager
def integration_operations_collection_step(code: str) -> Iterator[None]:
    if _COLLECTION_DIAGNOSTIC_ACTIVE.get():
        from .frappe_repository import (
            integration_operations_collection_step as server_step,
        )

        with server_step(code):
            yield
        return
    yield


@contextmanager
def integration_operations_action_diagnostics(
    trace_id: str | None,
    *,
    active: bool,
) -> Iterator[None]:
    """Bind one exact, response-neutral action diagnostic request."""

    token = _ACTION_DIAGNOSTIC_ACTIVE.set(active)
    try:
        if active:
            from .frappe_repository import (
                integration_operations_action_diagnostics as server_scope,
            )

            with server_scope(trace_id, active=True):
                yield
        else:
            yield
    finally:
        _ACTION_DIAGNOSTIC_ACTIVE.reset(token)


@contextmanager
def integration_operations_action_step(code: str) -> Iterator[None]:
    if _ACTION_DIAGNOSTIC_ACTIVE.get():
        from .frappe_repository import (
            integration_operations_action_step as server_step,
        )

        with server_step(code):
            yield
        return
    yield


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from .frappe_repository import FrappeIntegrationOperationsRepository

    return FrappeIntegrationOperationsRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def integration_operations_routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p8_07_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_integration_operations(
    operationKind: Any = None,
    sharedState: Any = None,
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    trace_id = frappe.get_request_header("X-Trace-ID")
    with integration_operations_collection_diagnostics(
        trace_id,
        active=_integration_operations_collection_diagnostic_active(trace_id),
    ):
        with integration_operations_collection_step(
            "P807_COLLECTION_API_DOMAIN_CALL"
        ):
            return _list(
                operation_kind=operationKind,
                shared_state=sharedState,
                cursor=cursor,
                limit=limit,
                logical_dlq=False,
                request_fields=request_fields,
            )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_integration_operation_dlq(
    operationKind: Any = None,
    sharedState: Any = None,
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _list(
        operation_kind=operationKind,
        shared_state=sharedState,
        cursor=cursor,
        limit=limit,
        logical_dlq=True,
        request_fields=request_fields,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_integration_operation(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, _actor = _context(
            request_fields,
            allowed_fields=frozenset(),
            administer=False,
        )
        response = repository.operation_detail(
            project_id,
            operation_kind=_route_operation_kind(),
            operation_id=_route_uuid("integration_operation_id"),
        )
        if response is None:
            raise IntegrationOperationsUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response, project_id=project_id)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _fixed_action(
    operation_kind: IntegrationOperationKind,
    action_kind: IntegrationActionKind,
    *,
    expectedRawState: Any,
    expectedVersion: Any,
    request_fields: dict[str, Any],
) -> dict[str, Any] | None:
    trace_id = frappe.get_request_header("X-Trace-ID")
    active = _integration_operations_action_diagnostic_active(
        trace_id,
        operation_kind=operation_kind,
        action_kind=action_kind,
        expected_raw_state=expectedRawState,
        expected_version=expectedVersion,
        request_fields=request_fields,
    )
    with integration_operations_action_diagnostics(trace_id, active=active):
        with integration_operations_action_step("P807_ACTION_API_DOMAIN_CALL"):
            return _fixed_action_in_scope(
                operation_kind,
                action_kind,
                expectedRawState=expectedRawState,
                expectedVersion=expectedVersion,
                request_fields=request_fields,
            )


def _fixed_action_in_scope(
    operation_kind: IntegrationOperationKind,
    action_kind: IntegrationActionKind,
    *,
    expectedRawState: Any,
    expectedVersion: Any,
    request_fields: dict[str, Any],
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }
    replayed = False

    def handle() -> dict[str, Any]:
        nonlocal replayed
        with integration_operations_action_step("P807_ACTION_API_CSRF"):
            require_csrf_token()
        with integration_operations_action_step("P807_ACTION_API_FIELDS"):
            command_fields = {
                **request_fields,
                "expectedRawState": expectedRawState,
                "expectedVersion": expectedVersion,
            }
            reject_unexpected_request_fields(_ACTION_FIELDS, command_fields)
            require_request_fields(_ACTION_FIELDS, command_fields)
        with integration_operations_action_step("P807_ACTION_API_CONTEXT"):
            request_id, repository, project_id, actor = _context(
                request_fields,
                allowed_fields=_ACTION_FIELDS,
                administer=True,
            )
        with integration_operations_action_step("P807_ACTION_API_REPOSITORY"):
            outcome = repository.request_action(
                project_id,
                operation_kind=operation_kind,
                operation_id=_route_uuid("integration_operation_id"),
                action_kind=action_kind,
                expected_raw_state=_raw_state(expectedRawState),
                expected_version=_positive(expectedVersion, "expectedVersion"),
                action_idempotency_key_hash=actor_idempotency_key_hash(
                    actor,
                    frappe.get_request_header("Idempotency-Key"),
                ),
            )
        with integration_operations_action_step("P807_ACTION_API_OUTCOME"):
            if outcome is None or type(outcome.replayed) is not bool:
                raise IntegrationOperationsUnavailable()
            if not isinstance(outcome.response, dict):
                raise RuntimeError("The integration operation action result is invalid.")
        with integration_operations_action_step("P807_ACTION_API_RESPONSE"):
            safe_response = _response(
                outcome.response,
                project_id=project_id,
                action=True,
            )
        with integration_operations_action_step("P807_ACTION_API_COMMIT"):
            try:
                frappe.db.commit()
            except Exception:
                try:
                    frappe.db.rollback()
                except Exception:
                    pass
                raise
        with integration_operations_action_step("P807_ACTION_API_HEADERS"):
            replayed = outcome.replayed
            headers["X-Request-ID"] = request_id
            headers["Idempotency-Replayed"] = str(replayed).lower()
            return safe_response

    result = frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )
    if replayed and frappe.local.response.http_status_code == 201:
        frappe.local.response.http_status_code = 200
    return result


def _list(
    *,
    operation_kind: Any,
    shared_state: Any,
    cursor: Any,
    limit: Any,
    logical_dlq: bool,
    request_fields: dict[str, Any],
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        with integration_operations_collection_step("P807_COLLECTION_API_FIELDS"):
            supplied = {
                **request_fields,
                "operationKind": operation_kind,
                "sharedState": shared_state,
                "cursor": cursor,
                "limit": limit,
            }
            reject_unexpected_request_fields(_LIST_FIELDS, supplied)
        with integration_operations_collection_step("P807_COLLECTION_API_CONTEXT"):
            request_id, repository, project_id, _actor = _context(
                request_fields,
                allowed_fields=_LIST_FIELDS,
                administer=False,
            )
        with integration_operations_collection_step("P807_COLLECTION_API_ARGUMENTS"):
            values = {
                "operation_kind": _optional_operation_kind(operation_kind),
                "shared_state": _optional_shared_state(shared_state),
                "cursor": _optional_cursor(cursor),
                "limit": _limit(limit),
                "logical_dlq": logical_dlq,
            }
        with integration_operations_collection_step("P807_COLLECTION_API_REPOSITORY"):
            response = repository.list_operations(project_id, **values)
        with integration_operations_collection_step("P807_COLLECTION_API_OUTCOME"):
            if response is None:
                raise IntegrationOperationsUnavailable()
        with integration_operations_collection_step("P807_COLLECTION_API_RESPONSE"):
            headers["X-Request-ID"] = request_id
            return _response(response, project_id=project_id)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _integration_operations_collection_diagnostic_active(trace_id: object) -> bool:
    try:
        request = getattr(getattr(frappe, "local", None), "request", None)
        arguments = getattr(request, "args", None)
        route = getattr(frappe.flags, "npi_route_params", None)
        form = getattr(getattr(frappe, "local", None), "form_dict", None)
        return (
            frappe.get_request_header(
                INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_HEADER
            )
            == INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_SCOPE
            and frappe.get_request_header("X-Trace-ID") == trace_id
            and isinstance(trace_id, str)
            and re.fullmatch(r"trace-[a-f0-9]{32}", trace_id) is not None
            and getattr(request, "method", None) == "GET"
            and arguments is not None
            and list(arguments.keys()) == []
            and isinstance(route, dict)
            and set(route) == {"project_id"}
            and isinstance(form, dict)
            and set(form) == {"cmd"}
            and form.get("cmd")
            == "npi_integration.integration_operations.api.get_integration_operations"
        )
    except Exception:
        return False


def _integration_operations_action_diagnostic_active(
    trace_id: object,
    *,
    operation_kind: IntegrationOperationKind,
    action_kind: IntegrationActionKind,
    expected_raw_state: Any,
    expected_version: Any,
    request_fields: dict[str, Any],
) -> bool:
    authorized_trace: str | None = None
    try:
        request = getattr(getattr(frappe, "local", None), "request", None)
        arguments = getattr(request, "args", None)
        route = getattr(frappe.flags, "npi_route_params", None)
        form = getattr(getattr(frappe, "local", None), "form_dict", None)
        if not (
            frappe.get_request_header(
                INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_HEADER
            )
            == INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_SCOPE
            and frappe.get_request_header("X-Trace-ID") == trace_id
            and isinstance(trace_id, str)
            and re.fullmatch(r"trace-[a-f0-9]{32}", trace_id) is not None
        ):
            return False
        authorized_trace = trace_id
        predicates = (
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[0],
                lambda: operation_kind is IntegrationOperationKind.PUBLISH_ITEM,
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[1],
                lambda: action_kind is IntegrationActionKind.REPLAY,
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[2],
                lambda: isinstance(request_fields, dict)
                and list(request_fields.keys()) == [],
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[3],
                lambda: getattr(request, "method", None) == "POST",
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[4],
                lambda: arguments is not None and list(arguments.keys()) == [],
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[5],
                lambda: isinstance(route, dict)
                and set(route) == {"project_id", "integration_operation_id"},
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[6],
                lambda: isinstance(form, dict)
                and set(form) == {"cmd", "expectedRawState", "expectedVersion"},
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[7],
                lambda: isinstance(form, dict)
                and form.get("cmd")
                == "npi_integration.integration_operations.api.replay_publish_item",
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[8],
                lambda: isinstance(form, dict)
                and form.get("expectedRawState") == expected_raw_state,
            ),
            (
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[9],
                lambda: isinstance(form, dict)
                and form.get("expectedVersion") == expected_version,
            ),
        )
        for code, predicate in predicates:
            if not predicate():
                _record_action_entry_diagnostic(code, authorized_trace)
                return False
        return True
    except Exception:
        if authorized_trace is not None:
            _record_action_entry_diagnostic(
                INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES[10],
                authorized_trace,
            )
        return False


def _record_action_entry_diagnostic(code: str, trace_id: str) -> None:
    try:
        if (
            code not in INTEGRATION_OPERATIONS_ACTION_ENTRY_DIAGNOSTIC_CODES
            or re.fullmatch(r"trace-[a-f0-9]{32}", trace_id) is None
        ):
            return
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI integration operation action entry predicate failed",
            exception_type="RuntimeError",
            trace_id=trace_id,
        )
    except Exception:
        # Diagnostics must never alter the request, response or transaction.
        pass


def _context(
    request_fields: dict[str, Any],
    *,
    allowed_fields: frozenset[str],
    administer: bool,
) -> tuple[str, _Repository, UUID, str]:
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    if principal.is_external:
        raise PermissionDenied()
    request_id = _request_id()
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The integration operation request has no trace identity.")
    repository = _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    project_id = _route_uuid("project_id")
    if not repository.authorize_scope(project_id, administer=administer):
        raise IntegrationOperationsUnavailable()
    reject_unexpected_request_fields(allowed_fields, request_fields)
    if integration_operations_routes_are_disabled():
        raise IntegrationOperationsRoutesDisabled()
    return request_id, repository, project_id, actor


def _request_id() -> str:
    value = response_request_id()
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError) as error:
        raise _field("X-Request-ID", _("Enter a valid request identifier.")) from error
    if str(parsed) != str(value).casefold():
        raise _field("X-Request-ID", _("Enter a valid request identifier."))
    return str(parsed)


def _route_uuid(name: str) -> UUID:
    raw = getattr(frappe.flags, "npi_route_params", {}).get(name)
    try:
        parsed = UUID(str(raw))
    except (TypeError, ValueError) as error:
        raise IntegrationOperationsUnavailable() from error
    if str(parsed) != str(raw).casefold():
        raise IntegrationOperationsUnavailable()
    return parsed


def _route_operation_kind() -> IntegrationOperationKind:
    raw = getattr(frappe.flags, "npi_route_params", {}).get("operation_kind")
    try:
        return IntegrationOperationKind(str(raw))
    except (TypeError, ValueError) as error:
        raise IntegrationOperationsUnavailable() from error


def _optional_operation_kind(value: Any) -> IntegrationOperationKind | None:
    if value in (None, ""):
        return None
    try:
        return IntegrationOperationKind(str(value))
    except (TypeError, ValueError) as error:
        raise _field("operationKind", _("Select a supported value.")) from error


def _optional_shared_state(value: Any) -> IntegrationViewState | None:
    if value in (None, ""):
        return None
    try:
        return IntegrationViewState(str(value))
    except (TypeError, ValueError) as error:
        raise _field("sharedState", _("Select a supported value.")) from error


def _optional_cursor(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or value != value.strip() or len(value) > 512:
        raise _field("cursor", _("Enter a valid cursor."))
    return value


def _limit(value: Any) -> int:
    if value in (None, ""):
        return _DEFAULT_LIMIT
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    if type(value) is not int or not 1 <= value <= _MAX_LIMIT:
        raise _field("limit", _("Enter a whole number from 1 to 200."))
    return value


def _raw_state(value: Any) -> str:
    if not isinstance(value, str) or _RAW_STATE.fullmatch(value) is None:
        raise _field("expectedRawState", _("Select a supported operation state."))
    return value


def _positive(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(field, _("Enter a positive whole number."))
    return value


def _field(field: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed({field: message})


def _response(
    value: object,
    *,
    project_id: UUID,
    action: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The integration operation response is invalid.")
    if not action and str(value.get("projectGlobalId")) != str(project_id):
        raise RuntimeError("The integration operation response Project is invalid.")
    _reject_unsafe_response(value)
    return value


def _reject_unsafe_response(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized in _FORBIDDEN_RESPONSE_KEYS:
                raise RuntimeError("The integration operation response is unsafe.")
            _reject_unsafe_response(child)
    elif isinstance(value, list):
        for child in value:
            _reject_unsafe_response(child)


def _bind_action(
    operation_kind: IntegrationOperationKind,
    action_kind: IntegrationActionKind,
):
    def invoke(
        expectedRawState: Any = None,
        expectedVersion: Any = None,
        **request_fields: Any,
    ) -> dict[str, Any] | None:
        return _fixed_action(
            operation_kind,
            action_kind,
            expectedRawState=expectedRawState,
            expectedVersion=expectedVersion,
            request_fields=request_fields,
        )

    return frappe.whitelist(allow_guest=True, methods=["POST"])(invoke)


replay_receive_project_submission = _bind_action(
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION,
    IntegrationActionKind.REPLAY,
)
request_reconciliation_receive_project_submission = _bind_action(
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION,
    IntegrationActionKind.REQUEST_RECONCILIATION,
)
replay_publish_item = _bind_action(
    IntegrationOperationKind.PUBLISH_ITEM,
    IntegrationActionKind.REPLAY,
)
request_reconciliation_publish_item = _bind_action(
    IntegrationOperationKind.PUBLISH_ITEM,
    IntegrationActionKind.REQUEST_RECONCILIATION,
)
replay_publish_mbom = _bind_action(
    IntegrationOperationKind.PUBLISH_MBOM,
    IntegrationActionKind.REPLAY,
)
request_reconciliation_publish_mbom = _bind_action(
    IntegrationOperationKind.PUBLISH_MBOM,
    IntegrationActionKind.REQUEST_RECONCILIATION,
)
replay_create_tool_asset = _bind_action(
    IntegrationOperationKind.CREATE_TOOL_ASSET,
    IntegrationActionKind.REPLAY,
)
request_reconciliation_create_tool_asset = _bind_action(
    IntegrationOperationKind.CREATE_TOOL_ASSET,
    IntegrationActionKind.REQUEST_RECONCILIATION,
)
replay_update_tool_asset = _bind_action(
    IntegrationOperationKind.UPDATE_TOOL_ASSET,
    IntegrationActionKind.REPLAY,
)
request_reconciliation_update_tool_asset = _bind_action(
    IntegrationOperationKind.UPDATE_TOOL_ASSET,
    IntegrationActionKind.REQUEST_RECONCILIATION,
)
