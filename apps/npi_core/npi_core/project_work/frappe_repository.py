from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import (
    CursorSigningUnavailable,
    PermissionDenied,
    RequestValidationFailed,
    VersionConflict,
)
from npi_core.foundation.security import (
    Principal,
    ProjectAccess,
    authorize_project,
)
from npi_core.project.domain import IdempotencyConflict
from npi_core.project.frappe_validation import canonical_json
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.project_work.domain import (
    BaselineEntry,
    DomainWorkItem,
    DomainWorkItemKind,
    KindLifecycle,
    LifecycleDefinition,
    LifecycleState,
    PolicyPublicationState,
    ProjectMember,
    ProjectRaciAssignment,
    ProjectRoleAssignment,
    ProjectSubstitution,
    ProjectTeam,
    ProjectWorkPolicySnapshot,
    ProjectWorkPolicyVersion,
    RaciContextType,
    RaciResponsibility,
    Severity,
    WbsDependency,
    WbsItem,
    WbsPlan,
    WbsPlanBaseline,
    capture_wbs_baseline as build_wbs_baseline,
    compare_wbs_baseline as compare_domain_wbs_baseline,
    create_domain_work_item as build_domain_work_item,
)


_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_BUSINESS_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_MISSING = object()
_DOMAIN_WORK_ITEM_CURSOR_VERSION = 2
_DOMAIN_WORK_ITEM_CURSOR_KEY_CONTEXT = (
    b"npi-one:project-work:domain-work-item-cursor:v2"
)
_DOMAIN_WORK_ITEM_PAGE_FIELDS = (
    "global_id",
    "project_global_id",
    "kind",
    "title",
    "detail",
    "stage_global_id",
    "wbs_item_global_id",
    "owner_user_id",
    "due_at",
    "severity",
    "blocking",
    "state_key",
    "state_label_source",
    "state_terminal",
    "work_policy_global_id",
    "work_policy_version",
    "work_policy_snapshot_hash",
    "relations",
    "optimistic_version",
    "creation",
    "modified",
)


@dataclass(frozen=True, slots=True)
class WorkCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class _DomainWorkItemCursor:
    due_at: datetime
    global_id: str
    as_of: datetime
    query_fingerprint: str


class FrappeProjectWorkRepository:
    """Authorized persistence adapter for the bounded P4-02 Project work slice."""

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

    def work_context(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id, ProjectAccess.VIEW)
        if project is None:
            return None
        return self._work_context_for(project)

    def list_domain_work_items(
        self,
        project_id: UUID,
        *,
        stage_id: UUID | None,
        owner_user_id: str | None,
        overdue: bool | None,
        kind: object | None,
        cursor: str | None,
        limit: int,
        work_item_id: object | None = None,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id, ProjectAccess.VIEW)
        if project is None:
            return None
        if work_item_id is not None:
            exact_id = _uuid_value(work_item_id, "workItemId")
            if any(
                value is not None
                for value in (stage_id, owner_user_id, overdue, kind, cursor)
            ):
                raise _field_problem(
                    "workItemId",
                    _(
                        "An exact WorkItem identity cannot be combined with collection filters or a cursor."
                    ),
                )
            exact_documents = frappe.get_all(
                "NPI Domain Work Item",
                filters={
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "global_id": str(exact_id),
                },
                fields=list(_DOMAIN_WORK_ITEM_PAGE_FIELDS),
                order_by="global_id asc",
                limit_page_length=2,
            )
            if not exact_documents:
                return None
            if len(exact_documents) != 1:
                raise RuntimeError("Exact Domain WorkItem identity is ambiguous.")
            as_of = datetime.now(UTC)
            return {
                "projectId": str(project_id),
                "projectVersion": int(project.optimistic_version),
                "items": [
                    self._domain_work_item_response(
                        exact_documents[0],
                        now=as_of,
                    )
                ],
                "nextCursor": None,
            }
        cursor_signing_key = _domain_work_item_cursor_signing_key()
        filters: list[list[object]] = [
            ["tenant_id", "=", str(project.tenant_id)],
            ["project_global_id", "=", str(project_id)],
        ]
        if stage_id is not None:
            filters.append(["stage_global_id", "=", str(stage_id)])
        if owner_user_id is not None:
            filters.append(["owner_user_id", "=", owner_user_id])
        if kind is not None:
            filters.append(["kind", "=", _enum_or_string(kind)])

        query_fingerprint = _domain_work_item_query_fingerprint(
            project_id=project_id,
            stage_id=stage_id,
            owner_user_id=owner_user_id,
            overdue=overdue,
            kind=kind,
        )
        cursor_value = (
            _decode_cursor(
                cursor,
                expected_query_fingerprint=query_fingerprint,
                signing_key=cursor_signing_key,
            )
            if cursor is not None
            else None
        )
        as_of = (
            cursor_value.as_of
            if cursor_value is not None
            else datetime.now(UTC)
        )
        keyset_cursor = (
            (cursor_value.due_at, cursor_value.global_id)
            if cursor_value is not None
            else None
        )
        page_size = limit + 1
        if overdue is True:
            documents = _query_domain_work_item_page(
                [
                    *filters,
                    ["state_terminal", "=", 0],
                    ["due_at", "<", _database_datetime(as_of)],
                ],
                cursor=keyset_cursor,
                limit=page_size,
            )
        elif overdue is False:
            terminal = _query_domain_work_item_page(
                [*filters, ["state_terminal", "=", 1]],
                cursor=keyset_cursor,
                limit=page_size,
            )
            not_yet_due = _query_domain_work_item_page(
                [
                    *filters,
                    ["state_terminal", "=", 0],
                    ["due_at", ">=", _database_datetime(as_of)],
                ],
                cursor=keyset_cursor,
                limit=page_size,
            )
            documents = _merge_domain_work_item_pages(
                terminal,
                not_yet_due,
                limit=page_size,
            )
        else:
            documents = _query_domain_work_item_page(
                filters,
                cursor=keyset_cursor,
                limit=page_size,
            )

        page = documents[: limit + 1]
        has_more = len(page) > limit
        page = page[:limit]
        next_cursor = (
            _encode_cursor(
                _work_item_sort_key(page[-1]),
                as_of=as_of,
                query_fingerprint=query_fingerprint,
                signing_key=cursor_signing_key,
            )
            if has_more and page
            else None
        )
        return {
            "projectId": str(project_id),
            "projectVersion": int(project.optimistic_version),
            "items": [
                self._domain_work_item_response(document, now=as_of)
                for document in page
            ],
            "nextCursor": next_cursor,
        }

    def configure_team(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: object,
        members: Sequence[object],
        role_assignments: Sequence[object],
        substitutions: Sequence[object],
        raci_assignments: Sequence[object],
    ) -> WorkCommandOutcome | None:
        project = self._locked_authorized_project(
            project_id,
            ProjectAccess.ADMINISTER,
        )
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "expectedProjectVersion": expected_project_version,
            "workPolicyRef": work_policy_ref,
            "members": members,
            "roleAssignments": role_assignments,
            "substitutions": substitutions,
            "raciAssignments": raci_assignments,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return WorkCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_project_version(project, expected_project_version)
        policy = self._load_policy(work_policy_ref)
        self._require_current_policy(project, policy["ref"])
        prepared = self._prepare_team(
            project,
            policy,
            members=members,
            role_assignments=role_assignments,
            substitutions=substitutions,
            raci_assignments=raci_assignments,
        )
        with _controlled_work_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.team.configure",
            )
            if isinstance(idempotency, dict):
                return WorkCommandOutcome(idempotency, replayed=True)
            self._upsert_team_documents(project, prepared)
            self._advance_project(project, policy["ref"])
            self._append_audit(
                operation="project.team.configure",
                global_id=project_id,
                object_version=int(project.optimistic_version),
                result="updated",
                summary={
                    "memberCount": len(prepared["members"]),
                    "raciCount": len(prepared["raci"]),
                    "requestId": self.request_id,
                    "roleAssignmentCount": len(prepared["roles"]),
                    "substitutionCount": len(prepared["substitutions"]),
                },
            )
            response = self._work_context_for(project)
            self._seal_idempotency(idempotency, response)
        return WorkCommandOutcome(response)

    def apply_work_plan(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: object,
        items: Sequence[object],
        dependencies: Sequence[object],
    ) -> WorkCommandOutcome | None:
        project = self._locked_authorized_project(
            project_id,
            ProjectAccess.ADMINISTER,
        )
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "expectedProjectVersion": expected_project_version,
            "workPolicyRef": work_policy_ref,
            "items": items,
            "dependencies": dependencies,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return WorkCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_project_version(project, expected_project_version)
        policy = self._load_policy(work_policy_ref)
        self._require_current_policy(project, policy["ref"])
        next_plan_revision = int(project.work_plan_revision or 0) + 1
        prepared = self._prepare_work_plan(
            project,
            policy,
            items=items,
            dependencies=dependencies,
            plan_revision=next_plan_revision,
        )
        with _controlled_work_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.work_plan.apply",
            )
            if isinstance(idempotency, dict):
                return WorkCommandOutcome(idempotency, replayed=True)
            self._upsert_plan_documents(project, prepared)
            project.work_plan_revision = next_plan_revision
            self._advance_project(project, policy["ref"])
            self._append_audit(
                operation="project.work_plan.apply",
                global_id=project_id,
                object_version=int(project.optimistic_version),
                result="updated",
                summary={
                    "dependencyCount": len(prepared["dependencies"]),
                    "itemCount": len(prepared["items"]),
                    "planRevision": next_plan_revision,
                    "requestId": self.request_id,
                },
            )
            response = self._work_context_for(project)
            self._seal_idempotency(idempotency, response)
        return WorkCommandOutcome(response)

    def capture_plan_baseline(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: object,
        label: str,
    ) -> WorkCommandOutcome | None:
        project = self._locked_authorized_project(
            project_id,
            ProjectAccess.ADMINISTER,
        )
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "expectedProjectVersion": expected_project_version,
            "workPolicyRef": work_policy_ref,
            "label": label,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return WorkCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_project_version(project, expected_project_version)
        policy = self._load_policy(work_policy_ref)
        self._require_current_policy(project, policy["ref"])
        if not isinstance(label, str) or not label.strip() or len(label) > 140:
            raise _field_problem(
                "label",
                _("Enter a Plan Baseline label with no more than 140 characters."),
            )
        base_filters = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project_id),
        }
        items = _project_documents(
            "NPI WBS Item",
            base_filters,
            order_by="wbs_code asc, global_id asc",
        )
        if not items:
            raise _field_problem(
                "workPolicyRef",
                _("Apply a Project work plan before capturing its baseline."),
            )
        baselines = _project_documents(
            "NPI WBS Plan Baseline",
            base_filters,
            order_by="captured_at asc, global_id asc",
        )
        if len(baselines) >= 100:
            raise _field_problem(
                "label",
                _("This Project already contains the maximum number of Plan Baselines."),
            )
        baseline_id = uuid4()
        captured_at = datetime.now(UTC)
        plan = _domain_wbs_plan_from_documents(
            project,
            policy["snapshot"],
            item_documents=items,
            dependency_documents=_project_documents(
                "NPI WBS Dependency",
                {**base_filters, "active": 1},
                order_by="global_id asc",
            ),
            role_documents=_project_documents(
                "NPI Project Role Assignment",
                base_filters,
                order_by="global_id asc",
            ),
            project_version=int(project.optimistic_version),
        )
        domain_baseline = build_wbs_baseline(
            plan,
            global_id=baseline_id,
            label=label,
            captured_at=captured_at,
            captured_by=self.actor,
        )
        with _controlled_work_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.plan_baseline.capture",
            )
            if isinstance(idempotency, dict):
                return WorkCommandOutcome(idempotency, replayed=True)
            baseline = frappe.get_doc(
                {
                    "doctype": "NPI WBS Plan Baseline",
                    "global_id": str(baseline_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "plan_revision": domain_baseline.plan_revision,
                    "project_version": domain_baseline.project_version,
                    "label": domain_baseline.label,
                    "work_policy_global_id": str(
                        domain_baseline.work_policy_global_id
                    ),
                    "work_policy_version": domain_baseline.work_policy_version,
                    "work_policy_snapshot_hash": (
                        domain_baseline.work_policy_snapshot_hash
                    ),
                    "snapshot_hash": domain_baseline.snapshot_hash,
                    "snapshot": domain_baseline.snapshot_payload,
                    "captured_at": _database_datetime(
                        domain_baseline.captured_at
                    ),
                    "captured_by": domain_baseline.captured_by,
                    "optimistic_version": domain_baseline.version,
                }
            ).insert()
            project.active_plan_baseline_global_id = str(baseline_id)
            self._advance_project(project, policy["ref"])
            self._append_audit(
                operation="project.plan_baseline.capture",
                global_id=baseline_id,
                object_version=domain_baseline.version,
                result="created",
                summary={
                    "itemCount": len(domain_baseline.entries),
                    "planRevision": domain_baseline.plan_revision,
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "snapshotHash": domain_baseline.snapshot_hash,
                },
            )
            response = _baseline_response(baseline)
            self._seal_idempotency(idempotency, response)
        return WorkCommandOutcome(response)

    def create_domain_work_item(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        expected_project_version: int,
        work_policy_ref: object,
        kind: object,
        title: str,
        detail: str | None,
        context: object,
        owner_user_id: str,
        due_at: datetime,
        severity: object,
        blocking: bool,
        related_work_item_ids: Sequence[UUID],
    ) -> WorkCommandOutcome | None:
        project = self._locked_authorized_project(
            project_id,
            ProjectAccess.ADMINISTER,
        )
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "expectedProjectVersion": expected_project_version,
            "workPolicyRef": work_policy_ref,
            "kind": kind,
            "title": title,
            "detail": detail,
            "context": context,
            "ownerUserId": owner_user_id,
            "dueAt": due_at,
            "severity": severity,
            "blocking": blocking,
            "relatedWorkItemIds": related_work_item_ids,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return WorkCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_project_version(project, expected_project_version)
        policy = self._load_policy(work_policy_ref)
        self._require_current_policy(project, policy["ref"])
        if (
            frappe.db.count(
                "NPI Domain Work Item",
                filters={
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                },
            )
            >= 10000
        ):
            raise _field_problem(
                "projectId",
                _(
                    "This Project already contains the maximum number of Domain Work Items."
                ),
            )
        item_id = uuid4()
        domain_item = self._prepare_domain_work_item(
            project,
            policy,
            item_id=item_id,
            kind=kind,
            title=title,
            detail=detail,
            context=context,
            owner_user_id=owner_user_id,
            due_at=due_at,
            severity=severity,
            blocking=blocking,
            related_work_item_ids=related_work_item_ids,
        )
        with _controlled_work_write_scope():
            idempotency = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project,
                "project.domain_work_item.create",
            )
            if isinstance(idempotency, dict):
                return WorkCommandOutcome(idempotency, replayed=True)
            item = frappe.get_doc(
                {
                    "doctype": "NPI Domain Work Item",
                    "global_id": str(item_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "stage_global_id": (
                        str(domain_item.stage_global_id)
                        if domain_item.stage_global_id is not None
                        else None
                    ),
                    "wbs_item_global_id": (
                        str(domain_item.wbs_item_global_id)
                        if domain_item.wbs_item_global_id is not None
                        else None
                    ),
                    "kind": domain_item.kind.value,
                    "title": domain_item.title,
                    "detail": domain_item.detail,
                    "owner_user_id": domain_item.owner_user_id,
                    "due_at": _database_datetime(domain_item.due_at),
                    "severity": domain_item.severity.value,
                    "blocking": domain_item.blocking,
                    "state_key": domain_item.state_key,
                    "state_label_source": domain_item.state_label_source,
                    "state_terminal": domain_item.state_terminal,
                    "work_policy_global_id": str(
                        domain_item.work_policy_global_id
                    ),
                    "work_policy_version": domain_item.work_policy_version,
                    "work_policy_snapshot_hash": (
                        domain_item.work_policy_snapshot_hash
                    ),
                    "relations": [
                        str(value)
                        for value in domain_item.related_work_item_ids
                    ],
                    "evidence_references": [],
                    "source_system": "NPI_ONE",
                    "optimistic_version": domain_item.version,
                }
            ).insert()
            self._advance_project(project, policy["ref"])
            self._append_audit(
                operation="project.domain_work_item.create",
                global_id=item_id,
                object_version=domain_item.version,
                result="created",
                summary={
                    "blocking": domain_item.blocking,
                    "kind": domain_item.kind.value,
                    "projectId": str(project_id),
                    "relatedCount": len(
                        domain_item.related_work_item_ids
                    ),
                    "requestId": self.request_id,
                    "severity": domain_item.severity.value,
                },
            )
            response = self._domain_work_item_response(item)
            self._seal_idempotency(idempotency, response)
        return WorkCommandOutcome(response)

    def _load_policy(self, reference: object) -> dict[str, Any]:
        policy_global_id = _uuid_value(
            _record_value(reference, "global_id", "globalId"),
            "workPolicyRef.globalId",
        )
        version = _positive_integer(
            _record_value(reference, "version"),
            "workPolicyRef.version",
        )
        supplied_hash = _hash_value(
            _record_value(reference, "snapshot_hash", "snapshotHash"),
            "workPolicyRef.snapshotHash",
        )
        document = _optional_doc(
            "NPI Project Work Policy Version",
            f"{policy_global_id}:{version}",
        )
        if document is None or str(document.publication_state) != "published":
            raise _field_problem(
                "workPolicyRef",
                _("Select an available published Project Work Policy version."),
            )
        if (
            str(UUID(str(document.policy_global_id))) != str(policy_global_id)
            or int(document.policy_version) != version
            or str(document.snapshot_hash) != supplied_hash
        ):
            raise _field_problem(
                "workPolicyRef",
                _("The Project Work Policy reference does not match its published version."),
            )
        role_keys = tuple(str(value) for value in _json_array(document.role_keys))
        wbs_lifecycle = _domain_lifecycle(_json_object(document.wbs_states))
        lifecycle_values = _json_array(document.work_item_lifecycles)
        lifecycles = tuple(
            KindLifecycle(
                DomainWorkItemKind(str(value["kind"])),
                _domain_lifecycle(
                    {
                        "initialStateKey": value["initialStateKey"],
                        "states": value["states"],
                    }
                ),
            )
            for value in lifecycle_values
            if isinstance(value, dict)
        )
        if len(lifecycles) != len(lifecycle_values):
            raise ValueError("Persisted Project Work Policy structure is invalid.")
        domain_policy = ProjectWorkPolicyVersion(
            global_id=UUID(str(document.global_id)),
            policy_global_id=policy_global_id,
            policy_key=str(document.policy_key),
            policy_version=version,
            version=int(document.optimistic_version),
            title=str(document.title),
            publication_state=PolicyPublicationState.PUBLISHED,
            role_keys=role_keys,
            wbs_lifecycle=wbs_lifecycle,
            work_item_lifecycles=lifecycles,
        )
        if domain_policy.snapshot_hash != supplied_hash:
            raise ValueError("Persisted Project Work Policy hash is invalid.")
        snapshot = domain_policy.snapshot()
        return {
            "ref": {
                "globalId": str(policy_global_id),
                "version": version,
                "snapshotHash": supplied_hash,
            },
            "snapshot": snapshot,
            "role_keys": frozenset(snapshot.role_keys),
            "wbs_states": {
                state.key: state.canonical_dict()
                for state in snapshot.wbs_lifecycle.states
            },
            "lifecycles": {
                lifecycle.kind.value: lifecycle.lifecycle.canonical_dict()
                for lifecycle in snapshot.work_item_lifecycles
            },
        }

    def _require_current_policy(
        self,
        project,
        policy_ref: Mapping[str, object],
    ) -> None:
        current = _project_policy_ref(project)
        if current is not None and current != dict(policy_ref):
            raise _field_problem(
                "workPolicyRef",
                _(
                    "The Project already uses a different Project Work Policy version."
                ),
            )

    def _prepare_team(
        self,
        project,
        policy: Mapping[str, Any],
        *,
        members: Sequence[object],
        role_assignments: Sequence[object],
        substitutions: Sequence[object],
        raci_assignments: Sequence[object],
    ) -> dict[str, list[dict[str, Any]]]:
        project_id = UUID(str(project.global_id))
        tenant_id = str(project.tenant_id)
        base_filters = {
            "tenant_id": tenant_id,
            "project_global_id": str(project_id),
        }
        merged_members = {
            str(UUID(str(document.global_id))): {
                "global_id": UUID(str(document.global_id)),
                "user_id": str(document.user_id),
                "effective_from": date.fromisoformat(
                    _date_iso(document.effective_from)
                ),
                "effective_to": (
                    date.fromisoformat(_date_iso(document.effective_to))
                    if document.effective_to
                    else None
                ),
            }
            for document in _project_documents(
                "NPI Project Member",
                base_filters,
                order_by="global_id asc",
            )
        }
        prepared_members: list[dict[str, Any]] = []
        for index, value in enumerate(members):
            path = f"members[{index}]"
            item = {
                "global_id": _uuid_value(
                    _record_value(value, "global_id", "globalId"),
                    f"{path}.globalId",
                ),
                "user_id": _email_value(
                    _record_value(value, "user_id", "userId"),
                    f"{path}.userId",
                ),
                "effective_from": _date_value(
                    _record_value(value, "effective_from", "effectiveFrom"),
                    f"{path}.effectiveFrom",
                ),
                "effective_to": _optional_date_value(
                    _record_value(
                        value,
                        "effective_to",
                        "effectiveTo",
                        default=None,
                    ),
                    f"{path}.effectiveTo",
                ),
            }
            _validate_date_range(
                item["effective_from"],
                item["effective_to"],
                f"{path}.effectiveTo",
            )
            self._require_same_project_identity(
                "NPI Project Member",
                item["global_id"],
                project_id,
                f"{path}.globalId",
                tenant_id=tenant_id,
            )
            key = str(item["global_id"])
            existing = merged_members.get(key)
            if key in {str(record["global_id"]) for record in prepared_members}:
                raise _field_problem(
                    f"{path}.globalId",
                    _("Project member global IDs must be unique."),
                )
            if (
                existing is not None
                and existing["user_id"].casefold() != item["user_id"].casefold()
            ):
                raise _field_problem(
                    f"{path}.userId",
                    _("An existing Project member identity cannot be changed."),
                )
            user_enabled = (
                frappe.db.get_value("User", item["user_id"], "enabled") == 1
            )
            closes_disabled_membership = (
                existing is not None
                and item["effective_from"] == existing["effective_from"]
                and item["effective_to"] is not None
                and (
                    existing["effective_to"] is None
                    or item["effective_to"] <= existing["effective_to"]
                )
            )
            if not user_enabled and not closes_disabled_membership:
                raise _field_problem(
                    f"{path}.userId",
                    _("Select an enabled Project member."),
                )
            merged_members[key] = item
            prepared_members.append(item)
        if len(merged_members) > 500:
            raise _field_problem(
                "members",
                _("A Project cannot contain more than 500 members."),
            )

        merged_roles = {
            str(UUID(str(document.global_id))): {
                "global_id": UUID(str(document.global_id)),
                "member_id": UUID(str(document.member_global_id)),
                "role_key": str(document.role_key),
                "effective_from": date.fromisoformat(
                    _date_iso(document.effective_from)
                ),
                "effective_to": (
                    date.fromisoformat(_date_iso(document.effective_to))
                    if document.effective_to
                    else None
                ),
            }
            for document in _project_documents(
                "NPI Project Role Assignment",
                base_filters,
                order_by="global_id asc",
            )
        }
        prepared_roles: list[dict[str, Any]] = []
        for index, value in enumerate(role_assignments):
            path = f"roleAssignments[{index}]"
            item = {
                "global_id": _uuid_value(
                    _record_value(value, "global_id", "globalId"),
                    f"{path}.globalId",
                ),
                "member_id": _uuid_value(
                    _record_value(value, "member_id", "memberId"),
                    f"{path}.memberId",
                ),
                "role_key": _key_value(
                    _record_value(value, "role_key", "roleKey"),
                    f"{path}.roleKey",
                ),
                "effective_from": _date_value(
                    _record_value(value, "effective_from", "effectiveFrom"),
                    f"{path}.effectiveFrom",
                ),
                "effective_to": _optional_date_value(
                    _record_value(
                        value,
                        "effective_to",
                        "effectiveTo",
                        default=None,
                    ),
                    f"{path}.effectiveTo",
                ),
            }
            _validate_date_range(
                item["effective_from"],
                item["effective_to"],
                f"{path}.effectiveTo",
            )
            member = merged_members.get(str(item["member_id"]))
            if member is None:
                raise _field_problem(
                    f"{path}.memberId",
                    _("Select a Project member from this Project."),
                )
            if item["role_key"] not in policy["role_keys"]:
                raise _field_problem(
                    f"{path}.roleKey",
                    _("Select a role allowed by the Project Work Policy."),
                )
            if not _interval_contains(member, item):
                raise _field_problem(
                    f"{path}.effectiveFrom",
                    _("A role assignment must remain within the member effective dates."),
                )
            self._require_same_project_identity(
                "NPI Project Role Assignment",
                item["global_id"],
                project_id,
                f"{path}.globalId",
                tenant_id=tenant_id,
            )
            key = str(item["global_id"])
            if key in {str(record["global_id"]) for record in prepared_roles}:
                raise _field_problem(
                    f"{path}.globalId",
                    _("Project role assignment global IDs must be unique."),
                )
            existing = merged_roles.get(key)
            if existing is not None and (
                existing["member_id"] != item["member_id"]
                or existing["role_key"] != item["role_key"]
            ):
                raise _field_problem(
                    f"{path}.globalId",
                    _("An existing Project role assignment cannot be redirected."),
                )
            merged_roles[key] = item
            prepared_roles.append(item)
        if len(merged_roles) > 1000:
            raise _field_problem(
                "roleAssignments",
                _("A Project cannot contain more than 1000 role assignments."),
            )
        _reject_overlapping_roles(merged_roles.values())

        merged_substitutions = {
            str(UUID(str(document.global_id))): {
                "global_id": UUID(str(document.global_id)),
                "role_assignment_id": UUID(
                    str(document.role_assignment_global_id)
                ),
                "substitute_member_id": UUID(
                    str(document.substitute_member_global_id)
                ),
                "effective_from": date.fromisoformat(
                    _date_iso(document.effective_from)
                ),
                "effective_to": date.fromisoformat(
                    _date_iso(document.effective_to)
                ),
            }
            for document in _project_documents(
                "NPI Project Substitution",
                base_filters,
                order_by="global_id asc",
            )
        }
        prepared_substitutions: list[dict[str, Any]] = []
        for index, value in enumerate(substitutions):
            path = f"substitutions[{index}]"
            item = {
                "global_id": _uuid_value(
                    _record_value(value, "global_id", "globalId"),
                    f"{path}.globalId",
                ),
                "role_assignment_id": _uuid_value(
                    _record_value(
                        value,
                        "role_assignment_id",
                        "roleAssignmentId",
                    ),
                    f"{path}.roleAssignmentId",
                ),
                "substitute_member_id": _uuid_value(
                    _record_value(
                        value,
                        "substitute_member_id",
                        "substituteMemberId",
                    ),
                    f"{path}.substituteMemberId",
                ),
                "effective_from": _date_value(
                    _record_value(value, "effective_from", "effectiveFrom"),
                    f"{path}.effectiveFrom",
                ),
                "effective_to": _date_value(
                    _record_value(value, "effective_to", "effectiveTo"),
                    f"{path}.effectiveTo",
                ),
            }
            _validate_date_range(
                item["effective_from"],
                item["effective_to"],
                f"{path}.effectiveTo",
            )
            role = merged_roles.get(str(item["role_assignment_id"]))
            substitute = merged_members.get(str(item["substitute_member_id"]))
            if role is None:
                raise _field_problem(
                    f"{path}.roleAssignmentId",
                    _("Select a role assignment from this Project."),
                )
            if substitute is None:
                raise _field_problem(
                    f"{path}.substituteMemberId",
                    _("Select a substitute member from this Project."),
                )
            if role["member_id"] == item["substitute_member_id"]:
                raise _field_problem(
                    f"{path}.substituteMemberId",
                    _("A role assignee cannot substitute for the same role assignment."),
                )
            if not _interval_contains(role, item) or not _interval_contains(
                substitute,
                item,
            ):
                raise _field_problem(
                    f"{path}.effectiveFrom",
                    _(
                        "A substitution must remain within both role and member effective dates."
                    ),
                )
            self._require_same_project_identity(
                "NPI Project Substitution",
                item["global_id"],
                project_id,
                f"{path}.globalId",
                tenant_id=tenant_id,
            )
            key = str(item["global_id"])
            if key in {
                str(record["global_id"]) for record in prepared_substitutions
            }:
                raise _field_problem(
                    f"{path}.globalId",
                    _("Project substitution global IDs must be unique."),
                )
            existing = merged_substitutions.get(key)
            if existing is not None and (
                existing["role_assignment_id"] != item["role_assignment_id"]
                or existing["substitute_member_id"] != item["substitute_member_id"]
            ):
                raise _field_problem(
                    f"{path}.globalId",
                    _("An existing Project substitution cannot be redirected."),
                )
            merged_substitutions[key] = item
            prepared_substitutions.append(item)
        if len(merged_substitutions) > 1000:
            raise _field_problem(
                "substitutions",
                _("A Project cannot contain more than 1000 substitutions."),
            )

        merged_raci = {
            str(UUID(str(document.global_id))): {
                "global_id": UUID(str(document.global_id)),
                "context_type": str(document.context_type),
                "context_id": UUID(str(document.context_global_id)),
                "responsibility_key": str(document.responsibility_key),
                "role_assignment_id": UUID(
                    str(document.role_assignment_global_id)
                ),
                "raci": str(document.responsibility),
            }
            for document in _project_documents(
                "NPI Project RACI Assignment",
                base_filters,
                order_by="global_id asc",
            )
        }
        prepared_raci: list[dict[str, Any]] = []
        for index, value in enumerate(raci_assignments):
            path = f"raciAssignments[{index}]"
            item = {
                "global_id": _uuid_value(
                    _record_value(value, "global_id", "globalId"),
                    f"{path}.globalId",
                ),
                "context_type": _enum_or_string(
                    _record_value(value, "context_type", "contextType")
                ),
                "context_id": _uuid_value(
                    _record_value(value, "context_id", "contextId"),
                    f"{path}.contextId",
                ),
                "responsibility_key": _key_value(
                    _record_value(
                        value,
                        "responsibility_key",
                        "responsibilityKey",
                    ),
                    f"{path}.responsibilityKey",
                ),
                "role_assignment_id": _uuid_value(
                    _record_value(
                        value,
                        "role_assignment_id",
                        "roleAssignmentId",
                    ),
                    f"{path}.roleAssignmentId",
                ),
                "raci": _enum_or_string(_record_value(value, "raci")),
            }
            if item["context_type"] not in {
                "project",
                "wbs_item",
                "domain_work_item",
            }:
                raise _field_problem(
                    f"{path}.contextType",
                    _("Select a supported RACI context type."),
                )
            if item["raci"] not in {
                "responsible",
                "accountable",
                "consulted",
                "informed",
            }:
                raise _field_problem(
                    f"{path}.raci",
                    _("Select a supported RACI responsibility."),
                )
            if str(item["role_assignment_id"]) not in merged_roles:
                raise _field_problem(
                    f"{path}.roleAssignmentId",
                    _("Select a role assignment from this Project."),
                )
            self._validate_raci_context(
                project_id,
                tenant_id,
                item["context_type"],
                item["context_id"],
                f"{path}.contextId",
            )
            self._require_same_project_identity(
                "NPI Project RACI Assignment",
                item["global_id"],
                project_id,
                f"{path}.globalId",
                tenant_id=tenant_id,
            )
            key = str(item["global_id"])
            if key in {str(record["global_id"]) for record in prepared_raci}:
                raise _field_problem(
                    f"{path}.globalId",
                    _("Project RACI assignment global IDs must be unique."),
                )
            existing = merged_raci.get(key)
            if existing is not None and any(
                existing[field] != item[field]
                for field in (
                    "context_type",
                    "context_id",
                    "responsibility_key",
                    "role_assignment_id",
                    "raci",
                )
            ):
                raise _field_problem(
                    f"{path}.globalId",
                    _("An existing Project RACI assignment cannot be changed."),
                )
            merged_raci[key] = item
            prepared_raci.append(item)
        if len(merged_raci) > 2000:
            raise _field_problem(
                "raciAssignments",
                _("A Project cannot contain more than 2000 RACI assignments."),
            )
        _reject_duplicate_raci(merged_raci.values())
        domain_team = ProjectTeam(
            tenant_id=tenant_id,
            project_global_id=project_id,
            policy=policy["snapshot"],
            members=tuple(
                ProjectMember(
                    global_id=value["global_id"],
                    tenant_id=tenant_id,
                    project_global_id=project_id,
                    user_id=value["user_id"],
                    effective_from=value["effective_from"],
                    effective_to=value["effective_to"],
                )
                for value in merged_members.values()
            ),
            role_assignments=tuple(
                ProjectRoleAssignment(
                    global_id=value["global_id"],
                    tenant_id=tenant_id,
                    project_global_id=project_id,
                    member_global_id=value["member_id"],
                    role_key=value["role_key"],
                    effective_from=value["effective_from"],
                    effective_to=value["effective_to"],
                )
                for value in merged_roles.values()
            ),
            substitutions=tuple(
                ProjectSubstitution(
                    global_id=value["global_id"],
                    tenant_id=tenant_id,
                    project_global_id=project_id,
                    role_assignment_global_id=value["role_assignment_id"],
                    substitute_member_global_id=value["substitute_member_id"],
                    effective_from=value["effective_from"],
                    effective_to=value["effective_to"],
                )
                for value in merged_substitutions.values()
            ),
            raci_assignments=tuple(
                ProjectRaciAssignment(
                    global_id=value["global_id"],
                    tenant_id=tenant_id,
                    project_global_id=project_id,
                    context_type=RaciContextType(value["context_type"]),
                    context_global_id=value["context_id"],
                    responsibility_key=value["responsibility_key"],
                    role_assignment_global_id=value["role_assignment_id"],
                    responsibility=RaciResponsibility(value["raci"]),
                )
                for value in merged_raci.values()
            ),
        )
        domain_team.validate_contexts(
            wbs_item_ids=frozenset(
                UUID(str(document.global_id))
                for document in _project_documents(
                    "NPI WBS Item",
                    base_filters,
                    order_by="global_id asc",
                )
            ),
            domain_work_item_ids=frozenset(
                UUID(str(document.global_id))
                for document in _project_documents(
                    "NPI Domain Work Item",
                    base_filters,
                    order_by="global_id asc",
                )
            ),
        )
        return {
            "members": prepared_members,
            "roles": prepared_roles,
            "substitutions": prepared_substitutions,
            "raci": prepared_raci,
        }

    def _prepare_work_plan(
        self,
        project,
        policy: Mapping[str, Any],
        *,
        items: Sequence[object],
        dependencies: Sequence[object],
        plan_revision: int,
    ) -> dict[str, list[dict[str, Any]]]:
        project_id = UUID(str(project.global_id))
        tenant_id = str(project.tenant_id)
        base_filters = {
            "tenant_id": tenant_id,
            "project_global_id": str(project_id),
        }
        merged_items = {
            str(UUID(str(document.global_id))): {
                "global_id": UUID(str(document.global_id)),
                "code": str(document.wbs_code),
                "title": str(document.title),
                "parent_id": (
                    UUID(str(document.parent_global_id))
                    if document.parent_global_id
                    else None
                ),
                "owner_role_assignment_id": (
                    UUID(str(document.owner_role_assignment_global_id))
                    if document.owner_role_assignment_global_id
                    else None
                ),
                "planned_start": date.fromisoformat(
                    _date_iso(document.planned_start)
                ),
                "planned_finish": date.fromisoformat(
                    _date_iso(document.planned_end)
                ),
                "actual_start": (
                    date.fromisoformat(_date_iso(document.actual_start))
                    if document.actual_start
                    else None
                ),
                "actual_finish": (
                    date.fromisoformat(_date_iso(document.actual_end))
                    if document.actual_end
                    else None
                ),
                "milestone": bool(document.milestone),
                "status_key": str(document.status_key),
                "status_label_source": str(document.status_label_source),
                "progress_percent": int(document.progress_percent),
                "critical": bool(document.critical_task),
                "work_policy_global_id": UUID(
                    str(document.work_policy_global_id)
                ),
                "work_policy_version": int(document.work_policy_version),
                "work_policy_snapshot_hash": str(
                    document.work_policy_snapshot_hash
                ),
                "plan_revision": int(document.plan_revision),
            }
            for document in _project_documents(
                "NPI WBS Item",
                base_filters,
                order_by="global_id asc",
            )
        }
        prepared_items: list[dict[str, Any]] = []
        for index, value in enumerate(items):
            path = f"items[{index}]"
            status_key = _key_value(
                _record_value(value, "status_key", "statusKey"),
                f"{path}.statusKey",
            )
            state = policy["wbs_states"].get(status_key)
            if state is None:
                raise _field_problem(
                    f"{path}.statusKey",
                    _("Select a WBS status allowed by the Project Work Policy."),
                )
            item = {
                "global_id": _uuid_value(
                    _record_value(value, "global_id", "globalId"),
                    f"{path}.globalId",
                ),
                "code": _business_code_value(
                    _record_value(value, "code"),
                    f"{path}.code",
                ),
                "title": _text_value(
                    _record_value(value, "title"),
                    f"{path}.title",
                    280,
                ),
                "parent_id": _optional_uuid_value(
                    _record_value(value, "parent_id", "parentId", default=None),
                    f"{path}.parentId",
                ),
                "owner_role_assignment_id": _optional_uuid_value(
                    _record_value(
                        value,
                        "owner_role_assignment_id",
                        "ownerRoleAssignmentId",
                        default=None,
                    ),
                    f"{path}.ownerRoleAssignmentId",
                ),
                "planned_start": _date_value(
                    _record_value(value, "planned_start", "plannedStart"),
                    f"{path}.plannedStart",
                ),
                "planned_finish": _date_value(
                    _record_value(value, "planned_finish", "plannedFinish"),
                    f"{path}.plannedFinish",
                ),
                "actual_start": _optional_date_value(
                    _record_value(
                        value,
                        "actual_start",
                        "actualStart",
                        default=None,
                    ),
                    f"{path}.actualStart",
                ),
                "actual_finish": _optional_date_value(
                    _record_value(
                        value,
                        "actual_finish",
                        "actualFinish",
                        default=None,
                    ),
                    f"{path}.actualFinish",
                ),
                "milestone": _bool_value(
                    _record_value(value, "milestone"),
                    f"{path}.milestone",
                ),
                "status_key": status_key,
                "status_label_source": str(state["labelSource"]),
                "progress_percent": _percentage_value(
                    _record_value(
                        value,
                        "progress_percent",
                        "progressPercent",
                    ),
                    f"{path}.progressPercent",
                ),
                "critical": _bool_value(
                    _record_value(value, "critical"),
                    f"{path}.critical",
                ),
                "work_policy_global_id": UUID(
                    str(policy["ref"]["globalId"])
                ),
                "work_policy_version": int(policy["ref"]["version"]),
                "work_policy_snapshot_hash": str(
                    policy["ref"]["snapshotHash"]
                ),
                "plan_revision": plan_revision,
            }
            _validate_date_range(
                item["planned_start"],
                item["planned_finish"],
                f"{path}.plannedFinish",
            )
            _validate_date_range(
                item["actual_start"],
                item["actual_finish"],
                f"{path}.actualFinish",
            )
            if item["owner_role_assignment_id"] is not None:
                self._require_related_project_document(
                    "NPI Project Role Assignment",
                    item["owner_role_assignment_id"],
                    project_id,
                    f"{path}.ownerRoleAssignmentId",
                    tenant_id=tenant_id,
                )
            self._require_same_project_identity(
                "NPI WBS Item",
                item["global_id"],
                project_id,
                f"{path}.globalId",
                tenant_id=tenant_id,
            )
            key = str(item["global_id"])
            if key in {str(record["global_id"]) for record in prepared_items}:
                raise _field_problem(
                    f"{path}.globalId",
                    _("WBS item global IDs must be unique."),
                )
            existing = merged_items.get(key)
            if existing is not None and existing["code"] != item["code"]:
                raise _field_problem(
                    f"{path}.code",
                    _("An existing WBS item code cannot be changed."),
                )
            merged_items[key] = item
            prepared_items.append(item)
        if len(merged_items) > 2000:
            raise _field_problem(
                "items",
                _("A Project cannot contain more than 2000 WBS items."),
            )
        _reject_duplicate_wbs_codes(merged_items.values())
        _validate_parent_graph(merged_items)

        merged_dependencies = {
            str(UUID(str(document.global_id))): {
                "global_id": UUID(str(document.global_id)),
                "predecessor_id": UUID(str(document.predecessor_global_id)),
                "successor_id": UUID(str(document.successor_global_id)),
                "plan_revision": int(document.plan_revision),
            }
            for document in _project_documents(
                "NPI WBS Dependency",
                {**base_filters, "active": 1},
                order_by="global_id asc",
            )
        }
        prepared_dependencies: list[dict[str, Any]] = []
        for index, value in enumerate(dependencies):
            path = f"dependencies[{index}]"
            dependency = {
                "global_id": _uuid_value(
                    _record_value(value, "global_id", "globalId"),
                    f"{path}.globalId",
                ),
                "predecessor_id": _uuid_value(
                    _record_value(
                        value,
                        "predecessor_item_id",
                        "predecessorItemId",
                    ),
                    f"{path}.predecessorItemId",
                ),
                "successor_id": _uuid_value(
                    _record_value(
                        value,
                        "successor_item_id",
                        "successorItemId",
                    ),
                    f"{path}.successorItemId",
                ),
                "plan_revision": plan_revision,
            }
            if dependency["predecessor_id"] == dependency["successor_id"]:
                raise _field_problem(
                    f"{path}.successorItemId",
                    _("A WBS dependency cannot reference the same item twice."),
                )
            for field_name in ("predecessor_id", "successor_id"):
                if str(dependency[field_name]) not in merged_items:
                    response_name = (
                        "predecessorItemId"
                        if field_name == "predecessor_id"
                        else "successorItemId"
                    )
                    raise _field_problem(
                        f"{path}.{response_name}",
                        _("Select a WBS item from this Project."),
                    )
            self._require_same_project_identity(
                "NPI WBS Dependency",
                dependency["global_id"],
                project_id,
                f"{path}.globalId",
                tenant_id=tenant_id,
            )
            key = str(dependency["global_id"])
            if key in {
                str(record["global_id"])
                for record in prepared_dependencies
            }:
                raise _field_problem(
                    f"{path}.globalId",
                    _("WBS dependency global IDs must be unique."),
                )
            existing = merged_dependencies.get(key)
            if existing is not None and (
                existing["predecessor_id"] != dependency["predecessor_id"]
                or existing["successor_id"] != dependency["successor_id"]
            ):
                raise _field_problem(
                    f"{path}.globalId",
                    _("An existing WBS dependency cannot be redirected."),
                )
            merged_dependencies[key] = dependency
            prepared_dependencies.append(dependency)
        if len(merged_dependencies) > 5000:
            raise _field_problem(
                "dependencies",
                _("A Project cannot contain more than 5000 WBS dependencies."),
            )
        _reject_duplicate_dependencies(merged_dependencies.values())
        _validate_dependency_graph(merged_items, merged_dependencies.values())
        role_documents = _project_documents(
            "NPI Project Role Assignment",
            base_filters,
            order_by="global_id asc",
        )
        WbsPlan(
            tenant_id=tenant_id,
            project_global_id=project_id,
            project_version=int(project.optimistic_version) + 1,
            policy=policy["snapshot"],
            items=tuple(
                WbsItem(
                    global_id=value["global_id"],
                    tenant_id=tenant_id,
                    project_global_id=project_id,
                    work_policy_global_id=value["work_policy_global_id"],
                    work_policy_version=value["work_policy_version"],
                    work_policy_snapshot_hash=value[
                        "work_policy_snapshot_hash"
                    ],
                    code=value["code"],
                    title=value["title"],
                    planned_start=value["planned_start"],
                    planned_finish=value["planned_finish"],
                    milestone=value["milestone"],
                    status_key=value["status_key"],
                    progress_percent=value["progress_percent"],
                    critical=value["critical"],
                    plan_revision=value["plan_revision"],
                    parent_global_id=value["parent_id"],
                    owner_role_assignment_global_id=value[
                        "owner_role_assignment_id"
                    ],
                    actual_start=value["actual_start"],
                    actual_finish=value["actual_finish"],
                )
                for value in merged_items.values()
            ),
            dependencies=tuple(
                WbsDependency(
                    global_id=value["global_id"],
                    tenant_id=tenant_id,
                    project_global_id=project_id,
                    predecessor_global_id=value["predecessor_id"],
                    successor_global_id=value["successor_id"],
                    plan_revision=value["plan_revision"],
                )
                for value in merged_dependencies.values()
            ),
            role_assignments=tuple(
                ProjectRoleAssignment(
                    global_id=UUID(str(document.global_id)),
                    tenant_id=tenant_id,
                    project_global_id=project_id,
                    member_global_id=UUID(str(document.member_global_id)),
                    role_key=str(document.role_key),
                    effective_from=date.fromisoformat(
                        _date_iso(document.effective_from)
                    ),
                    effective_to=(
                        date.fromisoformat(_date_iso(document.effective_to))
                        if document.effective_to
                        else None
                    ),
                    version=int(document.optimistic_version),
                )
                for document in role_documents
            ),
        )
        for item in prepared_items:
            item["policy_ref"] = policy["ref"]
        return {
            "items": prepared_items,
            "dependencies": prepared_dependencies,
        }

    def _prepare_domain_work_item(
        self,
        project,
        policy: Mapping[str, Any],
        *,
        item_id: UUID,
        kind: object,
        title: str,
        detail: str | None,
        context: object,
        owner_user_id: str,
        due_at: datetime,
        severity: object,
        blocking: bool,
        related_work_item_ids: Sequence[UUID],
    ) -> DomainWorkItem:
        project_id = UUID(str(project.global_id))
        kind_value = _enum_or_string(kind)
        severity_value = _enum_or_string(severity)
        if kind_value not in {
            "risk",
            "issue",
            "action",
            "decision_request",
        }:
            raise _field_problem("kind", _("Select a supported Work Item kind."))
        if severity_value not in {"low", "medium", "high", "critical"}:
            raise _field_problem("severity", _("Select a supported severity."))
        title_value = _text_value(title, "title", 280)
        detail_value = (
            None if detail is None else _text_value(detail, "detail", 4000, empty=True)
        )
        owner = _email_value(owner_user_id, "ownerUserId")
        if frappe.db.get_value("User", owner, "enabled") != 1:
            raise _field_problem(
                "ownerUserId",
                _("Select an enabled Work Item owner."),
            )
        due = _datetime_value(due_at)
        if type(blocking) is not bool:
            raise _field_problem("blocking", _("Select true or false."))
        stage_id = _optional_uuid_value(
            _record_value(context, "stage_id", "stageId", default=None),
            "context.stageId",
        )
        wbs_item_id = _optional_uuid_value(
            _record_value(
                context,
                "wbs_item_id",
                "wbsItemId",
                default=None,
            ),
            "context.wbsItemId",
        )
        known_stage_ids: frozenset[UUID] | None = None
        if stage_id is not None:
            self._require_related_project_document(
                "NPI Gate Shell",
                stage_id,
                project_id,
                "context.stageId",
                project_field="project_global_id",
                tenant_id=str(project.tenant_id),
                tenant_field=None,
            )
            known_stage_ids = frozenset((stage_id,))
        known_wbs_item_ids: frozenset[UUID] | None = None
        if wbs_item_id is not None:
            self._require_related_project_document(
                "NPI WBS Item",
                wbs_item_id,
                project_id,
                "context.wbsItemId",
                tenant_id=str(project.tenant_id),
            )
            known_wbs_item_ids = frozenset((wbs_item_id,))
        related_ids = tuple(UUID(str(value)) for value in related_work_item_ids)
        if len(related_ids) != len(set(related_ids)) or len(related_ids) > 100:
            raise _field_problem(
                "relatedWorkItemIds",
                _("Related Work Item IDs must be unique."),
            )
        related_documents: list[Any] = []
        for index, related_id in enumerate(related_ids):
            related_documents.append(
                self._require_related_project_document(
                    "NPI Domain Work Item",
                    related_id,
                    project_id,
                    f"relatedWorkItemIds[{index}]",
                    tenant_id=str(project.tenant_id),
                )
            )
        return build_domain_work_item(
            global_id=item_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            policy=policy["snapshot"],
            kind=DomainWorkItemKind(kind_value),
            title=title_value,
            detail=detail_value,
            stage_global_id=stage_id,
            wbs_item_global_id=wbs_item_id,
            owner_user_id=owner,
            due_at=due,
            severity=Severity(severity_value),
            blocking=blocking,
            related_work_item_ids=related_ids,
            related_items=tuple(
                _domain_work_item_from_document(document)
                for document in related_documents
            ),
            known_stage_ids=known_stage_ids,
            known_wbs_item_ids=known_wbs_item_ids,
        )

    def _upsert_team_documents(
        self,
        project,
        prepared: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> None:
        common = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
        }
        for item in prepared["members"]:
            self._upsert_managed_document(
                "NPI Project Member",
                item["global_id"],
                {
                    **common,
                    "user_id": item["user_id"],
                    "effective_from": item["effective_from"],
                    "effective_to": item["effective_to"],
                },
            )
        for item in prepared["roles"]:
            self._upsert_managed_document(
                "NPI Project Role Assignment",
                item["global_id"],
                {
                    **common,
                    "member_global_id": str(item["member_id"]),
                    "role_key": item["role_key"],
                    "effective_from": item["effective_from"],
                    "effective_to": item["effective_to"],
                },
            )
        for item in prepared["substitutions"]:
            self._upsert_managed_document(
                "NPI Project Substitution",
                item["global_id"],
                {
                    **common,
                    "role_assignment_global_id": str(
                        item["role_assignment_id"]
                    ),
                    "substitute_member_global_id": str(
                        item["substitute_member_id"]
                    ),
                    "effective_from": item["effective_from"],
                    "effective_to": item["effective_to"],
                },
            )
        for item in prepared["raci"]:
            self._upsert_managed_document(
                "NPI Project RACI Assignment",
                item["global_id"],
                {
                    **common,
                    "context_type": item["context_type"],
                    "context_global_id": str(item["context_id"]),
                    "responsibility_key": item["responsibility_key"],
                    "role_assignment_global_id": str(
                        item["role_assignment_id"]
                    ),
                    "responsibility": item["raci"],
                },
            )

    def _upsert_plan_documents(
        self,
        project,
        prepared: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> None:
        common = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
        }
        for item in prepared["items"]:
            policy_ref = item["policy_ref"]
            self._upsert_managed_document(
                "NPI WBS Item",
                item["global_id"],
                {
                    **common,
                    "work_policy_global_id": policy_ref["globalId"],
                    "work_policy_version": policy_ref["version"],
                    "work_policy_snapshot_hash": policy_ref["snapshotHash"],
                    "wbs_code": item["code"],
                    "title": item["title"],
                    "parent_global_id": (
                        str(item["parent_id"])
                        if item["parent_id"] is not None
                        else None
                    ),
                    "owner_role_assignment_global_id": (
                        str(item["owner_role_assignment_id"])
                        if item["owner_role_assignment_id"] is not None
                        else None
                    ),
                    "planned_start": item["planned_start"],
                    "planned_end": item["planned_finish"],
                    "actual_start": item["actual_start"],
                    "actual_end": item["actual_finish"],
                    "milestone": item["milestone"],
                    "status_key": item["status_key"],
                    "status_label_source": item["status_label_source"],
                    "progress_percent": item["progress_percent"],
                    "critical_task": item["critical"],
                    "plan_revision": item["plan_revision"],
                },
            )
        for item in prepared["dependencies"]:
            self._upsert_managed_document(
                "NPI WBS Dependency",
                item["global_id"],
                {
                    **common,
                    "predecessor_global_id": str(item["predecessor_id"]),
                    "successor_global_id": str(item["successor_id"]),
                    "plan_revision": item["plan_revision"],
                    "active": 1,
                },
            )

    def _upsert_managed_document(
        self,
        doctype: str,
        global_id: UUID,
        values: Mapping[str, object],
    ):
        existing = _optional_doc(doctype, str(global_id))
        if existing is None:
            return frappe.get_doc(
                {
                    "doctype": doctype,
                    "global_id": str(global_id),
                    "optimistic_version": 1,
                    **dict(values),
                }
            ).insert()
        changed = False
        for fieldname, value in values.items():
            if _comparable(existing.get(fieldname)) != _comparable(value):
                existing.set(fieldname, value)
                changed = True
        if changed:
            existing.save()
        return existing

    def _advance_project(
        self,
        project,
        policy_ref: Mapping[str, object],
    ) -> None:
        project.work_policy_global_id = str(policy_ref["globalId"])
        project.work_policy_version = int(policy_ref["version"])
        project.work_policy_snapshot_hash = str(policy_ref["snapshotHash"])
        project.optimistic_version = int(project.optimistic_version) + 1
        project.save()

    def _idempotency_replay(
        self,
        actor_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        record = frappe.db.get_value(
            "NPI Project Work Idempotency",
            {"actor_key_hash": actor_key_hash},
            ["payload_hash", "response_json", "response_sealed"],
            as_dict=True,
            for_update=True,
        )
        if not record:
            return None
        if str(record.payload_hash) != payload_hash:
            raise IdempotencyConflict()
        if int(record.response_sealed or 0) != 1:
            raise RuntimeError("Persisted Project work idempotency is unsealed.")
        response = _json_object(record.response_json)
        return response

    def _insert_idempotency(
        self,
        actor_key_hash: str,
        payload_hash: str,
        project,
        operation: str,
    ):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Project Work Idempotency",
                    "record_id": str(uuid4()),
                    "actor": self.actor,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "operation": operation,
                    "actor_key_hash": actor_key_hash,
                    "payload_hash": payload_hash,
                    "response_json": {},
                    "response_sealed": 0,
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            frappe.db.rollback()
            replay = self._idempotency_replay(actor_key_hash, payload_hash)
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_idempotency(document, response: Mapping[str, object]) -> None:
        document.response_json = dict(response)
        document.response_sealed = 1
        document.save()

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        result: str,
        summary: Mapping[str, object],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result=result,
            input_summary=summary,
        )
        frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(event.event_id),
                "global_id": str(event.global_id),
                "object_version": event.object_version,
                "actor": event.actor,
                "trace_id": event.trace_id,
                "operation": event.operation,
                "result": event.result,
                "input_summary": dict(event.input_summary),
            }
        ).insert()

    @staticmethod
    def _require_project_version(project, expected: int) -> None:
        if int(project.optimistic_version) != expected:
            raise VersionConflict()

    @staticmethod
    def _require_same_project_identity(
        doctype: str,
        global_id: UUID,
        project_id: UUID,
        path: str,
        *,
        tenant_id: str,
    ) -> None:
        document = _optional_doc(doctype, str(global_id))
        if (
            document is not None
            and (
                str(document.get("project_global_id")) != str(project_id)
                or str(document.get("tenant_id")) != tenant_id
            )
        ):
            raise _field_problem(
                path,
                _("Select an identifier that belongs to this Project."),
            )

    @staticmethod
    def _require_related_project_document(
        doctype: str,
        global_id: UUID,
        project_id: UUID,
        path: str,
        *,
        project_field: str = "project_global_id",
        tenant_id: str,
        tenant_field: str | None = "tenant_id",
    ):
        document = _optional_doc(doctype, str(global_id))
        if (
            document is None
            or str(document.get(project_field)) != str(project_id)
            or (
                tenant_field is not None
                and str(document.get(tenant_field)) != tenant_id
            )
        ):
            raise _field_problem(
                path,
                _("Select an object from this Project."),
            )
        return document

    def _validate_raci_context(
        self,
        project_id: UUID,
        tenant_id: str,
        context_type: str,
        context_id: UUID,
        path: str,
    ) -> None:
        if context_type == "project":
            if context_id != project_id:
                raise _field_problem(path, _("Select this Project."))
            return
        doctype = (
            "NPI WBS Item"
            if context_type == "wbs_item"
            else "NPI Domain Work Item"
        )
        self._require_related_project_document(
            doctype,
            context_id,
            project_id,
            path,
            tenant_id=tenant_id,
        )

    def _work_context_for(self, project) -> dict[str, Any]:
        project_id = UUID(str(project.global_id))
        tenant_id = str(project.tenant_id)
        base_filters = {
            "tenant_id": tenant_id,
            "project_global_id": str(project_id),
        }
        members = _project_documents(
            "NPI Project Member",
            base_filters,
            order_by="effective_from asc, user_id asc, global_id asc",
        )
        roles = _project_documents(
            "NPI Project Role Assignment",
            base_filters,
            order_by="role_key asc, global_id asc",
        )
        substitutions = _project_documents(
            "NPI Project Substitution",
            base_filters,
            order_by="effective_from asc, global_id asc",
        )
        raci = _project_documents(
            "NPI Project RACI Assignment",
            base_filters,
            order_by="context_type asc, responsibility_key asc, global_id asc",
        )
        wbs_items = _project_documents(
            "NPI WBS Item",
            base_filters,
            order_by="wbs_code asc, global_id asc",
        )
        dependencies = _project_documents(
            "NPI WBS Dependency",
            {**base_filters, "active": 1},
            order_by="predecessor_global_id asc, successor_global_id asc",
        )
        baseline_documents = _project_documents(
            "NPI WBS Plan Baseline",
            base_filters,
            order_by="captured_at asc, global_id asc",
        )
        policy_ref = _project_policy_ref(project)
        active_baseline = None
        if project.active_plan_baseline_global_id:
            active_baseline = _optional_doc(
                "NPI WBS Plan Baseline",
                str(project.active_plan_baseline_global_id),
            )
            if (
                active_baseline is None
                or str(active_baseline.project_global_id) != str(project_id)
                or str(active_baseline.tenant_id) != tenant_id
            ):
                raise ValueError("Persisted active Plan Baseline integrity failed.")
        baseline_comparison = None
        if active_baseline is not None:
            if policy_ref is None:
                raise ValueError(
                    "Persisted active Plan Baseline requires a Project Work Policy."
                )
            policy = self._load_policy(policy_ref)
            current_plan = _domain_wbs_plan_from_documents(
                project,
                policy["snapshot"],
                item_documents=wbs_items,
                dependency_documents=dependencies,
                role_documents=roles,
                project_version=int(project.optimistic_version),
            )
            baseline_comparison = _baseline_comparison(
                active_baseline,
                current_plan,
            )
        system_manager = self._is_internal_system_manager()
        project_mutable = str(project.get("lifecycle_state") or "") not in {
            "cancelled",
            "completed",
        }
        return {
            "projectId": str(project_id),
            "projectVersion": int(project.optimistic_version),
            "initialized": policy_ref is not None,
            "workPolicyRef": policy_ref,
            "members": [_member_response(document) for document in members],
            "roleAssignments": [
                _role_assignment_response(document) for document in roles
            ],
            "substitutions": [
                _substitution_response(document) for document in substitutions
            ],
            "raciAssignments": [
                _raci_assignment_response(document) for document in raci
            ],
            "wbsItems": [_wbs_item_response(document) for document in wbs_items],
            "dependencies": [
                _dependency_response(document) for document in dependencies
            ],
            "baselines": [
                _baseline_response(document) for document in baseline_documents
            ],
            "baselineComparison": baseline_comparison,
            "permissions": {
                "canView": True,
                "canContribute": system_manager and project_mutable,
                "canAdminister": system_manager and project_mutable,
            },
        }

    def _domain_work_item_response(
        self,
        document,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            "projectId": str(UUID(str(document.project_global_id)))
        }
        if document.stage_global_id:
            context["stageId"] = str(UUID(str(document.stage_global_id)))
        if document.wbs_item_global_id:
            context["wbsItemId"] = str(UUID(str(document.wbs_item_global_id)))
        response: dict[str, Any] = {
            "globalId": str(UUID(str(document.global_id))),
            "projectId": str(UUID(str(document.project_global_id))),
            "kind": str(document.kind),
            "title": str(document.title),
            "context": context,
            "ownerUserId": str(document.owner_user_id),
            "dueAt": _datetime_iso(document.due_at),
            "severity": str(document.severity),
            "blocking": bool(document.blocking),
            "relatedWorkItemIds": [
                str(UUID(str(value))) for value in _json_array(document.relations)
            ],
            "workPolicyRef": {
                "globalId": str(UUID(str(document.work_policy_global_id))),
                "version": int(document.work_policy_version),
                "snapshotHash": str(document.work_policy_snapshot_hash),
            },
            "stateKey": str(document.state_key),
            "stateLabelSource": str(document.state_label_source),
            "overdue": _is_overdue(document, now or datetime.now(UTC)),
            "version": int(document.optimistic_version),
            "createdAt": _datetime_iso(document.creation),
            "lastChangedAt": _datetime_iso(document.modified),
            "source": {
                "sourceSystem": "NPI_ONE",
                "editableIn": "NPI_ONE",
                "syncState": "local",
            },
        }
        if document.detail:
            response["detail"] = str(document.detail)
        return response

    def _authorized_project(
        self,
        project_id: UUID,
        required: ProjectAccess,
    ):
        document = _optional_doc("NPI Engineering Project", str(project_id))
        if document is None:
            return None
        return self._authorize_project_document(document, project_id, required)

    def _locked_authorized_project(
        self,
        project_id: UUID,
        required: ProjectAccess,
    ):
        try:
            document = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return self._authorize_project_document(
            document,
            project_id,
            required,
        )

    def _authorize_project_document(
        self,
        document,
        project_id: UUID,
        required: ProjectAccess,
    ):
        access = None
        if self._is_internal_system_manager():
            access = ProjectAccess.ADMINISTER
        elif str(document.owner_user_id).casefold() == self.actor.casefold():
            access = ProjectAccess.VIEW
        scoped_principal = self.principal
        if access is not None:
            from dataclasses import replace

            scoped_principal = replace(
                self.principal,
                project_access={str(project_id): access},
            )
        try:
            authorize_project(
                scoped_principal,
                str(project_id),
                required,
                project_tenant_id=str(document.tenant_id),
            )
        except PermissionDenied:
            return None
        return document

    def _is_internal_system_manager(self) -> bool:
        return (
            not self.principal.is_external
            and "System Manager" in self.principal.roles
        )


def _project_policy_ref(project) -> dict[str, Any] | None:
    values = (
        project.work_policy_global_id,
        project.work_policy_version,
        project.work_policy_snapshot_hash,
    )
    if not any(values):
        return None
    if not all(values):
        raise ValueError("Persisted Project Work Policy identity is incomplete.")
    return {
        "globalId": str(UUID(str(project.work_policy_global_id))),
        "version": int(project.work_policy_version),
        "snapshotHash": str(project.work_policy_snapshot_hash),
    }


def _domain_wbs_plan_from_documents(
    project,
    policy: ProjectWorkPolicySnapshot,
    *,
    item_documents: Sequence[Any],
    dependency_documents: Sequence[Any],
    role_documents: Sequence[Any],
    project_version: int,
) -> WbsPlan:
    project_id = UUID(str(project.global_id))
    tenant_id = str(project.tenant_id)
    return WbsPlan(
        tenant_id=tenant_id,
        project_global_id=project_id,
        project_version=project_version,
        policy=policy,
        items=tuple(
            WbsItem(
                global_id=UUID(str(document.global_id)),
                tenant_id=tenant_id,
                project_global_id=project_id,
                work_policy_global_id=UUID(
                    str(document.work_policy_global_id)
                ),
                work_policy_version=int(document.work_policy_version),
                work_policy_snapshot_hash=str(
                    document.work_policy_snapshot_hash
                ),
                code=str(document.wbs_code),
                title=str(document.title),
                planned_start=date.fromisoformat(
                    _date_iso(document.planned_start)
                ),
                planned_finish=date.fromisoformat(
                    _date_iso(document.planned_end)
                ),
                milestone=bool(document.milestone),
                status_key=str(document.status_key),
                progress_percent=int(document.progress_percent),
                critical=bool(document.critical_task),
                plan_revision=int(document.plan_revision),
                parent_global_id=(
                    UUID(str(document.parent_global_id))
                    if document.parent_global_id
                    else None
                ),
                owner_role_assignment_global_id=(
                    UUID(str(document.owner_role_assignment_global_id))
                    if document.owner_role_assignment_global_id
                    else None
                ),
                actual_start=(
                    date.fromisoformat(_date_iso(document.actual_start))
                    if document.actual_start
                    else None
                ),
                actual_finish=(
                    date.fromisoformat(_date_iso(document.actual_end))
                    if document.actual_end
                    else None
                ),
                version=int(document.optimistic_version),
            )
            for document in item_documents
        ),
        dependencies=tuple(
            WbsDependency(
                global_id=UUID(str(document.global_id)),
                tenant_id=tenant_id,
                project_global_id=project_id,
                predecessor_global_id=UUID(
                    str(document.predecessor_global_id)
                ),
                successor_global_id=UUID(
                    str(document.successor_global_id)
                ),
                plan_revision=int(document.plan_revision),
                active=bool(document.active),
                version=int(document.optimistic_version),
            )
            for document in dependency_documents
        ),
        role_assignments=tuple(
            ProjectRoleAssignment(
                global_id=UUID(str(document.global_id)),
                tenant_id=tenant_id,
                project_global_id=project_id,
                member_global_id=UUID(str(document.member_global_id)),
                role_key=str(document.role_key),
                effective_from=date.fromisoformat(
                    _date_iso(document.effective_from)
                ),
                effective_to=(
                    date.fromisoformat(_date_iso(document.effective_to))
                    if document.effective_to
                    else None
                ),
                version=int(document.optimistic_version),
            )
            for document in role_documents
        ),
    )


def _domain_baseline_from_document(document) -> WbsPlanBaseline:
    snapshot = _json_object(document.snapshot)
    if set(snapshot) != {"items"} or not isinstance(snapshot["items"], list):
        raise ValueError("Persisted Plan Baseline snapshot is invalid.")
    entries: list[BaselineEntry] = []
    for value in snapshot["items"]:
        if (
            not isinstance(value, dict)
            or set(value)
            != {"wbsItemId", "plannedStart", "plannedFinish", "critical"}
            or type(value["critical"]) is not bool
        ):
            raise ValueError("Persisted Plan Baseline item is invalid.")
        entries.append(
            BaselineEntry(
                wbs_item_global_id=UUID(str(value["wbsItemId"])),
                planned_start=date.fromisoformat(str(value["plannedStart"])),
                planned_finish=date.fromisoformat(
                    str(value["plannedFinish"])
                ),
                critical=value["critical"],
            )
        )
    return WbsPlanBaseline(
        global_id=UUID(str(document.global_id)),
        tenant_id=str(document.tenant_id),
        project_global_id=UUID(str(document.project_global_id)),
        plan_revision=int(document.plan_revision),
        project_version=int(document.project_version),
        label=str(document.label),
        work_policy_global_id=UUID(str(document.work_policy_global_id)),
        work_policy_version=int(document.work_policy_version),
        work_policy_snapshot_hash=str(
            document.work_policy_snapshot_hash
        ),
        snapshot_hash=str(document.snapshot_hash),
        entries=tuple(entries),
        captured_at=_datetime_value(document.captured_at),
        captured_by=str(document.captured_by),
        version=int(document.optimistic_version),
    )


def _domain_work_item_from_document(document) -> DomainWorkItem:
    return DomainWorkItem(
        global_id=UUID(str(document.global_id)),
        tenant_id=str(document.tenant_id),
        project_global_id=UUID(str(document.project_global_id)),
        kind=DomainWorkItemKind(str(document.kind)),
        title=str(document.title),
        detail=str(document.detail) if document.detail else None,
        stage_global_id=(
            UUID(str(document.stage_global_id))
            if document.stage_global_id
            else None
        ),
        wbs_item_global_id=(
            UUID(str(document.wbs_item_global_id))
            if document.wbs_item_global_id
            else None
        ),
        owner_user_id=str(document.owner_user_id),
        due_at=_datetime_value(document.due_at),
        severity=Severity(str(document.severity)),
        blocking=bool(document.blocking),
        state_key=str(document.state_key),
        state_label_source=str(document.state_label_source),
        state_terminal=bool(document.state_terminal),
        work_policy_global_id=UUID(str(document.work_policy_global_id)),
        work_policy_version=int(document.work_policy_version),
        work_policy_snapshot_hash=str(
            document.work_policy_snapshot_hash
        ),
        related_work_item_ids=tuple(
            UUID(str(value)) for value in _json_array(document.relations)
        ),
        evidence_references=tuple(
            UUID(str(value))
            for value in _json_array(document.evidence_references)
        ),
        version=int(document.optimistic_version),
    )


def _member_response(document) -> dict[str, Any]:
    response: dict[str, Any] = {
        "globalId": str(UUID(str(document.global_id))),
        "projectId": str(UUID(str(document.project_global_id))),
        "userId": str(document.user_id),
        "effectiveFrom": _date_iso(document.effective_from),
        "version": int(document.optimistic_version),
    }
    if document.effective_to:
        response["effectiveTo"] = _date_iso(document.effective_to)
    return response


def _role_assignment_response(document) -> dict[str, Any]:
    response: dict[str, Any] = {
        "globalId": str(UUID(str(document.global_id))),
        "projectId": str(UUID(str(document.project_global_id))),
        "memberId": str(UUID(str(document.member_global_id))),
        "roleKey": str(document.role_key),
        "effectiveFrom": _date_iso(document.effective_from),
        "version": int(document.optimistic_version),
    }
    if document.effective_to:
        response["effectiveTo"] = _date_iso(document.effective_to)
    return response


def _substitution_response(document) -> dict[str, Any]:
    return {
        "globalId": str(UUID(str(document.global_id))),
        "projectId": str(UUID(str(document.project_global_id))),
        "roleAssignmentId": str(UUID(str(document.role_assignment_global_id))),
        "substituteMemberId": str(
            UUID(str(document.substitute_member_global_id))
        ),
        "effectiveFrom": _date_iso(document.effective_from),
        "effectiveTo": _date_iso(document.effective_to),
        "version": int(document.optimistic_version),
    }


def _raci_assignment_response(document) -> dict[str, Any]:
    return {
        "globalId": str(UUID(str(document.global_id))),
        "projectId": str(UUID(str(document.project_global_id))),
        "contextType": str(document.context_type),
        "contextId": str(UUID(str(document.context_global_id))),
        "responsibilityKey": str(document.responsibility_key),
        "roleAssignmentId": str(
            UUID(str(document.role_assignment_global_id))
        ),
        "raci": str(document.responsibility),
        "version": int(document.optimistic_version),
    }


def _wbs_item_response(document) -> dict[str, Any]:
    response: dict[str, Any] = {
        "globalId": str(UUID(str(document.global_id))),
        "projectId": str(UUID(str(document.project_global_id))),
        "code": str(document.wbs_code),
        "title": str(document.title),
        "plannedStart": _date_iso(document.planned_start),
        "plannedFinish": _date_iso(document.planned_end),
        "milestone": bool(document.milestone),
        "statusKey": str(document.status_key),
        "statusLabelSource": str(document.status_label_source),
        "progressPercent": int(document.progress_percent),
        "critical": bool(document.critical_task),
        "version": int(document.optimistic_version),
    }
    optional_uuid_fields = (
        ("parentId", document.parent_global_id),
        ("ownerRoleAssignmentId", document.owner_role_assignment_global_id),
    )
    for response_key, value in optional_uuid_fields:
        if value:
            response[response_key] = str(UUID(str(value)))
    optional_date_fields = (
        ("actualStart", document.actual_start),
        ("actualFinish", document.actual_end),
    )
    for response_key, value in optional_date_fields:
        if value:
            response[response_key] = _date_iso(value)
    return response


def _dependency_response(document) -> dict[str, Any]:
    return {
        "globalId": str(UUID(str(document.global_id))),
        "projectId": str(UUID(str(document.project_global_id))),
        "predecessorItemId": str(UUID(str(document.predecessor_global_id))),
        "successorItemId": str(UUID(str(document.successor_global_id))),
        "version": int(document.optimistic_version),
    }


def _baseline_response(document) -> dict[str, Any]:
    return {
        "globalId": str(UUID(str(document.global_id))),
        "projectId": str(UUID(str(document.project_global_id))),
        "projectVersion": int(document.project_version),
        "workPolicyRef": {
            "globalId": str(UUID(str(document.work_policy_global_id))),
            "version": int(document.work_policy_version),
            "snapshotHash": str(document.work_policy_snapshot_hash),
        },
        "label": str(document.label),
        "snapshotHash": str(document.snapshot_hash),
        "capturedAt": _datetime_iso(document.captured_at),
        "capturedBy": str(document.captured_by),
        "version": int(document.optimistic_version),
    }


def _baseline_comparison(
    baseline,
    current_plan: WbsPlan,
) -> dict[str, Any]:
    comparison = compare_domain_wbs_baseline(
        _domain_baseline_from_document(baseline),
        current_plan,
    )
    return {
        "baselineId": str(comparison.baseline_global_id),
        "baselineProjectVersion": comparison.baseline_project_version,
        "currentProjectVersion": comparison.current_project_version,
        "items": [
            {
                "wbsItemId": str(item.wbs_item_global_id),
                "baselinePlannedStart": (
                    item.baseline_planned_start.isoformat()
                ),
                "baselinePlannedFinish": (
                    item.baseline_planned_finish.isoformat()
                ),
                "currentPlannedStart": (
                    item.current_planned_start.isoformat()
                ),
                "currentPlannedFinish": (
                    item.current_planned_finish.isoformat()
                ),
                "startVarianceDays": item.start_variance_days,
                "finishVarianceDays": item.finish_variance_days,
                "critical": item.critical,
            }
            for item in comparison.items
        ],
    }


def _project_documents(
    doctype: str,
    filters: Mapping[str, object],
    *,
    order_by: str,
) -> tuple[Any, ...]:
    names = frappe.get_all(
        doctype,
        filters=dict(filters),
        pluck="name",
        order_by=order_by,
        limit_page_length=10001,
    )
    if len(names) > 10000:
        raise ValueError("Persisted Project work collection exceeds its safe bound.")
    return tuple(frappe.get_doc(doctype, name) for name in names)


def _query_domain_work_item_page(
    filters: Sequence[Sequence[object]],
    *,
    cursor: tuple[datetime, str] | None,
    limit: int,
) -> tuple[Any, ...]:
    def query(extra_filters: Sequence[Sequence[object]]) -> tuple[Any, ...]:
        return tuple(
            frappe.get_all(
                "NPI Domain Work Item",
                filters=[
                    list(filter_value)
                    for filter_value in (*filters, *extra_filters)
                ],
                fields=list(_DOMAIN_WORK_ITEM_PAGE_FIELDS),
                order_by="due_at asc, global_id asc",
                limit_page_length=limit,
            )
        )

    if cursor is None:
        return query(())

    cursor_due_at, cursor_global_id = cursor
    database_due_at = _database_datetime(cursor_due_at)
    same_due_at = query(
        (
            ("due_at", "=", database_due_at),
            ("global_id", ">", cursor_global_id),
        )
    )
    later_due_at = query((("due_at", ">", database_due_at),))
    return _merge_domain_work_item_pages(
        same_due_at,
        later_due_at,
        limit=limit,
    )


def _merge_domain_work_item_pages(
    *pages: Sequence[Any],
    limit: int,
) -> tuple[Any, ...]:
    return tuple(
        sorted(
            (document for page in pages for document in page),
            key=_work_item_sort_key,
        )[:limit]
    )


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _is_overdue(document, now: datetime) -> bool:
    return (
        not bool(document.state_terminal)
        and _datetime_value(document.due_at) < now
    )


def _work_item_sort_key(document) -> tuple[datetime, str]:
    return (
        _datetime_value(document.due_at),
        str(UUID(str(document.global_id))),
    )


def _domain_work_item_query_fingerprint(
    *,
    project_id: UUID,
    stage_id: UUID | None,
    owner_user_id: str | None,
    overdue: bool | None,
    kind: object | None,
) -> str:
    query_identity = {
        "kind": None if kind is None else _enum_or_string(kind),
        "overdue": overdue,
        "ownerUserId": owner_user_id,
        "projectId": str(project_id),
        "stageId": None if stage_id is None else str(stage_id),
    }
    return hashlib.sha256(
        canonical_json(query_identity).encode("utf-8")
    ).hexdigest()


def _encode_cursor(
    value: tuple[object, str],
    *,
    as_of: object,
    query_fingerprint: str,
    signing_key: bytes | None = None,
) -> str:
    if _HASH_PATTERN.fullmatch(query_fingerprint) is None:
        raise ValueError("A cursor query fingerprint must be a SHA-256 hash.")
    payload = canonical_json(
        {
            "asOf": _datetime_iso(as_of),
            "dueAt": _datetime_iso(value[0]),
            "globalId": str(UUID(str(value[1]))),
            "queryFingerprint": query_fingerprint,
            "version": _DOMAIN_WORK_ITEM_CURSOR_VERSION,
        }
    ).encode("utf-8")
    resolved_signing_key = (
        signing_key
        if signing_key is not None
        else _domain_work_item_cursor_signing_key()
    )
    signature = hmac.new(
        resolved_signing_key,
        payload,
        hashlib.sha256,
    ).digest()
    cursor = f"{_base64url_encode(payload)}.{_base64url_encode(signature)}"
    if len(cursor) > 500:
        raise ValueError("The generated cursor exceeds the API limit.")
    return cursor


def _decode_cursor(
    value: str,
    *,
    expected_query_fingerprint: str,
    signing_key: bytes | None = None,
) -> _DomainWorkItemCursor:
    resolved_signing_key = (
        signing_key
        if signing_key is not None
        else _domain_work_item_cursor_signing_key()
    )
    try:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 500
            or _HASH_PATTERN.fullmatch(expected_query_fingerprint) is None
        ):
            raise ValueError
        encoded_payload, encoded_signature = value.split(".")
        decoded = _base64url_decode(encoded_payload)
        signature = _base64url_decode(encoded_signature)
        if len(signature) != hashlib.sha256().digest_size or not hmac.compare_digest(
            signature,
            hmac.new(
                resolved_signing_key,
                decoded,
                hashlib.sha256,
            ).digest(),
        ):
            raise ValueError
        payload = json.loads(decoded.decode("utf-8"))
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "asOf",
                "dueAt",
                "globalId",
                "queryFingerprint",
                "version",
            }
            or type(payload["version"]) is not int
            or payload["version"] != _DOMAIN_WORK_ITEM_CURSOR_VERSION
            or not isinstance(payload["queryFingerprint"], str)
            or _HASH_PATTERN.fullmatch(payload["queryFingerprint"]) is None
            or payload["queryFingerprint"] != expected_query_fingerprint
        ):
            raise ValueError
        as_of = _datetime_value(payload["asOf"])
        due_at = _datetime_value(payload["dueAt"])
        global_id = str(UUID(str(payload["globalId"])))
        if (
            _base64url_encode(
                canonical_json(
                    {
                        "asOf": _datetime_iso(as_of),
                        "dueAt": _datetime_iso(due_at),
                        "globalId": global_id,
                        "queryFingerprint": payload["queryFingerprint"],
                        "version": payload["version"],
                    }
                ).encode("utf-8")
            )
            != encoded_payload
        ):
            raise ValueError
        return _DomainWorkItemCursor(
            due_at=due_at,
            global_id=global_id,
            as_of=as_of,
            query_fingerprint=payload["queryFingerprint"],
        )
    except (
        binascii.Error,
        OverflowError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as error:
        raise RequestValidationFailed(
            [{"path": "cursor", "message": _("Enter a valid cursor.")}]
        ) from error


def _domain_work_item_cursor_signing_key() -> bytes:
    try:
        local = getattr(frappe, "local", None)
        configuration = getattr(local, "conf", None)
        if configuration is None:
            configuration = getattr(frappe, "conf", None)
        if configuration is None:
            raise KeyError("encryption_key")
        persisted_key = configuration.get("encryption_key")
        if not isinstance(persisted_key, str):
            raise ValueError
        encoded_key = persisted_key.encode("ascii")
        decoded_key = base64.b64decode(
            encoded_key,
            altchars=b"-_",
            validate=True,
        )
        if (
            len(decoded_key) != 32
            or base64.urlsafe_b64encode(decoded_key) != encoded_key
        ):
            raise ValueError
    except (ImportError, KeyError, TypeError, UnicodeError, ValueError) as error:
        raise CursorSigningUnavailable() from error
    except Exception as error:
        raise CursorSigningUnavailable() from error
    return hmac.new(
        decoded_key,
        _DOMAIN_WORK_ITEM_CURSOR_KEY_CONTEXT,
        hashlib.sha256,
    ).digest()


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    if not value or "=" in value:
        raise ValueError
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(
        (value + padding).encode("ascii"),
        altchars=b"-_",
        validate=True,
    )
    if _base64url_encode(decoded) != value:
        raise ValueError
    return decoded


def _json_array(value: object) -> list[object]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Persisted JSON value must be an array.")
    return parsed


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("Persisted JSON value must be an object.")
    return parsed


def _domain_lifecycle(value: object) -> LifecycleDefinition:
    if (
        not isinstance(value, dict)
        or set(value) != {"initialStateKey", "states"}
        or not isinstance(value["states"], list)
        or any(
            not isinstance(state, dict)
            or set(state) != {"key", "labelSource", "terminal"}
            for state in value["states"]
        )
    ):
        raise ValueError("Persisted lifecycle definition is invalid.")
    return LifecycleDefinition(
        initial_state_key=str(value["initialStateKey"]),
        states=tuple(
            LifecycleState(
                key=str(state["key"]),
                label_source=str(state["labelSource"]),
                terminal=state["terminal"],
            )
            for state in value["states"]
        ),
    )


def _date_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _datetime_iso(value: object) -> str:
    return _datetime_value(value).isoformat().replace("+00:00", "Z")


def _database_datetime(value: object) -> datetime:
    return _datetime_value(value).replace(tzinfo=None)


def _enum_or_string(value: object) -> str:
    enum_value = getattr(value, "value", value)
    return str(enum_value)


def _canonical_value(value: object) -> object:
    if is_dataclass(value):
        return _canonical_value(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _datetime_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return value


def _payload_hash(value: object) -> str:
    payload = canonical_json(_canonical_value(value))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_value(
    value: object,
    *names: str,
    default: object = _MISSING,
) -> object:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    if default is not _MISSING:
        return default
    raise _field_problem(names[-1], _("This field is required."))


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid_value(value: object, path: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid global ID."))
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise _field_problem(path, _("Enter a valid global ID."))
    if str(parsed) != value.casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _optional_uuid_value(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid_value(value, path)


def _positive_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _percentage_value(value: object, path: str) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise _field_problem(
            path,
            _("Enter a progress percentage from 0 to 100."),
        )
    return value


def _bool_value(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _field_problem(path, _("Select true or false."))
    return value


def _hash_value(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid snapshot hash."))
    return value


def _key_value(value: object, path: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid controlled key."))
    return value


def _business_code_value(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or _BUSINESS_CODE_PATTERN.fullmatch(value) is None
    ):
        raise _field_problem(path, _("Enter a valid WBS code."))
    return value


def _text_value(
    value: object,
    path: str,
    maximum_length: int,
    *,
    empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid value."))
    normalized = value.strip()
    if (not empty and not normalized) or len(normalized) > maximum_length:
        raise _field_problem(path, _("Enter a valid value."))
    return normalized


def _email_value(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 254
        or _EMAIL_PATTERN.fullmatch(value) is None
    ):
        raise _field_problem(path, _("Enter a valid email address."))
    return value.casefold()


def _date_value(value: object, path: str) -> date:
    if type(value) is date:
        return value
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid date."))
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise _field_problem(path, _("Enter a valid date."))
    if parsed.isoformat() != value:
        raise _field_problem(path, _("Enter a valid date."))
    return parsed


def _optional_date_value(value: object, path: str) -> date | None:
    return None if value is None else _date_value(value, path)


def _validate_date_range(
    start: date | None,
    finish: date | None,
    path: str,
) -> None:
    if start is not None and finish is not None and finish < start:
        raise _field_problem(
            path,
            _("The end date cannot be earlier than the start date."),
        )


def _interval_contains(
    outer: Mapping[str, Any],
    inner: Mapping[str, Any],
) -> bool:
    outer_start = outer["effective_from"]
    outer_finish = outer.get("effective_to")
    inner_start = inner["effective_from"]
    inner_finish = inner.get("effective_to")
    if inner_start < outer_start:
        return False
    if outer_finish is None:
        return True
    return inner_finish is not None and inner_finish <= outer_finish


def _intervals_overlap(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    left_finish = left.get("effective_to")
    right_finish = right.get("effective_to")
    return (
        left_finish is None or right["effective_from"] <= left_finish
    ) and (
        right_finish is None or left["effective_from"] <= right_finish
    )


def _reject_overlapping_roles(records: Sequence[Mapping[str, Any]]) -> None:
    values = tuple(records)
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            if (
                left["member_id"] == right["member_id"]
                and left["role_key"] == right["role_key"]
                and _intervals_overlap(left, right)
            ):
                raise _field_problem(
                    "roleAssignments",
                    _("Duplicate role-assignment periods cannot overlap."),
                )


def _reject_duplicate_raci(records: Sequence[Mapping[str, Any]]) -> None:
    identities: set[tuple[object, ...]] = set()
    for record in records:
        identity = (
            record["context_type"],
            record["context_id"],
            record["responsibility_key"],
            record["role_assignment_id"],
            record["raci"],
        )
        if identity in identities:
            raise _field_problem(
                "raciAssignments",
                _("RACI assignments must be unique."),
            )
        identities.add(identity)


def _reject_duplicate_wbs_codes(records: Sequence[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for record in records:
        key = str(record["code"]).casefold()
        if key in seen:
            raise _field_problem("items.code", _("WBS codes must be unique."))
        seen.add(key)


def _validate_parent_graph(records: Mapping[str, Mapping[str, Any]]) -> None:
    edges = {
        UUID(item_id): (
            (record["parent_id"],)
            if record.get("parent_id") is not None
            else ()
        )
        for item_id, record in records.items()
    }
    for record in records.values():
        parent_id = record.get("parent_id")
        if parent_id is not None and str(parent_id) not in records:
            raise _field_problem(
                "items.parentId",
                _("Select a parent WBS item from this Project."),
            )
    _reject_graph_cycle(edges, "items.parentId")


def _reject_duplicate_dependencies(
    records: Sequence[Mapping[str, Any]],
) -> None:
    seen: set[tuple[UUID, UUID]] = set()
    for record in records:
        identity = (
            record["predecessor_id"],
            record["successor_id"],
        )
        if identity in seen:
            raise _field_problem(
                "dependencies",
                _("WBS dependencies must be unique."),
            )
        seen.add(identity)


def _validate_dependency_graph(
    items: Mapping[str, Mapping[str, Any]],
    dependencies: Sequence[Mapping[str, Any]],
) -> None:
    edges: dict[UUID, list[UUID]] = {
        UUID(item_id): [] for item_id in items
    }
    for dependency in dependencies:
        edges[dependency["predecessor_id"]].append(
            dependency["successor_id"]
        )
    _reject_graph_cycle(
        {node: tuple(successors) for node, successors in edges.items()},
        "dependencies",
    )


def _reject_graph_cycle(
    edges: Mapping[UUID, Sequence[UUID]],
    path: str,
) -> None:
    unvisited, visiting, visited = 0, 1, 2
    states: dict[UUID, int] = {}

    for start in edges:
        if states.get(start, unvisited) != unvisited:
            continue
        states[start] = visiting
        stack: list[tuple[UUID, int]] = [(start, 0)]
        while stack:
            node, successor_index = stack[-1]
            successors = edges.get(node, ())
            if successor_index >= len(successors):
                states[node] = visited
                stack.pop()
                continue

            successor = successors[successor_index]
            stack[-1] = (node, successor_index + 1)
            successor_state = states.get(successor, unvisited)
            if successor_state == visiting:
                raise _field_problem(
                    path,
                    _("The WBS graph cannot contain a cycle."),
                )
            if successor_state == unvisited:
                states[successor] = visiting
                stack.append((successor, 0))


def _comparable(value: object) -> object:
    if isinstance(value, datetime):
        return _datetime_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if value in ("", None):
        return None
    return value


@contextmanager
def _controlled_work_write_scope() -> Iterator[None]:
    flags = frappe.flags
    missing = object()
    previous_work = getattr(flags, "npi_project_work_command_write", missing)
    previous_project = getattr(flags, "npi_project_command_write", missing)
    previous_audit = getattr(flags, "npi_audit_append", missing)
    flags.npi_project_work_command_write = True
    flags.npi_project_command_write = True
    flags.npi_audit_append = True
    try:
        yield
    finally:
        _restore_flag(
            flags,
            "npi_project_work_command_write",
            previous_work,
            missing,
        )
        _restore_flag(
            flags,
            "npi_project_command_write",
            previous_project,
            missing,
        )
        _restore_flag(flags, "npi_audit_append", previous_audit, missing)


def _restore_flag(flags, name: str, previous: object, missing: object) -> None:
    if previous is missing:
        try:
            delattr(flags, name)
        except AttributeError:
            pass
    else:
        setattr(flags, name, previous)
