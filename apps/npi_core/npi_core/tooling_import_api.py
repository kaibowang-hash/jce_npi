from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    require_tooling_import_routes_enabled,
    response_request_id,
)
from npi_core.tooling.domain import ToolingUnavailable
from npi_core.tooling.import_repository import FrappeToolingImportRepository


_HASH = re.compile(r"^[a-f0-9]{64}$")
_CONTENT_HASH = re.compile(r"^[a-f0-9]{32,128}$")
_BATCH_FIELDS = frozenset(
    {
        "customerScopeId",
        "fileRevisionGlobalId",
        "fileOptimisticVersion",
        "frappeContentHash",
        "sha256",
    }
)
_MAPPING_FIELDS = frozenset(
    {"inspectionGlobalId", "inspectionSnapshotHash", "templateKey", "reason"}
)
_PREVIEW_FIELDS = frozenset(
    {
        "inspectionGlobalId",
        "inspectionSnapshotHash",
        "mappingGlobalId",
        "mappingSnapshotHash",
    }
)
_CONFIRMATION_FIELDS = frozenset(
    {"expectedVersion", "expectedSnapshotHash", "confirmations"}
)
_CONFIRMATION_ITEM_FIELDS = frozenset(
    {
        "kind",
        "worksheetName",
        "sourceRow",
        "anchorKey",
        "selectedTargetObject",
        "selectedTargetGlobalId",
        "selectedTargetSnapshotHash",
        "reason",
    }
)


class _Outcome(Protocol):
    response: dict[str, Any]
    replayed: bool


class _Repository(Protocol):
    def authorize_scope(
        self,
        project_id: UUID,
        tooling_master_id: UUID | None = None,
        *,
        administer: bool = False,
    ) -> bool: ...

    def tooling_import_batches(self, project_id: UUID) -> dict[str, object] | None: ...

    def tooling_import_batch_detail(
        self, project_id: UUID, batch_id: UUID
    ) -> dict[str, object] | None: ...

    def create_tooling_import_batch(self, project_id: UUID, **values: Any) -> _Outcome | None: ...

    def create_tooling_import_inspection(
        self, project_id: UUID, batch_id: UUID, **values: Any
    ) -> _Outcome | None: ...

    def create_tooling_import_mapping_proposal(
        self, project_id: UUID, batch_id: UUID, **values: Any
    ) -> _Outcome | None: ...

    def create_tooling_import_preview(
        self, project_id: UUID, batch_id: UUID, **values: Any
    ) -> _Outcome | None: ...

    def create_tooling_import_confirmation(
        self, project_id: UUID, batch_id: UUID, preview_id: UUID, **values: Any
    ) -> _Outcome | None: ...


_repository_factory = FrappeToolingImportRepository


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_import_batches(**request_fields: Any) -> dict[str, Any] | None:
    return _query(
        request_fields,
        lambda repository, project_id: repository.tooling_import_batches(project_id),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_import_batch(**request_fields: Any) -> dict[str, Any] | None:
    return _query(
        request_fields,
        lambda repository, project_id: repository.tooling_import_batch_detail(
            project_id,
            _opaque_route_uuid("batch_id"),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_import_batch(
    customerScopeId: Any = None,
    fileRevisionGlobalId: Any = None,
    fileOptimisticVersion: Any = None,
    frappeContentHash: Any = None,
    sha256: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        allowed=_BATCH_FIELDS,
        required=_BATCH_FIELDS,
        request_fields=request_fields,
        values=lambda: {
            "customer_scope_id": _text(customerScopeId, "customerScopeId", 128),
            "file_revision_id": _uuid(fileRevisionGlobalId, "fileRevisionGlobalId"),
            "file_optimistic_version": _positive(
                fileOptimisticVersion, "fileOptimisticVersion"
            ),
            "frappe_content_hash": _hash(
                frappeContentHash, "frappeContentHash", _CONTENT_HASH
            ),
            "sha256": _hash(sha256, "sha256", _HASH),
        },
        operation=lambda repository, project_id, parsed: (
            repository.create_tooling_import_batch(project_id, **parsed)
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_import_inspection(
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        allowed=frozenset(),
        required=frozenset(),
        request_fields=request_fields,
        values=lambda: {},
        operation=lambda repository, project_id, parsed: (
            repository.create_tooling_import_inspection(
                project_id,
                _opaque_route_uuid("batch_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_import_mapping_proposal(
    inspectionGlobalId: Any = None,
    inspectionSnapshotHash: Any = None,
    templateKey: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        allowed=_MAPPING_FIELDS,
        required=_MAPPING_FIELDS,
        request_fields=request_fields,
        values=lambda: {
            "inspection_id": _uuid(inspectionGlobalId, "inspectionGlobalId"),
            "inspection_snapshot_hash": _hash(
                inspectionSnapshotHash, "inspectionSnapshotHash", _HASH
            ),
            "template_key": _stable_code(templateKey, "templateKey"),
            "reason": _text(reason, "reason", 1_000),
        },
        operation=lambda repository, project_id, parsed: (
            repository.create_tooling_import_mapping_proposal(
                project_id,
                _opaque_route_uuid("batch_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_import_preview(
    inspectionGlobalId: Any = None,
    inspectionSnapshotHash: Any = None,
    mappingGlobalId: Any = None,
    mappingSnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        allowed=_PREVIEW_FIELDS,
        required=_PREVIEW_FIELDS,
        request_fields=request_fields,
        values=lambda: {
            "inspection_id": _uuid(inspectionGlobalId, "inspectionGlobalId"),
            "inspection_snapshot_hash": _hash(
                inspectionSnapshotHash, "inspectionSnapshotHash", _HASH
            ),
            "mapping_id": _uuid(mappingGlobalId, "mappingGlobalId"),
            "mapping_snapshot_hash": _hash(
                mappingSnapshotHash, "mappingSnapshotHash", _HASH
            ),
        },
        operation=lambda repository, project_id, parsed: (
            repository.create_tooling_import_preview(
                project_id,
                _opaque_route_uuid("batch_id"),
                **parsed,
            )
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_import_confirmation(
    expectedVersion: Any = None,
    expectedSnapshotHash: Any = None,
    confirmations: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        allowed=_CONFIRMATION_FIELDS,
        required=_CONFIRMATION_FIELDS,
        request_fields=request_fields,
        values=lambda: {
            "expected_version": _positive(expectedVersion, "expectedVersion"),
            "expected_snapshot_hash": _hash(
                expectedSnapshotHash, "expectedSnapshotHash", _HASH
            ),
            "confirmations": _confirmations(confirmations),
        },
        operation=lambda repository, project_id, parsed: (
            repository.create_tooling_import_confirmation(
                project_id,
                _opaque_route_uuid("batch_id"),
                _opaque_route_uuid("preview_id"),
                **parsed,
            )
        ),
    )


def _query(request_fields: dict[str, Any], operation) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_tooling_import_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        if not repository.authorize_scope(project_id):
            raise ToolingUnavailable()
        reject_unexpected_request_fields(frozenset(), request_fields)
        outcome = operation(repository, project_id)
        if outcome is None:
            raise ToolingUnavailable()
        if not isinstance(outcome, dict):
            raise RuntimeError("The Tooling import response is invalid.")
        headers["X-Request-ID"] = request_id
        return outcome

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _command(
    *,
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values,
    operation,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        require_tooling_import_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        if principal.is_external or "System Manager" not in principal.roles:
            raise PermissionDenied()
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        if not repository.authorize_scope(project_id, administer=True):
            raise ToolingUnavailable()
        reject_unexpected_request_fields(allowed, request_fields)
        require_request_fields(required, request_fields)
        parsed = values()
        parsed["idempotency_key_hash"] = actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        )
        outcome = operation(repository, project_id, parsed)
        if outcome is None:
            raise ToolingUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The Tooling import replay result is invalid.")
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return outcome.response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Tooling import request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ToolingUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise ToolingUnavailable()
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


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > 2_147_483_647:
        raise _field(path, _("Enter a positive whole number."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > maximum
    ):
        raise _field(path, _("Enter a bounded text value."))
    return value


def _stable_code(value: object, path: str) -> str:
    text = _text(value, path, 128)
    if re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", text) is None:
        raise _field(path, _("Enter a valid stable code."))
    return text


def _hash(value: object, path: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise _field(path, _("Enter a valid lowercase hash."))
    return value


def _confirmations(value: object) -> tuple[dict[str, object], ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not 1 <= len(value) <= 100
        or any(not isinstance(item, Mapping) for item in value)
    ):
        raise _field("confirmations", _("Enter a valid bounded list."))
    result = []
    for index, candidate in enumerate(value):
        item = candidate
        path = f"confirmations[{index}]"
        allowed = set(_CONFIRMATION_ITEM_FIELDS)
        required = allowed - {"anchorKey"}
        if not required.issubset(item) or not set(item).issubset(allowed):
            raise _field(path, _("Select a supported value."))
        kind = str(item.get("kind"))
        target_object = str(item.get("selectedTargetObject"))
        if kind not in {"image_anchor", "relationship"}:
            raise _field(f"{path}.kind", _("Select a supported value."))
        if target_object not in {"part_revision", "tooling_master"}:
            raise _field(
                f"{path}.selectedTargetObject", _("Select a supported value.")
            )
        anchor_key = (
            _stable_code(item.get("anchorKey"), f"{path}.anchorKey")
            if "anchorKey" in item
            else None
        )
        if (kind == "image_anchor") != (anchor_key is not None):
            raise _field(f"{path}.anchorKey", _("Select a supported value."))
        result.append(
            {
                "kind": kind,
                "worksheetName": _text(
                    item.get("worksheetName"), f"{path}.worksheetName", 255
                ),
                "sourceRow": _positive(item.get("sourceRow"), f"{path}.sourceRow"),
                "anchorKey": anchor_key,
                "selectedTargetObject": target_object,
                "selectedTargetGlobalId": str(
                    _uuid(
                        item.get("selectedTargetGlobalId"),
                        f"{path}.selectedTargetGlobalId",
                    )
                ),
                "selectedTargetSnapshotHash": _hash(
                    item.get("selectedTargetSnapshotHash"),
                    f"{path}.selectedTargetSnapshotHash",
                    _HASH,
                ),
                "reason": _text(item.get("reason"), f"{path}.reason", 1_000),
            }
        )
    identities = {
        (item["kind"], item["worksheetName"], item["sourceRow"], item["anchorKey"])
        for item in result
    }
    if len(identities) != len(result):
        raise _field("confirmations", _("Enter a valid bounded list."))
    return tuple(result)


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
