from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

import frappe


P606_ASSET_CREATE_DIAGNOSTIC_CODES = frozenset(
    {
        "P805_P606_ASSET_COMMAND_CONTEXT",
        "P805_P606_ASSET_INPUT_PARSE",
        "P805_P606_ASSET_REPOSITORY_INIT",
        "P805_P606_ASSET_PROJECT_LOCK",
        "P805_P606_ASSET_MASTER_RESOLVE",
        "P805_P606_ASSET_SET_RESOLVE",
        "P805_P606_ASSET_BINDING_RESOLVE",
        "P805_P606_ASSET_REVISION_RESOLVE",
        "P805_P606_ASSET_ACCEPTANCE_RESOLVE",
        "P805_P606_ASSET_INPUT_BUILD",
        "P805_P606_ASSET_PAYLOAD_BUILD",
        "P805_P606_ASSET_RECEIPT_REPLAY",
        "P805_P606_ASSET_DOMAIN_BUILD",
        "P805_P606_ASSET_RESPONSE_BUILD",
        "P805_P606_ASSET_TRANSACTION_SCOPE",
        "P805_P606_ASSET_RECEIPT_INSERT",
        "P805_P606_ASSET_REQUEST_INSERT",
        "P805_P606_ASSET_AUDIT_APPEND",
        "P805_P606_ASSET_RECEIPT_SEAL",
        "P805_P606_ASSET_OUTCOME_VALIDATE",
    }
)
P606_ASSET_CREATE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
P606_ASSET_CREATE_DIAGNOSTIC_SCOPE = "p805-p606-asset-create-v1"
_DIAGNOSTIC_FLAG = "npi_p805_p606_asset_create_diagnostic"
TOOL_ASSET_CONTEXT_DIAGNOSTIC_CODES = frozenset(
    {
        "P805_TOOL_ASSET_CONTEXT_ROUTES_ENABLED",
        "P805_TOOL_ASSET_CONTEXT_AUTHENTICATED_USER",
        "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_PRINCIPAL_INTERNAL",
        "P805_TOOL_ASSET_CONTEXT_REQUEST_ID",
        "P805_TOOL_ASSET_CONTEXT_REPOSITORY_INIT",
        "P805_TOOL_ASSET_CONTEXT_PROJECT_ROUTE",
        "P805_TOOL_ASSET_CONTEXT_PROJECT_AUTHORIZE",
        "P805_TOOL_ASSET_CONTEXT_REQUEST_FIELDS",
        "P805_TOOL_ASSET_CONTEXT_MASTER_ROUTE",
        "P805_TOOL_ASSET_CONTEXT_SET_ROUTE",
        "P805_TOOL_ASSET_CONTEXT_QUERY_PARSE",
        "P805_TOOL_ASSET_CONTEXT_REPOSITORY_LIST",
        "P805_TOOL_ASSET_CONTEXT_PROJECT_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_MASTER_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_SET_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_PROFILE_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_CREATE_SOURCE",
        "P805_TOOL_ASSET_CONTEXT_CREATE_PROFILE_BINDING",
        "P805_TOOL_ASSET_CONTEXT_CREATE_AUTHORITY",
        "P805_TOOL_ASSET_CONTEXT_CREATE_SANDBOX_GUARD",
        "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
        "P805_TOOL_ASSET_CONTEXT_CREATE_REQUEST_BUILD",
        "P805_TOOL_ASSET_CONTEXT_CREATE_PROJECT",
        "P805_TOOL_ASSET_CONTEXT_REQUEST_ROWS",
        "P805_TOOL_ASSET_CONTEXT_PERMISSIONS",
        "P805_TOOL_ASSET_CONTEXT_PROFILE_RESPONSE",
        "P805_TOOL_ASSET_CONTEXT_ITEM_PROJECT",
        "P805_TOOL_ASSET_CONTEXT_RESPONSE_BUILD",
        "P805_TOOL_ASSET_CONTEXT_RESPONSE_AVAILABLE",
        "P805_TOOL_ASSET_CONTEXT_RESPONSE_SERIALIZE",
    }
)
TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE = "p805-tool-asset-command-context-v1"
_TOOL_ASSET_CONTEXT_FLAG = "npi_p805_tool_asset_context_diagnostic"
TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES = frozenset(
    {
        "P805_TOOL_ASSET_CREATE_ROUTES_ENABLED",
        "P805_TOOL_ASSET_CREATE_AUTHENTICATED_USER",
        "P805_TOOL_ASSET_CREATE_CSRF",
        "P805_TOOL_ASSET_CREATE_PRINCIPAL_RESOLVE",
        "P805_TOOL_ASSET_CREATE_PRINCIPAL_INTERNAL",
        "P805_TOOL_ASSET_CREATE_REQUEST_ID",
        "P805_TOOL_ASSET_CREATE_REPOSITORY_INIT",
        "P805_TOOL_ASSET_CREATE_PROJECT_ROUTE",
        "P805_TOOL_ASSET_CREATE_PROJECT_AUTHORIZE",
        "P805_TOOL_ASSET_CREATE_REQUEST_FIELDS",
        "P805_TOOL_ASSET_CREATE_INPUT_PARSE",
        "P805_TOOL_ASSET_CREATE_OPERATION_SELECT",
        "P805_TOOL_ASSET_CREATE_REPOSITORY_COMMAND",
        "P805_TOOL_ASSET_CREATE_OUTCOME_VALIDATE",
        "P805_TOOL_ASSET_CREATE_COMMIT",
        "P805_TOOL_ASSET_CREATE_PROBLEM_RAISE",
        "P805_TOOL_ASSET_CREATE_RESPONSE_SERIALIZE",
        "P805_TOOL_ASSET_CREATE_OUTBOX_VALIDATE",
        "P805_TOOL_ASSET_CREATE_DOMAIN_CALL",
        "P805_TOOL_ASSET_CREATE_PROJECT_LOCK",
        "P805_TOOL_ASSET_CREATE_RECEIPT_LOOKUP",
        "P805_TOOL_ASSET_CREATE_RECEIPT_REPLAY",
        "P805_TOOL_ASSET_CREATE_PROJECT_MUTABLE",
        "P805_TOOL_ASSET_CREATE_PROFILE_RESOLVE",
        "P805_TOOL_ASSET_CREATE_REQUEST_BUILD",
        "P805_TOOL_ASSET_CREATE_HASH_COMPARE",
        "P805_TOOL_ASSET_CREATE_TRANSACTION_SCOPE",
        "P805_TOOL_ASSET_CREATE_STREAM_GUARD",
        "P805_TOOL_ASSET_CREATE_REQUEST_INSERT",
        "P805_TOOL_ASSET_CREATE_OUTBOX_INSERT",
        "P805_TOOL_ASSET_CREATE_GUARD_ACTIVATE",
        "P805_TOOL_ASSET_CREATE_AUDIT_APPEND",
        "P805_TOOL_ASSET_CREATE_RECEIPT_INSERT",
        "P805_TOOL_ASSET_CREATE_OUTCOME_BUILD",
        "P805_TOOL_ASSET_CREATE_SOURCE",
        "P805_TOOL_ASSET_CREATE_PROFILE_BINDING",
        "P805_TOOL_ASSET_CREATE_AUTHORITY",
        "P805_TOOL_ASSET_CREATE_SANDBOX_GUARD",
        "P805_TOOL_ASSET_CREATE_MAPPING",
        "P805_TOOL_ASSET_CREATE_DOMAIN_BUILD",
    }
)
TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_SCOPE = (
    "p805-tool-asset-create-response-v1"
)
TOOL_ASSET_CREATE_HTTP_BOUNDARY_DIAGNOSTIC_SCOPE = (
    "p805-tool-asset-create-http-boundary-v1"
)
TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE = (
    "p805-tool-asset-create-prehandler-v1"
)
_TOOL_ASSET_CREATE_RESPONSE_FLAG = (
    "npi_p805_tool_asset_create_response_diagnostic"
)
_TOOL_ASSET_CREATE_COMMAND = (
    "npi_integration.tool_asset_request_api."
    "create_tool_asset_execution_request"
)
_TOOL_ASSET_CREATE_FIELDS = frozenset(
    {
        "acceptanceRevisionGlobalId",
        "expectedSourceHash",
        "expectedApprovalHash",
        "expectedMappingExpectationHash",
        "expectedProfileSnapshotHash",
        "acknowledgement",
    }
)
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")


@contextmanager
def p606_asset_create_diagnostics(trace_id: object) -> Iterator[None]:
    """Enable one exact-scope response-neutral predecessor diagnostic."""

    try:
        enabled = (
            frappe.get_request_header(P606_ASSET_CREATE_DIAGNOSTIC_HEADER)
            == P606_ASSET_CREATE_DIAGNOSTIC_SCOPE
        )
        state = (
            {"trace_id": trace_id, "recorded": False}
            if enabled
            and isinstance(trace_id, str)
            and _TRACE_PATTERN.fullmatch(trace_id) is not None
            else None
        )
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _DIAGNOSTIC_FLAG, missing)
        setattr(flags, _DIAGNOSTIC_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _DIAGNOSTIC_FLAG)
            else:
                setattr(flags, _DIAGNOSTIC_FLAG, previous)
        except Exception:
            pass


@contextmanager
def p606_asset_create_step(code: str) -> Iterator[None]:
    """Record the innermost allowlisted stage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        _record_failure(code, error)
        raise


@contextmanager
def tool_asset_context_diagnostics(
    trace_id: object,
    acceptance_revision_id: object,
) -> Iterator[None]:
    """Enable one exact GET/query response-neutral command-context diagnostic."""

    try:
        request = getattr(getattr(frappe, "local", None), "request", None)
        enabled = (
            frappe.get_request_header(TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER)
            == TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE
            and getattr(request, "method", None) == "GET"
            and _exact_acceptance_query(request, acceptance_revision_id)
        )
        state = (
            {"trace_id": trace_id, "recorded": False}
            if enabled
            and isinstance(trace_id, str)
            and _TRACE_PATTERN.fullmatch(trace_id) is not None
            else None
        )
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _TOOL_ASSET_CONTEXT_FLAG, missing)
        setattr(flags, _TOOL_ASSET_CONTEXT_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _TOOL_ASSET_CONTEXT_FLAG)
            else:
                setattr(flags, _TOOL_ASSET_CONTEXT_FLAG, previous)
        except Exception:
            pass


@contextmanager
def tool_asset_context_step(
    code: str,
    *,
    create_operation: bool = True,
) -> Iterator[None]:
    """Record one innermost create-context stage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        if create_operation:
            _record_context_failure(code, error)
        raise


@contextmanager
def tool_asset_create_response_diagnostics(
    _context_trace_id: object,
    operation: object,
    command_fields: object,
) -> Iterator[None]:
    """Enable one exact Frappe-bound create POST response-neutral diagnostic."""

    try:
        request = getattr(getattr(frappe, "local", None), "request", None)
        request_trace_id = frappe.get_request_header("X-Trace-ID")
        enabled = (
            frappe.get_request_header(
                TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_HEADER
            )
            == TOOL_ASSET_CREATE_PREHANDLER_DIAGNOSTIC_SCOPE
            and getattr(request, "method", None) == "POST"
            and operation == "create_tool_asset"
            and isinstance(command_fields, dict)
            and set(command_fields) == _TOOL_ASSET_CREATE_FIELDS | {"cmd"}
            and command_fields.get("cmd") == _TOOL_ASSET_CREATE_COMMAND
            and _exact_empty_query(request)
            and _exact_create_route()
            and isinstance(frappe.get_request_header("Idempotency-Key"), str)
            and bool(frappe.get_request_header("Idempotency-Key"))
        )
        state = (
            {"trace_id": request_trace_id, "recorded": False}
            if enabled
            and isinstance(request_trace_id, str)
            and _TRACE_PATTERN.fullmatch(request_trace_id) is not None
            else None
        )
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _TOOL_ASSET_CREATE_RESPONSE_FLAG, missing)
        setattr(flags, _TOOL_ASSET_CREATE_RESPONSE_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _TOOL_ASSET_CREATE_RESPONSE_FLAG)
            else:
                setattr(flags, _TOOL_ASSET_CREATE_RESPONSE_FLAG, previous)
        except Exception:
            pass


@contextmanager
def tool_asset_create_response_step(code: str) -> Iterator[None]:
    """Record one innermost allowlisted create stage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        _record_create_response_failure(code, error)
        raise


def _record_failure(code: str, error: Exception) -> None:
    try:
        state = _state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in P606_ASSET_CREATE_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        _safe_record(
            code,
            "NPI predecessor Tool Asset create stage failed",
            exception_type,
            str(state["trace_id"]),
        )
    except Exception:
        # Diagnostic observation must never replace the original response.
        pass


def _record_context_failure(code: str, error: Exception) -> None:
    try:
        state = _context_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in TOOL_ASSET_CONTEXT_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        _safe_record(
            code,
            "NPI Tool Asset command context stage failed",
            exception_type,
            str(state["trace_id"]),
        )
    except Exception:
        # Diagnostic observation must never replace the original response.
        pass


def _record_create_response_failure(code: str, error: Exception) -> None:
    try:
        state = _create_response_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in TOOL_ASSET_CREATE_RESPONSE_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        _safe_record(
            code,
            "NPI Tool Asset create response stage failed",
            exception_type,
            str(state["trace_id"]),
        )
    except Exception:
        # Diagnostic observation must never replace the original response.
        pass


def _state() -> dict[str, object] | None:
    state = getattr(frappe.flags, _DIAGNOSTIC_FLAG, None)
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
        or type(state.get("recorded")) is not bool
    ):
        return None
    return state


def _context_state() -> dict[str, object] | None:
    state = getattr(frappe.flags, _TOOL_ASSET_CONTEXT_FLAG, None)
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
        or type(state.get("recorded")) is not bool
    ):
        return None
    return state


def _create_response_state() -> dict[str, object] | None:
    state = getattr(frappe.flags, _TOOL_ASSET_CREATE_RESPONSE_FLAG, None)
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
        or type(state.get("recorded")) is not bool
    ):
        return None
    return state


def _safe_record(
    code: str,
    title: str,
    exception_type: str,
    trace_id: str,
) -> None:
    from npi_core.api import record_safe_diagnostic

    record_safe_diagnostic(
        code=code,
        title=title,
        exception_type=exception_type,
        trace_id=trace_id,
    )


def _exact_acceptance_query(request: object, acceptance_revision_id: object) -> bool:
    if not isinstance(acceptance_revision_id, str) or not acceptance_revision_id:
        return False
    arguments = getattr(request, "args", None)
    if arguments is None:
        return False
    try:
        keys = list(arguments.keys())
        values = (
            list(arguments.getlist("acceptanceRevisionGlobalId"))
            if callable(getattr(arguments, "getlist", None))
            else [arguments.get("acceptanceRevisionGlobalId")]
        )
    except Exception:
        return False
    return (
        keys == ["acceptanceRevisionGlobalId"]
        and values == [acceptance_revision_id]
    )


def _exact_empty_query(request: object) -> bool:
    arguments = getattr(request, "args", None)
    if arguments is None:
        return False
    try:
        return list(arguments.keys()) == []
    except Exception:
        return False


def _exact_create_route() -> bool:
    route = getattr(frappe.flags, "npi_route_params", None)
    try:
        return (
            isinstance(route, dict)
            and set(route)
            == {
                "project_id",
                "tooling_master_id",
                "tooling_set_id",
            }
            and all(
                isinstance(route[key], str)
                and str(UUID(route[key])) == route[key]
                for key in (
                    "project_id",
                    "tooling_master_id",
                    "tooling_set_id",
                )
            )
        )
    except Exception:
        return False
