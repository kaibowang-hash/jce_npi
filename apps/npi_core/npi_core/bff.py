from __future__ import annotations

import json
import re

import frappe

from .api import frappe_domain_call
from .foundation.errors import ApiRouteNotFound, CsrfTokenInvalid, MalformedRequest
from .foundation.tracing import resolve_trace_id
from .request_security import response_request_id

_ROUTES = {
    ("GET", "/api/npi/v1/session/bootstrap"): (
        "npi_core.localization_api.get_session_bootstrap"
    ),
    ("PUT", "/api/npi/v1/session/language"): (
        "npi_core.localization_api.set_current_user_language"
    ),
    ("POST", "/api/npi/v1/projects"): "npi_core.project_api.create_project",
}

_PROJECT_COCKPIT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/cockpit$"
)
_PROJECT_WORK_CONTEXT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/work-context$"
)
_PROJECT_DOMAIN_WORK_ITEMS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/domain-work-items$"
)
_GATE_EVIDENCE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+)/evidence$"
)
_GATE_REQUIREMENT_FREEZE_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+):freeze-requirements$"
)
_GATE_EVIDENCE_ATTACH_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+)/requirements/(?P<requirement_key>[^/]+)/evidence$"
)
_PROJECT_WORK_COMMAND_ROUTES = (
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):configure-team$"),
        "npi_core.project_work_api.configure_project_team",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):apply-work-plan$"),
        "npi_core.project_work_api.apply_project_work_plan",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):capture-plan-baseline$"
        ),
        "npi_core.project_work_api.capture_project_plan_baseline",
    ),
)


def route_request() -> None:
    """Map the fixed NPI BFF surface before Frappe's generic API router runs."""
    request = frappe.local.request
    path = request.path.rstrip("/") or "/"
    if not _is_npi_api_path(path) or request.method == "OPTIONS":
        return

    command = _ROUTES.get((request.method, path))
    route_params: dict[str, str] = {}
    if command is None and request.method == "GET":
        match = _PROJECT_COCKPIT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_api.get_project_cockpit"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_WORK_CONTEXT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_work_api.get_project_work_context"
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_DOMAIN_WORK_ITEMS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.project_work_api.get_project_domain_work_items"
                if request.method == "GET"
                else "npi_core.project_work_api.create_project_domain_work_item"
            )
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _GATE_EVIDENCE_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_evidence_api.get_gate_evidence_workspace"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _GATE_REQUIREMENT_FREEZE_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_evidence_api.freeze_gate_requirements"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _GATE_EVIDENCE_ATTACH_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_evidence_api.attach_gate_evidence"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        for route, candidate in _PROJECT_WORK_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    frappe.local.form_dict.cmd = command or "npi_core.bff.route_not_found"
    frappe.flags.npi_bff_request = True
    frappe.flags.npi_route_params = route_params


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def route_not_found() -> dict[str, object] | None:
    """Return the NPI problem contract instead of leaking Frappe routing errors."""

    def raise_not_found() -> dict[str, object]:
        raise ApiRouteNotFound()

    return frappe_domain_call(raise_not_found)


def _is_npi_api_path(path: str) -> bool:
    normalized_path = path.rstrip("/") or "/"
    return normalized_path == "/api/npi/v1" or normalized_path.startswith(
        "/api/npi/v1/"
    )


def _normalize_pre_handler_problem(response, request) -> bool:
    """Normalize narrowly identified failures raised before the BFF route hook."""
    request = request or getattr(getattr(frappe, "local", None), "request", None)
    if not request or not _is_npi_api_path(getattr(request, "path", "")):
        return False

    flags = getattr(frappe, "flags", None)
    if (
        getattr(flags, "npi_response_headers", None)
        or getattr(flags, "npi_response_body", None) is not None
    ):
        return False

    response_metadata = getattr(getattr(frappe, "local", None), "response", None)
    exception_type = (
        response_metadata.get("exc_type") if hasattr(response_metadata, "get") else None
    )
    response_status = getattr(response, "status_code", None)
    if exception_type == "CSRFTokenError" and response_status in {400, 403}:
        problem_error = CsrfTokenInvalid()
    elif (
        exception_type in {"JSONDecodeError", "ValidationError"}
        and isinstance(response_status, int)
        and response_status >= 400
    ):
        problem_error = MalformedRequest()
    else:
        return False

    trace_id = resolve_trace_id(frappe.get_request_header("X-Trace-ID"))
    problem = problem_error.as_dict(trace_id)
    headers = {
        "Cache-Control": "private, no-store",
        "Content-Type": "application/problem+json",
        "X-Trace-ID": trace_id,
    }
    if _requires_project_request_id(request.method, request.path.rstrip("/")):
        headers["X-Request-ID"] = response_request_id()
    frappe.flags.npi_response_body = problem
    frappe.flags.npi_response_headers = headers
    response.status_code = problem["status"]
    response.set_data(json.dumps(problem, ensure_ascii=False, separators=(",", ":")))
    for name, value in headers.items():
        response.headers[name] = value
    return True


def _requires_project_request_id(method: str, path: str) -> bool:
    if method == "POST" and path == "/api/npi/v1/projects":
        return True
    if method == "GET" and (
        _PROJECT_COCKPIT_ROUTE.fullmatch(path) is not None
        or _PROJECT_WORK_CONTEXT_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_DOMAIN_WORK_ITEMS_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and _GATE_EVIDENCE_ROUTE.fullmatch(path) is not None:
        return True
    if method == "POST" and (
        _GATE_REQUIREMENT_FREEZE_ROUTE.fullmatch(path) is not None
        or _GATE_EVIDENCE_ATTACH_ROUTE.fullmatch(path) is not None
    ):
        return True
    return method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _PROJECT_WORK_COMMAND_ROUTES
    )


def attach_response_headers(response=None, request=None) -> None:
    """Replace Frappe's RPC envelope and attach real NPI HTTP headers."""
    if response is None:
        return
    if _normalize_pre_handler_problem(response, request):
        return
    body = getattr(getattr(frappe, "flags", None), "npi_response_body", None)
    if body is not None:
        response.set_data(json.dumps(body, ensure_ascii=False, separators=(",", ":")))
    headers = getattr(getattr(frappe, "flags", None), "npi_response_headers", None)
    if not headers:
        return
    for name, value in headers.items():
        response.headers[name] = value
