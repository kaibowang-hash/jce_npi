from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

import frappe


BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P503_BASELINE_WORKSPACE_DOCUMENT_ROUTE_ENABLEMENT",
        "P503_BASELINE_WORKSPACE_BASELINE_ROUTE_ENABLEMENT",
        "P503_BASELINE_WORKSPACE_AUTHENTICATION",
        "P503_BASELINE_WORKSPACE_PRINCIPAL",
        "P503_BASELINE_WORKSPACE_REPOSITORY_FACTORY",
        "P503_BASELINE_WORKSPACE_ROUTE_SCOPE",
        "P503_BASELINE_WORKSPACE_REQUEST_FIELDS",
        "P503_BASELINE_WORKSPACE_REQUEST_ID",
        "P503_BASELINE_WORKSPACE_PROJECT_LOOKUP",
        "P503_BASELINE_WORKSPACE_PROJECT_IDENTITY",
        "P503_BASELINE_WORKSPACE_PROJECT_INTERNAL_PRINCIPAL",
        "P503_BASELINE_WORKSPACE_PROJECT_TENANT",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_QUERY",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_LOAD",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_ABSENT",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_EFFECTIVITY",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBER_USER",
        "P503_BASELINE_WORKSPACE_PROJECT_MEMBERSHIP_CARDINALITY",
        "P503_BASELINE_WORKSPACE_POLICY_QUERY",
        "P503_BASELINE_WORKSPACE_POLICY_ROW",
        "P503_BASELINE_WORKSPACE_POLICY_LOAD",
        "P503_BASELINE_WORKSPACE_BASELINE_QUERY",
        "P503_BASELINE_WORKSPACE_BASELINE_LOAD",
        "P503_BASELINE_WORKSPACE_IMPACT_QUERY",
        "P503_BASELINE_WORKSPACE_IMPACT_LOAD",
        "P503_BASELINE_WORKSPACE_REPOSITORY_RESPONSE",
        "P503_BASELINE_WORKSPACE_API_RESPONSE",
    }
)

BASELINE_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P503_BASELINE_CREATE_COMMAND_CONTEXT",
        "P503_BASELINE_CREATE_INPUT_PARSE",
        "P503_BASELINE_CREATE_PROJECT_LOCK",
        "P503_BASELINE_CREATE_MEMBERSHIP_AUTHORITY",
        "P503_BASELINE_CREATE_POLICY_LOAD",
        "P503_BASELINE_CREATE_IDEMPOTENCY_REPLAY",
        "P503_BASELINE_CREATE_MEMBER_RESOLVE",
        "P503_BASELINE_CREATE_DOMAIN_BUILD",
        "P503_BASELINE_CREATE_RECEIPT_INSERT",
        "P503_BASELINE_CREATE_BASELINE_INSERT",
        "P503_BASELINE_CREATE_MEMBER_INSERT",
        "P503_BASELINE_CREATE_AUDIT_APPEND",
        "P503_BASELINE_CREATE_RESPONSE_BUILD",
        "P503_BASELINE_CREATE_RECEIPT_SEAL",
    }
)

BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_SCOPE = (
    "p503-baseline-workspace-http-v1"
)
_DIAGNOSTIC_FLAG = "npi_p503_baseline_workspace_server_diagnostic"
BASELINE_CREATE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
BASELINE_CREATE_SERVER_DIAGNOSTIC_SCOPE = "p503-baseline-create-v1"
_BASELINE_CREATE_DIAGNOSTIC_FLAG = "npi_p503_baseline_create_diagnostic"
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")


@contextmanager
def baseline_workspace_server_diagnostics(trace_id: str | None) -> Iterator[None]:
    """Enable one closed, response-neutral P5-03 workspace diagnostic scope."""

    try:
        enabled = (
            frappe.get_request_header(
                BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_HEADER
            )
            == BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_SCOPE
        )
        state = None
        if (
            enabled
            and isinstance(trace_id, str)
            and _TRACE_PATTERN.fullmatch(trace_id)
        ):
            state = {"trace_id": trace_id, "recorded": False}
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
def baseline_workspace_server_step(code: str) -> Iterator[None]:
    """Record one allowlisted failing substage and re-raise the same exception."""

    try:
        yield
    except Exception as error:
        record_baseline_workspace_server_failure(code, error)
        raise


@contextmanager
def baseline_create_server_diagnostics(trace_id: str | None) -> Iterator[None]:
    """Enable one closed, response-neutral P5-03 create diagnostic scope."""

    try:
        enabled = (
            frappe.get_request_header(BASELINE_CREATE_SERVER_DIAGNOSTIC_HEADER)
            == BASELINE_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )
        state = None
        if (
            enabled
            and isinstance(trace_id, str)
            and _TRACE_PATTERN.fullmatch(trace_id)
        ):
            state = {"trace_id": trace_id, "recorded": False}
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _BASELINE_CREATE_DIAGNOSTIC_FLAG, missing)
        setattr(flags, _BASELINE_CREATE_DIAGNOSTIC_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _BASELINE_CREATE_DIAGNOSTIC_FLAG)
            else:
                setattr(flags, _BASELINE_CREATE_DIAGNOSTIC_FLAG, previous)
        except Exception:
            pass


@contextmanager
def baseline_create_server_step(code: str) -> Iterator[None]:
    """Record one allowlisted create substage and re-raise the same exception."""

    try:
        yield
    except Exception as error:
        record_baseline_create_server_failure(code, error)
        raise


def record_baseline_create_server_failure(
    code: str,
    error: Exception,
) -> None:
    """Record only create stage code, validated type, and exact trace ID."""

    try:
        state = _baseline_create_diagnostic_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in BASELINE_CREATE_SERVER_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Document baseline create substage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostics are secondary and must never change the original response.
        pass


def record_baseline_workspace_server_failure(
    code: str,
    error: Exception,
) -> None:
    """Record no exception text, response, request, cookie, or credential data."""

    try:
        _record_baseline_workspace_server_diagnostic(code, type(error).__name__)
    except Exception:
        pass


def record_baseline_workspace_server_predicate(
    code: str,
    *,
    exception_type: str,
) -> None:
    """Record a closed failed predicate without changing its return behavior."""

    try:
        _record_baseline_workspace_server_diagnostic(code, exception_type)
    except Exception:
        pass


def _record_baseline_workspace_server_diagnostic(
    code: str,
    exception_type: str,
) -> None:
    state = _diagnostic_state()
    if (
        state is None
        or state["recorded"] is True
        or code not in BASELINE_WORKSPACE_SERVER_DIAGNOSTIC_CODES
        or _TYPE_PATTERN.fullmatch(exception_type) is None
    ):
        return
    state["recorded"] = True
    try:
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Document baseline workspace server substage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostics are secondary and must never change the original response.
        pass


def _diagnostic_state() -> dict[str, object] | None:
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


def _baseline_create_diagnostic_state() -> dict[str, object] | None:
    state = getattr(frappe.flags, _BASELINE_CREATE_DIAGNOSTIC_FLAG, None)
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
        or type(state.get("recorded")) is not bool
    ):
        return None
    return state
