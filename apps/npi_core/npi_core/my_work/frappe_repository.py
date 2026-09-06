from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe
from frappe import _

from npi_core.foundation.errors import (
    CursorSigningUnavailable,
    PermissionDenied,
    RequestValidationFailed,
)
from npi_core.foundation.security import Principal
from npi_core.my_work.domain import (
    CURSOR_KEY_CONTEXT,
    DomainWorkItemKind,
    DomainWorkItemTarget,
    GateReviewTarget,
    InvalidMyWorkCursor,
    MyWorkCategory,
    MyWorkCursorCodec,
    MyWorkItem,
    MyWorkPriority,
    MyWorkPriorityScheme,
    MyWorkQuery,
    MyWorkSourceReference,
    MyWorkSourceType,
    MyWorkStatus,
    MyWorkView,
    calculate_my_work_counts,
    filter_my_work_items,
    my_work_due_state,
)


_ASSIGNMENT_DOCTYPE = "NPI My Work Assignment"
_MAX_ACTOR_ASSIGNMENTS = 2000
_MAX_SOURCE_ASSIGNMENTS = 256
_MAX_REBUILD_SOURCES = 10_000
_REBUILD_PAGE_SIZE = 500
_PROJECTION_NAMESPACE = UUID("819dbd63-c06f-4f3f-b07e-1375dc7f8a34")
_CURSOR_QUERY_CONTEXT = b"npi-one:my-work:repository-query:v1"
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_ASSIGNMENT_FIELDS = (
    "global_id",
    "assignment_key",
    "tenant_id",
    "actor_user_id",
    "project_global_id",
    "source_type",
    "source_global_id",
    "source_version",
    "assignment_code",
    "category",
    "due_at",
    "priority_scheme",
    "priority_value",
    "blocking",
    "active",
    "source_snapshot",
    "snapshot_hash",
    "indexed_at",
)
_DOMAIN_CATEGORY = {
    "risk": MyWorkCategory.RISK,
    "issue": MyWorkCategory.ISSUE,
    "action": MyWorkCategory.TASK,
    "decision_request": MyWorkCategory.DECISION,
}
_MUTABLE_PROJECT_STATES = frozenset({"draft", "proposed", "active", "on_hold"})
_PROJECT_SOURCE_TYPES = frozenset(
    {
        MyWorkSourceType.DOMAIN_WORK_ITEM,
        MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
        MyWorkSourceType.GATE_REVIEW_INVALIDATION,
    }
)


class MyWorkAssignmentStore(Protocol):
    def actor_assignments(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
        maximum: int,
    ) -> Sequence[object]: ...

    def upsert(self, spec: ProjectionSpec, *, indexed_at: datetime) -> UUID: ...

    def deactivate_source_except(
        self,
        *,
        tenant_id: str,
        source_type: MyWorkSourceType,
        source_global_id: UUID,
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None: ...

    def deactivate_tenant_except(
        self,
        *,
        tenant_id: str,
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None: ...

    def deactivate_project_except(
        self,
        *,
        tenant_id: str,
        project_global_id: UUID,
        source_types: frozenset[MyWorkSourceType],
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None: ...

    def deactivate_one(
        self,
        *,
        assignment_global_id: UUID,
        expected_snapshot_hash: str,
        indexed_at: datetime,
    ) -> bool: ...


class MyWorkSourceResolver(Protocol):
    def resolve(
        self,
        assignment: object,
        *,
        as_of: datetime,
    ) -> ResolvedMyWorkRow | None: ...


@dataclass(frozen=True, slots=True)
class ProjectionSpec:
    global_id: UUID
    assignment_key: str
    tenant_id: str
    actor_user_id: str
    project_global_id: UUID
    source_type: MyWorkSourceType
    source_global_id: UUID
    source_version: int
    assignment_code: str
    category: MyWorkCategory
    due_at: datetime | None
    priority: MyWorkPriority | None
    blocking: bool
    status: MyWorkStatus
    domain_kind: DomainWorkItemKind | None
    source_detail: tuple[tuple[str, str], ...]
    title: str
    project_business_code: str
    project_title: str
    context_code: str
    context_title: str

    def source_detail_dict(self) -> dict[str, str]:
        return dict(self.source_detail)

    def to_item(self) -> MyWorkItem:
        target: DomainWorkItemTarget | GateReviewTarget
        if self.source_type is MyWorkSourceType.DOMAIN_WORK_ITEM:
            target = DomainWorkItemTarget(self.source_global_id)
        else:
            target = GateReviewTarget(
                self.project_global_id,
                self.source_global_id,
            )
        return MyWorkItem(
            id=self.global_id,
            project_global_id=self.project_global_id,
            source=MyWorkSourceReference(
                self.source_type,
                self.source_global_id,
                self.source_version,
            ),
            domain_kind=self.domain_kind,
            category=self.category,
            status=self.status,
            due_at=self.due_at,
            priority=self.priority,
            blocking=self.blocking,
            target=target,
        )

    def to_resolved(self) -> ResolvedMyWorkRow:
        return ResolvedMyWorkRow(
            item=self.to_item(),
            title=_business_text(self.title, 280),
            project_business_code=_business_text(
                self.project_business_code,
                64,
            ),
            project_title=_business_text(self.project_title, 280),
            context_code=_business_text(self.context_code, 64),
            context_title=_business_text(self.context_title, 280),
            why=self.assignment_code,
            action=(
                "view_work_item"
                if self.source_type is MyWorkSourceType.DOMAIN_WORK_ITEM
                else "open_gate_review"
            ),
        )


@dataclass(frozen=True, slots=True)
class MyWorkProjectionRebuildResult:
    """Bounded-memory, stable evidence for one complete tenant rebuild."""

    source_count: int
    assignment_count: int
    assignment_digest: str


@dataclass(frozen=True, slots=True)
class ResolvedMyWorkRow:
    item: MyWorkItem
    title: str
    project_business_code: str
    project_title: str
    context_code: str
    context_title: str
    why: str
    action: str

    def response(
        self,
        *,
        as_of: datetime,
        time_zone: str,
    ) -> dict[str, object]:
        target: dict[str, str]
        context_type: str
        if type(self.item.target) is DomainWorkItemTarget:
            context_type = "domain_work_item"
            target = {
                "kind": self.item.target.kind.value,
                "workItemId": str(self.item.target.work_item_id),
            }
        elif type(self.item.target) is GateReviewTarget:
            context_type = "gate"
            target = {
                "kind": self.item.target.kind.value,
                "projectId": str(self.item.target.project_id),
                "gateId": str(self.item.target.gate_id),
            }
        else:
            raise ValueError("Resolved My Work target is not typed.")
        return {
            "id": str(self.item.id),
            "category": self.item.category.value,
            "title": self.title,
            "project": {
                "globalId": str(self.item.project_global_id),
                "businessCode": self.project_business_code,
                "title": self.project_title,
            },
            "context": {
                "type": context_type,
                "globalId": str(self.item.source.global_id),
                "code": self.context_code,
                "title": self.context_title,
            },
            "source": {
                "type": self.item.source.type.value,
                "globalId": str(self.item.source.global_id),
                "version": self.item.source.version,
            },
            "why": self.why,
            "status": self.item.status.value,
            "dueAt": (
                None if self.item.due_at is None else _datetime_iso(self.item.due_at)
            ),
            "dueState": my_work_due_state(
                self.item,
                as_of=as_of,
                time_zone=time_zone,
            ).value,
            "priority": (
                None
                if self.item.priority is None
                else self.item.priority.canonical_dict()
            ),
            "blocking": self.item.blocking,
            "action": self.action,
            "target": target,
            "sourceStatus": {
                "sourceSystem": "NPI_ONE",
                "editableIn": "NPI_ONE",
                "syncState": "local",
            },
        }


@dataclass(frozen=True, slots=True)
class GateWorkspaceAccess:
    workspace: Mapping[str, object]
    roles: frozenset[str]
    internal: bool = True


class FrappeMyWorkRepository:
    """Current-actor My Work query over a revalidated assignment projection."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        store: MyWorkAssignmentStore | None = None,
        source_resolver: MyWorkSourceResolver | None = None,
        clock: Callable[[], datetime] | None = None,
        time_zone_resolver: Callable[[str], str] | None = None,
        signing_key_resolver: Callable[[], bytes] | None = None,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id
        self.store = store or FrappeMyWorkAssignmentStore()
        self.source_resolver = source_resolver or FrappeMyWorkSourceResolver(
            principal=principal,
            request_id=request_id,
            trace_id=trace_id,
        )
        self.clock = clock or (lambda: datetime.now(UTC))
        self.time_zone_resolver = time_zone_resolver or _resolved_user_time_zone
        self.signing_key_resolver = signing_key_resolver or _my_work_cursor_signing_key

    def query(
        self,
        *,
        view: MyWorkView,
        project_global_id: UUID | None,
        priority: MyWorkPriority | None,
        search: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, object]:
        if (
            self.principal.is_external
            or not self.principal.tenant_id
            or not self.actor
            or self.actor == "Guest"
        ):
            raise PermissionDenied()
        query = MyWorkQuery(
            view=view,
            project_global_id=project_global_id,
            priority=priority,
            limit=limit,
        )
        normalized_search = _search_value(search)
        time_zone = _validated_time_zone(self.time_zone_resolver(self.actor))
        base_signing_key = self.signing_key_resolver()
        codec = _query_cursor_codec(
            base_signing_key,
            query=query,
            search=normalized_search,
            tenant_id=self.principal.tenant_id,
            actor_user_id=self.actor,
        )
        decoded = None
        if cursor is not None:
            try:
                decoded = codec.decode(
                    cursor,
                    query=query,
                    expected_time_zone=time_zone,
                )
            except InvalidMyWorkCursor as error:
                raise _field_problem(
                    "cursor",
                    _("Enter a valid cursor."),
                ) from error
        as_of = decoded.as_of if decoded is not None else _datetime_value(self.clock())
        after = decoded.last if decoded is not None else None
        assignments = self.store.actor_assignments(
            tenant_id=self.principal.tenant_id,
            actor_user_id=self.actor.casefold(),
            maximum=_MAX_ACTOR_ASSIGNMENTS,
        )
        all_resolved: list[ResolvedMyWorkRow] = []
        seen: set[UUID] = set()
        for assignment in assignments:
            try:
                row = self.source_resolver.resolve(
                    assignment,
                    as_of=as_of,
                )
            except (KeyError, TypeError, ValueError):
                row = None
            if row is None:
                continue
            if row.item.id in seen:
                raise RuntimeError("Duplicate live My Work projection identity.")
            seen.add(row.item.id)
            all_resolved.append(row)

        projects: dict[UUID, dict[str, str]] = {}
        for row in all_resolved:
            project = {
                "globalId": str(row.item.project_global_id),
                "businessCode": row.project_business_code,
                "title": row.project_title,
            }
            prior = projects.get(row.item.project_global_id)
            if prior is not None and prior != project:
                raise RuntimeError("Conflicting live My Work Project identity.")
            projects[row.item.project_global_id] = project
        project_options = sorted(
            projects.values(),
            key=lambda value: (
                value["businessCode"].casefold(),
                value["businessCode"],
                value["globalId"],
            ),
        )
        resolved = [
            row
            for row in all_resolved
            if normalized_search is None
            or _matches_search(
                row,
                normalized_search,
            )
        ]

        by_id = {row.item.id: row for row in resolved}
        values = tuple(row.item for row in resolved)
        counts = calculate_my_work_counts(
            values,
            as_of=as_of,
            time_zone=time_zone,
            project_global_id=project_global_id,
            priority=priority,
        )
        page_items = filter_my_work_items(
            values,
            query,
            as_of=as_of,
            time_zone=time_zone,
            after=after,
        )
        has_more = False
        if len(page_items) == limit:
            remainder = filter_my_work_items(
                values,
                replace(query, limit=1),
                as_of=as_of,
                time_zone=time_zone,
                after=page_items[-1].sort_tuple,
            )
            has_more = bool(remainder)
        next_cursor = (
            codec.encode(
                query=query,
                as_of=as_of,
                time_zone=time_zone,
                last=page_items[-1].sort_tuple,
            )
            if has_more and page_items
            else None
        )
        return {
            "asOf": _datetime_iso(as_of),
            "timeZone": time_zone,
            "projectOptions": project_options,
            "items": [
                by_id[item.id].response(as_of=as_of, time_zone=time_zone)
                for item in page_items
            ],
            "nextCursor": next_cursor,
            "counts": _counts_response(counts),
        }


class FrappeMyWorkSourceResolver:
    """Resolve every candidate from its live source and source-specific access."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id

    def resolve(
        self,
        assignment: object,
        *,
        as_of: datetime,
    ) -> ResolvedMyWorkRow | None:
        if (
            self.principal.is_external
            or not self.principal.tenant_id
            or str(_record(assignment, "tenant_id")) != self.principal.tenant_id
            or str(_record(assignment, "actor_user_id")).casefold()
            != self.actor.casefold()
            or not bool(_record(assignment, "active"))
        ):
            return None
        if _validated_assignment_snapshot(assignment) is None:
            return None
        source_type = str(_record(assignment, "source_type"))
        if source_type == MyWorkSourceType.DOMAIN_WORK_ITEM.value:
            return self._resolve_domain_work_item(assignment)
        if source_type in {
            MyWorkSourceType.GATE_REVIEW_ASSIGNMENT.value,
            MyWorkSourceType.GATE_REVIEW_INVALIDATION.value,
        }:
            return self._resolve_gate(assignment, as_of=as_of)
        return None

    def _resolve_domain_work_item(
        self,
        assignment: object,
    ) -> ResolvedMyWorkRow | None:
        source = _optional_doc(
            "NPI Domain Work Item",
            str(_record(assignment, "source_global_id")),
        )
        if source is None:
            return None
        project = _optional_doc(
            "NPI Engineering Project",
            str(_record(assignment, "project_global_id")),
        )
        if project is None:
            return None
        spec = _domain_projection_spec(source, project)
        if spec is None or not _assignment_matches_spec(assignment, spec):
            return None
        from npi_core.project_work.frappe_repository import (
            FrappeProjectWorkRepository,
        )

        accessible = FrappeProjectWorkRepository(
            principal=self.principal,
            request_id=self.request_id,
            trace_id=self.trace_id,
        ).work_context(spec.project_global_id)
        return spec.to_resolved() if accessible is not None else None

    def _resolve_gate(
        self,
        assignment: object,
        *,
        as_of: datetime,
    ) -> ResolvedMyWorkRow | None:
        project_id = _uuid_value(
            _record(assignment, "project_global_id"),
        )
        gate_id = _uuid_value(
            _record(assignment, "source_global_id"),
        )
        access = _gate_workspace_for_principal(
            self.principal,
            project_id,
            gate_id,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        if access is None:
            return None
        for spec in _gate_projection_specs(access, actor=self.actor):
            if _assignment_matches_spec(assignment, spec):
                return spec.to_resolved()
        return None


class FrappeMyWorkAssignmentStore:
    """Controlled projection persistence; records are never deleted."""

    def actor_assignments(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
        maximum: int,
    ) -> Sequence[object]:
        rows = frappe.get_all(
            _ASSIGNMENT_DOCTYPE,
            filters={
                "tenant_id": tenant_id,
                "actor_user_id": actor_user_id,
                "active": 1,
            },
            fields=list(_ASSIGNMENT_FIELDS),
            order_by="global_id asc",
            limit_page_length=maximum + 1,
        )
        if len(rows) > maximum:
            raise RuntimeError("My Work actor assignment bound exceeded.")
        return tuple(rows)

    def upsert(self, spec: ProjectionSpec, *, indexed_at: datetime) -> UUID:
        snapshot = _projection_snapshot(spec)
        values = {
            "doctype": _ASSIGNMENT_DOCTYPE,
            "global_id": str(spec.global_id),
            "assignment_key": spec.assignment_key,
            "tenant_id": spec.tenant_id,
            "actor_user_id": spec.actor_user_id,
            "project_global_id": str(spec.project_global_id),
            "source_type": spec.source_type.value,
            "source_global_id": str(spec.source_global_id),
            "source_version": spec.source_version,
            "assignment_code": spec.assignment_code,
            "category": spec.category.value,
            "due_at": _database_datetime(spec.due_at),
            "priority_scheme": (
                spec.priority.scheme.value if spec.priority is not None else None
            ),
            "priority_value": (
                spec.priority.value if spec.priority is not None else None
            ),
            "blocking": int(spec.blocking),
            "active": 1,
            "source_snapshot": _canonical_json(snapshot),
            "snapshot_hash": _sha256_json(snapshot),
            "indexed_at": _database_datetime(indexed_at),
        }
        document = _optional_doc(_ASSIGNMENT_DOCTYPE, str(spec.global_id))
        with _controlled_projection_write_scope():
            if document is None:
                frappe.get_doc(values).insert()
            else:
                for fieldname, value in values.items():
                    if fieldname != "doctype":
                        document.set(fieldname, value)
                document.save()
        return spec.global_id

    def deactivate_source_except(
        self,
        *,
        tenant_id: str,
        source_type: MyWorkSourceType,
        source_global_id: UUID,
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None:
        names = self._active_names(
            {
                "tenant_id": tenant_id,
                "source_type": source_type.value,
                "source_global_id": str(source_global_id),
            },
            maximum=_MAX_SOURCE_ASSIGNMENTS,
        )
        self._deactivate_names(
            names,
            keep_assignment_keys=keep_assignment_keys,
            indexed_at=indexed_at,
        )

    def deactivate_tenant_except(
        self,
        *,
        tenant_id: str,
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None:
        self._deactivate_matching(
            {"tenant_id": tenant_id},
            keep_assignment_keys=keep_assignment_keys,
            indexed_at=indexed_at,
        )

    def deactivate_project_except(
        self,
        *,
        tenant_id: str,
        project_global_id: UUID,
        source_types: frozenset[MyWorkSourceType],
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None:
        if not source_types or not source_types.issubset(_PROJECT_SOURCE_TYPES):
            raise ValueError("My Work Project source types are invalid.")
        self._deactivate_matching(
            {
                "tenant_id": tenant_id,
                "project_global_id": str(project_global_id),
                "source_type": [
                    "in",
                    sorted(value.value for value in source_types),
                ],
            },
            keep_assignment_keys=keep_assignment_keys,
            indexed_at=indexed_at,
        )

    def deactivate_one(
        self,
        *,
        assignment_global_id: UUID,
        expected_snapshot_hash: str,
        indexed_at: datetime,
    ) -> bool:
        document = _optional_doc(
            _ASSIGNMENT_DOCTYPE,
            str(assignment_global_id),
        )
        if (
            document is None
            or str(document.snapshot_hash) != expected_snapshot_hash
            or not bool(document.active)
        ):
            return False
        self._deactivate_document(document, indexed_at=indexed_at)
        return True

    @staticmethod
    def _active_names(
        filters: Mapping[str, object],
        *,
        maximum: int,
    ) -> tuple[str, ...]:
        names = frappe.get_all(
            _ASSIGNMENT_DOCTYPE,
            filters={**dict(filters), "active": 1},
            pluck="name",
            order_by="global_id asc",
            limit_page_length=maximum + 1,
        )
        if len(names) > maximum:
            raise RuntimeError("My Work source assignment bound exceeded.")
        return tuple(str(value) for value in names)

    def _deactivate_names(
        self,
        names: Sequence[str],
        *,
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None:
        for name in names:
            document = _optional_doc(_ASSIGNMENT_DOCTYPE, name)
            if (
                document is not None
                and str(document.assignment_key) not in keep_assignment_keys
                and bool(document.active)
            ):
                self._deactivate_document(
                    document,
                    indexed_at=indexed_at,
                )

    def _deactivate_matching(
        self,
        filters: Mapping[str, object],
        *,
        keep_assignment_keys: frozenset[str],
        indexed_at: datetime,
    ) -> None:
        last_global_id: str | None = None
        while True:
            query_filters: list[list[object]] = []
            for fieldname, value in filters.items():
                if (
                    isinstance(value, (list, tuple))
                    and len(value) == 2
                    and value[0] == "in"
                ):
                    query_filters.append([fieldname, "in", value[1]])
                else:
                    query_filters.append([fieldname, "=", value])
            query_filters.append(["active", "=", 1])
            if last_global_id is not None:
                query_filters.append(["global_id", ">", last_global_id])
            names = tuple(
                str(value)
                for value in frappe.get_all(
                    _ASSIGNMENT_DOCTYPE,
                    filters=query_filters,
                    pluck="name",
                    order_by="global_id asc",
                    limit_page_length=_REBUILD_PAGE_SIZE,
                )
            )
            if not names:
                return
            next_global_id = names[-1]
            if (
                last_global_id is not None
                and next_global_id <= last_global_id
            ):
                raise RuntimeError(
                    "My Work assignment deactivation page did not advance."
                )
            self._deactivate_names(
                names,
                keep_assignment_keys=keep_assignment_keys,
                indexed_at=indexed_at,
            )
            last_global_id = next_global_id
            if len(names) < _REBUILD_PAGE_SIZE:
                return

    @staticmethod
    def _deactivate_document(document, *, indexed_at: datetime) -> None:
        snapshot = _json_object(document.source_snapshot)
        snapshot["active"] = False
        with _controlled_projection_write_scope():
            document.active = 0
            document.source_snapshot = _canonical_json(snapshot)
            document.snapshot_hash = _sha256_json(snapshot)
            document.indexed_at = _database_datetime(indexed_at)
            document.save()


def refresh_domain_work_item_assignment(
    document: object,
    method: str | None = None,
    *,
    store: MyWorkAssignmentStore | None = None,
    tenant_id: str | None = None,
    indexed_at: datetime | None = None,
    project: object | None = None,
) -> tuple[UUID, ...]:
    """Refresh one exact non-terminal owner projection from its source."""

    del method
    resolved_store = store or FrappeMyWorkAssignmentStore()
    now = _datetime_value(indexed_at or datetime.now(UTC))
    source = _source_document("NPI Domain Work Item", document)
    source_id = _uuid_value(_record(source, "global_id"))
    source_tenant = str(_record(source, "tenant_id"))
    effective_tenant = tenant_id or _configured_tenant_id()
    if source_tenant != effective_tenant:
        return ()
    source_project = project or _optional_doc(
        "NPI Engineering Project",
        str(_record(source, "project_global_id")),
    )
    spec = (
        _domain_projection_spec(source, source_project)
        if source_project is not None
        else None
    )
    keep = frozenset({spec.assignment_key} if spec is not None else set())
    if spec is not None:
        resolved_store.upsert(spec, indexed_at=now)
    resolved_store.deactivate_source_except(
        tenant_id=effective_tenant,
        source_type=MyWorkSourceType.DOMAIN_WORK_ITEM,
        source_global_id=source_id,
        keep_assignment_keys=keep,
        indexed_at=now,
    )
    return (spec.global_id,) if spec is not None else ()


def refresh_gate_review_assignments(
    document: object,
    method: str | None = None,
    *,
    store: MyWorkAssignmentStore | None = None,
    tenant_id: str | None = None,
    indexed_at: datetime | None = None,
    workspace_loader: (
        Callable[[str, UUID, UUID], GateWorkspaceAccess | None] | None
    ) = None,
) -> tuple[UUID, ...]:
    """Refresh exact current-cycle Gate assignments and invalidation work."""

    del method
    resolved_store = store or FrappeMyWorkAssignmentStore()
    now = _datetime_value(indexed_at or datetime.now(UTC))
    gate = _source_document("NPI Gate Shell", document)
    gate_id = _uuid_value(_record(gate, "global_id"))
    project_id = _uuid_value(_record(gate, "project_global_id"))
    project = _optional_doc("NPI Engineering Project", str(project_id))
    if project is None:
        return ()
    effective_tenant = tenant_id or _configured_tenant_id()
    if str(_record(project, "tenant_id")) != effective_tenant:
        return ()
    actors = _current_cycle_binding_actors(gate) if _project_is_mutable(project) else ()
    loader = workspace_loader or (
        lambda actor, selected_project, selected_gate: _gate_workspace_for_user(
            actor,
            effective_tenant,
            selected_project,
            selected_gate,
        )
    )
    specs: list[ProjectionSpec] = []
    for actor in actors:
        try:
            access = loader(actor, project_id, gate_id)
        except (KeyError, TypeError, ValueError):
            # A malformed or integrity-failed source workspace cannot grant
            # derived work. Keep no assignments for that actor so the
            # source-level deactivation below removes any stale projection.
            access = None
        if access is not None:
            specs.extend(_gate_projection_specs(access, actor=actor))
    unique = {spec.assignment_key: spec for spec in specs}
    if len(unique) != len(specs):
        raise RuntimeError("Gate My Work assignment identity is ambiguous.")
    for spec in unique.values():
        resolved_store.upsert(spec, indexed_at=now)
    for source_type in (
        MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
        MyWorkSourceType.GATE_REVIEW_INVALIDATION,
    ):
        keep = frozenset(
            spec.assignment_key
            for spec in unique.values()
            if spec.source_type is source_type
        )
        resolved_store.deactivate_source_except(
            tenant_id=effective_tenant,
            source_type=source_type,
            source_global_id=gate_id,
            keep_assignment_keys=keep,
            indexed_at=now,
        )
    return tuple(
        spec.global_id
        for spec in sorted(
            unique.values(),
            key=lambda value: value.assignment_key,
        )
    )


def refresh_gate_review_assignments_for_cycle(
    document: object,
    method: str | None = None,
    *,
    store: MyWorkAssignmentStore | None = None,
    tenant_id: str | None = None,
    indexed_at: datetime | None = None,
) -> tuple[UUID, ...]:
    """Refresh the owning Gate after a review-cycle state or opinion change."""

    del method
    cycle = _source_document("NPI Gate Review Cycle", document)
    gate = _optional_doc(
        "NPI Gate Shell",
        str(_record(cycle, "gate_global_id")),
    )
    if gate is None or str(_record(gate, "project_global_id")) != str(
        _record(cycle, "project_global_id")
    ):
        return ()
    return refresh_gate_review_assignments(
        gate,
        store=store,
        tenant_id=tenant_id,
        indexed_at=indexed_at,
    )


def refresh_project_my_work_assignments(
    document: object,
    method: str | None = None,
    *,
    store: MyWorkAssignmentStore | None = None,
    tenant_id: str | None = None,
    indexed_at: datetime | None = None,
    workspace_loader: (
        Callable[[str, UUID, UUID], GateWorkspaceAccess | None] | None
    ) = None,
) -> tuple[UUID, ...]:
    """Refresh one bounded Project projection, or durably deactivate history."""

    del method
    project = _source_document("NPI Engineering Project", document)
    project_id = _uuid_value(_record(project, "global_id"))
    effective_tenant = tenant_id or _configured_tenant_id()
    if str(_record(project, "tenant_id")) != effective_tenant:
        return ()
    resolved_store = store or FrappeMyWorkAssignmentStore()
    now = _datetime_value(indexed_at or datetime.now(UTC))
    if not _project_is_mutable(project):
        resolved_store.deactivate_project_except(
            tenant_id=effective_tenant,
            project_global_id=project_id,
            source_types=_PROJECT_SOURCE_TYPES,
            keep_assignment_keys=frozenset(),
            indexed_at=now,
        )
        return ()

    work_names = _bounded_names(
        "NPI Domain Work Item",
        {
            "tenant_id": effective_tenant,
            "project_global_id": str(project_id),
        },
    )
    gate_names = _bounded_names(
        "NPI Gate Shell",
        {"project_global_id": str(project_id)},
    )
    if len(work_names) + len(gate_names) > _MAX_REBUILD_SOURCES:
        raise RuntimeError("My Work Project refresh source bound exceeded.")
    retained: list[UUID] = []
    for name in work_names:
        retained.extend(
            refresh_domain_work_item_assignment(
                name,
                store=resolved_store,
                tenant_id=effective_tenant,
                indexed_at=now,
                project=project,
            )
        )
    for name in gate_names:
        retained.extend(
            refresh_gate_review_assignments(
                name,
                store=resolved_store,
                tenant_id=effective_tenant,
                indexed_at=now,
                workspace_loader=workspace_loader,
            )
        )
    keep_keys = frozenset(
        _assignment_key_for_global_id(value, resolved_store) for value in retained
    )
    resolved_store.deactivate_project_except(
        tenant_id=effective_tenant,
        project_global_id=project_id,
        source_types=_PROJECT_SOURCE_TYPES,
        keep_assignment_keys=keep_keys,
        indexed_at=now,
    )
    return tuple(retained)


def refresh_project_member_my_work_assignments(
    document: object,
    method: str | None = None,
    *,
    store: MyWorkAssignmentStore | None = None,
    tenant_id: str | None = None,
    indexed_at: datetime | None = None,
) -> tuple[UUID, ...]:
    """Refresh target authorization when Project membership changes."""

    del method
    member = _source_document("NPI Project Member", document)
    project = _optional_doc(
        "NPI Engineering Project",
        str(_record(member, "project_global_id")),
    )
    if project is None:
        return ()
    return refresh_project_my_work_assignments(
        project,
        store=store,
        tenant_id=tenant_id,
        indexed_at=indexed_at,
    )


def rebuild_my_work_projection(
    *,
    store: MyWorkAssignmentStore | None = None,
    tenant_id: str | None = None,
    indexed_at: datetime | None = None,
    workspace_loader: (
        Callable[[str, UUID, UUID], GateWorkspaceAccess | None] | None
    ) = None,
) -> MyWorkProjectionRebuildResult:
    """Rebuild the Site tenant projection without deleting retained rows."""

    resolved_store = store or FrappeMyWorkAssignmentStore()
    effective_tenant = tenant_id or _configured_tenant_id()
    now = _datetime_value(indexed_at or datetime.now(UTC))
    # A complete patch transaction first marks the retained projection
    # inactive in bounded pages, then exact live sources reactivate stable
    # identities. Any exception is rolled back by migrate; no delete is used.
    resolved_store.deactivate_tenant_except(
        tenant_id=effective_tenant,
        keep_assignment_keys=frozenset(),
        indexed_at=now,
    )
    digest = hashlib.sha256()
    source_count = 0
    assignment_count = 0

    def record(values: Sequence[UUID]) -> None:
        nonlocal assignment_count
        for value in values:
            digest.update(value.bytes)
            assignment_count += 1

    for work_names in _paged_names(
        "NPI Domain Work Item",
        {"tenant_id": effective_tenant},
    ):
        for name in work_names:
            source_count += 1
            record(
                refresh_domain_work_item_assignment(
                    name,
                    store=resolved_store,
                    tenant_id=effective_tenant,
                    indexed_at=now,
                )
            )
    for project_names in _paged_names(
        "NPI Engineering Project",
        {"tenant_id": effective_tenant},
    ):
        for project_name in project_names:
            for gate_names in _paged_names(
                "NPI Gate Shell",
                {"project_global_id": project_name},
            ):
                for name in gate_names:
                    source_count += 1
                    record(
                        refresh_gate_review_assignments(
                            name,
                            store=resolved_store,
                            tenant_id=effective_tenant,
                            indexed_at=now,
                            workspace_loader=workspace_loader,
                        )
                    )
    return MyWorkProjectionRebuildResult(
        source_count=source_count,
        assignment_count=assignment_count,
        assignment_digest=digest.hexdigest(),
    )


def deactivate_stale_assignment(
    assignment_global_id: UUID,
    expected_snapshot_hash: str,
    *,
    store: MyWorkAssignmentStore | None = None,
    indexed_at: datetime | None = None,
) -> bool:
    """Conditionally deactivate one stale row; GET intentionally never calls it."""

    if (
        not isinstance(assignment_global_id, UUID)
        or assignment_global_id.int == 0
        or not isinstance(expected_snapshot_hash, str)
        or _HASH_PATTERN.fullmatch(expected_snapshot_hash) is None
    ):
        raise ValueError("Stale assignment identity is invalid.")
    return (store or FrappeMyWorkAssignmentStore()).deactivate_one(
        assignment_global_id=assignment_global_id,
        expected_snapshot_hash=expected_snapshot_hash,
        indexed_at=_datetime_value(indexed_at or datetime.now(UTC)),
    )


def _domain_projection_spec(
    source: object,
    project: object,
) -> ProjectionSpec | None:
    if (
        bool(_record(source, "state_terminal"))
        or not _project_is_mutable(project)
        or str(_record(source, "tenant_id")) != str(_record(project, "tenant_id"))
        or str(_record(source, "project_global_id"))
        != str(_record(project, "global_id"))
    ):
        return None
    kind_value = str(_record(source, "kind"))
    category = _DOMAIN_CATEGORY.get(kind_value)
    if category is None:
        return None
    actor = _actor_value(_record(source, "owner_user_id"))
    source_id = _uuid_value(_record(source, "global_id"))
    project_id = _uuid_value(_record(source, "project_global_id"))
    tenant_id = _tenant_value(_record(source, "tenant_id"))
    source_version = _positive_int(_record(source, "optimistic_version"))
    priority = MyWorkPriority(
        MyWorkPriorityScheme.DOMAIN_SEVERITY,
        str(_record(source, "severity")),
    )
    assignment_key = _assignment_key(
        source_type=MyWorkSourceType.DOMAIN_WORK_ITEM,
        source_global_id=source_id,
        actor=actor,
        discriminator="owner",
    )
    blocking = _bool_value(_record(source, "blocking"))
    return ProjectionSpec(
        global_id=uuid5(_PROJECTION_NAMESPACE, assignment_key),
        assignment_key=assignment_key,
        tenant_id=tenant_id,
        actor_user_id=actor,
        project_global_id=project_id,
        source_type=MyWorkSourceType.DOMAIN_WORK_ITEM,
        source_global_id=source_id,
        source_version=source_version,
        assignment_code="domain_work_item_owner",
        category=category,
        due_at=_datetime_value(_record(source, "due_at")),
        priority=priority,
        blocking=blocking,
        status=(MyWorkStatus.BLOCKED if blocking else MyWorkStatus.READY),
        domain_kind=DomainWorkItemKind(kind_value),
        source_detail=(("domainKind", kind_value),),
        title=str(_record(source, "title")),
        project_business_code=str(_record(project, "business_code")),
        project_title=str(_record(project, "title")),
        context_code=str(source_id),
        context_title=str(_record(source, "title")),
    )


def _gate_projection_specs(
    access: GateWorkspaceAccess,
    *,
    actor: str,
) -> tuple[ProjectionSpec, ...]:
    if not access.internal or "NPI API User" not in access.roles:
        return ()
    try:
        return _validated_gate_projection_specs(access.workspace, actor=actor)
    except (KeyError, TypeError, ValueError):
        # A My Work index must never grant authority from a malformed or
        # partially drifted Gate workspace.
        return ()


def _validated_gate_projection_specs(
    workspace: Mapping[str, object],
    *,
    actor: str,
) -> tuple[ProjectionSpec, ...]:
    project = _mapping(workspace.get("project"))
    gate = _mapping(workspace.get("gate"))
    cycle = _mapping(workspace.get("activeCycle"))
    permissions = _mapping(workspace.get("permissions"))
    if not project or not gate or not cycle or not permissions:
        return ()
    if str(project.get("lifecycleState")) not in _MUTABLE_PROJECT_STATES:
        return ()

    canonical_actor = _canonical_actor_value(actor)
    stored_actor = _actor_value(canonical_actor)
    tenant_id = _tenant_value(workspace.get("tenantId"))
    project_id = _uuid_value(project.get("globalId"))
    gate_id = _uuid_value(gate.get("globalId"))
    cycle_id = _uuid_value(cycle.get("globalId"))
    gate_version = _positive_int(gate.get("version"))
    gate_state = str(gate.get("reviewState"))
    cycle_state = str(cycle.get("state"))
    expected_cycle_state = {
        "in_review": "active",
        "requires_review": "active",
        "decided": "decided",
    }.get(gate_state)
    if (
        expected_cycle_state is None
        or str(gate.get("currentCycleGlobalId")) != str(cycle_id)
        or cycle_state != expected_cycle_state
    ):
        return ()

    authority = _gate_authority_context(workspace, cycle)
    if authority is None:
        return ()
    eligible_members, bindings, purpose_slots, exception_slots = authority
    selected_steps = _gate_selected_steps(cycle, bindings, purpose_slots)
    if selected_steps is None:
        return ()

    def exact_current_assignee(slot: str) -> bool:
        binding = bindings.get(slot.casefold())
        return bool(
            binding is not None
            and binding[2] == canonical_actor
            and (binding[1], binding[2]) in eligible_members
        )

    def append_spec(
        result: list[ProjectionSpec],
        *,
        source_type: MyWorkSourceType,
        assignment_code: str,
        discriminator: str,
        status: MyWorkStatus,
        blocking: bool,
        source_detail: tuple[tuple[str, str], ...],
        due_at: datetime | None = None,
    ) -> None:
        assignment_key = _assignment_key(
            source_type=source_type,
            source_global_id=gate_id,
            actor=stored_actor,
            discriminator=discriminator,
        )
        result.append(
            ProjectionSpec(
                global_id=uuid5(_PROJECTION_NAMESPACE, assignment_key),
                assignment_key=assignment_key,
                tenant_id=tenant_id,
                actor_user_id=stored_actor,
                project_global_id=project_id,
                source_type=source_type,
                source_global_id=gate_id,
                source_version=gate_version,
                assignment_code=assignment_code,
                category=(
                    MyWorkCategory.BLOCKER
                    if source_type is MyWorkSourceType.GATE_REVIEW_INVALIDATION
                    else MyWorkCategory.APPROVAL
                ),
                due_at=due_at,
                priority=None,
                blocking=blocking,
                status=status,
                domain_kind=None,
                source_detail=source_detail,
                title=str(gate.get("title")),
                project_business_code=str(project.get("businessCode")),
                project_title=str(project.get("title")),
                context_code=str(gate.get("key")),
                context_title=str(gate.get("title")),
            )
        )

    result: list[ProjectionSpec] = []
    actor_steps = tuple(
        step
        for step in selected_steps
        if step["actor"] == canonical_actor
        and (step["member_id"], canonical_actor) in eligible_members
        and step["review"] is None
    )
    if gate_state == "in_review":
        for step in actor_steps:
            step_state = step["state"]
            if step_state == "available":
                if permissions.get("canReview") is not True:
                    continue
                status = MyWorkStatus.READY
            elif step_state == "waiting":
                status = MyWorkStatus.WAITING
            else:
                continue
            step_key = step["step_key"]
            append_spec(
                result,
                source_type=MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
                assignment_code="gate_review_step",
                discriminator=f"{cycle_id}:{step_key}",
                status=status,
                blocking=False,
                source_detail=(
                    ("cycleGlobalId", str(cycle_id)),
                    ("stepKey", step_key),
                ),
            )

        decision_slot = _single_purpose_slot(purpose_slots, "decision")
        if (
            permissions.get("canDecide") is True
            and decision_slot is not None
            and exact_current_assignee(decision_slot)
        ):
            append_spec(
                result,
                source_type=MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
                assignment_code="gate_final_decision",
                discriminator=f"{cycle_id}:decision:{decision_slot.casefold()}",
                status=MyWorkStatus.READY,
                blocking=False,
                source_detail=(
                    ("cycleGlobalId", str(cycle_id)),
                    ("authoritySlot", decision_slot),
                ),
            )

        if permissions.get("canApproveException") is True:
            exceptions = _gate_pending_exceptions(cycle, exception_slots)
            if exceptions is None:
                return ()
            for exception in exceptions:
                authority_slot = exception["authority_slot"]
                if not exact_current_assignee(authority_slot):
                    continue
                exception_id = exception["global_id"]
                append_spec(
                    result,
                    source_type=MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
                    assignment_code="gate_exception",
                    discriminator=f"{cycle_id}:exception:{exception_id}",
                    status=MyWorkStatus.READY,
                    blocking=False,
                    due_at=exception["expires_at"],
                    source_detail=(
                        ("cycleGlobalId", str(cycle_id)),
                        ("authoritySlot", authority_slot),
                        ("exceptionGlobalId", str(exception_id)),
                    ),
                )
    elif (
        gate_state == "requires_review"
        and permissions.get("canStartReview") is True
        and actor_steps
    ):
        minimum = min(step["sequence"] for step in actor_steps)
        for step in actor_steps:
            if step["sequence"] != minimum:
                continue
            step_key = step["step_key"]
            append_spec(
                result,
                source_type=MyWorkSourceType.GATE_REVIEW_INVALIDATION,
                assignment_code="gate_dependency_change",
                discriminator=f"{cycle_id}:{step_key}",
                status=MyWorkStatus.BLOCKED,
                blocking=True,
                source_detail=(
                    ("cycleGlobalId", str(cycle_id)),
                    ("stepKey", step_key),
                ),
            )
    elif gate_state == "decided":
        reopen_slot = _single_purpose_slot(purpose_slots, "reopen")
        if (
            permissions.get("canReopen") is True
            and reopen_slot is not None
            and exact_current_assignee(reopen_slot)
        ):
            append_spec(
                result,
                source_type=MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
                assignment_code="gate_reopen",
                discriminator=f"{cycle_id}:reopen:{reopen_slot.casefold()}",
                status=MyWorkStatus.READY,
                blocking=False,
                source_detail=(
                    ("cycleGlobalId", str(cycle_id)),
                    ("authoritySlot", reopen_slot),
                ),
            )

    assignment_keys = {spec.assignment_key for spec in result}
    if len(assignment_keys) != len(result):
        raise RuntimeError("Gate My Work assignment identity is ambiguous.")
    return tuple(result)


def _gate_authority_context(
    workspace: Mapping[str, object],
    cycle: Mapping[str, object],
) -> (
    tuple[
        frozenset[tuple[str, str]],
        dict[str, tuple[str, str, str]],
        dict[str, tuple[str, ...]],
        dict[str, str],
    ]
    | None
):
    eligible_members = _gate_eligible_members(workspace.get("eligibleMembers"))
    if eligible_members is None:
        return None

    bindings: dict[str, tuple[str, str, str]] = {}
    for value in _sequence(cycle.get("bindings")):
        binding = _mapping(value)
        if set(binding) != {
            "slot",
            "memberGlobalId",
            "userId",
            "displayName",
        }:
            return None
        slot = _controlled_key(binding["slot"])
        member_id = str(_uuid_value(binding["memberGlobalId"]))
        user_id = _canonical_actor_value(binding["userId"])
        _business_text(binding["displayName"], 140)
        slot_key = slot.casefold()
        if slot_key in bindings:
            return None
        bindings[slot_key] = (slot, member_id, user_id)

    policy = _mapping(cycle.get("policyDefinition"))
    if set(policy) != {"policyRef", "authoritySlots", "exceptionRules"}:
        return None
    policy_ref = _mapping(policy["policyRef"])
    cycle_policy_ref = _mapping(cycle.get("policyRef"))
    if (
        set(policy_ref) != {"globalId", "version", "snapshotHash"}
        or cycle_policy_ref != policy_ref
        or not isinstance(policy_ref["snapshotHash"], str)
        or _HASH_PATTERN.fullmatch(policy_ref["snapshotHash"]) is None
    ):
        return None
    _uuid_value(policy_ref["globalId"])
    _positive_int(policy_ref["version"])
    purpose_slots: dict[str, list[str]] = {
        "review": [],
        "decision": [],
        "reopen": [],
        "exception": [],
    }
    seen_authorities: set[tuple[str, str]] = set()
    for value in _sequence(policy.get("authoritySlots")):
        authority = _mapping(value)
        if set(authority) != {"slot", "purpose"}:
            return None
        slot = _controlled_key(authority["slot"])
        purpose = str(authority["purpose"])
        if purpose not in purpose_slots:
            return None
        identity = (slot.casefold(), purpose)
        if identity in seen_authorities:
            return None
        seen_authorities.add(identity)
        purpose_slots[purpose].append(slot)

    required_slots = {
        slot.casefold()
        for slots in purpose_slots.values()
        for slot in slots
    }
    if not required_slots or set(bindings) != required_slots:
        return None

    exception_slots: dict[str, str] = {}
    seen_exception_kinds: set[str] = set()
    exception_authority_slots = {
        value.casefold() for value in purpose_slots["exception"]
    }
    for value in _sequence(policy.get("exceptionRules")):
        rule = _mapping(value)
        if set(rule) != {
            "kind",
            "eligibleRequirementKeys",
            "approvalAuthoritySlot",
            "maximumValidityDays",
            "requiredClosureActionKind",
        }:
            return None
        kind = _controlled_key(rule["kind"])
        kind_key = kind.casefold()
        if kind_key in seen_exception_kinds:
            return None
        seen_exception_kinds.add(kind_key)
        requirement_keys = tuple(
            _controlled_key(candidate)
            for candidate in _sequence(rule["eligibleRequirementKeys"])
        )
        if (
            not requirement_keys
            or len({value.casefold() for value in requirement_keys})
            != len(requirement_keys)
            or _positive_int(rule["maximumValidityDays"]) > 3650
            or rule["requiredClosureActionKind"] != "action"
        ):
            return None
        slot = _controlled_key(rule["approvalAuthoritySlot"])
        if slot.casefold() not in exception_authority_slots:
            return None
        exception_slots[kind] = slot

    frozen_purpose_slots = {
        purpose: tuple(sorted(slots, key=str.casefold))
        for purpose, slots in purpose_slots.items()
    }
    return eligible_members, bindings, frozen_purpose_slots, exception_slots


def _gate_eligible_members(
    value: object,
) -> frozenset[tuple[str, str]] | None:
    result: set[tuple[str, str]] = set()
    normalized_users: dict[str, str] = {}
    normalized_members: dict[str, str] = {}
    for candidate in _sequence(value):
        member = _mapping(candidate)
        if set(member) != {"memberGlobalId", "userId", "displayName"}:
            return None
        member_id = str(_uuid_value(member["memberGlobalId"]))
        user_id = _canonical_actor_value(member["userId"])
        _business_text(member["displayName"], 140)
        user_key = user_id.casefold()
        if (
            (user_key in normalized_users and normalized_users[user_key] != member_id)
            or (
                member_id in normalized_members
                and normalized_members[member_id] != user_id
            )
            or (member_id, user_id) in result
        ):
            return None
        normalized_users[user_key] = member_id
        normalized_members[member_id] = user_id
        result.add((member_id, user_id))
    return frozenset(result)


def _gate_selected_steps(
    cycle: Mapping[str, object],
    bindings: Mapping[str, tuple[str, str, str]],
    purpose_slots: Mapping[str, tuple[str, ...]],
) -> tuple[dict[str, object], ...] | None:
    review_slots = {slot.casefold() for slot in purpose_slots.get("review", ())}
    result: list[dict[str, object]] = []
    step_keys: set[str] = set()
    for value in _sequence(cycle.get("selectedSteps")):
        step = _mapping(value)
        if set(step) != {
            "stepKey",
            "sequence",
            "slot",
            "assignedMember",
            "state",
            "review",
        }:
            return None
        step_key = _controlled_key(step["stepKey"])
        sequence = _positive_int(step["sequence"])
        slot = _controlled_key(step["slot"])
        assigned = _mapping(step["assignedMember"])
        if set(assigned) != {"memberGlobalId", "userId", "displayName"}:
            return None
        member_id = str(_uuid_value(assigned["memberGlobalId"]))
        user_id = _canonical_actor_value(assigned["userId"])
        _business_text(assigned["displayName"], 140)
        binding = bindings.get(slot.casefold())
        if (
            slot.casefold() not in review_slots
            or binding is None
            or binding[1:] != (member_id, user_id)
            or step_key.casefold() in step_keys
        ):
            return None
        step_keys.add(step_key.casefold())
        result.append(
            {
                "step_key": step_key,
                "sequence": sequence,
                "slot": slot,
                "member_id": member_id,
                "actor": user_id,
                "state": str(step["state"]),
                "review": step["review"],
            }
        )
    if not result:
        return None
    return tuple(
        sorted(
            result,
            key=lambda step: (int(step["sequence"]), str(step["step_key"]).casefold()),
        )
    )


def _gate_pending_exceptions(
    cycle: Mapping[str, object],
    exception_slots: Mapping[str, str],
) -> tuple[dict[str, object], ...] | None:
    result: list[dict[str, object]] = []
    identities: set[UUID] = set()
    for value in _sequence(cycle.get("exceptions")):
        exception = _mapping(value)
        required = {
            "globalId",
            "requirementGlobalId",
            "requirementKey",
            "kind",
            "reason",
            "risk",
            "requester",
            "requestedAt",
            "expiresAt",
            "requestSchemaVersion",
            "closureActionRef",
            "state",
            "allowedOutcomes",
            "version",
            "requestSnapshotHash",
            "decision",
        }
        if set(exception) != required:
            return None
        exception_id = _uuid_value(exception["globalId"])
        if exception_id in identities:
            return None
        identities.add(exception_id)
        kind = _controlled_key(exception["kind"])
        authority_slot = exception_slots.get(kind)
        if authority_slot is None:
            return None
        allowed_outcomes = tuple(_sequence(exception["allowedOutcomes"]))
        if (
            len(set(allowed_outcomes)) != len(allowed_outcomes)
            or any(
                not isinstance(outcome, str)
                or outcome not in {"approved", "rejected"}
                for outcome in allowed_outcomes
            )
        ):
            return None
        if str(exception["state"]) != "pending" or not allowed_outcomes:
            continue
        result.append(
            {
                "global_id": exception_id,
                "authority_slot": authority_slot,
                "expires_at": _datetime_value(exception["expiresAt"]),
            }
        )
    return tuple(sorted(result, key=lambda value: str(value["global_id"])))


def _single_purpose_slot(
    purpose_slots: Mapping[str, tuple[str, ...]],
    purpose: str,
) -> str | None:
    values = purpose_slots.get(purpose, ())
    return values[0] if len(values) == 1 else None


def _gate_workspace_for_principal(
    principal: Principal,
    project_id: UUID,
    gate_id: UUID,
    *,
    request_id: str,
    trace_id: str,
) -> GateWorkspaceAccess | None:
    from npi_core.gate_review.frappe_repository import (
        FrappeGateReviewRepository,
    )

    workspace = FrappeGateReviewRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    ).review_workspace(project_id, gate_id)
    if workspace is None:
        return None
    payload = dict(workspace)
    project = _mapping(payload.get("project"))
    if not project:
        return None
    source_project = _optional_doc(
        "NPI Engineering Project",
        str(project.get("globalId")),
    )
    if source_project is None or not _project_is_mutable(source_project):
        return None
    payload["project"] = {
        **project,
        "lifecycleState": str(_record(source_project, "lifecycle_state")),
    }
    payload["tenantId"] = str(_record(source_project, "tenant_id"))
    return GateWorkspaceAccess(
        workspace=payload,
        roles=principal.roles,
        internal=not principal.is_external,
    )


def _gate_workspace_for_user(
    actor: str,
    tenant_id: str,
    project_id: UUID,
    gate_id: UUID,
) -> GateWorkspaceAccess | None:
    user = frappe.db.get_value(
        "User",
        actor,
        ["enabled", "user_type"],
        as_dict=True,
    )
    if not user or not bool(user.enabled) or str(user.user_type) != "System User":
        return None
    principal = Principal(
        user_id=actor,
        roles=frozenset(frappe.get_roles(actor)),
        is_external=False,
        tenant_id=tenant_id,
    )
    identity = str(uuid4())
    return _gate_workspace_for_principal(
        principal,
        project_id,
        gate_id,
        request_id=identity,
        trace_id=identity,
    )


def _current_cycle_binding_actors(gate: object) -> tuple[str, ...]:
    cycle_id = _record(gate, "current_review_cycle_global_id", default=None)
    if not cycle_id:
        return ()
    cycle = _optional_doc("NPI Gate Review Cycle", str(cycle_id))
    if (
        cycle is None
        or str(_record(cycle, "gate_global_id")) != str(_record(gate, "global_id"))
        or str(_record(cycle, "project_global_id"))
        != str(_record(gate, "project_global_id"))
        or str(_record(cycle, "state")) not in {"active", "decided"}
    ):
        return ()
    try:
        bindings = _json_array(_record(cycle, "authority_bindings"))
        actors: dict[str, str] = {}
        slots: set[str] = set()
        for value in bindings:
            binding = _mapping(value)
            if set(binding) != {
                "slot",
                "memberGlobalId",
                "userId",
                "displayName",
            }:
                return ()
            slot = _controlled_key(binding["slot"]).casefold()
            actor = _canonical_actor_value(binding["userId"])
            _uuid_value(binding["memberGlobalId"])
            _business_text(binding["displayName"], 140)
            actor_key = actor.casefold()
            if (
                slot in slots
                or (actor_key in actors and actors[actor_key] != actor)
            ):
                return ()
            slots.add(slot)
            actors[actor_key] = actor
    except (KeyError, TypeError, ValueError):
        return ()
    return tuple(actors[key] for key in sorted(actors))


def _assignment_matches_spec(
    assignment: object,
    spec: ProjectionSpec,
) -> bool:
    try:
        due_at = _record(assignment, "due_at", default=None)
        priority_scheme = _record(
            assignment,
            "priority_scheme",
            default=None,
        )
        priority_value = _record(
            assignment,
            "priority_value",
            default=None,
        )
        return bool(
            str(_record(assignment, "global_id")) == str(spec.global_id)
            and str(_record(assignment, "assignment_key")) == spec.assignment_key
            and str(_record(assignment, "tenant_id")) == spec.tenant_id
            and str(_record(assignment, "actor_user_id")).casefold()
            == spec.actor_user_id
            and str(_record(assignment, "project_global_id"))
            == str(spec.project_global_id)
            and str(_record(assignment, "source_type")) == spec.source_type.value
            and str(_record(assignment, "source_global_id"))
            == str(spec.source_global_id)
            and _positive_int(_record(assignment, "source_version"))
            == spec.source_version
            and str(_record(assignment, "assignment_code")) == spec.assignment_code
            and str(_record(assignment, "category")) == spec.category.value
            and ((_datetime_value(due_at) if due_at else None) == spec.due_at)
            and (str(priority_scheme) if priority_scheme else None)
            == (spec.priority.scheme.value if spec.priority is not None else None)
            and (str(priority_value) if priority_value else None)
            == (spec.priority.value if spec.priority is not None else None)
            and bool(_record(assignment, "blocking")) is spec.blocking
            and bool(_record(assignment, "active"))
            and _validated_assignment_snapshot(assignment) == _projection_snapshot(spec)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _validated_assignment_snapshot(
    assignment: object,
) -> dict[str, object] | None:
    try:
        snapshot = _json_object(_record(assignment, "source_snapshot"))
        if (
            set(snapshot)
            != {
                "schemaVersion",
                "assignmentGlobalId",
                "assignmentKey",
                "tenantId",
                "actorUserId",
                "projectGlobalId",
                "sourceType",
                "sourceGlobalId",
                "sourceVersion",
                "assignmentCode",
                "category",
                "dueAt",
                "priority",
                "blocking",
                "active",
                "sourceDetail",
            }
            or _sha256_json(snapshot) != str(_record(assignment, "snapshot_hash"))
            or snapshot["assignmentGlobalId"] != str(_record(assignment, "global_id"))
            or snapshot["assignmentKey"] != str(_record(assignment, "assignment_key"))
            or snapshot["tenantId"] != str(_record(assignment, "tenant_id"))
            or str(snapshot["actorUserId"]).casefold()
            != str(_record(assignment, "actor_user_id")).casefold()
            or snapshot["projectGlobalId"]
            != str(_record(assignment, "project_global_id"))
            or snapshot["sourceType"] != str(_record(assignment, "source_type"))
            or snapshot["sourceGlobalId"]
            != str(_record(assignment, "source_global_id"))
            or snapshot["sourceVersion"] != int(_record(assignment, "source_version"))
            or snapshot["assignmentCode"] != str(_record(assignment, "assignment_code"))
            or snapshot["category"] != str(_record(assignment, "category"))
            or snapshot["blocking"] is not bool(_record(assignment, "blocking"))
            or snapshot["active"] is not bool(_record(assignment, "active"))
            or not isinstance(snapshot["sourceDetail"], dict)
        ):
            return None
        return snapshot
    except (KeyError, TypeError, ValueError):
        return None


def _projection_snapshot(spec: ProjectionSpec) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "assignmentGlobalId": str(spec.global_id),
        "assignmentKey": spec.assignment_key,
        "tenantId": spec.tenant_id,
        "actorUserId": spec.actor_user_id,
        "projectGlobalId": str(spec.project_global_id),
        "sourceType": spec.source_type.value,
        "sourceGlobalId": str(spec.source_global_id),
        "sourceVersion": spec.source_version,
        "assignmentCode": spec.assignment_code,
        "category": spec.category.value,
        "dueAt": (None if spec.due_at is None else _datetime_iso(spec.due_at)),
        "priority": (None if spec.priority is None else spec.priority.canonical_dict()),
        "blocking": spec.blocking,
        "active": True,
        "sourceDetail": spec.source_detail_dict(),
    }


def _counts_response(counts) -> dict[str, object]:
    return {
        "all": {
            "availability": counts.all.availability.value,
            "value": counts.all.value,
        },
        "today": {
            "availability": counts.today.availability.value,
            "value": counts.today.value,
        },
        "overdue": {
            "availability": counts.overdue.availability.value,
            "value": counts.overdue.value,
        },
        "approvals": {
            "availability": counts.approvals.availability.value,
            "value": counts.approvals.value,
        },
        "blockers": {
            "availability": counts.blockers.availability.value,
            "value": counts.blockers.value,
        },
        "waiting": {
            "availability": counts.waiting.availability.value,
            "value": counts.waiting.value,
        },
        "integration": {
            "availability": counts.integration.availability.value,
            "reason": counts.integration.reason.value,
        },
    }


def _query_cursor_codec(
    signing_key: bytes,
    *,
    query: MyWorkQuery,
    search: str | None,
    tenant_id: str,
    actor_user_id: str,
) -> MyWorkCursorCodec:
    if type(signing_key) is not bytes or len(signing_key) < 32:
        raise CursorSigningUnavailable()
    identity = {
        **query.identity_dict(),
        "actorUserId": _actor_value(actor_user_id),
        "search": search,
        "tenantId": _tenant_value(tenant_id),
    }
    fingerprint = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
    query_key = hmac.new(
        signing_key,
        _CURSOR_QUERY_CONTEXT + b":" + fingerprint.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return MyWorkCursorCodec(
        query_key,
        context=CURSOR_KEY_CONTEXT,
    )


def _matches_search(row: ResolvedMyWorkRow, search: str) -> bool:
    needle = search.casefold()
    return any(
        needle in value.casefold()
        for value in (
            row.title,
            row.project_business_code,
            row.project_title,
            row.context_code,
            row.context_title,
        )
    )


def _search_value(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("My Work search must be text.")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > 140
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ValueError("My Work search is invalid.")
    return normalized


def _my_work_cursor_signing_key() -> bytes:
    try:
        configuration = getattr(frappe, "conf", None)
        persisted_key = (
            configuration.get("encryption_key")
            if hasattr(configuration, "get")
            else None
        )
        if not isinstance(persisted_key, str):
            raise ValueError
        encoded = persisted_key.encode("ascii")
        decoded = base64.b64decode(
            encoded,
            altchars=b"-_",
            validate=True,
        )
        if len(decoded) != 32 or base64.urlsafe_b64encode(decoded) != encoded:
            raise ValueError
        return decoded
    except (TypeError, UnicodeError, ValueError) as error:
        raise CursorSigningUnavailable() from error


def _resolved_user_time_zone(actor: str) -> str:
    user_time_zone = frappe.db.get_value("User", actor, "time_zone")
    system_time_zone = frappe.db.get_single_value(
        "System Settings",
        "time_zone",
    )
    for candidate in (user_time_zone, system_time_zone):
        if isinstance(candidate, str) and candidate.strip():
            return _validated_time_zone(candidate.strip())
    raise RuntimeError("The effective user time zone is unavailable.")


def _validated_time_zone(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 64
        or value != value.strip()
    ):
        raise ValueError("The effective user time zone is invalid.")
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError("The effective user time zone is invalid.") from error
    return value


def _project_is_mutable(project: object) -> bool:
    return (
        str(_record(project, "lifecycle_state", default="")) in _MUTABLE_PROJECT_STATES
    )


def _assignment_key(
    *,
    source_type: MyWorkSourceType,
    source_global_id: UUID,
    actor: str,
    discriminator: str,
) -> str:
    actor_hash = hashlib.sha256(actor.casefold().encode("utf-8")).hexdigest()
    return f"{source_type.value}:{source_global_id}:" f"{discriminator}:{actor_hash}"


def _assignment_key_for_global_id(
    global_id: UUID,
    store: MyWorkAssignmentStore,
) -> str:
    if hasattr(store, "assignment_key"):
        value = store.assignment_key(global_id)  # type: ignore[attr-defined]
        if isinstance(value, str) and value:
            return value
    document = _optional_doc(_ASSIGNMENT_DOCTYPE, str(global_id))
    if document is None:
        raise RuntimeError("Rebuilt My Work assignment is unavailable.")
    return str(document.assignment_key)


def _bounded_names(
    doctype: str,
    filters: Mapping[str, object],
) -> tuple[str, ...]:
    names = frappe.get_all(
        doctype,
        filters=dict(filters),
        pluck="name",
        order_by="global_id asc",
        limit_page_length=_MAX_REBUILD_SOURCES + 1,
    )
    if len(names) > _MAX_REBUILD_SOURCES:
        raise RuntimeError("My Work rebuild source bound exceeded.")
    return tuple(str(value) for value in names)


def _paged_names(
    doctype: str,
    filters: Mapping[str, object],
) -> Iterator[tuple[str, ...]]:
    """Yield stable source-name pages without a tenant-wide volume ceiling."""

    last_global_id: str | None = None
    while True:
        query_filters = [
            [fieldname, "=", value]
            for fieldname, value in filters.items()
        ]
        if last_global_id is not None:
            query_filters.append(["global_id", ">", last_global_id])
        names = tuple(
            str(value)
            for value in frappe.get_all(
                doctype,
                filters=query_filters,
                pluck="name",
                order_by="global_id asc",
                limit_page_length=_REBUILD_PAGE_SIZE,
            )
        )
        if not names:
            break
        next_global_id = names[-1]
        if last_global_id is not None and next_global_id <= last_global_id:
            raise RuntimeError("My Work rebuild source page did not advance.")
        yield names
        last_global_id = next_global_id
        if len(names) < _REBUILD_PAGE_SIZE:
            break


def _configured_tenant_id() -> str:
    from npi_core.request_security import configured_tenant_id

    return configured_tenant_id()


def _source_document(doctype: str, value: object):
    if isinstance(value, (str, UUID)):
        document = _optional_doc(doctype, str(value))
        if document is None:
            raise ValueError("My Work source is unavailable.")
        return document
    if str(_record(value, "doctype", default=doctype)) != doctype:
        raise ValueError("My Work source type is invalid.")
    return value


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


@contextmanager
def _controlled_projection_write_scope():
    flags = frappe.flags
    marker = object()
    previous = getattr(flags, "npi_my_work_projection_write", marker)
    flags.npi_my_work_projection_write = True
    try:
        yield
    finally:
        if previous is marker:
            try:
                delattr(flags, "npi_my_work_projection_write")
            except AttributeError:
                pass
        else:
            flags.npi_my_work_projection_write = previous


def _record(
    value: object,
    name: str,
    *,
    default: object = ...,
) -> object:
    if isinstance(value, Mapping) and name in value:
        return value[name]
    if hasattr(value, name):
        return getattr(value, name)
    if default is not ...:
        return default
    raise KeyError(name)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, (list, tuple)) else ()


def _json_object(value: object) -> dict[str, object]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return dict(parsed)


def _json_array(value: object) -> list[object]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array.")
    return parsed


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T"))
    else:
        raise ValueError("Expected a date and time.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _datetime_iso(value: datetime) -> str:
    return (
        _datetime_value(value).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _database_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _datetime_value(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def _uuid_value(value: object) -> UUID:
    parsed = UUID(str(value))
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise ValueError("Expected a canonical non-zero UUID.")
    return parsed


def _positive_int(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("Expected a positive integer.")
    return value


def _bool_value(value: object) -> bool:
    if type(value) is bool:
        return value
    if type(value) is int and value in {0, 1}:
        return bool(value)
    raise ValueError("Expected a true or false value.")


def _actor_value(value: object) -> str:
    return _canonical_actor_value(value).casefold()


def _canonical_actor_value(value: object) -> str:
    if not isinstance(value, str) or _ACTOR_PATTERN.fullmatch(value) is None:
        raise ValueError("Expected an actor identity.")
    return value


def _tenant_value(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("Expected a tenant identity.")
    return value


def _controlled_key(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 64
        or re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", value) is None
    ):
        raise ValueError("Expected a controlled key.")
    return value


def _business_text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError("Expected bounded business text.")
    return value.strip()


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
