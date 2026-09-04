from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import ProjectType, actor_idempotency_key_hash
from npi_core.readiness.domain import (
    MAX_CATEGORIES,
    MAX_ITEMS,
    MAX_REQUIREMENTS,
    ReadinessApplicabilitySelector,
    ReadinessBlockingLevel,
    ReadinessCategoryDefinition,
    ReadinessCompletionRule,
    ReadinessEvidenceRequirement,
    ReadinessItemDefinition,
    ReadinessItemState,
    ReadinessSourceKind,
)
from npi_core.readiness.request_validation import (
    closed_payload,
    parse_source_requests,
)
from npi_core.readiness.response_validation import (
    validate_command_response,
    validate_template_catalog_response,
    validate_workspace_response,
)
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    response_request_id,
)


_HASH = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CREATE_TEMPLATE_FIELDS = frozenset(
    {"templateCode", "title", "applicability", "categories", "items"}
)
_EDIT_TEMPLATE_FIELDS = frozenset(
    {"expectedOptimisticVersion", "title", "applicability", "categories", "items"}
)
_PUBLISH_TEMPLATE_FIELDS = frozenset({"expectedOptimisticVersion"})
_INITIALIZE_FIELDS = frozenset(
    {
        "templateRevisionGlobalId",
        "templateVersion",
        "templateSnapshotHash",
        "industryKey",
        "assignments",
    }
)
_REVISE_FIELDS = frozenset(
    {
        "expectedInstanceVersion",
        "expectedRevisionGlobalId",
        "expectedRevisionSnapshotHash",
        "itemKey",
        "ownerMemberGlobalId",
        "dueDate",
        "state",
        "confirmationValue",
        "sources",
    }
)
_APPLICABILITY_FIELDS = frozenset(
    {"projectTypes", "customerReferenceKeys", "industryKeys"}
)
_CATEGORY_FIELDS = frozenset({"key", "title"})
_REQUIREMENT_FIELDS = frozenset(
    {"key", "acceptedSourceKinds", "minimumCount", "unavailableBlocks"}
)
_ITEM_FIELDS = frozenset(
    {
        "key",
        "title",
        "categoryKey",
        "weight",
        "required",
        "blockingLevel",
        "gateKey",
        "completionRule",
        "applicability",
        "evidenceRequirements",
    }
)
_ASSIGNMENT_FIELDS = frozenset({"itemKey", "ownerMemberGlobalId", "dueDate"})


class ReadinessRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "READINESS_ROUTES_DISABLED",
            _("The NPI Readiness workspace is temporarily unavailable."),
            _("The routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


class ReadinessUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "READINESS_UNAVAILABLE",
            _("The Project is unavailable for this NPI Readiness Instance."),
        )


class ReadinessTemplateUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "READINESS_TEMPLATE_UNAVAILABLE",
            _("The NPI Readiness Template is unavailable."),
        )


class _Repository(Protocol):
    def template_catalog(self, project_id: UUID) -> dict[str, Any] | None: ...

    def create_template(self, **values: Any): ...

    def edit_template(self, template_id: UUID, template_version: int, **values: Any): ...

    def publish_template(self, template_id: UUID, template_version: int, **values: Any): ...

    def readiness_workspace(self, project_id: UUID) -> dict[str, Any] | None: ...

    def initialize_readiness(self, project_id: UUID, **values: Any): ...

    def revise_readiness(self, project_id: UUID, instance_id: UUID, **values: Any): ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _Repository:
    from npi_core.readiness.frappe_repository import FrappeReadinessRepository

    return FrappeReadinessRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_readiness_templates(
    projectId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_api_user(principal)
        reject_unexpected_request_fields(frozenset({"projectId"}), request_fields)
        require_request_fields(frozenset({"projectId"}), request_fields)
        request_id, repository = _new_repository(principal)
        project_id = _uuid(projectId, "projectId")
        response = repository.template_catalog(project_id)
        if response is None:
            raise ReadinessUnavailable()
        headers["X-Request-ID"] = request_id
        return validate_template_catalog_response(
            response,
            project_global_id=str(project_id),
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_readiness_template(
    templateCode: Any = None,
    title: Any = None,
    applicability: Any = None,
    categories: Any = None,
    items: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "templateCode": templateCode,
        "title": title,
        "applicability": applicability,
        "categories": categories,
        "items": items,
    }
    return _command(
        allowed_fields=_CREATE_TEMPLATE_FIELDS,
        required_fields=_CREATE_TEMPLATE_FIELDS,
        request_fields=request_fields,
        success_status=201,
        unavailable=ReadinessTemplateUnavailable,
        validate_response=lambda response: validate_command_response(
            "readiness_template.create",
            response,
        ),
        invoke=lambda repository, key_hash: repository.create_template(
            idempotency_key_hash=key_hash,
            template_code=_text(values["templateCode"], "templateCode", 64),
            title=_text(values["title"], "title", 200),
            applicability=_applicability(values["applicability"], "applicability"),
            categories=_categories(values["categories"]),
            items=_items(values["items"]),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def edit_readiness_template(
    expectedOptimisticVersion: Any = None,
    title: Any = None,
    applicability: Any = None,
    categories: Any = None,
    items: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedOptimisticVersion": expectedOptimisticVersion,
        "title": title,
        "applicability": applicability,
        "categories": categories,
        "items": items,
    }
    return _command(
        allowed_fields=_EDIT_TEMPLATE_FIELDS,
        required_fields=_EDIT_TEMPLATE_FIELDS,
        request_fields=request_fields,
        success_status=200,
        unavailable=ReadinessTemplateUnavailable,
        validate_response=lambda response: validate_command_response(
            "readiness_template.edit",
            response,
            template_global_id=str(
                _route_uuid("template_id", ReadinessTemplateUnavailable)
            ),
            template_version=_route_positive(
                "template_version",
                ReadinessTemplateUnavailable,
            ),
        ),
        invoke=lambda repository, key_hash: repository.edit_template(
            _route_uuid("template_id", ReadinessTemplateUnavailable),
            _route_positive("template_version", ReadinessTemplateUnavailable),
            idempotency_key_hash=key_hash,
            expected_optimistic_version=_positive(
                values["expectedOptimisticVersion"], "expectedOptimisticVersion"
            ),
            title=_text(values["title"], "title", 200),
            applicability=_applicability(values["applicability"], "applicability"),
            categories=_categories(values["categories"]),
            items=_items(values["items"]),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def publish_readiness_template(
    expectedOptimisticVersion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        allowed_fields=_PUBLISH_TEMPLATE_FIELDS,
        required_fields=_PUBLISH_TEMPLATE_FIELDS,
        request_fields=request_fields,
        success_status=200,
        unavailable=ReadinessTemplateUnavailable,
        validate_response=lambda response: validate_command_response(
            "readiness_template.publish",
            response,
            template_global_id=str(
                _route_uuid("template_id", ReadinessTemplateUnavailable)
            ),
            template_version=_route_positive(
                "template_version",
                ReadinessTemplateUnavailable,
            ),
        ),
        invoke=lambda repository, key_hash: repository.publish_template(
            _route_uuid("template_id", ReadinessTemplateUnavailable),
            _route_positive("template_version", ReadinessTemplateUnavailable),
            idempotency_key_hash=key_hash,
            expected_optimistic_version=_positive(
                expectedOptimisticVersion, "expectedOptimisticVersion"
            ),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_readiness(**request_fields: Any) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        _require_api_user(principal)
        reject_unexpected_request_fields(frozenset(), request_fields)
        request_id, repository = _new_repository(principal)
        project_id = _route_uuid("project_id", ReadinessUnavailable)
        response = repository.readiness_workspace(project_id)
        if response is None:
            raise ReadinessUnavailable()
        headers["X-Request-ID"] = request_id
        return validate_workspace_response(
            response,
            project_global_id=str(project_id),
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def initialize_project_readiness(
    templateRevisionGlobalId: Any = None,
    templateVersion: Any = None,
    templateSnapshotHash: Any = None,
    industryKey: Any = None,
    assignments: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "templateRevisionGlobalId": templateRevisionGlobalId,
        "templateVersion": templateVersion,
        "templateSnapshotHash": templateSnapshotHash,
        "industryKey": industryKey,
        "assignments": assignments,
    }
    return _command(
        allowed_fields=_INITIALIZE_FIELDS,
        required_fields=_INITIALIZE_FIELDS,
        request_fields=request_fields,
        success_status=201,
        unavailable=ReadinessUnavailable,
        validate_response=lambda response: validate_command_response(
            "readiness_instance.initialize",
            response,
            project_global_id=str(
                _route_uuid("project_id", ReadinessUnavailable)
            ),
        ),
        invoke=lambda repository, key_hash: repository.initialize_readiness(
            _route_uuid("project_id", ReadinessUnavailable),
            idempotency_key_hash=key_hash,
            template_revision_global_id=_uuid(
                values["templateRevisionGlobalId"], "templateRevisionGlobalId"
            ),
            template_version=_positive(values["templateVersion"], "templateVersion"),
            template_snapshot_hash=_hash(
                values["templateSnapshotHash"], "templateSnapshotHash"
            ),
            industry_key=_key(values["industryKey"], "industryKey"),
            assignments=_assignments(values["assignments"]),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def revise_project_readiness(
    expectedInstanceVersion: Any = None,
    expectedRevisionGlobalId: Any = None,
    expectedRevisionSnapshotHash: Any = None,
    itemKey: Any = None,
    ownerMemberGlobalId: Any = None,
    dueDate: Any = None,
    state: Any = None,
    confirmationValue: Any = None,
    sources: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    values = {
        "expectedInstanceVersion": expectedInstanceVersion,
        "expectedRevisionGlobalId": expectedRevisionGlobalId,
        "expectedRevisionSnapshotHash": expectedRevisionSnapshotHash,
        "itemKey": itemKey,
        "ownerMemberGlobalId": ownerMemberGlobalId,
        "dueDate": dueDate,
        "state": state,
        "confirmationValue": confirmationValue,
        "sources": sources,
    }
    return _command(
        allowed_fields=_REVISE_FIELDS,
        required_fields=_REVISE_FIELDS,
        request_fields=request_fields,
        success_status=201,
        unavailable=ReadinessUnavailable,
        validate_response=lambda response: validate_command_response(
            "readiness_instance.revise",
            response,
            project_global_id=str(
                _route_uuid("project_id", ReadinessUnavailable)
            ),
            instance_global_id=str(
                _route_uuid("instance_id", ReadinessUnavailable)
            ),
        ),
        invoke=lambda repository, key_hash: repository.revise_readiness(
            _route_uuid("project_id", ReadinessUnavailable),
            _route_uuid("instance_id", ReadinessUnavailable),
            idempotency_key_hash=key_hash,
            expected_instance_version=_positive(
                values["expectedInstanceVersion"], "expectedInstanceVersion"
            ),
            expected_revision_global_id=_uuid(
                values["expectedRevisionGlobalId"], "expectedRevisionGlobalId"
            ),
            expected_revision_snapshot_hash=_hash(
                values["expectedRevisionSnapshotHash"],
                "expectedRevisionSnapshotHash",
            ),
            item_key=_key(values["itemKey"], "itemKey"),
            owner_member_global_id=_uuid(
                values["ownerMemberGlobalId"], "ownerMemberGlobalId"
            ),
            due_date=_date(values["dueDate"], "dueDate"),
            state=_item_state(values["state"], "state"),
            confirmation_value=_optional_text(
                values["confirmationValue"], "confirmationValue", 4000
            ),
            source_requests=parse_source_requests(values["sources"]),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET", "POST", "PUT"])
def readiness_routes_disabled(**_request_fields: Any) -> dict[str, Any] | None:
    def handle() -> dict[str, Any]:
        raise ReadinessRoutesDisabled()

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers={"X-Request-ID": response_request_id()},
    )


def _command(
    *,
    allowed_fields: frozenset[str],
    required_fields: frozenset[str],
    request_fields: dict[str, Any],
    success_status: int,
    unavailable: type[NpiProblem],
    validate_response: Callable[[object], dict[str, Any]],
    invoke,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        _require_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        _require_administrator(principal)
        reject_unexpected_request_fields(allowed_fields, request_fields)
        require_request_fields(required_fields, request_fields)
        request_id, repository = _new_repository(principal)
        outcome = invoke(
            repository,
            actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
        )
        if outcome is None:
            raise unavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The NPI Readiness command response is invalid.")
        response = validate_response(outcome.response)
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=success_status,
        response_headers=headers,
    )


def _new_repository(principal: Principal) -> tuple[str, _Repository]:
    request_id = str(_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The NPI Readiness request has no active trace identity.")
    return request_id, _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _routes_are_disabled() -> bool:
    configuration = getattr(frappe, "conf", None)
    value = (
        configuration.get("npi_p7_05_routes_disabled")
        if hasattr(configuration, "get")
        else None
    )
    return value is not False


def _require_routes_enabled() -> None:
    if _routes_are_disabled():
        raise ReadinessRoutesDisabled()


def _require_api_user(principal: Principal) -> None:
    if principal.is_external or "NPI API User" not in principal.roles:
        raise PermissionDenied()


def _require_administrator(principal: Principal) -> None:
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()


def _route_uuid(name: str, unavailable: type[NpiProblem]) -> UUID:
    value = _route_value(name)
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise unavailable() from error
    if str(parsed) != str(value).casefold():
        raise unavailable()
    return parsed


def _route_positive(name: str, unavailable: type[NpiProblem]) -> int:
    value = _route_value(name)
    if not isinstance(value, str) or not value.isdecimal():
        raise unavailable()
    parsed = int(value)
    if parsed < 1 or str(parsed) != value:
        raise unavailable()
    return parsed


def _route_value(name: str) -> object:
    params = getattr(frappe.flags, "npi_route_params", None)
    return params.get(name) if hasattr(params, "get") else None


def _applicability(value: object, path: str) -> ReadinessApplicabilitySelector:
    record = closed_payload(value, path, _APPLICABILITY_FIELDS)
    project_types = tuple(
        _project_type(item, f"{path}.projectTypes[{index}]")
        for index, item in enumerate(
            _array(record["projectTypes"], f"{path}.projectTypes", 0, 20)
        )
    )
    customer_keys = tuple(
        _text(item, f"{path}.customerReferenceKeys[{index}]", 256)
        for index, item in enumerate(
            _array(
                record["customerReferenceKeys"],
                f"{path}.customerReferenceKeys",
                0,
                100,
            )
        )
    )
    industry_keys = tuple(
        _key(item, f"{path}.industryKeys[{index}]")
        for index, item in enumerate(
            _array(record["industryKeys"], f"{path}.industryKeys", 0, 100)
        )
    )
    return ReadinessApplicabilitySelector(
        project_types=project_types,
        customer_reference_keys=customer_keys,
        industry_keys=industry_keys,
    )


def _categories(value: object) -> tuple[ReadinessCategoryDefinition, ...]:
    return tuple(
        ReadinessCategoryDefinition(
            key=_key(record["key"], f"categories[{index}].key"),
            title=_text(record["title"], f"categories[{index}].title", 200),
        )
        for index, record in (
            (
                index,
                closed_payload(item, f"categories[{index}]", _CATEGORY_FIELDS),
            )
            for index, item in enumerate(
                _array(value, "categories", 1, MAX_CATEGORIES)
            )
        )
    )


def _items(value: object) -> tuple[ReadinessItemDefinition, ...]:
    result: list[ReadinessItemDefinition] = []
    for index, item in enumerate(_array(value, "items", 1, MAX_ITEMS)):
        path = f"items[{index}]"
        record = closed_payload(item, path, _ITEM_FIELDS)
        result.append(
            ReadinessItemDefinition(
                key=_key(record["key"], f"{path}.key"),
                title=_text(record["title"], f"{path}.title", 240),
                category_key=_key(record["categoryKey"], f"{path}.categoryKey"),
                weight=_positive(record["weight"], f"{path}.weight"),
                required=_boolean(record["required"], f"{path}.required"),
                blocking_level=_blocking_level(
                    record["blockingLevel"], f"{path}.blockingLevel"
                ),
                gate_key=_key(record["gateKey"], f"{path}.gateKey"),
                completion_rule=_completion_rule(
                    record["completionRule"], f"{path}.completionRule"
                ),
                applicability=_applicability(
                    record["applicability"], f"{path}.applicability"
                ),
                evidence_requirements=_requirements(
                    record["evidenceRequirements"],
                    f"{path}.evidenceRequirements",
                ),
            )
        )
    return tuple(result)


def _requirements(
    value: object,
    path: str,
) -> tuple[ReadinessEvidenceRequirement, ...]:
    result: list[ReadinessEvidenceRequirement] = []
    for index, item in enumerate(_array(value, path, 0, MAX_REQUIREMENTS)):
        item_path = f"{path}[{index}]"
        record = closed_payload(item, item_path, _REQUIREMENT_FIELDS)
        kinds = tuple(
            _source_kind(source, f"{item_path}.acceptedSourceKinds[{kind_index}]")
            for kind_index, source in enumerate(
                _array(
                    record["acceptedSourceKinds"],
                    f"{item_path}.acceptedSourceKinds",
                    1,
                    30,
                )
            )
        )
        result.append(
            ReadinessEvidenceRequirement(
                key=_key(record["key"], f"{item_path}.key"),
                accepted_source_kinds=kinds,
                minimum_count=_positive(
                    record["minimumCount"], f"{item_path}.minimumCount"
                ),
                unavailable_blocks=_boolean(
                    record["unavailableBlocks"], f"{item_path}.unavailableBlocks"
                ),
            )
        )
    return tuple(result)


def _assignments(value: object) -> dict[str, tuple[UUID, date]]:
    result: dict[str, tuple[UUID, date]] = {}
    for index, item in enumerate(_array(value, "assignments", 1, MAX_ITEMS)):
        path = f"assignments[{index}]"
        record = closed_payload(item, path, _ASSIGNMENT_FIELDS)
        key = _key(record["itemKey"], f"{path}.itemKey")
        if key in result:
            raise _field("assignments", _("Values must be unique."))
        result[key] = (
            _uuid(record["ownerMemberGlobalId"], f"{path}.ownerMemberGlobalId"),
            _date(record["dueDate"], f"{path}.dueDate"),
        )
    return result


def _array(
    value: object,
    path: str,
    minimum: int,
    maximum: int,
) -> list[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not minimum <= len(value) <= maximum
    ):
        raise _field(path, _("Enter a valid bounded list."))
    return list(value)


def _project_type(value: object, path: str) -> ProjectType:
    try:
        return ProjectType(str(value))
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error


def _source_kind(value: object, path: str) -> ReadinessSourceKind:
    try:
        return ReadinessSourceKind(str(value))
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error


def _blocking_level(value: object, path: str) -> ReadinessBlockingLevel:
    try:
        return ReadinessBlockingLevel(str(value))
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error


def _completion_rule(value: object, path: str) -> ReadinessCompletionRule:
    try:
        return ReadinessCompletionRule(str(value))
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error


def _item_state(value: object, path: str) -> ReadinessItemState:
    try:
        state = ReadinessItemState(str(value))
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error
    if state is ReadinessItemState.NOT_APPLICABLE:
        raise _field(path, _("Select a supported value."))
    return state


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
        raise _field(path, _("Enter a valid value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, path, maximum)


def _key(value: object, path: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise _field(path, _("Enter a valid value."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field(path, _("Enter a valid SHA-256 hash."))
    return value


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != value.casefold():
        raise _field(path, _("Enter a valid global ID."))
    return parsed


def _date(value: object, path: str) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise _field(path, _("Enter a valid date.")) from error
        if parsed.isoformat() == value:
            return parsed
    raise _field(path, _("Enter a valid date."))


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
