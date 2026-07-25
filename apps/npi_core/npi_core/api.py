from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Mapping

from .foundation.errors import InternalServerError, NpiProblem
from .foundation.tracing import current_trace_id, resolve_trace_id


UnexpectedErrorReporter = Callable[[Exception, str], None]


@dataclass(frozen=True, slots=True)
class BinaryPayload:
    content: bytes
    file_name: str
    mime_type: str
    disposition: str
    headers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class _PreparedBinaryPayload:
    payload: BinaryPayload
    response_headers: dict[str, str]
    payload_headers: dict[str, str]


class _BinaryResponseFailure(RuntimeError):
    http_status_code = 500

    def __init__(self) -> None:
        super().__init__("The NPI binary response could not be completed.")


def execute_api(
    handler: Callable[[], Any],
    incoming_trace_id: str | None = None,
    report_unexpected_error: UnexpectedErrorReporter | None = None,
) -> tuple[int, Any, dict[str, str]]:
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
    handler: Callable[[], dict[str, Any]],
    *,
    cache_control: str | None = None,
    success_status: int = 200,
    response_headers: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """Thin adapter for whitelisted methods; handler must perform domain authorization."""
    import frappe

    if not 200 <= success_status < 300:
        raise ValueError("The success status must be a 2xx HTTP status.")

    status, body, headers = execute_api(
        handler,
        frappe.get_request_header("X-Trace-ID"),
        _record_unexpected_error,
    )
    if response_headers:
        headers.update(response_headers)
    if status == 200:
        status = success_status
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


def frappe_binary_call(
    handler: Callable[[], BinaryPayload],
    *,
    response_headers: Mapping[str, str] | None = None,
) -> None:
    """Return exact bytes only after the handler's audit transaction commits."""
    import frappe

    commit_observed = False

    def mark_committed() -> None:
        nonlocal commit_observed
        commit_observed = True

    try:
        frappe.db.after_commit.add(mark_committed)
    except Exception as error:
        trace_id = resolve_trace_id(frappe.get_request_header("X-Trace-ID"))
        _record_binary_failure(
            error,
            trace_id=trace_id,
            code="BINARY_COMMIT_OUTCOME_UNCERTAIN",
        )
        _stage_binary_internal_error(
            trace_id=trace_id,
            response_headers=response_headers,
        )
        raise _BinaryResponseFailure() from None

    status, body, headers = execute_api(
        lambda: _prepare_binary_payload(handler(), response_headers),
        frappe.get_request_header("X-Trace-ID"),
        _record_unexpected_error,
    )
    if status >= 400:
        if status >= 500:
            _stage_binary_problem(
                body,
                trace_id=headers["X-Trace-ID"],
                response_headers=response_headers,
            )
            raise _BinaryResponseFailure() from None
        if getattr(frappe, "db", None) is not None:
            try:
                frappe.db.rollback()
            except Exception as error:
                _record_binary_failure(
                    error,
                    trace_id=headers["X-Trace-ID"],
                    code="BINARY_ROLLBACK_FAILED",
                )
                _stage_binary_internal_error(
                    trace_id=headers["X-Trace-ID"],
                    response_headers=response_headers,
                )
                raise _BinaryResponseFailure() from None
        if response_headers:
            headers.update(response_headers)
        headers["Cache-Control"] = "private, no-store"
        frappe.local.response.http_status_code = status
        frappe.flags.npi_response_headers = headers
        frappe.flags.npi_response_body = body
        return
    if not isinstance(body, _PreparedBinaryPayload):
        _stage_binary_internal_error(
            trace_id=headers["X-Trace-ID"],
            response_headers=response_headers,
        )
        raise _BinaryResponseFailure() from None
    # Content authorization, integrity verification, audit append and command
    # receipt sealing are complete at this point. Commit them before any byte
    # can be handed to the response server.
    try:
        frappe.db.commit()
    except Exception as error:
        code = (
            "BINARY_AFTER_COMMIT_FAILED"
            if commit_observed
            else "BINARY_COMMIT_OUTCOME_UNCERTAIN"
        )
        _record_binary_failure(
            error,
            trace_id=headers["X-Trace-ID"],
            code=code,
        )
        _stage_binary_internal_error(
            trace_id=headers["X-Trace-ID"],
            response_headers=response_headers,
        )
        # Raising skips Frappe's unsafe-method success finalizer. Its finally
        # rollback contains an unknown transaction or the new transaction
        # opened after a successful SQL commit.
        raise _BinaryResponseFailure() from None

    try:
        payload = body.payload
        headers.update(body.response_headers)
        headers.update(body.payload_headers)
        headers["Content-Type"] = payload.mime_type
        headers["Content-Length"] = str(len(payload.content))
        headers["Cache-Control"] = "private, no-store"
        frappe.local.response.filename = payload.file_name
        frappe.local.response.filecontent = payload.content
        frappe.local.response.display_content_as = payload.disposition
        frappe.local.response.content_type = payload.mime_type
        frappe.flags.npi_response_headers = headers
        frappe.flags.npi_response_body = None
        frappe.local.response.http_status_code = 200
        # Set the response type last so no failed assignment can leave a
        # partially prepared download response visible to Frappe.
        frappe.local.response.type = "download"
    except Exception as error:
        _record_binary_failure(
            error,
            trace_id=headers["X-Trace-ID"],
            code="BINARY_RESPONSE_ASSEMBLY_FAILED",
        )
        _stage_binary_internal_error(
            trace_id=headers["X-Trace-ID"],
            response_headers=response_headers,
        )
        raise _BinaryResponseFailure() from None


_BINARY_PAYLOAD_HEADERS = frozenset(
    {
        "Content-Disposition",
        "Content-Security-Policy",
        "Referrer-Policy",
        "X-Content-Type-Options",
    }
)


def _prepare_binary_payload(
    value: object,
    response_headers: Mapping[str, str] | None,
) -> _PreparedBinaryPayload:
    if not isinstance(value, BinaryPayload):
        raise TypeError("A binary API handler must return BinaryPayload.")
    if (
        not isinstance(value.content, bytes)
        or not value.content
        or not _safe_header_value(value.file_name)
        or not _safe_header_value(value.mime_type)
        or "/" not in value.mime_type
        or value.disposition not in {"inline", "attachment"}
    ):
        raise ValueError("The binary API payload is invalid.")
    payload_headers = dict(value.headers)
    if set(payload_headers) != _BINARY_PAYLOAD_HEADERS or any(
        not _safe_header_value(name) or not _safe_header_value(header_value)
        for name, header_value in payload_headers.items()
    ):
        raise ValueError("The binary API headers are invalid.")
    if (
        payload_headers["X-Content-Type-Options"] != "nosniff"
        or payload_headers["Content-Security-Policy"] != "sandbox; default-src 'none'"
        or payload_headers["Referrer-Policy"] != "no-referrer"
    ):
        raise ValueError("The binary API security headers are invalid.")
    prepared_response_headers = dict(response_headers or {})
    if any(
        not _safe_header_value(name) or not _safe_header_value(header_value)
        for name, header_value in prepared_response_headers.items()
    ):
        raise ValueError("The binary API response headers are invalid.")
    return _PreparedBinaryPayload(
        payload=value,
        response_headers=prepared_response_headers,
        payload_headers=payload_headers,
    )


def _safe_header_value(value: object) -> bool:
    return bool(
        isinstance(value, str) and value and "\r" not in value and "\n" not in value
    )


def _record_binary_failure(
    error: Exception,
    *,
    trace_id: str,
    code: str,
) -> None:
    record_safe_diagnostic(
        code=code,
        title="NPI binary response failure",
        exception_type=type(error).__name__,
        trace_id=trace_id,
    )


def _stage_binary_internal_error(
    *,
    trace_id: str,
    response_headers: Mapping[str, str] | None,
) -> None:
    _stage_binary_problem(
        InternalServerError().as_dict(trace_id),
        trace_id=trace_id,
        response_headers=response_headers,
    )


def _stage_binary_problem(
    problem: object,
    *,
    trace_id: str,
    response_headers: Mapping[str, str] | None,
) -> None:
    import frappe

    safe_problem = (
        problem
        if isinstance(problem, dict) and problem.get("status") == 500
        else InternalServerError().as_dict(trace_id)
    )
    headers = {
        "Cache-Control": "private, no-store",
        "Content-Type": "application/problem+json",
        "X-Trace-ID": trace_id,
    }
    request_id = (
        response_headers.get("X-Request-ID")
        if hasattr(response_headers, "get")
        else None
    )
    if _safe_header_value(request_id):
        headers["X-Request-ID"] = request_id
    _clear_binary_response()
    frappe.local.response.http_status_code = 500
    frappe.flags.npi_response_headers = headers
    frappe.flags.npi_response_body = safe_problem


def _clear_binary_response() -> None:
    import frappe

    response = frappe.local.response
    for fieldname in (
        "type",
        "filename",
        "filecontent",
        "display_content_as",
        "content_type",
    ):
        if hasattr(response, "pop"):
            response.pop(fieldname, None)
        else:
            try:
                delattr(response, fieldname)
            except AttributeError:
                pass
