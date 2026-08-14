from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
POLICY_ID = "0878087f-6192-4e40-862d-05e0a5927638"
HANDOVER_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
HANDOVER_REVISION_ID = "6dd227c4-2c74-4f2f-a3ce-347497758118"
OBSERVATION_ID = "a8ab6f87-227f-42f9-a7cb-d695e8d34bca"
MEMBER_A_ID = "99d03125-7947-4a72-a94f-47930cfcb7bb"
MEMBER_B_ID = "b898fb3d-cf5b-4817-9ca5-a2244d35ad40"
ROLE_A_ID = "527628b7-0d9a-42b1-b0bf-ad71c913b489"
ROLE_B_ID = "77c1291f-c81e-4209-80ae-3ab62ee106d6"
SOURCE_ID = "c8dfa1ca-6c0d-4c74-9bf2-12cbba12998e"
TARGET_ID = "e2d6233b-952a-49ae-aa87-952e89127989"
REQUEST_ID = "5dc0ef7b-8563-46ad-9f40-76dd474566ea"
SHA256_A = "a" * 64
SHA256_B = "b" * 64


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self, owner: "Phase7ProductionTransitionApiTest") -> None:
        self.owner = owner
        self.rollback_count = 0

    def get_value(self, doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return self.owner.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self) -> None:
        self.available = True
        self.replayed: object = False
        self.target_global_id: object = TARGET_ID
        self.failure: Exception | None = None
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def policy_catalog(self, *args: object, **kwargs: Any):
        return self._query("policy_catalog", args, kwargs)

    def create_policy(self, *args: object, **kwargs: Any):
        return self._command("create_policy", args, kwargs)

    def edit_policy(self, *args: object, **kwargs: Any):
        return self._command("edit_policy", args, kwargs)

    def publish_policy(self, *args: object, **kwargs: Any):
        return self._command("publish_policy", args, kwargs)

    def create_policy_version(self, *args: object, **kwargs: Any):
        return self._command("create_policy_version", args, kwargs)

    def production_transition_workspace(self, *args: object, **kwargs: Any):
        return self._query("production_transition_workspace", args, kwargs)

    def create_handover(self, *args: object, **kwargs: Any):
        return self._command("create_handover", args, kwargs)

    def revise_handover(self, *args: object, **kwargs: Any):
        return self._command("revise_handover", args, kwargs)

    def acknowledge_handover(self, *args: object, **kwargs: Any):
        return self._command("acknowledge_handover", args, kwargs)

    def create_observation(self, *args: object, **kwargs: Any):
        return self._command("create_observation", args, kwargs)

    def revise_observation(self, *args: object, **kwargs: Any):
        return self._command("revise_observation", args, kwargs)

    def _query(
        self,
        name: str,
        args: tuple[object, ...],
        kwargs: dict[str, Any],
    ):
        self.calls.append((name, args, kwargs))
        if self.failure is not None:
            raise self.failure
        if not self.available:
            return None
        return {"query": name}

    def _command(
        self,
        name: str,
        args: tuple[object, ...],
        kwargs: dict[str, Any],
    ):
        self.calls.append((name, args, kwargs))
        if self.failure is not None:
            raise self.failure
        if not self.available:
            return None
        return types.SimpleNamespace(
            response={"command": name},
            replayed=self.replayed,
            target_global_id=self.target_global_id,
        )


def policy_definition() -> dict[str, Any]:
    metric_dispositions = ["not_evaluable", "within_rule", "outside_rule"]
    return {
        "applicability": {
            "projectTypes": ["new_tool"],
            "projectGlobalIds": [],
            "customerReferenceKeys": [],
        },
        "receivingGroups": [
            {"key": "npi_sender", "title": "NPI sender group"},
            {
                "key": "production_receiver",
                "title": "Production receiving group",
            },
        ],
        "acknowledgementSlots": [
            {
                "key": "sender",
                "groupKey": "npi_sender",
                "direction": "sender",
                "allowedProjectRoleKeys": ["npi_owner"],
            },
            {
                "key": "receiver",
                "groupKey": "production_receiver",
                "direction": "receiver",
                "allowedProjectRoleKeys": ["production_receiver"],
            },
        ],
        "handoverRequirements": [
            {
                "key": "open_work",
                "acceptedSourceKinds": ["domain_work_item"],
                "manifestRole": "unresolved_action",
                "minimumCount": 1,
            }
        ],
        "observationSourceRules": [
            {
                "providerKind": "actual_sop",
                "unit": None,
                "comparator": None,
                "threshold": None,
                "allowedDispositions": ["not_evaluable"],
            },
            {
                "providerKind": "customer_complaint",
                "unit": "count",
                "comparator": "less_than_or_equal",
                "threshold": "1",
                "allowedDispositions": metric_dispositions,
            },
            {
                "providerKind": "first_batch_yield",
                "unit": "percent",
                "comparator": "greater_than_or_equal",
                "threshold": "95",
                "allowedDispositions": metric_dispositions,
            },
            {
                "providerKind": "production_cycle_time",
                "unit": "second",
                "comparator": "less_than_or_equal",
                "threshold": "60",
                "allowedDispositions": metric_dispositions,
            },
            {
                "providerKind": "tooling_stability",
                "unit": "count",
                "comparator": "less_than_or_equal",
                "threshold": "0",
                "allowedDispositions": metric_dispositions,
            },
        ],
        "observationWindowDays": 30,
    }


def policy_ref() -> dict[str, Any]:
    return {
        "policyGlobalId": POLICY_ID,
        "policyVersion": 1,
        "policySnapshotHash": SHA256_A,
    }


def handover_content() -> dict[str, Any]:
    return {
        "expectedProjectVersion": 7,
        "policy": policy_ref(),
        "slotAssignments": [
            {
                "slotKey": "sender",
                "memberGlobalId": MEMBER_A_ID,
                "memberExpectedVersion": 2,
                "roleAssignmentGlobalId": ROLE_A_ID,
                "roleExpectedVersion": 3,
            },
            {
                "slotKey": "receiver",
                "memberGlobalId": MEMBER_B_ID,
                "memberExpectedVersion": 2,
                "roleAssignmentGlobalId": ROLE_B_ID,
                "roleExpectedVersion": 3,
            },
        ],
        "manifestSources": [
            {
                "requirementKey": "open_work",
                "kind": "domain_work_item",
                "globalId": SOURCE_ID,
                "expectedVersion": 4,
            }
        ],
        "reason": "Freeze exact technical handover evidence.",
    }


def observation_create() -> dict[str, Any]:
    return {
        "expectedProjectVersion": 7,
        "policy": policy_ref(),
        "handover": {
            "handoverGlobalId": HANDOVER_ID,
            "handoverVersion": 1,
            "handoverRevisionGlobalId": HANDOVER_REVISION_ID,
            "handoverSnapshotHash": SHA256_B,
        },
        "contextSources": [
            {
                "kind": "domain_work_item",
                "globalId": SOURCE_ID,
                "expectedVersion": 4,
            }
        ],
        "retrospectiveSources": [],
        "retrospectiveNote": None,
        "reason": "Open the independent technical observation period.",
    }


class Phase7ProductionTransitionApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.production_transition_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.headers = {
            "Idempotency-Key": "p7-production-transition-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-" + "a" * 32,
        }
        self.roles = {
            "admin@example.invalid": ["System Manager"],
            "reader@example.invalid": ["NPI API User"],
            "dual-role@example.invalid": ["System Manager", "NPI API User"],
            "ordinary@example.invalid": [],
            "external@example.invalid": ["System Manager", "NPI API User"],
        }
        self.user_types = {
            "admin@example.invalid": "System User",
            "reader@example.invalid": "System User",
            "dual-role@example.invalid": "System User",
            "ordinary@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="admin@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p7_01_routes_disabled=False,
            npi_p7_02_routes_disabled=False,
            npi_p7_03_routes_disabled=False,
            npi_p7_04_routes_disabled=False,
            npi_p7_05_routes_disabled=False,
            npi_p7_06_routes_disabled=False,
        )
        self.frappe.flags = AttrDict(
            npi_bff_request=False,
            npi_route_params=self.route_params(),
        )
        self.frappe.local = types.SimpleNamespace(
            response=AttrDict(),
            form_dict=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
        )
        self.frappe.request = self.frappe.local.request
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda user: self.roles.get(user, [])
        self.frappe.db = StubDatabase(self)
        self.frappe.log_error = lambda **_values: None
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda *_args, **_kwargs: None
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + "a" * 48
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.sessions"] = sessions

        self.api = importlib.import_module("npi_core.production_transition_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository()
        self.factory_calls: list[dict[str, Any]] = []
        self.validation_calls: list[tuple[str, object, dict[str, Any]]] = []
        self.validation_failure: Exception | None = None

        def repository_factory(**values: Any):
            self.factory_calls.append(values)
            return self.repository

        self.api._repository_factory = repository_factory

        def validate_command(operation: str, value: object, **values: Any):
            self.validation_calls.append((operation, copy.deepcopy(value), values))
            if self.validation_failure is not None:
                raise self.validation_failure
            return copy.deepcopy(value)

        def validate_query(value: object, **values: Any):
            self.validation_calls.append(("query", copy.deepcopy(value), values))
            if self.validation_failure is not None:
                raise self.validation_failure
            return copy.deepcopy(value)

        self.api.validate_command_response = validate_command
        self.api.validate_policy_catalog_response = validate_query
        self.api.validate_workspace_response = validate_query

    def tearDown(self) -> None:
        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    @staticmethod
    def route_params() -> AttrDict:
        return AttrDict(
            project_id=PROJECT_ID,
            policy_id=POLICY_ID,
            policy_version="1",
            handover_id=HANDOVER_ID,
            handover_version="1",
            observation_id=OBSERVATION_ID,
        )

    def reset_response(self) -> None:
        self.frappe.local.response = AttrDict()
        self.frappe.local.form_dict = AttrDict()
        self.frappe.flags.npi_bff_request = False
        self.frappe.flags.npi_route_params = self.route_params()
        self.frappe.flags.pop("npi_response_headers", None)
        self.frappe.flags.pop("npi_response_body", None)

    def invoke(self, function, payload: dict[str, Any] | None = None):
        self.reset_response()
        values = copy.deepcopy(payload or {})
        self.frappe.local.form_dict = AttrDict(values)
        return function(**values)

    def route(self, method: str, path: str) -> tuple[str, dict[str, str]]:
        self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
        self.frappe.request = self.frappe.local.request
        self.frappe.local.form_dict = AttrDict()
        self.frappe.flags.npi_route_params = AttrDict()
        self.router.route_request()
        return (
            self.frappe.local.form_dict.cmd,
            dict(self.frappe.flags.npi_route_params),
        )

    def assert_problem(
        self,
        response: object,
        status: int,
        code: str,
    ) -> dict[str, Any]:
        self.assertIsInstance(response, dict)
        assert isinstance(response, dict)
        self.assertEqual(response["status"], status)
        self.assertEqual(response["code"], code)
        self.assertEqual(self.frappe.local.response.http_status_code, status)
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        self.assertEqual(headers["X-Trace-ID"], response["traceId"])
        self.assertIn("X-Request-ID", headers)
        return response

    @staticmethod
    def route_matrix() -> tuple[tuple[str, str, str, dict[str, str]], ...]:
        prefix = "npi_core.production_transition_api."
        return (
            (
                "GET",
                "/api/npi/v1/production-transition/policies",
                prefix + "list_eligible_production_transition_policies",
                {},
            ),
            (
                "POST",
                "/api/npi/v1/production-transition/policies",
                prefix + "create_production_transition_policy_draft",
                {},
            ),
            (
                "PUT",
                f"/api/npi/v1/production-transition/policies/{POLICY_ID}/versions/1",
                prefix + "edit_production_transition_policy_draft",
                {"policy_id": POLICY_ID, "policy_version": "1"},
            ),
            (
                "POST",
                f"/api/npi/v1/production-transition/policies/{POLICY_ID}/versions/1:publish",
                prefix + "publish_production_transition_policy_version",
                {"policy_id": POLICY_ID, "policy_version": "1"},
            ),
            (
                "POST",
                f"/api/npi/v1/production-transition/policies/{POLICY_ID}/versions",
                prefix + "create_next_production_transition_policy_version",
                {"policy_id": POLICY_ID},
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/production-transition",
                prefix + "get_project_production_transition_workspace",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/production-handover",
                prefix + "create_production_handover_package",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/production-handover/{HANDOVER_ID}/revisions",
                prefix + "revise_production_handover_package",
                {"project_id": PROJECT_ID, "handover_id": HANDOVER_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/production-handover/{HANDOVER_ID}/revisions/1/acknowledgements",
                prefix + "acknowledge_production_handover_slot",
                {
                    "project_id": PROJECT_ID,
                    "handover_id": HANDOVER_ID,
                    "handover_version": "1",
                },
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/observation-periods",
                prefix + "create_observation_period",
                {"project_id": PROJECT_ID},
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/observation-periods/{OBSERVATION_ID}/revisions",
                prefix + "revise_observation_period",
                {"project_id": PROJECT_ID, "observation_id": OBSERVATION_ID},
            ),
        )

    @staticmethod
    def handler_matrix() -> tuple[tuple[str, str, dict[str, Any], int], ...]:
        create_policy = {
            "policyCode": "PROD-TRANSITION",
            "title": "Production transition policy",
            "definition": policy_definition(),
        }
        edit_policy = {
            "expectedOptimisticVersion": 1,
            "title": "Edited production transition policy",
            "definition": policy_definition(),
        }
        publish_policy = {
            "expectedOptimisticVersion": 1,
            "expectedSnapshotHash": SHA256_A,
        }
        next_policy = {
            "expectedPublishedVersion": 1,
            "expectedPublishedSnapshotHash": SHA256_A,
        }
        revise_handover = {
            "expectedRevisionGlobalId": HANDOVER_REVISION_ID,
            "expectedSnapshotHash": SHA256_B,
            "content": handover_content(),
        }
        acknowledgement = {
            "expectedRevisionGlobalId": HANDOVER_REVISION_ID,
            "expectedSnapshotHash": SHA256_B,
            "slotKey": "sender",
            "intent": "acknowledge",
        }
        revise_observation = {
            "expectedRevisionGlobalId": HANDOVER_REVISION_ID,
            "expectedSnapshotHash": SHA256_B,
            "contextSources": observation_create()["contextSources"],
            "retrospectiveSources": [],
            "retrospectiveNote": "Reviewed exact NPI context.",
            "reason": "Append an immutable technical review.",
        }
        return (
            (
                "list_eligible_production_transition_policies",
                "policy_catalog",
                {"projectId": PROJECT_ID},
                200,
            ),
            (
                "create_production_transition_policy_draft",
                "create_policy",
                create_policy,
                201,
            ),
            (
                "edit_production_transition_policy_draft",
                "edit_policy",
                edit_policy,
                200,
            ),
            (
                "publish_production_transition_policy_version",
                "publish_policy",
                publish_policy,
                200,
            ),
            (
                "create_next_production_transition_policy_version",
                "create_policy_version",
                next_policy,
                201,
            ),
            (
                "get_project_production_transition_workspace",
                "production_transition_workspace",
                {},
                200,
            ),
            (
                "create_production_handover_package",
                "create_handover",
                handover_content(),
                201,
            ),
            (
                "revise_production_handover_package",
                "revise_handover",
                revise_handover,
                201,
            ),
            (
                "acknowledge_production_handover_slot",
                "acknowledge_handover",
                acknowledgement,
                201,
            ),
            (
                "create_observation_period",
                "create_observation",
                observation_create(),
                201,
            ),
            (
                "revise_observation_period",
                "revise_observation",
                revise_observation,
                201,
            ),
        )

    def test_bff_maps_exactly_the_eleven_frozen_method_routes(self) -> None:
        for method, path, expected, params in self.route_matrix():
            with self.subTest(method=method, path=path):
                command, actual_params = self.route(method, path)
                self.assertEqual(command, expected)
                self.assertEqual(actual_params, params)
        malformed = (
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}:bad/production-transition",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/production-handover/{HANDOVER_ID}:bad/revisions",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/observation-periods/{OBSERVATION_ID}/revisions/extra",
            ),
            ("DELETE", "/api/npi/v1/production-transition/policies"),
            ("POST", "/api/npi/v1/NPI Handover Package Revision"),
        )
        for method, path in malformed:
            with self.subTest(method=method, path=path):
                command, params = self.route(method, path)
                self.assertEqual(command, "npi_core.bff.route_not_found")
                self.assertEqual(params, {})

    def test_p706_switch_is_independent_and_only_exact_false_enables(self) -> None:
        sample = self.route_matrix()[5][:2]
        for value in (None, True, 0, "false"):
            with self.subTest(value=value):
                if value is None:
                    self.frappe.conf.pop("npi_p7_06_routes_disabled", None)
                else:
                    self.frappe.conf.npi_p7_06_routes_disabled = value
                command, params = self.route(*sample)
                self.assertEqual(
                    command,
                    "npi_core.production_transition_api.production_transition_routes_disabled",
                )
                self.assertEqual(params, {})
        self.frappe.conf.npi_p7_06_routes_disabled = False
        for earlier in (
            "npi_p7_01_routes_disabled",
            "npi_p7_02_routes_disabled",
            "npi_p7_03_routes_disabled",
            "npi_p7_04_routes_disabled",
            "npi_p7_05_routes_disabled",
        ):
            self.frappe.conf[earlier] = True
        self.assertEqual(
            self.route(*sample)[0],
            "npi_core.production_transition_api.get_project_production_transition_workspace",
        )

    def test_direct_switch_guard_precedes_authentication_and_body_parsing(self) -> None:
        self.frappe.conf.pop("npi_p7_06_routes_disabled")
        self.frappe.session.user = "Guest"
        response = self.invoke(
            self.api.create_production_transition_policy_draft,
            {"unexpected": {"externalActual": 1}},
        )
        self.assert_problem(response, 503, "PRODUCTION_TRANSITION_ROUTES_DISABLED")
        self.assertEqual(self.repository.calls, [])
        self.assertEqual(self.factory_calls, [])

    def test_authentication_csrf_and_role_precede_closed_body_validation(self) -> None:
        invalid = {"unexpected": "caller-owned-truth"}
        self.frappe.session.user = "Guest"
        self.assert_problem(
            self.invoke(self.api.create_production_transition_policy_draft, invalid),
            401,
            "AUTHENTICATION_REQUIRED",
        )
        self.frappe.session.user = "admin@example.invalid"
        self.headers.pop("X-Frappe-CSRF-Token")
        self.assert_problem(
            self.invoke(self.api.create_production_transition_policy_draft, invalid),
            403,
            "CSRF_TOKEN_INVALID",
        )
        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + "a" * 48
        self.frappe.session.user = "reader@example.invalid"
        self.assert_problem(
            self.invoke(self.api.create_production_transition_policy_draft, invalid),
            403,
            "PERMISSION_DENIED",
        )
        self.frappe.session.user = "admin@example.invalid"
        response = self.invoke(
            self.api.create_production_transition_policy_draft,
            invalid,
        )
        problem = self.assert_problem(response, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "unexpected")
        self.assertEqual(self.repository.calls, [])

    def test_read_role_and_actor_bound_acknowledgement_have_no_admin_proxy(self) -> None:
        self.frappe.session.user = "admin@example.invalid"
        self.assert_problem(
            self.invoke(
                self.api.list_eligible_production_transition_policies,
                {"projectId": PROJECT_ID},
            ),
            403,
            "PERMISSION_DENIED",
        )
        self.assert_problem(
            self.invoke(
                self.api.acknowledge_production_handover_slot,
                self.handler_matrix()[8][2],
            ),
            403,
            "PERMISSION_DENIED",
        )
        self.frappe.session.user = "reader@example.invalid"
        response = self.invoke(
            self.api.acknowledge_production_handover_slot,
            self.handler_matrix()[8][2],
        )
        self.assertEqual(response, {"command": "acknowledge_handover"})
        request = self.repository.calls[-1][2]["request"]
        self.assertEqual(request.slot_key, "sender")
        self.assertFalse(hasattr(request, "actor_user_id"))
        self.frappe.session.user = "external@example.invalid"
        self.assert_problem(
            self.invoke(
                self.api.get_project_production_transition_workspace,
                {},
            ),
            403,
            "PERMISSION_DENIED",
        )

    def test_nested_payloads_are_closed_and_caller_truth_never_reaches_repository(
        self,
    ) -> None:
        payload = handover_content()
        payload["manifestSources"][0]["snapshotHash"] = SHA256_A
        self.assert_problem(
            self.invoke(self.api.create_production_handover_package, payload),
            422,
            "VALIDATION_FAILED",
        )
        payload = observation_create()
        payload["actualSop"] = {"observedAt": "2026-08-14", "value": "pass"}
        self.assert_problem(
            self.invoke(self.api.create_observation_period, payload),
            422,
            "VALIDATION_FAILED",
        )
        payload = self.handler_matrix()[8][2]
        payload["fullyAcknowledged"] = True
        self.frappe.session.user = "reader@example.invalid"
        self.assert_problem(
            self.invoke(self.api.acknowledge_production_handover_slot, payload),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(self.repository.calls, [])

    def test_success_status_headers_factory_context_and_typed_repository_calls(
        self,
    ) -> None:
        for handler_name, call_name, payload, status in self.handler_matrix():
            with self.subTest(handler=handler_name):
                self.repository.calls.clear()
                self.factory_calls.clear()
                self.validation_calls.clear()
                self.frappe.session.user = (
                    "reader@example.invalid"
                    if handler_name
                    in {
                        "list_eligible_production_transition_policies",
                        "get_project_production_transition_workspace",
                        "acknowledge_production_handover_slot",
                    }
                    else "admin@example.invalid"
                )
                response = self.invoke(getattr(self.api, handler_name), payload)
                self.assertEqual(
                    response,
                    {"query": call_name}
                    if status == 200 and call_name in {
                        "policy_catalog",
                        "production_transition_workspace",
                    }
                    else {"command": call_name},
                )
                self.assertEqual(self.frappe.local.response.http_status_code, status)
                headers = self.frappe.flags.npi_response_headers
                self.assertEqual(headers["X-Request-ID"], REQUEST_ID)
                self.assertEqual(headers["X-Trace-ID"], self.headers["X-Trace-ID"])
                self.assertEqual(headers["Cache-Control"], "private, no-store")
                if call_name not in {
                    "policy_catalog",
                    "production_transition_workspace",
                }:
                    self.assertEqual(headers["Idempotency-Replayed"], "false")
                    self.assertIn("request", self.repository.calls[0][2])
                    self.assertEqual(
                        len(self.repository.calls[0][2]["idempotency_key_hash"]),
                        64,
                    )
                else:
                    self.assertNotIn("Idempotency-Replayed", headers)
                self.assertEqual(self.repository.calls[0][0], call_name)
                self.assertEqual(self.factory_calls[0]["request_id"], REQUEST_ID)
                self.assertEqual(
                    self.factory_calls[0]["trace_id"],
                    self.headers["X-Trace-ID"],
                )
                self.assertEqual(
                    self.validation_calls[-1][2]["tenant_id"],
                    "TENANT-A",
                )

    def test_route_and_request_identity_bindings_reach_response_validator(self) -> None:
        self.invoke(
            self.api.publish_production_transition_policy_version,
            self.handler_matrix()[3][2],
        )
        operation, _response, bindings = self.validation_calls[-1]
        self.assertEqual(operation, "production_transition_policy.publish")
        self.assertEqual(bindings["target_global_id"], TARGET_ID)
        self.assertEqual(bindings["policy_global_id"], UUID(POLICY_ID))
        self.assertEqual(bindings["policy_version"], 1)
        self.assertEqual(bindings["policy_snapshot_hash"], SHA256_A)
        self.assertEqual(bindings["tenant_id"], "TENANT-A")

        self.validation_calls.clear()
        self.frappe.session.user = "reader@example.invalid"
        self.invoke(
            self.api.acknowledge_production_handover_slot,
            self.handler_matrix()[8][2],
        )
        operation, _response, bindings = self.validation_calls[-1]
        self.assertEqual(operation, "production_handover.acknowledge")
        self.assertEqual(bindings["project_global_id"], UUID(PROJECT_ID))
        self.assertEqual(bindings["handover_global_id"], UUID(HANDOVER_ID))
        self.assertEqual(bindings["handover_version"], 1)
        self.assertEqual(
            bindings["handover_revision_global_id"],
            UUID(HANDOVER_REVISION_ID),
        )
        self.assertEqual(bindings["handover_snapshot_hash"], SHA256_B)
        self.assertEqual(bindings["slot_key"], "sender")

        self.validation_calls.clear()
        self.frappe.session.user = "admin@example.invalid"
        self.invoke(self.api.create_observation_period, observation_create())
        operation, _response, bindings = self.validation_calls[-1]
        self.assertEqual(operation, "observation_period.create")
        self.assertEqual(bindings["policy_global_id"], UUID(POLICY_ID))
        self.assertEqual(bindings["handover_global_id"], UUID(HANDOVER_ID))
        self.assertEqual(
            bindings["handover_revision_global_id"],
            UUID(HANDOVER_REVISION_ID),
        )

    def test_replay_is_actor_bound_and_header_uses_only_boolean_outcome(self) -> None:
        from npi_core.project.domain import actor_idempotency_key_hash

        payload = self.handler_matrix()[1][2]
        self.repository.replayed = True
        self.invoke(self.api.create_production_transition_policy_draft, payload)
        first_hash = self.repository.calls[-1][2]["idempotency_key_hash"]
        self.assertEqual(
            first_hash,
            actor_idempotency_key_hash(
                "admin@example.invalid",
                self.headers["Idempotency-Key"],
            ),
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )
        self.frappe.session.user = "dual-role@example.invalid"
        self.invoke(self.api.create_production_transition_policy_draft, payload)
        second_hash = self.repository.calls[-1][2]["idempotency_key_hash"]
        self.assertNotEqual(first_hash, second_hash)

    def test_closed_errors_rollback_and_do_not_expose_or_claim_success(self) -> None:
        payload = self.handler_matrix()[1][2]
        self.repository.available = False
        response = self.invoke(
            self.api.create_production_transition_policy_draft,
            payload,
        )
        self.assert_problem(
            response,
            404,
            "PRODUCTION_TRANSITION_POLICY_UNAVAILABLE",
        )
        self.assertEqual(self.frappe.db.rollback_count, 1)

        self.repository.available = True
        self.repository.failure = RuntimeError("secret database value")
        response = self.invoke(
            self.api.create_production_transition_policy_draft,
            payload,
        )
        problem = self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.assertNotIn("secret", str(problem))
        self.repository.failure = None

        self.validation_failure = RuntimeError("tampered response")
        response = self.invoke(
            self.api.create_production_transition_policy_draft,
            payload,
        )
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")
        self.validation_failure = None

        self.repository.replayed = "true"
        response = self.invoke(
            self.api.create_production_transition_policy_draft,
            payload,
        )
        self.assert_problem(response, 500, "INTERNAL_SERVER_ERROR")

    def test_bad_request_id_and_opaque_route_ids_fail_before_repository_method(self) -> None:
        self.headers["X-Request-ID"] = "not-a-request-id"
        response = self.invoke(
            self.api.create_production_transition_policy_draft,
            self.handler_matrix()[1][2],
        )
        self.assert_problem(response, 422, "VALIDATION_FAILED")
        self.assertNotEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            "not-a-request-id",
        )
        self.assertEqual(self.repository.calls, [])

        self.headers["X-Request-ID"] = REQUEST_ID
        self.reset_response()
        self.frappe.flags.npi_route_params.handover_id = "not-a-uuid"
        payload = copy.deepcopy(self.handler_matrix()[7][2])
        self.frappe.local.form_dict = AttrDict(payload)
        response = self.api.revise_production_handover_package(**payload)
        self.assert_problem(response, 404, "PRODUCTION_TRANSITION_UNAVAILABLE")
        self.assertEqual(self.repository.calls, [])

    def test_whitelists_request_ids_and_no_raw_doctype_route_surface(self) -> None:
        expected_methods = {
            "list_eligible_production_transition_policies": ("GET",),
            "create_production_transition_policy_draft": ("POST",),
            "edit_production_transition_policy_draft": ("PUT",),
            "publish_production_transition_policy_version": ("POST",),
            "create_next_production_transition_policy_version": ("POST",),
            "get_project_production_transition_workspace": ("GET",),
            "create_production_handover_package": ("POST",),
            "revise_production_handover_package": ("POST",),
            "acknowledge_production_handover_slot": ("POST",),
            "create_observation_period": ("POST",),
            "revise_observation_period": ("POST",),
        }
        for name, methods in expected_methods.items():
            with self.subTest(name=name):
                handler = getattr(self.api, name)
                self.assertTrue(handler.allow_guest)
                self.assertEqual(handler.allowed_methods, methods)
        for method, path, _command, _params in self.route_matrix():
            self.assertTrue(self.router._requires_project_request_id(method, path))
        self.assertFalse(
            self.router._requires_project_request_id(
                "POST",
                "/api/npi/v1/NPI%20Handover%20Package%20Revision",
            )
        )


if __name__ == "__main__":
    unittest.main()
