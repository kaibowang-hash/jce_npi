from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.ebom.domain import (
    EngineeringBomReviewDecision,
    EngineeringBomUnavailable,
)
from npi_core.ebom.diagnostics import (
    ebom_create_server_diagnostics,
    ebom_create_server_step,
    ebom_transition_server_diagnostics,
    ebom_transition_server_step,
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
    require_engineering_bom_routes_enabled,
    require_request_fields,
    response_request_id,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_LINE_FIELDS = frozenset(
    {
        "lineKey",
        "parentLineKey",
        "engineeringItemId",
        "description",
        "quantity",
        "engineeringUom",
        "alternateForLineKey",
        "alternateGroupKey",
        "effectivityStart",
        "effectivityEnd",
        "attributes",
    }
)
_LINE_REQUIRED = frozenset(
    {"lineKey", "engineeringItemId", "description", "quantity", "engineeringUom"}
)
_CREATE_FIELDS = frozenset(
    {
        "policyGlobalId",
        "policyVersion",
        "policySnapshotHash",
        "engineeringBomKey",
        "title",
        "reason",
        "effectivityNote",
        "lines",
    }
)
_CREATE_REQUIRED = _CREATE_FIELDS - {"effectivityNote"}
_REVISE_FIELDS = frozenset(
    {
        "expectedEbomVersion",
        "predecessorRevisionId",
        "expectedPredecessorSnapshotHash",
        "policyGlobalId",
        "policyVersion",
        "policySnapshotHash",
        "reason",
        "effectivityNote",
        "lines",
    }
)
_REVISE_REQUIRED = _REVISE_FIELDS - {"effectivityNote"}
_TRANSITION_COMMON = frozenset(
    {
        "expectedEbomVersion",
        "expectedRevisionSnapshotHash",
        "expectedLifecycleVersion",
        "policyGlobalId",
        "policyVersion",
        "policySnapshotHash",
    }
)
_SUBMIT_FIELDS = _TRANSITION_COMMON | {"reason"}
_REVIEW_FIELDS = _TRANSITION_COMMON | {"decision", "reason"}
_RELEASE_FIELDS = _TRANSITION_COMMON | {"confirmed", "confirmationIntent"}


class _Outcome(Protocol):
    response: dict[str, Any]
    replayed: bool


class _Repository(Protocol):
    def authorize_scope(
        self,
        project_id: UUID,
        ebom_id: UUID | None = None,
        *,
        administer: bool = False,
    ) -> bool: ...

    def list_eboms(self, project_id: UUID) -> dict[str, Any] | None: ...
    def ebom_detail(self, project_id: UUID, ebom_id: UUID) -> dict[str, Any] | None: ...
    def create_ebom(self, project_id: UUID, **values: Any) -> _Outcome | None: ...
    def create_revision(self, project_id: UUID, ebom_id: UUID, **values: Any) -> _Outcome | None: ...
    def submit_review(self, project_id: UUID, ebom_id: UUID, revision_id: UUID, **values: Any) -> _Outcome | None: ...
    def review(self, project_id: UUID, ebom_id: UUID, revision_id: UUID, **values: Any) -> _Outcome | None: ...
    def release(self, project_id: UUID, ebom_id: UUID, revision_id: UUID, **values: Any) -> _Outcome | None: ...
    def compare(self, project_id: UUID, ebom_id: UUID, **values: Any) -> dict[str, Any] | None: ...


def _repository_factory(*, principal: Principal, request_id: str, trace_id: str) -> _Repository:
    from npi_core.ebom.frappe_repository import FrappeEngineeringBomRepository

    return FrappeEngineeringBomRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_eboms(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, _ebom_id = _query_context(
            frozenset(),
            request_fields,
        )
        response = repository.list_eboms(project_id)
        if response is None:
            raise EngineeringBomUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_ebom(
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    engineeringBomKey: Any = None,
    title: Any = None,
    reason: Any = None,
    effectivityNote: Any = None,
    lines: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = _command_headers()

    def handle() -> dict[str, Any]:
        with ebom_create_server_diagnostics(current_trace_id.get()):
            with ebom_create_server_step("P504_CREATE_COMMAND_CONTEXT"):
                request_id, key_hash, repository, project_id, _ebom_id = (
                    _command_context(
                        _CREATE_FIELDS,
                        _CREATE_REQUIRED,
                        request_fields,
                    )
                )
            with ebom_create_server_step("P504_CREATE_INPUT_PARSE"):
                values = {
                    "policy_global_id": _uuid(
                        policyGlobalId,
                        "policyGlobalId",
                    ),
                    "policy_version": _positive(
                        policyVersion,
                        "policyVersion",
                    ),
                    "policy_snapshot_hash": _hash(
                        policySnapshotHash,
                        "policySnapshotHash",
                    ),
                    "engineering_bom_key": _text(
                        engineeringBomKey,
                        "engineeringBomKey",
                        64,
                    ),
                    "title": _text(title, "title", 140),
                    "reason": _text(reason, "reason", 280),
                    "effectivity_note": _optional_text(
                        effectivityNote,
                        "effectivityNote",
                        280,
                    ),
                    "lines": _lines(lines),
                }
            with ebom_create_server_step("P504_CREATE_API_RESPONSE"):
                outcome = repository.create_ebom(
                    project_id,
                    idempotency_key_hash=key_hash,
                    **values,
                )
                return _command_response(
                    outcome,
                    request_id=request_id,
                    headers=headers,
                )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_ebom(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, ebom_id = _query_context(
            frozenset(),
            request_fields,
            require_ebom=True,
        )
        assert ebom_id is not None
        response = repository.ebom_detail(project_id, ebom_id)
        if response is None:
            raise EngineeringBomUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_ebom_revision(
    expectedEbomVersion: Any = None,
    predecessorRevisionId: Any = None,
    expectedPredecessorSnapshotHash: Any = None,
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    reason: Any = None,
    effectivityNote: Any = None,
    lines: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = _command_headers()

    def handle() -> dict[str, Any]:
        request_id, key_hash, repository, project_id, ebom_id = _command_context(
            _REVISE_FIELDS,
            _REVISE_REQUIRED,
            request_fields,
            require_ebom=True,
        )
        assert ebom_id is not None
        outcome = repository.create_revision(
            project_id,
            ebom_id,
            idempotency_key_hash=key_hash,
            expected_ebom_version=_positive(expectedEbomVersion, "expectedEbomVersion"),
            predecessor_revision_id=_uuid(predecessorRevisionId, "predecessorRevisionId"),
            expected_predecessor_snapshot_hash=_hash(
                expectedPredecessorSnapshotHash,
                "expectedPredecessorSnapshotHash",
            ),
            policy_global_id=_uuid(policyGlobalId, "policyGlobalId"),
            policy_version=_positive(policyVersion, "policyVersion"),
            policy_snapshot_hash=_hash(policySnapshotHash, "policySnapshotHash"),
            reason=_text(reason, "reason", 280),
            effectivity_note=_optional_text(effectivityNote, "effectivityNote", 280),
            lines=_lines(lines),
        )
        return _command_response(outcome, request_id=request_id, headers=headers)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_ebom_review(
    expectedEbomVersion: Any = None,
    expectedRevisionSnapshotHash: Any = None,
    expectedLifecycleVersion: Any = None,
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _transition_call(
        "submit_review",
        _SUBMIT_FIELDS,
        _TRANSITION_COMMON,
        request_fields,
        {
            "expectedEbomVersion": expectedEbomVersion,
            "expectedRevisionSnapshotHash": expectedRevisionSnapshotHash,
            "expectedLifecycleVersion": expectedLifecycleVersion,
            "policyGlobalId": policyGlobalId,
            "policyVersion": policyVersion,
            "policySnapshotHash": policySnapshotHash,
            "reason": reason,
        },
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def review_ebom_revision(
    expectedEbomVersion: Any = None,
    expectedRevisionSnapshotHash: Any = None,
    expectedLifecycleVersion: Any = None,
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    decision: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _transition_call(
        "review",
        _REVIEW_FIELDS,
        _TRANSITION_COMMON | {"decision"},
        request_fields,
        {
            "expectedEbomVersion": expectedEbomVersion,
            "expectedRevisionSnapshotHash": expectedRevisionSnapshotHash,
            "expectedLifecycleVersion": expectedLifecycleVersion,
            "policyGlobalId": policyGlobalId,
            "policyVersion": policyVersion,
            "policySnapshotHash": policySnapshotHash,
            "decision": decision,
            "reason": reason,
        },
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def release_ebom_revision(
    expectedEbomVersion: Any = None,
    expectedRevisionSnapshotHash: Any = None,
    expectedLifecycleVersion: Any = None,
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    confirmed: Any = None,
    confirmationIntent: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _transition_call(
        "release",
        _RELEASE_FIELDS,
        _RELEASE_FIELDS,
        request_fields,
        {
            "expectedEbomVersion": expectedEbomVersion,
            "expectedRevisionSnapshotHash": expectedRevisionSnapshotHash,
            "expectedLifecycleVersion": expectedLifecycleVersion,
            "policyGlobalId": policyGlobalId,
            "policyVersion": policyVersion,
            "policySnapshotHash": policySnapshotHash,
            "confirmed": confirmed,
            "confirmationIntent": confirmationIntent,
        },
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def compare_ebom_revisions(
    fromRevisionId: Any = None,
    toRevisionId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        fields = frozenset({"fromRevisionId", "toRevisionId"})
        request_id, repository, project_id, ebom_id = _query_context(
            fields,
            request_fields,
            require_ebom=True,
        )
        require_request_fields(fields, request_fields)
        assert ebom_id is not None
        response = repository.compare(
            project_id,
            ebom_id,
            from_revision_id=_uuid(fromRevisionId, "fromRevisionId"),
            to_revision_id=_uuid(toRevisionId, "toRevisionId"),
        )
        if response is None:
            raise EngineeringBomUnavailable()
        headers["X-Request-ID"] = request_id
        return _response(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _transition_call(
    action: str,
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    values: Mapping[str, object],
) -> dict[str, Any] | None:
    headers = _command_headers()

    def handle() -> dict[str, Any]:
        with ebom_transition_server_diagnostics(current_trace_id.get()):
            with ebom_transition_server_step("P504_TRANSITION_COMMAND_CONTEXT"):
                request_id, key_hash, repository, project_id, ebom_id = (
                    _command_context(
                        allowed,
                        required,
                        request_fields,
                        require_ebom=True,
                    )
                )
                assert ebom_id is not None
                revision_id = _opaque_route_uuid("revision_id")
            with ebom_transition_server_step("P504_TRANSITION_INPUT_PARSE"):
                common = {
                    "idempotency_key_hash": key_hash,
                    "expected_ebom_version": _positive(
                        values["expectedEbomVersion"], "expectedEbomVersion"
                    ),
                    "expected_revision_snapshot_hash": _hash(
                        values["expectedRevisionSnapshotHash"],
                        "expectedRevisionSnapshotHash",
                    ),
                    "expected_lifecycle_version": _positive(
                        values["expectedLifecycleVersion"],
                        "expectedLifecycleVersion",
                    ),
                    "policy_global_id": _uuid(
                        values["policyGlobalId"], "policyGlobalId"
                    ),
                    "policy_version": _positive(
                        values["policyVersion"], "policyVersion"
                    ),
                    "policy_snapshot_hash": _hash(
                        values["policySnapshotHash"], "policySnapshotHash"
                    ),
                }
                if action == "submit_review":
                    action_values = {
                        "reason": _optional_text(
                            values.get("reason"), "reason", 280
                        )
                    }
                elif action == "review":
                    action_values = {
                        "decision": _decision(values.get("decision")),
                        "reason": _optional_text(
                            values.get("reason"), "reason", 280
                        ),
                    }
                else:
                    action_values = {
                        "confirmed": _confirmed(values.get("confirmed")),
                        "confirmation_intent": _exact_text(
                            values.get("confirmationIntent"),
                            "confirmationIntent",
                            "release_exact_ebom_revision",
                        ),
                    }
            with ebom_transition_server_step("P504_TRANSITION_API_RESPONSE"):
                if action == "submit_review":
                    outcome = repository.submit_review(
                        project_id,
                        ebom_id,
                        revision_id,
                        **common,
                        **action_values,
                    )
                elif action == "review":
                    outcome = repository.review(
                        project_id,
                        ebom_id,
                        revision_id,
                        **common,
                        **action_values,
                    )
                else:
                    outcome = repository.release(
                        project_id,
                        ebom_id,
                        revision_id,
                        **common,
                        **action_values,
                    )
                return _command_response(
                    outcome,
                    request_id=request_id,
                    headers=headers,
                )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _query_context(
    allowed: frozenset[str],
    request_fields: dict[str, Any],
    *,
    require_ebom: bool = False,
) -> tuple[str, _Repository, UUID, UUID | None]:
    require_engineering_bom_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    repository = _new_repository(principal, response_request_id())
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise EngineeringBomUnavailable()
    ebom_id = None
    if require_ebom:
        ebom_id = _opaque_route_uuid("ebom_id")
        if not repository.authorize_scope(project_id, ebom_id):
            raise EngineeringBomUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    return _request_id(), repository, project_id, ebom_id


def _command_context(
    allowed: frozenset[str],
    required: frozenset[str],
    request_fields: dict[str, Any],
    *,
    require_ebom: bool = False,
) -> tuple[str, str, _Repository, UUID, UUID | None]:
    require_engineering_bom_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()
    repository = _new_repository(principal, response_request_id())
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(project_id):
        raise EngineeringBomUnavailable()
    ebom_id = None
    if require_ebom:
        ebom_id = _opaque_route_uuid("ebom_id")
        if not repository.authorize_scope(project_id, ebom_id):
            raise EngineeringBomUnavailable()
    reject_unexpected_request_fields(allowed, request_fields)
    require_request_fields(required, request_fields)
    return (
        _request_id(),
        actor_idempotency_key_hash(
            actor,
            frappe.get_request_header("Idempotency-Key"),
        ),
        repository,
        project_id,
        ebom_id,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The EBOM request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _command_headers() -> dict[str, str]:
    return {"X-Request-ID": response_request_id(), "Idempotency-Replayed": "false"}


def _command_response(outcome: _Outcome | None, *, request_id: str, headers: dict[str, str]) -> dict[str, Any]:
    if outcome is None:
        raise EngineeringBomUnavailable()
    if type(outcome.replayed) is not bool:
        raise RuntimeError("The EBOM command replay result is invalid.")
    headers["X-Request-ID"] = request_id
    headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
    return _response(outcome.response)


def _response(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The EBOM response is invalid.")
    return value


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise EngineeringBomUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise EngineeringBomUnavailable()
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


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field(path, _("Enter a lowercase SHA-256 value."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
        raise _field(path, _("Enter a bounded text value."))
    return value


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value in (None, "") else _text(value, path, maximum)


def _exact_text(value: object, path: str, expected: str) -> str:
    if value != expected:
        raise _field(path, _("Select the required confirmation intent."))
    return expected


def _confirmed(value: object) -> bool:
    if value is not True:
        raise _field("confirmed", _("Confirm release of the exact EBOM revision."))
    return True


def _decision(value: object) -> EngineeringBomReviewDecision:
    try:
        return EngineeringBomReviewDecision(str(value))
    except ValueError as error:
        raise _field("decision", _("Select approve or reject.")) from error


def _lines(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or not value or len(value) > 500:
        raise _field("lines", _("Enter a bounded EBOM line list."))
    result = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise _field(f"lines[{index}]", _("Enter a valid EBOM line."))
        keys = set(raw)
        if not _LINE_REQUIRED <= keys or not keys <= _LINE_FIELDS:
            raise _field(f"lines[{index}]", _("EBOM line fields are invalid."))
        attributes = raw.get("attributes", {})
        if not isinstance(attributes, Mapping) or len(attributes) > 50 or any(
            not isinstance(key, str) or not isinstance(item, str)
            for key, item in attributes.items()
        ):
            raise _field(f"lines[{index}].attributes", _("Enter controlled text attributes."))
        quantity = raw.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (str, int, float, Decimal)):
            raise _field(f"lines[{index}].quantity", _("Enter a positive decimal quantity."))
        try:
            decimal = Decimal(str(quantity))
        except InvalidOperation as error:
            raise _field(f"lines[{index}].quantity", _("Enter a positive decimal quantity.")) from error
        if not decimal.is_finite() or decimal <= 0:
            raise _field(f"lines[{index}].quantity", _("Enter a positive decimal quantity."))
        item: dict[str, object] = {
            "lineKey": _text(raw.get("lineKey"), f"lines[{index}].lineKey", 64),
            "parentLineKey": _optional_text(raw.get("parentLineKey"), f"lines[{index}].parentLineKey", 64),
            "engineeringItemId": _key_text(raw.get("engineeringItemId"), f"lines[{index}].engineeringItemId"),
            "description": _text(raw.get("description"), f"lines[{index}].description", 280),
            "quantity": str(quantity),
            "engineeringUom": _text(raw.get("engineeringUom"), f"lines[{index}].engineeringUom", 16),
            "alternateForLineKey": _optional_text(raw.get("alternateForLineKey"), f"lines[{index}].alternateForLineKey", 64),
            "alternateGroupKey": _optional_text(raw.get("alternateGroupKey"), f"lines[{index}].alternateGroupKey", 64),
            "effectivityStart": _optional_date(raw.get("effectivityStart"), f"lines[{index}].effectivityStart"),
            "effectivityEnd": _optional_date(raw.get("effectivityEnd"), f"lines[{index}].effectivityEnd"),
            "attributes": {str(key): str(item) for key, item in sorted(attributes.items())},
        }
        result.append(item)
    return tuple(result)


def _key_text(value: object, path: str) -> str:
    result = _text(value, path, 128)
    if _KEY.fullmatch(result) is None:
        raise _field(path, _("Enter a supported engineering identity."))
    return result


def _optional_date(value: object, path: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid effectivity date."))
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise _field(path, _("Enter a valid effectivity date.")) from error
    if parsed.isoformat() != value:
        raise _field(path, _("Enter a canonical effectivity date."))
    return value


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
