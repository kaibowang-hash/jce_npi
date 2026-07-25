from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from datetime import UTC, date, datetime
from typing import Any, Callable
from unittest import mock
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
POLICY_ID = "77932078-9512-428e-b9d7-863303661059"
MEMBER_ID = "4b5e2ed1-0e5a-41b6-a217-6f84a809ba36"
SUBSTITUTE_MEMBER_ID = "44f7b429-a527-4304-865d-d61e6a42320b"
ROLE_ID = "48a4b232-c848-4c9f-869e-5da76ef14372"
RACI_ID = "9526f55c-f810-41c3-89ae-e8f66b9bd1ba"
WBS_PARENT_ID = "590b332e-1ec4-44d8-8778-8b84eaf079bc"
WBS_CHILD_ID = "2579bd55-bd84-461a-ae82-9f4f2f31a6f3"
DEPENDENCY_ID = "c4506916-c9e5-4535-a04f-04513620369c"
WORK_ITEM_ID = "faee945d-6ea6-4852-a168-a125d55f06b7"
RELATED_WORK_ITEM_ID = "8c1fe01a-8c97-4272-b2db-971a0a6d5f64"
STAGE_ID = "62d6ac02-b85f-4ae0-a522-953c4ebc2de4"
REQUEST_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubResponse(dict):
    def __getattr__(self, name: str) -> Any:
        return self.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self, user_types: dict[str, str]) -> None:
        self.user_types = user_types
        self.rollback_count = 0

    def get_value(
        self,
        doctype: str,
        name: str,
        fieldname: str,
    ) -> object | None:
        if doctype == "User" and fieldname == "user_type":
            return self.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockProjectWorkRepository:
    def __init__(self, owner: "Phase4ProjectWorkApiTest") -> None:
        self.owner = owner
        self.calls: list[tuple[str, UUID, dict[str, Any]]] = []
        self.unavailable = False
        self.replayed = False

    def _record(
        self,
        operation: str,
        project_id: UUID,
        values: dict[str, Any],
    ) -> None:
        self.calls.append((operation, project_id, values))

    def _outcome(self, response: dict[str, Any]):
        return types.SimpleNamespace(
            response=copy.deepcopy(response),
            replayed=self.replayed,
        )

    def work_context(self, project_id: UUID) -> dict[str, Any] | None:
        self._record("work_context", project_id, {})
        if self.unavailable:
            return None
        return copy.deepcopy(self.owner.work_context)

    def configure_team(self, project_id: UUID, **values: Any):
        self._record("configure_team", project_id, values)
        if self.unavailable:
            return None
        return self._outcome(self.owner.work_context)

    def apply_work_plan(self, project_id: UUID, **values: Any):
        self._record("apply_work_plan", project_id, values)
        if self.unavailable:
            return None
        return self._outcome(self.owner.work_context)

    def capture_plan_baseline(self, project_id: UUID, **values: Any):
        self._record("capture_plan_baseline", project_id, values)
        if self.unavailable:
            return None
        return self._outcome(self.owner.baseline)

    def create_domain_work_item(self, project_id: UUID, **values: Any):
        self._record("create_domain_work_item", project_id, values)
        if self.unavailable:
            return None
        return self._outcome(self.owner.domain_work_item)

    def list_domain_work_items(
        self,
        project_id: UUID,
        **values: Any,
    ) -> dict[str, Any] | None:
        self._record("list_domain_work_items", project_id, values)
        if self.unavailable:
            return None
        return {
            "projectId": PROJECT_ID,
            "projectVersion": 5,
            "items": [copy.deepcopy(self.owner.domain_work_item)],
            "nextCursor": None,
        }


class Phase4ProjectWorkApiTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.sessions",
        "npi_core.project.frappe_repository",
        "npi_core.project_api",
        "npi_core.project_work_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.headers = {
            "Idempotency-Key": "p4-project-work-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase4-project-work-api",
        }
        self.roles = {
            "Administrator": ["System Manager"],
            "manager@example.invalid": ["System Manager"],
            "external-manager@example.invalid": ["System Manager"],
            "owner@example.invalid": ["NPI User"],
            "unrelated@example.invalid": ["NPI User"],
        }
        self.user_types = {
            "Administrator": "System User",
            "manager@example.invalid": "System User",
            "external-manager@example.invalid": "Website User",
            "owner@example.invalid": "System User",
            "unrelated@example.invalid": "System User",
        }
        self.logged_errors: list[dict[str, object]] = []

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="Administrator")
        self.frappe.conf = AttrDict(npi_tenant_id="TENANT-A")
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={"project_id": PROJECT_ID},
        )
        self.frappe.local = types.SimpleNamespace(
            response=StubResponse(),
            request=types.SimpleNamespace(path="/", method="GET"),
            form_dict=AttrDict(),
        )
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda user: self.roles.get(user, [])
        self.frappe.db = StubDatabase(self.user_types)
        self.frappe.log_error = lambda **values: self.logged_errors.append(values)
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda *_args, **_kwargs: None
        )
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

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + ("a" * 48)
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.sessions"] = sessions

        self.api = importlib.import_module("npi_core.project_work_api")
        self.router = importlib.import_module("npi_core.bff")
        self.factory_calls: list[dict[str, Any]] = []
        self.repository = MockProjectWorkRepository(self)

        def repository_factory(**values: Any):
            self.factory_calls.append(values)
            return self.repository

        self.api._repository_factory = repository_factory
        self.work_context = {
            "projectId": PROJECT_ID,
            "projectVersion": 5,
            "initialized": True,
            "workPolicyRef": self.policy_ref(),
            "members": [],
            "roleAssignments": [],
            "substitutions": [],
            "raciAssignments": [],
            "wbsItems": [],
            "dependencies": [],
            "baselines": [],
            "baselineComparison": None,
            "permissions": {
                "canView": True,
                "canContribute": True,
                "canAdminister": True,
            },
        }
        self.baseline = {
            "globalId": "73f59090-07da-4f1b-9331-c0bb1438edc8",
            "projectId": PROJECT_ID,
            "projectVersion": 5,
            "workPolicyRef": self.policy_ref(),
            "label": "Synthetic baseline",
            "snapshotHash": "b" * 64,
            "capturedAt": "2026-07-23T12:00:00Z",
            "capturedBy": "Administrator",
            "version": 1,
        }
        self.domain_work_item = {
            "globalId": WORK_ITEM_ID,
            "projectId": PROJECT_ID,
            "kind": "action",
            "title": "Prepare synthetic evidence",
            "context": {
                "projectId": PROJECT_ID,
                "stageId": STAGE_ID,
                "wbsItemId": WBS_CHILD_ID,
            },
            "ownerUserId": "owner@example.invalid",
            "dueAt": "2026-08-01T12:00:00Z",
            "severity": "medium",
            "blocking": False,
            "relatedWorkItemIds": [RELATED_WORK_ITEM_ID],
            "workPolicyRef": self.policy_ref(),
            "stateKey": "open",
            "stateLabelSource": "Open",
            "overdue": False,
            "version": 1,
            "createdAt": "2026-07-23T12:00:00Z",
            "lastChangedAt": "2026-07-23T12:00:00Z",
            "source": {
                "sourceSystem": "NPI_ONE",
                "editableIn": "NPI_ONE",
                "syncState": "local",
            },
        }

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    @staticmethod
    def policy_ref() -> dict[str, object]:
        return {
            "globalId": POLICY_ID,
            "version": 1,
            "snapshotHash": "a" * 64,
        }

    def team_payload(self) -> dict[str, object]:
        return {
            "expectedProjectVersion": 1,
            "workPolicyRef": self.policy_ref(),
            "members": [
                {
                    "globalId": MEMBER_ID,
                    "userId": "owner@example.invalid",
                    "effectiveFrom": "2026-07-23",
                },
                {
                    "globalId": SUBSTITUTE_MEMBER_ID,
                    "userId": "manager@example.invalid",
                    "effectiveFrom": "2026-07-23",
                    "effectiveTo": "2026-12-31",
                },
            ],
            "roleAssignments": [
                {
                    "globalId": ROLE_ID,
                    "memberId": MEMBER_ID,
                    "roleKey": "project_manager",
                    "effectiveFrom": "2026-07-23",
                }
            ],
            "substitutions": [
                {
                    "globalId": "ea145888-b2ee-4f30-bfdf-9c6eef99ab61",
                    "roleAssignmentId": ROLE_ID,
                    "substituteMemberId": SUBSTITUTE_MEMBER_ID,
                    "effectiveFrom": "2026-08-01",
                    "effectiveTo": "2026-08-31",
                }
            ],
            "raciAssignments": [
                {
                    "globalId": RACI_ID,
                    "contextType": "project",
                    "contextId": PROJECT_ID,
                    "responsibilityKey": "project_coordination",
                    "roleAssignmentId": ROLE_ID,
                    "raci": "responsible",
                }
            ],
        }

    def plan_payload(self) -> dict[str, object]:
        return {
            "expectedProjectVersion": 2,
            "workPolicyRef": self.policy_ref(),
            "items": [
                {
                    "globalId": WBS_PARENT_ID,
                    "code": "1",
                    "title": "Synthetic parent",
                    "ownerRoleAssignmentId": ROLE_ID,
                    "plannedStart": "2026-07-23",
                    "plannedFinish": "2026-07-30",
                    "milestone": False,
                    "statusKey": "not_started",
                    "progressPercent": 0,
                    "critical": True,
                },
                {
                    "globalId": WBS_CHILD_ID,
                    "code": "1.1",
                    "title": "Synthetic child",
                    "parentId": WBS_PARENT_ID,
                    "plannedStart": "2026-07-24",
                    "plannedFinish": "2026-07-25",
                    "actualStart": "2026-07-24",
                    "milestone": True,
                    "statusKey": "in_progress",
                    "progressPercent": 50,
                    "critical": False,
                },
            ],
            "dependencies": [
                {
                    "globalId": DEPENDENCY_ID,
                    "predecessorItemId": WBS_PARENT_ID,
                    "successorItemId": WBS_CHILD_ID,
                }
            ],
        }

    def domain_work_item_payload(self) -> dict[str, object]:
        return {
            "expectedProjectVersion": 4,
            "workPolicyRef": self.policy_ref(),
            "kind": "action",
            "title": "Prepare synthetic evidence",
            "context": {
                "stageId": STAGE_ID,
                "wbsItemId": WBS_CHILD_ID,
            },
            "ownerUserId": "owner@example.invalid",
            "dueAt": "2026-08-01T12:00:00Z",
            "severity": "medium",
            "blocking": False,
            "relatedWorkItemIds": [RELATED_WORK_ITEM_ID],
        }

    def reset_response(self, *, user: str = "Administrator") -> None:
        self.frappe.session.user = user
        self.frappe.local.response = StubResponse()
        self.frappe.flags.npi_route_params = {"project_id": PROJECT_ID}
        self.frappe.flags.npi_bff_request = False
        for name in ("npi_response_headers", "npi_response_body"):
            try:
                delattr(self.frappe.flags, name)
            except AttributeError:
                pass

    def call(
        self,
        command: str,
        function: Callable[..., dict[str, Any] | None],
        payload: dict[str, object],
        **extra: object,
    ) -> dict[str, Any] | None:
        self.frappe.local.form_dict = AttrDict(
            {"cmd": command, **payload, **extra}
        )
        return function(**payload, **extra)

    def assert_problem(
        self,
        result: dict[str, Any] | None,
        status: int,
        code: str,
    ) -> dict[str, Any]:
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result["status"], status)
        self.assertEqual(result["code"], code)
        self.assertEqual(self.frappe.local.response.http_status_code, status)
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(headers["X-Trace-ID"], result["traceId"])
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        UUID(headers["X-Request-ID"])
        return result

    def test_commands_require_authentication_internal_manager_csrf_and_headers(
        self,
    ) -> None:
        payload = self.team_payload()
        cases = (
            ("Guest", "AUTHENTICATION_REQUIRED"),
            ("owner@example.invalid", "PERMISSION_DENIED"),
            ("external-manager@example.invalid", "PERMISSION_DENIED"),
        )
        for user, code in cases:
            with self.subTest(user=user):
                self.reset_response(user=user)
                result = self.call(
                    "npi_core.project_work_api.configure_project_team",
                    self.api.configure_project_team,
                    payload,
                )
                self.assert_problem(result, 401 if user == "Guest" else 403, code)

        self.reset_response()
        self.headers.pop("X-Frappe-CSRF-Token")
        result = self.call(
            "npi_core.project_work_api.configure_project_team",
            self.api.configure_project_team,
            payload,
        )
        problem = self.assert_problem(result, 403, "CSRF_TOKEN_INVALID")
        self.assertTrue(problem["retryable"])

        self.reset_response()
        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + ("a" * 48)
        self.headers["X-Request-ID"] = "not-a-uuid"
        result = self.call(
            "npi_core.project_work_api.configure_project_team",
            self.api.configure_project_team,
            payload,
        )
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "requestId")

        self.reset_response()
        self.headers["X-Request-ID"] = REQUEST_ID
        self.headers.pop("Idempotency-Key")
        result = self.call(
            "npi_core.project_work_api.configure_project_team",
            self.api.configure_project_team,
            payload,
        )
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "idempotencyKey")
        self.assertEqual(self.repository.calls, [])

    def test_configure_team_is_closed_typed_and_calls_semantic_repository(
        self,
    ) -> None:
        result = self.call(
            "npi_core.project_work_api.configure_project_team",
            self.api.configure_project_team,
            self.team_payload(),
        )
        self.assertEqual(result, self.work_context)
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(headers["X-Request-ID"], REQUEST_ID)
        self.assertEqual(headers["Idempotency-Replayed"], "false")
        operation, project_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "configure_team")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        self.assertEqual(values["expected_project_version"], 1)
        self.assertEqual(len(values["idempotency_key"]), 64)
        self.assertNotEqual(
            values["idempotency_key"],
            "p4-project-work-command-0001",
        )
        self.assertEqual(values["work_policy_ref"]["global_id"], UUID(POLICY_ID))
        self.assertEqual(values["members"][0]["global_id"], UUID(MEMBER_ID))
        self.assertEqual(
            values["members"][0]["effective_from"],
            date(2026, 7, 23),
        )
        self.assertEqual(
            values["raci_assignments"][0]["raci"],
            "responsible",
        )
        self.assertNotIn("approval", values["raci_assignments"][0])

        self.reset_response()
        controlled_keys = self.team_payload()
        controlled_keys["roleAssignments"][0]["roleKey"] = "project.manager-v1"
        controlled_keys["raciAssignments"][0][
            "responsibilityKey"
        ] = "project.delivery-v1"
        result = self.call(
            "npi_core.project_work_api.configure_project_team",
            self.api.configure_project_team,
            controlled_keys,
        )
        self.assertEqual(result, self.work_context)
        values = self.repository.calls[-1][2]
        self.assertEqual(
            values["role_assignments"][0]["role_key"],
            "project.manager-v1",
        )
        self.assertEqual(
            values["raci_assignments"][0]["responsibility_key"],
            "project.delivery-v1",
        )

        self.reset_response()
        nested_extra = self.team_payload()
        nested_extra["members"][0]["approval"] = True
        result = self.call(
            "npi_core.project_work_api.configure_project_team",
            self.api.configure_project_team,
            nested_extra,
        )
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "members[0].approval")

        self.reset_response()
        result = self.call(
            "npi_core.project_work_api.configure_project_team",
            self.api.configure_project_team,
            self.team_payload(),
            unapproved="must-fail",
        )
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "unapproved")

    def test_apply_work_plan_parses_dates_booleans_and_rejects_loose_values(
        self,
    ) -> None:
        result = self.call(
            "npi_core.project_work_api.apply_project_work_plan",
            self.api.apply_project_work_plan,
            self.plan_payload(),
        )
        self.assertEqual(result, self.work_context)
        operation, project_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "apply_work_plan")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        parent, child = values["items"]
        self.assertEqual(parent["planned_finish"], date(2026, 7, 30))
        self.assertIs(parent["critical"], True)
        self.assertEqual(child["parent_id"], UUID(WBS_PARENT_ID))
        self.assertEqual(child["actual_start"], date(2026, 7, 24))
        self.assertIsNone(child["actual_finish"])
        dependency = values["dependencies"][0]
        self.assertEqual(
            dependency["predecessor_item_id"],
            UUID(WBS_PARENT_ID),
        )

        invalid_cases = []
        loose_boolean = self.plan_payload()
        loose_boolean["items"][0]["critical"] = "true"
        invalid_cases.append((loose_boolean, "items[0].critical"))
        bool_progress = self.plan_payload()
        bool_progress["items"][0]["progressPercent"] = False
        invalid_cases.append((bool_progress, "items[0].progressPercent"))
        dependency_type = self.plan_payload()
        dependency_type["dependencies"][0]["dependencyType"] = "finish_to_start"
        invalid_cases.append(
            (dependency_type, "dependencies[0].dependencyType")
        )
        client_status_label = self.plan_payload()
        client_status_label["items"][0][
            "statusLabelSource"
        ] = "Not started"
        invalid_cases.append(
            (client_status_label, "items[0].statusLabelSource")
        )
        bad_date = self.plan_payload()
        bad_date["items"][0]["plannedStart"] = "2026-02-30"
        invalid_cases.append((bad_date, "items[0].plannedStart"))
        for payload, path in invalid_cases:
            with self.subTest(path=path):
                self.reset_response()
                problem = self.assert_problem(
                    self.call(
                        "npi_core.project_work_api.apply_project_work_plan",
                        self.api.apply_project_work_plan,
                        payload,
                    ),
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(problem["fieldErrors"][0]["path"], path)

    def test_baseline_and_domain_work_item_creation_use_201_and_exact_types(
        self,
    ) -> None:
        baseline_payload = {
            "expectedProjectVersion": 3,
            "workPolicyRef": self.policy_ref(),
            "label": " Synthetic baseline ",
        }
        result = self.call(
            "npi_core.project_work_api.capture_project_plan_baseline",
            self.api.capture_project_plan_baseline,
            baseline_payload,
        )
        self.assertEqual(result, self.baseline)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.repository.calls[-1][2]["label"],
            "Synthetic baseline",
        )

        self.reset_response()
        self.repository.replayed = True
        result = self.call(
            "npi_core.project_work_api.create_project_domain_work_item",
            self.api.create_project_domain_work_item,
            self.domain_work_item_payload(),
        )
        self.assertEqual(result, self.domain_work_item)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )
        operation, project_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "create_domain_work_item")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        self.assertEqual(values["kind"], "action")
        self.assertEqual(values["context"]["stage_id"], UUID(STAGE_ID))
        self.assertEqual(values["context"]["wbs_item_id"], UUID(WBS_CHILD_ID))
        self.assertEqual(values["due_at"], datetime(2026, 8, 1, 12, tzinfo=UTC))
        self.assertIs(values["blocking"], False)
        self.assertEqual(
            values["related_work_item_ids"],
            (UUID(RELATED_WORK_ITEM_ID),),
        )
        self.assertNotIn("state_key", values)

        self.reset_response()
        for field_name, value in (
            ("stateKey", "completed"),
            ("stateLabelSource", "Completed"),
        ):
            with self.subTest(client_lifecycle_field=field_name):
                self.reset_response()
                payload = self.domain_work_item_payload()
                payload[field_name] = value
                problem = self.assert_problem(
                    self.call(
                        "npi_core.project_work_api.create_project_domain_work_item",
                        self.api.create_project_domain_work_item,
                        payload,
                    ),
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(
                    problem["fieldErrors"][0]["path"],
                    field_name,
                )

    def test_get_context_maps_repository_none_to_one_idor_safe_problem(self) -> None:
        self.reset_response(user="owner@example.invalid")
        self.frappe.local.form_dict = AttrDict(
            {"cmd": "npi_core.project_work_api.get_project_work_context"}
        )
        result = self.api.get_project_work_context()
        self.assertEqual(result, self.work_context)
        self.assertEqual(self.factory_calls[-1]["principal"].user_id, "owner@example.invalid")
        self.assertEqual(
            self.factory_calls[-1]["principal"].tenant_id,
            "TENANT-A",
        )

        problems = []
        for user in ("owner@example.invalid", "unrelated@example.invalid"):
            self.reset_response(user=user)
            self.repository.unavailable = True
            self.frappe.local.form_dict = AttrDict(
                {"cmd": "npi_core.project_work_api.get_project_work_context"}
            )
            problem = self.assert_problem(
                self.api.get_project_work_context(),
                404,
                "PROJECT_UNAVAILABLE",
            )
            problems.append(problem)
        for field in ("type", "title", "status", "code", "retryable"):
            self.assertEqual(problems[0][field], problems[1][field])

        self.reset_response(user="Guest")
        self.repository.unavailable = False
        self.frappe.local.form_dict = AttrDict(
            {"cmd": "npi_core.project_work_api.get_project_work_context"}
        )
        self.assert_problem(
            self.api.get_project_work_context(),
            401,
            "AUTHENTICATION_REQUIRED",
        )

        self.reset_response(user="owner@example.invalid")
        self.frappe.flags.npi_route_params = {"project_id": "not-a-uuid"}
        self.frappe.local.form_dict = AttrDict(
            {"cmd": "npi_core.project_work_api.get_project_work_context"}
        )
        problem = self.assert_problem(
            self.api.get_project_work_context(),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "projectId")

        self.reset_response(user="owner@example.invalid")
        self.frappe.local.form_dict = AttrDict(
            {
                "cmd": "npi_core.project_work_api.get_project_work_context",
                "expand": "all",
            }
        )
        problem = self.assert_problem(
            self.api.get_project_work_context(expand="all"),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "expand")

    def test_domain_work_item_query_parses_filters_and_rejects_aliases(self) -> None:
        self.reset_response(user="owner@example.invalid")
        query = {
            "stageId": STAGE_ID,
            "ownerUserId": "OWNER@EXAMPLE.INVALID",
            "overdue": "true",
            "kind": "risk",
            "cursor": "cursor.v1:abc_123",
            "limit": "100",
        }
        result = self.call(
            "npi_core.project_work_api.get_project_domain_work_items",
            self.api.get_project_domain_work_items,
            query,
        )
        self.assertEqual(result["projectId"], PROJECT_ID)
        operation, project_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "list_domain_work_items")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        self.assertEqual(values["stage_id"], UUID(STAGE_ID))
        self.assertEqual(values["owner_user_id"], "owner@example.invalid")
        self.assertIs(values["overdue"], True)
        self.assertEqual(values["kind"], "risk")
        self.assertEqual(values["cursor"], "cursor.v1:abc_123")
        self.assertEqual(values["limit"], 100)
        self.assertIsNone(values["work_item_id"])

        invalid_queries = (
            ({"overdue": "yes"}, "overdue"),
            ({"limit": "0"}, "limit"),
            ({"limit": "101"}, "limit"),
            ({"limit": "01"}, "limit"),
            ({"stageId": "not-a-uuid"}, "stageId"),
            ({"kind": "approval"}, "kind"),
        )
        for invalid, path in invalid_queries:
            with self.subTest(path=path, value=invalid[path]):
                self.reset_response(user="owner@example.invalid")
                problem = self.assert_problem(
                    self.call(
                        "npi_core.project_work_api.get_project_domain_work_items",
                        self.api.get_project_domain_work_items,
                        invalid,
                    ),
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(problem["fieldErrors"][0]["path"], path)

    def test_exact_work_item_identity_remains_raw_until_repository_authorization(
        self,
    ) -> None:
        self.reset_response(user="owner@example.invalid")
        result = self.call(
            "npi_core.project_work_api.get_project_domain_work_items",
            self.api.get_project_domain_work_items,
            {"workItemId": WORK_ITEM_ID},
        )
        self.assertEqual(result["projectId"], PROJECT_ID)
        operation, project_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "list_domain_work_items")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        self.assertEqual(values["work_item_id"], WORK_ITEM_ID)

        self.reset_response(user="unrelated@example.invalid")
        self.repository.unavailable = True
        problem = self.assert_problem(
            self.call(
                "npi_core.project_work_api.get_project_domain_work_items",
                self.api.get_project_domain_work_items,
                {"workItemId": "not-a-global-id"},
            ),
            404,
            "PROJECT_UNAVAILABLE",
        )
        self.assertEqual(problem["retryable"], False)
        self.assertEqual(
            self.repository.calls[-1][2]["work_item_id"],
            "not-a-global-id",
        )

    def test_malformed_cursor_is_passed_to_authorized_repository_boundary(
        self,
    ) -> None:
        self.reset_response(user="unrelated@example.invalid")
        self.repository.unavailable = True

        problem = self.assert_problem(
            self.call(
                "npi_core.project_work_api.get_project_domain_work_items",
                self.api.get_project_domain_work_items,
                {"cursor": "cursor with spaces"},
            ),
            404,
            "PROJECT_UNAVAILABLE",
        )

        self.assertEqual(problem["retryable"], False)
        operation, project_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "list_domain_work_items")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        self.assertEqual(values["cursor"], "cursor with spaces")

    def test_domain_work_item_cursor_signing_configuration_returns_503(
        self,
    ) -> None:
        from npi_core.foundation.errors import CursorSigningUnavailable

        self.reset_response(user="owner@example.invalid")
        self.repository.list_domain_work_items = mock.Mock(
            side_effect=CursorSigningUnavailable()
        )
        problem = self.assert_problem(
            self.call(
                "npi_core.project_work_api.get_project_domain_work_items",
                self.api.get_project_domain_work_items,
                {"cursor": "signed.cursor"},
            ),
            503,
            "CURSOR_SIGNING_UNAVAILABLE",
        )
        self.assertEqual(problem["title"], "Secure pagination is unavailable.")
        self.assertEqual(problem["retryable"], False)

    def test_bff_maps_only_the_six_explicit_project_work_operations(self) -> None:
        routes = (
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/work-context",
                "npi_core.project_work_api.get_project_work_context",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:configure-team",
                "npi_core.project_work_api.configure_project_team",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:apply-work-plan",
                "npi_core.project_work_api.apply_project_work_plan",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:capture-plan-baseline",
                "npi_core.project_work_api.capture_project_plan_baseline",
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/domain-work-items",
                "npi_core.project_work_api.get_project_domain_work_items",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/domain-work-items",
                "npi_core.project_work_api.create_project_domain_work_item",
            ),
        )
        for method, path, command in routes:
            with self.subTest(method=method, path=path):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                )
                self.router.route_request()
                self.assertEqual(self.frappe.local.form_dict.cmd, command)
                self.assertEqual(
                    self.frappe.flags.npi_route_params,
                    {"project_id": PROJECT_ID},
                )
                self.assertTrue(
                    self.router._requires_project_request_id(method, path)
                )

        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/domain-work-items/extra",
            method="GET",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.route_not_found",
        )

    def test_endpoint_decorators_keep_transport_open_and_methods_exact(self) -> None:
        expected = {
            self.api.get_project_work_context: ("GET",),
            self.api.configure_project_team: ("POST",),
            self.api.apply_project_work_plan: ("POST",),
            self.api.capture_project_plan_baseline: ("POST",),
            self.api.create_project_domain_work_item: ("POST",),
            self.api.get_project_domain_work_items: ("GET",),
        }
        for endpoint, methods in expected.items():
            with self.subTest(endpoint=endpoint.__name__):
                self.assertTrue(endpoint.allow_guest)
                self.assertEqual(endpoint.allowed_methods, methods)


if __name__ == "__main__":
    unittest.main()
