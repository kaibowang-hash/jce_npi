from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

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
        "P805_TOOL_ASSET_CONTEXT_QUERY_PARSE",
        "P805_TOOL_ASSET_CONTEXT_PROFILE_RESOLVE",
        "P805_TOOL_ASSET_CONTEXT_CREATE_SOURCE",
        "P805_TOOL_ASSET_CONTEXT_CREATE_PROFILE_BINDING",
        "P805_TOOL_ASSET_CONTEXT_CREATE_AUTHORITY",
        "P805_TOOL_ASSET_CONTEXT_CREATE_SANDBOX_GUARD",
        "P805_TOOL_ASSET_CONTEXT_CREATE_MAPPING",
        "P805_TOOL_ASSET_CONTEXT_CREATE_REQUEST_BUILD",
    }
)
TOOL_ASSET_CONTEXT_DIAGNOSTIC_HEADER = "X-NPI-Diagnostic-Scope"
TOOL_ASSET_CONTEXT_DIAGNOSTIC_SCOPE = "p805-tool-asset-command-context-v1"
_TOOL_ASSET_CONTEXT_FLAG = "npi_p805_tool_asset_context_diagnostic"
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
