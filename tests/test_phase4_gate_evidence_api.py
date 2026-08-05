from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from datetime import date
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
GATE_ID = "62d6ac02-b85f-4ae0-a522-953c4ebc2de4"
OWNER_MEMBER_ID = "4b5e2ed1-0e5a-41b6-a217-6f84a809ba36"
REVIEWER_MEMBER_ID = "44f7b429-a527-4304-865d-d61e6a42320b"
SOURCE_ID = "590b332e-1ec4-44d8-8778-8b84eaf079bc"
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


class MockGateEvidenceRepository:
    def __init__(self, owner: "Phase4GateEvidenceApiTest") -> None:
        self.owner = owner
        self.calls: list[tuple[str, UUID, UUID, dict[str, Any]]] = []
        self.unavailable = False
        self.replayed = False
        self.attach_failure: Exception | None = None

    def evidence_workspace(
        self,
        project_id: UUID,
        gate_id: UUID,
    ) -> dict[str, Any] | None:
        self.calls.append(("workspace", project_id, gate_id, {}))
        if self.unavailable:
            return None
        return copy.deepcopy(self.owner.workspace)

    def freeze_requirements(
        self,
        project_id: UUID,
        gate_id: UUID,
        **values: Any,
    ):
        self.calls.append(("freeze", project_id, gate_id, values))
        if self.unavailable:
            return None
        return types.SimpleNamespace(
            response=copy.deepcopy(self.owner.workspace),
            replayed=self.replayed,
        )

    def attach_evidence(
        self,
        project_id: UUID,
        gate_id: UUID,
        requirement_key: str,
        **values: Any,
    ):
        self.calls.append(
            (
                "attach",
                project_id,
                gate_id,
                {"requirement_key": requirement_key, **values},
            )
        )
        if self.attach_failure is not None:
            raise self.attach_failure
        if self.unavailable:
            return None
        return types.SimpleNamespace(
            response=copy.deepcopy(self.owner.workspace),
            replayed=self.replayed,
        )


class Phase4GateEvidenceApiTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.sessions",
        "npi_core.documents.baseline_diagnostics",
        "npi_core.gate_evidence_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.headers = {
            "Idempotency-Key": "p4-gate-evidence-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase4-gate-evidence-api",
        }
        self.roles = {
            "Administrator": ["System Manager"],
            "manager@example.invalid": ["System Manager"],
            "owner@example.invalid": ["NPI User"],
            "external-manager@example.invalid": ["System Manager"],
        }
        self.user_types = {
            "Administrator": "System User",
            "manager@example.invalid": "System User",
            "owner@example.invalid": "System User",
            "external-manager@example.invalid": "Website User",
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

        self.api = importlib.import_module("npi_core.gate_evidence_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockGateEvidenceRepository(self)
        self.factory_calls: list[dict[str, Any]] = []

        def repository_factory(**values: Any):
            self.factory_calls.append(values)
            return self.repository

        self.api._repository_factory = repository_factory
        self.workspace = {
            "project": {
                "globalId": PROJECT_ID,
                "businessCode": "SYN-P403",
                "title": "Synthetic P4-03 Project",
            },
            "gate": {
                "globalId": GATE_ID,
                "key": "G1",
                "title": "Synthetic Gate",
                "state": "not_started",
                "version": 2,
                "dueDate": "2026-08-31",
                "templateRef": {
                    "globalId": "77932078-9512-428e-b9d7-863303661059",
                    "version": 1,
                    "snapshotHash": "a" * 64,
                },
                "requirementSnapshotHash": "b" * 64,
                "frozenAt": "2026-07-23T12:00:00Z",
                "frozenBy": "Administrator",
            },
            "requirements": [],
            "baselineImpacts": [],
            "summary": {
                "requiredCount": 1,
                "missingRequiredCount": 1,
                "unsafeScanCount": 0,
                "evidenceCount": 0,
            },
            "permissions": {
                "canView": True,
                "canAttachEvidence": True,
                "canAdminister": True,
            },
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
        self.frappe.flags.npi_route_params = {
            "project_id": PROJECT_ID,
            "gate_id": GATE_ID,
        }
        self.repository.calls.clear()

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
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        UUID(headers["X-Request-ID"])
        return result

    @staticmethod
    def freeze_payload() -> dict[str, object]:
        return {
            "expectedGateVersion": 1,
            "gateDueDate": "2026-08-31",
            "requirements": [
                {
                    "key": "drawing",
                    "ownerMemberId": OWNER_MEMBER_ID,
                    "reviewerMemberIds": [REVIEWER_MEMBER_ID],
                    "dueDate": "2026-08-28",
                }
            ],
        }

    @staticmethod
    def attach_payload() -> dict[str, object]:
        return {
            "expectedGateVersion": 2,
            "evidenceKind": "wbs_item",
            "sourceGlobalId": SOURCE_ID,
            "sourceVersion": 3,
            "sourceHash": "c" * 64,
        }

    def test_workspace_query_is_authenticated_and_calls_exact_route_identity(
        self,
    ) -> None:
        self.reset_response(user="owner@example.invalid")
        result = self.call(
            "npi_core.gate_evidence_api.get_gate_evidence_workspace",
            self.api.get_gate_evidence_workspace,
            {},
        )
        self.assertEqual(result, self.workspace)
        self.assertEqual(
            self.repository.calls,
            [
                (
                    "workspace",
                    UUID(PROJECT_ID),
                    UUID(GATE_ID),
                    {},
                )
            ],
        )
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )

    def test_commands_require_internal_system_manager_and_csrf(self) -> None:
        for user, status, code in (
            ("Guest", 401, "AUTHENTICATION_REQUIRED"),
            ("owner@example.invalid", 403, "PERMISSION_DENIED"),
            (
                "external-manager@example.invalid",
                403,
                "PERMISSION_DENIED",
            ),
        ):
            with self.subTest(user=user):
                self.reset_response(user=user)
                result = self.call(
                    "npi_core.gate_evidence_api.freeze_gate_requirements",
                    self.api.freeze_gate_requirements,
                    self.freeze_payload(),
                )
                self.assert_problem(result, status, code)

        self.reset_response()
        self.headers.pop("X-Frappe-CSRF-Token")
        result = self.call(
            "npi_core.gate_evidence_api.freeze_gate_requirements",
            self.api.freeze_gate_requirements,
            self.freeze_payload(),
        )
        problem = self.assert_problem(result, 403, "CSRF_TOKEN_INVALID")
        self.assertTrue(problem["retryable"])
        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + ("a" * 48)

    def test_freeze_is_closed_typed_and_retry_safe(self) -> None:
        result = self.call(
            "npi_core.gate_evidence_api.freeze_gate_requirements",
            self.api.freeze_gate_requirements,
            self.freeze_payload(),
        )
        self.assertEqual(result, self.workspace)
        operation, project_id, gate_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "freeze")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        self.assertEqual(gate_id, UUID(GATE_ID))
        self.assertEqual(values["expected_gate_version"], 1)
        self.assertEqual(values["gate_due_date"], date(2026, 8, 31))
        self.assertEqual(
            values["assignments"][0]["owner_member_id"],
            UUID(OWNER_MEMBER_ID),
        )
        self.assertEqual(
            values["assignments"][0]["reviewer_member_ids"],
            (UUID(REVIEWER_MEMBER_ID),),
        )
        self.assertEqual(len(values["idempotency_key"]), 64)
        self.assertNotEqual(
            values["idempotency_key"],
            "p4-gate-evidence-command-0001",
        )

        self.reset_response()
        invalid = self.freeze_payload()
        invalid["unexpected"] = True
        problem = self.assert_problem(
            self.call(
                "npi_core.gate_evidence_api.freeze_gate_requirements",
                self.api.freeze_gate_requirements,
                invalid,
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "unexpected")

    def test_freeze_rejects_duplicate_requirement_and_reviewer_identities(
        self,
    ) -> None:
        duplicate_key = self.freeze_payload()
        duplicate_key["requirements"].append(  # type: ignore[union-attr]
            copy.deepcopy(duplicate_key["requirements"][0])  # type: ignore[index]
        )
        problem = self.assert_problem(
            self.call(
                "npi_core.gate_evidence_api.freeze_gate_requirements",
                self.api.freeze_gate_requirements,
                duplicate_key,
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "requirements")

        self.reset_response()
        duplicate_reviewer = self.freeze_payload()
        duplicate_reviewer["requirements"][0]["reviewerMemberIds"] = [  # type: ignore[index]
            REVIEWER_MEMBER_ID,
            REVIEWER_MEMBER_ID,
        ]
        problem = self.assert_problem(
            self.call(
                "npi_core.gate_evidence_api.freeze_gate_requirements",
                self.api.freeze_gate_requirements,
                duplicate_reviewer,
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(
            problem["fieldErrors"][0]["path"],
            "requirements[0].reviewerMemberIds",
        )

    def test_attach_accepts_only_exact_supported_identity(self) -> None:
        self.frappe.flags.npi_route_params["requirement_key"] = "drawing"
        result = self.call(
            "npi_core.gate_evidence_api.attach_gate_evidence",
            self.api.attach_gate_evidence,
            self.attach_payload(),
        )
        self.assertEqual(result, self.workspace)
        operation, project_id, gate_id, values = self.repository.calls[-1]
        self.assertEqual(operation, "attach")
        self.assertEqual(project_id, UUID(PROJECT_ID))
        self.assertEqual(gate_id, UUID(GATE_ID))
        self.assertEqual(values["requirement_key"], "drawing")
        self.assertEqual(values["evidence_kind"], "wbs_item")
        self.assertEqual(values["source_global_id"], UUID(SOURCE_ID))
        self.assertEqual(values["source_version"], 3)
        self.assertEqual(values["source_hash"], "c" * 64)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)

        self.reset_response()
        self.frappe.flags.npi_route_params["requirement_key"] = "drawing"
        baseline_payload = self.attach_payload()
        baseline_payload["evidenceKind"] = "release_baseline"
        baseline_payload["sourceVersion"] = 1
        self.call(
            "npi_core.gate_evidence_api.attach_gate_evidence",
            self.api.attach_gate_evidence,
            baseline_payload,
        )
        self.assertEqual(
            self.repository.calls[-1][3]["evidence_kind"],
            "release_baseline",
        )

        for field, value in (
            ("evidenceKind", "latest"),
            ("sourceVersion", 0),
            ("sourceHash", "not-a-hash"),
        ):
            with self.subTest(field=field):
                self.reset_response()
                self.frappe.flags.npi_route_params["requirement_key"] = "drawing"
                payload = self.attach_payload()
                payload[field] = value
                self.assert_problem(
                    self.call(
                        "npi_core.gate_evidence_api.attach_gate_evidence",
                        self.api.attach_gate_evidence,
                        payload,
                    ),
                    422,
                    "VALIDATION_FAILED",
                )

    def test_baseline_dependency_failure_returns_500_and_rolls_back(self) -> None:
        self.frappe.flags.npi_route_params["requirement_key"] = "drawing"
        self.repository.attach_failure = RuntimeError(
            "synthetic baseline dependency persistence secret"
        )
        payload = self.attach_payload()
        payload["evidenceKind"] = "release_baseline"
        payload["sourceVersion"] = 1

        problem = self.assert_problem(
            self.call(
                "npi_core.gate_evidence_api.attach_gate_evidence",
                self.api.attach_gate_evidence,
                payload,
            ),
            500,
            "INTERNAL_SERVER_ERROR",
        )
        self.assertEqual(self.frappe.db.rollback_count, 1)
        self.assertNotIn("persistence secret", str(problem))

    def test_unavailable_project_or_gate_uses_one_non_leaking_problem(self) -> None:
        self.repository.unavailable = True
        self.assert_problem(
            self.call(
                "npi_core.gate_evidence_api.get_gate_evidence_workspace",
                self.api.get_gate_evidence_workspace,
                {},
            ),
            404,
            "GATE_UNAVAILABLE",
        )

        self.reset_response()
        self.assert_problem(
            self.call(
                "npi_core.gate_evidence_api.freeze_gate_requirements",
                self.api.freeze_gate_requirements,
                self.freeze_payload(),
            ),
            404,
            "GATE_UNAVAILABLE",
        )

    def test_bff_maps_only_the_three_explicit_gate_evidence_operations(self) -> None:
        routes = (
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/gates/{GATE_ID}/evidence",
                "npi_core.gate_evidence_api.get_gate_evidence_workspace",
                {"project_id": PROJECT_ID, "gate_id": GATE_ID},
            ),
            (
                "POST",
                (
                    f"/api/npi/v1/projects/{PROJECT_ID}/gates/"
                    f"{GATE_ID}:freeze-requirements"
                ),
                "npi_core.gate_evidence_api.freeze_gate_requirements",
                {"project_id": PROJECT_ID, "gate_id": GATE_ID},
            ),
            (
                "POST",
                (
                    f"/api/npi/v1/projects/{PROJECT_ID}/gates/{GATE_ID}"
                    "/requirements/drawing/evidence"
                ),
                "npi_core.gate_evidence_api.attach_gate_evidence",
                {
                    "project_id": PROJECT_ID,
                    "gate_id": GATE_ID,
                    "requirement_key": "drawing",
                },
            ),
        )
        for method, path, command, params in routes:
            with self.subTest(method=method, path=path):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                )
                self.router.route_request()
                self.assertEqual(self.frappe.local.form_dict.cmd, command)
                self.assertEqual(self.frappe.flags.npi_route_params, params)
                self.assertTrue(self.router._requires_project_request_id(method, path))

        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path=(
                f"/api/npi/v1/projects/{PROJECT_ID}/gates/{GATE_ID}"
                "/requirements/drawing/evidence/extra"
            ),
            method="POST",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.route_not_found",
        )

    def test_endpoint_decorators_keep_transport_open_and_methods_exact(self) -> None:
        expected = {
            self.api.get_gate_evidence_workspace: ("GET",),
            self.api.freeze_gate_requirements: ("POST",),
            self.api.attach_gate_evidence: ("POST",),
        }
        for endpoint, methods in expected.items():
            with self.subTest(endpoint=endpoint.__name__):
                self.assertTrue(endpoint.allow_guest)
                self.assertEqual(endpoint.allowed_methods, methods)


if __name__ == "__main__":
    unittest.main()
