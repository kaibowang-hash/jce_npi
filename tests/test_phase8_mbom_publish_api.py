from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from uuid import UUID


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

ROOT = Path(__file__).resolve().parents[1]

PROJECT = "00000000-0000-4000-8000-000000009401"
PHASE5 = "00000000-0000-4000-8000-000000009402"
REQUEST = "00000000-0000-4000-8000-000000009403"
OUTBOX = "00000000-0000-4000-8000-000000009404"
ACK = (
    "I confirm this request uses the exact released EBOM topology, current Item "
    "readiness, MBOM expectations, and execution profile."
)


class FakeRepository:
    def __init__(self, owner: "Phase8MbomPublishApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []
        self.outcome = owner.outcome()

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.owner.events.append("authorize")
        return self.scope

    def list_mbom_publish_requests(self, *args: object, **kwargs: Any):
        self.calls.append(("list", args, kwargs))
        return {"projectGlobalId": PROJECT, "items": []}

    def mbom_publish_request_detail(self, *args: object, **kwargs: Any):
        self.calls.append(("detail", args, kwargs))
        return self.owner.response

    def create_mbom_publish_request(self, *args: object, **kwargs: Any):
        self.owner.events.append("create")
        self.calls.append(("create", args, kwargs))
        return self.outcome


class Phase8MbomPublishApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.foundation.security",
        "npi_core.foundation.tracing",
        "npi_core.project.domain",
        "npi_core.request_security",
        "npi_integration.mbom_publish.diagnostics",
        "npi_integration.mbom_publish.frappe_repository",
        "npi_integration.mbom_publish_api",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        self.enqueued: list[dict[str, object]] = []
        self.diagnostics: list[dict[str, object]] = []
        self.headers = {
            "Idempotency-Key": "p804-mbom-command",
            "X-Request-ID": REQUEST,
        }
        self.response = {
            "requestGlobalId": REQUEST,
            "request": {"globalId": REQUEST, "state": "queued"},
            "outboxEventId": OUTBOX,
            "updatedAt": "2026-08-21T15:00:00Z",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace(
            npi_route_params={
                "project_id": PROJECT,
                "mbom_publish_request_id": REQUEST,
            }
        )
        self.frappe.session = types.SimpleNamespace(user="publisher@example.invalid")
        self.frappe.local = types.SimpleNamespace(
            response=types.SimpleNamespace(http_status_code=200)
        )
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_hooks = lambda _name: []
        self.frappe.get_attr = lambda _path: None
        self.frappe.db = types.SimpleNamespace(
            commit=lambda: self.events.append("commit"),
            rollback=lambda: self.events.append("rollback"),
        )
        self.frappe.enqueue = lambda *args, **kwargs: (
            self.events.append("enqueue"),
            self.enqueued.append({"args": args, **kwargs}),
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        sys.modules["frappe"] = self.frappe

        api_module = types.ModuleType("npi_core.api")

        def domain_call(handle, *, success_status=200, response_headers=None, **_kwargs):
            result = handle()
            self.frappe.local.response.http_status_code = success_status
            self.frappe.local.response.headers = dict(response_headers or {})
            return result

        api_module.frappe_domain_call = domain_call
        def record_safe_diagnostic(**values: object) -> None:
            self.events.append("diagnostic")
            self.diagnostics.append(values)

        api_module.record_safe_diagnostic = record_safe_diagnostic
        sys.modules["npi_core.api"] = api_module

        security_module = types.ModuleType("npi_core.foundation.security")
        security_module.Principal = object
        sys.modules["npi_core.foundation.security"] = security_module
        tracing_module = types.ModuleType("npi_core.foundation.tracing")
        tracing_module.current_trace_id = ContextVar(
            "p804-test-trace",
            default="trace-p804-api-0001",
        )
        sys.modules["npi_core.foundation.tracing"] = tracing_module
        project_module = types.ModuleType("npi_core.project.domain")
        project_module.actor_idempotency_key_hash = lambda actor, key: "d" * 64
        sys.modules["npi_core.project.domain"] = project_module

        request_module = types.ModuleType("npi_core.request_security")
        request_module.authenticated_user = lambda: self.frappe.session.user
        request_module.authenticated_principal = lambda actor: types.SimpleNamespace(
            actor=actor,
            is_external=False,
            roles=frozenset({"NPI API User"}),
        )
        request_module.require_csrf_token = lambda: self.events.append("csrf")
        request_module.response_request_id = lambda: REQUEST
        request_module.reject_unexpected_request_fields = (
            lambda allowed, fields: self._reject(allowed, fields)
        )
        request_module.require_request_fields = lambda required, fields: self._require(
            required, fields
        )
        sys.modules["npi_core.request_security"] = request_module

        self.api = importlib.import_module("npi_integration.mbom_publish_api")
        self.repository = FakeRepository(self)
        self.api._repository_factory = lambda **_values: self.repository

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def _reject(allowed: frozenset[str], fields: dict[str, object]) -> None:
        unexpected = set(fields) - set(allowed)
        if unexpected:
            raise AssertionError(f"unexpected fields: {unexpected}")

    @staticmethod
    def _require(required: frozenset[str], fields: dict[str, object]) -> None:
        if any(fields.get(field) is None for field in required):
            raise AssertionError("missing required field")

    def outcome(self, *, replayed: bool = False, enqueue: bool = True):
        return types.SimpleNamespace(
            response=self.response,
            replayed=replayed,
            should_enqueue=enqueue,
            outbox_event_id=UUID(OUTBOX) if enqueue else None,
            problem=None,
        )

    @staticmethod
    def payload() -> dict[str, object]:
        return {
            "phase5PublishRequestGlobalId": PHASE5,
            "expectedSourceHash": "a" * 64,
            "expectedTopologyHash": "b" * 64,
            "expectedItemMappingSetHash": "c" * 64,
            "expectedMbomMappingSetHash": "d" * 64,
            "acknowledgement": ACK,
        }

    def test_create_freezes_exact_fields_commits_then_enqueues(self) -> None:
        result = self.api.create_mbom_publish_request(**self.payload())
        self.assertEqual(result, self.response)
        self.assertEqual(self.events, ["csrf", "authorize", "create", "commit", "enqueue"])
        call = self.repository.calls[-1]
        self.assertEqual(call[0], "create")
        self.assertEqual(str(call[2]["phase5_publish_request_id"]), PHASE5)
        self.assertEqual(call[2]["expected_source_hash"], "a" * 64)
        self.assertEqual(call[2]["idempotency_key_hash"], "d" * 64)
        self.assertEqual(self.enqueued[0]["job_id"], f"mbom-publish-{OUTBOX}")
        self.assertFalse(self.enqueued[0]["enqueue_after_commit"])

    def test_exact_replay_is_200_and_never_enqueues(self) -> None:
        self.repository.outcome = self.outcome(replayed=True, enqueue=False)
        self.api.create_mbom_publish_request(**self.payload())
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertNotIn("enqueue", self.events)

    def test_commit_failure_rolls_back_and_never_enqueues(self) -> None:
        def fail_commit() -> None:
            self.events.append("commit")
            raise RuntimeError("synthetic private commit detail")

        self.frappe.db.commit = fail_commit
        with self.assertRaises(RuntimeError):
            self.api.create_mbom_publish_request(**self.payload())
        self.assertEqual(self.events[-2:], ["commit", "rollback"])
        self.assertNotIn("enqueue", self.events)

    def test_enqueue_failure_keeps_committed_pending_request_and_safe_diagnostic(self) -> None:
        private_message = "synthetic enqueue failure with private business detail"

        def fail_enqueue(*_args: object, **_kwargs: object) -> None:
            self.events.append("enqueue")
            raise RuntimeError(private_message)

        self.frappe.enqueue = fail_enqueue
        result = self.api.create_mbom_publish_request(**self.payload())
        self.assertEqual(result, self.response)
        self.assertEqual(result["request"]["state"], "queued")
        self.assertEqual(result["outboxEventId"], OUTBOX)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.events,
            ["csrf", "authorize", "create", "commit", "enqueue", "diagnostic"],
        )
        self.assertNotIn("rollback", self.events)
        self.assertEqual(
            self.diagnostics,
            [
                {
                    "code": "MBOM_PUBLISH_ENQUEUE_FAILED",
                    "title": "NPI MBOM publish enqueue failed",
                    "exception_type": "RuntimeError",
                    "trace_id": "trace-p804-api-0001",
                }
            ],
        )
        self.assertNotIn(private_message, repr(result))
        self.assertNotIn(private_message, repr(self.diagnostics))

    def test_create_diagnostic_is_exact_inner_first_and_response_neutral(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.mbom_publish.diagnostics"
        )
        trace_id = "trace-" + "8" * 32
        self.headers[diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )
        self.api.current_trace_id.set(trace_id)
        original = RuntimeError(
            "private MBOM id/hash actor/profile target /tmp/private stack"
        )

        def fail(*_args: object, **_kwargs: object) -> None:
            with diagnostics.mbom_create_server_step(
                "P804_CREATE_PROJECT_LOCK"
            ):
                raise original

        self.repository.create_mbom_publish_request = fail
        self.headers.pop(diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_HEADER)
        with self.assertRaises(RuntimeError) as baseline:
            self.api.create_mbom_publish_request(**self.payload())
        self.assertIs(baseline.exception, original)
        self.assertEqual(self.diagnostics, [])
        self.headers[diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )
        with self.assertRaises(RuntimeError) as raised:
            self.api.create_mbom_publish_request(**self.payload())

        self.assertIs(raised.exception, original)
        self.assertEqual(
            self.diagnostics,
            [
                {
                    "code": "P804_CREATE_PROJECT_LOCK",
                    "title": "NPI MBOM publish create substage failed",
                    "exception_type": "RuntimeError",
                    "trace_id": trace_id,
                }
            ],
        )
        self.assertNotIn(str(original), repr(self.diagnostics))
        self.assertNotIn("commit", self.events)
        self.assertFalse(
            hasattr(self.frappe.flags, "npi_p804_mbom_create_diagnostic")
        )

    def test_create_diagnostic_wrong_scope_or_trace_records_nothing(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.mbom_publish.diagnostics"
        )
        private = RuntimeError("private response value")

        def fail(*_args: object, **_kwargs: object) -> None:
            raise private

        self.repository.create_mbom_publish_request = fail
        for scope, trace_id in (
            (None, "trace-" + "8" * 32),
            ("p804-mbom-create-wrong", "trace-" + "8" * 32),
            (diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_SCOPE, "trace-invalid"),
        ):
            with self.subTest(scope=scope, trace_id=trace_id):
                self.headers[diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_HEADER] = scope
                self.api.current_trace_id.set(trace_id)
                with self.assertRaises(RuntimeError) as raised:
                    self.api.create_mbom_publish_request(**self.payload())
                self.assertIs(raised.exception, private)
                self.assertEqual(self.diagnostics, [])
                self.assertFalse(
                    hasattr(self.frappe.flags, "npi_p804_mbom_create_diagnostic")
                )

    def test_create_diagnostic_restores_a_preexisting_request_flag(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.mbom_publish.diagnostics"
        )
        trace_id = "trace-" + "6" * 32
        sentinel = {"owned": "by-outer-request"}
        setattr(
            self.frappe.flags,
            "npi_p804_mbom_create_diagnostic",
            sentinel,
        )
        self.headers[diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_HEADER] = (
            diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_SCOPE
        )
        with diagnostics.mbom_create_server_diagnostics(trace_id):
            self.assertIsNot(
                getattr(
                    self.frappe.flags,
                    "npi_p804_mbom_create_diagnostic",
                ),
                sentinel,
            )
        self.assertIs(
            getattr(self.frappe.flags, "npi_p804_mbom_create_diagnostic"),
            sentinel,
        )

    def test_each_create_server_code_has_one_product_context(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.mbom_publish.diagnostics"
        )
        source = "\n".join(
            (
                (
                    ROOT
                    / "apps/npi_integration/npi_integration/mbom_publish_api.py"
                ).read_text(encoding="utf-8"),
                (
                    ROOT
                    / "apps/npi_integration/npi_integration/mbom_publish/frappe_repository.py"
                ).read_text(encoding="utf-8"),
            )
        )
        for code in diagnostics.MBOM_CREATE_SERVER_DIAGNOSTIC_CODES:
            with self.subTest(code=code):
                self.assertEqual(source.count(f'"{code}"'), 1)
        self.assertNotIn("P804_CREATE_ENQUEUE", source)

    def test_queries_authorize_project_before_secondary_request(self) -> None:
        self.api.get_mbom_publish_requests(
            phase5PublishRequestGlobalId=PHASE5,
        )
        self.assertEqual(self.repository.calls[-1][0], "list")
        self.assertEqual(
            str(
                self.repository.calls[-1][2][
                    "phase5_publish_request_id"
                ]
            ),
            PHASE5,
        )
        self.api.get_mbom_publish_request()
        self.assertEqual(self.repository.calls[-1][0], "detail")
        self.assertEqual(str(self.repository.calls[-1][1][1]), REQUEST)
        self.repository.scope = False
        with self.assertRaises(Exception) as caught:
            self.api.get_mbom_publish_request()
        self.assertEqual(getattr(caught.exception, "code", None), "MBOM_PUBLISH_REQUEST_UNAVAILABLE")

    def test_invalid_hash_acknowledgement_and_extra_field_fail_before_repository(self) -> None:
        for mutation in (
            {"expectedSourceHash": "A" * 64},
            {"acknowledgement": "yes"},
            {"targetMethod": "frappe.client.insert"},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(Exception):
                self.api.create_mbom_publish_request(**{**self.payload(), **mutation})
        self.assertFalse(any(call[0] == "create" for call in self.repository.calls))

    def test_method_contract_is_closed(self) -> None:
        self.assertEqual(self.api.get_mbom_publish_requests.allowed_methods, ("GET",))
        self.assertEqual(self.api.get_mbom_publish_request.allowed_methods, ("GET",))
        self.assertEqual(self.api.create_mbom_publish_request.allowed_methods, ("POST",))


if __name__ == "__main__":
    unittest.main()
