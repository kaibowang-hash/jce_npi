from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

import frappe


MBOM_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P804_CREATE_COMMAND_CONTEXT",
        "P804_CREATE_INPUT_PARSE",
        "P804_CREATE_PROJECT_LOCK",
        "P804_CREATE_IDEMPOTENCY_CONTEXT",
        "P804_CREATE_IDEMPOTENCY_REPLAY",
        "P804_CREATE_PROBLEM_OUTCOME",
        "P804_CREATE_PROJECT_MUTABILITY",
        "P804_CREATE_PROFILE_RESOLVE",
        "P804_CREATE_PRELOCK_BUILD",
        "P804_CREATE_SERVICE_ACTOR_VALIDATE",
        "P804_CREATE_RESPONSE_BUILD",
        "P804_CREATE_TRANSACTION_SCOPE",
        "P804_CREATE_STREAM_GUARD",
        "P804_CREATE_PROFILE_REVALIDATE",
        "P804_CREATE_LOCKED_BUILD",
        "P804_CREATE_LOCK_COMPARE",
        "P804_CREATE_REQUEST_INSERT",
        "P804_CREATE_NODE_INSERT",
        "P804_CREATE_OUTBOX_INSERT",
        "P804_CREATE_GUARD_ACTIVATE",
        "P804_CREATE_AUDIT_APPEND",
        "P804_CREATE_IDEMPOTENCY_INSERT",
        "P804_CREATE_REPOSITORY_COMMAND",
        "P804_CREATE_OUTCOME_VALIDATE",
        "P804_CREATE_COMMIT",
        "P804_CREATE_OUTCOME_PROBLEM",
        "P804_CREATE_RESPONSE_VALIDATE",
        "P804_CREATE_OUTBOX_VALIDATE",
        "P804_CREATE_API_RESPONSE",
    }
)
MBOM_CREATE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
MBOM_CREATE_SERVER_DIAGNOSTIC_SCOPE = "p804-mbom-create-v1"
_DIAGNOSTIC_FLAG = "npi_p804_mbom_create_diagnostic"
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")


@contextmanager
def mbom_create_server_diagnostics(trace_id: str | None) -> Iterator[None]:
    """Enable one closed, response-neutral P8-04 create diagnostic scope."""

    try:
        enabled = (
            frappe.get_request_header(MBOM_CREATE_SERVER_DIAGNOSTIC_HEADER)
            == MBOM_CREATE_SERVER_DIAGNOSTIC_SCOPE
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
def mbom_create_server_step(code: str) -> Iterator[None]:
    """Record the innermost allowlisted failing substage and re-raise it."""

    try:
        yield
    except Exception as error:
        _record_mbom_create_server_failure(code, error)
        raise


def _record_mbom_create_server_failure(code: str, error: Exception) -> None:
    """Record only stage code, validated type, and the exact request trace."""

    try:
        state = _diagnostic_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in MBOM_CREATE_SERVER_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI MBOM publish create substage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostics must never alter the original response or transaction.
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
