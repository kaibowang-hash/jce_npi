from __future__ import annotations

import json
import re

import frappe

from .api import frappe_domain_call
from .foundation.errors import (
    ApiRouteNotFound,
    CsrfTokenInvalid,
    DocumentBaselineRoutesDisabled,
    DocumentReleaseRoutesDisabled,
    DocumentRoutesDisabled,
    MalformedRequest,
    ProjectCollaborationRoutesDisabled,
)
from .foundation.tracing import resolve_trace_id
from .request_security import (
    document_baseline_routes_are_disabled,
    document_release_routes_are_disabled,
    document_routes_are_disabled,
    project_collaboration_routes_are_disabled,
    response_request_id,
)

_ROUTES = {
    ("GET", "/api/npi/v1/session/bootstrap"): (
        "npi_core.localization_api.get_session_bootstrap"
    ),
    ("PUT", "/api/npi/v1/session/language"): (
        "npi_core.localization_api.set_current_user_language"
    ),
    ("PUT", "/api/npi/v1/session/preferences/navigation"): (
        "npi_core.localization_api.set_current_user_navigation_preference"
    ),
    ("POST", "/api/npi/v1/projects"): "npi_core.project_api.create_project",
    ("GET", "/api/npi/v1/me/work"): "npi_core.my_work_api.get_my_work",
    ("GET", "/api/npi/v1/me/preferences/my-work-grid"): (
        "npi_core.grid_personalization_api.get_my_work_grid_preferences"
    ),
    ("PUT", "/api/npi/v1/me/preferences/my-work-grid"): (
        "npi_core.grid_personalization_api.set_my_work_grid_preferences"
    ),
    ("GET", "/api/npi/v1/me/preferences/my-work-inspector"): (
        "npi_core.inspector_preferences_api.get_my_work_inspector_preference"
    ),
    ("PUT", "/api/npi/v1/me/preferences/my-work-inspector"): (
        "npi_core.inspector_preferences_api.set_my_work_inspector_preference"
    ),
    ("GET", "/api/npi/v1/learning"): (
        "npi_core.project_controls_api.search_project_learning"
    ),
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
_PROJECT_CONTROLS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/controls$"
)
_PROJECT_ACTIVITY_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/activity$"
)
_PROJECT_COMMENTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/comments$"
)
_PROJECT_LEARNING_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/learning$"
)
_PROJECT_DOCUMENTS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents$"
)
_PROJECT_DOCUMENT_BASELINES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/document-baselines$"
)
_PROJECT_DOCUMENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)$"
)
_DOCUMENT_CHECK_OUT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+):check-out$"
)
_DOCUMENT_CHECK_IN_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+):check-in$"
)
_DOCUMENT_RECOVER_LOCK_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+):recover-lock$"
)
_DOCUMENT_REVISIONS_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)/revisions$"
)
_DOCUMENT_RELEASE_COMMAND_ROUTES = (
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":submit-review$"
        ),
        "npi_core.document_api.submit_document_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":review$"
        ),
        "npi_core.document_api.confirm_document_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":resubmit-review$"
        ),
        "npi_core.document_api.resubmit_document_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":release$"
        ),
        "npi_core.document_api.release_document_revision",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":supersede$"
        ),
        "npi_core.document_api.supersede_document_revision",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
            r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)"
            r":obsolete$"
        ),
        "npi_core.document_api.obsolete_document_revision",
    ),
)
_DOCUMENT_FILE_CAPABILITIES_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)/files/"
    r"(?P<file_revision_id>[^/:]+)/capabilities$"
)
_DOCUMENT_FILE_CONTENT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/:]+)/documents/"
    r"(?P<document_id>[^/:]+)/revisions/(?P<revision_id>[^/:]+)/files/"
    r"(?P<file_revision_id>[^/:]+):content$"
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
_GATE_REVIEW_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/" r"(?P<gate_id>[^/:]+)/review$"
)
_GATE_REVIEW_COMMAND_RECEIPT_ROUTE = re.compile(
    r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
    r"(?P<gate_id>[^/:]+)/review-command-receipts/(?P<operation>[^/]+)$"
)
_GATE_REVIEW_COMMAND_ROUTES = (
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+):start-review$"
        ),
        "npi_core.gate_review_api.start_gate_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+)/review-cycles/(?P<cycle_id>[^/:]+)/reviews$"
        ),
        "npi_core.gate_review_api.submit_gate_review",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+)/review-cycles/(?P<cycle_id>[^/:]+)/exceptions$"
        ),
        "npi_core.gate_review_api.request_gate_review_exception",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+)/review-cycles/(?P<cycle_id>[^/:]+)/"
            r"exceptions/(?P<exception_id>[^/:]+):decide$"
        ),
        "npi_core.gate_review_api.decide_gate_review_exception",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+):decide$"
        ),
        "npi_core.gate_review_api.decide_gate",
    ),
    (
        re.compile(
            r"^/api/npi/v1/projects/(?P<project_id>[^/]+)/gates/"
            r"(?P<gate_id>[^/:]+):reopen$"
        ),
        "npi_core.gate_review_api.reopen_gate",
    ),
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
_PROJECT_CONTROL_COMMAND_ROUTES = (
    (
        re.compile(
            r"^/api/npi/v1/projects/" r"(?P<project_id>[^/:]+):bind-control-policy$"
        ),
        "npi_core.project_controls_api.bind_project_control_policy",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/" r"(?P<project_id>[^/:]+):assess-health$"),
        "npi_core.project_controls_api.assess_project_health",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):transition$"),
        "npi_core.project_controls_api.transition_project",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):follow$"),
        "npi_core.project_controls_api.follow_project",
    ),
    (
        re.compile(r"^/api/npi/v1/projects/(?P<project_id>[^/:]+):unfollow$"),
        "npi_core.project_controls_api.unfollow_project",
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
        match = _PROJECT_CONTROLS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_controls_api.get_project_controls"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _PROJECT_ACTIVITY_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_controls_api.get_project_activity"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _PROJECT_COMMENTS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.project_controls_api.add_project_comment"
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_LEARNING_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.project_controls_api.get_project_learning"
                if request.method == "GET"
                else "npi_core.project_controls_api.create_project_learning"
            )
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_DOCUMENT_BASELINES_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.document_api.get_document_baselines"
                if request.method == "GET"
                else "npi_core.document_api.create_document_baseline"
            )
            route_params = match.groupdict()
    if command is None and request.method in {"GET", "POST"}:
        match = _PROJECT_DOCUMENTS_ROUTE.fullmatch(path)
        if match is not None:
            command = (
                "npi_core.document_api.get_documents"
                if request.method == "GET"
                else "npi_core.document_api.create_document"
            )
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _DOCUMENT_FILE_CAPABILITIES_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.get_file_capabilities"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _DOCUMENT_FILE_CONTENT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.get_file_content"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        match = _DOCUMENT_REVISIONS_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.create_document_revision"
            route_params = match.groupdict()
    if command is None and request.method == "POST":
        for route, candidate in _DOCUMENT_RELEASE_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        document_commands = (
            (_DOCUMENT_CHECK_OUT_ROUTE, "npi_core.document_api.check_out_document"),
            (_DOCUMENT_CHECK_IN_ROUTE, "npi_core.document_api.check_in_document"),
            (
                _DOCUMENT_RECOVER_LOCK_ROUTE,
                "npi_core.document_api.recover_document_lock",
            ),
        )
        for route, candidate in document_commands:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "GET":
        match = _PROJECT_DOCUMENT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.document_api.get_document"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _GATE_EVIDENCE_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_evidence_api.get_gate_evidence_workspace"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _GATE_REVIEW_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_review_api.get_gate_review"
            route_params = match.groupdict()
    if command is None and request.method == "GET":
        match = _GATE_REVIEW_COMMAND_RECEIPT_ROUTE.fullmatch(path)
        if match is not None:
            command = "npi_core.gate_review_api.get_gate_review_command_receipt"
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
        for route, candidate in _GATE_REVIEW_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        for route, candidate in _PROJECT_WORK_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if command is None and request.method == "POST":
        for route, candidate in _PROJECT_CONTROL_COMMAND_ROUTES:
            match = route.fullmatch(path)
            if match is not None:
                command = candidate
                route_params = match.groupdict()
                break
    if _p4_05_routes_disabled(command):
        command = "npi_core.bff.project_collaboration_routes_disabled"
        route_params = {}
    if _p5_01_routes_disabled(command):
        command = "npi_core.bff.document_routes_disabled"
        route_params = {}
    if _p5_02_routes_disabled(command):
        command = "npi_core.bff.document_release_routes_disabled"
        route_params = {}
    if _p5_03_routes_disabled(command):
        command = "npi_core.bff.document_baseline_routes_disabled"
        route_params = {}
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


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST", "PUT"],
)
def project_collaboration_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P4-05 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise ProjectCollaborationRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def document_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P5-01 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise DocumentRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["POST"],
)
def document_release_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P5-02 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise DocumentReleaseRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


@frappe.whitelist(
    allow_guest=True,
    methods=["GET", "POST"],
)
def document_baseline_routes_disabled() -> dict[str, object] | None:
    """Fail closed while P5-03 routes await a reviewed forward fix."""

    def raise_disabled() -> dict[str, object]:
        raise DocumentBaselineRoutesDisabled()

    return frappe_domain_call(
        raise_disabled,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


def _p4_05_routes_disabled(command: str | None) -> bool:
    return project_collaboration_routes_are_disabled() and (
        command == "npi_core.my_work_api.get_my_work"
        or (
            isinstance(command, str)
            and command.startswith("npi_core.inspector_preferences_api.")
        )
        or (
            isinstance(command, str)
            and command.startswith("npi_core.project_controls_api.")
        )
    )


def _p5_02_routes_disabled(command: str | None) -> bool:
    release_commands = frozenset(
        candidate for _route, candidate in _DOCUMENT_RELEASE_COMMAND_ROUTES
    )
    return document_release_routes_are_disabled() and command in release_commands


def _p5_03_routes_disabled(command: str | None) -> bool:
    return document_baseline_routes_are_disabled() and command in {
        "npi_core.document_api.get_document_baselines",
        "npi_core.document_api.create_document_baseline",
    }


def _p5_01_routes_disabled(command: str | None) -> bool:
    return document_routes_are_disabled() and (
        isinstance(command, str) and command.startswith("npi_core.document_api.")
    )


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
    if method == "GET" and path == "/api/npi/v1/me/work":
        return True
    if (
        method in {"GET", "PUT"}
        and path == "/api/npi/v1/me/preferences/my-work-grid"
    ):
        return True
    if (
        method in {"GET", "PUT"}
        and path == "/api/npi/v1/me/preferences/my-work-inspector"
    ):
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
    if method == "GET" and (
        path == "/api/npi/v1/learning"
        or _PROJECT_CONTROLS_ROUTE.fullmatch(path) is not None
        or _PROJECT_ACTIVITY_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and _PROJECT_COMMENTS_ROUTE.fullmatch(path) is not None:
        return True
    if (
        method in {"GET", "POST"}
        and _PROJECT_LEARNING_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and _GATE_EVIDENCE_ROUTE.fullmatch(path) is not None:
        return True
    if method == "GET" and _GATE_REVIEW_ROUTE.fullmatch(path) is not None:
        return True
    if method in {"GET", "POST"} and (
        _PROJECT_DOCUMENTS_ROUTE.fullmatch(path) is not None
        or _PROJECT_DOCUMENT_BASELINES_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "GET" and (
        _PROJECT_DOCUMENT_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_FILE_CAPABILITIES_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and (
        _DOCUMENT_CHECK_OUT_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_CHECK_IN_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_RECOVER_LOCK_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_REVISIONS_ROUTE.fullmatch(path) is not None
        or _DOCUMENT_FILE_CONTENT_ROUTE.fullmatch(path) is not None
        or any(
            route.fullmatch(path) is not None
            for route, _command in _DOCUMENT_RELEASE_COMMAND_ROUTES
        )
    ):
        return True
    if (
        method == "GET"
        and _GATE_REVIEW_COMMAND_RECEIPT_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and (
        _GATE_REQUIREMENT_FREEZE_ROUTE.fullmatch(path) is not None
        or _GATE_EVIDENCE_ATTACH_ROUTE.fullmatch(path) is not None
    ):
        return True
    if method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _GATE_REVIEW_COMMAND_ROUTES
    ):
        return True
    if method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _PROJECT_WORK_COMMAND_ROUTES
    ):
        return True
    return method == "POST" and any(
        route.fullmatch(path) is not None
        for route, _command in _PROJECT_CONTROL_COMMAND_ROUTES
    )


def attach_response_headers(response=None, request=None) -> None:
    """Replace Frappe's RPC envelope and attach real NPI HTTP headers."""
    if response is None:
        return
    if _normalize_pre_handler_problem(response, request):
        return
    flags = getattr(frappe, "flags", None)
    body = getattr(flags, "npi_response_body", None)
    headers = getattr(flags, "npi_response_headers", None)
    if body is not None:
        response.set_data(json.dumps(body, ensure_ascii=False, separators=(",", ":")))
        body_status = body.get("status") if isinstance(body, dict) else None
        body_type = body.get("type") if isinstance(body, dict) else None
        if (
            isinstance(headers, dict)
            and headers.get("Content-Type") == "application/problem+json"
            and type(body_status) is int
            and 400 <= body_status <= 599
            and isinstance(body_type, str)
            and body_type.startswith("urn:npi:problem:")
        ):
            response.status_code = body_status
    if not headers:
        return
    for name, value in headers.items():
        response.headers[name] = value
