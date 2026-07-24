from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.gate_evidence_api import GateUnavailable
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    response_request_id,
)


_START_REVIEW_FIELDS = frozenset(
    {
        "expectedGateVersion",
        "policyGlobalId",
        "policyVersion",
        "policySnapshotHash",
        "bindings",
    }
)
_SUBMIT_REVIEW_FIELDS = frozenset(
    {
        "expectedCycleVersion",
        "expectedInputHash",
        "stepKey",
        "outcome",
        "opinion",
    }
)
_REQUEST_EXCEPTION_FIELDS = frozenset(
    {
        "expectedCycleVersion",
        "expectedInputHash",
        "requirementGlobalId",
        "requirementKey",
        "kind",
        "reason",
        "risk",
        "expiresAt",
        "closureActionGlobalId",
    }
)
_DECIDE_EXCEPTION_FIELDS = frozenset(
    {
        "expectedCycleVersion",
        "expectedExceptionVersion",
        "expectedInputHash",
        "outcome",
        "opinion",
    }
)
_DECIDE_GATE_FIELDS = frozenset(
    {
        "expectedGateVersion",
        "expectedCycleVersion",
        "expectedInputHash",
        "outcome",
    }
)
_REOPEN_GATE_FIELDS = frozenset(
    {
        "expectedGateVersion",
        "expectedCycleVersion",
        "expectedInputHash",
        "reason",
        "policyGlobalId",
        "policyVersion",
        "policySnapshotHash",
        "bindings",
    }
)
_BINDING_FIELDS = frozenset({"slot", "memberGlobalId"})

_CONTROLLED_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_UTC_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_REVIEW_OUTCOMES = frozenset({"approved", "rejected"})
_EXCEPTION_OUTCOMES = frozenset({"approved", "rejected"})
_DECISION_OUTCOMES = frozenset({"pass", "conditional_pass", "reject"})
_COMMAND_RECEIPT_OPERATIONS = frozenset(
    {
        "gate.review.start",
        "gate.review.submit",
        "gate.review.exception.request",
        "gate.review.exception.decide",
        "gate.review.decide",
        "gate.review.reopen",
    }
)
_TRANSPORT_ROLE = "NPI API User"
_MAX_BINDINGS = 64
_MAX_OPINION_LENGTH = 4000
_MAX_EXCEPTION_TEXT_LENGTH = 4000


class GateReviewCommandOutcomeLike(Protocol):
    response: dict[str, Any]
    replayed: bool


class GateReviewRepositoryLike(Protocol):
    def review_workspace(
        self,
        project_id: UUID,
        gate_id: UUID,
    ) -> dict[str, Any] | None: ...

    def command_receipt(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        operation: str,
        actor_key_hash: str,
    ) -> dict[str, object] | None: ...

    def start_review(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        bindings: tuple[dict[str, Any], ...],
    ) -> GateReviewCommandOutcomeLike | None: ...

    def submit_review(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        *,
        idempotency_key: str,
        expected_cycle_version: int,
        expected_input_hash: str,
        step_key: str,
        outcome: str,
        opinion: str,
    ) -> GateReviewCommandOutcomeLike | None: ...

    def request_exception(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        *,
        idempotency_key: str,
        expected_cycle_version: int,
        expected_input_hash: str,
        requirement_global_id: UUID,
        requirement_key: str,
        kind: str,
        reason: str,
        risk: str,
        expires_at: datetime,
        closure_action_global_id: UUID,
    ) -> GateReviewCommandOutcomeLike | None: ...

    def decide_exception(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        exception_id: UUID,
        *,
        idempotency_key: str,
        expected_cycle_version: int,
        expected_exception_version: int,
        expected_input_hash: str,
        outcome: str,
        opinion: str,
    ) -> GateReviewCommandOutcomeLike | None: ...

    def decide_gate(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        expected_cycle_version: int,
        expected_input_hash: str,
        outcome: str,
    ) -> GateReviewCommandOutcomeLike | None: ...

    def reopen_gate(
        self,
        project_id: UUID,
        gate_id: UUID,
        *,
        idempotency_key: str,
        expected_gate_version: int,
        expected_cycle_version: int,
        expected_input_hash: str,
        reason: str,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        bindings: tuple[dict[str, Any], ...],
    ) -> GateReviewCommandOutcomeLike | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> GateReviewRepositoryLike:
    from npi_core.gate_review.frappe_repository import FrappeGateReviewRepository

    return FrappeGateReviewRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_gate_review(**request_fields: Any) -> dict[str, Any] | None:
    """Return one IDOR-safe Gate review workspace built by the repository."""
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        reject_unexpected_request_fields(frozenset(), request_fields)
        request_id = _request_id()
        repository = _repository(
            principal=authenticated_principal(actor),
            request_id=request_id,
        )
        response = repository.review_workspace(
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


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_gate_review_command_receipt(
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Reconcile one exact actor-bound command without replaying its payload."""
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        reject_unexpected_request_fields(frozenset(), request_fields)
        principal = authenticated_principal(actor)
        if (
            principal.is_external
            or not principal.roles.intersection({_TRANSPORT_ROLE, "System Manager"})
        ):
            raise PermissionDenied()
        operation = _route_value("operation")
        if (
            not isinstance(operation, str)
            or operation not in _COMMAND_RECEIPT_OPERATIONS
        ):
            raise GateUnavailable()
        request_id = _request_id()
        repository = _repository(principal=principal, request_id=request_id)
        response = repository.command_receipt(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            operation=operation,
            actor_key_hash=actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
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
def start_gate_review(
    expectedGateVersion: Any = None,
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    bindings: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Start a cycle from an exact policy under the management-only boundary."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _START_REVIEW_FIELDS,
            request_fields,
            system_manager_only=True,
        )
        outcome = repository.start_review(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            idempotency_key=idempotency_key,
            expected_gate_version=_positive_integer(
                expectedGateVersion,
                "expectedGateVersion",
            ),
            policy_global_id=_uuid_value(policyGlobalId, "policyGlobalId"),
            policy_version=_positive_integer(policyVersion, "policyVersion"),
            policy_snapshot_hash=_hash_value(
                policySnapshotHash,
                "policySnapshotHash",
            ),
            bindings=_bindings(bindings),
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


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_gate_review(
    expectedCycleVersion: Any = None,
    expectedInputHash: Any = None,
    stepKey: Any = None,
    outcome: Any = None,
    opinion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Append one review after transport admission; repository proves authority."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _SUBMIT_REVIEW_FIELDS,
            request_fields,
        )
        result = repository.submit_review(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            _route_uuid("cycle_id", "cycleId"),
            idempotency_key=idempotency_key,
            expected_cycle_version=_positive_integer(
                expectedCycleVersion,
                "expectedCycleVersion",
            ),
            expected_input_hash=_hash_value(
                expectedInputHash,
                "expectedInputHash",
            ),
            step_key=_key_value(stepKey, "stepKey"),
            outcome=_enum_value(outcome, "outcome", _REVIEW_OUTCOMES),
            opinion=_text_value(
                opinion,
                "opinion",
                maximum_length=_MAX_OPINION_LENGTH,
            ),
        )
        return _command_response(
            result,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def request_gate_review_exception(
    expectedCycleVersion: Any = None,
    expectedInputHash: Any = None,
    requirementGlobalId: Any = None,
    requirementKey: Any = None,
    kind: Any = None,
    reason: Any = None,
    risk: Any = None,
    expiresAt: Any = None,
    closureActionGlobalId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Request one policy-governed exception without accepting authority claims."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _REQUEST_EXCEPTION_FIELDS,
            request_fields,
        )
        result = repository.request_exception(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            _route_uuid("cycle_id", "cycleId"),
            idempotency_key=idempotency_key,
            expected_cycle_version=_positive_integer(
                expectedCycleVersion,
                "expectedCycleVersion",
            ),
            expected_input_hash=_hash_value(
                expectedInputHash,
                "expectedInputHash",
            ),
            requirement_global_id=_uuid_value(
                requirementGlobalId,
                "requirementGlobalId",
            ),
            requirement_key=_key_value(requirementKey, "requirementKey"),
            kind=_key_value(kind, "kind"),
            reason=_text_value(
                reason,
                "reason",
                maximum_length=_MAX_EXCEPTION_TEXT_LENGTH,
            ),
            risk=_text_value(
                risk,
                "risk",
                maximum_length=_MAX_EXCEPTION_TEXT_LENGTH,
            ),
            expires_at=_utc_timestamp(expiresAt, "expiresAt"),
            closure_action_global_id=_uuid_value(
                closureActionGlobalId,
                "closureActionGlobalId",
            ),
        )
        return _command_response(
            result,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def decide_gate_review_exception(
    expectedCycleVersion: Any = None,
    expectedExceptionVersion: Any = None,
    expectedInputHash: Any = None,
    outcome: Any = None,
    opinion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Append the exact policy-authorized exception decision."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _DECIDE_EXCEPTION_FIELDS,
            request_fields,
        )
        result = repository.decide_exception(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            _route_uuid("cycle_id", "cycleId"),
            _route_uuid("exception_id", "exceptionId"),
            idempotency_key=idempotency_key,
            expected_cycle_version=_positive_integer(
                expectedCycleVersion,
                "expectedCycleVersion",
            ),
            expected_exception_version=_positive_integer(
                expectedExceptionVersion,
                "expectedExceptionVersion",
            ),
            expected_input_hash=_hash_value(
                expectedInputHash,
                "expectedInputHash",
            ),
            outcome=_enum_value(outcome, "outcome", _EXCEPTION_OUTCOMES),
            opinion=_text_value(
                opinion,
                "opinion",
                maximum_length=_MAX_OPINION_LENGTH,
            ),
        )
        return _command_response(
            result,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def decide_gate(
    expectedGateVersion: Any = None,
    expectedCycleVersion: Any = None,
    expectedInputHash: Any = None,
    outcome: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Create a server-built immutable Gate decision snapshot."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _DECIDE_GATE_FIELDS,
            request_fields,
        )
        result = repository.decide_gate(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            idempotency_key=idempotency_key,
            expected_gate_version=_positive_integer(
                expectedGateVersion,
                "expectedGateVersion",
            ),
            expected_cycle_version=_positive_integer(
                expectedCycleVersion,
                "expectedCycleVersion",
            ),
            expected_input_hash=_hash_value(
                expectedInputHash,
                "expectedInputHash",
            ),
            outcome=_enum_value(outcome, "outcome", _DECISION_OUTCOMES),
        )
        return _command_response(
            result,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reopen_gate(
    expectedGateVersion: Any = None,
    expectedCycleVersion: Any = None,
    expectedInputHash: Any = None,
    reason: Any = None,
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    bindings: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Create a new cycle while preserving the immutable prior decision."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _REOPEN_GATE_FIELDS,
            request_fields,
        )
        result = repository.reopen_gate(
            _route_uuid("project_id", "projectId"),
            _route_uuid("gate_id", "gateId"),
            idempotency_key=idempotency_key,
            expected_gate_version=_positive_integer(
                expectedGateVersion,
                "expectedGateVersion",
            ),
            expected_cycle_version=_positive_integer(
                expectedCycleVersion,
                "expectedCycleVersion",
            ),
            expected_input_hash=_hash_value(
                expectedInputHash,
                "expectedInputHash",
            ),
            reason=_text_value(
                reason,
                "reason",
                maximum_length=_MAX_EXCEPTION_TEXT_LENGTH,
            ),
            policy_global_id=_uuid_value(policyGlobalId, "policyGlobalId"),
            policy_version=_positive_integer(policyVersion, "policyVersion"),
            policy_snapshot_hash=_hash_value(
                policySnapshotHash,
                "policySnapshotHash",
            ),
            bindings=_bindings(bindings),
        )
        return _command_response(
            result,
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
    *,
    system_manager_only: bool = False,
) -> tuple[str, str, GateReviewRepositoryLike]:
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    required_role = "System Manager" if system_manager_only else _TRANSPORT_ROLE
    if principal.is_external or required_role not in principal.roles:
        raise PermissionDenied()
    # The transport role admits the request to this command boundary only.
    # Exact frozen slot/member authority remains a repository/domain decision.
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
) -> GateReviewRepositoryLike:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Gate review request has no active trace identity.")
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
    outcome: GateReviewCommandOutcomeLike | None,
    *,
    request_id: str,
    success_headers: dict[str, str],
) -> dict[str, Any]:
    if outcome is None:
        raise GateUnavailable()
    if type(outcome.replayed) is not bool:
        raise RuntimeError("The Gate review command replay result is invalid.")
    success_headers["X-Request-ID"] = request_id
    success_headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
    return _response_dict(outcome.response)


def _response_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Gate review response is invalid.")
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


def _bindings(value: object) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "bindings",
        minimum_items=1,
        maximum_items=_MAX_BINDINGS,
    )
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        path = f"bindings[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_BINDING_FIELDS,
            required=_BINDING_FIELDS,
        )
        result.append(
            {
                "slot": _key_value(item["slot"], f"{path}.slot"),
                "member_global_id": _uuid_value(
                    item["memberGlobalId"],
                    f"{path}.memberGlobalId",
                ),
            }
        )
    slots = [str(item["slot"]) for item in result]
    if len(slots) != len(set(slots)):
        raise _field_problem("bindings", _("Values must be unique."))
    return tuple(result)


def _object_array(
    value: object,
    path: str,
    *,
    minimum_items: int,
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


def _uuid_value(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise _field_problem(path, _("Enter a valid global ID."))
    if parsed.int == 0 or str(parsed) != value:
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _key_value(value: object, path: str) -> str:
    return _pattern_text(
        value,
        path,
        pattern=_CONTROLLED_KEY_PATTERN,
    )


def _pattern_text(
    value: object,
    path: str,
    *,
    pattern: re.Pattern[str],
) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid value."))
    return value


def _enum_value(
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


def _utc_timestamp(value: object, path: str) -> datetime:
    if (
        not isinstance(value, str)
        or _UTC_DATETIME_PATTERN.fullmatch(value) is None
    ):
        raise _field_problem(path, _("Enter a valid date and time."))
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise _field_problem(path, _("Enter a valid date and time."))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise _field_problem(path, _("Enter a valid date and time."))
    return parsed.astimezone(UTC)


def _text_value(value: object, path: str, *, maximum_length: int) -> str:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid value."))
    normalized = value.strip()
    if not normalized or len(normalized) > maximum_length:
        raise _field_problem(path, _("Enter a valid value."))
    return normalized


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
