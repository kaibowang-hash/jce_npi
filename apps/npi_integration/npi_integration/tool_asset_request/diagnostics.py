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
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI predecessor Tool Asset create stage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
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
