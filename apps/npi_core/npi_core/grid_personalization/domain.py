from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence
from uuid import UUID, uuid4

try:
    from frappe import _
except ImportError:

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


GRID_ID = "my-work"
TABLE_SCHEMA_VERSION = "my-work-grid-v1"
PROJECT_PERMISSION_BOUNDARY = "project_viewers"
PUBLISHER_AUTHORITY_REASON = "publisher_authority_policy_required"
EXPORT_UNAVAILABLE_REASON = "export_contract_required"
BULK_UNAVAILABLE_REASON = "bulk_action_contract_required"
MAX_RECENT_VIEW_IDS = 5

VIEW_IDS = (
    "all",
    "today",
    "overdue",
    "approvals",
    "blockers",
    "waiting",
    "integration",
)
COLUMN_IDS = (
    "type",
    "item",
    "context",
    "assignment",
    "priority",
    "due",
    "status",
    "action",
)
REQUIRED_VISIBLE_COLUMN_IDS = frozenset({"item", "action"})
MAX_FIXED_COLUMN_COUNT = 2

_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_PRIORITY_VALUES = MappingProxyType(
    {
        "domain_severity": frozenset({"low", "medium", "high", "critical"}),
        "gate_requirement_priority": frozenset({"P0", "P1", "P2"}),
    }
)


@dataclass(frozen=True, slots=True)
class ColumnWidthSpec:
    minimum: int
    maximum: int
    default: int


COLUMN_WIDTH_SPECS: Mapping[str, ColumnWidthSpec] = MappingProxyType(
    {
        "type": ColumnWidthSpec(88, 180, 112),
        "item": ColumnWidthSpec(180, 480, 260),
        "context": ColumnWidthSpec(160, 420, 240),
        "assignment": ColumnWidthSpec(140, 320, 180),
        "priority": ColumnWidthSpec(96, 180, 112),
        "due": ColumnWidthSpec(120, 220, 144),
        "status": ColumnWidthSpec(112, 220, 136),
        "action": ColumnWidthSpec(120, 260, 160),
    }
)

CAPABILITIES: Mapping[str, object] = MappingProxyType(
    {
        "canPublishSharedView": False,
        "canRollbackSharedView": False,
        "canExport": False,
        "canRunBulkActions": False,
        "publishUnavailableReason": PUBLISHER_AUTHORITY_REASON,
        "rollbackUnavailableReason": PUBLISHER_AUTHORITY_REASON,
        "exportUnavailableReason": EXPORT_UNAVAILABLE_REASON,
        "bulkUnavailableReason": BULK_UNAVAILABLE_REASON,
    }
)


class GridPersonalizationValidationError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def _fail(path: str, message: str) -> GridPersonalizationValidationError:
    return GridPersonalizationValidationError(path, message)


def _plain_json_value(
    value: object,
    active_container_ids: set[int] | None = None,
) -> object:
    if isinstance(value, Mapping):
        active = active_container_ids if active_container_ids is not None else set()
        container_id = id(value)
        if container_id in active:
            raise ValueError("JSON values must not contain cycles.")
        active.add(container_id)
        try:
            plain: dict[str, object] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise TypeError("JSON object keys must be strings.")
                plain[key] = _plain_json_value(item, active)
            return plain
        finally:
            active.remove(container_id)
    if isinstance(value, (list, tuple)):
        active = active_container_ids if active_container_ids is not None else set()
        container_id = id(value)
        if container_id in active:
            raise ValueError("JSON values must not contain cycles.")
        active.add(container_id)
        try:
            return [_plain_json_value(item, active) for item in value]
        finally:
            active.remove(container_id)
    return value


def _freeze_json_value(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _immutable_json_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    parsed = json.loads(canonical_json(value))
    if not isinstance(parsed, dict):
        raise TypeError("JSON evidence must be an object.")
    frozen = _freeze_json_value(parsed)
    if not isinstance(frozen, Mapping):
        raise TypeError("JSON evidence must be an object.")
    return frozen


def canonical_json(value: object) -> str:
    return json.dumps(
        _plain_json_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def preference_key(tenant_id: object, actor_user_id: object) -> str:
    tenant = _tenant(tenant_id, "tenantId")
    actor = _actor(actor_user_id, "actorUserId")
    identity = "\0".join(
        (
            "npi-one:grid-personalization:v1",
            tenant,
            actor.casefold(),
            GRID_ID,
            TABLE_SCHEMA_VERSION,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _tenant(value: object, path: str) -> str:
    if type(value) is not str or _TENANT_PATTERN.fullmatch(value) is None:
        raise _fail(path, _("Enter a valid tenant identity."))
    return value


def _actor(value: object, path: str) -> str:
    if type(value) is not str or _ACTOR_PATTERN.fullmatch(value) is None:
        raise _fail(path, _("Enter a valid user identity."))
    return value


def _uuid(value: object, path: str) -> UUID:
    if type(value) is not str:
        raise _fail(path, _("Enter a canonical UUID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise _fail(path, _("Enter a canonical UUID.")) from error
    if parsed.int == 0 or str(parsed) != value:
        raise _fail(path, _("Enter a canonical UUID."))
    return parsed


def _positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _fail(path, _("Enter a positive integer."))
    return value


def expected_version(value: object) -> int:
    if type(value) is not int or value < 0:
        raise _fail(
            "expectedVersion",
            _("Enter a non-negative expected version."),
        )
    return value


def _exact_mapping(
    value: object,
    fields: frozenset[str],
    path: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _fail(path, _("Enter an object with the exact supported fields."))
    return value


def _sequence(value: object, path: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _fail(path, _("Enter a valid list."))
    return value


def _closed_view_id(value: object, path: str) -> str:
    if type(value) is not str or value not in VIEW_IDS:
        raise _fail(path, _("Select a supported My Work view."))
    return value


def _closed_view_ids(
    value: object,
    path: str,
    *,
    maximum: int,
) -> tuple[str, ...]:
    values = _sequence(value, path)
    if len(values) > maximum:
        raise _fail(path, _("Select no more than the supported number of views."))
    parsed = tuple(
        _closed_view_id(item, f"{path}[{index}]")
        for index, item in enumerate(values)
    )
    if len(set(parsed)) != len(parsed):
        raise _fail(path, _("Select each My Work view only once."))
    return parsed


@dataclass(frozen=True, slots=True)
class GridLayout:
    column_order: tuple[str, ...]
    widths: Mapping[str, int]
    hidden_column_ids: tuple[str, ...]
    fixed_column_count: int

    @classmethod
    def parse(
        cls,
        value: object,
        path: str = "layout",
    ) -> GridLayout:
        values = _exact_mapping(
            value,
            frozenset(
                {
                    "columnOrder",
                    "widths",
                    "hiddenColumnIds",
                    "fixedColumnCount",
                }
            ),
            path,
        )
        column_values = _sequence(values["columnOrder"], f"{path}.columnOrder")
        column_order = tuple(column_values)
        if (
            len(column_order) != len(COLUMN_IDS)
            or any(type(column_id) is not str for column_id in column_order)
            or len(set(column_order)) != len(column_order)
            or set(column_order) != set(COLUMN_IDS)
        ):
            raise _fail(
                f"{path}.columnOrder",
                _("Provide every supported column exactly once."),
            )

        width_values = _exact_mapping(
            values["widths"],
            frozenset(COLUMN_IDS),
            f"{path}.widths",
        )
        parsed_widths: dict[str, int] = {}
        for column_id in COLUMN_IDS:
            width = width_values[column_id]
            spec = COLUMN_WIDTH_SPECS[column_id]
            if (
                type(width) is not int
                or width < spec.minimum
                or width > spec.maximum
            ):
                raise _fail(
                    f"{path}.widths.{column_id}",
                    _("Enter a column width within the supported range."),
                )
            parsed_widths[column_id] = width

        hidden_values = _sequence(
            values["hiddenColumnIds"],
            f"{path}.hiddenColumnIds",
        )
        if any(type(column_id) is not str for column_id in hidden_values):
            raise _fail(
                f"{path}.hiddenColumnIds",
                _("Select only supported columns."),
            )
        hidden = tuple(hidden_values)
        if len(set(hidden)) != len(hidden) or not set(hidden).issubset(COLUMN_IDS):
            raise _fail(
                f"{path}.hiddenColumnIds",
                _("Select each supported column no more than once."),
            )
        if REQUIRED_VISIBLE_COLUMN_IDS.intersection(hidden):
            raise _fail(
                f"{path}.hiddenColumnIds",
                _("Required columns cannot be hidden."),
            )
        canonical_hidden = tuple(
            column_id for column_id in column_order if column_id in set(hidden)
        )

        fixed_count = values["fixedColumnCount"]
        visible_count = len(COLUMN_IDS) - len(canonical_hidden)
        if (
            type(fixed_count) is not int
            or fixed_count < 0
            or fixed_count > MAX_FIXED_COLUMN_COUNT
            or fixed_count > visible_count
        ):
            raise _fail(
                f"{path}.fixedColumnCount",
                _("Select a supported fixed-column count."),
            )
        return cls(
            column_order=column_order,
            widths=MappingProxyType(parsed_widths),
            hidden_column_ids=canonical_hidden,
            fixed_column_count=fixed_count,
        )

    @classmethod
    def default(cls) -> GridLayout:
        return cls(
            column_order=COLUMN_IDS,
            widths=MappingProxyType(
                {
                    column_id: COLUMN_WIDTH_SPECS[column_id].default
                    for column_id in COLUMN_IDS
                }
            ),
            hidden_column_ids=(),
            fixed_column_count=2,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "columnOrder": list(self.column_order),
            "widths": {
                column_id: self.widths[column_id] for column_id in COLUMN_IDS
            },
            "hiddenColumnIds": list(self.hidden_column_ids),
            "fixedColumnCount": self.fixed_column_count,
        }


@dataclass(frozen=True, slots=True)
class GridPriorityFilter:
    scheme: str
    value: str

    @classmethod
    def parse(
        cls,
        value: object,
        path: str,
    ) -> GridPriorityFilter:
        values = _exact_mapping(
            value,
            frozenset({"scheme", "value"}),
            path,
        )
        scheme = values["scheme"]
        priority_value = values["value"]
        if (
            type(scheme) is not str
            or scheme not in _PRIORITY_VALUES
            or type(priority_value) is not str
            or priority_value not in _PRIORITY_VALUES[scheme]
        ):
            raise _fail(path, _("Select a supported My Work priority."))
        return cls(scheme, priority_value)

    def canonical_dict(self) -> dict[str, str]:
        return {"scheme": self.scheme, "value": self.value}


@dataclass(frozen=True, slots=True)
class GridFilterSnapshot:
    project_id: UUID | None
    priority: GridPriorityFilter | None
    search: str

    @classmethod
    def parse(
        cls,
        value: object,
        path: str = "filter",
    ) -> GridFilterSnapshot:
        values = _exact_mapping(
            value,
            frozenset({"projectId", "priority", "search"}),
            path,
        )
        project_value = values["projectId"]
        project_id = (
            None
            if project_value is None
            else _uuid(project_value, f"{path}.projectId")
        )
        priority_value = values["priority"]
        priority = (
            None
            if priority_value is None
            else GridPriorityFilter.parse(priority_value, f"{path}.priority")
        )
        search_value = values["search"]
        if type(search_value) is not str:
            raise _fail(f"{path}.search", _("Enter valid search text."))
        search = search_value.strip()
        if len(search) > 140 or any(
            ord(character) < 32 or ord(character) == 127 for character in search
        ):
            raise _fail(f"{path}.search", _("Enter valid search text."))
        return cls(project_id=project_id, priority=priority, search=search)

    @classmethod
    def default(cls) -> GridFilterSnapshot:
        return cls(project_id=None, priority=None, search="")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "projectId": None if self.project_id is None else str(self.project_id),
            "priority": (
                None if self.priority is None else self.priority.canonical_dict()
            ),
            "search": self.search,
        }


@dataclass(frozen=True, slots=True)
class SavedViewPreference:
    view_id: str
    layout: GridLayout
    filter: GridFilterSnapshot
    has_saved_filter: bool

    @classmethod
    def parse(
        cls,
        value: object,
        path: str,
    ) -> SavedViewPreference:
        values = _exact_mapping(
            value,
            frozenset({"viewId", "layout", "filter", "hasSavedFilter"}),
            path,
        )
        parsed_filter = GridFilterSnapshot.parse(
            values["filter"],
            f"{path}.filter",
        )
        has_saved_filter = values["hasSavedFilter"]
        if type(has_saved_filter) is not bool:
            raise _fail(
                f"{path}.hasSavedFilter",
                _("Select whether this view has a saved filter."),
            )
        if (
            not has_saved_filter
            and parsed_filter != GridFilterSnapshot.default()
        ):
            raise _fail(
                f"{path}.filter",
                _("An unsaved filter must use code-owned defaults."),
            )
        return cls(
            view_id=_closed_view_id(values["viewId"], f"{path}.viewId"),
            layout=GridLayout.parse(values["layout"], f"{path}.layout"),
            filter=parsed_filter,
            has_saved_filter=has_saved_filter,
        )

    @classmethod
    def default(cls, view_id: str) -> SavedViewPreference:
        return cls(
            view_id=_closed_view_id(view_id, "viewId"),
            layout=GridLayout.default(),
            filter=GridFilterSnapshot.default(),
            has_saved_filter=False,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "viewId": self.view_id,
            "layout": self.layout.canonical_dict(),
            "filter": self.filter.canonical_dict(),
            "hasSavedFilter": self.has_saved_filter,
        }


@dataclass(frozen=True, slots=True)
class PersonalGridPreference:
    version: int
    view_preferences: tuple[SavedViewPreference, ...]
    favorite_view_ids: tuple[str, ...]
    recent_view_ids: tuple[str, ...]
    default_project_id: UUID | None

    @classmethod
    def default(cls, *, version: int = 0) -> PersonalGridPreference:
        if type(version) is not int or version < 0:
            raise _fail("version", _("Enter a non-negative version."))
        return cls(
            version=version,
            view_preferences=tuple(
                SavedViewPreference.default(view_id) for view_id in VIEW_IDS
            ),
            favorite_view_ids=(),
            recent_view_ids=(),
            default_project_id=None,
        )

    @classmethod
    def from_storage(
        cls,
        *,
        version: object,
        value: object,
    ) -> PersonalGridPreference:
        parsed_version = expected_version(version)
        values = _exact_mapping(
            value,
            frozenset(
                {
                    "tableSchemaVersion",
                    "viewLayouts",
                    "favoriteViewIds",
                    "recentViewIds",
                    "defaultProjectId",
                }
            ),
            "preference",
        )
        if values["tableSchemaVersion"] != TABLE_SCHEMA_VERSION:
            raise _fail(
                "tableSchemaVersion",
                _("Select the supported My Work table schema."),
            )
        view_values = _sequence(values["viewLayouts"], "viewLayouts")
        if len(view_values) != len(VIEW_IDS):
            raise _fail(
                "viewLayouts",
                _("Provide every supported My Work view exactly once."),
            )
        view_preferences = tuple(
            SavedViewPreference.parse(value, f"viewLayouts[{index}]")
            for index, value in enumerate(view_values)
        )
        if tuple(item.view_id for item in view_preferences) != VIEW_IDS:
            raise _fail(
                "viewLayouts",
                _("Provide My Work views in the supported order."),
            )
        favorite_view_ids = _closed_view_ids(
            values["favoriteViewIds"],
            "favoriteViewIds",
            maximum=len(VIEW_IDS),
        )
        recent_view_ids = _closed_view_ids(
            values["recentViewIds"],
            "recentViewIds",
            maximum=MAX_RECENT_VIEW_IDS,
        )
        default_value = values["defaultProjectId"]
        default_project_id = (
            None
            if default_value is None
            else _uuid(default_value, "defaultProjectId")
        )
        return cls(
            version=parsed_version,
            view_preferences=view_preferences,
            favorite_view_ids=favorite_view_ids,
            recent_view_ids=recent_view_ids,
            default_project_id=default_project_id,
        )

    def update(
        self,
        *,
        view_id: object,
        layout: object,
        filter_snapshot: object,
        save_filter: object,
        favorite_view_ids: object,
        recent_view_ids: object,
        default_project_id: object,
    ) -> PersonalGridPreference:
        selected_view_id = _closed_view_id(view_id, "viewId")
        selected_layout = GridLayout.parse(layout)
        selected_filter = GridFilterSnapshot.parse(filter_snapshot)
        if type(save_filter) is not bool:
            raise _fail(
                "saveFilter",
                _("Select whether to save the current filter."),
            )
        favorites = _closed_view_ids(
            favorite_view_ids,
            "favoriteViewIds",
            maximum=len(VIEW_IDS),
        )
        recent = _closed_view_ids(
            recent_view_ids,
            "recentViewIds",
            maximum=MAX_RECENT_VIEW_IDS,
        )
        parsed_default_project = (
            None
            if default_project_id is None
            else _uuid(default_project_id, "defaultProjectId")
        )
        updated_views = tuple(
            SavedViewPreference(
                view_id=item.view_id,
                layout=selected_layout,
                filter=selected_filter if save_filter else item.filter,
                has_saved_filter=(
                    True if save_filter else item.has_saved_filter
                ),
            )
            if item.view_id == selected_view_id
            else item
            for item in self.view_preferences
        )
        return PersonalGridPreference(
            version=self.version + 1,
            view_preferences=updated_views,
            favorite_view_ids=favorites,
            recent_view_ids=recent,
            default_project_id=parsed_default_project,
        )

    def referenced_project_ids(self) -> frozenset[UUID]:
        values = {
            item.filter.project_id
            for item in self.view_preferences
            if item.filter.project_id is not None
        }
        if self.default_project_id is not None:
            values.add(self.default_project_id)
        return frozenset(values)

    def effective_for(
        self,
        accessible_project_ids: frozenset[UUID],
    ) -> PersonalGridPreference:
        views = tuple(
            replace(
                item,
                filter=replace(item.filter, project_id=None),
            )
            if (
                item.filter.project_id is not None
                and item.filter.project_id not in accessible_project_ids
            )
            else item
            for item in self.view_preferences
        )
        default_project_id = (
            self.default_project_id
            if self.default_project_id in accessible_project_ids
            else None
        )
        return replace(
            self,
            view_preferences=views,
            default_project_id=default_project_id,
        )

    def storage_dict(self) -> dict[str, object]:
        return {
            "tableSchemaVersion": TABLE_SCHEMA_VERSION,
            "viewLayouts": [
                preference.canonical_dict()
                for preference in self.view_preferences
            ],
            "favoriteViewIds": list(self.favorite_view_ids),
            "recentViewIds": list(self.recent_view_ids),
            "defaultProjectId": (
                None
                if self.default_project_id is None
                else str(self.default_project_id)
            ),
        }

    def response_dict(
        self,
        *,
        recovery_reason: str | None = None,
    ) -> dict[str, object]:
        if recovery_reason not in {None, "stored_preference_invalid"}:
            raise ValueError("The grid preference recovery reason is invalid.")
        return {
            "gridId": GRID_ID,
            "tableSchemaVersion": TABLE_SCHEMA_VERSION,
            "version": self.version,
            "viewLayouts": [
                preference.canonical_dict()
                for preference in self.view_preferences
            ],
            "favoriteViewIds": list(self.favorite_view_ids),
            "recentViewIds": list(self.recent_view_ids),
            "defaultProjectId": (
                None
                if self.default_project_id is None
                else str(self.default_project_id)
            ),
            "recoveryReason": recovery_reason,
            "capabilities": dict(CAPABILITIES),
        }


@dataclass(frozen=True, slots=True)
class PublicationAuthorityDecision:
    allowed: bool
    reason_code: str
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise ValueError("The publication authority decision must be explicit.")
        if (
            type(self.reason_code) is not str
            or not self.reason_code
            or len(self.reason_code) > 100
        ):
            raise ValueError("The publication authority reason is invalid.")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("The publication authority evidence is invalid.")
        try:
            evidence = _immutable_json_mapping(self.evidence)
        except (RecursionError, TypeError, ValueError) as error:
            raise ValueError(
                "The publication authority evidence is invalid."
            ) from error
        object.__setattr__(self, "evidence", evidence)


class PublishedViewAuthorizer(Protocol):
    def decide(
        self,
        *,
        operation: str,
        tenant_id: str,
        project_id: UUID,
        actor_user_id: str,
    ) -> PublicationAuthorityDecision: ...


class FailClosedPublishedViewAuthorizer:
    def decide(
        self,
        *,
        operation: str,
        tenant_id: str,
        project_id: UUID,
        actor_user_id: str,
    ) -> PublicationAuthorityDecision:
        del operation, tenant_id, project_id, actor_user_id
        return PublicationAuthorityDecision(
            allowed=False,
            reason_code=PUBLISHER_AUTHORITY_REASON,
            evidence=MappingProxyType({}),
        )


@dataclass(frozen=True, slots=True)
class PublishedGridViewDefinition:
    view_id: str
    layout: GridLayout
    filter: GridFilterSnapshot

    @classmethod
    def parse(cls, value: object) -> PublishedGridViewDefinition:
        values = _exact_mapping(
            value,
            frozenset({"viewId", "layout", "filter"}),
            "definition",
        )
        return cls(
            view_id=_closed_view_id(values["viewId"], "definition.viewId"),
            layout=GridLayout.parse(values["layout"], "definition.layout"),
            filter=GridFilterSnapshot.parse(values["filter"], "definition.filter"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "viewId": self.view_id,
            "layout": self.layout.canonical_dict(),
            "filter": self.filter.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class PublishedRevisionReference:
    global_id: UUID
    revision_number: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.global_id, UUID) or self.global_id.int == 0:
            raise ValueError("The revision reference identity is invalid.")
        _positive_integer(self.revision_number, "revisionNumber")
        if not re.fullmatch(r"[a-f0-9]{64}", self.snapshot_hash):
            raise ValueError("The revision reference hash is invalid.")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "revisionNumber": self.revision_number,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class PublishedGridViewRevision:
    global_id: UUID
    published_view_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    revision_number: int
    prior_revision: PublishedRevisionReference | None
    restored_from_revision: PublishedRevisionReference | None
    name: str
    description: str
    definition: PublishedGridViewDefinition
    published_by: str
    published_at: datetime
    authority_reason_code: str
    authority_evidence: Mapping[str, object]
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        try:
            evidence = _immutable_json_mapping(self.authority_evidence)
        except (RecursionError, TypeError, ValueError) as error:
            raise ValueError(
                "The publication authority evidence is invalid."
            ) from error
        object.__setattr__(self, "authority_evidence", evidence)

    @classmethod
    def create(
        cls,
        *,
        published_view_global_id: UUID,
        tenant_id: str,
        project_global_id: UUID,
        revision_number: int,
        prior_revision: PublishedRevisionReference | None,
        restored_from_revision: PublishedRevisionReference | None,
        name: object,
        description: object,
        definition: PublishedGridViewDefinition,
        published_by: object,
        published_at: datetime,
        authority: PublicationAuthorityDecision,
        request_id: UUID,
        trace_id: object,
        global_id: UUID | None = None,
    ) -> PublishedGridViewRevision:
        if not authority.allowed:
            raise PermissionError(PUBLISHER_AUTHORITY_REASON)
        if not isinstance(published_view_global_id, UUID):
            raise _fail("publishedViewId", _("Enter a canonical UUID."))
        if not isinstance(project_global_id, UUID):
            raise _fail("projectId", _("Enter a canonical UUID."))
        if definition.filter.project_id not in (None, project_global_id):
            raise _fail(
                "definition.filter.projectId",
                _("A published grid view filter must stay within its Project boundary."),
            )
        _tenant(tenant_id, "tenantId")
        parsed_name = _bounded_text(name, "name", maximum=140)
        parsed_description = _bounded_text(
            description,
            "description",
            maximum=1000,
            allow_empty=True,
        )
        _positive_integer(revision_number, "revisionNumber")
        if revision_number == 1 and prior_revision is not None:
            raise _fail(
                "priorRevision",
                _("The first published view revision cannot have a prior revision."),
            )
        if revision_number > 1 and (
            prior_revision is None
            or prior_revision.revision_number != revision_number - 1
        ):
            raise _fail(
                "priorRevision",
                _("Select the exact preceding published view revision."),
            )
        if (
            restored_from_revision is not None
            and restored_from_revision.revision_number >= revision_number
        ):
            raise _fail(
                "restoredFromRevision",
                _("Select an earlier published view revision to restore."),
            )
        if (
            not isinstance(published_at, datetime)
            or published_at.tzinfo is None
            or published_at.utcoffset() is None
        ):
            raise _fail("publishedAt", _("Enter a timezone-aware date and time."))
        if not isinstance(request_id, UUID) or request_id.int == 0:
            raise _fail("requestId", _("Enter a canonical UUID."))
        parsed_trace = _trace(trace_id)
        return cls(
            global_id=global_id or uuid4(),
            published_view_global_id=published_view_global_id,
            tenant_id=tenant_id,
            project_global_id=project_global_id,
            revision_number=revision_number,
            prior_revision=prior_revision,
            restored_from_revision=restored_from_revision,
            name=parsed_name,
            description=parsed_description,
            definition=definition,
            published_by=_actor(published_by, "publishedBy"),
            published_at=published_at.astimezone(UTC),
            authority_reason_code=authority.reason_code,
            authority_evidence=authority.evidence,
            request_id=request_id,
            trace_id=parsed_trace,
        )

    @property
    def definition_hash(self) -> str:
        return canonical_hash(self.definition.canonical_dict())

    @property
    def reference(self) -> PublishedRevisionReference:
        return PublishedRevisionReference(
            global_id=self.global_id,
            revision_number=self.revision_number,
            snapshot_hash=self.snapshot_hash,
        )

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.snapshot_dict())

    @property
    def revision_key(self) -> str:
        return f"{self.published_view_global_id}:{self.revision_number}"

    def snapshot_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "globalId": str(self.global_id),
            "publishedViewId": str(self.published_view_global_id),
            "tenantId": self.tenant_id,
            "projectId": str(self.project_global_id),
            "gridId": GRID_ID,
            "tableSchemaVersion": TABLE_SCHEMA_VERSION,
            "revisionNumber": self.revision_number,
            "priorRevision": (
                None
                if self.prior_revision is None
                else self.prior_revision.canonical_dict()
            ),
            "restoredFromRevision": (
                None
                if self.restored_from_revision is None
                else self.restored_from_revision.canonical_dict()
            ),
            "name": self.name,
            "description": self.description,
            "permissionBoundary": PROJECT_PERMISSION_BOUNDARY,
            "definition": self.definition.canonical_dict(),
            "definitionHash": self.definition_hash,
            "publishedBy": self.published_by,
            "publishedAt": _datetime_text(self.published_at),
            "authorityReasonCode": self.authority_reason_code,
            "authorityEvidence": _plain_json_value(self.authority_evidence),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class PublishedGridViewRoot:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    optimistic_version: int
    current_revision: PublishedRevisionReference
    created_by: str
    created_at: datetime
    request_id: UUID
    trace_id: str

    @classmethod
    def from_first_revision(
        cls,
        revision: PublishedGridViewRevision,
    ) -> PublishedGridViewRoot:
        if revision.revision_number != 1:
            raise ValueError("A published view root must begin with revision one.")
        return cls(
            global_id=revision.published_view_global_id,
            tenant_id=revision.tenant_id,
            project_global_id=revision.project_global_id,
            optimistic_version=1,
            current_revision=revision.reference,
            created_by=revision.published_by,
            created_at=revision.published_at,
            request_id=revision.request_id,
            trace_id=revision.trace_id,
        )

    def advance(
        self,
        revision: PublishedGridViewRevision,
    ) -> PublishedGridViewRoot:
        if (
            revision.published_view_global_id != self.global_id
            or revision.tenant_id != self.tenant_id
            or revision.project_global_id != self.project_global_id
            or revision.revision_number != self.current_revision.revision_number + 1
            or revision.prior_revision != self.current_revision
        ):
            raise ValueError("The published view revision is not the next successor.")
        return replace(
            self,
            optimistic_version=self.optimistic_version + 1,
            current_revision=revision.reference,
            request_id=revision.request_id,
            trace_id=revision.trace_id,
        )


def rollback_as_new_revision(
    *,
    root: PublishedGridViewRoot,
    current_revision: PublishedGridViewRevision,
    target_revision: PublishedGridViewRevision,
    published_by: str,
    published_at: datetime,
    authority: PublicationAuthorityDecision,
    request_id: UUID,
    trace_id: str,
) -> PublishedGridViewRevision:
    if (
        current_revision.reference != root.current_revision
        or current_revision.published_view_global_id != root.global_id
        or target_revision.published_view_global_id != root.global_id
        or target_revision.tenant_id != root.tenant_id
        or target_revision.project_global_id != root.project_global_id
    ):
        raise ValueError("The published view rollback lineage is invalid.")
    if target_revision.revision_number >= current_revision.revision_number:
        raise _fail(
            "targetRevision",
            _("Select an earlier published view revision to restore."),
        )
    return PublishedGridViewRevision.create(
        published_view_global_id=root.global_id,
        tenant_id=root.tenant_id,
        project_global_id=root.project_global_id,
        revision_number=current_revision.revision_number + 1,
        prior_revision=current_revision.reference,
        restored_from_revision=target_revision.reference,
        name=target_revision.name,
        description=target_revision.description,
        definition=target_revision.definition,
        published_by=published_by,
        published_at=published_at,
        authority=authority,
        request_id=request_id,
        trace_id=trace_id,
    )


def _bounded_text(
    value: object,
    path: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if type(value) is not str:
        raise _fail(path, _("Enter valid text."))
    normalized = value.strip()
    if (
        (not normalized and not allow_empty)
        or len(normalized) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise _fail(path, _("Enter valid text."))
    return normalized


def _trace(value: object) -> str:
    if type(value) is not str or _TRACE_PATTERN.fullmatch(value) is None:
        raise _fail("traceId", _("Enter a valid trace identity."))
    return value


def _datetime_text(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
