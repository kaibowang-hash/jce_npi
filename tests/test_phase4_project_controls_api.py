from __future__ import annotations

import base64
import copy
import importlib
import inspect
import sys
import types
import unittest
from datetime import UTC, datetime
from typing import Any
from unittest import mock
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.security import Principal  # noqa: E402
from npi_core.foundation.errors import (  # noqa: E402
    CursorSigningUnavailable,
    PermissionDenied,
    RequestValidationFailed,
    VersionConflict,
)
from npi_core.project.domain import IdempotencyConflict  # noqa: E402
from npi_core.project_controls.domain import (  # noqa: E402
    HealthDimension,
    HealthRuleMode,
    PrerequisiteStatus,
    ProjectPrerequisiteKey,
)

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
POLICY_ID = "77932078-9512-428e-b9d7-863303661059"
MEMBER_ID = "4b5e2ed1-0e5a-41b6-a217-6f84a809ba36"
TEMPLATE_ID = "44f7b429-a527-4304-865d-d61e6a42320b"
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


class StubDocument:
    pass


class StubDatabase:
    def __init__(self, user_types: dict[str, str]) -> None:
        self.user_types = user_types
        self.rollback_count = 0

    def get_value(
        self,
        doctype: str,
        name: object,
        fieldname: object,
        **_kwargs: object,
    ) -> object | None:
        if doctype == "User" and fieldname == "user_type":
            return self.user_types.get(str(name))
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockProjectControlsRepository:
    def __init__(self, owner: "Phase4ProjectControlsApiTest") -> None:
        self.owner = owner
        self.calls: list[tuple[str, UUID | None, dict[str, Any]]] = []
        self.unavailable = False
        self.replayed = False

    def _query(
        self,
        operation: str,
        routed_project_id: UUID | None,
        response: dict[str, Any],
        **values: Any,
    ) -> dict[str, Any] | None:
        self.calls.append((operation, routed_project_id, values))
        if self.unavailable:
            return None
        return copy.deepcopy(response)

    def _command(
        self,
        operation: str,
        project_id: UUID,
        response: dict[str, Any],
        **values: Any,
    ):
        self.calls.append((operation, project_id, values))
        if self.unavailable:
            return None
        return self.owner.api.ProjectControlCommandOutcome(
            copy.deepcopy(response),
            replayed=self.replayed,
        )

    def controls(self, project_id: UUID) -> dict[str, Any] | None:
        return self._query(
            "controls",
            project_id,
            self.owner.controls,
        )

    def bind_policy(self, project_id: UUID, **values: Any):
        return self._command(
            "bind_policy",
            project_id,
            self.owner.controls,
            **values,
        )

    def assess_health(self, project_id: UUID, **values: Any):
        return self._command(
            "assess_health",
            project_id,
            self.owner.controls,
            **values,
        )

    def transition(self, project_id: UUID, **values: Any):
        return self._command(
            "transition",
            project_id,
            self.owner.controls,
            **values,
        )

    def activity(
        self,
        project_id: UUID,
        **values: Any,
    ) -> dict[str, Any] | None:
        return self._query(
            "activity",
            project_id,
            self.owner.activity,
            **values,
        )

    def add_comment(self, project_id: UUID, **values: Any):
        return self._command(
            "add_comment",
            project_id,
            self.owner.activity["items"][0],
            **values,
        )

    def set_following(self, project_id: UUID, **values: Any):
        return self._command(
            "set_following",
            project_id,
            self.owner.follow,
            **values,
        )

    def project_learning(
        self,
        project_id: UUID,
        **values: Any,
    ) -> dict[str, Any] | None:
        return self._query(
            "project_learning",
            project_id,
            self.owner.learning_page,
            **values,
        )

    def create_learning(self, project_id: UUID, **values: Any):
        return self._command(
            "create_learning",
            project_id,
            self.owner.learning,
            **values,
        )

    def search_learning(self, **values: Any) -> dict[str, Any] | None:
        return self._query(
            "search_learning",
            None,
            {"items": [self.owner.learning]},
            **values,
        )


class Phase4ProjectControlsApiTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.sessions",
        "npi_core.project_controls.frappe_repository",
        "npi_core.project_controls_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.headers = {
            "Idempotency-Key": "p4-project-controls-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase4-project-controls-api",
        }
        self.roles = {
            "Administrator": ["System Manager", "NPI API User"],
            "manager@example.invalid": ["System Manager"],
            "owner@example.invalid": ["NPI User", "NPI API User"],
            "external@example.invalid": ["NPI User"],
        }
        self.user_types = {
            "Administrator": "System User",
            "manager@example.invalid": "System User",
            "owner@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }
        self.logged_errors: list[dict[str, object]] = []

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="Administrator")
        self.frappe.conf = AttrDict(
            encryption_key=base64.urlsafe_b64encode(b"a" * 32).decode("ascii"),
            npi_tenant_id="TENANT-A",
        )
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
        self.frappe.get_all = lambda *_args, **_kwargs: []
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
        self.frappe.PermissionError = type(
            "PermissionError",
            (Exception,),
            {},
        )
        self.frappe.ValidationError = type(
            "ValidationError",
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
        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        self.frappe.model = model
        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + ("a" * 48)
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document
        sys.modules["frappe.sessions"] = sessions

        self.api = importlib.import_module("npi_core.project_controls_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockProjectControlsRepository(self)
        self.factory_calls: list[dict[str, Any]] = []
        self.original_repository_class = self.api.FrappeProjectControlsRepository

        def repository_factory(**values: Any):
            self.factory_calls.append(values)
            return self.repository

        self.api.FrappeProjectControlsRepository = repository_factory
        self.controls = {
            "project": {
                "globalId": PROJECT_ID,
                "businessCode": "SYN-P405",
                "title": "Synthetic Project controls",
                "state": "active",
                "version": 4,
                "tenantId": "TENANT-A",
            },
            "policy": None,
            "binding": None,
            "health": {
                "overallStatus": "unassessed",
                "dimensions": [],
                "assessment": None,
            },
            "lifecycleActions": [],
            "bindingOptions": {
                "policies": [],
                "eligibleMembers": [],
            },
            "permissions": {
                "canBindPolicy": True,
                "canAssessHealth": False,
                "canTransition": False,
            },
        }
        activity_item = {
            "globalId": TEMPLATE_ID,
            "eventType": "comment_added",
            "actorUserId": "owner@example.invalid",
            "occurredAt": "2026-07-25T12:00:00Z",
            "detail": {
                "body": "Synthetic comment",
                "mentions": [],
                "attachments": [],
                "objectLinks": [],
            },
        }
        self.activity = {
            "projectId": PROJECT_ID,
            "items": [activity_item],
            "nextCursor": None,
            "permissions": {
                "canComment": True,
                "canFollow": True,
            },
            "commentOptions": {
                "truncated": False,
                "mentions": [],
                "attachments": [],
                "objectLinks": [],
            },
            "following": False,
            "followerVersion": 0,
        }
        self.follow = {
            "projectId": PROJECT_ID,
            "following": True,
            "version": 1,
            "changedAt": "2026-07-25T12:00:00Z",
        }
        self.learning = {
            "globalId": TEMPLATE_ID,
            "projectGlobalId": PROJECT_ID,
            "kind": "lesson",
            "title": "Synthetic lesson",
        }
        self.learning_page = {
            "projectId": PROJECT_ID,
            "items": [self.learning],
            "permissions": {"canCreate": True},
        }

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def reset_response(self, *, user: str = "Administrator") -> None:
        self.frappe.session.user = user
        self.frappe.local.response = StubResponse()
        self.frappe.local.form_dict = AttrDict()
        self.frappe.flags.npi_bff_request = False
        self.frappe.flags.npi_response_headers = None
        self.frappe.flags.npi_response_body = None
        self.frappe.flags.npi_route_params = {"project_id": PROJECT_ID}
        self.repository.calls.clear()
        self.factory_calls.clear()

    def call(
        self,
        command: str,
        function,
        payload: dict[str, Any],
        **extra: Any,
    ) -> dict[str, Any] | None:
        self.frappe.local.form_dict = AttrDict({"cmd": command, **payload, **extra})
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
        self.assertEqual(
            headers["Content-Type"],
            "application/problem+json",
        )
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        UUID(headers["X-Request-ID"])
        return result

    @staticmethod
    def bind_payload() -> dict[str, object]:
        return {
            "expectedProjectVersion": 4,
            "policyRef": {
                "globalId": POLICY_ID,
                "version": 2,
                "snapshotHash": "a" * 64,
            },
            "bindings": [
                {
                    "slot": "project_controller",
                    "memberGlobalId": MEMBER_ID,
                }
            ],
        }

    @staticmethod
    def assess_payload() -> dict[str, object]:
        return {
            "expectedProjectVersion": 4,
            "measurements": [
                {
                    "dimension": "quality",
                    "numericValue": None,
                    "manualStatus": "green",
                }
            ],
            "reason": None,
            "recoveryPlan": None,
        }

    @staticmethod
    def transition_payload() -> dict[str, object]:
        return {
            "expectedProjectVersion": 4,
            "action": "pause",
            "reason": "Awaiting exact supplied material.",
        }

    @staticmethod
    def comment_payload() -> dict[str, object]:
        return {
            "body": "Synthetic comment",
            "mentions": [{"memberGlobalId": MEMBER_ID}],
            "attachments": [],
            "objectLinks": [],
        }

    @staticmethod
    def learning_payload() -> dict[str, object]:
        return {
            "kind": "lesson",
            "title": "Synthetic lesson",
            "content": "Keep exact authority bindings.",
            "recommendation": None,
            "tags": ["governance"],
        }

    def test_whitelisted_methods_are_transport_only_not_guest_access(
        self,
    ) -> None:
        query_names = (
            "get_project_controls",
            "get_project_activity",
            "get_project_learning",
            "search_project_learning",
        )
        command_names = (
            "bind_project_control_policy",
            "assess_project_health",
            "transition_project",
            "add_project_comment",
            "follow_project",
            "unfollow_project",
            "create_project_learning",
        )
        for name in query_names:
            function = getattr(self.api, name)
            self.assertEqual(function.allowed_methods, ("GET",))
            self.assertTrue(function.allow_guest)
        for name in command_names:
            function = getattr(self.api, name)
            self.assertEqual(function.allowed_methods, ("POST",))
            self.assertTrue(function.allow_guest)

        self.reset_response(user="Guest")
        result = self.call(
            "npi_core.project_controls_api.get_project_controls",
            self.api.get_project_controls,
            {},
        )
        self.assert_problem(result, 401, "AUTHENTICATION_REQUIRED")
        self.assertEqual(self.repository.calls, [])

    def test_controls_query_uses_exact_route_and_authenticated_principal(
        self,
    ) -> None:
        self.reset_response(user="owner@example.invalid")
        result = self.call(
            "npi_core.project_controls_api.get_project_controls",
            self.api.get_project_controls,
            {},
        )
        self.assertEqual(result, self.controls)
        self.assertEqual(
            self.repository.calls,
            [("controls", UUID(PROJECT_ID), {})],
        )
        self.assertEqual(len(self.factory_calls), 1)
        principal = self.factory_calls[0]["principal"]
        self.assertEqual(principal.user_id, "owner@example.invalid")
        self.assertEqual(principal.tenant_id, "TENANT-A")
        self.assertFalse(principal.is_external)
        self.assertEqual(
            self.factory_calls[0]["request_id"],
            REQUEST_ID,
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Trace-ID"],
            self.headers["X-Trace-ID"],
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )

    def test_commands_require_csrf_request_and_actor_bound_idempotency(
        self,
    ) -> None:
        self.reset_response(user="owner@example.invalid")
        self.headers.pop("X-Frappe-CSRF-Token")
        result = self.call(
            "npi_core.project_controls_api.transition_project",
            self.api.transition_project,
            self.transition_payload(),
        )
        self.assert_problem(result, 403, "CSRF_TOKEN_INVALID")
        self.assertEqual(self.repository.calls, [])

        self.reset_response(user="owner@example.invalid")
        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + ("a" * 48)
        self.headers["X-Request-ID"] = "not-a-request-id"
        result = self.call(
            "npi_core.project_controls_api.transition_project",
            self.api.transition_project,
            self.transition_payload(),
        )
        self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(self.repository.calls, [])

        self.reset_response(user="owner@example.invalid")
        self.headers["X-Request-ID"] = REQUEST_ID
        self.headers.pop("Idempotency-Key")
        result = self.call(
            "npi_core.project_controls_api.transition_project",
            self.api.transition_project,
            self.transition_payload(),
        )
        problem = self.assert_problem(
            result,
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(
            problem["fieldErrors"][0]["path"],
            "idempotencyKey",
        )
        self.assertEqual(self.repository.calls, [])

    def test_commands_require_transport_admission_before_request_details(
        self,
    ) -> None:
        self.roles["owner@example.invalid"] = ["NPI User"]
        self.reset_response(user="owner@example.invalid")
        denied = self.call(
            "npi_core.project_controls_api.add_project_comment",
            self.api.add_project_comment,
            self.comment_payload(),
            unexpected="must-not-be-validated-first",
        )
        self.assert_problem(denied, 403, "PERMISSION_DENIED")
        self.assertEqual(self.factory_calls, [])
        self.assertEqual(self.repository.calls, [])

        self.roles["owner@example.invalid"] = [
            "NPI User",
            "NPI API User",
        ]
        self.reset_response(user="owner@example.invalid")
        denied_bind = self.call(
            "npi_core.project_controls_api.bind_project_control_policy",
            self.api.bind_project_control_policy,
            self.bind_payload(),
        )
        self.assert_problem(denied_bind, 403, "PERMISSION_DENIED")
        self.assertEqual(self.factory_calls, [])
        self.assertEqual(self.repository.calls, [])

    def test_commands_map_exact_fields_and_report_safe_replay(self) -> None:
        commands = (
            (
                "bind_project_control_policy",
                self.api.bind_project_control_policy,
                self.bind_payload(),
                "bind_policy",
                {
                    "expected_project_version": 4,
                    "policy_ref": self.bind_payload()["policyRef"],
                    "bindings": self.bind_payload()["bindings"],
                },
                200,
            ),
            (
                "assess_project_health",
                self.api.assess_project_health,
                self.assess_payload(),
                "assess_health",
                {
                    "expected_project_version": 4,
                    "measurements": self.assess_payload()["measurements"],
                    "reason": None,
                    "recovery_plan": None,
                },
                200,
            ),
            (
                "transition_project",
                self.api.transition_project,
                self.transition_payload(),
                "transition",
                {
                    "expected_project_version": 4,
                    "action": "pause",
                    "reason": "Awaiting exact supplied material.",
                },
                200,
            ),
            (
                "add_project_comment",
                self.api.add_project_comment,
                self.comment_payload(),
                "add_comment",
                {
                    "body": "Synthetic comment",
                    "mentions": [{"memberGlobalId": MEMBER_ID}],
                    "attachments": [],
                    "object_links": [],
                },
                201,
            ),
            (
                "create_project_learning",
                self.api.create_project_learning,
                self.learning_payload(),
                "create_learning",
                {
                    "kind": "lesson",
                    "title": "Synthetic lesson",
                    "content": "Keep exact authority bindings.",
                    "recommendation": None,
                    "tags": ["governance"],
                },
                201,
            ),
        )
        for name, function, payload, operation, expected, status in commands:
            with self.subTest(command=name):
                self.reset_response(
                    user=(
                        "Administrator"
                        if name == "bind_project_control_policy"
                        else "owner@example.invalid"
                    )
                )
                self.repository.replayed = True
                result = self.call(
                    f"npi_core.project_controls_api.{name}",
                    function,
                    payload,
                )
                self.assertIsNotNone(result)
                self.assertEqual(
                    self.frappe.local.response.http_status_code,
                    status,
                )
                self.assertEqual(len(self.repository.calls), 1)
                called_operation, project_id, values = self.repository.calls[0]
                self.assertEqual(called_operation, operation)
                self.assertEqual(project_id, UUID(PROJECT_ID))
                key = values.pop("idempotency_key")
                self.assertRegex(key, r"^[a-f0-9]{64}$")
                self.assertEqual(values, expected)
                self.assertEqual(
                    self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
                    "true",
                )
                self.assertEqual(
                    self.frappe.flags.npi_response_headers["X-Request-ID"],
                    REQUEST_ID,
                )

    def test_nullable_command_fields_must_be_explicitly_present(self) -> None:
        cases = (
            (
                "assess_project_health",
                self.api.assess_project_health,
                self.assess_payload(),
                "reason",
            ),
            (
                "assess_project_health",
                self.api.assess_project_health,
                self.assess_payload(),
                "recoveryPlan",
            ),
            (
                "create_project_learning",
                self.api.create_project_learning,
                self.learning_payload(),
                "recommendation",
            ),
        )
        for name, function, payload, missing in cases:
            with self.subTest(command=name, missing=missing):
                self.reset_response(user="owner@example.invalid")
                incomplete = dict(payload)
                del incomplete[missing]
                problem = self.assert_problem(
                    self.call(
                        f"npi_core.project_controls_api.{name}",
                        function,
                        incomplete,
                    ),
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(
                    problem["fieldErrors"],
                    [
                        {
                            "path": missing,
                            "message": "This field is required.",
                        }
                    ],
                )
                self.assertEqual(self.repository.calls, [])

    def test_follow_commands_keep_boolean_server_owned(self) -> None:
        for name, function, active in (
            ("follow_project", self.api.follow_project, True),
            ("unfollow_project", self.api.unfollow_project, False),
        ):
            with self.subTest(command=name):
                self.reset_response(user="owner@example.invalid")
                result = self.call(
                    f"npi_core.project_controls_api.{name}",
                    function,
                    {"expectedVersion": 0},
                )
                self.assertEqual(result, self.follow)
                operation, project_id, values = self.repository.calls[0]
                self.assertEqual(operation, "set_following")
                self.assertEqual(project_id, UUID(PROJECT_ID))
                values.pop("idempotency_key")
                self.assertEqual(
                    values,
                    {"expected_version": 0, "active": active},
                )

    def test_queries_map_filters_and_enforce_bounded_integers(self) -> None:
        query_cases = (
            (
                "get_project_activity",
                self.api.get_project_activity,
                {"cursor": "opaque.activity.cursor", "limit": "25"},
                "activity",
                {"cursor": "opaque.activity.cursor", "limit": 25},
            ),
            (
                "get_project_learning",
                self.api.get_project_learning,
                {
                    "kind": "lesson",
                    "search": "authority",
                    "limit": 10,
                },
                "project_learning",
                {
                    "kind": "lesson",
                    "search": "authority",
                    "learning_id": None,
                    "limit": 10,
                },
            ),
            (
                "search_project_learning",
                self.api.search_project_learning,
                {
                    "kind": "template_improvement",
                    "tag": "governance",
                    "search": "authority",
                    "projectId": PROJECT_ID,
                    "templateGlobalId": TEMPLATE_ID,
                    "templateVersion": "2",
                    "limit": "30",
                },
                "search_learning",
                {
                    "kind": "template_improvement",
                    "tag": "governance",
                    "search": "authority",
                    "project_id": UUID(PROJECT_ID),
                    "template_global_id": TEMPLATE_ID,
                    "template_version": "2",
                    "limit": 30,
                },
            ),
        )
        for name, function, payload, operation, expected in query_cases:
            with self.subTest(query=name):
                self.reset_response(user="owner@example.invalid")
                result = self.call(
                    f"npi_core.project_controls_api.{name}",
                    function,
                    payload,
                )
                self.assertIsNotNone(result)
                called_operation, project_id, values = self.repository.calls[0]
                self.assertEqual(called_operation, operation)
                self.assertEqual(
                    project_id,
                    None if operation == "search_learning" else UUID(PROJECT_ID),
                )
                self.assertEqual(values, expected)

        for invalid_limit in (
            0,
            -1,
            True,
            "01",
            "1.5",
            101,
            "101",
            "9" * 5000,
        ):
            with self.subTest(invalid_limit=invalid_limit):
                self.reset_response(user="owner@example.invalid")
                result = self.call(
                    "npi_core.project_controls_api.get_project_activity",
                    self.api.get_project_activity,
                    {"limit": invalid_limit},
                )
                self.assert_problem(
                    result,
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(self.repository.calls, [])

    def test_global_learning_rejects_external_users_before_filter_parsing(
        self,
    ) -> None:
        self.reset_response(user="external@example.invalid")
        result = self.call(
            "npi_core.project_controls_api.search_project_learning",
            self.api.search_project_learning,
            {
                "projectId": "not-a-global-id",
                "templateVersion": "not-an-integer",
            },
            unexpected="must-not-be-validated-first",
        )
        self.assert_problem(result, 403, "PERMISSION_DENIED")
        self.assertEqual(self.factory_calls, [])
        self.assertEqual(self.repository.calls, [])

        with self.assertRaises(PermissionDenied):
            self.repository_for(external=True).search_learning(
                kind="not-a-kind",
                tag="governance",
                search="authority",
                project_id=None,
                template_global_id=None,
                template_version=None,
                limit=50,
            )

    def test_exact_project_learning_search_does_not_enumerate_all_projects(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
        )
        with (
            mock.patch.object(
                repository,
                "_authorized_project",
                return_value=project,
            ) as authorized,
            mock.patch.object(
                repository,
                "_accessible_project_ids",
                side_effect=AssertionError("global enumeration is forbidden"),
            ),
            mock.patch.object(
                repository_module.frappe,
                "get_all",
                return_value=[],
            ),
        ):
            result = repository.search_learning(
                kind=None,
                tag=None,
                search=None,
                project_id=UUID(PROJECT_ID),
                template_global_id=None,
                template_version=None,
                limit=50,
            )
        self.assertEqual(result, {"items": []})
        authorized.assert_called_once_with(UUID(PROJECT_ID))

    def test_global_learning_authorizes_exact_project_before_secondary_filters(
        self,
    ) -> None:
        repository = self.repository_for()
        repository._authorized_project = mock.Mock(return_value=None)
        self.frappe.get_all = mock.Mock(
            side_effect=AssertionError("Unavailable Project must not query learning.")
        )
        result = repository.search_learning(
            kind="not-a-kind",
            tag="invalid tag!",
            search=object(),
            project_id=UUID(PROJECT_ID),
            template_global_id=TEMPLATE_ID,
            template_version="not-an-integer",
            limit=50,
        )
        self.assertIsNone(result)
        repository._authorized_project.assert_called_once_with(UUID(PROJECT_ID))
        self.frappe.get_all.assert_not_called()

        self.reset_response(user="owner@example.invalid")
        self.repository.unavailable = True
        problem = self.assert_problem(
            self.call(
                "npi_core.project_controls_api.search_project_learning",
                self.api.search_project_learning,
                {
                    "projectId": PROJECT_ID,
                    "templateVersion": "not-an-integer",
                },
            ),
            404,
            "PROJECT_UNAVAILABLE",
        )
        self.assertEqual(problem["retryable"], False)

    def test_global_learning_validates_filters_even_when_access_set_is_empty(
        self,
    ) -> None:
        repository = self.repository_for()
        repository._accessible_project_ids = mock.Mock(return_value=set())
        self.frappe.get_all = mock.Mock(
            side_effect=AssertionError("An empty access set must not query.")
        )
        with self.assertRaises(RequestValidationFailed):
            repository.search_learning(
                kind="not-a-kind",
                tag=None,
                search=None,
                project_id=None,
                template_global_id=None,
                template_version=None,
                limit=50,
            )
        self.assertEqual(
            repository.search_learning(
                kind=None,
                tag=None,
                search=None,
                project_id=None,
                template_global_id=None,
                template_version=None,
                limit=50,
            ),
            {"items": []},
        )
        self.frappe.get_all.assert_not_called()

    def test_global_learning_requires_an_exact_template_pair_after_authorization(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
        )
        repository._authorized_project = mock.Mock(return_value=project)
        for template_id, template_version in (
            (TEMPLATE_ID, None),
            (None, "2"),
            (TEMPLATE_ID, "02"),
            (TEMPLATE_ID, "9" * 5000),
        ):
            with self.subTest(
                template_global_id=template_id,
                template_version=template_version,
            ):
                with self.assertRaises(RequestValidationFailed):
                    repository.search_learning(
                        kind=None,
                        tag=None,
                        search=None,
                        project_id=UUID(PROJECT_ID),
                        template_global_id=template_id,
                        template_version=template_version,
                        limit=50,
                    )

        self.reset_response(user="owner@example.invalid")
        problem = self.assert_problem(
            self.call(
                "npi_core.project_controls_api.search_project_learning",
                self.api.search_project_learning,
                {"projectId": "not-a-project-id"},
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertTrue(problem["fieldErrors"])
        self.assertEqual(self.repository.calls, [])

    def test_unknown_fields_and_unavailable_projects_are_non_leaking(
        self,
    ) -> None:
        self.reset_response(user="owner@example.invalid")
        result = self.call(
            "npi_core.project_controls_api.get_project_controls",
            self.api.get_project_controls,
            {},
            tenantId="TENANT-B",
        )
        problem = self.assert_problem(
            result,
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "tenantId")
        self.assertEqual(self.repository.calls, [])

        self.reset_response(user="owner@example.invalid")
        self.repository.unavailable = True
        result = self.call(
            "npi_core.project_controls_api.get_project_controls",
            self.api.get_project_controls,
            {},
        )
        problem = self.assert_problem(result, 404, "PROJECT_UNAVAILABLE")
        self.assertNotIn("tenant", str(problem).casefold())

    def test_router_registers_every_control_and_collaboration_route(
        self,
    ) -> None:
        routes = (
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/controls",
                "npi_core.project_controls_api.get_project_controls",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:bind-control-policy",
                ("npi_core.project_controls_api" ".bind_project_control_policy"),
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:assess-health",
                "npi_core.project_controls_api.assess_project_health",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:transition",
                "npi_core.project_controls_api.transition_project",
                {"project_id": PROJECT_ID},
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/activity",
                "npi_core.project_controls_api.get_project_activity",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/comments",
                "npi_core.project_controls_api.add_project_comment",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:follow",
                "npi_core.project_controls_api.follow_project",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}:unfollow",
                "npi_core.project_controls_api.unfollow_project",
                {"project_id": PROJECT_ID},
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/learning",
                "npi_core.project_controls_api.get_project_learning",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/learning",
                "npi_core.project_controls_api.create_project_learning",
                {"project_id": PROJECT_ID},
            ),
            (
                "GET",
                "/api/npi/v1/learning",
                "npi_core.project_controls_api.search_project_learning",
                {},
            ),
        )
        for method, path, command, route_params in routes:
            with self.subTest(method=method, path=path):
                self.reset_response()
                self.frappe.local.request = types.SimpleNamespace(
                    method=method,
                    path=path,
                )
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    command,
                )
                self.assertEqual(
                    self.frappe.flags.npi_route_params,
                    route_params,
                )
                self.assertTrue(self.frappe.flags.npi_bff_request)
                self.assertTrue(
                    self.router._requires_project_request_id(
                        method,
                        path,
                    )
                )

    def test_route_disable_switch_fails_closed_only_for_p4_05_routes(self) -> None:
        self.frappe.conf["npi_p4_05_routes_disabled"] = True
        try:
            for method, path in (
                ("GET", "/api/npi/v1/me/work"),
                ("GET", "/api/npi/v1/learning"),
                (
                    "GET",
                    f"/api/npi/v1/projects/{PROJECT_ID}/controls",
                ),
                (
                    "POST",
                    f"/api/npi/v1/projects/{PROJECT_ID}:follow",
                ),
            ):
                with self.subTest(method=method, path=path):
                    self.reset_response()
                    self.frappe.local.request = types.SimpleNamespace(
                        method=method,
                        path=path,
                    )
                    self.frappe.local.form_dict = AttrDict()
                    self.router.route_request()
                    self.assertEqual(
                        self.frappe.local.form_dict.cmd,
                        (
                            "npi_core.bff."
                            "project_collaboration_routes_disabled"
                        ),
                    )
                    self.assertEqual(
                        self.frappe.flags.npi_route_params,
                        {},
                    )

            self.reset_response()
            self.frappe.local.request = types.SimpleNamespace(
                method="GET",
                path=(
                    f"/api/npi/v1/projects/{PROJECT_ID}/work-context"
                ),
            )
            self.frappe.local.form_dict = AttrDict()
            self.router.route_request()
            self.assertEqual(
                self.frappe.local.form_dict.cmd,
                "npi_core.project_work_api.get_project_work_context",
            )

            self.reset_response(user="owner@example.invalid")
            problem = self.assert_problem(
                self.router.project_collaboration_routes_disabled(),
                503,
                "PROJECT_COLLABORATION_ROUTES_DISABLED",
            )
            self.assertTrue(problem["retryable"])
        finally:
            self.frappe.conf.pop("npi_p4_05_routes_disabled", None)

    def test_route_disable_switch_requires_an_exact_boolean(self) -> None:
        self.frappe.conf["npi_p4_05_routes_disabled"] = "true"
        try:
            self.reset_response()
            self.frappe.local.request = types.SimpleNamespace(
                method="GET",
                path="/api/npi/v1/me/work",
            )
            self.frappe.local.form_dict = AttrDict()
            self.router.route_request()
            self.assertEqual(
                self.frappe.local.form_dict.cmd,
                "npi_core.my_work_api.get_my_work",
            )
        finally:
            self.frappe.conf.pop("npi_p4_05_routes_disabled", None)

    def test_route_disable_switch_also_closes_direct_whitelisted_handlers(
        self,
    ) -> None:
        self.frappe.conf["npi_p4_05_routes_disabled"] = True
        try:
            for label, invoke in (
                (
                    "global query",
                    lambda: self.api.search_project_learning(limit="1"),
                ),
                (
                    "project controls malformed query",
                    lambda: self.api.get_project_controls(unexpected="value"),
                ),
                (
                    "project activity malformed query",
                    lambda: self.api.get_project_activity(unexpected="value"),
                ),
                (
                    "project learning malformed query",
                    lambda: self.api.get_project_learning(unexpected="value"),
                ),
                (
                    "project command",
                    lambda: self.call(
                        "npi_core.project_controls_api.follow_project",
                        self.api.follow_project,
                        {"expectedVersion": 0},
                    ),
                ),
            ):
                with self.subTest(label=label):
                    self.reset_response()
                    self.assert_problem(
                        invoke(),
                        503,
                        "PROJECT_COLLABORATION_ROUTES_DISABLED",
                    )
                    self.assertEqual(self.factory_calls, [])
                    self.assertEqual(self.repository.calls, [])
        finally:
            self.frappe.conf.pop("npi_p4_05_routes_disabled", None)

    def test_router_rejects_wrong_methods_without_generic_crud(self) -> None:
        for method, path in (
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/controls",
            ),
            (
                "PATCH",
                f"/api/npi/v1/projects/{PROJECT_ID}/learning",
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}:transition",
            ),
        ):
            with self.subTest(method=method, path=path):
                self.reset_response()
                self.frappe.local.request = types.SimpleNamespace(
                    method=method,
                    path=path,
                )
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    "npi_core.bff.route_not_found",
                )
                self.assertEqual(
                    self.frappe.flags.npi_route_params,
                    {},
                )
                self.assertTrue(self.frappe.flags.npi_bff_request)

    def repository_for(
        self,
        *,
        user_id: str = "owner@example.invalid",
        roles: frozenset[str] = frozenset({"NPI User", "NPI API User"}),
        external: bool = False,
        tenant_id: str = "TENANT-A",
    ):
        return self.original_repository_class(
            principal=Principal(
                user_id=user_id,
                roles=roles,
                is_external=external,
                tenant_id=tenant_id,
            ),
            request_id=REQUEST_ID,
            trace_id="trace-project-controls-repository",
        )

    def test_activity_uses_signed_descending_tuple_keyset_without_gaps(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules[
            "npi_core.project_controls.frappe_repository"
        ]
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            owner_user_id="owner@example.invalid",
        )

        def activity_document(global_id: str, occurred_at: str) -> AttrDict:
            payload = {
                "globalId": global_id,
                "projectGlobalId": PROJECT_ID,
                "eventType": "comment_added",
                "actorUserId": "owner@example.invalid",
                "occurredAt": occurred_at,
                "detail": {
                    "body": global_id,
                    "mentions": [],
                    "attachments": [],
                    "objectLinks": [],
                },
            }
            return AttrDict(
                global_id=global_id,
                occurred_at=occurred_at,
                payload=repository_module.canonical_json(payload),
                payload_hash=repository_module.sha256_json(payload),
            )

        ids = [str(UUID(int=value)) for value in range(1, 5)]
        documents = [
            activity_document(ids[2], "2020-01-02T12:00:00Z"),
            activity_document(ids[1], "2020-01-02T12:00:00Z"),
            activity_document(ids[0], "2020-01-02T12:00:00Z"),
            activity_document(ids[3], "2020-01-02T11:00:00Z"),
        ]
        queries: list[dict[str, object]] = []

        def get_all(doctype: str, **values: object) -> list[AttrDict]:
            self.assertEqual(doctype, "NPI Project Activity Event")
            queries.append(values)
            selected = list(documents)
            for field, operator, expected in values["filters"]:
                if field in {"tenant_id", "project_global_id"}:
                    self.assertEqual(
                        expected,
                        "TENANT-A" if field == "tenant_id" else PROJECT_ID,
                    )
                    continue
                if field == "occurred_at":
                    expected_value = repository_module._datetime_value(expected)
                    selected = [
                        document
                        for document in selected
                        if {
                            "<": repository_module._datetime_value(
                                document.occurred_at
                            )
                            < expected_value,
                            "<=": repository_module._datetime_value(
                                document.occurred_at
                            )
                            <= expected_value,
                            "=": repository_module._datetime_value(
                                document.occurred_at
                            )
                            == expected_value,
                        }[operator]
                    ]
                    continue
                self.assertEqual(field, "global_id")
                self.assertEqual(operator, "<")
                selected = [
                    document
                    for document in selected
                    if document.global_id < expected
                ]
            selected.sort(
                key=repository_module._activity_sort_key,
                reverse=True,
            )
            return selected[: int(values["limit_page_length"])]

        empty_options = {
            "truncated": False,
            "mentions": [],
            "attachments": [],
            "objectLinks": [],
        }
        self.frappe.get_all = get_all
        with (
            mock.patch.object(
                repository,
                "_authorized_project",
                return_value=project,
            ),
            mock.patch.object(
                repository,
                "_follower_document",
                return_value=None,
            ),
            mock.patch.object(
                repository,
                "_comment_options",
                return_value=empty_options,
            ),
        ):
            first = repository.activity(
                UUID(PROJECT_ID),
                cursor=None,
                limit=2,
            )
            assert first is not None
            self.assertEqual(
                [item["globalId"] for item in first["items"]],
                [ids[2], ids[1]],
            )
            self.assertIsInstance(first["nextCursor"], str)
            first_query_count = len(queries)
            second = repository.activity(
                UUID(PROJECT_ID),
                cursor=first["nextCursor"],
                limit=2,
            )

        assert second is not None
        self.assertEqual(
            [item["globalId"] for item in second["items"]],
            [ids[0], ids[3]],
        )
        self.assertIsNone(second["nextCursor"])
        self.assertEqual(
            len(
                {
                    item["globalId"]
                    for page in (first, second)
                    for item in page["items"]
                }
            ),
            4,
        )
        self.assertEqual(first_query_count, 1)
        self.assertEqual(len(queries), 3)
        self.assertTrue(
            all(query["limit_page_length"] == 3 for query in queries)
        )
        continuation_filters = queries[1]["filters"], queries[2]["filters"]
        self.assertTrue(
            any(
                ["occurred_at", "=", "2020-01-02 12:00:00.000000"]
                in filters
                and ["global_id", "<", ids[1]] in filters
                for filters in continuation_filters
            )
        )
        self.assertTrue(
            any(
                ["occurred_at", "<", "2020-01-02 12:00:00.000000"]
                in filters
                for filters in continuation_filters
            )
        )

    def test_activity_cursor_fails_closed_after_project_authorization(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules[
            "npi_core.project_controls.frappe_repository"
        ]
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            owner_user_id="owner@example.invalid",
        )
        owner_fingerprint = repository_module._project_activity_query_fingerprint(
            tenant_id="TENANT-A",
            actor_user_id="owner@example.invalid",
            project_id=UUID(PROJECT_ID),
        )
        valid_cursor = repository_module._encode_project_activity_cursor(
            (datetime(2020, 1, 2, 12, tzinfo=UTC), TEMPLATE_ID),
            as_of=datetime(2020, 1, 3, 12, tzinfo=UTC),
            query_fingerprint=owner_fingerprint,
        )
        authorization_calls: list[UUID] = []

        def authorize(project_id: UUID):
            authorization_calls.append(project_id)
            return project

        self.frappe.get_all = mock.Mock(
            side_effect=AssertionError("Activity must not be queried.")
        )
        with mock.patch.object(
            repository,
            "_authorized_project",
            side_effect=authorize,
        ):
            for cursor in (
                "malformed",
                f"{valid_cursor[:-1]}{'A' if valid_cursor[-1] != 'A' else 'B'}",
            ):
                with self.subTest(cursor=cursor):
                    with self.assertRaises(RequestValidationFailed) as raised:
                        repository.activity(
                            UUID(PROJECT_ID),
                            cursor=cursor,
                            limit=2,
                        )
                    self.assertEqual(
                        raised.exception.field_errors,
                        [
                            {
                                "path": "cursor",
                                "message": "Enter a valid cursor.",
                            }
                        ],
                    )

        other_actor = self.repository_for(
            user_id="manager@example.invalid",
            roles=frozenset({"System Manager"}),
        )
        with mock.patch.object(
            other_actor,
            "_authorized_project",
            return_value=project,
        ):
            with self.assertRaises(RequestValidationFailed):
                other_actor.activity(
                    UUID(PROJECT_ID),
                    cursor=valid_cursor,
                    limit=2,
                )
        self.assertEqual(
            authorization_calls,
            [UUID(PROJECT_ID), UUID(PROJECT_ID)],
        )
        self.frappe.get_all.assert_not_called()

        self.frappe.conf = AttrDict(npi_tenant_id="TENANT-A")
        with mock.patch.object(
            repository,
            "_authorized_project",
            return_value=project,
        ):
            with self.assertRaises(CursorSigningUnavailable):
                repository.activity(
                    UUID(PROJECT_ID),
                    cursor=None,
                    limit=2,
                )
        self.frappe.get_all.assert_not_called()

    def test_activity_integrity_binds_payload_to_persisted_timestamp(
        self,
    ) -> None:
        repository_module = sys.modules[
            "npi_core.project_controls.frappe_repository"
        ]
        payload = {
            "globalId": TEMPLATE_ID,
            "projectGlobalId": PROJECT_ID,
            "eventType": "comment_added",
            "actorUserId": "owner@example.invalid",
            "occurredAt": "2020-01-02T12:00:00Z",
            "detail": {
                "body": "Synthetic comment",
                "mentions": [],
                "attachments": [],
                "objectLinks": [],
            },
        }
        document = AttrDict(
            global_id=TEMPLATE_ID,
            occurred_at="2020-01-02T12:00:01Z",
            payload=repository_module.canonical_json(payload),
            payload_hash=repository_module.sha256_json(payload),
        )
        with self.assertRaisesRegex(
            ValueError,
            "Persisted Project activity integrity failed",
        ):
            repository_module._activity_response(
                document,
                UUID(PROJECT_ID),
            )

    def test_repository_project_scope_is_internal_tenant_and_owner_bounded(
        self,
    ) -> None:
        project = types.SimpleNamespace(
            tenant_id="TENANT-A",
            owner_user_id="owner@example.invalid",
        )
        self.assertTrue(self.repository_for()._can_view_project(project))
        self.assertFalse(
            self.repository_for(
                user_id="unrelated@example.invalid",
            )._can_view_project(project)
        )
        self.assertTrue(
            self.repository_for(
                user_id="manager@example.invalid",
                roles=frozenset({"System Manager"}),
            )._can_view_project(project)
        )
        self.assertFalse(
            self.repository_for(
                roles=frozenset({"System Manager"}),
                tenant_id="TENANT-B",
            )._can_view_project(project)
        )
        self.assertFalse(self.repository_for(external=True)._can_view_project(project))

    def test_repository_completion_sources_fail_closed(self) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(
            tenant_id="TENANT-A",
            global_id=PROJECT_ID,
        )
        count_calls: list[tuple[str, dict[str, object]]] = []

        def count(doctype: str, *, filters: dict[str, object]) -> int:
            count_calls.append((doctype, filters))
            return 1

        self.frappe.db.count = count
        self.frappe.get_all = lambda *_args, **_kwargs: []
        result = repository._resolve_prerequisites(
            project,
            (
                ProjectPrerequisiteKey.OPEN_BLOCKERS,
                ProjectPrerequisiteKey.CONTROLLED_FILES,
                ProjectPrerequisiteKey.HANDOVER,
                ProjectPrerequisiteKey.COST,
            ),
        )
        self.assertEqual(
            result,
            {
                ProjectPrerequisiteKey.OPEN_BLOCKERS: (PrerequisiteStatus.BLOCKED),
                ProjectPrerequisiteKey.CONTROLLED_FILES: (PrerequisiteStatus.SATISFIED),
                ProjectPrerequisiteKey.HANDOVER: (PrerequisiteStatus.UNAVAILABLE),
                ProjectPrerequisiteKey.COST: (PrerequisiteStatus.UNAVAILABLE),
            },
        )
        self.assertEqual(len(count_calls), 1)
        self.assertEqual(
            count_calls[0][1],
            {
                "tenant_id": "TENANT-A",
                "project_global_id": PROJECT_ID,
                "blocking": 1,
                "state_terminal": 0,
            },
        )

        self.frappe.db.count = lambda *_args, **_kwargs: 0
        self.frappe.get_all = lambda *_args, **_kwargs: [
            types.SimpleNamespace(scan_state="pending", released=0)
        ]
        result = repository._resolve_prerequisites(
            project,
            (ProjectPrerequisiteKey.CONTROLLED_FILES,),
        )
        self.assertEqual(
            result[ProjectPrerequisiteKey.CONTROLLED_FILES],
            PrerequisiteStatus.BLOCKED,
        )

    def test_controls_without_policy_never_claim_health_or_readiness(
        self,
    ) -> None:
        repository = self.repository_for(
            user_id="manager@example.invalid",
            roles=frozenset({"System Manager"}),
        )
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            business_code="SYN-P405",
            title="Synthetic Project",
            lifecycle_state="active",
            optimistic_version=4,
            owner_user_id="owner@example.invalid",
            control_binding_global_id=None,
            current_health_snapshot=None,
            current_health_status="unassessed",
        )
        response = repository._controls_response(project)
        self.assertIsNone(response["policy"])
        self.assertIsNone(response["binding"])
        self.assertEqual(
            response["health"]["overallStatus"],
            "unassessed",
        )
        self.assertIsNone(response["health"]["assessment"])
        self.assertEqual(
            {
                (
                    dimension["dimension"],
                    dimension["ruleMode"],
                    dimension["status"],
                )
                for dimension in response["health"]["dimensions"]
            },
            {
                ("progress", "unavailable", "unassessed"),
                ("cost", "unavailable", "unassessed"),
                ("quality", "unavailable", "unassessed"),
                ("risk", "unavailable", "unassessed"),
            },
        )
        self.assertTrue(response["permissions"]["canBindPolicy"])
        self.assertEqual(
            response["bindingOptions"],
            {"policies": [], "eligibleMembers": []},
        )
        self.assertFalse(response["permissions"]["canAssessHealth"])
        self.assertFalse(response["permissions"]["canTransition"])
        self.assertTrue(
            all(
                action["available"] is False
                and action["reasonCode"] == "policy_missing"
                for action in response["lifecycleActions"]
            )
        )

        project.lifecycle_state = "completed"
        terminal = repository._controls_response(project)
        self.assertFalse(terminal["permissions"]["canBindPolicy"])
        self.assertIsNone(terminal["bindingOptions"])
        self.assertTrue(
            all(
                action["available"] is False
                and action["reasonCode"] == "project_terminal"
                for action in terminal["lifecycleActions"]
            )
        )

    def test_controls_hide_commands_without_the_transport_role(
        self,
    ) -> None:
        repository = self.repository_for(roles=frozenset({"NPI User"}))
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            business_code="SYN-P405",
            title="Synthetic Project",
            lifecycle_state="active",
            optimistic_version=4,
            owner_user_id="owner@example.invalid",
            control_binding_global_id=TEMPLATE_ID,
            control_binding_version=1,
            current_health_snapshot=None,
            current_health_status="unassessed",
        )
        policy = types.SimpleNamespace(
            policy_global_id=UUID(POLICY_ID),
            policy_code="project_control",
            policy_version=3,
            snapshot_hash="a" * 64,
            health_assessment_slot="project_controller",
            health_rules=tuple(
                types.SimpleNamespace(
                    dimension=dimension,
                    mode=HealthRuleMode.MANUAL,
                )
                for dimension in HealthDimension
            ),
            transition=lambda _state, _action: types.SimpleNamespace(
                authority_slot="project_controller",
                prerequisites=(),
            ),
        )
        binding = types.SimpleNamespace(global_id=UUID(TEMPLATE_ID))
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        persisted_bindings = [
            {
                "slot": "project_controller",
                "memberGlobalId": MEMBER_ID,
                "userId": "owner@example.invalid",
                "displayName": "Project Owner",
            }
        ]
        with (
            mock.patch.object(
                repository,
                "_current_policy",
                return_value=(policy, {"schemaVersion": 1}),
            ),
            mock.patch.object(
                repository,
                "_current_binding",
                return_value=(binding, persisted_bindings),
            ),
            mock.patch.object(
                repository,
                "_resolve_prerequisites",
            ) as prerequisites,
            mock.patch.object(
                repository_module,
                "_optional_doc",
                return_value=None,
            ),
        ):
            response = repository._controls_response(project)
        prerequisites.assert_not_called()
        self.assertFalse(response["permissions"]["canAssessHealth"])
        self.assertFalse(response["permissions"]["canTransition"])
        self.assertTrue(
            all(
                action["available"] is False
                and action["reasonCode"] == "command_access_required"
                and action["prerequisites"] == []
                for action in response["lifecycleActions"]
            )
        )

    def test_binding_options_are_exact_bounded_server_resolved_choices(
        self,
    ) -> None:
        repository = self.repository_for(
            user_id="manager@example.invalid",
            roles=frozenset({"System Manager"}),
        )
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            owner_user_id="owner@example.invalid",
        )
        calls: list[tuple[str, dict[str, object]]] = []

        def get_all(doctype: str, **values: object):
            calls.append((doctype, values))
            if doctype == "NPI Project Control Policy":
                return [POLICY_ID]
            if doctype == "NPI Project Control Policy Version":
                return [
                    AttrDict(
                        policy_global_id=POLICY_ID,
                        policy_code="project_control",
                        policy_version=3,
                        snapshot_hash="a" * 64,
                        title="Published project control",
                    )
                ]
            if doctype == "NPI Project Member":
                return [
                    AttrDict(
                        global_id=MEMBER_ID,
                        user_id="owner@example.invalid",
                        effective_from="2020-01-01",
                        effective_to=None,
                    ),
                    AttrDict(
                        global_id=TEMPLATE_ID,
                        user_id="expired@example.invalid",
                        effective_from="2020-01-01",
                        effective_to="2020-12-31",
                    ),
                ]
            raise AssertionError(doctype)

        self.frappe.get_all = get_all
        self.frappe.db.get_value = lambda *_args, **_kwargs: AttrDict(
            enabled=1,
            user_type="System User",
            full_name="Project Owner",
        )
        policy = types.SimpleNamespace(
            policy_global_id=UUID(POLICY_ID),
            policy_version=3,
            policy_code="project_control",
            authority_slots=("project_controller", "project_manager"),
        )
        with mock.patch.object(
            repository,
            "_load_policy",
            return_value=(policy, {"schemaVersion": 1}),
        ) as load:
            options = repository._binding_options(project)

        self.assertEqual(
            options,
            {
                "policies": [
                    {
                        "policyRef": {
                            "globalId": POLICY_ID,
                            "version": 3,
                            "snapshotHash": "a" * 64,
                        },
                        "code": "project_control",
                        "title": "Published project control",
                        "authoritySlots": [
                            "project_controller",
                            "project_manager",
                        ],
                    }
                ],
                "eligibleMembers": [
                    {
                        "memberGlobalId": MEMBER_ID,
                        "userId": "owner@example.invalid",
                        "displayName": "Project Owner",
                    }
                ],
            },
        )
        load.assert_called_once_with(
            {
                "globalId": POLICY_ID,
                "version": 3,
                "snapshotHash": "a" * 64,
            }
        )
        self.assertEqual(
            [doctype for doctype, _values in calls],
            [
                "NPI Project Control Policy",
                "NPI Project Control Policy Version",
                "NPI Project Member",
            ],
        )
        version_filters = calls[1][1]["filters"]
        self.assertEqual(
            version_filters,
            {
                "project_control_policy": ["in", [POLICY_ID]],
                "publication_state": "published",
            },
        )

    def test_authority_binding_rejects_a_member_without_control_route_access(
        self,
    ) -> None:
        repository = self.repository_for(
            user_id="manager@example.invalid",
            roles=frozenset({"System Manager"}),
        )
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            owner_user_id="owner@example.invalid",
        )
        policy = types.SimpleNamespace(authority_slots=("project_controller",))
        member = types.SimpleNamespace(
            global_id=MEMBER_ID,
            user_id="reviewer@example.invalid",
        )
        with mock.patch.object(
            repository,
            "_active_internal_member",
            return_value=member,
        ):
            with self.assertRaises(RequestValidationFailed) as raised:
                repository._resolve_authorities(
                    project,
                    policy,
                    [
                        {
                            "slot": "project_controller",
                            "memberGlobalId": MEMBER_ID,
                        }
                    ],
                )
        self.assertEqual(
            raised.exception.field_errors[0]["path"],
            "bindings.project_controller",
        )

    def test_comment_options_are_server_resolved_and_url_free(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            business_code="SYN-P405",
            title="Synthetic Project",
            optimistic_version=8,
        )

        def get_all(doctype: str, **_values: object):
            if doctype == "NPI Project Member":
                return [
                    AttrDict(
                        global_id=MEMBER_ID,
                        user_id="owner@example.invalid",
                        effective_from="2020-01-01",
                        effective_to=None,
                    )
                ]
            if doctype in {
                "NPI File Revision",
                "NPI Gate Shell",
                "NPI Domain Work Item",
                "NPI Project Learning",
            }:
                return []
            raise AssertionError(doctype)

        self.frappe.get_all = get_all
        self.frappe.db.get_value = lambda *_args, **_kwargs: AttrDict(
            enabled=1,
            user_type="System User",
            full_name="Project Owner",
        )
        options = repository._comment_options(project)
        self.assertFalse(options["truncated"])
        self.assertEqual(
            options["mentions"],
            [
                {
                    "memberGlobalId": MEMBER_ID,
                    "userId": "owner@example.invalid",
                    "displayName": "Project Owner",
                }
            ],
        )
        self.assertEqual(options["attachments"], [])
        self.assertEqual(
            options["objectLinks"],
            [
                {
                    "type": "project",
                    "globalId": PROJECT_ID,
                    "version": 8,
                    "code": "SYN-P405",
                    "title": "Synthetic Project",
                    "target": {
                        "kind": "project",
                        "projectId": PROJECT_ID,
                    },
                }
            ],
        )
        self.assertNotIn("url", str(options).casefold())

    def test_comment_options_truncate_choices_without_hiding_activity(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            business_code="SYN-P405",
            title="Synthetic Project",
            optimistic_version=8,
        )
        member_rows = [
            AttrDict(
                global_id=str(UUID(int=index + 1)),
                user_id=f"member-{index:03d}@example.invalid",
                effective_from="2020-01-01",
                effective_to=None,
            )
            for index in range(501)
        ]

        def get_all(doctype: str, **_values: object):
            if doctype == "NPI Project Member":
                return member_rows
            if doctype in {
                "NPI File Revision",
                "NPI Gate Shell",
                "NPI Domain Work Item",
                "NPI Project Learning",
            }:
                return []
            raise AssertionError(doctype)

        self.frappe.get_all = get_all
        self.frappe.db.get_value = lambda *_args, **_kwargs: AttrDict(
            enabled=1,
            user_type="System User",
            full_name="Eligible Project Member",
        )
        options = repository._comment_options(project)
        self.assertTrue(options["truncated"])
        self.assertEqual(len(options["mentions"]), 500)
        self.assertEqual(
            options["mentions"][0]["userId"],
            "member-000@example.invalid",
        )
        self.assertEqual(
            options["mentions"][-1]["userId"],
            "member-499@example.invalid",
        )
        self.assertEqual(
            [(value["type"], value["globalId"]) for value in options["objectLinks"]],
            [("project", PROJECT_ID)],
        )

    def test_project_learning_resolves_exact_identity_after_project_access(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            owner_user_id="owner@example.invalid",
        )
        calls: list[dict[str, object]] = []

        def get_all(doctype: str, **values: object):
            self.assertEqual(doctype, "NPI Project Learning")
            calls.append(values)
            return []

        self.frappe.get_all = get_all
        with mock.patch.object(
            repository,
            "_authorized_project",
            return_value=project,
        ) as authorize:
            response = repository.project_learning(
                UUID(PROJECT_ID),
                kind=None,
                search=None,
                learning_id=TEMPLATE_ID,
                limit=10,
            )
        authorize.assert_called_once_with(UUID(PROJECT_ID))
        self.assertEqual(
            calls[0]["filters"],
            [
                ["tenant_id", "=", "TENANT-A"],
                ["project_global_id", "=", PROJECT_ID],
                ["global_id", "=", TEMPLATE_ID],
            ],
        )
        self.assertEqual(calls[0]["limit_page_length"], 2)
        self.assertIsNone(response)

        self.reset_response(user="owner@example.invalid")
        self.repository.unavailable = True
        problem = self.assert_problem(
            self.call(
                "npi_core.project_controls_api.get_project_learning",
                self.api.get_project_learning,
                {"learningId": TEMPLATE_ID, "limit": 1},
            ),
            404,
            "PROJECT_UNAVAILABLE",
        )
        self.assertFalse(problem["retryable"])

    def test_project_learning_exact_identity_rejects_additional_filters(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            owner_user_id="owner@example.invalid",
        )
        with mock.patch.object(
            repository,
            "_authorized_project",
            return_value=project,
        ):
            with self.assertRaises(RequestValidationFailed):
                repository.project_learning(
                    UUID(PROJECT_ID),
                    kind="lesson",
                    search=None,
                    learning_id=TEMPLATE_ID,
                    limit=1,
                )

    def test_project_version_shape_is_422_and_only_staleness_is_409(
        self,
    ) -> None:
        repository_module = sys.modules[
            "npi_core.project_controls.frappe_repository"
        ]
        project = types.SimpleNamespace(optimistic_version=4)
        for invalid in (None, True, 0, -1, "4"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RequestValidationFailed) as problem:
                    repository_module._require_project_version(
                        project,
                        invalid,
                    )
                self.assertEqual(
                    problem.exception.field_errors[0]["path"],
                    "expectedProjectVersion",
                )
        with self.assertRaises(VersionConflict):
            repository_module._require_project_version(project, 3)
        repository_module._require_project_version(project, 4)

    def test_comment_options_omit_a_stale_live_file_without_hiding_activity(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            business_code="SYN-P405",
            title="Synthetic Project",
            optimistic_version=8,
        )
        revision = types.SimpleNamespace(
            global_id=TEMPLATE_ID,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
        )

        def get_all(doctype: str, **_values: object):
            if doctype == "NPI File Revision":
                return [TEMPLATE_ID]
            if doctype in {
                "NPI Project Member",
                "NPI Gate Shell",
                "NPI Domain Work Item",
                "NPI Project Learning",
            }:
                return []
            raise AssertionError(doctype)

        self.frappe.get_all = get_all
        with (
            mock.patch.object(
                repository_module,
                "_optional_doc",
                return_value=revision,
            ),
            mock.patch.object(
                repository_module,
                "has_live_private_file_identity",
                return_value=False,
            ),
        ):
            options = repository._comment_options(project)
        self.assertFalse(options["truncated"])
        self.assertEqual(options["attachments"], [])
        self.assertEqual(
            [(value["type"], value["globalId"]) for value in options["objectLinks"]],
            [("project", PROJECT_ID)],
        )

    def test_gate_object_link_derives_tenant_from_authorized_project(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            business_code="SYN-P405",
            title="Synthetic Project",
            optimistic_version=8,
        )
        gate = types.SimpleNamespace(
            global_id=TEMPLATE_ID,
            project_global_id=PROJECT_ID,
            optimistic_version=3,
            gate_key="G1",
            title="Design Gate",
        )
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        with mock.patch.object(
            repository_module,
            "_optional_doc",
            return_value=gate,
        ):
            result = repository._resolve_object_link(
                project,
                "gate",
                UUID(TEMPLATE_ID),
                3,
                path="objectLinks[0]",
            )
        self.assertEqual(
            result,
            {
                "type": "gate",
                "globalId": TEMPLATE_ID,
                "version": 3,
                "code": "G1",
                "title": "Design Gate",
            },
        )

    def test_file_comment_references_require_the_live_private_file_identity(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
        )
        revision = types.SimpleNamespace(
            global_id=TEMPLATE_ID,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            optimistic_version=3,
            revision=1,
            file_name="controlled.pdf",
        )
        snapshot = {
            "globalId": TEMPLATE_ID,
            "fileOptimisticVersion": 3,
            "fileName": "controlled.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 42,
            "sha256": "a" * 64,
            "scanState": "clean",
            "isPrivate": True,
        }
        with (
            mock.patch.object(
                repository_module,
                "_optional_doc",
                return_value=revision,
            ),
            mock.patch.object(
                repository_module,
                "file_revision_source_snapshot",
                return_value=snapshot,
            ),
            mock.patch.object(
                repository_module,
                "has_live_private_file_identity",
                return_value=False,
            ),
        ):
            with self.assertRaises(RequestValidationFailed):
                repository._resolve_attachments(
                    project,
                    [{"globalId": TEMPLATE_ID, "version": 3}],
                )
            with self.assertRaises(RequestValidationFailed):
                repository._resolve_object_link(
                    project,
                    "file_revision",
                    UUID(TEMPLATE_ID),
                    3,
                    path="objectLinks[0]",
                )

    def test_missing_or_malformed_command_arrays_are_controlled_422_inputs(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(lifecycle_state="active")
        cases = (
            (
                "bindings",
                lambda: repository.bind_policy(
                    UUID(PROJECT_ID),
                    idempotency_key="a" * 64,
                    expected_project_version=1,
                    policy_ref={},
                    bindings=None,  # type: ignore[arg-type]
                ),
            ),
            (
                "measurements",
                lambda: repository.assess_health(
                    UUID(PROJECT_ID),
                    idempotency_key="b" * 64,
                    expected_project_version=1,
                    measurements=7,  # type: ignore[arg-type]
                    reason=None,
                    recovery_plan=None,
                ),
            ),
            (
                "mentions",
                lambda: repository.add_comment(
                    UUID(PROJECT_ID),
                    idempotency_key="c" * 64,
                    body="Invalid array inputs must not become HTTP 500.",
                    mentions="owner@example.invalid",  # type: ignore[arg-type]
                    attachments=[],
                    object_links=[],
                ),
            ),
            (
                "tags",
                lambda: repository.create_learning(
                    UUID(PROJECT_ID),
                    idempotency_key="d" * 64,
                    kind="lesson",
                    title="Controlled validation",
                    content="Reject a missing array before hashing it.",
                    recommendation=None,
                    tags=None,  # type: ignore[arg-type]
                ),
            ),
        )
        with (
            mock.patch.object(
                repository,
                "_locked_authorized_project",
                return_value=project,
            ),
            mock.patch.object(repository, "_idempotency_replay") as replay,
        ):
            for expected_path, operation in cases:
                with self.subTest(expected_path=expected_path):
                    with self.assertRaises(RequestValidationFailed) as raised:
                        operation()
                    self.assertEqual(
                        raised.exception.field_errors[0]["path"],
                        expected_path,
                    )
        replay.assert_not_called()

    def test_unfollow_without_a_follower_does_not_create_false_history(
        self,
    ) -> None:
        repository = self.repository_for()
        project = types.SimpleNamespace(lifecycle_state="active")
        with (
            mock.patch.object(
                repository,
                "_locked_authorized_project",
                return_value=project,
            ),
            mock.patch.object(
                repository,
                "_idempotency_replay",
                return_value=None,
            ),
            mock.patch.object(
                repository,
                "_follower_document",
                return_value=None,
            ),
        ):
            with self.assertRaises(RequestValidationFailed) as raised:
                repository.set_following(
                    UUID(PROJECT_ID),
                    idempotency_key="e" * 64,
                    expected_version=0,
                    active=False,
                )
        self.assertEqual(
            raised.exception.field_errors[0]["path"],
            "active",
        )

    def test_idempotency_replay_is_payload_bound_and_must_be_sealed(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        first_hash = repository_module._payload_hash(
            {"projectId": PROJECT_ID, "action": "pause"}
        )
        second_hash = repository_module._payload_hash(
            {"action": "pause", "projectId": PROJECT_ID}
        )
        self.assertEqual(first_hash, second_hash)

        self.frappe.db.get_value = lambda *_args, **_kwargs: AttrDict(
            payload_hash=first_hash,
            response_json='{"projectId":"' + PROJECT_ID + '"}',
            response_sealed=1,
        )
        self.assertEqual(
            repository._idempotency_replay("a" * 64, first_hash),
            {"projectId": PROJECT_ID},
        )

        with self.assertRaises(IdempotencyConflict):
            repository._idempotency_replay("a" * 64, "b" * 64)

        self.frappe.db.get_value = lambda *_args, **_kwargs: AttrDict(
            payload_hash=first_hash,
            response_json="{}",
            response_sealed=0,
        )
        with self.assertRaisesRegex(RuntimeError, "unsealed"):
            repository._idempotency_replay("a" * 64, first_hash)

    def test_sealed_control_replays_survive_a_later_terminal_project_state(
        self,
    ) -> None:
        repository = self.repository_for()
        terminal_project = types.SimpleNamespace(lifecycle_state="cancelled")
        replay = {"project": {"globalId": PROJECT_ID, "state": "cancelled"}}

        with (
            mock.patch.object(
                repository,
                "_locked_authorized_project",
                return_value=terminal_project,
            ),
            mock.patch.object(
                repository,
                "_idempotency_replay",
                return_value=replay,
            ),
        ):
            outcomes = (
                repository.bind_policy(
                    UUID(PROJECT_ID),
                    idempotency_key="a" * 64,
                    expected_project_version=3,
                    policy_ref={},
                    bindings=[],
                ),
                repository.assess_health(
                    UUID(PROJECT_ID),
                    idempotency_key="b" * 64,
                    expected_project_version=3,
                    measurements=[],
                    reason=None,
                    recovery_plan=None,
                ),
                repository.transition(
                    UUID(PROJECT_ID),
                    idempotency_key="c" * 64,
                    expected_project_version=3,
                    action="cancel",
                    reason="Preserve the sealed terminal command response.",
                ),
            )

        self.assertTrue(all(outcome is not None for outcome in outcomes))
        self.assertTrue(all(outcome.replayed for outcome in outcomes if outcome))
        self.assertTrue(
            all(outcome.response == replay for outcome in outcomes if outcome)
        )

    def test_binding_reads_fail_closed_when_snapshot_or_columns_drift(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        authority_bindings = [
            {
                "slot": "project_controller",
                "memberGlobalId": MEMBER_ID,
                "userId": "owner@example.invalid",
                "displayName": "Project Owner",
            }
        ]
        snapshot = {
            "schemaVersion": 1,
            "globalId": TEMPLATE_ID,
            "tenantId": "TENANT-A",
            "projectGlobalId": PROJECT_ID,
            "bindingVersion": 2,
            "policyRef": {
                "globalId": POLICY_ID,
                "version": 3,
                "snapshotHash": "a" * 64,
            },
            "policySnapshotHash": "a" * 64,
            "authorityBindings": authority_bindings,
            "boundBy": "Administrator",
            "boundAt": "2026-07-25T10:00:00Z",
            "projectVersion": 7,
            "requestId": REQUEST_ID,
            "traceId": "trace-project-controls-repository",
        }
        document = types.SimpleNamespace(
            global_id=TEMPLATE_ID,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            binding_version=2,
            policy_global_id=POLICY_ID,
            policy_version=3,
            policy_snapshot_hash="a" * 64,
            authority_bindings=copy.deepcopy(authority_bindings),
            bound_by="Administrator",
            bound_at="2026-07-25T10:00:00Z",
            project_version=7,
            request_id=REQUEST_ID,
            trace_id="trace-project-controls-repository",
            binding_snapshot=snapshot,
            snapshot_hash=repository_module.sha256_json(snapshot),
        )
        self.assertEqual(
            repository_module._validated_binding_snapshot(document),
            snapshot,
        )

        project = types.SimpleNamespace(
            global_id=PROJECT_ID,
            tenant_id="TENANT-A",
            control_binding_global_id=TEMPLATE_ID,
            control_binding_version=2,
        )
        policy = types.SimpleNamespace(
            policy_global_id=UUID(POLICY_ID),
            policy_version=3,
            snapshot_hash="a" * 64,
        )
        document.authority_bindings = []
        with mock.patch.object(
            repository_module,
            "_optional_doc",
            return_value=document,
        ):
            with self.assertRaisesRegex(ValueError, "bindings drifted"):
                repository._current_binding(project, policy)

        document.authority_bindings = copy.deepcopy(authority_bindings)
        document.snapshot_hash = "b" * 64
        with self.assertRaisesRegex(ValueError, "Binding snapshot failed"):
            repository_module._validated_binding_snapshot(document)

    def test_learning_reads_fail_closed_when_snapshot_or_columns_drift(
        self,
    ) -> None:
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        snapshot = {
            "schemaVersion": 1,
            "globalId": TEMPLATE_ID,
            "tenantId": "TENANT-A",
            "projectGlobalId": PROJECT_ID,
            "kind": "lesson",
            "title": "Frozen lesson",
            "content": "Use the immutable learning record.",
            "recommendation": "",
            "tags": ["governance"],
            "templateGlobalId": POLICY_ID,
            "templateVersion": 4,
            "templateSnapshotHash": "c" * 64,
            "createdBy": "Administrator",
            "createdAt": "2026-07-25T10:01:00Z",
            "requestId": REQUEST_ID,
            "traceId": "trace-project-controls-repository",
        }
        document = types.SimpleNamespace(
            global_id=TEMPLATE_ID,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            kind="lesson",
            title="Frozen lesson",
            content="Use the immutable learning record.",
            recommendation=None,
            tags=["governance"],
            template_global_id=POLICY_ID,
            template_version=4,
            template_snapshot_hash="c" * 64,
            created_by="Administrator",
            created_at="2026-07-25T10:01:00Z",
            request_id=REQUEST_ID,
            trace_id="trace-project-controls-repository",
            optimistic_version=1,
            record_snapshot=snapshot,
            snapshot_hash=repository_module.sha256_json(snapshot),
        )
        response = repository_module._learning_response(document)
        self.assertEqual(response["globalId"], TEMPLATE_ID)
        self.assertEqual(response["title"], "Frozen lesson")

        document.title = "Drifted lesson"
        with self.assertRaisesRegex(ValueError, "Learning snapshot failed"):
            repository_module._learning_response(document)

        document.title = "Frozen lesson"
        document.snapshot_hash = "d" * 64
        with self.assertRaisesRegex(ValueError, "Learning snapshot failed"):
            repository_module._learning_response(document)

    def test_disabled_policy_root_blocks_new_binding_not_frozen_history(
        self,
    ) -> None:
        repository = self.repository_for()
        repository_module = sys.modules["npi_core.project_controls.frappe_repository"]
        payload = {"frozen": True}
        snapshot_hash = repository_module.sha256_json(payload)
        version = types.SimpleNamespace(
            publication_state="published",
            policy_global_id=POLICY_ID,
            policy_version=1,
            snapshot_hash=snapshot_hash,
            project_control_policy=POLICY_ID,
            policy_code="project_control",
            snapshot=payload,
        )
        root = types.SimpleNamespace(
            global_id=POLICY_ID,
            policy_code="project_control",
            enabled=0,
        )

        def optional_doc(doctype: str, _name: str):
            return version if doctype == "NPI Project Control Policy Version" else root

        reference = {
            "globalId": POLICY_ID,
            "version": 1,
            "snapshotHash": snapshot_hash,
        }
        with (
            mock.patch.object(
                repository_module,
                "_optional_doc",
                side_effect=optional_doc,
            ),
            mock.patch.object(
                repository_module,
                "_policy_from_snapshot",
                return_value="frozen-policy",
            ),
        ):
            with self.assertRaises(repository_module.ProjectControlPolicyUnavailable):
                repository._load_policy(reference)
            self.assertEqual(
                repository._load_policy(
                    reference,
                    require_enabled_root=False,
                ),
                ("frozen-policy", payload),
            )

        default = (
            inspect.signature(self.original_repository_class._load_policy)
            .parameters["require_enabled_root"]
            .default
        )
        self.assertIs(default, True)
        bind_source = inspect.getsource(self.original_repository_class.bind_policy)
        self.assertIn(
            "self._load_policy(policy_ref)",
            bind_source,
        )

        project = types.SimpleNamespace(
            control_binding_global_id=TEMPLATE_ID,
            control_policy_global_id=POLICY_ID,
            control_policy_version=1,
            control_policy_snapshot_hash=snapshot_hash,
        )
        with mock.patch.object(
            repository,
            "_load_policy",
            return_value=("frozen-policy", payload),
        ) as load:
            self.assertEqual(
                repository._current_policy(project),
                ("frozen-policy", payload),
            )
            load.assert_called_once_with(
                reference,
                require_enabled_root=False,
            )


if __name__ == "__main__":
    unittest.main()
