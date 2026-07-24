from __future__ import annotations

import re
from datetime import date
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import (
    NpiProblem,
    PermissionDenied,
    RequestValidationFailed,
)
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.gate_template.domain import MAX_GATE_REQUIREMENTS
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    response_request_id,
)


_FREEZE_FIELDS = frozenset({"expectedGateVersion", "gateDueDate", "requirements"})
_REQUIREMENT_ASSIGNMENT_FIELDS = frozenset(
    {"key", "ownerMemberId", "reviewerMemberIds", "dueDate"}
)
_ATTACH_FIELDS = frozenset(
    {
        "expectedGateVersion",
        "evidenceKind",
        "sourceGlobalId",
        "sourceVersion",
        "sourceHash",
    }
)
_EVIDENCE_KINDS = frozenset({"wbs_item", "file_revision"})
_CONTROLLED_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class GateUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "GATE_UNAVAILABLE",
            _("The requested Gate is unavailable."),
        )


class GateCommandOutcomeLike(Protocol):
    response: dict[str, Any]
    replayed: bool


class GateEvidenceRepositoryLike(Protocol):
    def evidence_workspace(
        self,
        project_id: UUID,
        gate_id: UUID,
    ) -> dict[str, Any] | None: ...

    def freeze_requirements(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        gate_due_date: date,
        assignments: tuple[dict[str, Any], ...],
    ) -> GateCommandOutcomeLike | None: ...

    def attach_evidence(
        self,
        project_id: UUID,
        gate_id: UUID,
        requirement_key: str,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        evidence_kind: str,
        source_global_id: UUID,
        source_version: int,
        source_hash: str,
    ) -> GateCommandOutcomeLike | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> GateEvidenceRepositoryLike:
    from npi_core.gate_evidence.frappe_repository import (
        FrappeGateEvidenceRepository,
    )

    return FrappeGateEvidenceRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_gate_evidence_workspace(
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Return the IDOR-safe frozen Gate requirements and exact evidence metadata."""
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        reject_unexpected_request_fields(frozenset(), request_fields)
        request_id = _request_id()
        repository = _repository(
            principal=authenticated_principal(actor),
            request_id=request_id,
        )
        response = repository.evidence_workspace(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
        )
        if response is None:
            raise GateUnavailable()
        success_headers["X-Request-ID"] = request_id
        return _response_dict(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def freeze_gate_requirements(
    expectedGateVersion: Any = None,
    gateDueDate: Any = None,
    requirements: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Freeze explicit Project member assignments on one configured Gate."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _FREEZE_FIELDS,
            request_fields,
        )
        outcome = repository.freeze_requirements(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            idempotency_key=idempotency_key,
            expected_gate_version=_positive_integer(
                expectedGateVersion,
                "expectedGateVersion",
            ),
            gate_due_date=_date_value(gateDueDate, "gateDueDate"),
            assignments=_requirement_assignments(requirements),
        )
        return _command_response(
            outcome,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def attach_gate_evidence(
    expectedGateVersion: Any = None,
    evidenceKind: Any = None,
    sourceGlobalId: Any = None,
    sourceVersion: Any = None,
    sourceHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Append one exact evidence reference without accepting mutable URLs."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _ATTACH_FIELDS,
            request_fields,
        )
        outcome = repository.attach_evidence(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            _route_key("requirement_key", "requirementKey"),
            idempotency_key=idempotency_key,
            expected_gate_version=_positive_integer(
                expectedGateVersion,
                "expectedGateVersion",
            ),
            evidence_kind=_enum_text(
                evidenceKind,
                "evidenceKind",
                _EVIDENCE_KINDS,
            ),
            source_global_id=_uuid_value(
                sourceGlobalId,
                "sourceGlobalId",
            ),
            source_version=_positive_integer(
                sourceVersion,
                "sourceVersion",
            ),
            source_hash=_hash_value(sourceHash, "sourceHash"),
        )
        return _command_response(
            outcome,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=success_headers,
    )


def _command_context(
    allowed_fields: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, GateEvidenceRepositoryLike]:
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    reject_unexpected_request_fields(allowed_fields, request_fields)
    request_id = _request_id()
    idempotency_key = actor_idempotency_key_hash(
        actor,
        frappe.get_request_header("Idempotency-Key"),
    )
    return (
        request_id,
        idempotency_key,
        _repository(principal=principal, request_id=request_id),
    )


def _repository(
    *,
    principal: Principal,
    request_id: str,
) -> GateEvidenceRepositoryLike:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Gate evidence request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _command_response_headers() -> dict[str, str]:
    return {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }


def _command_response(
    outcome: GateCommandOutcomeLike | None,
    *,
    request_id: str,
    success_headers: dict[str, str],
) -> dict[str, Any]:
    if outcome is None:
        raise GateUnavailable()
    if type(outcome.replayed) is not bool:
        raise RuntimeError("The Gate evidence command replay result is invalid.")
    success_headers["X-Request-ID"] = request_id
    success_headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
    return _response_dict(outcome.response)


def _response_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Gate evidence response is invalid.")
    return value


def _request_id() -> str:
    return str(
        _uuid_value(
            frappe.get_request_header("X-Request-ID"),
            "requestId",
        )
    )


def _route_value(name: str) -> object:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    return route_params.get(name) if hasattr(route_params, "get") else None


def _route_uuid(name: str, path: str) -> UUID:
    return _uuid_value(_route_value(name), path)


def _route_key(name: str, path: str) -> str:
    return _pattern_text(
        _route_value(name),
        path,
        pattern=_CONTROLLED_KEY_PATTERN,
    )


def _requirement_assignments(
    value: object,
) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "requirements",
        minimum_items=1,
        maximum_items=MAX_GATE_REQUIREMENTS,
    )
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        path = f"requirements[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_REQUIREMENT_ASSIGNMENT_FIELDS,
            required=_REQUIREMENT_ASSIGNMENT_FIELDS,
        )
        reviewers = _uuid_array(
            item["reviewerMemberIds"],
            f"{path}.reviewerMemberIds",
            minimum_items=1,
            maximum_items=50,
        )
        result.append(
            {
                "key": _pattern_text(
                    item["key"],
                    f"{path}.key",
                    pattern=_CONTROLLED_KEY_PATTERN,
                ),
                "owner_member_id": _uuid_value(
                    item["ownerMemberId"],
                    f"{path}.ownerMemberId",
                ),
                "reviewer_member_ids": reviewers,
                "due_date": _date_value(
                    item["dueDate"],
                    f"{path}.dueDate",
                ),
            }
        )
    normalized_keys = [str(item["key"]).casefold() for item in result]
    if len(normalized_keys) != len(set(normalized_keys)):
        raise _field_problem(
            "requirements",
            _("Requirement assignment keys must be unique."),
        )
    return tuple(result)


def _object_array(
    value: object,
    path: str,
    *,
    minimum_items: int = 0,
    maximum_items: int,
) -> tuple[dict[str, Any], ...]:
    if (
        not isinstance(value, list)
        or len(value) < minimum_items
        or len(value) > maximum_items
        or any(not isinstance(item, dict) for item in value)
    ):
        raise _field_problem(path, _("Enter a valid list."))
    return tuple(value)


def _strict_object(
    value: object,
    path: str,
    *,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _field_problem(path, _("Enter a valid value."))
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise RequestValidationFailed(
            [
                {
                    "path": f"{path}.{field}",
                    "message": _("This field is not allowed."),
                }
                for field in unexpected
            ]
        )
    missing = sorted(required - set(value))
    if missing:
        raise RequestValidationFailed(
            [
                {
                    "path": f"{path}.{field}",
                    "message": _("This field is required."),
                }
                for field in missing
            ]
        )
    return value


def _uuid_array(
    value: object,
    path: str,
    *,
    minimum_items: int,
    maximum_items: int,
) -> tuple[UUID, ...]:
    if (
        not isinstance(value, list)
        or len(value) < minimum_items
        or len(value) > maximum_items
    ):
        raise _field_problem(path, _("Enter a valid list."))
    result = tuple(
        _uuid_value(item, f"{path}[{index}]") for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        raise _field_problem(path, _("Values must be unique."))
    return result


def _uuid_value(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise _field_problem(path, _("Enter a valid global ID."))
    if str(parsed) != value.casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _date_value(value: object, path: str) -> date:
    if not isinstance(value, str) or _DATE_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid date."))
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise _field_problem(path, _("Enter a valid date."))
    if parsed.isoformat() != value:
        raise _field_problem(path, _("Enter a valid date."))
    return parsed


def _pattern_text(
    value: object,
    path: str,
    *,
    pattern: re.Pattern[str],
) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid value."))
    return value


def _enum_text(
    value: object,
    path: str,
    allowed: frozenset[str],
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _field_problem(path, _("Select a supported value."))
    return value


def _hash_value(value: object, path: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
