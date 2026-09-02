from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Callable, Iterable, Mapping, Sequence

import frappe

from npi_core.foundation.errors import CursorSigningUnavailable, PermissionDenied
from npi_core.foundation.security import Principal, authorize_tenant
from npi_core.reporting.domain import (
    CONFIGURATION_CAPABILITIES,
    KPI_DEFINITIONS,
    Availability,
    PageCursor,
    PortfolioFilters,
    SearchKind,
    SourceSystem,
    decode_cursor,
    encode_cursor,
    query_fingerprint,
)


MAX_PROJECTS = 5_000
MAX_SOURCE_ROWS = 1_000
_CURSOR_CONTEXT = b"npi-one:p9-02:reporting-cursor:v1"


@dataclass(frozen=True, slots=True)
class _SearchSource:
    doctype: str
    kind: SearchKind
    project_field: str
    id_field: str
    version_field: str | None
    label_fields: tuple[str, ...]
    code_field: str | None
    route_suffix: str


_SEARCH_SOURCES = (
    _SearchSource("NPI Engineering Part", SearchKind.PART, "originating_project_global_id", "global_id", "optimistic_version", ("title",), None, "/tooling"),
    _SearchSource("NPI Tooling Master", SearchKind.TOOLING, "originating_project_global_id", "global_id", None, ("title",), None, "/tooling"),
    _SearchSource("NPI Controlled Document", SearchKind.DOCUMENT, "project_global_id", "global_id", "optimistic_version", ("title", "document_number"), "document_number", "/documents"),
    _SearchSource("NPI Trial Round", SearchKind.TRIAL, "project_global_id", "global_id", "optimistic_version", ("display_label",), None, "/trials"),
    _SearchSource("NPI Trial Defect Revision", SearchKind.DEFECT, "project_global_id", "defect_global_id", "defect_version", ("title", "business_code"), "business_code", "/trials"),
    _SearchSource("NPI Tooling Defect Revision", SearchKind.DEFECT, "project_global_id", "defect_global_id", "defect_version", ("title", "business_code"), "business_code", "/tooling"),
    _SearchSource("NPI Engineering Change", SearchKind.CHANGE, "project_global_id", "global_id", "optimistic_version", ("title",), None, "/changes"),
    _SearchSource("NPI File Revision", SearchKind.FILE, "project_global_id", "global_id", "optimistic_version", ("file_name",), "file_name", "/documents"),
)


class FrappeReportingRepository:
    """Bounded read adapter; it never calls ERPNext or writes source records."""

    def __init__(
        self,
        *,
        principal: Principal,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id.casefold()
        self.clock = clock or (lambda: datetime.now(UTC))
        if principal.tenant_id is None:
            raise PermissionDenied()
        authorize_tenant(principal, principal.tenant_id)

    def portfolio(
        self,
        *,
        filters: PortfolioFilters,
        cursor: object | None,
        limit: int,
    ) -> dict[str, object]:
        now = self.clock().astimezone(UTC)
        visible = self._visible_projects(now.date())
        fingerprint = query_fingerprint(
            "project_portfolio",
            {
                "actor": self.actor,
                "tenantId": self.principal.tenant_id,
                **filters.canonical_dict(),
            },
        )
        position = (
            None
            if cursor is None
            else decode_cursor(cursor, self._cursor_signing_key(), fingerprint)
        )
        rows: list[dict[str, object]] = []
        for document in visible:
            references = self._project_references(document)
            if not self._matches_project(document, references, filters):
                continue
            rows.append(self._portfolio_row(document, references, now))
        rows.sort(key=lambda item: (str(item["targetSop"]), str(item["globalId"])))
        if position is not None:
            rows = [
                item
                for item in rows
                if (str(item["targetSop"]), str(item["globalId"]))
                > (position.sort_value, position.global_id)
            ]
        selected = rows[: limit + 1]
        has_more = len(selected) > limit
        selected = selected[:limit]
        next_cursor = None
        if has_more and selected:
            last = selected[-1]
            next_cursor = encode_cursor(
                PageCursor(fingerprint, str(last["targetSop"]), str(last["globalId"])),
                self._cursor_signing_key(),
            )
        return {
            "schemaVersion": 1,
            "asOf": _utc(now),
            "filters": filters.canonical_dict(),
            "items": selected,
            "page": {"limit": limit, "hasMore": has_more, "nextCursor": next_cursor},
            "permissions": {"serverFiltered": True},
        }

    def global_search(
        self,
        *,
        query: str,
        kinds: tuple[SearchKind, ...],
        cursor: object | None,
        limit: int,
    ) -> dict[str, object]:
        now = self.clock().astimezone(UTC)
        projects = self._visible_projects(now.date())
        project_by_id = {str(_value(item, "global_id")): item for item in projects}
        project_ids = frozenset(project_by_id)
        fingerprint = query_fingerprint(
            "global_search",
            {
                "actor": self.actor,
                "kinds": [kind.value for kind in kinds],
                "query": query.casefold(),
                "tenantId": self.principal.tenant_id,
            },
        )
        position = (
            None
            if cursor is None
            else decode_cursor(cursor, self._cursor_signing_key(), fingerprint)
        )
        results: list[dict[str, object]] = []
        if SearchKind.PROJECT in kinds:
            results.extend(self._project_search_results(projects, query))
        if SearchKind.CUSTOMER in kinds:
            results.extend(self._customer_search_results(projects, query))
        for source in _SEARCH_SOURCES:
            if source.kind in kinds:
                results.extend(self._object_search_results(source, project_ids, query))
        unique: dict[tuple[str, str], dict[str, object]] = {}
        for item in results:
            key = (str(item["kind"]), str(item["globalId"]))
            existing = unique.get(key)
            if existing is None or int(item.get("version", 0)) > int(existing.get("version", 0)):
                unique[key] = item
        ordered = sorted(
            unique.values(),
            key=lambda item: (
                str(item["label"]).casefold(),
                str(item["kind"]),
                str(item["globalId"]),
            ),
        )
        if position is not None:
            ordered = [
                item
                for item in ordered
                if (
                    str(item["label"]).casefold() + "\x1f" + str(item["kind"]),
                    str(item["globalId"]),
                )
                > (position.sort_value, position.global_id)
            ]
        selected = ordered[: limit + 1]
        has_more = len(selected) > limit
        selected = selected[:limit]
        next_cursor = None
        if has_more and selected:
            last = selected[-1]
            next_cursor = encode_cursor(
                PageCursor(
                    fingerprint,
                    str(last["label"]).casefold() + "\x1f" + str(last["kind"]),
                    str(last["globalId"]),
                ),
                self._cursor_signing_key(),
            )
        return {
            "schemaVersion": 1,
            "query": query,
            "kinds": [kind.value for kind in kinds],
            "items": selected,
            "page": {"limit": limit, "hasMore": has_more, "nextCursor": next_cursor},
            "permissions": {"serverFiltered": True},
        }

    def kpi_trends(
        self,
        *,
        from_month: str,
        to_month: str,
        filters: PortfolioFilters,
    ) -> dict[str, object]:
        # Each named calculation is frozen now; values remain unavailable until
        # its exact controlled source dates/mappings exist. Modified timestamps
        # and raw ERP statuses are intentionally never used as business truth.
        projects = [
            item
            for item in self._visible_projects(self.clock().date())
            if self._matches_project(item, self._project_references(item), filters)
        ]
        return {
            "schemaVersion": 1,
            "fromMonth": from_month,
            "toMonth": to_month,
            "filters": filters.canonical_dict(),
            "visibleProjectCount": len(projects),
            "series": [
                {
                    "definition": definition.public_dict(),
                    "availability": Availability.UNAVAILABLE.value,
                    "reasonCode": _kpi_unavailable_reason(definition.key),
                    "points": [],
                }
                for definition in KPI_DEFINITIONS
            ],
            "permissions": {"serverFiltered": True},
        }

    def configuration_catalog(self) -> dict[str, object]:
        if self.principal.is_external or "System Manager" not in self.principal.roles:
            raise PermissionDenied()
        return {
            "schemaVersion": 1,
            "mode": "read_only_catalog",
            "genericWriterAvailable": False,
            "items": [dict(value) for value in CONFIGURATION_CAPABILITIES],
        }

    def _visible_projects(self, today: date) -> list[Any]:
        rows = frappe.get_all(
            "NPI Engineering Project",
            filters={"tenant_id": self.principal.tenant_id},
            fields=[
                "global_id",
                "tenant_id",
                "business_code",
                "title",
                "project_type",
                "owner_user_id",
                "target_sop",
                "lifecycle_state",
                "optimistic_version",
                "current_health_status",
                "current_health_at",
                "modified",
            ],
            order_by="target_sop asc, global_id asc",
            limit_page_length=MAX_PROJECTS + 1,
        )
        if len(rows) > MAX_PROJECTS:
            raise RuntimeError("The reporting Project scope exceeds its safe bound.")
        if self._is_internal_system_manager():
            return list(rows)
        member_projects = self._active_member_project_ids(today)
        return [
            row
            for row in rows
            if str(_value(row, "owner_user_id")).casefold() == self.actor
            or str(_value(row, "global_id")) in member_projects
        ]

    def _active_member_project_ids(self, today: date) -> frozenset[str]:
        rows = frappe.get_all(
            "NPI Project Member",
            filters={"tenant_id": self.principal.tenant_id, "user_id": self.principal.user_id},
            fields=["project_global_id", "effective_from", "effective_to"],
            limit_page_length=MAX_PROJECTS + 1,
        )
        if len(rows) > MAX_PROJECTS:
            raise RuntimeError("The reporting membership scope exceeds its safe bound.")
        return frozenset(
            str(_value(row, "project_global_id"))
            for row in rows
            if _date(_value(row, "effective_from")) <= today
            and (
                _value(row, "effective_to", None) is None
                or _date(_value(row, "effective_to")) >= today
            )
        )

    def _project_references(self, project: Any) -> dict[str, tuple[str, ...]]:
        document = frappe.get_doc("NPI Engineering Project", str(_value(project, "global_id")))
        if str(_value(document, "tenant_id")) != self.principal.tenant_id:
            raise RuntimeError("A reporting Project escaped its tenant boundary.")
        grouped: dict[str, list[str]] = {}
        for row in getattr(document, "references", ()):
            grouped.setdefault(str(_value(row, "reference_type")), []).append(
                str(_value(row, "source_object_id"))
            )
        return {key: tuple(sorted(set(values))) for key, values in grouped.items()}

    @staticmethod
    def _matches_project(
        project: Any,
        references: Mapping[str, tuple[str, ...]],
        filters: PortfolioFilters,
    ) -> bool:
        if filters.customer_reference_key is not None and filters.customer_reference_key not in references.get("customer", ()):
            return False
        if filters.factory_reference_key is not None and filters.factory_reference_key not in references.get("factory", ()):
            return False
        if filters.owner_user_id is not None and str(_value(project, "owner_user_id")).casefold() != filters.owner_user_id:
            return False
        if filters.project_type is not None and str(_value(project, "project_type")) != filters.project_type:
            return False
        if filters.lifecycle_state is not None and str(_value(project, "lifecycle_state")) != filters.lifecycle_state:
            return False
        if filters.sop_month is not None and _date(_value(project, "target_sop")).strftime("%Y-%m") != filters.sop_month:
            return False
        return True

    def _portfolio_row(
        self,
        project: Any,
        references: Mapping[str, tuple[str, ...]],
        now: datetime,
    ) -> dict[str, object]:
        project_id = str(_value(project, "global_id"))
        work_items = frappe.get_all(
            "NPI Domain Work Item",
            filters={"tenant_id": self.principal.tenant_id, "project_global_id": project_id},
            fields=["kind", "due_at", "blocking", "state_terminal"],
            limit_page_length=MAX_SOURCE_ROWS + 1,
        )
        if len(work_items) > MAX_SOURCE_ROWS:
            raise RuntimeError("A Project reporting Work Item scope exceeds its safe bound.")
        active = [item for item in work_items if not bool(_value(item, "state_terminal"))]
        overdue = [item for item in active if _datetime(_value(item, "due_at")) < now]
        gates = frappe.get_all(
            "NPI Gate Shell",
            filters={"project_global_id": project_id},
            fields=["global_id", "gate_key", "title", "sequence", "gate_due_date", "review_state", "latest_decision_outcome"],
            order_by="sequence asc, global_id asc",
            limit_page_length=100,
        )
        current_gate = next(
            (gate for gate in gates if str(_value(gate, "latest_decision_outcome", "")) not in {"pass", "conditional_pass"}),
            None,
        )
        source = self._erp_source_summary(project_id)
        return {
            "schemaVersion": 1,
            "globalId": project_id,
            "businessCode": str(_value(project, "business_code")),
            "title": str(_value(project, "title")),
            "projectType": str(_value(project, "project_type")),
            "ownerUserId": str(_value(project, "owner_user_id")),
            "targetSop": _date(_value(project, "target_sop")).isoformat(),
            "lifecycleState": str(_value(project, "lifecycle_state")),
            "version": int(_value(project, "optimistic_version")),
            "customerReferenceKeys": list(references.get("customer", ())),
            "factoryReferenceKeys": list(references.get("factory", ())),
            "health": {
                "state": str(_value(project, "current_health_status")),
                "assessedAt": _optional_utc(_value(project, "current_health_at", None)),
                "sourceSystem": SourceSystem.NPI_ONE.value,
            },
            "currentGate": None if current_gate is None else {
                "globalId": str(_value(current_gate, "global_id")),
                "key": str(_value(current_gate, "gate_key")),
                "title": str(_value(current_gate, "title")),
                "sequence": int(_value(current_gate, "sequence")),
                "reviewState": str(_value(current_gate, "review_state")),
                "dueDate": _optional_date(_value(current_gate, "gate_due_date", None)),
            },
            "work": {
                "activeCount": len(active),
                "overdueCount": len(overdue),
                "blockerCount": sum(bool(_value(item, "blocking")) for item in active),
                "decisionCount": sum(str(_value(item, "kind")) == "decision_request" for item in active),
                "sourceSystem": SourceSystem.NPI_ONE.value,
            },
            "erp": source,
            "detailRoute": f"/projects/{project_id}",
        }

    def _erp_source_summary(self, project_id: str) -> dict[str, object]:
        try:
            rows = frappe.get_all(
                "NPI ERP Projection Head",
                filters={"tenant_id": self.principal.tenant_id, "project_global_id": project_id},
                fields=["projection_kind", "availability", "freshness", "updated_at"],
                limit_page_length=MAX_SOURCE_ROWS + 1,
            )
        except Exception as error:
            if _missing_doctype(error):
                return {
                    "sourceSystem": SourceSystem.ERPNEXT.value,
                    "availability": Availability.UNAVAILABLE.value,
                    "reasonCode": "erp_projection_store_unavailable",
                    "observedKinds": [],
                    "freshestAt": None,
                }
            raise
        if len(rows) > MAX_SOURCE_ROWS:
            raise RuntimeError("A Project ERP projection scope exceeds its safe bound.")
        if not rows:
            availability = Availability.UNAVAILABLE
            reason = "erp_projection_not_observed"
        else:
            states = tuple(_projection_availability(row) for row in rows)
            if all(state is Availability.AVAILABLE for state in states):
                availability = Availability.AVAILABLE
            elif all(state in {Availability.AVAILABLE, Availability.STALE} for state in states):
                availability = Availability.STALE
            else:
                availability = Availability.PARTIAL
            reason = None
        return {
            "sourceSystem": SourceSystem.ERPNEXT.value,
            "availability": availability.value,
            "reasonCode": reason,
            "observedKinds": sorted({str(_value(row, "projection_kind")) for row in rows}),
            "freshestAt": max(
                (
                    value
                    for row in rows
                    if (value := _optional_utc(_value(row, "updated_at", None))) is not None
                ),
                default=None,
            ),
        }

    @staticmethod
    def _project_search_results(projects: Sequence[Any], query: str) -> list[dict[str, object]]:
        needle = query.casefold()
        results = []
        for project in projects:
            label = str(_value(project, "title"))
            code = str(_value(project, "business_code"))
            if needle not in label.casefold() and needle not in code.casefold():
                continue
            project_id = str(_value(project, "global_id"))
            results.append({
                "schemaVersion": 1,
                "kind": SearchKind.PROJECT.value,
                "globalId": project_id,
                "projectGlobalId": project_id,
                "label": label,
                "code": code,
                "sourceSystem": SourceSystem.NPI_ONE.value,
                "availability": Availability.AVAILABLE.value,
                "detailRoute": f"/projects/{project_id}",
                "version": int(_value(project, "optimistic_version")),
            })
        return results

    def _customer_search_results(self, projects: Sequence[Any], query: str) -> list[dict[str, object]]:
        needle = query.casefold()
        results: dict[tuple[str, str], dict[str, object]] = {}
        for project in projects:
            project_id = str(_value(project, "global_id"))
            for customer in self._project_references(project).get("customer", ()):
                if needle not in customer.casefold():
                    continue
                key = (project_id, customer)
                results[key] = {
                    "schemaVersion": 1,
                    "kind": SearchKind.CUSTOMER.value,
                    "globalId": hashlib.sha256((project_id + "\x00" + customer).encode()).hexdigest(),
                    "projectGlobalId": project_id,
                    "label": customer,
                    "code": customer,
                    "sourceSystem": SourceSystem.ERPNEXT.value,
                    "availability": Availability.PARTIAL.value,
                    "reasonCode": "customer_reference_only",
                    "detailRoute": f"/projects/{project_id}",
                    "version": 1,
                }
        return list(results.values())

    def _object_search_results(
        self,
        source: _SearchSource,
        project_ids: frozenset[str],
        query: str,
    ) -> list[dict[str, object]]:
        if not project_ids:
            return []
        fields = list(dict.fromkeys((source.id_field, source.project_field, *source.label_fields)))
        if source.version_field is not None:
            fields.append(source.version_field)
        filters = {source.project_field: ["in", sorted(project_ids)]}
        or_filters = [[field, "like", f"%{query}%"] for field in source.label_fields]
        rows = frappe.get_all(
            source.doctype,
            filters=filters,
            or_filters=or_filters,
            fields=fields,
            order_by=f"{source.id_field} asc",
            limit_page_length=MAX_SOURCE_ROWS + 1,
        )
        if len(rows) > MAX_SOURCE_ROWS:
            raise RuntimeError(f"The {source.kind.value} search scope exceeds its safe bound.")
        results = []
        for row in rows:
            project_id = str(_value(row, source.project_field))
            if project_id not in project_ids:
                raise RuntimeError("A search result escaped its Project permission boundary.")
            label = next((str(_value(row, field)) for field in source.label_fields if _value(row, field, None)), "")
            global_id = str(_value(row, source.id_field))
            results.append({
                "schemaVersion": 1,
                "kind": source.kind.value,
                "globalId": global_id,
                "projectGlobalId": project_id,
                "label": label,
                "code": None if source.code_field is None else str(_value(row, source.code_field)),
                "sourceSystem": SourceSystem.NPI_ONE.value,
                "availability": Availability.AVAILABLE.value,
                "detailRoute": f"/projects/{project_id}{source.route_suffix}",
                "version": int(
                    _value(row, source.version_field, 1)
                    if source.version_field is not None
                    else 1
                ),
            })
        return results

    def _cursor_signing_key(self) -> bytes:
        try:
            configuration = getattr(getattr(frappe, "local", None), "conf", None)
            if configuration is None:
                configuration = getattr(frappe, "conf", None)
            persisted = configuration.get("encryption_key")
            decoded = base64.b64decode(persisted.encode("ascii"), altchars=b"-_", validate=True)
            if len(decoded) != 32 or base64.urlsafe_b64encode(decoded) != persisted.encode("ascii"):
                raise ValueError
        except Exception as error:
            raise CursorSigningUnavailable() from error
        return hmac.new(decoded, _CURSOR_CONTEXT, hashlib.sha256).digest()

    def _is_internal_system_manager(self) -> bool:
        return not self.principal.is_external and "System Manager" in self.principal.roles


def _value(record: Any, field: str, default: Any = ...):
    if isinstance(record, Mapping):
        if field in record:
            return record[field]
    elif hasattr(record, field):
        return getattr(record, field)
    if default is not ...:
        return default
    raise RuntimeError(f"Persisted reporting field is missing: {field}")


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _optional_utc(value: object | None) -> str | None:
    return None if value in {None, ""} else _utc(_datetime(value))


def _optional_date(value: object | None) -> str | None:
    return None if value in {None, ""} else _date(value).isoformat()


def _projection_availability(row: Any) -> Availability:
    availability = str(_value(row, "availability"))
    freshness = str(_value(row, "freshness"))
    if availability != "available":
        return Availability.UNAVAILABLE
    return Availability.STALE if freshness != "fresh" else Availability.AVAILABLE


def _missing_doctype(error: Exception) -> bool:
    return type(error).__name__ in {"DoesNotExistError", "ProgrammingError"} and "DocType" in str(error)


def _kpi_unavailable_reason(key: str) -> str:
    return {
        "project_sop_on_time_rate": "controlled_project_completion_date_unavailable",
        "project_cycle_time_days": "controlled_project_activation_completion_dates_unavailable",
        "trial_first_pass_rate": "accepted_trial_plan_result_mapping_unavailable",
        "project_cost_variance_rate": "approved_budget_or_fresh_erp_cost_projection_unavailable",
    }[key]
