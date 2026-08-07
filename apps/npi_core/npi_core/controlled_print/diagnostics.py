from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

import frappe


CONTROLLED_PRINT_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P506_CREATE_COMMAND_CONTEXT",
        "P506_CREATE_INPUT_PARSE",
        "P506_CREATE_PROJECT_LOCK",
        "P506_CREATE_PAYLOAD_HASH",
        "P506_CREATE_IDEMPOTENCY_REPLAY",
        "P506_CREATE_SOURCE_RESOLVE",
        "P506_CREATE_MAPPING_RESOLVE",
        "P506_CREATE_AUTHORITY",
        "P506_CREATE_SNAPSHOT_BUILD",
        "P506_CREATE_PDF_RENDER",
        "P506_CREATE_TRANSACTION_SCOPE",
        "P506_CREATE_RECEIPT_INSERT",
        "P506_CREATE_SNAPSHOT_INSERT",
        "P506_CREATE_FILE_SAVE",
        "P506_CREATE_OUTPUT_INSERT",
        "P506_CREATE_ACCESS_EVENT_INSERT",
        "P506_CREATE_AUDIT_APPEND",
        "P506_CREATE_RESPONSE_BUILD",
        "P506_CREATE_RECEIPT_SEAL",
        "P506_CREATE_API_RESPONSE",
    }
)
CONTROLLED_PRINT_CREATE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
CONTROLLED_PRINT_CREATE_SERVER_DIAGNOSTIC_SCOPE = "p506-controlled-print-create-v1"
_DIAGNOSTIC_FLAG = "npi_p506_controlled_print_create_diagnostic"
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")


@contextmanager
def controlled_print_create_server_diagnostics(
    trace_id: str | None,
) -> Iterator[None]:
    """Enable one closed, response-neutral P5-06 create diagnostic scope."""

    try:
        enabled = (
            frappe.get_request_header(
                CONTROLLED_PRINT_CREATE_SERVER_DIAGNOSTIC_HEADER
            )
            == CONTROLLED_PRINT_CREATE_SERVER_DIAGNOSTIC_SCOPE
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
def controlled_print_create_server_step(code: str) -> Iterator[None]:
    """Record one allowlisted failing substage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        _record_controlled_print_create_server_failure(code, error)
        raise


def _record_controlled_print_create_server_failure(
    code: str,
    error: Exception,
) -> None:
    """Record only stage code, validated type, and the exact request trace."""

    try:
        state = _diagnostic_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in CONTROLLED_PRINT_CREATE_SERVER_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI controlled print create substage failed",
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
