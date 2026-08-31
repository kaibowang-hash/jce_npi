from __future__ import annotations

import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Callable, Iterator
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call, record_safe_diagnostic
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.foundation.security import Principal, ProjectAccess
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    configured_tenant_id,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    response_request_id,
)

from .engineering_change.config import IntegrationProfile
from .engineering_change.ingress import IngressProblem, authenticate_inbound_request
from .engineering_change.problems import EngineeringChangeAuthenticationFailed, EngineeringChangeIntegrationUnavailable
from .engineering_change.signature import WEBHOOK_PATH


_PROFILE_HOOK = "npi_engineering_change_profile_resolver"
_SECRET_HOOK = "npi_engineering_change_secret_resolver"
_SUMMARY_FIELDS = frozenset({"expectedRevision", "expectedRevisionGlobalId", "expectedRevisionSnapshotHash"})
ENGINEERING_CHANGE_INBOUND_FULL_DIAGNOSTICS_ENABLED = False
ENGINEERING_CHANGE_POST_RAW_BODY_DIAGNOSTICS_ENABLED = True
ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_HEADER = (
    "X-NPI-P901-Change-Inbound-Diagnostic"
)
ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_SCOPE = (
    "p9-01-engineering-change-inbound-server-v1"
)
ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_TRACE_HEADER = (
    "X-NPI-P901-Change-Inbound-Diagnostic-Trace"
)
_INBOUND_DIAGNOSTIC_ACTIVE: ContextVar[bool] = ContextVar(
    "p901_engineering_change_inbound_diagnostic_active", default=False
)
_DIAGNOSTIC_PATH_NAME = "p9-01-engineering-change-runtime-diagnostic.json"
_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")


@contextmanager
def engineering_change_inbound_diagnostics(
    trace_id: object,
    *,
    active: bool,
) -> Iterator[None]:
    token = _INBOUND_DIAGNOSTIC_ACTIVE.set(active)
    try:
        if active and isinstance(trace_id, str):
            from npi_core.change_control.frappe_repository import (
                engineering_change_revise_server_diagnostics as server_scope,
            )

            with server_scope(trace_id, active=True):
                yield
        else:
            yield
    finally:
        _INBOUND_DIAGNOSTIC_ACTIVE.reset(token)


@contextmanager
def engineering_change_inbound_step(code: str) -> Iterator[None]:
    if _INBOUND_DIAGNOSTIC_ACTIVE.get():
        from npi_core.change_control.frappe_repository import (
            engineering_change_revise_server_step as server_step,
        )

        with server_step(code):
            yield
    else:
        yield


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive_engineering_change_event() -> dict[str, Any] | None:
    request = getattr(frappe.local, "request", None)
    trace_id = (
        request.headers.get(ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_TRACE_HEADER)
        if request is not None and hasattr(request, "headers")
        else None
    )
    with engineering_change_inbound_diagnostics(
        trace_id,
        active=_engineering_change_inbound_diagnostic_active(trace_id),
    ):
        with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_CALL"):
            return _receive_engineering_change_event()


def _receive_engineering_change_event() -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id(), "Idempotency-Replayed": "false"}
    replayed = False

    def handle() -> dict[str, Any]:
        nonlocal replayed
        with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_FIELDS"):
            request = getattr(frappe.local, "request", None)
        with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_REQUEST"):
            if request is None:
                raise EngineeringChangeIntegrationUnavailable()
        with engineering_change_inbound_step(
            "P901_CHANGE_INBOUND_API_AUTHENTICATE"
        ):
            try:
                authenticated = authenticate_inbound_request(
                    method=str(request.method), path=WEBHOOK_PATH,
                    content_type=request.headers.get("Content-Type"), content_encoding=request.headers.get("Content-Encoding"),
                    raw_body=request.get_data(cache=True), request_id=request.headers.get("X-Request-ID"),
                    key_id=request.headers.get("X-NPI-Key-ID"), timestamp=request.headers.get("X-NPI-Timestamp"),
                    signature=request.headers.get("X-NPI-Signature"), is_secure=bool(request.is_secure),
                    site_tenant_id=_site_tenant_id(), now=datetime.now(UTC),
                    profile_resolver=_profile_resolver(), secret_resolver=_secret_resolver(),
                )
            except IngressProblem as error:
                if error.status == 401:
                    raise EngineeringChangeAuthenticationFailed() from error
                raise NpiProblem(
                    error.status,
                    error.code,
                    _("The Engineering Change event is unavailable."),
                    retryable=error.retryable,
                ) from error
        with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_PRINCIPAL"):
            profile = authenticated.profile
            principal = Principal(
                user_id=profile.service_actor_user_id,
                roles=frozenset({"NPI API User", "System Manager"}),
                project_access={str(authenticated.event.project_global_id): ProjectAccess.ADMINISTER},
                tenant_id=profile.tenant_id,
            )
        with engineering_change_inbound_step(
            "P901_CHANGE_INBOUND_API_REPOSITORY_INIT"
        ):
            repository = _repository(
                principal,
                authenticated.headers.request_id,
                authenticated.event.trace_id,
            )
        with engineering_change_inbound_step(
            "P901_CHANGE_INBOUND_API_REPOSITORY_CALL"
        ):
            outcome = repository.receive_inbound(authenticated)
        with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_COMMIT"):
            frappe.db.commit()
        with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_ENQUEUE"):
            if outcome.should_enqueue and outcome.queue_id is not None:
                _enqueue_inbox(outcome.queue_id)
        with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_OUTCOME"):
            replayed = outcome.replayed
            headers["X-Request-ID"] = authenticated.headers.request_id
            headers["Idempotency-Replayed"] = str(replayed).lower()
            return outcome.response

    with engineering_change_inbound_step("P901_CHANGE_INBOUND_API_RESPONSE"):
        result = frappe_domain_call(
            handle,
            cache_control="no-store",
            success_status=202,
            response_headers=headers,
        )
        if replayed and frappe.local.response.http_status_code == 202:
            frappe.local.response.http_status_code = 200
        return result


def _engineering_change_inbound_diagnostic_active(trace_id: object) -> bool:
    try:
        request = getattr(frappe.local, "request", None)
        arguments = getattr(request, "args", None)
        headers = getattr(request, "headers", None)
        diagnostic_path = os.environ.get("NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH")
        return (
            (
                ENGINEERING_CHANGE_INBOUND_FULL_DIAGNOSTICS_ENABLED
                or ENGINEERING_CHANGE_POST_RAW_BODY_DIAGNOSTICS_ENABLED
            )
            and os.environ.get("NPI_P9_01C_RUNTIME_ENABLED") == "1"
            and isinstance(diagnostic_path, str)
            and os.path.isabs(diagnostic_path)
            and os.path.basename(diagnostic_path) == _DIAGNOSTIC_PATH_NAME
            and request is not None
            and getattr(request, "method", None) == "POST"
            and getattr(request, "path", None) == WEBHOOK_PATH
            and arguments is not None
            and list(arguments.keys()) == []
            and headers is not None
            and headers.get(ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_HEADER)
            == ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_SCOPE
            and headers.get(
                ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_TRACE_HEADER
            )
            == trace_id
            and isinstance(trace_id, str)
            and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
        )
    except Exception:
        return False


@frappe.whitelist(allow_guest=True, methods=["POST"])
def request_change_implementation_summary(
    expectedRevision: Any = None,
    expectedRevisionGlobalId: Any = None,
    expectedRevisionSnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id(), "Idempotency-Replayed": "false"}
    replayed = False

    def handle() -> dict[str, Any]:
        nonlocal replayed
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        request_id = headers["X-Request-ID"]
        project_id = _route_uuid("project_id")
        change_id = _route_uuid("change_id")
        repository = _repository(principal, request_id, current_trace_id.get())
        if not repository.authorize_scope(project_id):
            raise EngineeringChangeIntegrationUnavailable()
        reject_unexpected_request_fields(_SUMMARY_FIELDS, request_fields)
        require_request_fields(_SUMMARY_FIELDS, request_fields)
        outcome = repository.create_summary_request(
            project_id, change_id,
            expected_revision=_positive(expectedRevision, "expectedRevision"),
            expected_revision_global_id=_uuid(expectedRevisionGlobalId, "expectedRevisionGlobalId"),
            expected_revision_snapshot_hash=_hash(expectedRevisionSnapshotHash, "expectedRevisionSnapshotHash"),
            idempotency_key_hash=actor_idempotency_key_hash(actor, _idempotency_key()),
        )
        if outcome is None:
            raise EngineeringChangeIntegrationUnavailable()
        frappe.db.commit()
        if outcome.should_enqueue and outcome.queue_id is not None:
            try:
                _enqueue_summary(outcome.queue_id)
            except Exception as error:
                record_safe_diagnostic(
                    code="CHANGE_SUMMARY_ENQUEUE_FAILED",
                    title="Engineering Change summary enqueue failed",
                    exception_type=type(error).__name__,
                    trace_id=current_trace_id.get(),
                )
        replayed = outcome.replayed
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(replayed).lower()
        return outcome.response

    result = frappe_domain_call(handle, cache_control="private, no-store", success_status=202, response_headers=headers)
    if replayed and frappe.local.response.http_status_code == 202:
        frappe.local.response.http_status_code = 200
    return result


def _repository(principal: Principal, request_id: str, trace_id: str):
    from .engineering_change.frappe_repository import FrappeEngineeringChangeIntegrationRepository
    if not isinstance(trace_id, str):
        raise EngineeringChangeIntegrationUnavailable()
    return FrappeEngineeringChangeIntegrationRepository(principal=principal, request_id=request_id, trace_id=trace_id, profile_resolver=_profile_resolver())


def _profile_resolver() -> Callable[..., IntegrationProfile | None] | None:
    return _hook(_PROFILE_HOOK)


def _secret_resolver() -> Callable[[str], bytes] | None:
    return _hook(_SECRET_HOOK)


def _hook(name: str):
    values = frappe.get_hooks(name)
    values = [values] if isinstance(values, str) else list(values or ())
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        raise EngineeringChangeIntegrationUnavailable()
    value = frappe.get_attr(values[0])
    if not callable(value):
        raise EngineeringChangeIntegrationUnavailable()
    return value


def _site_tenant_id() -> str:
    return configured_tenant_id()


def _route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    return _uuid(value, name)


def _uuid(value: object, path: str) -> UUID:
    try:
        result = UUID(str(value))
    except (TypeError, ValueError) as error:
        raise RequestValidationFailed([{"path": path, "message": "Enter a valid UUID."}]) from error
    if str(result) != str(value):
        raise RequestValidationFailed([{"path": path, "message": "Enter a canonical UUID."}])
    return result


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise RequestValidationFailed([{"path": path, "message": "Enter a positive integer."}])
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise RequestValidationFailed([{"path": path, "message": "Enter a valid SHA-256 hash."}])
    return value


def _idempotency_key() -> str:
    value = getattr(frappe.local, "request", None)
    key = value.headers.get("Idempotency-Key") if value is not None else None
    if not isinstance(key, str) or not 8 <= len(key) <= 255:
        raise RequestValidationFailed([{"path": "Idempotency-Key", "message": "Enter a valid idempotency key."}])
    return key


def _enqueue_inbox(receipt_id: UUID) -> None:
    frappe.enqueue(
        "npi_integration.engineering_change.worker.process_engineering_change_inbox",
        receipt_id=str(receipt_id),
        queue="short",
        enqueue_after_commit=False,
        deduplicate=True,
        job_id=f"engineering-change-inbox-{receipt_id}",
    )


def _enqueue_summary(event_id: UUID) -> None:
    frappe.enqueue(
        "npi_integration.engineering_change.worker.execute_change_implementation_summary",
        event_id=str(event_id),
        queue="short",
        enqueue_after_commit=False,
        deduplicate=True,
        job_id=f"engineering-change-summary-{event_id}",
    )
