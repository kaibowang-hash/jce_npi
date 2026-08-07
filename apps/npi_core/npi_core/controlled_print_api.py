from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import BinaryPayload, frappe_binary_call, frappe_domain_call
from npi_core.controlled_print.domain import (
    ControlledPrintUnavailable,
    PrintCopyState,
    PrintDeliveryMode,
)
from npi_core.controlled_print.service import ControlledPrintCapabilityService
from npi_core.controlled_print.source_registry import (
    ControlledPrintSourceRegistry,
    default_controlled_print_source_registry,
)
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_controlled_print_routes_enabled,
    require_request_fields,
    response_request_id,
)


_CAPABILITY_FIELDS = frozenset(
    {"sourceKind", "sourceGlobalId", "sourceVersion", "language"}
)
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_LANGUAGES = frozenset({"en", "zh", "zh-TW"})


class _Repository(Protocol):
    def authorize_project(self, project_global_id: UUID): ...
    def published_mapping_candidates(self, context, *, at: datetime): ...
    def create_snapshot(self, project_global_id: UUID, **values: Any): ...
    def snapshot_detail(
        self,
        project_global_id: UUID,
        snapshot_global_id: UUID,
    ): ...
    def content(
        self,
        project_global_id: UUID,
        snapshot_global_id: UUID,
    ): ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_core.controlled_print.frappe_repository import (
        FrappeControlledPrintRepository,
    )

    return FrappeControlledPrintRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _source_registry_factory() -> ControlledPrintSourceRegistry:
    return default_controlled_print_source_registry()


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_controlled_print_capability(
    sourceKind: Any = None,
    sourceGlobalId: Any = None,
    sourceVersion: Any = None,
    language: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_controlled_print_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_role(principal)
        request_id = _request_id()
        trace_id = current_trace_id.get()
        if trace_id is None:
            raise RuntimeError(
                "The controlled print request has no active trace identity."
            )
        reject_unexpected_request_fields(_CAPABILITY_FIELDS, request_fields)
        require_request_fields(_CAPABILITY_FIELDS, request_fields)
        repository = _repository_factory(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        service = ControlledPrintCapabilityService(
            repository=repository,
            source_registry=_source_registry_factory(),
            actor_user_id=actor,
        )
        response = service.capability(
            project_global_id=_opaque_project_uuid(),
            source_object_type=_key(sourceKind, "sourceKind"),
            source_global_id=_uuid(sourceGlobalId, "sourceGlobalId"),
            expected_source_version=_query_positive(sourceVersion, "sourceVersion"),
            language=_language(language),
            at=datetime.now(UTC),
        )
        if response is None:
            raise ControlledPrintUnavailable()
        _validate_capability_response(response)
        headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_controlled_print_snapshot(
    sourceKind: Any = None,
    sourceGlobalId: Any = None,
    sourceVersion: Any = None,
    language: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        require_controlled_print_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        _require_role(principal)
        request_id, repository = _new_repository(principal)
        project_id = _opaque_project_uuid()
        if repository.authorize_project(project_id) is None:
            raise ControlledPrintUnavailable()
        reject_unexpected_request_fields(_CAPABILITY_FIELDS, request_fields)
        require_request_fields(_CAPABILITY_FIELDS, request_fields)
        outcome = repository.create_snapshot(
            project_id,
            source_object_type=_key(sourceKind, "sourceKind"),
            source_global_id=_uuid(sourceGlobalId, "sourceGlobalId"),
            expected_source_version=_positive(sourceVersion, "sourceVersion"),
            language=_language(language),
            idempotency_key_hash=actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
        )
        if outcome is None:
            raise ControlledPrintUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The controlled print replay response is invalid.")
        response = _snapshot_response(outcome.response)
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_controlled_print_snapshot(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_controlled_print_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_role(principal)
        request_id, repository = _new_repository(principal)
        reject_unexpected_request_fields(frozenset(), request_fields)
        response = repository.snapshot_detail(
            _opaque_project_uuid(),
            _opaque_route_uuid("controlled_print_id"),
        )
        if response is None:
            raise ControlledPrintUnavailable()
        headers["X-Request-ID"] = request_id
        return _snapshot_response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def download_controlled_print_output(**request_fields: Any) -> None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> BinaryPayload:
        require_controlled_print_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_role(principal)
        request_id, repository = _new_repository(principal)
        reject_unexpected_request_fields(frozenset(), request_fields)
        outcome = repository.content(
            _opaque_project_uuid(),
            _opaque_route_uuid("controlled_print_id"),
        )
        if outcome is None:
            raise ControlledPrintUnavailable()
        headers["X-Request-ID"] = request_id
        headers["X-NPI-Snapshot-Hash"] = _sha256(
            outcome.snapshot_hash,
            "snapshotHash",
        )
        headers["X-NPI-Output-Hash"] = _sha256(
            outcome.output_hash,
            "outputHash",
        )
        return BinaryPayload(
            content=outcome.content,
            file_name=outcome.file_name,
            mime_type=outcome.mime_type,
            disposition="attachment",
            headers={
                "Content-Disposition": _content_disposition(outcome.file_name),
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "Referrer-Policy": "no-referrer",
            },
        )

    frappe_binary_call(handle, response_headers=headers)


def _new_repository(principal: Principal) -> tuple[str, _Repository]:
    request_id = _request_id()
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The controlled print request has no active trace identity.")
    return request_id, _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _require_role(principal: Principal) -> None:
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ControlledPrintUnavailable() from error
    if parsed.version != 4 or str(parsed) != str(value).casefold():
        raise ControlledPrintUnavailable()
    return parsed


def _opaque_project_uuid() -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get("project_id") if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ControlledPrintUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise ControlledPrintUnavailable()
    return parsed


def _request_id() -> str:
    return str(
        _canonical_uuid(
            frappe.get_request_header("X-Request-ID"),
            "requestId",
        )
    )


def _canonical_uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a canonical global ID."))
    return parsed


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if parsed.version != 4 or str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a canonical global ID."))
    return parsed


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field(path, _("Enter a positive whole number."))
    return value


def _query_positive(value: object, path: str) -> int:
    if type(value) is int:
        return _positive(value, path)
    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and len(value) <= 10
    ):
        parsed = int(value)
        if str(parsed) == value:
            return _positive(parsed, path)
    raise _field(path, _("Enter a positive whole number."))


def _key(value: object, path: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise _field(path, _("Enter a valid identifier."))
    return value


def _language(value: object) -> str:
    if value not in _LANGUAGES:
        raise _field("language", _("Select a supported language."))
    return str(value)


def _validate_capability_response(value: object) -> None:
    if not isinstance(value, dict):
        raise RuntimeError("The controlled print capability response is invalid.")
    if value.get("deliveryMode") not in {None, PrintDeliveryMode.CONTROLLED_PDF.value}:
        raise RuntimeError("The controlled print delivery response is invalid.")
    if value.get("copyState") not in {None, PrintCopyState.NOT_NUMBERED.value}:
        raise RuntimeError("The controlled print copy response is invalid.")


def _snapshot_response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The controlled print snapshot response is invalid.")
    required = {
        "globalId",
        "version",
        "source",
        "registry",
        "language",
        "deliveryMode",
        "copyState",
        "watermarkSource",
        "actorUserId",
        "printedAt",
        "snapshotHash",
        "verificationPayload",
        "output",
    }
    if set(value) != required or not isinstance(value.get("output"), dict):
        raise RuntimeError("The controlled print snapshot response is invalid.")
    return value


def _sha256(value: object, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise RuntimeError(f"The controlled print {path} response is invalid.")
    return value


def _content_disposition(file_name: object) -> str:
    if (
        not isinstance(file_name, str)
        or not file_name.casefold().endswith(".pdf")
        or re.fullmatch(r"[A-Za-z0-9._-]{1,140}", file_name) is None
    ):
        raise RuntimeError("The controlled print file name is invalid.")
    return f'attachment; filename="{file_name}"'


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
