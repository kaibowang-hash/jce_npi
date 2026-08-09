from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Iterable, TypeVar
from uuid import UUID

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.domain import sha256_json

try:
    from frappe import _
except ImportError:  # Keeps this policy layer independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


TOOLING_LIST_GRID_ID = "tooling-list"
TOOLING_LIST_TABLE_SCHEMA_VERSION = "tooling-list-grid-v1"
TOOLING_OBJECT_PACKAGE_SCHEMA_VERSION = "tooling-object-package-v1"
TOOLING_OBJECT_PACKAGE_MIME_TYPE = "application/zip"
TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY = "internal_project"
TOOLING_OBJECT_PACKAGE_VALIDITY = timedelta(hours=1)
MAX_TOOLING_EXPORT_OBJECTS = 100
MAX_TOOLING_LIST_SEARCH_LENGTH = 120
TOOLING_LIST_COLUMN_IDS = (
    "selection",
    "tooling",
    "applicability",
    "part_revisions",
    "physical_sets",
    "design_revisions",
    "origin",
    "source",
    "action",
)
REQUIRED_TOOLING_LIST_COLUMN_IDS = frozenset({"selection", "tooling", "action"})
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_E = TypeVar("_E", bound=StrEnum)


class ToolingListViewId(StrEnum):
    ALL = "all"
    MISSING_APPLICABILITY = "missing_applicability"
    SINGLE_PART = "single_part"
    SHARED_PARTS = "shared_parts"
    MISSING_PHYSICAL_SET = "missing_physical_set"
    SINGLE_PHYSICAL_SET = "single_physical_set"
    MULTIPLE_PHYSICAL_SETS = "multiple_physical_sets"
    MISSING_DESIGN_REVISION = "missing_design_revision"
    HAS_DESIGN_REVISION = "has_design_revision"
    CUSTOMER_OWNED_SET = "customer_owned_set"


class ToolingListSortKey(StrEnum):
    TITLE = "title"
    APPLICABILITY_COUNT = "applicability_count"
    PHYSICAL_SET_COUNT = "physical_set_count"
    LATEST_REVISION_NUMBER = "latest_revision_number"


class ToolingListSortDirection(StrEnum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class ToolingListGroupKey(StrEnum):
    NONE = "none"
    APPLICABILITY_SCOPE = "applicability_scope"
    PHYSICAL_SET_PRESENCE = "physical_set_presence"
    DESIGN_REVISION_PRESENCE = "design_revision_presence"


class ToolingExportMode(StrEnum):
    SELECTION = "selection"
    FILTERED = "filtered"


class ToolingExportLanguage(StrEnum):
    ENGLISH = "en"
    SIMPLIFIED_CHINESE = "zh"
    TRADITIONAL_CHINESE = "zh-TW"


class ToolingSource(StrEnum):
    MANUAL = "manual"
    CONTROLLED_XLSX_IMPORT = "controlled_xlsx_import"


class ToolingExportOperation(StrEnum):
    CREATE = "tooling_export_package.create"
    DOWNLOAD = "tooling_export_package.download"


@dataclass(frozen=True, slots=True)
class ToolingListFilter:
    view_id: ToolingListViewId = ToolingListViewId.ALL
    search: str = ""
    sort_key: ToolingListSortKey = ToolingListSortKey.TITLE
    sort_direction: ToolingListSortDirection = ToolingListSortDirection.ASCENDING
    group_key: ToolingListGroupKey = ToolingListGroupKey.NONE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "view_id",
            _enum(self.view_id, ToolingListViewId, "viewId"),
        )
        if not isinstance(self.search, str):
            raise _problem("search", _("Enter a valid Tooling List search."))
        normalized_search = " ".join(self.search.split())
        if len(normalized_search) > MAX_TOOLING_LIST_SEARCH_LENGTH:
            raise _problem("search", _("The Tooling List search is too long."))
        object.__setattr__(self, "search", normalized_search)
        object.__setattr__(
            self,
            "sort_key",
            _enum(self.sort_key, ToolingListSortKey, "sortKey"),
        )
        object.__setattr__(
            self,
            "sort_direction",
            _enum(self.sort_direction, ToolingListSortDirection, "sortDirection"),
        )
        object.__setattr__(
            self,
            "group_key",
            _enum(self.group_key, ToolingListGroupKey, "groupKey"),
        )

    def snapshot_payload(self) -> dict[str, str]:
        return {
            "viewId": self.view_id.value,
            "search": self.search,
            "sortKey": self.sort_key.value,
            "sortDirection": self.sort_direction.value,
            "groupKey": self.group_key.value,
        }


@dataclass(frozen=True, slots=True)
class ToolingListRow:
    tooling_master_global_id: UUID
    tooling_master_snapshot_hash: str
    title: str
    project_global_id: UUID
    project_code: str
    originating_project_global_id: UUID
    applicability_count: int
    distinct_part_revision_count: int
    physical_set_count: int
    design_revision_count: int
    latest_revision_number: int | None
    customer_owned_set: bool
    source: ToolingSource

    def __post_init__(self) -> None:
        for fieldname in (
            "tooling_master_global_id",
            "project_global_id",
            "originating_project_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(
            self,
            "tooling_master_snapshot_hash",
            _hash(self.tooling_master_snapshot_hash, "toolingMasterSnapshotHash"),
        )
        object.__setattr__(self, "title", _text(self.title, "title", 140))
        object.__setattr__(
            self,
            "project_code",
            _text(self.project_code, "projectCode", 64),
        )
        for fieldname in (
            "applicability_count",
            "distinct_part_revision_count",
            "physical_set_count",
            "design_revision_count",
        ):
            object.__setattr__(
                self,
                fieldname,
                _non_negative(getattr(self, fieldname), _camel(fieldname)),
            )
        if self.latest_revision_number is not None:
            object.__setattr__(
                self,
                "latest_revision_number",
                _positive(self.latest_revision_number, "latestRevisionNumber"),
            )
        if not isinstance(self.customer_owned_set, bool):
            raise _problem("customerOwnedSet", _("Select true or false."))
        object.__setattr__(
            self,
            "source",
            _enum(self.source, ToolingSource, "source"),
        )

    def reference(self) -> ToolingExportReference:
        return ToolingExportReference(
            tooling_master_global_id=self.tooling_master_global_id,
            snapshot_hash=self.tooling_master_snapshot_hash,
        )

    def matches_view(self, view_id: ToolingListViewId) -> bool:
        return {
            ToolingListViewId.ALL: True,
            ToolingListViewId.MISSING_APPLICABILITY: self.applicability_count == 0,
            ToolingListViewId.SINGLE_PART: self.distinct_part_revision_count == 1,
            ToolingListViewId.SHARED_PARTS: self.distinct_part_revision_count > 1,
            ToolingListViewId.MISSING_PHYSICAL_SET: self.physical_set_count == 0,
            ToolingListViewId.SINGLE_PHYSICAL_SET: self.physical_set_count == 1,
            ToolingListViewId.MULTIPLE_PHYSICAL_SETS: self.physical_set_count > 1,
            ToolingListViewId.MISSING_DESIGN_REVISION: self.design_revision_count == 0,
            ToolingListViewId.HAS_DESIGN_REVISION: self.design_revision_count > 0,
            ToolingListViewId.CUSTOMER_OWNED_SET: self.customer_owned_set,
        }[_enum(view_id, ToolingListViewId, "viewId")]


@dataclass(frozen=True, slots=True)
class ToolingExportReference:
    tooling_master_global_id: UUID
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tooling_master_global_id",
            _uuid(self.tooling_master_global_id, "toolingMasterGlobalId"),
        )
        object.__setattr__(self, "snapshot_hash", _hash(self.snapshot_hash, "snapshotHash"))

    def snapshot_payload(self) -> dict[str, str]:
        return {
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ToolingExportSelection:
    references: tuple[ToolingExportReference, ...]

    def __post_init__(self) -> None:
        references = _bounded_references(self.references, "selection")
        identities = [item.tooling_master_global_id for item in references]
        if len(identities) != len(set(identities)):
            raise _problem(
                "selection",
                _("A Tooling Master can only be selected once."),
            )
        object.__setattr__(self, "references", references)

    @property
    def snapshot_hash(self) -> str:
        return sha256_json([item.snapshot_payload() for item in self.references])


@dataclass(frozen=True, slots=True)
class ToolingListPreferenceSnapshot:
    view_id: ToolingListViewId
    filter_spec: ToolingListFilter
    column_order: tuple[str, ...] = TOOLING_LIST_COLUMN_IDS
    hidden_columns: tuple[str, ...] = ()
    column_widths: tuple[tuple[str, int], ...] = ()
    grid_id: str = TOOLING_LIST_GRID_ID
    table_schema_version: str = TOOLING_LIST_TABLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "view_id", _enum(self.view_id, ToolingListViewId, "viewId"))
        if self.filter_spec.view_id != self.view_id:
            raise _problem(
                "filter.viewId",
                _("The Tooling List filter must match the saved view."),
            )
        if self.grid_id != TOOLING_LIST_GRID_ID:
            raise _problem("gridId", _("Select the supported Tooling List grid."))
        if self.table_schema_version != TOOLING_LIST_TABLE_SCHEMA_VERSION:
            raise _problem(
                "tableSchemaVersion",
                _("The Tooling List table schema is unsupported."),
            )
        order = _string_tuple(self.column_order, "columnOrder")
        if len(order) != len(TOOLING_LIST_COLUMN_IDS) or set(order) != set(
            TOOLING_LIST_COLUMN_IDS
        ):
            raise _problem(
                "columnOrder",
                _("Use each supported Tooling List column exactly once."),
            )
        object.__setattr__(self, "column_order", order)
        hidden = _string_tuple(self.hidden_columns, "hiddenColumns")
        if len(hidden) != len(set(hidden)) or not set(hidden).issubset(TOOLING_LIST_COLUMN_IDS):
            raise _problem("hiddenColumns", _("Select supported Tooling List columns."))
        if set(hidden).intersection(REQUIRED_TOOLING_LIST_COLUMN_IDS):
            raise _problem(
                "hiddenColumns",
                _("Required Tooling List columns cannot be hidden."),
            )
        object.__setattr__(self, "hidden_columns", hidden)
        widths = _column_widths(self.column_widths)
        object.__setattr__(self, "column_widths", widths)

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "gridId": self.grid_id,
            "tableSchemaVersion": self.table_schema_version,
            "viewId": self.view_id.value,
            "filter": self.filter_spec.snapshot_payload(),
            "columnOrder": list(self.column_order),
            "hiddenColumns": list(self.hidden_columns),
            "columnWidths": {
                column_id: width for column_id, width in self.column_widths
            },
        }


@dataclass(frozen=True, slots=True)
class ToolingExportPackageIdentity:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    actor_user_id: str
    mode: ToolingExportMode
    language: ToolingExportLanguage
    query_snapshot_hash: str | None
    references: tuple[ToolingExportReference, ...]
    generated_at: datetime
    expires_at: datetime
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "projectGlobalId"),
        )
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "actor_user_id",
            _actor(self.actor_user_id, "actorUserId"),
        )
        object.__setattr__(self, "mode", _enum(self.mode, ToolingExportMode, "mode"))
        object.__setattr__(
            self,
            "language",
            _enum(self.language, ToolingExportLanguage, "language"),
        )
        references = _bounded_references(self.references, "objectRefs")
        object.__setattr__(self, "references", references)
        generated_at = _aware_utc(self.generated_at, "generatedAt")
        expires_at = _aware_utc(self.expires_at, "expiresAt")
        if expires_at != generated_at + TOOLING_OBJECT_PACKAGE_VALIDITY:
            raise _problem(
                "expiresAt",
                _("The Tooling object package must expire after one hour."),
            )
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "expires_at", expires_at)
        if self.mode is ToolingExportMode.FILTERED:
            object.__setattr__(
                self,
                "query_snapshot_hash",
                _hash(self.query_snapshot_hash, "querySnapshotHash"),
            )
        elif self.query_snapshot_hash not in (None, ""):
            raise _problem(
                "querySnapshotHash",
                _("A selection export cannot include a filtered query snapshot."),
            )
        else:
            object.__setattr__(self, "query_snapshot_hash", None)
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TOOLING_OBJECT_PACKAGE_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "actorUserId": self.actor_user_id,
            "mode": self.mode.value,
            "language": self.language.value,
            "confidentialityClass": TOOLING_OBJECT_PACKAGE_CONFIDENTIALITY,
            "querySnapshotHash": self.query_snapshot_hash,
            "objectRefs": [item.snapshot_payload() for item in self.references],
            "generatedAt": _utc_text(self.generated_at),
            "expiresAt": _utc_text(self.expires_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }

    @property
    def snapshot_hash(self) -> str:
        return sha256_json(self.snapshot_payload())


def select_filtered_rows(
    rows: Iterable[ToolingListRow],
    filter_spec: ToolingListFilter,
) -> tuple[ToolingListRow, ...]:
    normalized = tuple(rows)
    if not all(isinstance(item, ToolingListRow) for item in normalized):
        raise _problem("rows", _("Enter valid Tooling List rows."))
    search = filter_spec.search.casefold()
    selected = [
        row
        for row in normalized
        if row.matches_view(filter_spec.view_id)
        and (
            not search
            or search in row.title.casefold()
            or search in row.project_code.casefold()
            or search in str(row.tooling_master_global_id)
        )
    ]
    identities = [row.tooling_master_global_id for row in selected]
    if len(identities) != len(set(identities)):
        raise _problem("rows", _("Tooling List rows must be unique."))
    if len(selected) > MAX_TOOLING_EXPORT_OBJECTS:
        raise _problem(
            "filter",
            _("The filtered Tooling List contains more than one hundred objects."),
        )
    reverse = filter_spec.sort_direction is ToolingListSortDirection.DESCENDING
    selected.sort(key=lambda row: str(row.tooling_master_global_id))
    selected.sort(key=lambda row: _sort_value(row, filter_spec.sort_key), reverse=reverse)
    if filter_spec.group_key is not ToolingListGroupKey.NONE:
        selected.sort(key=lambda row: _group_value(row, filter_spec.group_key))
    return tuple(selected)


def filtered_query_snapshot_hash(
    filter_spec: ToolingListFilter,
    rows: Iterable[ToolingListRow],
) -> str:
    selected = select_filtered_rows(rows, filter_spec)
    return sha256_json(
        {
            "filter": filter_spec.snapshot_payload(),
            "objectRefs": [row.reference().snapshot_payload() for row in selected],
        }
    )


def tooling_list_preference_key_hash(
    *,
    tenant_id: str,
    project_global_id: UUID,
    actor_user_id: str,
    view_id: ToolingListViewId,
    grid_id: str = TOOLING_LIST_GRID_ID,
    table_schema_version: str = TOOLING_LIST_TABLE_SCHEMA_VERSION,
) -> str:
    if grid_id != TOOLING_LIST_GRID_ID:
        raise _problem("gridId", _("Select the supported Tooling List grid."))
    if table_schema_version != TOOLING_LIST_TABLE_SCHEMA_VERSION:
        raise _problem(
            "tableSchemaVersion",
            _("The Tooling List table schema is unsupported."),
        )
    return sha256_json(
        {
            "tenantId": _key(tenant_id, "tenantId"),
            "projectGlobalId": str(_uuid(project_global_id, "projectGlobalId")),
            "actorUserId": _actor(actor_user_id, "actorUserId"),
            "viewId": _enum(view_id, ToolingListViewId, "viewId").value,
            "gridId": grid_id,
            "tableSchemaVersion": table_schema_version,
        }
    )


def tooling_export_receipt_key_hash(
    *,
    tenant_id: str,
    project_global_id: UUID,
    actor_user_id: str,
    operation: ToolingExportOperation,
    idempotency_key_hash: str,
) -> str:
    return sha256_json(
        {
            "tenantId": _key(tenant_id, "tenantId"),
            "projectGlobalId": str(_uuid(project_global_id, "projectGlobalId")),
            "actorUserId": _actor(actor_user_id, "actorUserId"),
            "operation": _enum(operation, ToolingExportOperation, "operation").value,
            "idempotencyKeyHash": _hash(idempotency_key_hash, "idempotencyKeyHash"),
        }
    )


def resolve_exact_selection(
    rows: Iterable[ToolingListRow],
    selection: ToolingExportSelection,
) -> tuple[ToolingListRow, ...]:
    indexed = {row.tooling_master_global_id: row for row in rows}
    resolved: list[ToolingListRow] = []
    for reference in selection.references:
        row = indexed.get(reference.tooling_master_global_id)
        if row is None or row.tooling_master_snapshot_hash != reference.snapshot_hash:
            raise _problem(
                "selection",
                _("The Tooling List selection is stale."),
            )
        resolved.append(row)
    return tuple(resolved)


def _sort_value(row: ToolingListRow, key: ToolingListSortKey) -> tuple[object, ...]:
    if key is ToolingListSortKey.TITLE:
        return (row.title.casefold(),)
    if key is ToolingListSortKey.APPLICABILITY_COUNT:
        return (row.applicability_count, row.title.casefold())
    if key is ToolingListSortKey.PHYSICAL_SET_COUNT:
        return (row.physical_set_count, row.title.casefold())
    return (
        row.latest_revision_number is None,
        row.latest_revision_number or 0,
        row.title.casefold(),
    )


def _group_value(row: ToolingListRow, key: ToolingListGroupKey) -> tuple[int, ...]:
    if key is ToolingListGroupKey.APPLICABILITY_SCOPE:
        return (
            0
            if row.applicability_count == 0
            else 1 if row.applicability_count == 1 else 2,
        )
    if key is ToolingListGroupKey.PHYSICAL_SET_PRESENCE:
        return (0 if row.physical_set_count == 0 else 1,)
    if key is ToolingListGroupKey.DESIGN_REVISION_PRESENCE:
        return (0 if row.design_revision_count == 0 else 1,)
    return (0,)


def _bounded_references(value: object, path: str) -> tuple[ToolingExportReference, ...]:
    if not isinstance(value, (tuple, list)):
        raise _problem(path, _("Select between one and one hundred Tooling Masters."))
    normalized = tuple(value)
    if not 1 <= len(normalized) <= MAX_TOOLING_EXPORT_OBJECTS or not all(
        isinstance(item, ToolingExportReference) for item in normalized
    ):
        raise _problem(path, _("Select between one and one hundred Tooling Masters."))
    identities = [item.tooling_master_global_id for item in normalized]
    if len(identities) != len(set(identities)):
        raise _problem(path, _("A Tooling Master can only be selected once."))
    return normalized


def _column_widths(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, (tuple, list)):
        raise _problem("columnWidths", _("Enter valid Tooling List column widths."))
    normalized: list[tuple[str, int]] = []
    seen: set[str] = set()
    for item in value:
        if (
            not isinstance(item, (tuple, list))
            or len(item) != 2
            or item[0] not in TOOLING_LIST_COLUMN_IDS
            or isinstance(item[1], bool)
            or not isinstance(item[1], int)
            or not 56 <= item[1] <= 480
            or item[0] in seen
        ):
            raise _problem("columnWidths", _("Enter valid Tooling List column widths."))
        seen.add(item[0])
        normalized.append((item[0], item[1]))
    return tuple(sorted(normalized))


def _string_tuple(value: object, path: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not all(
        isinstance(item, str) for item in value
    ):
        raise _problem(path, _("Enter a valid list."))
    return tuple(value)


def _enum(value: object, enum_type: type[_E], path: str) -> _E:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Select a supported value.")) from error


def _uuid(value: object, path: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _problem(path, _("Enter a valid global ID.")) from error


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid SHA-256 value."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _problem(path, _("The value is too long."))
    return normalized


def _positive(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _problem(path, _("Enter a positive whole number."))
    return value


def _non_negative(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _problem(path, _("Enter a non-negative whole number."))
    return value


def _key(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if _KEY_PATTERN.fullmatch(normalized) is None:
        raise _problem(path, _("Use a valid key."))
    return normalized


def _actor(value: object, path: str) -> str:
    normalized = _text(value, path, 254)
    if _ACTOR_PATTERN.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid user identity."))
    return normalized


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a timezone-aware date and time."))
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
