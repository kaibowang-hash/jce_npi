from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import (
    PermissionDenied,
    RequestValidationFailed,
)
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.project_api import ProjectUnavailable
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    response_request_id,
)


_CONFIGURE_TEAM_FIELDS = frozenset(
    {
        "expectedProjectVersion",
        "workPolicyRef",
        "members",
        "roleAssignments",
        "substitutions",
        "raciAssignments",
    }
)
_APPLY_WORK_PLAN_FIELDS = frozenset(
    {
        "expectedProjectVersion",
        "workPolicyRef",
        "items",
        "dependencies",
    }
)
_CAPTURE_BASELINE_FIELDS = frozenset(
    {"expectedProjectVersion", "workPolicyRef", "label"}
)
_CREATE_DOMAIN_WORK_ITEM_FIELDS = frozenset(
    {
        "expectedProjectVersion",
        "workPolicyRef",
        "kind",
        "title",
        "detail",
        "context",
        "ownerUserId",
        "dueAt",
        "severity",
        "blocking",
        "relatedWorkItemIds",
    }
)
_LIST_DOMAIN_WORK_ITEM_FIELDS = frozenset(
    {"stageId", "ownerUserId", "overdue", "kind", "cursor", "limit"}
)
_WORK_POLICY_FIELDS = frozenset({"globalId", "version", "snapshotHash"})
_MEMBER_FIELDS = frozenset(
    {"globalId", "userId", "effectiveFrom", "effectiveTo"}
)
_ROLE_ASSIGNMENT_FIELDS = frozenset(
    {"globalId", "memberId", "roleKey", "effectiveFrom", "effectiveTo"}
)
_SUBSTITUTION_FIELDS = frozenset(
    {
        "globalId",
        "roleAssignmentId",
        "substituteMemberId",
        "effectiveFrom",
        "effectiveTo",
    }
)
_RACI_FIELDS = frozenset(
    {
        "globalId",
        "contextType",
        "contextId",
        "responsibilityKey",
        "roleAssignmentId",
        "raci",
    }
)
_WBS_ITEM_FIELDS = frozenset(
    {
        "globalId",
        "code",
        "title",
        "parentId",
        "ownerRoleAssignmentId",
        "plannedStart",
        "plannedFinish",
        "actualStart",
        "actualFinish",
        "milestone",
        "statusKey",
        "progressPercent",
        "critical",
    }
)
_DEPENDENCY_FIELDS = frozenset(
    {"globalId", "predecessorItemId", "successorItemId"}
)
_DOMAIN_CONTEXT_FIELDS = frozenset({"stageId", "wbsItemId"})

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UTC_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_CONTROLLED_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_DOMAIN_WORK_ITEM_KINDS = frozenset(
    {"risk", "issue", "action", "decision_request"}
)
_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
_RACI_RESPONSIBILITIES = frozenset(
    {"responsible", "accountable", "consulted", "informed"}
)
_RACI_CONTEXT_TYPES = frozenset(
    {"project", "wbs_item", "domain_work_item"}
)


class WorkCommandOutcomeLike(Protocol):
    response: dict[str, Any]
    replayed: bool


class ProjectWorkRepositoryLike(Protocol):
    def work_context(self, project_id: UUID) -> dict[str, Any] | None: ...

    def configure_team(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: dict[str, Any],
        members: tuple[dict[str, Any], ...],
        role_assignments: tuple[dict[str, Any], ...],
        substitutions: tuple[dict[str, Any], ...],
        raci_assignments: tuple[dict[str, Any], ...],
    ) -> WorkCommandOutcomeLike | None: ...

    def apply_work_plan(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: dict[str, Any],
        items: tuple[dict[str, Any], ...],
        dependencies: tuple[dict[str, Any], ...],
    ) -> WorkCommandOutcomeLike | None: ...

    def capture_plan_baseline(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: dict[str, Any],
        label: str,
    ) -> WorkCommandOutcomeLike | None: ...

    def create_domain_work_item(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: dict[str, Any],
        kind: str,
        title: str,
        detail: str | None,
        context: dict[str, UUID | None],
        owner_user_id: str,
        due_at: datetime,
        severity: str,
        blocking: bool,
        related_work_item_ids: tuple[UUID, ...],
    ) -> WorkCommandOutcomeLike | None: ...

    def list_domain_work_items(
        self,
        project_id: UUID,
        *,
        stage_id: UUID | None,
        owner_user_id: str | None,
        overdue: bool | None,
        kind: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any] | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> ProjectWorkRepositoryLike:
    from npi_core.project_work.frappe_repository import (
        FrappeProjectWorkRepository,
    )

    return FrappeProjectWorkRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_work_context(**request_fields: Any) -> dict[str, Any] | None:
    """Return the IDOR-safe Project Team, WBS, and baseline context."""
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        reject_unexpected_request_fields(frozenset(), request_fields)
        request_id = _request_id()
        project_id = _route_project_id()
        repository = _repository(actor=actor, request_id=request_id)
        response = repository.work_context(project_id)
        if response is None:
            raise ProjectUnavailable()
        success_headers["X-Request-ID"] = request_id
        return _response_dict(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def configure_project_team(
    expectedProjectVersion: Any = None,
    workPolicyRef: Any = None,
    members: Any = None,
    roleAssignments: Any = None,
    substitutions: Any = None,
    raciAssignments: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Atomically apply explicit Team, role, substitution, and RACI records."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _CONFIGURE_TEAM_FIELDS,
            request_fields,
        )
        outcome = repository.configure_team(
            _route_project_id(),
            idempotency_key=idempotency_key,
            expected_project_version=_positive_integer(
                expectedProjectVersion,
                "expectedProjectVersion",
            ),
            work_policy_ref=_work_policy_ref(workPolicyRef),
            members=_members(members),
            role_assignments=_role_assignments(roleAssignments),
            substitutions=_substitutions(substitutions),
            raci_assignments=_raci_assignments(raciAssignments),
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
def apply_project_work_plan(
    expectedProjectVersion: Any = None,
    workPolicyRef: Any = None,
    items: Any = None,
    dependencies: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Atomically apply WBS nodes after validating the complete resulting graph."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _APPLY_WORK_PLAN_FIELDS,
            request_fields,
        )
        outcome = repository.apply_work_plan(
            _route_project_id(),
            idempotency_key=idempotency_key,
            expected_project_version=_positive_integer(
                expectedProjectVersion,
                "expectedProjectVersion",
            ),
            work_policy_ref=_work_policy_ref(workPolicyRef),
            items=_wbs_items(items),
            dependencies=_dependencies(dependencies),
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
def capture_project_plan_baseline(
    expectedProjectVersion: Any = None,
    workPolicyRef: Any = None,
    label: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Capture one immutable WBS plan baseline."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _CAPTURE_BASELINE_FIELDS,
            request_fields,
        )
        outcome = repository.capture_plan_baseline(
            _route_project_id(),
            idempotency_key=idempotency_key,
            expected_project_version=_positive_integer(
                expectedProjectVersion,
                "expectedProjectVersion",
            ),
            work_policy_ref=_work_policy_ref(workPolicyRef),
            label=_text(label, "label", maximum_length=140),
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
def create_project_domain_work_item(
    expectedProjectVersion: Any = None,
    workPolicyRef: Any = None,
    kind: Any = None,
    title: Any = None,
    detail: Any = None,
    context: Any = None,
    ownerUserId: Any = None,
    dueAt: Any = None,
    severity: Any = None,
    blocking: Any = None,
    relatedWorkItemIds: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """Create one Domain WorkItem without accepting a caller-selected state."""
    success_headers = _command_response_headers()

    def handle() -> dict[str, Any]:
        request_id, idempotency_key, repository = _command_context(
            _CREATE_DOMAIN_WORK_ITEM_FIELDS,
            request_fields,
        )
        outcome = repository.create_domain_work_item(
            _route_project_id(),
            idempotency_key=idempotency_key,
            expected_project_version=_positive_integer(
                expectedProjectVersion,
                "expectedProjectVersion",
            ),
            work_policy_ref=_work_policy_ref(workPolicyRef),
            kind=_enum_text(kind, "kind", _DOMAIN_WORK_ITEM_KINDS),
            title=_text(title, "title", maximum_length=280),
            detail=_optional_text(detail, "detail", maximum_length=4000),
            context=_domain_context(context),
            owner_user_id=_email(ownerUserId, "ownerUserId"),
            due_at=_utc_datetime(dueAt, "dueAt"),
            severity=_enum_text(severity, "severity", _SEVERITIES),
            blocking=_boolean(blocking, "blocking"),
            related_work_item_ids=_uuid_array(
                relatedWorkItemIds,
                "relatedWorkItemIds",
                maximum_items=100,
            ),
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


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_domain_work_items(
    stageId: Any = None,
    ownerUserId: Any = None,
    overdue: Any = None,
    kind: Any = None,
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    """List Project-scoped Domain WorkItems without exposing My Work semantics."""
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        actor = authenticated_user()
        reject_unexpected_request_fields(
            _LIST_DOMAIN_WORK_ITEM_FIELDS,
            request_fields,
        )
        request_id = _request_id()
        repository = _repository(actor=actor, request_id=request_id)
        response = repository.list_domain_work_items(
            _route_project_id(),
            stage_id=_optional_uuid(stageId, "stageId"),
            owner_user_id=(
                None
                if ownerUserId is None
                else _email(ownerUserId, "ownerUserId")
            ),
            overdue=_optional_query_boolean(overdue, "overdue"),
            kind=(
                None
                if kind is None
                else _enum_text(kind, "kind", _DOMAIN_WORK_ITEM_KINDS)
            ),
            # Cursor shape/signature validation intentionally remains inside
            # the authorized repository boundary so an unavailable Project
            # cannot be distinguished with malformed input.
            cursor=cursor,
            limit=_query_limit(limit),
        )
        if response is None:
            raise ProjectUnavailable()
        success_headers["X-Request-ID"] = request_id
        return _response_dict(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


def _command_context(
    allowed_fields: frozenset[str],
    request_fields: dict[str, Any],
) -> tuple[str, str, ProjectWorkRepositoryLike]:
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
        _repository_from_principal(principal, request_id),
    )


def _repository(
    *,
    actor: str,
    request_id: str,
) -> ProjectWorkRepositoryLike:
    return _repository_from_principal(
        authenticated_principal(actor),
        request_id,
    )


def _repository_from_principal(
    principal: Principal,
    request_id: str,
) -> ProjectWorkRepositoryLike:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Project work request has no active trace identity.")
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
    outcome: WorkCommandOutcomeLike | None,
    *,
    request_id: str,
    success_headers: dict[str, str],
) -> dict[str, Any]:
    if outcome is None:
        raise ProjectUnavailable()
    if type(outcome.replayed) is not bool:
        raise RuntimeError("The Project work command replay result is invalid.")
    success_headers["X-Request-ID"] = request_id
    success_headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
    return _response_dict(outcome.response)


def _response_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Project work response is invalid.")
    return value


def _request_id() -> str:
    return str(
        _uuid_value(
            frappe.get_request_header("X-Request-ID"),
            "requestId",
        )
    )


def _route_project_id() -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    project_id = (
        route_params.get("project_id")
        if hasattr(route_params, "get")
        else None
    )
    return _uuid_value(project_id, "projectId")


def _work_policy_ref(value: object) -> dict[str, Any]:
    item = _strict_object(
        value,
        "workPolicyRef",
        allowed=_WORK_POLICY_FIELDS,
        required=_WORK_POLICY_FIELDS,
    )
    snapshot_hash = item["snapshotHash"]
    if (
        not isinstance(snapshot_hash, str)
        or _SHA256_PATTERN.fullmatch(snapshot_hash) is None
    ):
        raise _field_problem(
            "workPolicyRef.snapshotHash",
            _("Enter a valid value."),
        )
    return {
        "global_id": _uuid_value(
            item["globalId"],
            "workPolicyRef.globalId",
        ),
        "version": _positive_integer(
            item["version"],
            "workPolicyRef.version",
        ),
        "snapshot_hash": snapshot_hash,
    }


def _members(value: object) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "members",
        minimum_items=1,
        maximum_items=500,
    )
    result = []
    for index, row in enumerate(rows):
        path = f"members[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_MEMBER_FIELDS,
            required=frozenset({"globalId", "userId", "effectiveFrom"}),
        )
        result.append(
            {
                "global_id": _uuid_value(item["globalId"], f"{path}.globalId"),
                "user_id": _email(item["userId"], f"{path}.userId"),
                "effective_from": _date_value(
                    item["effectiveFrom"],
                    f"{path}.effectiveFrom",
                ),
                "effective_to": _optional_date(
                    item.get("effectiveTo"),
                    f"{path}.effectiveTo",
                ),
            }
        )
    _require_unique_global_ids(result, "members")
    return tuple(result)


def _role_assignments(value: object) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "roleAssignments",
        minimum_items=1,
        maximum_items=1000,
    )
    result = []
    for index, row in enumerate(rows):
        path = f"roleAssignments[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_ROLE_ASSIGNMENT_FIELDS,
            required=frozenset(
                {"globalId", "memberId", "roleKey", "effectiveFrom"}
            ),
        )
        result.append(
            {
                "global_id": _uuid_value(item["globalId"], f"{path}.globalId"),
                "member_id": _uuid_value(item["memberId"], f"{path}.memberId"),
                "role_key": _controlled_key(
                    item["roleKey"],
                    f"{path}.roleKey",
                ),
                "effective_from": _date_value(
                    item["effectiveFrom"],
                    f"{path}.effectiveFrom",
                ),
                "effective_to": _optional_date(
                    item.get("effectiveTo"),
                    f"{path}.effectiveTo",
                ),
            }
        )
    _require_unique_global_ids(result, "roleAssignments")
    return tuple(result)


def _substitutions(value: object) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "substitutions",
        maximum_items=1000,
    )
    result = []
    for index, row in enumerate(rows):
        path = f"substitutions[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_SUBSTITUTION_FIELDS,
            required=_SUBSTITUTION_FIELDS,
        )
        result.append(
            {
                "global_id": _uuid_value(item["globalId"], f"{path}.globalId"),
                "role_assignment_id": _uuid_value(
                    item["roleAssignmentId"],
                    f"{path}.roleAssignmentId",
                ),
                "substitute_member_id": _uuid_value(
                    item["substituteMemberId"],
                    f"{path}.substituteMemberId",
                ),
                "effective_from": _date_value(
                    item["effectiveFrom"],
                    f"{path}.effectiveFrom",
                ),
                "effective_to": _date_value(
                    item["effectiveTo"],
                    f"{path}.effectiveTo",
                ),
            }
        )
    _require_unique_global_ids(result, "substitutions")
    return tuple(result)


def _raci_assignments(value: object) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "raciAssignments",
        minimum_items=1,
        maximum_items=2000,
    )
    result = []
    for index, row in enumerate(rows):
        path = f"raciAssignments[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_RACI_FIELDS,
            required=_RACI_FIELDS,
        )
        result.append(
            {
                "global_id": _uuid_value(item["globalId"], f"{path}.globalId"),
                "context_type": _enum_text(
                    item["contextType"],
                    f"{path}.contextType",
                    _RACI_CONTEXT_TYPES,
                ),
                "context_id": _uuid_value(
                    item["contextId"],
                    f"{path}.contextId",
                ),
                "responsibility_key": _controlled_key(
                    item["responsibilityKey"],
                    f"{path}.responsibilityKey",
                ),
                "role_assignment_id": _uuid_value(
                    item["roleAssignmentId"],
                    f"{path}.roleAssignmentId",
                ),
                "raci": _enum_text(
                    item["raci"],
                    f"{path}.raci",
                    _RACI_RESPONSIBILITIES,
                ),
            }
        )
    _require_unique_global_ids(result, "raciAssignments")
    return tuple(result)


def _wbs_items(value: object) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "items",
        minimum_items=1,
        maximum_items=2000,
    )
    result = []
    required = frozenset(
        {
            "globalId",
            "code",
            "title",
            "plannedStart",
            "plannedFinish",
            "milestone",
            "statusKey",
            "progressPercent",
            "critical",
        }
    )
    for index, row in enumerate(rows):
        path = f"items[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_WBS_ITEM_FIELDS,
            required=required,
        )
        result.append(
            {
                "global_id": _uuid_value(item["globalId"], f"{path}.globalId"),
                "code": _pattern_text(
                    item["code"],
                    f"{path}.code",
                    maximum_length=64,
                    pattern=_CODE_PATTERN,
                ),
                "title": _text(
                    item["title"],
                    f"{path}.title",
                    maximum_length=280,
                ),
                "parent_id": _optional_uuid(
                    item.get("parentId"),
                    f"{path}.parentId",
                ),
                "owner_role_assignment_id": _optional_uuid(
                    item.get("ownerRoleAssignmentId"),
                    f"{path}.ownerRoleAssignmentId",
                ),
                "planned_start": _date_value(
                    item["plannedStart"],
                    f"{path}.plannedStart",
                ),
                "planned_finish": _date_value(
                    item["plannedFinish"],
                    f"{path}.plannedFinish",
                ),
                "actual_start": _optional_date(
                    item.get("actualStart"),
                    f"{path}.actualStart",
                ),
                "actual_finish": _optional_date(
                    item.get("actualFinish"),
                    f"{path}.actualFinish",
                ),
                "milestone": _boolean(
                    item["milestone"],
                    f"{path}.milestone",
                ),
                "status_key": _controlled_key(
                    item["statusKey"],
                    f"{path}.statusKey",
                ),
                "progress_percent": _bounded_integer(
                    item["progressPercent"],
                    f"{path}.progressPercent",
                    minimum=0,
                    maximum=100,
                ),
                "critical": _boolean(
                    item["critical"],
                    f"{path}.critical",
                ),
            }
        )
    _require_unique_global_ids(result, "items")
    return tuple(result)


def _dependencies(value: object) -> tuple[dict[str, Any], ...]:
    rows = _object_array(
        value,
        "dependencies",
        maximum_items=5000,
    )
    result = []
    for index, row in enumerate(rows):
        path = f"dependencies[{index}]"
        item = _strict_object(
            row,
            path,
            allowed=_DEPENDENCY_FIELDS,
            required=_DEPENDENCY_FIELDS,
        )
        result.append(
            {
                "global_id": _uuid_value(item["globalId"], f"{path}.globalId"),
                "predecessor_item_id": _uuid_value(
                    item["predecessorItemId"],
                    f"{path}.predecessorItemId",
                ),
                "successor_item_id": _uuid_value(
                    item["successorItemId"],
                    f"{path}.successorItemId",
                ),
            }
        )
    _require_unique_global_ids(result, "dependencies")
    return tuple(result)


def _domain_context(value: object) -> dict[str, UUID | None]:
    item = _strict_object(
        value,
        "context",
        allowed=_DOMAIN_CONTEXT_FIELDS,
        required=frozenset(),
    )
    return {
        "stage_id": _optional_uuid(item.get("stageId"), "context.stageId"),
        "wbs_item_id": _optional_uuid(
            item.get("wbsItemId"),
            "context.wbsItemId",
        ),
    }


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
    missing = sorted(required - set(value))
    errors = [
        {
            "path": f"{path}.{field}",
            "message": _("This field is not allowed."),
        }
        for field in unexpected
    ]
    errors.extend(
        {
            "path": f"{path}.{field}",
            "message": _("This field is required."),
        }
        for field in missing
    )
    if errors:
        raise RequestValidationFailed(errors)
    return value


def _object_array(
    value: object,
    path: str,
    *,
    minimum_items: int = 0,
    maximum_items: int,
) -> list[dict[str, Any]]:
    if (
        not isinstance(value, list)
        or len(value) < minimum_items
        or len(value) > maximum_items
        or any(not isinstance(item, dict) for item in value)
    ):
        raise _field_problem(path, _("Enter a valid value."))
    return value


def _uuid_array(
    value: object,
    path: str,
    *,
    maximum_items: int,
) -> tuple[UUID, ...]:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise _field_problem(path, _("Enter a valid value."))
    parsed = tuple(
        _uuid_value(item, f"{path}[{index}]")
        for index, item in enumerate(value)
    )
    if len(set(parsed)) != len(parsed):
        raise _field_problem(path, _("Enter a valid value."))
    return parsed


def _require_unique_global_ids(
    values: list[dict[str, Any]],
    path: str,
) -> None:
    identities = [value["global_id"] for value in values]
    if len(set(identities)) != len(identities):
        raise _field_problem(path, _("Enter a valid value."))


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


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid_value(value, path)


def _positive_integer(value: object, path: str) -> int:
    return _bounded_integer(
        value,
        path,
        minimum=1,
        maximum=2_147_483_647,
    )


def _bounded_integer(
    value: object,
    path: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _field_problem(path, _("Enter a valid value."))
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


def _optional_date(value: object, path: str) -> date | None:
    return None if value is None else _date_value(value, path)


def _utc_datetime(value: object, path: str) -> datetime:
    if (
        not isinstance(value, str)
        or _UTC_DATETIME_PATTERN.fullmatch(value) is None
    ):
        raise _field_problem(path, _("Enter a valid date."))
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise _field_problem(path, _("Enter a valid date."))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise _field_problem(path, _("Enter a valid date."))
    return parsed.astimezone(UTC)


def _email(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 254
        or _EMAIL_PATTERN.fullmatch(value) is None
    ):
        raise _field_problem(
            path,
            _("Enter a valid owner email address."),
        )
    return value.casefold()


def _text(value: object, path: str, *, maximum_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a value."))
    if len(value) > maximum_length:
        raise _field_problem(path, _("Enter a valid value."))
    normalized = value.strip()
    return normalized


def _optional_text(
    value: object,
    path: str,
    *,
    maximum_length: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum_length:
        raise _field_problem(path, _("Enter a valid value."))
    normalized = value.strip()
    return normalized


def _pattern_text(
    value: object,
    path: str,
    *,
    maximum_length: int,
    pattern: re.Pattern[str],
) -> str:
    normalized = _text(value, path, maximum_length=maximum_length)
    if pattern.fullmatch(normalized) is None:
        raise _field_problem(path, _("Enter a valid value."))
    return normalized


def _controlled_key(value: object, path: str) -> str:
    return _pattern_text(
        value,
        path,
        maximum_length=64,
        pattern=_CONTROLLED_KEY_PATTERN,
    )


def _enum_text(
    value: object,
    path: str,
    allowed: frozenset[str],
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _field_problem(path, _("Select a supported value."))
    return value


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _field_problem(path, _("Select a supported value."))
    return value


def _optional_query_boolean(value: object, path: str) -> bool | None:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise _field_problem(path, _("Select a supported value."))


def _query_limit(value: object) -> int:
    if value is None:
        return 50
    if type(value) is int:
        parsed = value
    elif (
        isinstance(value, str)
        and re.fullmatch(r"[1-9][0-9]{0,2}", value) is not None
    ):
        parsed = int(value)
    else:
        raise _field_problem("limit", _("Enter a valid value."))
    if not 1 <= parsed <= 100:
        raise _field_problem("limit", _("Enter a valid value."))
    return parsed


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
