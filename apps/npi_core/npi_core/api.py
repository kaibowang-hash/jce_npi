from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from .foundation.errors import InternalServerError, NpiProblem
from .foundation.tracing import current_trace_id, resolve_trace_id


UnexpectedErrorReporter = Callable[[Exception, str], None]


def execute_api(
    handler: Callable[[], dict[str, Any]],
    incoming_trace_id: str | None = None,
    report_unexpected_error: UnexpectedErrorReporter | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    trace_id = resolve_trace_id(incoming_trace_id)
    headers = {"Content-Type": "application/json", "X-Trace-ID": trace_id}
    try:
        return 200, handler(), headers
    except NpiProblem as problem:
        headers["Content-Type"] = "application/problem+json"
        return problem.status, problem.as_dict(trace_id), headers
    except Exception as error:
        if report_unexpected_error is not None:
            try:
                report_unexpected_error(error, trace_id)
            except Exception:
                # Diagnostics are secondary to preserving the safe user contract.
                # The standard logger is the last local fallback and never receives
                # either the original exception or request data.
                try:
                    logging.getLogger("npi_core").error(
                        "NPI error reporter failed for trace %s", trace_id
                    )
                except Exception:
                    pass
        problem = InternalServerError()
        headers["Content-Type"] = "application/problem+json"
        return problem.status, problem.as_dict(trace_id), headers


def record_safe_diagnostic(
    *,
    code: str,
    title: str,
    exception_type: str,
    trace_id: str | None = None,
) -> None:
    """Best-effort file and deferred Error Log recording without sensitive text."""
    import frappe

    resolved_trace_id = trace_id or current_trace_id.get() or "unavailable"
    record = json.dumps(
        {
            "code": code,
            "exceptionType": exception_type,
            "traceId": resolved_trace_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    fallback_logger = logging.getLogger("npi_core")
    try:
        frappe.logger("npi_core").error(record)
    except Exception:
        try:
            fallback_logger.error(record)
        except Exception:
            pass
    try:
        frappe.log_error(
            title=title,
            message=record,
            defer_insert=True,
        )
    except Exception:
        try:
            fallback_logger.error(
                "NPI deferred Error Log failed for trace %s", resolved_trace_id
            )
        except Exception:
            pass


def _record_unexpected_error(error: Exception, trace_id: str) -> None:
    record_safe_diagnostic(
        code="UNEXPECTED_BFF_EXCEPTION",
        title="NPI BFF unexpected exception",
        exception_type=type(error).__name__,
        trace_id=trace_id,
    )


def frappe_domain_call(
    handler: Callable[[], dict[str, Any]], *, cache_control: str | None = None
) -> dict[str, Any] | None:
    """Thin adapter for whitelisted methods; handler must perform domain authorization."""
    import frappe

    status, body, headers = execute_api(
        handler,
        frappe.get_request_header("X-Trace-ID"),
        _record_unexpected_error,
    )
    if status >= 400 and getattr(frappe, "db", None) is not None:
        # Frappe commits unsafe methods when their handler returns normally. Every
        # controlled non-2xx response therefore rolls back before the framework's
        # request finalizer can commit a partial mutation.
        frappe.db.rollback()
    if cache_control is not None:
        headers["Cache-Control"] = cache_control
    frappe.local.response.http_status_code = status
    frappe.flags.npi_response_headers = headers
    if getattr(getattr(frappe, "flags", None), "npi_bff_request", False):
        frappe.flags.npi_response_body = body
        return None
    return body
