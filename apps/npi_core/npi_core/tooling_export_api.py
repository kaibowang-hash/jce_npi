from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import BinaryPayload, frappe_binary_call, frappe_domain_call
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
    require_tooling_export_routes_enabled,
    response_request_id,
)
from npi_core.tooling.domain import ToolingUnavailable
from npi_core.tooling.export_domain import (
    TOOLING_LIST_COLUMN_IDS,
    ToolingExportMode,
    ToolingExportReference,
    ToolingListFilter,
    ToolingListGroupKey,
    ToolingListPreferenceSnapshot,
    ToolingListSortDirection,
    ToolingListSortKey,
    ToolingListViewId,
)
from npi_core.tooling.export_repository import FrappeToolingExportRepository


_HASH = re.compile(r"^[a-f0-9]{64}$")
_LIST_FIELDS = frozenset(
    {"viewId", "search", "sortKey", "sortDirection", "groupKey", "pageSize", "cursor"}
)
_PREFERENCE_FIELDS = frozenset(
    {"expectedVersion", "expectedSnapshotHash", "preference"}
)
_PREFERENCE_SNAPSHOT_FIELDS = frozenset(
    {
        "gridId",
        "tableSchemaVersion",
        "viewId",
        "filter",
        "columnOrder",
        "hiddenColumns",
        "columnWidths",
    }
)
_FILTER_FIELDS = frozenset(
    {"viewId", "search", "sortKey", "sortDirection", "groupKey"}
)
_COLUMN_WIDTH_FIELDS = frozenset({"columnId", "width"})
_EXPORT_FIELDS = frozenset({"mode", "selection", "filter", "querySnapshotHash"})
_SELECTION_REFERENCE_FIELDS = frozenset({"toolingMasterGlobalId", "snapshotHash"})
_DOWNLOAD_FIELDS = frozenset({"expectedSnapshotHash"})


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

    def tooling_list(self, project_id: UUID, **values: Any) -> dict[str, object] | None: ...

    def tooling_list_preference(
        self, project_id: UUID, view_id: ToolingListViewId
    ) -> dict[str, object] | None: ...

    def save_tooling_list_preference(
        self, project_id: UUID, view_id: ToolingListViewId, **values: Any
    ) -> dict[str, object] | None: ...

    def create_tooling_export_package(
        self, project_id: UUID, **values: Any
    ) -> _Outcome | None: ...

    def tooling_export_package_content(
        self, project_id: UUID, package_id: UUID, **values: Any
    ) -> Any: ...


_repository_factory = FrappeToolingExportRepository


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_list(
    viewId: Any = "all",
    search: Any = "",
    sortKey: Any = "title",
    sortDirection: Any = "asc",
    groupKey: Any = "none",
    pageSize: Any = 50,
    cursor: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_tooling_export_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        if not repository.authorize_scope(project_id):
            raise ToolingUnavailable()
        reject_unexpected_request_fields(_LIST_FIELDS, request_fields)
        outcome = repository.tooling_list(
            project_id,
            filter_spec=ToolingListFilter(
                view_id=_enum(viewId, ToolingListViewId, "viewId"),
                search=_string(search, "search", allow_empty=True),
                sort_key=_enum(sortKey, ToolingListSortKey, "sortKey"),
                sort_direction=_enum(
                    sortDirection,
                    ToolingListSortDirection,
                    "sortDirection",
                ),
                group_key=_enum(groupKey, ToolingListGroupKey, "groupKey"),
            ),
            page_size=_integer(pageSize, "pageSize", minimum=1, maximum=100),
            cursor=_optional_string(cursor, "cursor", maximum=500),
        )
        if outcome is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return outcome

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_tooling_list_preference(**request_fields: Any) -> dict[str, Any] | None:
    return _preference_query(request_fields)


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def set_tooling_list_preference(
    expectedVersion: Any = None,
    expectedSnapshotHash: Any = None,
    preference: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_tooling_export_routes_enabled()
        actor = authenticated_user()
        require_csrf_token()
        principal = authenticated_principal(actor)
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        if not repository.authorize_scope(project_id):
            raise ToolingUnavailable()
        reject_unexpected_request_fields(_PREFERENCE_FIELDS, request_fields)
        require_request_fields(_PREFERENCE_FIELDS, request_fields)
        view_id = _opaque_route_view_id()
        outcome = repository.save_tooling_list_preference(
            project_id,
            view_id,
            expected_version=_integer(
                expectedVersion,
                "expectedVersion",
                minimum=0,
                maximum=2_147_483_647,
            ),
            expected_snapshot_hash=_optional_hash(
                expectedSnapshotHash,
                "expectedSnapshotHash",
            ),
            preference=_preference(preference, expected_view=view_id),
        )
        if outcome is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return outcome

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_tooling_export_package(
    mode: Any = None,
    selection: Any = None,
    filter: Any = None,
    querySnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> dict[str, Any]:
        require_tooling_export_routes_enabled()
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
        reject_unexpected_request_fields(_EXPORT_FIELDS, request_fields)
        require_request_fields(frozenset({"mode"}), request_fields)
        export_mode = _enum(mode, ToolingExportMode, "mode")
        if export_mode is ToolingExportMode.SELECTION:
            require_request_fields(frozenset({"mode", "selection"}), request_fields)
            parsed_selection = _selection(selection)
            parsed_filter = None
            parsed_query_hash = None
            if filter is not None or querySnapshotHash is not None:
                raise _field(
                    "mode",
                    _("Choose either an exact selection or the current filtered result."),
                )
        else:
            require_request_fields(
                frozenset({"mode", "filter", "querySnapshotHash"}),
                request_fields,
            )
            parsed_selection = None
            parsed_filter = _filter(filter)
            parsed_query_hash = _hash(querySnapshotHash, "querySnapshotHash")
            if selection is not None:
                raise _field(
                    "mode",
                    _("Choose either an exact selection or the current filtered result."),
                )
        outcome = repository.create_tooling_export_package(
            project_id,
            idempotency_key_hash=actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
            mode=export_mode,
            selection=parsed_selection,
            filter_spec=parsed_filter,
            query_snapshot_hash=parsed_query_hash,
        )
        if outcome is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return outcome.response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def download_tooling_export_package(
    expectedSnapshotHash: Any = None,
    **request_fields: Any,
) -> None:
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> BinaryPayload:
        require_tooling_export_routes_enabled()
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
        reject_unexpected_request_fields(_DOWNLOAD_FIELDS, request_fields)
        require_request_fields(_DOWNLOAD_FIELDS, request_fields)
        outcome = repository.tooling_export_package_content(
            project_id,
            _opaque_route_uuid("package_id"),
            idempotency_key_hash=actor_idempotency_key_hash(
                actor,
                frappe.get_request_header("Idempotency-Key"),
            ),
            expected_snapshot_hash=_hash(
                expectedSnapshotHash,
                "expectedSnapshotHash",
            ),
        )
        if outcome is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return BinaryPayload(
            content=outcome.content,
            file_name=outcome.file_name,
            mime_type=outcome.mime_type,
            disposition="attachment",
            headers={
                "Content-Disposition": f'attachment; filename="{outcome.file_name}"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "Referrer-Policy": "no-referrer",
            },
        )

    frappe_binary_call(handle, response_headers=headers)


def _preference_query(request_fields: dict[str, Any]) -> dict[str, Any] | None:
    headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_tooling_export_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        request_id = _request_id()
        repository = _new_repository(principal, request_id)
        project_id = _opaque_route_uuid("project_id")
        if not repository.authorize_scope(project_id):
            raise ToolingUnavailable()
        reject_unexpected_request_fields(frozenset(), request_fields)
        outcome = repository.tooling_list_preference(
            project_id,
            _opaque_route_view_id(),
        )
        if outcome is None:
            raise ToolingUnavailable()
        headers["X-Request-ID"] = request_id
        return outcome

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _new_repository(principal: Principal, request_id: str) -> _Repository:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Tooling export request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _preference(
    value: object,
    *,
    expected_view: ToolingListViewId,
) -> ToolingListPreferenceSnapshot:
    parsed = _mapping(
        value,
        "preference",
        allowed=_PREFERENCE_SNAPSHOT_FIELDS,
        required=_PREFERENCE_SNAPSHOT_FIELDS,
    )
    view_id = _enum(parsed["viewId"], ToolingListViewId, "preference.viewId")
    if view_id is not expected_view:
        raise _field(
            "preference.viewId",
            _("The Tooling List filter must match the saved view."),
        )
    widths = _sequence(parsed["columnWidths"], "preference.columnWidths", maximum=9)
    return ToolingListPreferenceSnapshot(
        view_id=view_id,
        filter_spec=_filter(parsed["filter"], path="preference.filter"),
        column_order=tuple(
            _string_sequence(
                parsed["columnOrder"],
                "preference.columnOrder",
                maximum=len(TOOLING_LIST_COLUMN_IDS),
            )
        ),
        hidden_columns=tuple(
            _string_sequence(
                parsed["hiddenColumns"],
                "preference.hiddenColumns",
                maximum=len(TOOLING_LIST_COLUMN_IDS),
            )
        ),
        column_widths=tuple(
            (
                str(
                    _mapping(
                        item,
                        f"preference.columnWidths[{index}]",
                        allowed=_COLUMN_WIDTH_FIELDS,
                        required=_COLUMN_WIDTH_FIELDS,
                    )["columnId"]
                ),
                _integer(
                    _mapping(
                        item,
                        f"preference.columnWidths[{index}]",
                        allowed=_COLUMN_WIDTH_FIELDS,
                        required=_COLUMN_WIDTH_FIELDS,
                    )["width"],
                    f"preference.columnWidths[{index}].width",
                    minimum=56,
                    maximum=480,
                ),
            )
            for index, item in enumerate(widths)
        ),
        grid_id=_string(parsed["gridId"], "preference.gridId"),
        table_schema_version=_string(
            parsed["tableSchemaVersion"],
            "preference.tableSchemaVersion",
        ),
    )


def _filter(value: object, *, path: str = "filter") -> ToolingListFilter:
    parsed = _mapping(
        value,
        path,
        allowed=_FILTER_FIELDS,
        required=_FILTER_FIELDS,
    )
    return ToolingListFilter(
        view_id=_enum(parsed["viewId"], ToolingListViewId, f"{path}.viewId"),
        search=_string(parsed["search"], f"{path}.search", allow_empty=True),
        sort_key=_enum(parsed["sortKey"], ToolingListSortKey, f"{path}.sortKey"),
        sort_direction=_enum(
            parsed["sortDirection"],
            ToolingListSortDirection,
            f"{path}.sortDirection",
        ),
        group_key=_enum(parsed["groupKey"], ToolingListGroupKey, f"{path}.groupKey"),
    )


def _selection(value: object) -> tuple[ToolingExportReference, ...]:
    values = _sequence(value, "selection", minimum=1, maximum=100)
    return tuple(
        ToolingExportReference(
            tooling_master_global_id=_uuid(
                parsed["toolingMasterGlobalId"],
                f"selection[{index}].toolingMasterGlobalId",
            ),
            snapshot_hash=_hash(
                parsed["snapshotHash"],
                f"selection[{index}].snapshotHash",
            ),
        )
        for index, item in enumerate(values)
        for parsed in (
            _mapping(
                item,
                f"selection[{index}]",
                allowed=_SELECTION_REFERENCE_FIELDS,
                required=_SELECTION_REFERENCE_FIELDS,
            ),
        )
    )


def _mapping(
    value: object,
    path: str,
    *,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, object]:
    parsed = frappe.parse_json(value)
    if not isinstance(parsed, Mapping):
        raise _field(path, _("Enter a valid object."))
    result = dict(parsed)
    unexpected = sorted(set(result) - allowed)
    missing = sorted(required - set(result))
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
    return result


def _sequence(
    value: object,
    path: str,
    *,
    minimum: int = 0,
    maximum: int,
) -> tuple[object, ...]:
    parsed = frappe.parse_json(value)
    if (
        not isinstance(parsed, Sequence)
        or isinstance(parsed, (str, bytes, bytearray))
        or not minimum <= len(parsed) <= maximum
    ):
        raise _field(path, _("Enter a valid list."))
    return tuple(parsed)


def _string_sequence(value: object, path: str, *, maximum: int) -> tuple[str, ...]:
    parsed = _sequence(value, path, maximum=maximum)
    if not all(isinstance(item, str) for item in parsed):
        raise _field(path, _("Enter a valid list."))
    return tuple(parsed)


def _opaque_route_uuid(name: str) -> UUID:
    value = _opaque_route_value(name)
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ToolingUnavailable() from error
    if str(parsed) != value.casefold():
        raise ToolingUnavailable()
    return parsed


def _opaque_route_view_id() -> ToolingListViewId:
    value = _opaque_route_value("view_id")
    try:
        return ToolingListViewId(value)
    except ValueError as error:
        raise ToolingUnavailable() from error


def _opaque_route_value(name: str) -> str:
    params = getattr(frappe.flags, "npi_route_params", None)
    value = params.get(name) if hasattr(params, "get") else None
    if not isinstance(value, str) or not value:
        raise ToolingUnavailable()
    return value


def _request_id() -> str:
    return str(_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))


def _uuid(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field(path, _("Enter a valid global ID."))
    return parsed


def _enum(value: object, enum_type, path: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise _field(path, _("Select a supported value.")) from error


def _integer(
    value: object,
    path: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise _field(path, _("Enter a whole number.")) from error
    if isinstance(value, bool) or str(parsed) != str(value) or not minimum <= parsed <= maximum:
        raise _field(path, _("Enter a whole number within the supported range."))
    return parsed


def _string(
    value: object,
    path: str,
    *,
    allow_empty: bool = False,
    maximum: int = 500,
) -> str:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid value."))
    if (not allow_empty and not value) or len(value) > maximum:
        raise _field(path, _("Enter a valid value."))
    return value


def _optional_string(value: object, path: str, *, maximum: int) -> str | None:
    if value in (None, ""):
        return None
    return _string(value, path, maximum=maximum)


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field(path, _("Enter a valid SHA-256 value."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
