from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .foundation.errors import NpiProblem
from .foundation.tracing import resolve_trace_id


def execute_api(handler: Callable[[], dict[str, Any]], incoming_trace_id: str | None = None) -> tuple[int, dict[str, Any], dict[str, str]]:
    trace_id = resolve_trace_id(incoming_trace_id)
    headers = {"Content-Type": "application/json", "X-Trace-ID": trace_id}
    try:
        return 200, handler(), headers
    except NpiProblem as problem:
        headers["Content-Type"] = "application/problem+json"
        return problem.status, problem.as_dict(trace_id), headers


def frappe_domain_call(handler: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Thin adapter for whitelisted methods; handler must perform domain authorization."""
    import frappe

    status, body, headers = execute_api(handler, frappe.get_request_header("X-Trace-ID"))
    frappe.local.response.http_status_code = status
    frappe.local.response.headers = headers
    return body
