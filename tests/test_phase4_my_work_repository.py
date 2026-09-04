from __future__ import annotations

import copy
import hashlib
import importlib
import json
import sys
import types
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


class DoesNotExistError(Exception):
    pass


class FakeDocument(SimpleNamespace):
    def __init__(self, frappe_module, values):
        super().__init__(**values)
        self._frappe = frappe_module

    def set(self, fieldname, value):
        setattr(self, fieldname, value)

    def insert(self):
        if not getattr(
            self._frappe.flags,
            "npi_my_work_projection_write",
            False,
        ):
            raise AssertionError("Projection insert escaped its controlled flag.")
        self._frappe.inserted.append(self)
        self._frappe.documents[(self.doctype, str(self.global_id))] = self
        return self

    def save(self):
        if not getattr(
            self._frappe.flags,
            "npi_my_work_projection_write",
            False,
        ):
            raise AssertionError("Projection save escaped its controlled flag.")
        self._frappe.saved.append(self)
        return self


class FakeDatabase:
    def get_value(self, *_args, **_kwargs):
        return None

    def get_single_value(self, *_args, **_kwargs):
        return "UTC"


def install_fake_frappe():
    module = types.ModuleType("frappe")
    module._ = lambda source: source
    module.flags = SimpleNamespace()
    module.conf = {}
    module.db = FakeDatabase()
    module.documents = {}
    module.inserted = []
    module.saved = []
    module.DoesNotExistError = DoesNotExistError
    module.session = SimpleNamespace(user="owner@example.invalid")
    module.local = SimpleNamespace(
        form_dict={},
        response=SimpleNamespace(),
    )
    module.get_roles = lambda _actor: ["NPI API User"]
    module.get_request_header = lambda _name: None
    module.whitelist = lambda **_kwargs: (lambda function: function)

    def get_doc(doctype_or_values, name=None, **_kwargs):
        if isinstance(doctype_or_values, dict):
            return FakeDocument(module, doctype_or_values)
        try:
            return module.documents[(doctype_or_values, str(name))]
        except KeyError as error:
            raise DoesNotExistError from error

    module.get_doc = get_doc
    module.get_all = lambda *_args, **_kwargs: []
    sys.modules["frappe"] = module
    return module


fake_frappe = install_fake_frappe()

from npi_core.foundation.errors import (
    PermissionDenied,
    ProjectCollaborationRoutesDisabled,
    RequestValidationFailed,
)
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.my_work.domain import (
    DomainWorkItemKind,
    DomainWorkItemTarget,
    GateReviewTarget,
    MyWorkCategory,
    MyWorkItem,
    MyWorkPriority,
    MyWorkPriorityScheme,
    MyWorkSourceReference,
    MyWorkSourceType,
    MyWorkStatus,
    MyWorkView,
)


repository_module = importlib.import_module("npi_core.my_work.frappe_repository")
api_module = importlib.import_module("npi_core.my_work_api")

FrappeMyWorkAssignmentStore = repository_module.FrappeMyWorkAssignmentStore
FrappeMyWorkRepository = repository_module.FrappeMyWorkRepository
FrappeMyWorkSourceResolver = repository_module.FrappeMyWorkSourceResolver
GateWorkspaceAccess = repository_module.GateWorkspaceAccess
ProjectionSpec = repository_module.ProjectionSpec
ResolvedMyWorkRow = repository_module.ResolvedMyWorkRow
refresh_domain_work_item_assignment = (
    repository_module.refresh_domain_work_item_assignment
)
refresh_gate_review_assignments = repository_module.refresh_gate_review_assignments
refresh_gate_review_assignments_for_cycle = (
    repository_module.refresh_gate_review_assignments_for_cycle
)
refresh_project_my_work_assignments = (
    repository_module.refresh_project_my_work_assignments
)
rebuild_my_work_projection = repository_module.rebuild_my_work_projection


TENANT_ID = "TENANT-A"
ACTOR = "owner@example.invalid"
OTHER_ACTOR = "reviewer@example.invalid"
DECISION_ACTOR = "decider@example.invalid"
EXCEPTION_ACTOR = "exception-approver@example.invalid"
REOPEN_ACTOR = "reopener@example.invalid"
PROJECT_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_PROJECT_ID = UUID("99999999-9999-4999-8999-999999999999")
WORK_ID = UUID("22222222-2222-4222-8222-222222222222")
GATE_ID = UUID("33333333-3333-4333-8333-333333333333")
CYCLE_ID = UUID("44444444-4444-4444-8444-444444444444")
OWNER_MEMBER_ID = UUID("66666666-6666-4666-8666-666666666666")
DECISION_MEMBER_ID = UUID("77777777-7777-4777-8777-777777777777")
EXCEPTION_MEMBER_ID = UUID("88888888-8888-4888-8888-888888888888")
REOPEN_MEMBER_ID = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
EXCEPTION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
REQUIREMENT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
AS_OF = datetime(2026, 7, 25, 12, tzinfo=UTC)
REQUEST_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TRACE_ID = "trace-my-work-tests"


def principal() -> Principal:
    return Principal(
        user_id=ACTOR,
        roles=frozenset({"NPI API User"}),
        tenant_id=TENANT_ID,
    )


def domain_row(
    *,
    item_id: UUID,
    project_id: UUID = PROJECT_ID,
    due_at: datetime | None = AS_OF - timedelta(hours=1),
    priority_value: str = "high",
    blocking: bool = True,
    title: str = "Hot runner delivery risk",
) -> ResolvedMyWorkRow:
    item = MyWorkItem(
        id=item_id,
        project_global_id=project_id,
        source=MyWorkSourceReference(
            MyWorkSourceType.DOMAIN_WORK_ITEM,
            item_id,
            4,
        ),
        domain_kind=DomainWorkItemKind.RISK,
        category=MyWorkCategory.RISK,
        status=(MyWorkStatus.BLOCKED if blocking else MyWorkStatus.READY),
        due_at=due_at,
        priority=MyWorkPriority(
            MyWorkPriorityScheme.DOMAIN_SEVERITY,
            priority_value,
        ),
        blocking=blocking,
        target=DomainWorkItemTarget(item_id),
    )
    return ResolvedMyWorkRow(
        item=item,
        title=title,
        project_business_code="NPI-26018",
        project_title="Battery housing",
        context_code=str(item_id),
        context_title=title,
        why="domain_work_item_owner",
        action="view_work_item",
    )


def gate_row(
    *,
    item_id: UUID,
    source_id: UUID,
    source_type: MyWorkSourceType,
    status: MyWorkStatus,
    due_at: datetime | None,
    blocking: bool,
) -> ResolvedMyWorkRow:
    category = (
        MyWorkCategory.APPROVAL
        if source_type is MyWorkSourceType.GATE_REVIEW_ASSIGNMENT
        else MyWorkCategory.BLOCKER
    )
    item = MyWorkItem(
        id=item_id,
        project_global_id=PROJECT_ID,
        source=MyWorkSourceReference(source_type, source_id, 7),
        domain_kind=None,
        category=category,
        status=status,
        due_at=due_at,
        priority=None,
        blocking=blocking,
        target=GateReviewTarget(PROJECT_ID, source_id),
    )
    return ResolvedMyWorkRow(
        item=item,
        title="Review Gate G3 evidence",
        project_business_code="NPI-26018",
        project_title="Battery housing",
        context_code="G3",
        context_title="Tooling release",
        why=(
            "gate_review_step"
            if source_type is MyWorkSourceType.GATE_REVIEW_ASSIGNMENT
            else "gate_dependency_change"
        ),
        action="open_gate_review",
    )


class MemoryStore:
    def __init__(self, records=()):
        self.records = tuple(records)
        self.actor_queries = []
        self.upserts = []
        self.deactivations = []
        self.tenant_deactivations = []
        self.project_deactivations = []
        self.deactivate_one_calls = []

    def actor_assignments(
        self,
        *,
        tenant_id,
        actor_user_id,
        maximum,
    ):
        self.actor_queries.append((tenant_id, actor_user_id, maximum))
        return tuple(
            record
            for record in self.records
            if record.tenant_id == tenant_id
            and record.actor_user_id == actor_user_id
            and record.active
        )

    def upsert(self, spec, *, indexed_at):
        self.upserts.append((spec, indexed_at))
        return spec.global_id

    def deactivate_source_except(self, **values):
        self.deactivations.append(values)

    def deactivate_tenant_except(self, **values):
        self.tenant_deactivations.append(values)

    def deactivate_project_except(self, **values):
        self.project_deactivations.append(values)

    def deactivate_one(self, **values):
        self.deactivate_one_calls.append(values)
        return True

    def assignment_key(self, global_id):
        for spec, _at in self.upserts:
            if spec.global_id == global_id:
                return spec.assignment_key
        raise KeyError(global_id)


class MappingResolver:
    def __init__(self, rows):
        self.rows = dict(rows)
        self.calls = []

    def resolve(self, assignment, *, as_of):
        self.calls.append((assignment.assignment_key, as_of))
        return self.rows.get(assignment.assignment_key)


def assignment_candidate(key: str, *, actor: str = ACTOR):
    return SimpleNamespace(
        assignment_key=key,
        tenant_id=TENANT_ID,
        actor_user_id=actor.casefold(),
        active=1,
    )


class MyWorkRepositoryQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.first = domain_row(
            item_id=UUID("10000000-0000-4000-8000-000000000001"),
        )
        self.second = gate_row(
            item_id=UUID("20000000-0000-4000-8000-000000000002"),
            source_id=GATE_ID,
            source_type=MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
            status=MyWorkStatus.WAITING,
            due_at=AS_OF + timedelta(hours=1),
            blocking=False,
        )
        self.third = gate_row(
            item_id=UUID("30000000-0000-4000-8000-000000000003"),
            source_id=UUID("55555555-5555-4555-8555-555555555555"),
            source_type=MyWorkSourceType.GATE_REVIEW_INVALIDATION,
            status=MyWorkStatus.BLOCKED,
            due_at=None,
            blocking=True,
        )
        records = tuple(
            assignment_candidate(key)
            for key in (
                "first",
                "second",
                "third",
                "stale",
                "cross-tenant-source",
                "inaccessible",
            )
        ) + (assignment_candidate("other-actor", actor=OTHER_ACTOR),)
        self.store = MemoryStore(records)
        self.resolver = MappingResolver(
            {
                "first": self.first,
                "second": self.second,
                "third": self.third,
            }
        )
        self.repository = FrappeMyWorkRepository(
            principal=principal(),
            request_id=REQUEST_ID,
            trace_id=TRACE_ID,
            store=self.store,
            source_resolver=self.resolver,
            clock=lambda: AS_OF,
            time_zone_resolver=lambda _actor: "UTC",
            signing_key_resolver=lambda: b"k" * 32,
        )

    def query(self, **overrides):
        values = {
            "view": MyWorkView.ALL,
            "project_global_id": None,
            "priority": None,
            "search": None,
            "cursor": None,
            "limit": 50,
        }
        values.update(overrides)
        return self.repository.query(**values)

    def test_query_revalidates_every_candidate_and_returns_closed_page(self):
        response = self.query(limit=2)
        self.assertEqual(
            self.store.actor_queries,
            [(TENANT_ID, ACTOR, 2000)],
        )
        self.assertEqual(
            {key for key, _as_of in self.resolver.calls},
            {
                "first",
                "second",
                "third",
                "stale",
                "cross-tenant-source",
                "inaccessible",
            },
        )
        self.assertEqual(
            set(response),
            {
                "asOf",
                "timeZone",
                "projectOptions",
                "items",
                "nextCursor",
                "counts",
            },
        )
        self.assertEqual(response["asOf"], "2026-07-25T12:00:00.000000Z")
        self.assertEqual(response["timeZone"], "UTC")
        self.assertEqual(
            response["projectOptions"],
            [
                {
                    "globalId": str(PROJECT_ID),
                    "businessCode": "NPI-26018",
                    "title": "Battery housing",
                }
            ],
        )
        self.assertEqual(len(response["items"]), 2)
        self.assertIsNotNone(response["nextCursor"])
        self.assertEqual(
            response["counts"],
            {
                "all": {"availability": "available", "value": 3},
                "today": {"availability": "available", "value": 2},
                "overdue": {"availability": "available", "value": 1},
                "approvals": {"availability": "available", "value": 1},
                "blockers": {"availability": "available", "value": 2},
                "waiting": {"availability": "available", "value": 1},
                "integration": {
                    "availability": "unavailable",
                    "reason": "source_not_available",
                },
            },
        )
        for item in response["items"]:
            self.assertEqual(
                set(item),
                {
                    "id",
                    "category",
                    "title",
                    "project",
                    "context",
                    "source",
                    "why",
                    "status",
                    "dueAt",
                    "dueState",
                    "priority",
                    "blocking",
                    "action",
                    "target",
                    "sourceStatus",
                },
            )
            self.assertNotIn("path", item["target"])
        self.assertEqual(
            [item["dueState"] for item in response["items"]],
            ["overdue", "today"],
        )
        self.assertEqual(self.store.deactivations, [])

    def test_project_filter_options_include_projects_beyond_the_current_page(self):
        other = domain_row(
            item_id=UUID("40000000-0000-4000-8000-000000000004"),
            project_id=OTHER_PROJECT_ID,
            due_at=None,
        )
        repository = FrappeMyWorkRepository(
            principal=principal(),
            request_id=REQUEST_ID,
            trace_id=TRACE_ID,
            store=MemoryStore(
                (
                    assignment_candidate("first"),
                    assignment_candidate("other"),
                )
            ),
            source_resolver=MappingResolver(
                {
                    "first": self.first,
                    "other": other,
                }
            ),
            clock=lambda: AS_OF,
            time_zone_resolver=lambda _actor: "UTC",
            signing_key_resolver=lambda: b"k" * 32,
        )
        response = repository.query(
            view=MyWorkView.ALL,
            project_global_id=None,
            priority=None,
            search=None,
            cursor=None,
            limit=1,
        )
        self.assertEqual(len(response["items"]), 1)
        self.assertIsNotNone(response["nextCursor"])
        self.assertEqual(
            {value["globalId"] for value in response["projectOptions"]},
            {str(PROJECT_ID), str(OTHER_PROJECT_ID)},
        )

    def test_cursor_keeps_as_of_and_search_query_identity(self):
        first_page = self.query(limit=2, search="housing")
        second_page = self.query(
            limit=2,
            search="housing",
            cursor=first_page["nextCursor"],
        )
        self.assertEqual(second_page["asOf"], first_page["asOf"])
        self.assertEqual(len(second_page["items"]), 1)
        self.assertIsNone(second_page["nextCursor"])
        with self.assertRaises(RequestValidationFailed) as mismatch:
            self.query(
                limit=2,
                search="tooling",
                cursor=first_page["nextCursor"],
            )
        self.assertEqual(
            mismatch.exception.field_errors[0]["path"],
            "cursor",
        )
        token = first_page["nextCursor"]
        replacement = "A" if token[-1] != "A" else "B"
        with self.assertRaises(RequestValidationFailed):
            self.query(
                limit=2,
                search="housing",
                cursor=token[:-1] + replacement,
            )

    def test_cursor_is_bound_to_exact_actor_and_tenant(self):
        first_page = self.query(limit=2, search="housing")
        cursor = first_page["nextCursor"]
        self.assertIsInstance(cursor, str)

        for mismatched_principal in (
            Principal(
                user_id=OTHER_ACTOR,
                roles=frozenset({"NPI API User"}),
                tenant_id=TENANT_ID,
            ),
            Principal(
                user_id=ACTOR,
                roles=frozenset({"NPI API User"}),
                tenant_id="TENANT-B",
            ),
        ):
            with self.subTest(principal=mismatched_principal):
                repository = FrappeMyWorkRepository(
                    principal=mismatched_principal,
                    request_id=REQUEST_ID,
                    trace_id=TRACE_ID,
                    store=self.store,
                    source_resolver=self.resolver,
                    clock=lambda: AS_OF,
                    time_zone_resolver=lambda _actor: "UTC",
                    signing_key_resolver=lambda: b"k" * 32,
                )
                with self.assertRaises(RequestValidationFailed) as mismatch:
                    repository.query(
                        view=MyWorkView.ALL,
                        project_global_id=None,
                        priority=None,
                        search="housing",
                        cursor=cursor,
                        limit=2,
                    )
                self.assertEqual(
                    mismatch.exception.field_errors,
                    [{"path": "cursor", "message": "Enter a valid cursor."}],
                )

    def test_views_project_and_exact_priority_filters_are_server_owned(self):
        blockers = self.query(view=MyWorkView.BLOCKERS)
        self.assertEqual(
            [item["category"] for item in blockers["items"]],
            ["risk", "blocker"],
        )
        waiting = self.query(view=MyWorkView.WAITING)
        self.assertEqual(
            [item["category"] for item in waiting["items"]],
            ["approval"],
        )
        high = self.query(
            priority=MyWorkPriority(
                MyWorkPriorityScheme.DOMAIN_SEVERITY,
                "high",
            )
        )
        self.assertEqual(
            [item["category"] for item in high["items"]],
            ["risk"],
        )
        integration = self.query(view=MyWorkView.INTEGRATION)
        self.assertEqual(integration["items"], [])
        self.assertEqual(
            integration["counts"]["integration"]["availability"],
            "unavailable",
        )
        other_project = self.query(project_global_id=OTHER_PROJECT_ID)
        self.assertEqual(other_project["items"], [])
        self.assertEqual(other_project["counts"]["all"]["value"], 0)


class MyWorkRefreshTests(unittest.TestCase):
    def project(self, *, lifecycle_state="active"):
        return SimpleNamespace(
            doctype="NPI Engineering Project",
            global_id=str(PROJECT_ID),
            tenant_id=TENANT_ID,
            business_code="NPI-26018",
            title="Battery housing",
            lifecycle_state=lifecycle_state,
        )

    def domain_source(self, *, terminal=False):
        return SimpleNamespace(
            doctype="NPI Domain Work Item",
            global_id=str(WORK_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            kind="action",
            owner_user_id=ACTOR.upper(),
            state_terminal=int(terminal),
            optimistic_version=4,
            severity="critical",
            due_at=AS_OF,
            blocking=1,
            title="Close dimensional action",
        )

    def test_domain_refresh_maps_exact_owner_and_deactivates_terminal(self):
        store = MemoryStore()
        result = refresh_domain_work_item_assignment(
            self.domain_source(),
            store=store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            project=self.project(),
        )
        self.assertEqual(len(result), 1)
        spec = store.upserts[0][0]
        self.assertEqual(spec.actor_user_id, ACTOR)
        self.assertIs(spec.category, MyWorkCategory.TASK)
        self.assertEqual(
            spec.priority,
            MyWorkPriority(
                MyWorkPriorityScheme.DOMAIN_SEVERITY,
                "critical",
            ),
        )
        self.assertTrue(spec.blocking)
        self.assertIs(spec.status, MyWorkStatus.BLOCKED)
        self.assertEqual(
            store.deactivations[0]["keep_assignment_keys"],
            frozenset({spec.assignment_key}),
        )

        terminal_store = MemoryStore()
        terminal_result = refresh_domain_work_item_assignment(
            self.domain_source(terminal=True),
            store=terminal_store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            project=self.project(),
        )
        self.assertEqual(terminal_result, ())
        self.assertEqual(terminal_store.upserts, [])
        self.assertEqual(
            terminal_store.deactivations[0]["keep_assignment_keys"],
            frozenset(),
        )

        completed_store = MemoryStore()
        completed_result = refresh_domain_work_item_assignment(
            self.domain_source(),
            store=completed_store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            project=self.project(lifecycle_state="completed"),
        )
        self.assertEqual(completed_result, ())
        self.assertEqual(completed_store.upserts, [])

    def workspace(self, *, review_state="in_review"):
        owner_member_id = str(OWNER_MEMBER_ID)
        steps = [
            {
                "stepKey": "quality",
                "sequence": 1,
                "slot": "quality",
                "assignedMember": {
                    "memberGlobalId": owner_member_id,
                    "userId": ACTOR,
                    "displayName": "Owner",
                },
                "state": ("available" if review_state == "in_review" else "waiting"),
                "review": None,
            },
            {
                "stepKey": "management",
                "sequence": 2,
                "slot": "management",
                "assignedMember": {
                    "memberGlobalId": owner_member_id,
                    "userId": ACTOR,
                    "displayName": "Owner",
                },
                "state": "waiting",
                "review": None,
            },
        ]
        return {
            "tenantId": TENANT_ID,
            "project": {
                "globalId": str(PROJECT_ID),
                "businessCode": "NPI-26018",
                "title": "Battery housing",
                "lifecycleState": "active",
            },
            "gate": {
                "globalId": str(GATE_ID),
                "key": "G3",
                "title": "Tooling release",
                "reviewState": review_state,
                "version": 7,
                "currentCycleGlobalId": str(CYCLE_ID),
            },
            "activeCycle": {
                "globalId": str(CYCLE_ID),
                "state": "active",
                "policyRef": {
                    "globalId": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                    "version": 1,
                    "snapshotHash": "a" * 64,
                },
                "policyDefinition": {
                    "policyRef": {
                        "globalId": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                        "version": 1,
                        "snapshotHash": "a" * 64,
                    },
                    "authoritySlots": [
                        {"slot": "quality", "purpose": "review"},
                        {"slot": "management", "purpose": "review"},
                        {"slot": "gate_decider", "purpose": "decision"},
                        {"slot": "gate_reopener", "purpose": "reopen"},
                        {"slot": "exception_approver", "purpose": "exception"},
                    ],
                    "exceptionRules": [
                        {
                            "kind": "temporary_deviation",
                            "eligibleRequirementKeys": ["tooling_ready"],
                            "approvalAuthoritySlot": "exception_approver",
                            "maximumValidityDays": 30,
                            "requiredClosureActionKind": "action",
                        }
                    ],
                },
                "bindings": [
                    {
                        "slot": slot,
                        "memberGlobalId": owner_member_id,
                        "userId": ACTOR,
                        "displayName": "Owner",
                    }
                    for slot in (
                        "quality",
                        "management",
                        "gate_decider",
                        "gate_reopener",
                        "exception_approver",
                    )
                ],
                "selectedSteps": steps,
                "exceptions": [],
            },
            "eligibleMembers": [
                {
                    "memberGlobalId": owner_member_id,
                    "userId": ACTOR,
                    "displayName": "Owner",
                }
            ],
            "permissions": {
                "canView": True,
                "canReview": review_state == "in_review",
                "canStartReview": review_state == "requires_review",
                "canRequestException": False,
                "canApproveException": False,
                "canDecide": False,
                "canReopen": False,
            },
        }

    def authority_workspace(self):
        workspace = self.workspace()
        identities = {
            "quality": (str(OWNER_MEMBER_ID), ACTOR, "Owner"),
            "management": (str(OWNER_MEMBER_ID), ACTOR, "Owner"),
            "gate_decider": (
                str(DECISION_MEMBER_ID),
                DECISION_ACTOR,
                "Gate Decider",
            ),
            "gate_reopener": (
                str(REOPEN_MEMBER_ID),
                REOPEN_ACTOR,
                "Gate Reopener",
            ),
            "exception_approver": (
                str(EXCEPTION_MEMBER_ID),
                EXCEPTION_ACTOR,
                "Exception Approver",
            ),
        }
        workspace["activeCycle"]["bindings"] = [
            {
                "slot": slot,
                "memberGlobalId": identity[0],
                "userId": identity[1],
                "displayName": identity[2],
            }
            for slot, identity in identities.items()
        ]
        workspace["eligibleMembers"] = [
            {
                "memberGlobalId": member_id,
                "userId": user_id,
                "displayName": display_name,
            }
            for member_id, user_id, display_name in dict.fromkeys(
                identities.values()
            )
        ]
        workspace["activeCycle"]["exceptions"] = [
            {
                "globalId": str(EXCEPTION_ID),
                "requirementGlobalId": str(REQUIREMENT_ID),
                "requirementKey": "tooling_ready",
                "kind": "temporary_deviation",
                "reason": "Controlled temporary deviation",
                "risk": "Tooling evidence must be completed",
                "requester": {
                    "memberGlobalId": str(OWNER_MEMBER_ID),
                    "userId": ACTOR,
                    "displayName": "Owner",
                },
                "requestedAt": "2026-07-25T10:00:00.000000Z",
                "expiresAt": "2026-07-27T12:00:00.000000Z",
                "requestSchemaVersion": 2,
                "closureActionRef": {
                    "globalId": str(WORK_ID),
                    "version": 4,
                    "snapshotHash": "b" * 64,
                },
                "state": "pending",
                "allowedOutcomes": ["approved", "rejected"],
                "version": 1,
                "requestSnapshotHash": "c" * 64,
                "decision": None,
            }
        ]
        return workspace

    def gate_documents(self, *, cycle_state="active", bindings=None):
        project = self.project()
        gate = SimpleNamespace(
            doctype="NPI Gate Shell",
            global_id=str(GATE_ID),
            project_global_id=str(PROJECT_ID),
            current_review_cycle_global_id=str(CYCLE_ID),
        )
        cycle = SimpleNamespace(
            doctype="NPI Gate Review Cycle",
            global_id=str(CYCLE_ID),
            gate_global_id=str(GATE_ID),
            project_global_id=str(PROJECT_ID),
            state=cycle_state,
            authority_bindings=json.dumps(
                bindings
                or [
                    {
                        "slot": "quality",
                        "memberGlobalId": str(OWNER_MEMBER_ID),
                        "userId": ACTOR,
                        "displayName": "Owner",
                    }
                ]
            ),
        )
        fake_frappe.documents[("NPI Engineering Project", str(PROJECT_ID))] = project
        fake_frappe.documents[("NPI Gate Review Cycle", str(CYCLE_ID))] = cycle
        fake_frappe.documents[("NPI Gate Shell", str(GATE_ID))] = gate
        return gate

    def test_gate_refresh_keeps_exact_active_steps_and_invalidation_actor(self):
        gate = self.gate_documents()
        active_store = MemoryStore()
        active_access = GateWorkspaceAccess(
            self.workspace(),
            frozenset({"NPI API User"}),
        )
        active = refresh_gate_review_assignments(
            gate,
            store=active_store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=lambda *_args: active_access,
        )
        self.assertEqual(len(active), 2)
        self.assertEqual(
            [spec.status for spec, _at in active_store.upserts],
            [MyWorkStatus.READY, MyWorkStatus.WAITING],
        )
        self.assertTrue(
            all(
                spec.category is MyWorkCategory.APPROVAL
                and spec.source_type is MyWorkSourceType.GATE_REVIEW_ASSIGNMENT
                for spec, _at in active_store.upserts
            )
        )

        invalidation_store = MemoryStore()
        invalidation_access = GateWorkspaceAccess(
            self.workspace(review_state="requires_review"),
            frozenset({"NPI API User", "System Manager"}),
        )
        invalidation = refresh_gate_review_assignments(
            gate,
            store=invalidation_store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=lambda *_args: invalidation_access,
        )
        self.assertEqual(len(invalidation), 1)
        spec = invalidation_store.upserts[0][0]
        self.assertIs(
            spec.source_type,
            MyWorkSourceType.GATE_REVIEW_INVALIDATION,
        )
        self.assertIs(spec.category, MyWorkCategory.BLOCKER)
        self.assertTrue(spec.blocking)
        self.assertEqual(
            spec.source_detail_dict()["stepKey"],
            "quality",
        )

    def test_gate_authorities_project_only_exact_capability_and_binding(self):
        workspace = self.authority_workspace()

        def projected(actor, capability, *, selected_workspace=workspace):
            actor_workspace = copy.deepcopy(selected_workspace)
            for key in (
                "canReview",
                "canStartReview",
                "canApproveException",
                "canDecide",
                "canReopen",
            ):
                actor_workspace["permissions"][key] = key == capability
            return repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    actor_workspace,
                    frozenset({"NPI API User", "System Manager"}),
                ),
                actor=actor,
            )

        owner_specs = projected(ACTOR, "canReview")
        self.assertEqual(
            [spec.assignment_code for spec in owner_specs],
            ["gate_review_step", "gate_review_step"],
        )
        self.assertEqual(
            [spec.status for spec in owner_specs],
            [MyWorkStatus.READY, MyWorkStatus.WAITING],
        )

        decision_specs = projected(DECISION_ACTOR, "canDecide")
        self.assertEqual(
            [spec.assignment_code for spec in decision_specs],
            ["gate_final_decision"],
        )
        self.assertEqual(
            decision_specs[0].source_detail_dict()["authoritySlot"],
            "gate_decider",
        )

        exception_specs = projected(EXCEPTION_ACTOR, "canApproveException")
        self.assertEqual(
            [spec.assignment_code for spec in exception_specs],
            ["gate_exception"],
        )
        self.assertEqual(
            exception_specs[0].due_at,
            datetime(2026, 7, 27, 12, tzinfo=UTC),
        )
        self.assertEqual(
            exception_specs[0].source_detail_dict()["exceptionGlobalId"],
            str(EXCEPTION_ID),
        )

        decided = copy.deepcopy(workspace)
        decided["gate"]["reviewState"] = "decided"
        decided["activeCycle"]["state"] = "decided"
        reopen_specs = projected(
            REOPEN_ACTOR,
            "canReopen",
            selected_workspace=decided,
        )
        self.assertEqual(
            [spec.assignment_code for spec in reopen_specs],
            ["gate_reopen"],
        )

        # Transport or System Manager status never substitutes for an exact
        # frozen authority assignment and current Project membership.
        self.assertEqual(projected(OTHER_ACTOR, "canDecide"), ())

    def test_parallel_gate_steps_with_shared_sequence_project_exact_assignees(self):
        same_actor = self.workspace()
        same_actor_steps = same_actor["activeCycle"]["selectedSteps"]
        same_actor_steps[1]["sequence"] = 1
        same_actor_steps[1]["state"] = "available"
        same_actor_specs = repository_module._gate_projection_specs(
            GateWorkspaceAccess(
                same_actor,
                frozenset({"NPI API User"}),
            ),
            actor=ACTOR,
        )
        self.assertEqual(len(same_actor_specs), 2)
        self.assertEqual(
            {
                spec.source_detail_dict()["stepKey"]
                for spec in same_actor_specs
            },
            {"quality", "management"},
        )
        self.assertTrue(
            all(spec.status is MyWorkStatus.READY for spec in same_actor_specs)
        )

        split_actor = copy.deepcopy(same_actor)
        reviewer_identity = {
            "memberGlobalId": str(DECISION_MEMBER_ID),
            "userId": OTHER_ACTOR,
            "displayName": "Reviewer",
        }
        split_actor["activeCycle"]["selectedSteps"][1]["assignedMember"] = (
            reviewer_identity
        )
        for binding in split_actor["activeCycle"]["bindings"]:
            if binding["slot"] == "management":
                binding.update(reviewer_identity)
        split_actor["eligibleMembers"].append(reviewer_identity)

        owner_specs = repository_module._gate_projection_specs(
            GateWorkspaceAccess(
                split_actor,
                frozenset({"NPI API User"}),
            ),
            actor=ACTOR,
        )
        reviewer_specs = repository_module._gate_projection_specs(
            GateWorkspaceAccess(
                split_actor,
                frozenset({"NPI API User"}),
            ),
            actor=OTHER_ACTOR,
        )
        self.assertEqual(
            [spec.source_detail_dict()["stepKey"] for spec in owner_specs],
            ["quality"],
        )
        self.assertEqual(
            [spec.source_detail_dict()["stepKey"] for spec in reviewer_specs],
            ["management"],
        )

    def test_same_actor_multi_authority_has_stable_unique_assignment_ids(self):
        workspace = self.workspace()
        workspace["activeCycle"]["exceptions"] = copy.deepcopy(
            self.authority_workspace()["activeCycle"]["exceptions"]
        )
        workspace["activeCycle"]["exceptions"][0]["requester"] = {
            "memberGlobalId": str(DECISION_MEMBER_ID),
            "userId": OTHER_ACTOR,
            "displayName": "Requester",
        }
        workspace["eligibleMembers"].append(
            {
                "memberGlobalId": str(DECISION_MEMBER_ID),
                "userId": OTHER_ACTOR,
                "displayName": "Requester",
            }
        )
        workspace["permissions"]["canDecide"] = True
        workspace["permissions"]["canApproveException"] = True
        access = GateWorkspaceAccess(
            workspace,
            frozenset({"NPI API User"}),
        )

        first = repository_module._gate_projection_specs(access, actor=ACTOR)
        second = repository_module._gate_projection_specs(access, actor=ACTOR)
        self.assertEqual(
            [spec.assignment_code for spec in first],
            [
                "gate_review_step",
                "gate_review_step",
                "gate_final_decision",
                "gate_exception",
            ],
        )
        self.assertEqual(
            [(spec.assignment_key, spec.global_id) for spec in first],
            [(spec.assignment_key, spec.global_id) for spec in second],
        )
        self.assertEqual(
            len({spec.assignment_key for spec in first}),
            len(first),
        )
        self.assertEqual(
            len({spec.global_id for spec in first}),
            len(first),
        )

    def test_refresh_loads_each_frozen_authority_and_decided_reopener(self):
        workspace = self.authority_workspace()
        bindings = copy.deepcopy(workspace["activeCycle"]["bindings"])
        gate = self.gate_documents(bindings=bindings)
        loaded = []

        def loader(actor, *_identities):
            loaded.append(actor)
            actor_workspace = copy.deepcopy(workspace)
            actor_workspace["permissions"].update(
                {
                    "canReview": actor == ACTOR,
                    "canStartReview": False,
                    "canApproveException": actor == EXCEPTION_ACTOR,
                    "canDecide": actor == DECISION_ACTOR,
                    "canReopen": False,
                }
            )
            return GateWorkspaceAccess(
                actor_workspace,
                frozenset({"NPI API User"}),
            )

        active_store = MemoryStore()
        result = refresh_gate_review_assignments(
            gate,
            store=active_store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=loader,
        )
        self.assertEqual(len(result), 4)
        self.assertEqual(
            set(loaded),
            {ACTOR, DECISION_ACTOR, EXCEPTION_ACTOR, REOPEN_ACTOR},
        )
        self.assertEqual(
            {
                spec.assignment_code
                for spec, _indexed_at in active_store.upserts
            },
            {
                "gate_review_step",
                "gate_final_decision",
                "gate_exception",
            },
        )

        fake_frappe.documents[
            ("NPI Gate Review Cycle", str(CYCLE_ID))
        ].state = "decided"
        decided_workspace = copy.deepcopy(workspace)
        decided_workspace["gate"]["reviewState"] = "decided"
        decided_workspace["activeCycle"]["state"] = "decided"

        def decided_loader(actor, *_identities):
            actor_workspace = copy.deepcopy(decided_workspace)
            actor_workspace["permissions"].update(
                {
                    "canReview": False,
                    "canStartReview": False,
                    "canApproveException": False,
                    "canDecide": False,
                    "canReopen": actor == REOPEN_ACTOR,
                }
            )
            return GateWorkspaceAccess(
                actor_workspace,
                frozenset({"NPI API User"}),
            )

        decided_store = MemoryStore()
        reopened = refresh_gate_review_assignments(
            gate,
            store=decided_store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=decided_loader,
        )
        self.assertEqual(len(reopened), 1)
        self.assertEqual(
            decided_store.upserts[0][0].assignment_code,
            "gate_reopen",
        )
        self.assertEqual(
            decided_store.upserts[0][0].actor_user_id,
            REOPEN_ACTOR,
        )

    def test_administrator_loader_preserves_case_but_storage_is_casefolded(self):
        administrator_member = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
        gate = self.gate_documents(
            bindings=[
                {
                    "slot": "quality",
                    "memberGlobalId": administrator_member,
                    "userId": "Administrator",
                    "displayName": "Administrator",
                }
            ]
        )
        self.assertEqual(
            repository_module._current_cycle_binding_actors(gate),
            ("Administrator",),
        )

        workspace = self.workspace()
        for binding in workspace["activeCycle"]["bindings"]:
            binding.update(
                {
                    "memberGlobalId": administrator_member,
                    "userId": "Administrator",
                    "displayName": "Administrator",
                }
            )
        for step in workspace["activeCycle"]["selectedSteps"]:
            step["assignedMember"].update(
                {
                    "memberGlobalId": administrator_member,
                    "userId": "Administrator",
                    "displayName": "Administrator",
                }
            )
        workspace["eligibleMembers"] = [
            {
                "memberGlobalId": administrator_member,
                "userId": "Administrator",
                "displayName": "Administrator",
            }
        ]
        loaded = []
        store = MemoryStore()
        result = refresh_gate_review_assignments(
            gate,
            store=store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=lambda actor, *_identities: (
                loaded.append(actor)
                or GateWorkspaceAccess(
                    workspace,
                    frozenset({"NPI API User"}),
                )
            ),
        )
        self.assertEqual(loaded, ["Administrator"])
        self.assertEqual(len(result), 2)
        self.assertTrue(
            all(
                spec.actor_user_id == "administrator"
                for spec, _indexed_at in store.upserts
            )
        )
        self.assertEqual(
            repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    workspace,
                    frozenset({"NPI API User"}),
                ),
                actor="administrator",
            ),
            (),
        )

        lower_workspace = copy.deepcopy(workspace)
        for binding in lower_workspace["activeCycle"]["bindings"]:
            binding["userId"] = "administrator"
        for step in lower_workspace["activeCycle"]["selectedSteps"]:
            step["assignedMember"]["userId"] = "administrator"
        lower_workspace["eligibleMembers"][0]["userId"] = "administrator"
        lower_specs = repository_module._gate_projection_specs(
            GateWorkspaceAccess(
                lower_workspace,
                frozenset({"NPI API User"}),
            ),
            actor="administrator",
        )
        self.assertEqual(
            [spec.assignment_key for spec, _indexed_at in store.upserts],
            [spec.assignment_key for spec in lower_specs],
        )

    def test_capability_membership_and_state_drift_remove_gate_projection(self):
        workspace = self.authority_workspace()
        workspace["permissions"]["canReview"] = False
        workspace["permissions"]["canDecide"] = True
        access = GateWorkspaceAccess(workspace, frozenset({"NPI API User"}))
        decision = repository_module._gate_projection_specs(
            access,
            actor=DECISION_ACTOR,
        )
        self.assertEqual(
            [spec.assignment_code for spec in decision],
            ["gate_final_decision"],
        )

        no_capability = copy.deepcopy(workspace)
        no_capability["permissions"]["canDecide"] = False
        self.assertEqual(
            repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    no_capability,
                    frozenset({"NPI API User", "System Manager"}),
                ),
                actor=DECISION_ACTOR,
            ),
            (),
        )

        former_member = copy.deepcopy(workspace)
        former_member["eligibleMembers"] = [
            member
            for member in former_member["eligibleMembers"]
            if member["userId"] != DECISION_ACTOR
        ]
        self.assertEqual(
            repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    former_member,
                    frozenset({"NPI API User"}),
                ),
                actor=DECISION_ACTOR,
            ),
            (),
        )

        no_exception_outcomes = copy.deepcopy(workspace)
        no_exception_outcomes["permissions"]["canDecide"] = False
        no_exception_outcomes["permissions"]["canApproveException"] = True
        no_exception_outcomes["activeCycle"]["exceptions"][0][
            "allowedOutcomes"
        ] = []
        self.assertEqual(
            repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    no_exception_outcomes,
                    frozenset({"NPI API User"}),
                ),
                actor=EXCEPTION_ACTOR,
            ),
            (),
        )

        mismatched_policy = copy.deepcopy(workspace)
        mismatched_policy["activeCycle"]["policyRef"]["snapshotHash"] = "b" * 64
        self.assertEqual(
            repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    mismatched_policy,
                    frozenset({"NPI API User"}),
                ),
                actor=DECISION_ACTOR,
            ),
            (),
        )

        wrong_cycle_state = copy.deepcopy(workspace)
        wrong_cycle_state["gate"]["reviewState"] = "decided"
        wrong_cycle_state["permissions"]["canDecide"] = False
        wrong_cycle_state["permissions"]["canReopen"] = True
        self.assertEqual(
            repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    wrong_cycle_state,
                    frozenset({"NPI API User"}),
                ),
                actor=REOPEN_ACTOR,
            ),
            (),
        )

        terminal = copy.deepcopy(workspace)
        terminal["project"]["lifecycleState"] = "completed"
        self.assertEqual(
            repository_module._gate_projection_specs(
                GateWorkspaceAccess(
                    terminal,
                    frozenset({"NPI API User"}),
                ),
                actor=DECISION_ACTOR,
            ),
            (),
        )

    def test_gate_refresh_requires_real_transport_and_current_member(self):
        gate = self.gate_documents()
        no_transport = GateWorkspaceAccess(
            self.workspace(),
            frozenset({"System Manager"}),
        )
        store = MemoryStore()
        result = refresh_gate_review_assignments(
            gate,
            store=store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=lambda *_args: no_transport,
        )
        self.assertEqual(result, ())
        self.assertEqual(store.upserts, [])
        self.assertEqual(len(store.deactivations), 2)

        for failure in (
            KeyError("activeCycle"),
            TypeError("Gate workspace is malformed."),
            ValueError("Persisted Gate evidence integrity failed."),
        ):
            with self.subTest(loader_failure=type(failure).__name__):
                integrity_failed_store = MemoryStore()

                def integrity_failed_loader(*_args):
                    raise failure

                result = refresh_gate_review_assignments(
                    gate,
                    store=integrity_failed_store,
                    tenant_id=TENANT_ID,
                    indexed_at=AS_OF,
                    workspace_loader=integrity_failed_loader,
                )
                self.assertEqual(result, ())
                self.assertEqual(integrity_failed_store.upserts, [])
                self.assertEqual(
                    [
                        deactivation["keep_assignment_keys"]
                        for deactivation in integrity_failed_store.deactivations
                    ],
                    [frozenset(), frozenset()],
                )

        operational_failure_store = MemoryStore()

        def operational_failure_loader(*_args):
            raise RuntimeError("Database connection failed.")

        with self.assertRaises(RuntimeError):
            refresh_gate_review_assignments(
                gate,
                store=operational_failure_store,
                tenant_id=TENANT_ID,
                indexed_at=AS_OF,
                workspace_loader=operational_failure_loader,
            )
        self.assertEqual(operational_failure_store.deactivations, [])

        inaccessible = self.workspace()
        inaccessible["eligibleMembers"] = []
        store = MemoryStore()
        result = refresh_gate_review_assignments(
            gate,
            store=store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=lambda *_args: GateWorkspaceAccess(
                inaccessible,
                frozenset({"NPI API User"}),
            ),
        )
        self.assertEqual(result, ())

        terminal = self.workspace()
        terminal["project"]["lifecycleState"] = "cancelled"
        store = MemoryStore()
        result = refresh_gate_review_assignments(
            gate,
            store=store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
            workspace_loader=lambda *_args: GateWorkspaceAccess(
                terminal,
                frozenset({"NPI API User"}),
            ),
        )
        self.assertEqual(result, ())
        self.assertEqual(store.upserts, [])

    def test_project_lifecycle_hook_durably_deactivates_all_source_types(self):
        store = MemoryStore()
        result = refresh_project_my_work_assignments(
            self.project(lifecycle_state="cancelled"),
            store=store,
            tenant_id=TENANT_ID,
            indexed_at=AS_OF,
        )
        self.assertEqual(result, ())
        self.assertEqual(len(store.project_deactivations), 1)
        deactivation = store.project_deactivations[0]
        self.assertEqual(
            deactivation["source_types"],
            frozenset(
                {
                    MyWorkSourceType.DOMAIN_WORK_ITEM,
                    MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
                    MyWorkSourceType.GATE_REVIEW_INVALIDATION,
                }
            ),
        )
        self.assertEqual(
            deactivation["keep_assignment_keys"],
            frozenset(),
        )

    def test_terminal_sources_fail_closed_even_when_index_rows_remain_active(self):
        active_project = self.project()
        source = self.domain_source()
        spec = repository_module._domain_projection_spec(
            source,
            active_project,
        )
        self.assertIsNotNone(spec)
        snapshot = repository_module._projection_snapshot(spec)
        assignment = SimpleNamespace(
            global_id=str(spec.global_id),
            assignment_key=spec.assignment_key,
            tenant_id=spec.tenant_id,
            actor_user_id=spec.actor_user_id,
            project_global_id=str(spec.project_global_id),
            source_type=spec.source_type.value,
            source_global_id=str(spec.source_global_id),
            source_version=spec.source_version,
            assignment_code=spec.assignment_code,
            category=spec.category.value,
            due_at=spec.due_at,
            priority_scheme=spec.priority.scheme.value,
            priority_value=spec.priority.value,
            blocking=int(spec.blocking),
            active=1,
            source_snapshot=repository_module._canonical_json(snapshot),
            snapshot_hash=repository_module._sha256_json(snapshot),
        )
        fake_frappe.documents[("NPI Domain Work Item", str(WORK_ID))] = source
        fake_frappe.documents[("NPI Engineering Project", str(PROJECT_ID))] = (
            self.project(lifecycle_state="completed")
        )
        resolver = FrappeMyWorkSourceResolver(
            principal=principal(),
            request_id=REQUEST_ID,
            trace_id=TRACE_ID,
        )
        self.assertIsNone(resolver.resolve(assignment, as_of=AS_OF))

        gate_access = GateWorkspaceAccess(
            self.workspace(),
            frozenset({"NPI API User"}),
        )
        gate_spec = repository_module._gate_projection_specs(
            gate_access,
            actor=ACTOR,
        )[0]
        gate_snapshot = repository_module._projection_snapshot(gate_spec)
        gate_assignment = SimpleNamespace(
            global_id=str(gate_spec.global_id),
            assignment_key=gate_spec.assignment_key,
            tenant_id=gate_spec.tenant_id,
            actor_user_id=gate_spec.actor_user_id,
            project_global_id=str(gate_spec.project_global_id),
            source_type=gate_spec.source_type.value,
            source_global_id=str(gate_spec.source_global_id),
            source_version=gate_spec.source_version,
            assignment_code=gate_spec.assignment_code,
            category=gate_spec.category.value,
            due_at=None,
            priority_scheme=None,
            priority_value=None,
            blocking=int(gate_spec.blocking),
            active=1,
            source_snapshot=repository_module._canonical_json(gate_snapshot),
            snapshot_hash=repository_module._sha256_json(gate_snapshot),
        )
        terminal_workspace = self.workspace()
        terminal_workspace["project"]["lifecycleState"] = "cancelled"
        with patch.object(
            repository_module,
            "_gate_workspace_for_principal",
            return_value=GateWorkspaceAccess(
                terminal_workspace,
                frozenset({"NPI API User"}),
            ),
        ):
            self.assertIsNone(resolver.resolve(gate_assignment, as_of=AS_OF))

    def test_cycle_hook_refreshes_owning_gate_projection(self):
        gate = self.gate_documents()
        cycle = fake_frappe.documents[("NPI Gate Review Cycle", str(CYCLE_ID))]
        with patch.object(
            repository_module,
            "refresh_gate_review_assignments",
            return_value=(GATE_ID,),
        ) as refresh:
            result = refresh_gate_review_assignments_for_cycle(
                cycle,
                store=MemoryStore(),
                tenant_id=TENANT_ID,
                indexed_at=AS_OF,
            )
        self.assertEqual(result, (GATE_ID,))
        self.assertIs(refresh.call_args.args[0], gate)

    def test_tenant_rebuild_pages_more_than_the_legacy_source_bound(self):
        source_names = tuple(f"{index:032x}" for index in range(10_001))
        query_sizes = []

        def get_all(doctype, *, filters, limit_page_length, **_values):
            query_sizes.append(limit_page_length)
            if doctype == "NPI Engineering Project":
                return []
            self.assertEqual(doctype, "NPI Domain Work Item")
            after = next(
                (
                    value[2]
                    for value in filters
                    if value[0] == "global_id" and value[1] == ">"
                ),
                None,
            )
            start = 0 if after is None else source_names.index(after) + 1
            return list(source_names[start : start + limit_page_length])

        store = MemoryStore()
        with (
            patch.object(fake_frappe, "get_all", side_effect=get_all),
            patch.object(
                repository_module,
                "refresh_domain_work_item_assignment",
                return_value=(),
            ) as refresh,
        ):
            result = rebuild_my_work_projection(
                store=store,
                tenant_id=TENANT_ID,
                indexed_at=AS_OF,
            )

        self.assertEqual(result.source_count, 10_001)
        self.assertEqual(result.assignment_count, 0)
        self.assertEqual(result.assignment_digest, hashlib.sha256().hexdigest())
        self.assertEqual(refresh.call_count, 10_001)
        self.assertEqual(set(query_sizes), {500})
        self.assertEqual(len(store.tenant_deactivations), 1)
        self.assertEqual(
            store.tenant_deactivations[0]["keep_assignment_keys"],
            frozenset(),
        )

    def test_tenant_deactivation_uses_advancing_bounded_pages(self):
        names = tuple(f"{index:032x}" for index in range(1_001))
        calls = []

        def get_all(_doctype, *, filters, limit_page_length, **_values):
            calls.append((filters, limit_page_length))
            after = next(
                (
                    value[2]
                    for value in filters
                    if value[0] == "global_id" and value[1] == ">"
                ),
                None,
            )
            start = 0 if after is None else names.index(after) + 1
            return list(names[start : start + limit_page_length])

        store = FrappeMyWorkAssignmentStore()
        with (
            patch.object(fake_frappe, "get_all", side_effect=get_all),
            patch.object(store, "_deactivate_names") as deactivate,
        ):
            store.deactivate_tenant_except(
                tenant_id=TENANT_ID,
                keep_assignment_keys=frozenset(),
                indexed_at=AS_OF,
            )

        self.assertEqual([call[1] for call in calls], [500, 500, 500])
        self.assertEqual(
            [len(call.args[0]) for call in deactivate.call_args_list],
            [500, 500, 1],
        )
        self.assertIn(
            ["global_id", ">", names[499]],
            calls[1][0],
        )
        self.assertIn(
            ["global_id", ">", names[999]],
            calls[2][0],
        )

    def test_bff_and_source_hooks_cover_live_my_work_consistency(self):
        root = Path("apps/npi_core/npi_core")
        bff = (root / "bff.py").read_text(encoding="utf-8")
        hooks = (root / "hooks.py").read_text(encoding="utf-8")
        self.assertIn(
            '("GET", "/api/npi/v1/me/work"): ' '"npi_core.my_work_api.get_my_work"',
            bff,
        )
        self.assertIn('"NPI Engineering Project": {', hooks)
        self.assertIn('"NPI Gate Review Cycle": {', hooks)
        self.assertIn('"NPI Project Member": {', hooks)
        self.assertIn(
            '"refresh_project_my_work_assignments"',
            hooks,
        )
        self.assertIn(
            '"refresh_gate_review_assignments_for_cycle"',
            hooks,
        )

    def test_frappe_store_sets_controlled_flag_only_around_write(self):
        source = self.domain_source()
        spec = repository_module._domain_projection_spec(
            source,
            self.project(),
        )
        self.assertIsNotNone(spec)
        store = FrappeMyWorkAssignmentStore()
        store.upsert(spec, indexed_at=AS_OF)
        self.assertEqual(len(fake_frappe.inserted), 1)
        self.assertFalse(
            hasattr(
                fake_frappe.flags,
                "npi_my_work_projection_write",
            )
        )


class MyWorkApiTests(unittest.TestCase):
    def test_direct_method_is_closed_by_the_exact_site_switch(self):
        calls = {}

        def domain_call(handler, **_options):
            calls["handler"] = True
            return handler()

        fake_frappe.conf["npi_p4_05_routes_disabled"] = True
        try:
            with (
                patch.object(
                    api_module,
                    "frappe_domain_call",
                    side_effect=domain_call,
                ),
                patch.object(
                    api_module,
                    "authenticated_user",
                ) as authenticated,
                patch.object(
                    api_module,
                    "_repository_factory",
                ) as factory,
            ):
                with self.assertRaises(
                    ProjectCollaborationRoutesDisabled
                ):
                    api_module.get_my_work(view="all")
        finally:
            fake_frappe.conf.pop("npi_p4_05_routes_disabled", None)

        self.assertTrue(calls["handler"])
        authenticated.assert_not_called()
        factory.assert_not_called()

    def test_get_is_current_actor_private_no_store_and_strictly_typed(self):
        calls = {}

        class Repository:
            def query(self, **values):
                calls["query"] = values
                return {
                    "asOf": "2026-07-25T12:00:00.000000Z",
                    "timeZone": "UTC",
                    "projectOptions": [],
                    "items": [],
                    "nextCursor": None,
                    "counts": {},
                }

        def domain_call(handler, **options):
            calls["options"] = options
            token = current_trace_id.set(TRACE_ID)
            try:
                return handler()
            finally:
                current_trace_id.reset(token)

        with (
            patch.object(
                api_module,
                "frappe_domain_call",
                side_effect=domain_call,
            ),
            patch.object(
                api_module,
                "response_request_id",
                return_value=REQUEST_ID,
            ),
            patch.object(
                api_module,
                "authenticated_user",
                return_value=ACTOR,
            ),
            patch.object(
                api_module,
                "authenticated_principal",
                return_value=principal(),
            ),
            patch.object(
                api_module,
                "reject_unexpected_request_fields",
            ) as reject,
            patch.object(
                api_module,
                "_repository_factory",
                return_value=Repository(),
            ) as factory,
        ):
            response = api_module.get_my_work(
                view="blockers",
                projectId=str(PROJECT_ID),
                priorityScheme="domain_severity",
                priorityValue="high",
                search="  housing  ",
                cursor=None,
                limit="25",
            )
        self.assertEqual(response["items"], [])
        reject.assert_called_once_with(
            api_module._QUERY_FIELDS,
            {},
        )
        factory.assert_called_once_with(
            principal=principal(),
            request_id=REQUEST_ID,
            trace_id=TRACE_ID,
        )
        self.assertIs(calls["query"]["view"], MyWorkView.BLOCKERS)
        self.assertEqual(calls["query"]["project_global_id"], PROJECT_ID)
        self.assertEqual(
            calls["query"]["priority"],
            MyWorkPriority(
                MyWorkPriorityScheme.DOMAIN_SEVERITY,
                "high",
            ),
        )
        self.assertEqual(calls["query"]["search"], "housing")
        self.assertEqual(calls["query"]["limit"], 25)
        self.assertEqual(
            calls["options"]["cache_control"],
            "private, no-store",
        )
        self.assertEqual(
            calls["options"]["response_headers"],
            {"X-Request-ID": REQUEST_ID},
        )

    def test_api_denies_external_actor_before_filter_resolution(self):
        external = Principal(
            user_id="external@example.invalid",
            roles=frozenset({"NPI API User"}),
            is_external=True,
            tenant_id=TENANT_ID,
        )

        def domain_call(handler, **_options):
            return handler()

        with (
            patch.object(
                api_module,
                "frappe_domain_call",
                side_effect=domain_call,
            ),
            patch.object(
                api_module,
                "response_request_id",
                return_value=REQUEST_ID,
            ),
            patch.object(
                api_module,
                "authenticated_user",
                return_value=external.user_id,
            ),
            patch.object(
                api_module,
                "authenticated_principal",
                return_value=external,
            ),
            patch.object(
                api_module,
                "reject_unexpected_request_fields",
            ) as reject,
            patch.object(api_module, "_repository_factory") as factory,
        ):
            with self.assertRaises(PermissionDenied):
                api_module.get_my_work(
                    view="not-a-view",
                    projectId="not-a-project-id",
                    cursor="not a cursor",
                    unexpected="not-resolved",
                )

        reject.assert_not_called()
        factory.assert_not_called()

    def test_api_rejects_unclosed_views_priority_pairs_and_limits(self):
        for kwargs, path in (
            ({"view": "unknown"}, "view"),
            (
                {
                    "view": "all",
                    "priorityScheme": "domain_severity",
                },
                "priorityScheme",
            ),
            ({"view": "all", "limit": "101"}, "limit"),
            ({"view": "all", "cursor": "not a cursor"}, "cursor"),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(RequestValidationFailed) as problem:
                    if path == "view":
                        api_module._view(kwargs["view"])
                    elif path == "priorityScheme":
                        api_module._priority(
                            kwargs.get("priorityScheme"),
                            kwargs.get("priorityValue"),
                        )
                    elif path == "limit":
                        api_module._limit(kwargs["limit"])
                    else:
                        api_module._optional_cursor(kwargs["cursor"])
                self.assertEqual(
                    problem.exception.field_errors[0]["path"],
                    path,
                )

    def test_api_error_literals_reuse_complete_frappe_catalog_entries(self):
        sources = (
            "Select a supported value.",
            "Enter a valid global ID.",
            "Enter a valid value.",
            "Enter a valid cursor.",
            "Enter a positive integer.",
        )
        root = Path("apps/npi_core/npi_core/translations")
        for locale in ("zh", "zh-TW"):
            catalog = (root / f"{locale}.csv").read_text(encoding="utf-8")
            for source in sources:
                with self.subTest(locale=locale, source=source):
                    self.assertIn(f"{source},", catalog)


if __name__ == "__main__":
    unittest.main()
