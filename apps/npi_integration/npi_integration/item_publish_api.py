from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call, record_safe_diagnostic
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    response_request_id,
)
from npi_integration.item_publish.domain import ITEM_PUBLISH_ACKNOWLEDGEMENT
from npi_integration.item_publish.diagnostics import (
    item_create_server_diagnostics,
    item_create_server_step,
)
from npi_integration.item_publish.problems import ItemPublishUnavailable


_PROFILE_RESOLVER_HOOK = "npi_item_publish_profile_resolver"
_CREATE_FIELDS = frozenset(
    {
        "publishRequestGlobalId",
        "selectedPublishNodeGlobalId",
        "expectedMappingVersion",
        "acknowledgement",
    }
)
_LIST_FIELDS = frozenset(
    {"publishRequestGlobalId", "selectedPublishNodeGlobalId"}
)


class _Repository(Protocol):
    def authorize_scope(self, project_id: UUID, **values: Any) -> bool: ...

    def list_item_publish_requests(
        self,
        project_id: UUID,
        *,
        publish_request_id: UUID | None = None,
        selected_publish_node_id: UUID | None = None,
    ) -> dict[str, Any] | None: ...

    def item_publish_request_detail(
        self,
        project_id: UUID,
        request_global_id: UUID,
    ) -> dict[str, Any] | None: ...

    def create_item_publish_request(
        self,
        project_id: UUID,
        **values: Any,
    ) -> _CommandOutcome | None: ...


class _CommandOutcome(Protocol):
    response: dict[str, Any] | None
    replayed: bool
    should_enqueue: bool
    outbox_event_id: UUID | None
    problem: NpiProblem | None


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
    profile_resolver: Callable[[str, UUID], object | None] | None,
) -> _Repository:
    from npi_integration.item_publish.frappe_repository import (
        FrappeItemPublishRepository,
    )

    return FrappeItemPublishRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        profile_resolver=profile_resolver,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_item_publish_requests(
    publishRequestGlobalId: Any = None,
    selectedPublishNodeGlobalId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(
            request_fields,
            allowed_fields=_LIST_FIELDS,
        )
        response = repository.list_item_publish_requests(
            project_id,
            publish_request_id=_optional_uuid(
                publishRequestGlobalId,
                "publishRequestGlobalId",
            ),
            selected_publish_node_id=_optional_uuid(
                selectedPublishNodeGlobalId,
                "selectedPublishNodeGlobalId",
            ),
        )
        if response is None:
            raise ItemPublishUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_item_publish_request(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id = _query_context(
            request_fields,
            allowed_fields=frozenset(),
        )
        response = repository.item_publish_request_detail(
            project_id,
            _opaque_route_uuid("item_publish_request_id"),
        )
        if response is None:
            raise ItemPublishUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_item_publish_request(
    publishRequestGlobalId: Any = None,
    selectedPublishNodeGlobalId: Any = None,
    expectedMappingVersion: Any = None,
    acknowledgement: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }
    replayed = False

    def handle() -> dict[str, Any]:
        nonlocal replayed
        with item_create_server_diagnostics(current_trace_id.get()):
            with item_create_server_step("P803_CREATE_COMMAND_CONTEXT"):
                request_id, key_hash, repository, project_id = _command_context(
                    request_fields
                )
            with item_create_server_step("P803_CREATE_INPUT_PARSE"):
                values = {
                    "publish_request_id": _uuid(
                        publishRequestGlobalId,
                        "publishRequestGlobalId",
                    ),
                    "selected_publish_node_id": _uuid(
                        selectedPublishNodeGlobalId,
                        "selectedPublishNodeGlobalId",
                    ),
                    "expected_mapping_version": _nonnegative(
                        expectedMappingVersion,
                        "expectedMappingVersion",
                    ),
                    "acknowledgement": _exact_acknowledgement(acknowledgement),
                }
            with item_create_server_step("P803_CREATE_REPOSITORY_COMMAND"):
                outcome = repository.create_item_publish_request(
                    project_id,
                    idempotency_key_hash=key_hash,
                    **values,
                )
            with item_create_server_step("P803_CREATE_COMMIT"):
                if outcome is None:
                    raise ItemPublishUnavailable()
                if (
                    type(outcome.replayed) is not bool
                    or type(outcome.should_enqueue) is not bool
                ):
                    raise RuntimeError("The Item publish command result is invalid.")
                try:
                    frappe.db.commit()
                except Exception:
                    # No response or enqueue is allowed when local durability is unknown.
                    try:
                        frappe.db.rollback()
                    except Exception:
                        pass
                    raise
            if outcome.problem is not None:
                if not isinstance(outcome.problem, NpiProblem):
                    raise RuntimeError("The Item publish command problem is invalid.")
                raise outcome.problem
            if outcome.response is None:
                raise RuntimeError("The Item publish command response is unavailable.")
            if outcome.should_enqueue:
                if outcome.outbox_event_id is None:
                    raise RuntimeError("The Item publish Outbox identity is unavailable.")
                try:
                    with item_create_server_step("P803_CREATE_ENQUEUE"):
                        _enqueue_after_commit(outcome.outbox_event_id)
                except Exception as error:
                    record_safe_diagnostic(
                        code="ITEM_PUBLISH_ENQUEUE_FAILED",
                        title="NPI Item publish enqueue failed",
                        exception_type=type(error).__name__,
                        trace_id=current_trace_id.get(),
                    )
            with item_create_server_step("P803_CREATE_API_RESPONSE"):
                replayed = outcome.replayed
                headers["X-Request-ID"] = request_id
                headers["Idempotency-Replayed"] = str(replayed).lower()
                return _response(outcome.response)

    result = frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )
    if replayed and frappe.local.response.http_status_code == 201:
        frappe.local.response.http_status_code = 200
    return result


def _query_context(
    request_fields: dict[str, Any],
    *,
    allowed_fields: frozenset[str],
) -> tuple[str, _Repository, UUID]:
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ItemPublishUnavailable()
    reject_unexpected_request_fields(allowed_fields, request_fields)
    return request_id, repository, project_id


def _command_context(
    request_fields: dict[str, Any],
) -> tuple[str, str, _Repository, UUID]:
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()
    request_id = _request_id()
    repository = _new_repository(principal, request_id)
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise ItemPublishUnavailable()
    reject_unexpected_request_fields(_CREATE_FIELDS, request_fields)
    require_request_fields(_CREATE_FIELDS, request_fields)
    return (
        request_id,
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Item publish request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        profile_resolver=_configured_profile,
    )


def _configured_profile(tenant_id: str, project_id: UUID) -> object | None:
    resolver = _single_hook(_PROFILE_RESOLVER_HOOK)
    return None if resolver is None else resolver(tenant_id, str(project_id))


def _single_hook(name: str) -> Callable[..., Any] | None:
    hooks = frappe.get_hooks(name)
    values = [hooks] if isinstance(hooks, str) else list(hooks or ())
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        raise RuntimeError("The Item execution profile resolver is ambiguous.")
    resolver = frappe.get_attr(values[0])
    if not callable(resolver):
        raise RuntimeError("The Item execution profile resolver is invalid.")
    return resolver


def _enqueue_after_commit(outbox_event_id: UUID) -> None:
    frappe.enqueue(
        "npi_integration.item_publish.worker.process_outbox_message",
        queue="short",
        enqueue_after_commit=False,
        deduplicate=True,
        job_id=f"item-publish-{outbox_event_id}",
        outbox_event_id=str(outbox_event_id),
    )


def _response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Item publish response is invalid.")
    return value


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ItemPublishUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise ItemPublishUnavailable()
    return parsed


def _request_id() -> str:
    return str(_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a canonical global ID."))
    return parsed


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or not 0 <= value <= 2_147_483_647:
        raise _field(path, _("Enter a non-negative whole number."))
    return value


def _exact_acknowledgement(value: object) -> str:
    if value != ITEM_PUBLISH_ACKNOWLEDGEMENT:
        raise _field(
            "acknowledgement",
            _("Confirm the exact released Item source and execution profile."),
        )
    return ITEM_PUBLISH_ACKNOWLEDGEMENT


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


__all__ = [
    "create_item_publish_request",
    "get_item_publish_request",
    "get_item_publish_requests",
]
