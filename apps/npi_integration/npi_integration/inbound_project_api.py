from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.api import record_safe_diagnostic
from npi_core.request_security import configured_tenant_id
from npi_integration.inbound_project.domain import MAX_RAW_BODY_BYTES, raw_body_hash
from npi_integration.inbound_project.frappe_repository import (
    FrappeInboundProjectRepository,
    InboundProjectLandingOutcome,
)
from npi_integration.inbound_project.ingress import (
    AuthenticatedProjectSourceRequest,
    InboundProjectIngressProblem,
    authenticate_project_source_request,
)


_PROFILE_RESOLVER_HOOK = "npi_inbound_project_profile_resolver"
_SECRET_RESOLVER_HOOK = "npi_inbound_project_secret_resolver"


class _InboundProjectCommitFailure(RuntimeError):
    http_status_code = 500


@frappe.whitelist(allow_guest=True, methods=["POST"])
def accept_project_source_event() -> None:
    """Accept exactly one raw signed event; never perform Project business work."""
    _execute_inbound_request(
        request=frappe.local.request,
        repository=FrappeInboundProjectRepository(),
        profile_resolver=_configured_profile,
        secret_resolver=_configured_secret,
        site_tenant_resolver=configured_tenant_id,
        clock=lambda: datetime.now(UTC),
        enqueue=_enqueue_after_commit,
    )


def _execute_inbound_request(
    *,
    request: Any,
    repository: FrappeInboundProjectRepository,
    profile_resolver: Callable[[], object | None],
    secret_resolver: Callable[[str], bytes],
    site_tenant_resolver: Callable[[], str],
    clock: Callable[[], datetime],
    enqueue: Callable[[UUID], None],
) -> None:
    received_at = clock()
    presented_request_id = _header(request, "X-Request-ID")
    response_request_id = _response_request_id(presented_request_id)
    trace_id = f"inbound-{response_request_id}"
    presented_key_id = _header(request, "X-NPI-Key-ID")
    raw_body = b""
    body_size: int | None = None
    try:
        content_length = getattr(request, "content_length", None)
        if type(content_length) is int and content_length > MAX_RAW_BODY_BYTES:
            body_size = content_length
            raise InboundProjectIngressProblem(
                status=413,
                code="INBOUND_PROJECT_BODY_TOO_LARGE",
            )
        raw_body = request.get_data(cache=True, as_text=False)
        if not isinstance(raw_body, bytes):
            raise TypeError("Raw request body is unavailable.")
        body_size = len(raw_body)
        try:
            site_tenant_id = site_tenant_resolver()
        except Exception as error:
            raise InboundProjectIngressProblem(
                status=503,
                code="INBOUND_PROJECT_INGRESS_UNAVAILABLE",
                retryable=True,
            ) from error
        authenticated = authenticate_project_source_request(
            method=str(getattr(request, "method", "")),
            path=str(getattr(request, "path", "")),
            content_type=getattr(request, "content_type", None),
            content_encoding=_header(request, "Content-Encoding"),
            raw_body=raw_body,
            request_id=presented_request_id,
            key_id=presented_key_id,
            timestamp=_header(request, "X-NPI-Timestamp"),
            signature=_header(request, "X-NPI-Signature"),
            is_secure=bool(getattr(request, "is_secure", False)),
            site_tenant_id=site_tenant_id,
            now=received_at,
            profile_resolver=profile_resolver,
            secret_resolver=secret_resolver,
        )
        trace_id = authenticated.event.trace_id
        outcome = _land_with_unique_race_retry(repository, authenticated)
        try:
            frappe.db.commit()
        except Exception as error:
            _rollback_safely()
            _record_failure("INBOUND_PROJECT_COMMIT_FAILED", error, trace_id)
            _stage_problem(
                status=500,
                code="INTERNAL_SERVER_ERROR",
                retryable=True,
                request_id=response_request_id,
                trace_id=trace_id,
            )
            # Raising skips Frappe's normal unsafe-method commit finalizer; the
            # after-request hook retains the already staged safe problem body.
            raise _InboundProjectCommitFailure(
                "Inbound Project commit outcome is unavailable."
            ) from None
        if outcome.conflict_code is not None:
            _stage_problem(
                status=409,
                code=outcome.conflict_code,
                retryable=False,
                request_id=response_request_id,
                trace_id=trace_id,
            )
            return
        if outcome.should_enqueue:
            try:
                enqueue(outcome.receipt_id)
            except Exception as error:
                _record_failure("INBOUND_PROJECT_ENQUEUE_FAILED", error, trace_id)
        _stage_success(
            outcome=outcome,
            request_id=response_request_id,
            trace_id=trace_id,
        )
    except _InboundProjectCommitFailure:
        raise
    except InboundProjectIngressProblem as problem:
        _persist_rejection(
            repository=repository,
            request_id=response_request_id,
            trace_id=trace_id,
            problem=problem,
            received_at=received_at,
            body_size=body_size,
            raw_body=raw_body,
            presented_key_id=presented_key_id,
        )
    except Exception as error:
        _rollback_safely()
        _record_failure("INBOUND_PROJECT_UNEXPECTED_FAILURE", error, trace_id)
        internal = InboundProjectIngressProblem(
            status=500,
            code="INTERNAL_SERVER_ERROR",
            retryable=True,
        )
        _persist_rejection(
            repository=repository,
            request_id=response_request_id,
            trace_id=trace_id,
            problem=internal,
            received_at=received_at,
            body_size=body_size,
            raw_body=raw_body,
            presented_key_id=presented_key_id,
        )


def _land_with_unique_race_retry(
    repository: FrappeInboundProjectRepository,
    authenticated: AuthenticatedProjectSourceRequest,
) -> InboundProjectLandingOutcome:
    try:
        return repository.land(authenticated)
    except frappe.DuplicateEntryError:
        # A concurrent first receipt or source-stream reservation can win its
        # unique key. Roll back every local partial write, then classify once
        # against the winner's now-durable truth.
        frappe.db.rollback()
        return repository.land(authenticated)


def _persist_rejection(
    *,
    repository: FrappeInboundProjectRepository,
    request_id: UUID,
    trace_id: str,
    problem: InboundProjectIngressProblem,
    received_at: datetime,
    body_size: int | None,
    raw_body: bytes,
    presented_key_id: str | None,
) -> None:
    _rollback_safely()
    try:
        repository.append_ingress_failure_audit(
            request_id=request_id,
            trace_id=trace_id,
            code=problem.code,
            received_at=received_at,
            body_size=body_size,
            raw_hash=(
                raw_body_hash(raw_body)
                if raw_body and len(raw_body) <= MAX_RAW_BODY_BYTES
                else None
            ),
            key_id_hash=_key_id_hash(presented_key_id),
        )
    except Exception as error:
        _rollback_safely()
        _record_failure("INBOUND_PROJECT_REJECTION_AUDIT_FAILED", error, trace_id)
        problem = InboundProjectIngressProblem(
            status=500,
            code="INTERNAL_SERVER_ERROR",
            retryable=True,
        )
    else:
        try:
            frappe.db.commit()
        except Exception as error:
            _rollback_safely()
            _record_failure(
                "INBOUND_PROJECT_REJECTION_COMMIT_FAILED", error, trace_id
            )
            _stage_problem(
                status=500,
                code="INTERNAL_SERVER_ERROR",
                retryable=True,
                request_id=request_id,
                trace_id=trace_id,
            )
            raise _InboundProjectCommitFailure(
                "Inbound Project rejection commit outcome is unavailable."
            ) from None
    _stage_problem(
        status=problem.status,
        code=problem.code,
        retryable=problem.retryable,
        request_id=request_id,
        trace_id=trace_id,
    )


def _configured_profile() -> object | None:
    resolver = _single_hook(_PROFILE_RESOLVER_HOOK)
    return None if resolver is None else resolver()


def _configured_secret(secret_reference: str) -> bytes:
    resolver = _single_hook(_SECRET_RESOLVER_HOOK)
    if resolver is None:
        raise RuntimeError("Inbound Project secret resolver is unavailable.")
    return resolver(secret_reference)


def _single_hook(name: str) -> Callable[..., Any] | None:
    hooks = frappe.get_hooks(name)
    values = [hooks] if isinstance(hooks, str) else list(hooks or ())
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        raise RuntimeError("Inbound Project resolver hook is ambiguous.")
    resolver = frappe.get_attr(values[0])
    if not callable(resolver):
        raise RuntimeError("Inbound Project resolver hook is invalid.")
    return resolver


def _enqueue_after_commit(receipt_id: UUID) -> None:
    frappe.enqueue(
        "npi_integration.inbound_project.worker.process_inbox_message",
        queue="short",
        enqueue_after_commit=False,
        deduplicate=True,
        job_id=f"inbound-project-{receipt_id}",
        receipt_id=str(receipt_id),
    )


def _stage_success(
    *,
    outcome: InboundProjectLandingOutcome,
    request_id: UUID,
    trace_id: str,
) -> None:
    body = {
        "receiptId": str(outcome.receipt_id),
        "eventId": str(outcome.event_id),
        "state": outcome.state,
        "exactDuplicate": outcome.exact_duplicate,
        "requestId": str(request_id),
        "traceId": trace_id,
    }
    _stage_response(
        status=202,
        body=body,
        content_type="application/json",
        request_id=request_id,
        trace_id=trace_id,
    )


def _stage_problem(
    *,
    status: int,
    code: str,
    retryable: bool,
    request_id: UUID,
    trace_id: str,
) -> None:
    body = {
        "type": f"urn:npi:problem:{code.casefold()}",
        "title": _problem_title(code),
        "status": status,
        "code": code,
        "traceId": trace_id,
        "retryable": retryable,
    }
    _stage_response(
        status=status,
        body=body,
        content_type="application/problem+json",
        request_id=request_id,
        trace_id=trace_id,
    )


def _problem_title(code: str) -> str:
    if code == "INBOUND_PROJECT_AUTHENTICATION_FAILED":
        return _("Webhook authentication failed.")
    if code == "INBOUND_PROJECT_BODY_TOO_LARGE":
        return _("The webhook request body is too large.")
    if code == "INBOUND_PROJECT_EVENT_CONFLICT":
        return _(
            "The authenticated Project source event conflicts with existing history."
        )
    if code == "INBOUND_PROJECT_EVENT_INVALID":
        return _("The authenticated Project source event is invalid.")
    if code == "INBOUND_PROJECT_INGRESS_UNAVAILABLE":
        return _("The inbound Project service is unavailable.")
    if code == "INBOUND_PROJECT_MEDIA_TYPE_UNSUPPORTED":
        return _("The webhook media type is not supported.")
    if code == "INBOUND_PROJECT_SOURCE_CONFLICT":
        return _("The Project source version conflicts with existing history.")
    return _("The request could not be completed.")


def _stage_response(
    *,
    status: int,
    body: dict[str, object],
    content_type: str,
    request_id: UUID,
    trace_id: str,
) -> None:
    frappe.local.response.http_status_code = status
    frappe.flags.npi_response_body = body
    frappe.flags.npi_response_headers = {
        "Cache-Control": "no-store",
        "Content-Type": content_type,
        "X-Request-ID": str(request_id),
        "X-Trace-ID": trace_id,
    }


def _header(request: Any, name: str) -> str | None:
    headers = getattr(request, "headers", None)
    value = headers.get(name) if hasattr(headers, "get") else None
    return value if isinstance(value, str) else None


def _response_request_id(value: object) -> UUID:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError):
        return uuid4()
    return parsed if str(parsed) == str(value) else uuid4()


def _key_id_hash(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _rollback_safely() -> None:
    try:
        frappe.db.rollback()
    except Exception:
        pass


def _record_failure(code: str, error: Exception, trace_id: str) -> None:
    record_safe_diagnostic(
        code=code,
        title="NPI inbound Project failure",
        exception_type=type(error).__name__,
        trace_id=trace_id,
    )
