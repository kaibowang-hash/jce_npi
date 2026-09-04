from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

import frappe


ITEM_CREATE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P803_CREATE_COMMAND_CONTEXT",
        "P803_CREATE_INPUT_PARSE",
        "P803_CREATE_PROJECT_LOCK",
        "P803_CREATE_IDEMPOTENCY_CONTEXT",
        "P803_CREATE_PROJECT_MUTABILITY",
        "P803_CREATE_SOURCE_RESOLVE",
        "P803_CREATE_MAPPING_READ",
        "P803_CREATE_PROFILE_RESOLVE",
        "P803_CREATE_DOMAIN_BUILD",
        "P803_CREATE_RESPONSE_BUILD",
        "P803_CREATE_TRANSACTION_SCOPE",
        "P803_CREATE_STREAM_GUARD",
        "P803_CREATE_LOCK_REVALIDATE",
        "P803_CREATE_REQUEST_INSERT",
        "P803_CREATE_OUTBOX_INSERT",
        "P803_CREATE_GUARD_ACTIVATE",
        "P803_CREATE_AUDIT_APPEND",
        "P803_CREATE_IDEMPOTENCY_INSERT",
        "P803_CREATE_REPOSITORY_COMMAND",
        "P803_CREATE_COMMIT",
        "P803_CREATE_ENQUEUE",
        "P803_CREATE_API_RESPONSE",
    }
)
ITEM_CREATE_SERVER_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
ITEM_CREATE_SERVER_DIAGNOSTIC_SCOPE = "p803-item-create-v1"
_DIAGNOSTIC_FLAG = "npi_p803_item_create_diagnostic"
ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P803_LEGACY_QUERY_CONTEXT",
        "P803_LEGACY_QUERY_REPOSITORY",
        "P803_LEGACY_QUERY_RESPONSE",
        "P803_LEGACY_QUERY_PROJECT",
        "P803_LEGACY_QUERY_PROFILE",
        "P803_LEGACY_QUERY_ROWS",
        "P803_LEGACY_QUERY_ROW_CLASSIFY",
        "P803_LEGACY_QUERY_BINDING_STATE",
        "P803_LEGACY_QUERY_STRICT_LEGACY",
        "P803_LEGACY_QUERY_LEGACY_PROJECT",
        "P803_LEGACY_QUERY_CURRENT_PROJECT",
        "P803_LEGACY_QUERY_MAPPING_EXPECTATION",
    }
)
ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER = ITEM_CREATE_SERVER_DIAGNOSTIC_HEADER
ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_SCOPE = "p803-legacy-query-v1"
_LEGACY_QUERY_DIAGNOSTIC_FLAG = "npi_p803_item_legacy_query_diagnostic"
_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")


@contextmanager
def item_create_server_diagnostics(trace_id: str | None) -> Iterator[None]:
    """Enable one closed, response-neutral P8-03 create diagnostic scope."""

    try:
        enabled = (
            frappe.get_request_header(ITEM_CREATE_SERVER_DIAGNOSTIC_HEADER)
            == ITEM_CREATE_SERVER_DIAGNOSTIC_SCOPE
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
def item_create_server_step(code: str) -> Iterator[None]:
    """Record one allowlisted failing substage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        _record_item_create_server_failure(code, error)
        raise


def _record_item_create_server_failure(code: str, error: Exception) -> None:
    """Record only stage code, validated type, and the exact request trace."""

    try:
        state = _diagnostic_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in ITEM_CREATE_SERVER_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Item publish create substage failed",
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


@contextmanager
def item_legacy_query_server_diagnostics(trace_id: str | None) -> Iterator[None]:
    """Enable one closed, response-neutral P8-03 legacy query scope."""

    try:
        enabled = (
            frappe.get_request_header(ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_HEADER)
            == ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_SCOPE
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
        previous = getattr(flags, _LEGACY_QUERY_DIAGNOSTIC_FLAG, missing)
        setattr(flags, _LEGACY_QUERY_DIAGNOSTIC_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _LEGACY_QUERY_DIAGNOSTIC_FLAG)
            else:
                setattr(flags, _LEGACY_QUERY_DIAGNOSTIC_FLAG, previous)
        except Exception:
            pass


@contextmanager
def item_legacy_query_server_step(code: str) -> Iterator[None]:
    """Record the innermost allowlisted legacy-query failure and re-raise it."""

    try:
        yield
    except Exception as error:
        _record_item_legacy_query_server_failure(code, error)
        raise


def _record_item_legacy_query_server_failure(code: str, error: Exception) -> None:
    try:
        state = _legacy_query_diagnostic_state()
        exception_type = type(error).__name__
        if (
            state is None
            or state["recorded"] is True
            or code not in ITEM_LEGACY_QUERY_SERVER_DIAGNOSTIC_CODES
            or _TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Item publish legacy query substage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        pass


def _legacy_query_diagnostic_state() -> dict[str, object] | None:
    state = getattr(frappe.flags, _LEGACY_QUERY_DIAGNOSTIC_FLAG, None)
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
        or type(state.get("recorded")) is not bool
    ):
        return None
    return state
