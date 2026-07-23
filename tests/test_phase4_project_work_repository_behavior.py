from __future__ import annotations

import base64
import hashlib
import importlib
import json
import sys
import types
import unittest
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest import mock
from uuid import UUID, uuid4


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = UUID("873f818c-cc37-48d7-a446-c32f8f92f330")
OTHER_PROJECT_ID = UUID("6410118d-01e9-408b-8b14-da4461da95db")
POLICY_ID = UUID("edebac00-2520-4327-8b39-0722c97396cc")
WBS_ID = UUID("4d94688f-b3bb-43c1-839a-69cd0f280791")
STAGE_ID = UUID("8e497b7e-5090-4eb6-b118-25ecaee44390")
RELATED_ID = UUID("68f9e45c-22c8-4981-a8b7-4643729e7eae")
TENANT_ID = "TENANT-A"


class AttrDoc(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def set(self, name: str, value: Any) -> None:
        self[name] = value

    def insert(self):
        self.inserted = True
        if self.get("doctype") == "NPI Domain Work Item":
            timestamp = datetime(2026, 7, 23, 13, 0, tzinfo=UTC)
            self.setdefault("creation", timestamp)
            self.setdefault("modified", timestamp)
        return self

    def save(self):
        self.saved = True
        return self

    def is_new(self) -> bool:
        return True


class StubDatabase:
    def __init__(self) -> None:
        self.count_value = 0

    def count(self, _doctype: str, *, filters: dict[str, object]) -> int:
        self.last_count_filters = filters
        return self.count_value

    def get_value(
        self,
        doctype: str,
        _name: object,
        fieldname: object,
        **_kwargs: object,
    ) -> object:
        if doctype == "User" and fieldname == "enabled":
            return 1
        return None

    def rollback(self) -> None:
        return None


class Phase4ProjectWorkRepositoryBehaviorTest(unittest.TestCase):
    MODULE_NAMES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        "frappe.utils.password",
        "npi_core.project_work.frappe_repository",
        "npi_core.project_work.frappe_validation",
        (
            "npi_core.npi_core.doctype.npi_wbs_plan_baseline."
            "npi_wbs_plan_baseline"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULE_NAMES
        }
        for name in self.MODULE_NAMES:
            sys.modules.pop(name, None)

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.db = StubDatabase()
        self.frappe.DoesNotExistError = type(
            "DoesNotExistError",
            (Exception,),
            {},
        )
        self.frappe.UniqueValidationError = type(
            "UniqueValidationError",
            (Exception,),
            {},
        )
        self.frappe.DuplicateEntryError = type(
            "DuplicateEntryError",
            (Exception,),
            {},
        )
        self.frappe.ValidationError = type(
            "ValidationError",
            (Exception,),
            {},
        )
        self.frappe.PermissionError = type(
            "PermissionError",
            (Exception,),
            {},
        )

        def throw(message: str, exception_type: type[Exception]) -> None:
            raise exception_type(message)

        self.frappe.throw = throw
        self.frappe.get_doc = lambda *_args, **_kwargs: None
        self.frappe.get_all = lambda *_args, **_kwargs: []

        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        utils = types.ModuleType("frappe.utils")
        password = types.ModuleType("frappe.utils.password")
        self.site_encryption_key = base64.urlsafe_b64encode(
            bytes(range(32))
        ).decode("ascii")
        self.site_configuration = AttrDoc(
            encryption_key=self.site_encryption_key
        )
        self.frappe.local = types.SimpleNamespace(
            conf=self.site_configuration
        )
        self.frappe.conf = self.site_configuration
        password.get_encryption_key = mock.Mock(
            side_effect=AssertionError(
                "Cursor signing must not auto-provision Site configuration."
            )
        )
        document.Document = AttrDoc
        model.document = document
        self.frappe.model = model
        self.frappe.utils = utils
        utils.password = password
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document
        sys.modules["frappe.utils"] = utils
        sys.modules["frappe.utils.password"] = password
        self.password = password

        self.repository_module = importlib.import_module(
            "npi_core.project_work.frappe_repository"
        )
        self.domain = importlib.import_module("npi_core.project_work.domain")
        self.policy = self._policy()

    def tearDown(self) -> None:
        for name in self.MODULE_NAMES:
            sys.modules.pop(name, None)
            previous = self.saved_modules[name]
            if previous is not None:
                sys.modules[name] = previous

    def _policy(self):
        LifecycleDefinition = self.domain.LifecycleDefinition
        LifecycleState = self.domain.LifecycleState
        KindLifecycle = self.domain.KindLifecycle
        DomainWorkItemKind = self.domain.DomainWorkItemKind

        def lifecycle(
            initial: str,
            initial_label: str,
            terminal: str,
        ):
            return LifecycleDefinition(
                initial,
                (
                    LifecycleState(initial, initial_label),
                    LifecycleState(terminal, "Draft", terminal=True),
                ),
            )

        draft = self.domain.ProjectWorkPolicyVersion.create_draft(
            policy_global_id=POLICY_ID,
            policy_key="repository_behavior",
            policy_version=1,
            title="Repository behavior policy",
            role_keys=("project_manager",),
            wbs_lifecycle=lifecycle("planned", "Not started", "completed"),
            work_item_lifecycles=(
                KindLifecycle(
                    DomainWorkItemKind.RISK,
                    lifecycle("identified", "Identified", "retired"),
                ),
                KindLifecycle(
                    DomainWorkItemKind.ISSUE,
                    lifecycle("open", "Open", "closed"),
                ),
                KindLifecycle(
                    DomainWorkItemKind.ACTION,
                    lifecycle("assigned", "Draft", "closed"),
                ),
                KindLifecycle(
                    DomainWorkItemKind.DECISION_REQUEST,
                    lifecycle("requested", "Requested", "decided"),
                ),
            ),
        )
        return draft.publish(expected_version=1).snapshot()

    def _policy_mapping(self) -> dict[str, object]:
        return {
            "ref": {
                "globalId": str(self.policy.policy_global_id),
                "version": self.policy.policy_version,
                "snapshotHash": self.policy.snapshot_hash,
            },
            "snapshot": self.policy,
        }

    def _project(self) -> AttrDoc:
        return AttrDoc(
            global_id=str(PROJECT_ID),
            tenant_id=TENANT_ID,
            optimistic_version=4,
            work_plan_revision=2,
            work_policy_global_id=str(self.policy.policy_global_id),
            work_policy_version=self.policy.policy_version,
            work_policy_snapshot_hash=self.policy.snapshot_hash,
            active_plan_baseline_global_id=None,
        )

    def _wbs_document(
        self,
        *,
        planned_start: date = date(2026, 8, 1),
        planned_end: date = date(2026, 8, 5),
        critical: bool = False,
    ) -> AttrDoc:
        return AttrDoc(
            global_id=str(WBS_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            work_policy_global_id=str(self.policy.policy_global_id),
            work_policy_version=self.policy.policy_version,
            work_policy_snapshot_hash=self.policy.snapshot_hash,
            wbs_code="1",
            title="Release tooling",
            planned_start=planned_start,
            planned_end=planned_end,
            actual_start=None,
            actual_end=None,
            milestone=False,
            status_key="planned",
            status_label_source="Not started",
            progress_percent=0,
            critical_task=critical,
            plan_revision=2,
            parent_global_id=None,
            owner_role_assignment_global_id=None,
            optimistic_version=1,
        )

    def _related_document(
        self,
        *,
        project_id: UUID = PROJECT_ID,
        tenant_id: str = TENANT_ID,
    ) -> AttrDoc:
        return AttrDoc(
            global_id=str(RELATED_ID),
            tenant_id=tenant_id,
            project_global_id=str(project_id),
            kind="risk",
            title="Existing risk",
            detail=None,
            stage_global_id=None,
            wbs_item_global_id=None,
            owner_user_id="owner@example.invalid",
            due_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
            severity="medium",
            blocking=False,
            state_key="identified",
            state_label_source="Identified",
            state_terminal=False,
            work_policy_global_id=str(self.policy.policy_global_id),
            work_policy_version=self.policy.policy_version,
            work_policy_snapshot_hash=self.policy.snapshot_hash,
            relations=[],
            evidence_references=[],
            optimistic_version=1,
        )

    def _work_item_document(
        self,
        *,
        global_id: UUID,
        due_at: datetime,
        terminal: bool,
        title: str,
    ) -> AttrDoc:
        timestamp = datetime(2026, 7, 23, 13, 0, tzinfo=UTC)
        return AttrDoc(
            global_id=str(global_id),
            project_global_id=str(PROJECT_ID),
            kind="action",
            title=title,
            detail=None,
            stage_global_id=str(STAGE_ID),
            wbs_item_global_id=None,
            owner_user_id="owner@example.invalid",
            due_at=due_at,
            severity="medium",
            blocking=False,
            state_key="closed" if terminal else "assigned",
            state_label_source="Draft",
            state_terminal=terminal,
            work_policy_global_id=str(self.policy.policy_global_id),
            work_policy_version=self.policy.policy_version,
            work_policy_snapshot_hash=self.policy.snapshot_hash,
            relations=[],
            optimistic_version=1,
            creation=timestamp,
            modified=timestamp,
        )

    def _repository(self, project: AttrDoc):
        principal = self.repository_module.Principal(
            user_id="Administrator",
            roles=frozenset(("System Manager",)),
            tenant_id=TENANT_ID,
        )
        repository = self.repository_module.FrappeProjectWorkRepository(
            principal=principal,
            request_id="a0dce453-3262-4d65-bcda-7a3090f3b1c2",
            trace_id="trace-repository-behavior",
        )
        audits: list[dict[str, object]] = []
        repository._authorized_project = lambda *_args: project
        repository._locked_authorized_project = lambda *_args: project
        repository._idempotency_replay = lambda *_args: None
        repository._load_policy = lambda _reference: self._policy_mapping()
        repository._require_current_policy = lambda *_args: None
        repository._insert_idempotency = (
            lambda *_args: types.SimpleNamespace()
        )
        repository._seal_idempotency = lambda *_args: None
        repository._advance_project = lambda *_args: None
        repository._append_audit = lambda **values: audits.append(values)
        return repository, audits

    def test_baseline_command_uses_domain_factory_and_canonical_snapshot(
        self,
    ) -> None:
        project = self._project()
        repository, audits = self._repository(project)
        wbs = self._wbs_document()
        inserted: list[AttrDoc] = []

        def get_doc(value: object, *_args: object) -> AttrDoc:
            self.assertIsInstance(value, dict)
            document = AttrDoc(value)
            inserted.append(document)
            return document

        def project_documents(
            doctype: str,
            _filters: object,
            *,
            order_by: str,
        ) -> tuple[AttrDoc, ...]:
            self.assertTrue(order_by)
            if doctype == "NPI WBS Item":
                return (wbs,)
            if doctype in {
                "NPI WBS Plan Baseline",
                "NPI WBS Dependency",
                "NPI Project Role Assignment",
            }:
                return ()
            raise AssertionError(doctype)

        self.frappe.get_doc = get_doc
        original_factory = self.repository_module.build_wbs_baseline
        with (
            mock.patch.object(
                self.repository_module,
                "_project_documents",
                side_effect=project_documents,
            ),
            mock.patch.object(
                self.repository_module,
                "build_wbs_baseline",
                wraps=original_factory,
            ) as factory,
        ):
            outcome = repository.capture_plan_baseline(
                PROJECT_ID,
                idempotency_key="repository-baseline-0001",
                expected_project_version=4,
                work_policy_ref=self._policy_mapping()["ref"],
                label="  Design release  ",
            )

        self.assertIsNotNone(outcome)
        self.assertEqual(factory.call_count, 1)
        baseline = next(
            value
            for value in inserted
            if value["doctype"] == "NPI WBS Plan Baseline"
        )
        expected_snapshot = {
            "items": [
                {
                    "wbsItemId": str(WBS_ID),
                    "plannedStart": "2026-08-01",
                    "plannedFinish": "2026-08-05",
                    "critical": False,
                }
            ]
        }
        self.assertEqual(baseline.snapshot, expected_snapshot)
        expected_hash = hashlib.sha256(
            json.dumps(
                expected_snapshot,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(baseline.snapshot_hash, expected_hash)
        self.assertEqual(baseline.label, "Design release")
        self.assertEqual(baseline.captured_by, "Administrator")
        self.assertIsNone(baseline.captured_at.tzinfo)
        self.assertEqual(outcome.response["capturedBy"], "Administrator")
        self.assertTrue(outcome.response["capturedAt"].endswith("Z"))
        self.assertEqual(audits[0]["result"], "created")

        current_plan = self.repository_module._domain_wbs_plan_from_documents(
            project,
            self.policy,
            item_documents=(
                self._wbs_document(
                    planned_start=date(2026, 8, 3),
                    planned_end=date(2026, 8, 9),
                    critical=True,
                ),
            ),
            dependency_documents=(),
            role_documents=(),
            project_version=5,
        )
        original_comparator = (
            self.repository_module.compare_domain_wbs_baseline
        )
        with mock.patch.object(
            self.repository_module,
            "compare_domain_wbs_baseline",
            wraps=original_comparator,
        ) as comparator:
            comparison = self.repository_module._baseline_comparison(
                baseline,
                current_plan,
            )
        self.assertEqual(comparator.call_count, 1)
        self.assertEqual(comparison["currentProjectVersion"], 5)
        self.assertEqual(
            comparison["items"][0],
            {
                "wbsItemId": str(WBS_ID),
                "baselinePlannedStart": "2026-08-01",
                "baselinePlannedFinish": "2026-08-05",
                "currentPlannedStart": "2026-08-03",
                "currentPlannedFinish": "2026-08-09",
                "startVarianceDays": 2,
                "finishVarianceDays": 4,
                "critical": True,
            },
        )

    def test_iterative_graph_guard_handles_contract_bounds(self) -> None:
        item_ids = tuple(UUID(int=100_000 + index) for index in range(2_000))
        parent_edges = {
            item_id: (
                (item_ids[index + 1],)
                if index + 1 < len(item_ids)
                else ()
            )
            for index, item_id in enumerate(item_ids)
        }

        self.repository_module._reject_graph_cycle(
            parent_edges,
            "items.parentId",
        )

        parent_edges[item_ids[-1]] = (item_ids[-2],)
        with self.assertRaises(
            self.repository_module.RequestValidationFailed
        ) as parent_cycle:
            self.repository_module._reject_graph_cycle(
                parent_edges,
                "items.parentId",
            )
        self.assertEqual(
            parent_cycle.exception.field_errors,
            [
                {
                    "path": "items.parentId",
                    "message": "The WBS graph cannot contain a cycle.",
                }
            ],
        )

        dependency_edges: dict[UUID, list[UUID]] = {
            item_id: [] for item_id in item_ids
        }
        pairs = [
            (item_ids[index], item_ids[index + 1])
            for index in range(len(item_ids) - 1)
        ]
        distance = 2
        while len(pairs) < 4_999:
            for index in range(len(item_ids) - distance):
                pairs.append((item_ids[index], item_ids[index + distance]))
                if len(pairs) == 4_999:
                    break
            distance += 1
        pairs.append((item_ids[-1], item_ids[0]))
        for predecessor_id, successor_id in pairs:
            dependency_edges[predecessor_id].append(successor_id)

        with self.assertRaises(
            self.repository_module.RequestValidationFailed
        ) as dependency_cycle:
            self.repository_module._reject_graph_cycle(
                dependency_edges,
                "dependencies",
            )
        self.assertEqual(len(pairs), 5_000)
        self.assertEqual(
            dependency_cycle.exception.field_errors,
            [
                {
                    "path": "dependencies",
                    "message": "The WBS graph cannot contain a cycle.",
                }
            ],
        )

    def test_work_item_command_uses_domain_factory_and_policy_initial_state(
        self,
    ) -> None:
        project = self._project()
        repository, audits = self._repository(project)
        related = self._related_document()
        stage = AttrDoc(project_global_id=str(PROJECT_ID))
        wbs = AttrDoc(
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
        )
        inserted: list[AttrDoc] = []

        def optional_doc(doctype: str, name: str):
            values = {
                ("NPI Gate Shell", str(STAGE_ID)): stage,
                ("NPI WBS Item", str(WBS_ID)): wbs,
                ("NPI Domain Work Item", str(RELATED_ID)): related,
            }
            return values.get((doctype, name))

        def get_doc(value: object, *_args: object) -> AttrDoc:
            self.assertIsInstance(value, dict)
            document = AttrDoc(value)
            inserted.append(document)
            return document

        self.frappe.get_doc = get_doc
        original_factory = self.repository_module.build_domain_work_item
        with (
            mock.patch.object(
                self.repository_module,
                "_optional_doc",
                side_effect=optional_doc,
            ),
            mock.patch.object(
                self.repository_module,
                "build_domain_work_item",
                wraps=original_factory,
            ) as factory,
        ):
            outcome = repository.create_domain_work_item(
                PROJECT_ID,
                idempotency_key="repository-work-item-0001",
                expected_project_version=4,
                work_policy_ref=self._policy_mapping()["ref"],
                kind="action",
                title="  Confirm steel release  ",
                detail="",
                context={
                    "stageId": str(STAGE_ID),
                    "wbsItemId": str(WBS_ID),
                },
                owner_user_id="owner@example.invalid",
                due_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
                severity="high",
                blocking=True,
                related_work_item_ids=(RELATED_ID,),
            )

        self.assertIsNotNone(outcome)
        self.assertEqual(factory.call_count, 1)
        item = next(
            value
            for value in inserted
            if value["doctype"] == "NPI Domain Work Item"
        )
        self.assertEqual(item.title, "Confirm steel release")
        self.assertIsNone(item.detail)
        self.assertEqual(item.state_key, "assigned")
        self.assertEqual(item.state_label_source, "Draft")
        self.assertEqual(item.relations, [str(RELATED_ID)])
        self.assertEqual(
            item.due_at,
            datetime(2026, 8, 7, 12, 0),
        )
        self.assertIsNone(item.due_at.tzinfo)
        self.assertEqual(
            outcome.response["dueAt"],
            "2026-08-07T12:00:00Z",
        )
        self.assertEqual(outcome.response["stateLabelSource"], "Draft")
        self.assertEqual(audits[0]["result"], "created")

    def test_cross_project_or_tenant_context_and_relation_fail_before_factory(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        original_factory = self.repository_module.build_domain_work_item

        cases = (
            (
                {"stageId": str(STAGE_ID)},
                (),
                "context.stageId",
                {
                    ("NPI Gate Shell", str(STAGE_ID)): AttrDoc(
                        project_global_id=str(OTHER_PROJECT_ID)
                    )
                },
            ),
            (
                {},
                (RELATED_ID,),
                "relatedWorkItemIds[0]",
                {
                    ("NPI Domain Work Item", str(RELATED_ID)): (
                        self._related_document(project_id=OTHER_PROJECT_ID)
                    )
                },
            ),
            (
                {"wbsItemId": str(WBS_ID)},
                (),
                "context.wbsItemId",
                {
                    ("NPI WBS Item", str(WBS_ID)): AttrDoc(
                        tenant_id="TENANT-B",
                        project_global_id=str(PROJECT_ID),
                    )
                },
            ),
            (
                {},
                (RELATED_ID,),
                "relatedWorkItemIds[0]",
                {
                    ("NPI Domain Work Item", str(RELATED_ID)): (
                        self._related_document(tenant_id="TENANT-B")
                    )
                },
            ),
        )
        for context, related_ids, expected_path, documents in cases:
            with self.subTest(path=expected_path):
                with (
                    mock.patch.object(
                        self.repository_module,
                        "_optional_doc",
                        side_effect=lambda doctype, name: documents.get(
                            (doctype, name)
                        ),
                    ),
                    mock.patch.object(
                        self.repository_module,
                        "build_domain_work_item",
                        wraps=original_factory,
                    ) as factory,
                ):
                    with self.assertRaises(
                        self.repository_module.RequestValidationFailed
                    ) as caught:
                        repository.create_domain_work_item(
                            PROJECT_ID,
                            idempotency_key="repository-cross-project-0001",
                            expected_project_version=4,
                            work_policy_ref=self._policy_mapping()["ref"],
                            kind="risk",
                            title="Cross-project reference",
                            detail=None,
                            context=context,
                            owner_user_id="owner@example.invalid",
                            due_at=datetime(
                                2026,
                                8,
                                7,
                                12,
                                0,
                                tzinfo=UTC,
                            ),
                            severity="medium",
                            blocking=False,
                            related_work_item_ids=related_ids,
                        )
                self.assertEqual(factory.call_count, 0)
                self.assertEqual(
                    caught.exception.field_errors[0]["path"],
                    expected_path,
                )

    def test_existing_identity_and_raci_context_reject_wrong_tenant(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        wrong_tenant = AttrDoc(
            tenant_id="TENANT-B",
            project_global_id=str(PROJECT_ID),
        )

        with mock.patch.object(
            self.repository_module,
            "_optional_doc",
            return_value=wrong_tenant,
        ):
            with self.assertRaises(
                self.repository_module.RequestValidationFailed
            ) as identity_error:
                repository._require_same_project_identity(
                    "NPI WBS Item",
                    WBS_ID,
                    PROJECT_ID,
                    "items[0].globalId",
                    tenant_id=TENANT_ID,
                )
            with self.assertRaises(
                self.repository_module.RequestValidationFailed
            ) as context_error:
                repository._validate_raci_context(
                    PROJECT_ID,
                    TENANT_ID,
                    "wbs_item",
                    WBS_ID,
                    "raciAssignments[0].contextId",
                )

        self.assertEqual(
            identity_error.exception.field_errors[0]["path"],
            "items[0].globalId",
        )
        self.assertEqual(
            context_error.exception.field_errors[0]["path"],
            "raciAssignments[0].contextId",
        )

    def test_disabled_existing_member_can_only_be_non_expansively_ended(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        member_id = UUID("99000000-0000-4000-8000-000000000001")
        member = AttrDoc(
            global_id=str(member_id),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            user_id="disabled@example.invalid",
            effective_from=date(2026, 7, 1),
            effective_to=None,
        )

        def project_documents(
            doctype: str,
            _filters: object,
            *,
            order_by: str,
        ) -> tuple[AttrDoc, ...]:
            self.assertTrue(order_by)
            return (member,) if doctype == "NPI Project Member" else ()

        self.frappe.db.get_value = mock.Mock(return_value=0)
        policy = {
            **self._policy_mapping(),
            "role_keys": frozenset(),
        }
        closing_member = {
            "globalId": str(member_id),
            "userId": "disabled@example.invalid",
            "effectiveFrom": "2026-07-01",
            "effectiveTo": "2026-07-23",
        }
        with (
            mock.patch.object(
                self.repository_module,
                "_project_documents",
                side_effect=project_documents,
            ),
            mock.patch.object(
                self.repository_module,
                "_optional_doc",
                return_value=member,
            ),
        ):
            prepared = repository._prepare_team(
                project,
                policy,
                members=(closing_member,),
                role_assignments=(),
                substitutions=(),
                raci_assignments=(),
            )
            with self.assertRaises(
                self.repository_module.RequestValidationFailed
            ) as active_error:
                repository._prepare_team(
                    project,
                    policy,
                    members=(
                        {
                            **closing_member,
                            "effectiveTo": None,
                        },
                    ),
                    role_assignments=(),
                    substitutions=(),
                    raci_assignments=(),
                )

        self.assertEqual(
            prepared["members"][0]["effective_to"],
            date(2026, 7, 23),
        )
        self.assertEqual(
            active_error.exception.field_errors[0]["path"],
            "members[0].userId",
        )

    def test_work_item_limit_fails_before_domain_factory_and_insert(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        self.frappe.db.count_value = 10000
        self.frappe.get_doc = mock.Mock(
            side_effect=AssertionError("No document may be inserted.")
        )
        with mock.patch.object(
            repository,
            "_prepare_domain_work_item",
        ) as factory:
            with self.assertRaises(
                self.repository_module.RequestValidationFailed
            ) as caught:
                repository.create_domain_work_item(
                    PROJECT_ID,
                    idempotency_key="repository-work-item-limit-0001",
                    expected_project_version=4,
                    work_policy_ref=self._policy_mapping()["ref"],
                    kind="risk",
                    title="Capacity overflow",
                    detail=None,
                    context={},
                    owner_user_id="owner@example.invalid",
                    due_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
                    severity="medium",
                    blocking=False,
                    related_work_item_ids=(),
                )
        factory.assert_not_called()
        self.frappe.get_doc.assert_not_called()
        self.assertEqual(caught.exception.field_errors[0]["path"], "projectId")

    def test_non_overdue_query_stable_merges_bounded_storage_pages(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        terminal_early = self._work_item_document(
            global_id=UUID("10000000-0000-4000-8000-000000000001"),
            due_at=datetime(2098, 1, 1, 12, 0, tzinfo=UTC),
            terminal=True,
            title="Closed early",
        )
        active_next = self._work_item_document(
            global_id=UUID("20000000-0000-4000-8000-000000000001"),
            due_at=datetime(
                2098,
                1,
                1,
                12,
                0,
                0,
                500_000,
                tzinfo=UTC,
            ),
            terminal=False,
            title="Active next",
        )
        terminal_later = self._work_item_document(
            global_id=UUID("30000000-0000-4000-8000-000000000001"),
            due_at=datetime(2099, 1, 1, 12, 0, tzinfo=UTC),
            terminal=True,
            title="Closed later",
        )
        active_later = self._work_item_document(
            global_id=UUID("40000000-0000-4000-8000-000000000001"),
            due_at=datetime(2100, 1, 1, 12, 0, tzinfo=UTC),
            terminal=False,
            title="Active later",
        )
        queries: list[dict[str, object]] = []

        def get_all(
            doctype: str,
            **values: object,
        ) -> list[AttrDoc]:
            self.assertEqual(doctype, "NPI Domain Work Item")
            queries.append(values)
            filters = values["filters"]
            self.assertIsInstance(filters, list)
            terminal_filter = next(
                row
                for row in filters
                if row[0] == "state_terminal"
            )
            if terminal_filter[2] == 1:
                return [terminal_early, terminal_later]
            return [active_next, active_later]

        self.frappe.get_all = get_all
        self.frappe.get_doc = mock.Mock(
            side_effect=AssertionError(
                "Paginated queries must not load each full document."
            )
        )
        with mock.patch.object(
            self.repository_module,
            "_project_documents",
            side_effect=AssertionError(
                "Paginated queries must not load the full Project collection."
            ),
        ):
            response = repository.list_domain_work_items(
                PROJECT_ID,
                stage_id=STAGE_ID,
                owner_user_id="owner@example.invalid",
                overdue=False,
                kind="action",
                cursor=None,
                limit=2,
            )

        self.assertIsNotNone(response)
        self.assertEqual(
            [item["globalId"] for item in response["items"]],
            [str(terminal_early.global_id), str(active_next.global_id)],
        )
        self.assertTrue(
            all(item["overdue"] is False for item in response["items"])
        )
        self.assertIsNotNone(response["nextCursor"])
        self.assertEqual(len(queries), 2)
        for query in queries:
            self.assertEqual(query["limit_page_length"], 3)
            self.assertEqual(
                query["order_by"],
                "due_at asc, global_id asc",
            )
            self.assertNotIn("pluck", query)
            self.assertIn("due_at", query["fields"])
            self.assertIn("global_id", query["fields"])
            filters = query["filters"]
            self.assertIn(["tenant_id", "=", TENANT_ID], filters)
            self.assertIn(
                ["project_global_id", "=", str(PROJECT_ID)],
                filters,
            )
            self.assertIn(
                ["stage_global_id", "=", str(STAGE_ID)],
                filters,
            )
            self.assertIn(
                ["owner_user_id", "=", "owner@example.invalid"],
                filters,
            )
            self.assertIn(["kind", "=", "action"], filters)
        active_query = next(
            query
            for query in queries
            if ["state_terminal", "=", 0] in query["filters"]
        )
        self.assertTrue(
            any(
                row[0] == "due_at" and row[1] == ">="
                for row in active_query["filters"]
            )
        )
        self.frappe.get_doc.assert_not_called()

    def test_overdue_cursor_is_pushed_into_two_bounded_storage_queries(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        cursor_global_id = UUID(
            "50000000-0000-4000-8000-000000000001"
        )
        same_due_at = self._work_item_document(
            global_id=UUID("60000000-0000-4000-8000-000000000001"),
            due_at=datetime(2020, 1, 1, 12, 0, tzinfo=UTC),
            terminal=False,
            title="Same due date",
        )
        later_due_at = self._work_item_document(
            global_id=UUID("70000000-0000-4000-8000-000000000001"),
            due_at=datetime(2020, 1, 2, 12, 0, tzinfo=UTC),
            terminal=False,
            title="Later due date",
        )
        as_of = datetime(2026, 7, 23, 13, 0, tzinfo=UTC)
        query_fingerprint = (
            self.repository_module._domain_work_item_query_fingerprint(
                project_id=PROJECT_ID,
                stage_id=None,
                owner_user_id=None,
                overdue=True,
                kind=None,
            )
        )
        cursor = self.repository_module._encode_cursor(
            ("2020-01-01T12:00:00Z", str(cursor_global_id)),
            as_of=as_of,
            query_fingerprint=query_fingerprint,
        )
        queries: list[dict[str, object]] = []

        def get_all(
            _doctype: str,
            **values: object,
        ) -> list[AttrDoc]:
            queries.append(values)
            filters = values["filters"]
            if any(
                row[0] == "due_at" and row[1] == "="
                for row in filters
            ):
                return [same_due_at]
            return [later_due_at]

        self.frappe.get_all = get_all
        self.frappe.get_doc = mock.Mock(
            side_effect=AssertionError(
                "Paginated queries must not load each full document."
            )
        )
        response = repository.list_domain_work_items(
            PROJECT_ID,
            stage_id=None,
            owner_user_id=None,
            overdue=True,
            kind=None,
            cursor=cursor,
            limit=1,
        )

        self.assertIsNotNone(response)
        self.assertEqual(
            [item["globalId"] for item in response["items"]],
            [str(same_due_at.global_id)],
        )
        self.assertTrue(response["items"][0]["overdue"])
        self.assertIsNotNone(response["nextCursor"])
        self.assertEqual(len(queries), 2)
        for query in queries:
            self.assertEqual(query["limit_page_length"], 2)
            filters = query["filters"]
            self.assertIn(["state_terminal", "=", 0], filters)
            self.assertTrue(
                any(
                    row[0] == "due_at" and row[1] == "<"
                    for row in filters
                )
            )
        same_due_query = next(
            query
            for query in queries
            if any(
                row[0] == "due_at" and row[1] == "="
                for row in query["filters"]
            )
        )
        self.assertIn(
            ["global_id", ">", str(cursor_global_id)],
            same_due_query["filters"],
        )
        later_due_query = next(
            query
            for query in queries
            if any(
                row[0] == "due_at" and row[1] == ">"
                for row in query["filters"]
            )
        )
        self.assertNotIn(
            ["global_id", ">", str(cursor_global_id)],
            later_due_query["filters"],
        )
        for query in queries:
            self.assertIn(
                ["due_at", "<", as_of.replace(tzinfo=None)],
                query["filters"],
            )
        self.frappe.get_doc.assert_not_called()

    def test_cursor_as_of_stays_fixed_across_due_boundary(self) -> None:
        as_of = datetime(2026, 7, 23, 13, 0, tzinfo=UTC)
        after_boundary = as_of + timedelta(minutes=1)

        for overdue in (True, False):
            with self.subTest(overdue=overdue):
                project = self._project()
                repository, _audits = self._repository(project)
                if overdue:
                    first_due_at = as_of - timedelta(minutes=2)
                    second_due_at = as_of - timedelta(minutes=1)
                    threshold_operator = "<"
                else:
                    first_due_at = as_of + timedelta(seconds=10)
                    second_due_at = as_of + timedelta(seconds=30)
                    threshold_operator = ">="
                first = self._work_item_document(
                    global_id=UUID(
                        "81000000-0000-4000-8000-000000000001"
                    ),
                    due_at=first_due_at,
                    terminal=False,
                    title="First page item",
                )
                second = self._work_item_document(
                    global_id=UUID(
                        "82000000-0000-4000-8000-000000000001"
                    ),
                    due_at=second_due_at,
                    terminal=False,
                    title="Boundary item",
                )
                queries: list[dict[str, object]] = []

                def get_all(
                    _doctype: str,
                    **values: object,
                ) -> list[AttrDoc]:
                    queries.append(values)
                    filters = values["filters"]
                    if ["state_terminal", "=", 1] in filters:
                        return []
                    if any(
                        row[0] == "due_at" and row[1] == "="
                        for row in filters
                    ):
                        return []
                    if any(
                        row[0] == "due_at" and row[1] == ">"
                        for row in filters
                    ):
                        return [second]
                    return [first, second]

                class AdvancingDateTime(datetime):
                    moments = [as_of, after_boundary]

                    @classmethod
                    def now(cls, timezone=None):
                        moment = cls.moments.pop(0)
                        if timezone is None:
                            return moment.replace(tzinfo=None)
                        return moment.astimezone(timezone)

                self.frappe.get_all = get_all
                self.frappe.get_doc = mock.Mock(
                    side_effect=AssertionError(
                        "Paginated queries must not load full documents."
                    )
                )
                with mock.patch.object(
                    self.repository_module,
                    "datetime",
                    AdvancingDateTime,
                ):
                    first_page = repository.list_domain_work_items(
                        PROJECT_ID,
                        stage_id=STAGE_ID,
                        owner_user_id="owner@example.invalid",
                        overdue=overdue,
                        kind="action",
                        cursor=None,
                        limit=1,
                    )
                    self.assertIsNotNone(first_page)
                    cursor = first_page["nextCursor"]
                    self.assertIsNotNone(cursor)
                    second_page = repository.list_domain_work_items(
                        PROJECT_ID,
                        stage_id=STAGE_ID,
                        owner_user_id="owner@example.invalid",
                        overdue=overdue,
                        kind="action",
                        cursor=cursor,
                        limit=2,
                    )

                self.assertIsNotNone(second_page)
                self.assertEqual(
                    [item["globalId"] for item in second_page["items"]],
                    [str(second.global_id)],
                )
                self.assertIs(
                    second_page["items"][0]["overdue"],
                    overdue,
                )
                self.assertEqual(
                    AdvancingDateTime.moments,
                    [after_boundary],
                )
                expected_fingerprint = (
                    self.repository_module._domain_work_item_query_fingerprint(
                        project_id=PROJECT_ID,
                        stage_id=STAGE_ID,
                        owner_user_id="owner@example.invalid",
                        overdue=overdue,
                        kind="action",
                    )
                )
                decoded_cursor = self.repository_module._decode_cursor(
                    cursor,
                    expected_query_fingerprint=expected_fingerprint,
                )
                self.assertEqual(decoded_cursor.as_of, as_of)
                self.assertEqual(
                    decoded_cursor.query_fingerprint,
                    expected_fingerprint,
                )
                active_queries = [
                    query
                    for query in queries
                    if ["state_terminal", "=", 0] in query["filters"]
                ]
                self.assertTrue(active_queries)
                for query in active_queries:
                    self.assertIn(
                        [
                            "due_at",
                            threshold_operator,
                            as_of.replace(tzinfo=None),
                        ],
                        query["filters"],
                    )
                self.frappe.get_doc.assert_not_called()

    def test_cursor_rejects_query_or_project_mismatch_before_item_query(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        base_query = {
            "project_id": PROJECT_ID,
            "stage_id": STAGE_ID,
            "owner_user_id": "owner@example.invalid",
            "overdue": False,
            "kind": "action",
        }
        fingerprint = (
            self.repository_module._domain_work_item_query_fingerprint(
                **base_query
            )
        )
        cursor = self.repository_module._encode_cursor(
            (
                datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                "83000000-0000-4000-8000-000000000001",
            ),
            as_of=datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
            query_fingerprint=fingerprint,
        )
        variants = (
            ("projectId", {"project_id": OTHER_PROJECT_ID}),
            ("stageId", {"stage_id": None}),
            (
                "ownerUserId",
                {"owner_user_id": "other@example.invalid"},
            ),
            ("overdue-null", {"overdue": None}),
            ("overdue-true", {"overdue": True}),
            ("kind", {"kind": "risk"}),
        )

        for label, changed in variants:
            with self.subTest(query_field=label):
                query = {**base_query, **changed}
                get_all = mock.Mock(
                    side_effect=AssertionError(
                        "A mismatched cursor must fail before item queries."
                    )
                )
                self.frappe.get_all = get_all
                with self.assertRaises(
                    self.repository_module.RequestValidationFailed
                ) as caught:
                    repository.list_domain_work_items(
                        query["project_id"],
                        stage_id=query["stage_id"],
                        owner_user_id=query["owner_user_id"],
                        overdue=query["overdue"],
                        kind=query["kind"],
                        cursor=cursor,
                        limit=100,
                    )
                self.assertEqual(
                    caught.exception.field_errors,
                    [
                        {
                            "path": "cursor",
                            "message": "Enter a valid cursor.",
                        }
                    ],
                )
                get_all.assert_not_called()

    def test_cursor_rejects_other_version_and_malformed_payloads(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        query = {
            "project_id": PROJECT_ID,
            "stage_id": None,
            "owner_user_id": None,
            "overdue": None,
            "kind": None,
        }
        fingerprint = (
            self.repository_module._domain_work_item_query_fingerprint(
                **query
            )
        )
        valid_cursor = self.repository_module._encode_cursor(
            (
                datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                "84000000-0000-4000-8000-000000000001",
            ),
            as_of=datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
            query_fingerprint=fingerprint,
        )
        encoded_payload, signature = valid_cursor.split(".")
        padding = "=" * (-len(encoded_payload) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(
                (encoded_payload + padding).encode("ascii")
            ).decode("utf-8")
        )

        def encoded_payload(**changes: object) -> str:
            changed_payload = {**payload, **changes}
            encoded = base64.urlsafe_b64encode(
                self.repository_module.canonical_json(
                    changed_payload
                ).encode("utf-8")
            )
            return f"{encoded.decode('ascii').rstrip('=')}.{signature}"

        invalid_cursors = (
            ("version", encoded_payload(version=1)),
            ("missing-field", encoded_payload(asOf=None)),
            (
                "fingerprint-shape",
                encoded_payload(queryFingerprint="not-a-sha256"),
            ),
            ("not-json", "bm90LWpzb24"),
            ("invalid-base64", "not+base64"),
            ("non-canonical", f"{valid_cursor}="),
        )

        for label, invalid_cursor in invalid_cursors:
            with self.subTest(invalid_cursor=label):
                get_all = mock.Mock(
                    side_effect=AssertionError(
                        "An invalid cursor must fail before item queries."
                    )
                )
                self.frappe.get_all = get_all
                with self.assertRaises(
                    self.repository_module.RequestValidationFailed
                ) as caught:
                    repository.list_domain_work_items(
                        PROJECT_ID,
                        stage_id=None,
                        owner_user_id=None,
                        overdue=None,
                        kind=None,
                        cursor=invalid_cursor,
                        limit=50,
                    )
                self.assertEqual(
                    caught.exception.field_errors[0]["path"],
                    "cursor",
                )
                get_all.assert_not_called()

    def test_cursor_rejects_public_fingerprint_forgery_and_signature_tampering(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        fingerprint = (
            self.repository_module._domain_work_item_query_fingerprint(
                project_id=PROJECT_ID,
                stage_id=None,
                owner_user_id=None,
                overdue=None,
                kind=None,
            )
        )
        forged_payload = self.repository_module.canonical_json(
            {
                "asOf": "2099-12-31T23:59:59Z",
                "dueAt": "1900-01-01T00:00:00Z",
                "globalId": "84000000-0000-4000-8000-000000000001",
                "queryFingerprint": fingerprint,
                "version": 2,
            }
        ).encode("utf-8")
        forged_cursor = (
            f"{self.repository_module._base64url_encode(forged_payload)}."
            f"{self.repository_module._base64url_encode(bytes(32))}"
        )
        valid_cursor = self.repository_module._encode_cursor(
            (
                datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                "84000000-0000-4000-8000-000000000001",
            ),
            as_of=datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
            query_fingerprint=fingerprint,
        )
        replacement = "A" if valid_cursor[-1] != "A" else "B"
        tampered_cursor = f"{valid_cursor[:-1]}{replacement}"

        for label, invalid_cursor in (
            ("public-fingerprint-forgery", forged_cursor),
            ("signature-tampering", tampered_cursor),
        ):
            with self.subTest(cursor=label):
                get_all = mock.Mock(
                    side_effect=AssertionError(
                        "A forged cursor must fail before item queries."
                    )
                )
                self.frappe.get_all = get_all
                with self.assertRaises(
                    self.repository_module.RequestValidationFailed
                ) as caught:
                    repository.list_domain_work_items(
                        PROJECT_ID,
                        stage_id=None,
                        owner_user_id=None,
                        overdue=None,
                        kind=None,
                        cursor=invalid_cursor,
                        limit=50,
                    )
                self.assertEqual(
                    caught.exception.field_errors,
                    [
                        {
                            "path": "cursor",
                            "message": "Enter a valid cursor.",
                        }
                    ],
                )
                get_all.assert_not_called()

    def test_cursor_rejects_a_signature_from_a_different_site_key(self) -> None:
        fingerprint = (
            self.repository_module._domain_work_item_query_fingerprint(
                project_id=PROJECT_ID,
                stage_id=None,
                owner_user_id=None,
                overdue=None,
                kind=None,
            )
        )
        cursor = self.repository_module._encode_cursor(
            (
                datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                "84000000-0000-4000-8000-000000000001",
            ),
            as_of=datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
            query_fingerprint=fingerprint,
        )
        other_site_key = base64.urlsafe_b64encode(
            bytes(reversed(range(32)))
        ).decode("ascii")

        self.site_configuration.encryption_key = other_site_key
        with self.assertRaises(
            self.repository_module.RequestValidationFailed
        ):
            self.repository_module._decode_cursor(
                cursor,
                expected_query_fingerprint=fingerprint,
            )

    def test_cursor_signing_configuration_fails_closed_as_503(self) -> None:
        fingerprint = "a" * 64
        invalid_keys = (
            ("missing", None),
            (
                "non-canonical",
                base64.urlsafe_b64encode(bytes(32))
                .decode("ascii")
                .rstrip("="),
            ),
            ("wrong-length", base64.urlsafe_b64encode(bytes(31)).decode("ascii")),
            ("wrong-type", b"not-a-text-key"),
        )

        for label, configured in invalid_keys:
            with self.subTest(configuration=label):
                if configured is None:
                    self.site_configuration.pop("encryption_key", None)
                else:
                    self.site_configuration.encryption_key = configured
                with self.assertRaises(
                    self.repository_module.CursorSigningUnavailable
                ) as caught:
                    self.repository_module._encode_cursor(
                        (
                            datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                            "84000000-0000-4000-8000-000000000001",
                        ),
                        as_of=datetime(2026, 7, 23, 13, 0, tzinfo=UTC),
                        query_fingerprint=fingerprint,
                    )
                self.assertEqual(caught.exception.status, 503)
                self.assertEqual(
                    caught.exception.code,
                    "CURSOR_SIGNING_UNAVAILABLE",
                )
                self.assertNotEqual(caught.exception.status, 422)
                self.password.get_encryption_key.assert_not_called()

    def test_first_page_requires_existing_cursor_key_before_item_query(
        self,
    ) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        self.site_configuration.pop("encryption_key")
        get_all = mock.Mock(
            side_effect=AssertionError(
                "A missing signing key must fail before item queries."
            )
        )
        self.frappe.get_all = get_all

        with self.assertRaises(
            self.repository_module.CursorSigningUnavailable
        ):
            repository.list_domain_work_items(
                PROJECT_ID,
                stage_id=None,
                owner_user_id=None,
                overdue=None,
                kind=None,
                cursor=None,
                limit=50,
            )

        self.assertNotIn("encryption_key", self.site_configuration)
        self.password.get_encryption_key.assert_not_called()
        get_all.assert_not_called()

    def test_project_authorization_precedes_cursor_validation(self) -> None:
        project = self._project()
        repository, _audits = self._repository(project)
        authorization = mock.Mock(return_value=None)
        repository._authorized_project = authorization
        get_all = mock.Mock(
            side_effect=AssertionError(
                "An unavailable Project must not query its WorkItems."
            )
        )
        self.frappe.get_all = get_all

        with mock.patch.object(
            self.repository_module,
            "_domain_work_item_cursor_signing_key",
            side_effect=AssertionError(
                "An unavailable Project must not read cursor configuration."
            ),
        ) as signing_key:
            response = repository.list_domain_work_items(
                OTHER_PROJECT_ID,
                stage_id=None,
                owner_user_id=None,
                overdue=None,
                kind=None,
                cursor="malformed-cursor",
                limit=50,
            )

        self.assertIsNone(response)
        authorization.assert_called_once_with(
            OTHER_PROJECT_ID,
            self.repository_module.ProjectAccess.VIEW,
        )
        signing_key.assert_not_called()
        get_all.assert_not_called()

    def test_locked_waiter_reloads_winner_version_before_any_aggregate_write(
        self,
    ) -> None:
        principal = self.repository_module.Principal(
            user_id="Administrator",
            roles=frozenset(("System Manager",)),
            tenant_id=TENANT_ID,
        )
        repository = self.repository_module.FrappeProjectWorkRepository(
            principal=principal,
            request_id="a0dce453-3262-4d65-bcda-7a3090f3b1c2",
            trace_id="trace-repository-lock-race",
        )
        winner_project = self._project()
        winner_project.optimistic_version = 5
        events: list[str] = []

        def locked_document(
            doctype: str,
            name: str,
            **kwargs: object,
        ) -> AttrDoc:
            self.assertEqual(doctype, "NPI Engineering Project")
            self.assertEqual(name, str(PROJECT_ID))
            self.assertIs(kwargs.get("for_update"), True)
            events.append("locked-load")
            return winner_project

        self.frappe.get_doc = locked_document

        def replay(*_args: object) -> None:
            events.append("replay")
            return None

        repository._idempotency_replay = replay
        with (
            mock.patch.object(repository, "_prepare_team") as prepare,
            mock.patch.object(repository, "_insert_idempotency") as insert,
            self.assertRaises(self.repository_module.VersionConflict),
        ):
            repository.configure_team(
                PROJECT_ID,
                idempotency_key="a" * 64,
                expected_project_version=4,
                work_policy_ref={},
                members=(),
                role_assignments=(),
                substitutions=(),
                raci_assignments=(),
            )

        self.assertEqual(events, ["locked-load", "replay"])
        prepare.assert_not_called()
        insert.assert_not_called()

    def test_baseline_controller_accepts_administrator_actor_identity(
        self,
    ) -> None:
        controller_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_wbs_plan_baseline."
            "npi_wbs_plan_baseline"
        )
        snapshot = {
            "items": [
                {
                    "wbsItemId": str(WBS_ID),
                    "plannedStart": "2026-08-01",
                    "plannedFinish": "2026-08-05",
                    "critical": False,
                }
            ]
        }
        snapshot_hash = hashlib.sha256(
            json.dumps(
                snapshot,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        baseline = controller_module.NPIWBSPlanBaseline(
            global_id=str(uuid4()),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            plan_revision=2,
            project_version=4,
            label="Design release",
            work_policy_global_id=str(self.policy.policy_global_id),
            work_policy_version=self.policy.policy_version,
            work_policy_snapshot_hash=self.policy.snapshot_hash,
            snapshot_hash=snapshot_hash,
            snapshot=snapshot,
            captured_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
            captured_by="Administrator",
            optimistic_version=1,
        )
        baseline.validate()
        self.assertEqual(baseline.captured_by, "Administrator")
        for invalid_actor in ("", "Admin User", "Administrator\n", "a" * 255):
            with self.subTest(invalid_actor=repr(invalid_actor)):
                values = dict(baseline)
                values["captured_by"] = invalid_actor
                invalid = controller_module.NPIWBSPlanBaseline(values)
                with self.assertRaises(self.frappe.ValidationError):
                    invalid.validate()


if __name__ == "__main__":
    unittest.main()
