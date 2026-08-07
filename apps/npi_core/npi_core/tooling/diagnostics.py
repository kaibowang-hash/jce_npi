from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

import frappe


PART_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P601_PART_CREATE_COMMAND_CONTEXT",
        "P601_PART_CREATE_INPUT_PARSE",
        "P601_PART_CREATE_PROJECT_LOCK",
        "P601_PART_CREATE_IDEMPOTENCY_CONTEXT",
        "P601_PART_CREATE_DOMAIN_BUILD",
        "P601_PART_CREATE_RECEIPT_INSERT",
        "P601_PART_CREATE_ROOT_INSERT",
        "P601_PART_CREATE_REVISION_INSERT",
        "P601_PART_CREATE_ROOT_POINTER_SAVE",
        "P601_PART_CREATE_AUDIT_APPEND",
        "P601_PART_CREATE_RESPONSE_BUILD",
        "P601_PART_CREATE_RECEIPT_SEAL",
        "P601_PART_CREATE_API_RESPONSE",
    }
)
APPLICABILITY_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P601_APPLICABILITY_CREATE_COMMAND_CONTEXT",
        "P601_APPLICABILITY_CREATE_INPUT_PARSE",
        "P601_APPLICABILITY_CREATE_PROJECT_LOCK",
        "P601_APPLICABILITY_CREATE_IDEMPOTENCY_CONTEXT",
        "P601_APPLICABILITY_CREATE_REFERENCE_LOAD",
        "P601_APPLICABILITY_CREATE_REFERENCE_VALIDATE",
        "P601_APPLICABILITY_CREATE_RETAINED_LOAD",
        "P601_APPLICABILITY_CREATE_PREDECESSOR_RESOLVE",
        "P601_APPLICABILITY_CREATE_DOMAIN_BUILD",
        "P601_APPLICABILITY_CREATE_DOMAIN_VALIDATE",
        "P601_APPLICABILITY_CREATE_RECEIPT_INSERT",
        "P601_APPLICABILITY_CREATE_RELATIONSHIP_INSERT",
        "P601_APPLICABILITY_CREATE_AUDIT_APPEND",
        "P601_APPLICABILITY_CREATE_RESPONSE_BUILD",
        "P601_APPLICABILITY_CREATE_RECEIPT_SEAL",
        "P601_APPLICABILITY_CREATE_API_RESPONSE",
    }
)
PART_CREATE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
PART_CREATE_SERVER_DIAGNOSTIC_SCOPE = "p601-part-create-v1"
APPLICABILITY_CREATE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
APPLICABILITY_CREATE_SERVER_DIAGNOSTIC_SCOPE = "p601-applicability-create-v1"
_DIAGNOSTIC_FLAG = "npi_p601_part_create_diagnostic"
_APPLICABILITY_DIAGNOSTIC_FLAG = "npi_p601_applicability_create_diagnostic"
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")


@contextmanager
def part_create_server_diagnostics(trace_id: str | None) -> Iterator[None]:
    """Enable one closed, response-neutral P6-01 Part-create diagnostic."""

    try:
        enabled = (
            frappe.get_request_header(PART_CREATE_SERVER_DIAGNOSTIC_HEADER)
            == PART_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )
        state = None
        if enabled and isinstance(trace_id, str) and _TRACE_PATTERN.fullmatch(trace_id):
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
def part_create_server_step(code: str) -> Iterator[None]:
    """Record one allowlisted failing substage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        _record_part_create_server_failure(code, error)
        raise


@contextmanager
def applicability_create_server_diagnostics(
    trace_id: str | None,
    *,
    route_enabled: bool,
) -> Iterator[None]:
    """Enable one closed, response-neutral P6-01 Applicability diagnostic."""

    try:
        enabled = route_enabled and (
            frappe.get_request_header(APPLICABILITY_CREATE_SERVER_DIAGNOSTIC_HEADER)
            == APPLICABILITY_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )
        state = None
        if enabled and isinstance(trace_id, str) and _TRACE_PATTERN.fullmatch(trace_id):
            state = {"trace_id": trace_id, "recorded": False}
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _APPLICABILITY_DIAGNOSTIC_FLAG, missing)
        setattr(flags, _APPLICABILITY_DIAGNOSTIC_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _APPLICABILITY_DIAGNOSTIC_FLAG)
            else:
                setattr(flags, _APPLICABILITY_DIAGNOSTIC_FLAG, previous)
        except Exception:
            pass


@contextmanager
def applicability_create_server_step(code: str) -> Iterator[None]:
    """Record one allowlisted failing Applicability substage unchanged."""

    try:
        yield
    except Exception as error:
        _record_applicability_create_server_failure(code, error)
        raise


def _record_part_create_server_failure(code: str, error: Exception) -> None:
    """Record only the stage, validated exception type and exact trace."""

    try:
        state = _diagnostic_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in PART_CREATE_SERVER_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Part create substage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostic recording cannot change the response or transaction.
        pass


def _record_applicability_create_server_failure(
    code: str,
    error: Exception,
) -> None:
    """Record only the Applicability stage, exception type and exact trace."""

    try:
        state = _applicability_diagnostic_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in APPLICABILITY_CREATE_SERVER_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Tooling Applicability create substage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostic recording cannot change the response or transaction.
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


def _applicability_diagnostic_state() -> dict[str, object] | None:
    state = getattr(frappe.flags, _APPLICABILITY_DIAGNOSTIC_FLAG, None)
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
        or type(state.get("recorded")) is not bool
    ):
        return None
    return state
