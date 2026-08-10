from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
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
    require_trial_routes_enabled,
    response_request_id,
)
from npi_core.trial.domain import TrialPurpose, TrialUnavailable


_PLAN_FIELDS = frozenset(
    {
        "toolingMasterGlobalId",
        "purpose",
        "objective",
        "plannedStartAt",
        "plannedEndAt",
        "resources",
        "responsibleMemberGlobalIds",
        "sampleQuantity",
        "measurementPlan",
        "reason",
    }
)
_REVISION_FIELDS = frozenset(
    {
        "expectedRevisionGlobalId",
        "expectedRevisionSnapshotHash",
        "expectedPlanVersion",
        "purpose",
        "objective",
        "plannedStartAt",
        "plannedEndAt",
        "resources",
        "responsibleMemberGlobalIds",
        "sampleQuantity",
        "measurementPlan",
        "reason",
    }
)
_ROUND_FIELDS = frozenset(
    {
        "expectedPlanRevisionGlobalId",
        "expectedPlanRevisionSnapshotHash",
        "displayLabel",
        "reason",
    }
)
_ROUND_REQUIRED = frozenset(
    {
        "expectedPlanRevisionGlobalId",
        "expectedPlanRevisionSnapshotHash",
        "reason",
    }
)
_GENERATE_FIELDS = frozenset(
    {
        "expectedPlanRevisionGlobalId",
        "expectedPlanRevisionSnapshotHash",
        "trialRoundGlobalId",
        "actions",
        "reason",
    }
)
_RESOURCE_FIELDS = frozenset(
    {"kind", "sourceSystem", "sourceObjectId", "label", "quantity", "unit"}
)
_RESOURCE_REQUIRED = frozenset(
    {"kind", "sourceSystem", "sourceObjectId", "label"}
)
_MEASUREMENT_FIELDS = frozenset(
    {
        "description",
        "documentRevisionGlobalId",
        "documentRevisionSnapshotHash",
        "documentOptimisticVersion",
    }
)
_ACTION_FIELDS = frozenset(
    {
        "actionKey",
        "title",
        "description",
        "responsibleMemberGlobalId",
        "dueAt",
        "severity",
        "blocking",
    }
)
_ACTION_REQUIRED = frozenset(
    {
        "actionKey",
        "title",
        "responsibleMemberGlobalId",
        "dueAt",
        "severity",
        "blocking",
    }
)
_HASH = re.compile(r"^[a-f0-9]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_ROUND_LABEL = re.compile(r"^T(?:0|[1-9][0-9]{0,3})$")


class _Repository(Protocol):
    def planning_workspace(self, project_id: UUID): ...
    def plan_detail(self, project_id: UUID, plan_id: UUID): ...
    def create_plan(self, project_id: UUID, **values: Any): ...
    def create_plan_revision(self, project_id: UUID, plan_id: UUID, **values: Any): ...
    def create_round(self, project_id: UUID, plan_id: UUID, **values: Any): ...
    def generate_actions(self, project_id: UUID, plan_id: UUID, **values: Any): ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_core.trial.frappe_repository import FrappeTrialRepository

    return FrappeTrialRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_trial_planning_workspace(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository = _query_repository(request_fields)
        response = repository.planning_workspace(_opaque_project_uuid())
        if response is None:
            raise TrialUnavailable()
        headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_trial_plan(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository = _query_repository(request_fields)
        response = repository.plan_detail(
            _opaque_project_uuid(),
            _opaque_route_uuid("trial_plan_id"),
        )
        if response is None:
            raise TrialUnavailable()
        headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_trial_plan(
    toolingMasterGlobalId: Any = None,
    purpose: Any = None,
    objective: Any = None,
    plannedStartAt: Any = None,
    plannedEndAt: Any = None,
    resources: Any = None,
    responsibleMemberGlobalIds: Any = None,
    sampleQuantity: Any = None,
    measurementPlan: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "toolingMasterGlobalId": toolingMasterGlobalId,
        "purpose": purpose,
        "objective": objective,
        "plannedStartAt": plannedStartAt,
        "plannedEndAt": plannedEndAt,
        "resources": resources,
        "responsibleMemberGlobalIds": responsibleMemberGlobalIds,
        "sampleQuantity": sampleQuantity,
        "measurementPlan": measurementPlan,
        "reason": reason,
    }
    return _command(
        allowed_fields=_PLAN_FIELDS,
        required_fields=_PLAN_FIELDS,
        request_fields=request_fields,
        invoke=lambda repository, project_id, key_hash: repository.create_plan(
            project_id,
            idempotency_key_hash=key_hash,
            tooling_master_global_id=_uuid(
                values["toolingMasterGlobalId"],
                "toolingMasterGlobalId",
            ),
            purpose=_purpose(values["purpose"]),
            objective=_text(values["objective"], "objective", 2000),
            planned_start_at=_datetime(values["plannedStartAt"], "plannedStartAt"),
            planned_end_at=_datetime(values["plannedEndAt"], "plannedEndAt"),
            resources=_resources(values["resources"]),
            responsible_member_global_ids=_uuid_array(
                values["responsibleMemberGlobalIds"],
                "responsibleMemberGlobalIds",
                maximum=50,
            ),
            sample_quantity=_positive(values["sampleQuantity"], "sampleQuantity"),
            measurement_plan=_measurement(values["measurementPlan"]),
            reason=_text(values["reason"], "reason", 500),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_trial_plan_revision(
    expectedRevisionGlobalId: Any = None,
    expectedRevisionSnapshotHash: Any = None,
    expectedPlanVersion: Any = None,
    purpose: Any = None,
    objective: Any = None,
    plannedStartAt: Any = None,
    plannedEndAt: Any = None,
    resources: Any = None,
    responsibleMemberGlobalIds: Any = None,
    sampleQuantity: Any = None,
    measurementPlan: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = locals()
    return _command(
        allowed_fields=_REVISION_FIELDS,
        required_fields=_REVISION_FIELDS,
        request_fields=request_fields,
        invoke=lambda repository, project_id, key_hash: repository.create_plan_revision(
            project_id,
            _opaque_route_uuid("trial_plan_id"),
            idempotency_key_hash=key_hash,
            expected_revision_global_id=_uuid(
                values["expectedRevisionGlobalId"],
                "expectedRevisionGlobalId",
            ),
            expected_revision_snapshot_hash=_hash(
                values["expectedRevisionSnapshotHash"],
                "expectedRevisionSnapshotHash",
            ),
            expected_plan_version=_positive(
                values["expectedPlanVersion"],
                "expectedPlanVersion",
            ),
            purpose=_purpose(values["purpose"]),
            objective=_text(values["objective"], "objective", 2000),
            planned_start_at=_datetime(values["plannedStartAt"], "plannedStartAt"),
            planned_end_at=_datetime(values["plannedEndAt"], "plannedEndAt"),
            resources=_resources(values["resources"]),
            responsible_member_global_ids=_uuid_array(
                values["responsibleMemberGlobalIds"],
                "responsibleMemberGlobalIds",
                maximum=50,
            ),
            sample_quantity=_positive(values["sampleQuantity"], "sampleQuantity"),
            measurement_plan=_measurement(values["measurementPlan"]),
            reason=_text(values["reason"], "reason", 500),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_planned_trial_round(
    expectedPlanRevisionGlobalId: Any = None,
    expectedPlanRevisionSnapshotHash: Any = None,
    displayLabel: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = locals()
    return _command(
        allowed_fields=_ROUND_FIELDS,
        required_fields=_ROUND_REQUIRED,
        request_fields=request_fields,
        invoke=lambda repository, project_id, key_hash: repository.create_round(
            project_id,
            _opaque_route_uuid("trial_plan_id"),
            idempotency_key_hash=key_hash,
            expected_plan_revision_global_id=_uuid(
                values["expectedPlanRevisionGlobalId"],
                "expectedPlanRevisionGlobalId",
            ),
            expected_plan_revision_snapshot_hash=_hash(
                values["expectedPlanRevisionSnapshotHash"],
                "expectedPlanRevisionSnapshotHash",
            ),
            display_label=_optional_round_label(values["displayLabel"]),
            reason=_text(values["reason"], "reason", 500),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def generate_trial_plan_actions(
    expectedPlanRevisionGlobalId: Any = None,
    expectedPlanRevisionSnapshotHash: Any = None,
    trialRoundGlobalId: Any = None,
    actions: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = locals()
    return _command(
        allowed_fields=_GENERATE_FIELDS,
        required_fields=frozenset(
            {
                "expectedPlanRevisionGlobalId",
                "expectedPlanRevisionSnapshotHash",
                "actions",
                "reason",
            }
        ),
        request_fields=request_fields,
        invoke=lambda repository, project_id, key_hash: repository.generate_actions(
            project_id,
            _opaque_route_uuid("trial_plan_id"),
            idempotency_key_hash=key_hash,
            expected_plan_revision_global_id=_uuid(
                values["expectedPlanRevisionGlobalId"],
                "expectedPlanRevisionGlobalId",
            ),
            expected_plan_revision_snapshot_hash=_hash(
                values["expectedPlanRevisionSnapshotHash"],
                "expectedPlanRevisionSnapshotHash",
            ),
            trial_round_global_id=_optional_uuid(
                values["trialRoundGlobalId"],
                "trialRoundGlobalId",
            ),
            actions=_actions(values["actions"]),
            reason=_text(values["reason"], "reason", 500),
        ),
    )


def _query_repository(
    request_fields: dict[str, Any],
) -> tuple[str, _Repository]:
    require_trial_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    _require_role(principal)
    reject_unexpected_request_fields(frozenset(), request_fields)
    return _new_repository(principal)


def _command(
    *,
    allowed_fields: frozenset[str],
    required_fields: frozenset[str],
    request_fields: dict[str, Any],
    invoke,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        require_trial_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        _require_role(principal)
        request_id, repository = _new_repository(principal)
        project_id = _opaque_project_uuid()
        reject_unexpected_request_fields(allowed_fields, request_fields)
        require_request_fields(required_fields, request_fields)
        outcome = invoke(
            repository,
            project_id,
            actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
        )
        if outcome is None:
            raise TrialUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The Trial replay response is invalid.")
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return outcome.response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


def _new_repository(principal: Principal) -> tuple[str, _Repository]:
    request_id = str(_canonical_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Trial request has no active trace identity.")
    return request_id, _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _require_role(principal: Principal) -> None:
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()


def _opaque_project_uuid() -> UUID:
    return _opaque_route_uuid("project_id")


def _opaque_route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise TrialUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise TrialUnavailable()
    return parsed


def _resources(value: object) -> list[dict[str, Any]]:
    items = _array(value, "resources", minimum=2, maximum=50)
    prepared = []
    for index, item in enumerate(items):
        record = _closed_record(
            item,
            f"resources[{index}]",
            allowed=_RESOURCE_FIELDS,
            required=_RESOURCE_REQUIRED,
        )
        quantity = record.get("quantity")
        unit = record.get("unit")
        if (quantity is None) != (unit is None):
            raise _field(
                f"resources[{index}].quantity",
                _("Enter both the planned quantity and unit, or leave both empty."),
            )
        prepared.append(
            {
                "kind": _choice(
                    record["kind"],
                    f"resources[{index}].kind",
                    {"machine", "auxiliary_equipment", "material"},
                ),
                "sourceSystem": _choice(
                    record["sourceSystem"],
                    f"resources[{index}].sourceSystem",
                    {"NPI_ONE", "ERPNEXT"},
                ),
                "sourceObjectId": _text(
                    record["sourceObjectId"],
                    f"resources[{index}].sourceObjectId",
                    128,
                ),
                "label": _text(
                    record["label"],
                    f"resources[{index}].label",
                    140,
                ),
                "quantity": (
                    _positive(quantity, f"resources[{index}].quantity")
                    if quantity is not None
                    else None
                ),
                "unit": (
                    _text(unit, f"resources[{index}].unit", 32)
                    if unit is not None
                    else None
                ),
            }
        )
    return prepared


def _measurement(value: object) -> dict[str, Any]:
    record = _closed_record(
        value,
        "measurementPlan",
        allowed=_MEASUREMENT_FIELDS,
        required=frozenset(),
    )
    description = record.get("description")
    document_values = (
        record.get("documentRevisionGlobalId"),
        record.get("documentRevisionSnapshotHash"),
        record.get("documentOptimisticVersion"),
    )
    if description is None and not any(value is not None for value in document_values):
        raise _field(
            "measurementPlan",
            _("Enter a measurement plan or select a controlled document revision."),
        )
    if any(value is not None for value in document_values) and not all(
        value is not None for value in document_values
    ):
        raise _field(
            "measurementPlan.documentRevisionGlobalId",
            _("Select one complete controlled document revision."),
        )
    return {
        "description": (
            _text(description, "measurementPlan.description", 1000)
            if description is not None
            else None
        ),
        "documentRevisionGlobalId": (
            _uuid(document_values[0], "measurementPlan.documentRevisionGlobalId")
            if document_values[0] is not None
            else None
        ),
        "documentRevisionSnapshotHash": (
            _hash(
                document_values[1],
                "measurementPlan.documentRevisionSnapshotHash",
            )
            if document_values[1] is not None
            else None
        ),
        "documentOptimisticVersion": (
            _positive(
                document_values[2],
                "measurementPlan.documentOptimisticVersion",
            )
            if document_values[2] is not None
            else None
        ),
    }


def _actions(value: object) -> list[dict[str, Any]]:
    items = _array(value, "actions", minimum=1, maximum=50)
    prepared = []
    for index, item in enumerate(items):
        path = f"actions[{index}]"
        record = _closed_record(
            item,
            path,
            allowed=_ACTION_FIELDS,
            required=_ACTION_REQUIRED,
        )
        action_key = _text(record["actionKey"], f"{path}.actionKey", 64)
        if _KEY.fullmatch(action_key) is None:
            raise _field(f"{path}.actionKey", _("Enter a valid value."))
        prepared.append(
            {
                "actionKey": action_key,
                "title": _text(record["title"], f"{path}.title", 280),
                "description": (
                    _text(record["description"], f"{path}.description", 2000)
                    if record.get("description") is not None
                    else None
                ),
                "responsibleMemberGlobalId": _uuid(
                    record["responsibleMemberGlobalId"],
                    f"{path}.responsibleMemberGlobalId",
                ),
                "dueAt": _datetime(record["dueAt"], f"{path}.dueAt"),
                "severity": _choice(
                    record["severity"],
                    f"{path}.severity",
                    {"low", "medium", "high", "critical"},
                ),
                "blocking": _boolean(record["blocking"], f"{path}.blocking"),
            }
        )
    return prepared


def _closed_record(
    value: object,
    path: str,
    *,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _field(path, _("Enter a valid object."))
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise RequestValidationFailed(
            [
                {
                    "path": f"{path}.{fieldname}",
                    "message": _("This field is not allowed."),
                }
                for fieldname in unexpected
            ]
        )
    missing = sorted(required - set(value))
    if missing:
        raise RequestValidationFailed(
            [
                {
                    "path": f"{path}.{fieldname}",
                    "message": _("This field is required."),
                }
                for fieldname in missing
            ]
        )
    return dict(value)


def _array(
    value: object,
    path: str,
    *,
    minimum: int,
    maximum: int,
) -> list[Any]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not minimum <= len(value) <= maximum
    ):
        raise _field(path, _("Enter a valid bounded list."))
    return list(value)


def _uuid_array(value: object, path: str, *, maximum: int) -> tuple[UUID, ...]:
    items = _array(value, path, minimum=1, maximum=maximum)
    parsed = tuple(_uuid(item, f"{path}[{index}]") for index, item in enumerate(items))
    if len(parsed) != len(set(parsed)):
        raise _field(path, _("Global IDs must be unique."))
    return parsed


def _purpose(value: object) -> TrialPurpose:
    try:
        return TrialPurpose(str(value))
    except ValueError as error:
        raise _field("purpose", _("Select a supported value.")) from error


def _optional_round_label(value: object) -> str | None:
    if value is None:
        return None
    label = _text(value, "displayLabel", 16).upper()
    if _ROUND_LABEL.fullmatch(label) is None:
        raise _field("displayLabel", _("Enter a Trial Round label such as T0 or T1."))
    return label


def _choice(value: object, path: str, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise _field(path, _("Select a supported value."))
    return value


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _field(path, _("Select true or false."))
    return value


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(path, _("Enter a positive integer."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field(path, _("Enter a shorter value."))
    return normalized


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid(value, path)


def _uuid(value: object, path: str) -> UUID:
    return _canonical_uuid(value, path)


def _canonical_uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a valid global ID."))
    return parsed


def _datetime(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise _field(path, _("Enter a valid date and time.")) from error
    else:
        raise _field(path, _("Enter a valid date and time."))
    if parsed.tzinfo is None:
        raise _field(path, _("Enter a valid date and time."))
    return parsed.astimezone(UTC)


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
