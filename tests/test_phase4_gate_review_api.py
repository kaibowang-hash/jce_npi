from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
GATE_ID = "62d6ac02-b85f-4ae0-a522-953c4ebc2de4"
CYCLE_ID = "7bdd76f9-0bbb-4b56-81e8-d958893997c7"
EXCEPTION_ID = "0c15b8b7-9794-45a8-a2c5-e7e6762e0400"
POLICY_ID = "fe383856-e1ab-471a-949a-bb645e68f503"
MEMBER_ID = "44f7b429-a527-4304-865d-d61e6a42320b"
REQUIREMENT_ID = "c22af769-32b3-4ae4-b9b3-b6b9f3e75e52"
ACTION_ID = "01583735-0612-4ca2-8d45-ea9f6f845a77"
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


class MockGateReviewRepository:
    def __init__(self, owner: "Phase4GateReviewApiTest") -> None:
        self.owner = owner
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []
        self.unavailable = False
        self.replayed = False
        self.deny_business_authority = False

    def _read(self, operation: str, *identities: object) -> dict[str, Any] | None:
        self.calls.append((operation, identities, {}))
        if self.unavailable:
            return None
        return copy.deepcopy(self.owner.workspace)

    def _write(
        self,
        operation: str,
        *identities: object,
        **values: Any,
    ):
        self.calls.append((operation, identities, values))
        if self.deny_business_authority:
            raise self.owner.api.PermissionDenied()
        if self.unavailable:
            return None
        return types.SimpleNamespace(
            response=copy.deepcopy(self.owner.workspace),
            replayed=self.replayed,
        )

    def review_workspace(self, project_id: UUID, gate_id: UUID):
        return self._read("workspace", project_id, gate_id)

    def start_review(self, project_id: UUID, gate_id: UUID, **values: Any):
        return self._write("start", project_id, gate_id, **values)

    def submit_review(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        **values: Any,
    ):
        return self._write(
            "review",
            project_id,
            gate_id,
            cycle_id,
            **values,
        )

    def request_exception(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        **values: Any,
    ):
        return self._write(
            "request_exception",
            project_id,
            gate_id,
            cycle_id,
            **values,
        )

    def decide_exception(
        self,
        project_id: UUID,
        gate_id: UUID,
        cycle_id: UUID,
        exception_id: UUID,
        **values: Any,
    ):
        return self._write(
            "decide_exception",
            project_id,
            gate_id,
            cycle_id,
            exception_id,
            **values,
        )

    def decide_gate(self, project_id: UUID, gate_id: UUID, **values: Any):
        return self._write("decide", project_id, gate_id, **values)

    def reopen_gate(self, project_id: UUID, gate_id: UUID, **values: Any):
        return self._write("reopen", project_id, gate_id, **values)


class Phase4GateReviewApiTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.sessions",
        "npi_core.gate_evidence_api",
        "npi_core.gate_review_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.headers = {
            "Idempotency-Key": "p4-gate-review-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase4-gate-review-api",
        }
        self.roles = {
            "Administrator": ["System Manager"],
            "manager@example.invalid": ["System Manager"],
            "reviewer@example.invalid": ["NPI API User"],
            "manager-transport@example.invalid": [
                "System Manager",
                "NPI API User",
            ],
            "ordinary@example.invalid": ["NPI User"],
            "external-reviewer@example.invalid": ["NPI API User"],
        }
        self.user_types = {
            "Administrator": "System User",
            "manager@example.invalid": "System User",
            "reviewer@example.invalid": "System User",
            "manager-transport@example.invalid": "System User",
            "ordinary@example.invalid": "System User",
            "external-reviewer@example.invalid": "Website User",
        }

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="Administrator")
        self.frappe.conf = AttrDict(npi_tenant_id="TENANT-A")
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "gate_id": GATE_ID,
            },
        )
        self.frappe.local = types.SimpleNamespace(
            response=StubResponse(),
            request=types.SimpleNamespace(path="/", method="GET"),
            form_dict=AttrDict(),
        )
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda user: self.roles.get(user, [])
        self.frappe.db = StubDatabase(self.user_types)
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
        sessions.get_csrf_token = lambda: "csrf-" + ("a" * 48)
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.sessions"] = sessions

        self.api = importlib.import_module("npi_core.gate_review_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockGateReviewRepository(self)
        self.factory_calls: list[dict[str, Any]] = []

        def repository_factory(**values: Any):
            self.factory_calls.append(values)
            return self.repository

        self.api._repository_factory = repository_factory
        self.workspace = {
            "project": {"globalId": PROJECT_ID},
            "gate": {"globalId": GATE_ID, "reviewState": "in_review"},
            "evidence": {
                "requirements": [
                    {
                        "globalId": REQUIREMENT_ID,
                        "key": "drawing",
                    }
                ]
            },
            "activeCycle": {
                "globalId": CYCLE_ID,
                "state": "decided",
                "version": 5,
                "inputHash": "b" * 64,
                "policyRef": {
                    "globalId": POLICY_ID,
                    "version": 1,
                    "snapshotHash": "a" * 64,
                },
                "bindings": [
                    {
                        "slot": "engineering_reviewer",
                        "memberGlobalId": MEMBER_ID,
                        "userId": "reviewer@example.invalid",
                        "displayName": "Synthetic Reviewer",
                    }
                ],
            },
            "decisions": [],
            "availablePolicies": [
                {
                    "policyRef": {
                        "globalId": POLICY_ID,
                        "version": 1,
                        "snapshotHash": "a" * 64,
                    },
                    "authoritySlots": [
                        {
                            "slot": "engineering_reviewer",
                            "purpose": "review",
                        }
                    ],
                    "exceptionRules": [],
                }
            ],
            "eligibleMembers": [
                {
                    "memberGlobalId": MEMBER_ID,
                    "userId": "reviewer@example.invalid",
                    "displayName": "Synthetic Reviewer",
                }
            ],
            "eligibleClosureActions": [
                {
                    "globalId": ACTION_ID,
                    "title": "Close the exception",
                    "state": "open",
                    "version": 1,
                }
            ],
            "blockers": [
                {
                    "globalId": ACTION_ID,
                    "kind": "action",
                    "title": "Resolve the active blocker",
                    "state": "open",
                    "dueAt": "2026-08-31T12:00:00Z",
                    "owner": "reviewer@example.invalid",
                }
            ],
            "permissions": {},
        }

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def reset_response(
        self,
        *,
        user: str = "Administrator",
        route_params: dict[str, str] | None = None,
    ) -> None:
        self.frappe.session.user = user
        self.frappe.local.response = StubResponse()
        self.frappe.local.form_dict = AttrDict()
        self.frappe.flags.npi_bff_request = False
        self.frappe.flags.npi_response_headers = None
        self.frappe.flags.npi_response_body = None
        self.frappe.flags.npi_route_params = route_params or {
            "project_id": PROJECT_ID,
            "gate_id": GATE_ID,
        }
        self.repository.calls.clear()
        self.factory_calls.clear()

    def call(
        self,
        command: str,
        function,
        payload: dict[str, Any],
        **extra: Any,
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
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        UUID(headers["X-Request-ID"])
        return result

    @staticmethod
    def bindings() -> list[dict[str, object]]:
        return [
            {
                "slot": "engineering_reviewer",
                "memberGlobalId": MEMBER_ID,
            }
        ]

    @classmethod
    def start_payload(cls) -> dict[str, object]:
        return {
            "expectedGateVersion": 2,
            "policyGlobalId": POLICY_ID,
            "policyVersion": 1,
            "policySnapshotHash": "a" * 64,
            "bindings": cls.bindings(),
        }

    @staticmethod
    def review_payload() -> dict[str, object]:
        return {
            "expectedCycleVersion": 1,
            "expectedInputHash": "b" * 64,
            "stepKey": "engineering",
            "outcome": "approved",
            "opinion": "Reviewed against the frozen input.",
        }

    @staticmethod
    def exception_payload() -> dict[str, object]:
        return {
            "expectedCycleVersion": 2,
            "expectedInputHash": "b" * 64,
            "requirementGlobalId": REQUIREMENT_ID,
            "requirementKey": "drawing",
            "kind": "timing",
            "reason": "The signed report will arrive after this review.",
            "risk": "The release could proceed without the final signature.",
            "expiresAt": "2026-08-31T12:00:00Z",
            "closureActionGlobalId": ACTION_ID,
        }

    @staticmethod
    def decide_exception_payload() -> dict[str, object]:
        return {
            "expectedCycleVersion": 3,
            "expectedExceptionVersion": 1,
            "expectedInputHash": "b" * 64,
            "outcome": "approved",
            "opinion": "Approved with the exact closure action.",
        }

    @staticmethod
    def decide_payload() -> dict[str, object]:
        return {
            "expectedGateVersion": 4,
            "expectedCycleVersion": 4,
            "expectedInputHash": "b" * 64,
            "outcome": "conditional_pass",
        }

    @classmethod
    def reopen_payload(cls) -> dict[str, object]:
        return {
            "expectedGateVersion": 5,
            "expectedCycleVersion": 5,
            "expectedInputHash": "b" * 64,
            "reason": "A controlled input changed after the prior decision.",
            "policyGlobalId": POLICY_ID,
            "policyVersion": 1,
            "policySnapshotHash": "a" * 64,
            "bindings": cls.bindings(),
        }

    def test_query_is_authenticated_and_delegates_idor_safe_resolution(self) -> None:
        self.reset_response(user="ordinary@example.invalid")
        result = self.call(
            "npi_core.gate_review_api.get_gate_review",
            self.api.get_gate_review,
            {},
        )
        self.assertEqual(result, self.workspace)
        self.assertEqual(
            self.repository.calls,
            [
                (
                    "workspace",
                    (UUID(PROJECT_ID), UUID(GATE_ID)),
                    {},
                )
            ],
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )

        self.reset_response(user="Guest")
        self.assert_problem(
            self.call(
                "npi_core.gate_review_api.get_gate_review",
                self.api.get_gate_review,
                {},
            ),
            401,
            "AUTHENTICATION_REQUIRED",
        )

    def test_query_preserves_server_resolved_command_construction_options(
        self,
    ) -> None:
        self.reset_response(user="ordinary@example.invalid")
        result = self.call(
            "npi_core.gate_review_api.get_gate_review",
            self.api.get_gate_review,
            {},
        )
        assert isinstance(result, dict)
        self.assertEqual(
            result["evidence"]["requirements"][0]["globalId"],
            REQUIREMENT_ID,
        )
        self.assertEqual(result["activeCycle"]["state"], "decided")
        self.assertEqual(
            result["activeCycle"]["bindings"][0]["memberGlobalId"],
            MEMBER_ID,
        )
        self.assertEqual(
            result["availablePolicies"][0]["policyRef"]["globalId"],
            POLICY_ID,
        )
        self.assertEqual(
            result["eligibleMembers"][0]["memberGlobalId"],
            MEMBER_ID,
        )
        self.assertEqual(
            result["eligibleClosureActions"][0]["globalId"],
            ACTION_ID,
        )
        self.assertEqual(result["blockers"][0]["kind"], "action")

    def test_start_review_is_system_manager_only_and_exactly_typed(self) -> None:
        result = self.call(
            "npi_core.gate_review_api.start_gate_review",
            self.api.start_gate_review,
            self.start_payload(),
        )
        self.assertEqual(result, self.workspace)
        operation, identities, values = self.repository.calls[-1]
        self.assertEqual(operation, "start")
        self.assertEqual(identities, (UUID(PROJECT_ID), UUID(GATE_ID)))
        self.assertEqual(values["expected_gate_version"], 2)
        self.assertEqual(values["policy_global_id"], UUID(POLICY_ID))
        self.assertEqual(values["policy_version"], 1)
        self.assertEqual(values["policy_snapshot_hash"], "a" * 64)
        self.assertEqual(
            values["bindings"],
            (
                {
                    "slot": "engineering_reviewer",
                    "member_global_id": UUID(MEMBER_ID),
                },
            ),
        )
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(len(values["idempotency_key"]), 64)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "false",
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )

        self.reset_response(user="reviewer@example.invalid")
        self.assert_problem(
            self.call(
                "npi_core.gate_review_api.start_gate_review",
                self.api.start_gate_review,
                self.start_payload(),
            ),
            403,
            "PERMISSION_DENIED",
        )
        self.assertEqual(self.factory_calls, [])

    def test_transport_role_precedes_repository_and_is_not_authority(self) -> None:
        route = {
            "project_id": PROJECT_ID,
            "gate_id": GATE_ID,
            "cycle_id": CYCLE_ID,
        }
        for user in (
            "manager@example.invalid",
            "ordinary@example.invalid",
            "external-reviewer@example.invalid",
        ):
            with self.subTest(user=user):
                self.reset_response(user=user, route_params=route)
                invalid = self.review_payload()
                invalid["decisionSnapshot"] = {"forged": True}
                self.assert_problem(
                    self.call(
                        "npi_core.gate_review_api.submit_gate_review",
                        self.api.submit_gate_review,
                        invalid,
                    ),
                    403,
                    "PERMISSION_DENIED",
                )
                self.assertEqual(self.factory_calls, [])
                self.assertEqual(self.repository.calls, [])

        self.reset_response(user="reviewer@example.invalid", route_params=route)
        self.repository.deny_business_authority = True
        self.assert_problem(
            self.call(
                "npi_core.gate_review_api.submit_gate_review",
                self.api.submit_gate_review,
                self.review_payload(),
            ),
            403,
            "PERMISSION_DENIED",
        )
        self.assertEqual(len(self.factory_calls), 1)
        self.assertEqual(self.repository.calls[-1][0], "review")
        self.repository.deny_business_authority = False

    def test_review_and_exception_commands_pass_only_typed_preconditions(self) -> None:
        cycle_route = {
            "project_id": PROJECT_ID,
            "gate_id": GATE_ID,
            "cycle_id": CYCLE_ID,
        }
        self.reset_response(
            user="reviewer@example.invalid",
            route_params=cycle_route,
        )
        result = self.call(
            "npi_core.gate_review_api.submit_gate_review",
            self.api.submit_gate_review,
            self.review_payload(),
        )
        self.assertEqual(result, self.workspace)
        operation, identities, values = self.repository.calls[-1]
        self.assertEqual(operation, "review")
        self.assertEqual(
            identities,
            (UUID(PROJECT_ID), UUID(GATE_ID), UUID(CYCLE_ID)),
        )
        self.assertEqual(values["expected_cycle_version"], 1)
        self.assertEqual(values["expected_input_hash"], "b" * 64)
        self.assertEqual(values["step_key"], "engineering")
        self.assertEqual(values["outcome"], "approved")
        self.assertEqual(
            values["opinion"],
            "Reviewed against the frozen input.",
        )

        self.reset_response(
            user="reviewer@example.invalid",
            route_params=cycle_route,
        )
        result = self.call(
            "npi_core.gate_review_api.request_gate_review_exception",
            self.api.request_gate_review_exception,
            self.exception_payload(),
        )
        self.assertEqual(result, self.workspace)
        operation, identities, values = self.repository.calls[-1]
        self.assertEqual(operation, "request_exception")
        self.assertEqual(
            identities,
            (UUID(PROJECT_ID), UUID(GATE_ID), UUID(CYCLE_ID)),
        )
        self.assertEqual(values["requirement_global_id"], UUID(REQUIREMENT_ID))
        self.assertEqual(values["closure_action_global_id"], UUID(ACTION_ID))
        self.assertEqual(
            values["expires_at"],
            datetime(2026, 8, 31, 12, tzinfo=UTC),
        )

    def test_exception_decision_gate_decision_and_reopen_are_separate(self) -> None:
        exception_route = {
            "project_id": PROJECT_ID,
            "gate_id": GATE_ID,
            "cycle_id": CYCLE_ID,
            "exception_id": EXCEPTION_ID,
        }
        self.reset_response(
            user="reviewer@example.invalid",
            route_params=exception_route,
        )
        self.call(
            "npi_core.gate_review_api.decide_gate_review_exception",
            self.api.decide_gate_review_exception,
            self.decide_exception_payload(),
        )
        operation, identities, values = self.repository.calls[-1]
        self.assertEqual(operation, "decide_exception")
        self.assertEqual(
            identities,
            (
                UUID(PROJECT_ID),
                UUID(GATE_ID),
                UUID(CYCLE_ID),
                UUID(EXCEPTION_ID),
            ),
        )
        self.assertEqual(values["expected_exception_version"], 1)
        self.assertEqual(values["expected_input_hash"], "b" * 64)

        self.reset_response(user="reviewer@example.invalid")
        self.call(
            "npi_core.gate_review_api.decide_gate",
            self.api.decide_gate,
            self.decide_payload(),
        )
        self.assertEqual(self.repository.calls[-1][0], "decide")
        self.assertEqual(
            self.repository.calls[-1][2]["outcome"],
            "conditional_pass",
        )

        self.reset_response(user="reviewer@example.invalid")
        self.call(
            "npi_core.gate_review_api.reopen_gate",
            self.api.reopen_gate,
            self.reopen_payload(),
        )
        self.assertEqual(self.repository.calls[-1][0], "reopen")
        self.assertEqual(self.frappe.local.response.http_status_code, 201)

    def test_closed_payloads_reject_forged_state_and_reopen_decision(self) -> None:
        cases = (
            (
                self.api.start_gate_review,
                "npi_core.gate_review_api.start_gate_review",
                self.start_payload(),
                "decisionSnapshot",
                {"forged": True},
                "manager@example.invalid",
                {},
            ),
            (
                self.api.submit_gate_review,
                "npi_core.gate_review_api.submit_gate_review",
                self.review_payload(),
                "canDecide",
                True,
                "reviewer@example.invalid",
                {"cycle_id": CYCLE_ID},
            ),
            (
                self.api.request_gate_review_exception,
                "npi_core.gate_review_api.request_gate_review_exception",
                self.exception_payload(),
                "url",
                "https://example.invalid/evidence",
                "reviewer@example.invalid",
                {"cycle_id": CYCLE_ID},
            ),
            (
                self.api.decide_gate,
                "npi_core.gate_review_api.decide_gate",
                self.decide_payload(),
                "snapshot",
                {},
                "reviewer@example.invalid",
                {},
            ),
            (
                self.api.decide_gate,
                "npi_core.gate_review_api.decide_gate",
                self.decide_payload(),
                "availablePolicies",
                [],
                "reviewer@example.invalid",
                {},
            ),
        )
        for function, command, base, field, value, user, route_extra in cases:
            with self.subTest(command=command, field=field):
                self.reset_response(
                    user=user,
                    route_params={
                        "project_id": PROJECT_ID,
                        "gate_id": GATE_ID,
                        **route_extra,
                    },
                )
                payload = copy.deepcopy(base)
                payload[field] = value
                problem = self.assert_problem(
                    self.call(command, function, payload),
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(problem["fieldErrors"][0]["path"], field)
                self.assertEqual(self.repository.calls, [])

        self.reset_response(user="reviewer@example.invalid")
        invalid_decision = self.decide_payload()
        invalid_decision["outcome"] = "reopen"
        self.assert_problem(
            self.call(
                "npi_core.gate_review_api.decide_gate",
                self.api.decide_gate,
                invalid_decision,
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(self.repository.calls, [])

    def test_canonical_identity_hash_timestamp_and_binding_rules(self) -> None:
        cases = (
            ("policyGlobalId", POLICY_ID.upper()),
            ("policySnapshotHash", "A" * 64),
            ("policyVersion", True),
        )
        for field, value in cases:
            with self.subTest(field=field):
                self.reset_response(user="manager@example.invalid")
                payload = self.start_payload()
                payload[field] = value
                self.assert_problem(
                    self.call(
                        "npi_core.gate_review_api.start_gate_review",
                        self.api.start_gate_review,
                        payload,
                    ),
                    422,
                    "VALIDATION_FAILED",
                )

        self.reset_response(user="manager@example.invalid")
        duplicate = self.start_payload()
        duplicate["bindings"] = self.bindings() + self.bindings()
        problem = self.assert_problem(
            self.call(
                "npi_core.gate_review_api.start_gate_review",
                self.api.start_gate_review,
                duplicate,
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "bindings")

        self.reset_response(
            user="reviewer@example.invalid",
            route_params={
                "project_id": PROJECT_ID,
                "gate_id": GATE_ID,
                "cycle_id": CYCLE_ID,
            },
        )
        invalid_time = self.exception_payload()
        invalid_time["expiresAt"] = "2026-08-31T12:00:00+00:00"
        self.assert_problem(
            self.call(
                "npi_core.gate_review_api.request_gate_review_exception",
                self.api.request_gate_review_exception,
                invalid_time,
            ),
            422,
            "VALIDATION_FAILED",
        )

        self.reset_response(user="ordinary@example.invalid")
        self.headers["X-Request-ID"] = "not-a-canonical-request-id"
        problem = self.assert_problem(
            self.call(
                "npi_core.gate_review_api.get_gate_review",
                self.api.get_gate_review,
                {},
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "requestId")
        self.assertNotEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            "not-a-canonical-request-id",
        )
        self.assertEqual(self.factory_calls, [])
        self.headers["X-Request-ID"] = REQUEST_ID

        self.reset_response(
            user="reviewer@example.invalid",
            route_params={
                "project_id": PROJECT_ID,
                "gate_id": GATE_ID,
                "cycle_id": CYCLE_ID,
            },
        )
        uppercase_key = self.review_payload()
        uppercase_key["stepKey"] = "Quality.P0"
        self.call(
            "npi_core.gate_review_api.submit_gate_review",
            self.api.submit_gate_review,
            uppercase_key,
        )
        self.assertEqual(
            self.repository.calls[-1][2]["step_key"],
            "Quality.P0",
        )

    def test_unavailable_and_replay_headers_are_controlled(self) -> None:
        self.reset_response(user="reviewer@example.invalid")
        self.repository.unavailable = True
        self.assert_problem(
            self.call(
                "npi_core.gate_review_api.decide_gate",
                self.api.decide_gate,
                self.decide_payload(),
            ),
            404,
            "GATE_UNAVAILABLE",
        )

        self.repository.unavailable = False
        self.repository.replayed = True
        self.reset_response(user="reviewer@example.invalid")
        self.call(
            "npi_core.gate_review_api.decide_gate",
            self.api.decide_gate,
            self.decide_payload(),
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )

    def test_idempotency_key_is_strict_and_actor_bound(self) -> None:
        original = self.headers["Idempotency-Key"]
        for invalid in ("too-short", "contains a space and is long", "é" * 20):
            with self.subTest(invalid=invalid):
                self.reset_response(user="reviewer@example.invalid")
                self.headers["Idempotency-Key"] = invalid
                self.assert_problem(
                    self.call(
                        "npi_core.gate_review_api.decide_gate",
                        self.api.decide_gate,
                        self.decide_payload(),
                    ),
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(self.repository.calls, [])

        self.headers["Idempotency-Key"] = original
        hashes: list[str] = []
        for user in (
            "reviewer@example.invalid",
            "manager-transport@example.invalid",
        ):
            self.reset_response(user=user)
            self.call(
                "npi_core.gate_review_api.decide_gate",
                self.api.decide_gate,
                self.decide_payload(),
            )
            hashes.append(self.repository.calls[-1][2]["idempotency_key"])
        self.assertNotEqual(hashes[0], hashes[1])

    def test_bff_maps_only_the_seven_exact_review_operations(self) -> None:
        prefix = f"/api/npi/v1/projects/{PROJECT_ID}/gates/{GATE_ID}"
        routes = (
            (
                "GET",
                f"{prefix}/review",
                "npi_core.gate_review_api.get_gate_review",
                {"project_id": PROJECT_ID, "gate_id": GATE_ID},
            ),
            (
                "POST",
                f"{prefix}:start-review",
                "npi_core.gate_review_api.start_gate_review",
                {"project_id": PROJECT_ID, "gate_id": GATE_ID},
            ),
            (
                "POST",
                f"{prefix}/review-cycles/{CYCLE_ID}/reviews",
                "npi_core.gate_review_api.submit_gate_review",
                {
                    "project_id": PROJECT_ID,
                    "gate_id": GATE_ID,
                    "cycle_id": CYCLE_ID,
                },
            ),
            (
                "POST",
                f"{prefix}/review-cycles/{CYCLE_ID}/exceptions",
                "npi_core.gate_review_api.request_gate_review_exception",
                {
                    "project_id": PROJECT_ID,
                    "gate_id": GATE_ID,
                    "cycle_id": CYCLE_ID,
                },
            ),
            (
                "POST",
                (
                    f"{prefix}/review-cycles/{CYCLE_ID}/exceptions/"
                    f"{EXCEPTION_ID}:decide"
                ),
                "npi_core.gate_review_api.decide_gate_review_exception",
                {
                    "project_id": PROJECT_ID,
                    "gate_id": GATE_ID,
                    "cycle_id": CYCLE_ID,
                    "exception_id": EXCEPTION_ID,
                },
            ),
            (
                "POST",
                f"{prefix}:decide",
                "npi_core.gate_review_api.decide_gate",
                {"project_id": PROJECT_ID, "gate_id": GATE_ID},
            ),
            (
                "POST",
                f"{prefix}:reopen",
                "npi_core.gate_review_api.reopen_gate",
                {"project_id": PROJECT_ID, "gate_id": GATE_ID},
            ),
        )
        for method, path, command, params in routes:
            with self.subTest(path=path):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                )
                self.router.route_request()
                self.assertEqual(self.frappe.local.form_dict.cmd, command)
                self.assertEqual(self.frappe.flags.npi_route_params, params)
                self.assertTrue(
                    self.router._requires_project_request_id(method, path)
                )

        for method, suffix in (
            ("PUT", "/review"),
            ("POST", "/review-cycles/" + CYCLE_ID + "/reviews/extra"),
            ("POST", ":decision"),
        ):
            with self.subTest(method=method, suffix=suffix):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(
                    path=prefix + suffix,
                    method=method,
                )
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    "npi_core.bff.route_not_found",
                )

    def test_endpoint_decorators_keep_transport_open_and_methods_exact(self) -> None:
        expected = {
            self.api.get_gate_review: ("GET",),
            self.api.start_gate_review: ("POST",),
            self.api.submit_gate_review: ("POST",),
            self.api.request_gate_review_exception: ("POST",),
            self.api.decide_gate_review_exception: ("POST",),
            self.api.decide_gate: ("POST",),
            self.api.reopen_gate: ("POST",),
        }
        for endpoint, methods in expected.items():
            with self.subTest(endpoint=endpoint.__name__):
                self.assertTrue(endpoint.allow_guest)
                self.assertEqual(endpoint.allowed_methods, methods)


if __name__ == "__main__":
    unittest.main()
