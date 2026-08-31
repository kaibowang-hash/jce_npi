from __future__ import annotations

import importlib
import inspect
import os
import sys
import types
import unittest
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]
ROOT = Path(__file__).resolve().parents[1]
PROJECT = "00000000-0000-5000-8000-000000009301"
CHANGE = "00000000-0000-4000-8000-000000009302"
REVISION = "00000000-0000-4000-8000-000000009303"
REQUEST = "00000000-0000-4000-8000-000000009304"


class Phase9ChangeIntegrationApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.foundation.errors",
        "npi_core.foundation.security",
        "npi_core.foundation.tracing",
        "npi_core.project.domain",
        "npi_core.request_security",
        "npi_integration.engineering_change.runtime_fixture",
        "npi_integration.engineering_change_api",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[object] = []
        self.headers = {"Idempotency-Key": "0000000000000000"}
        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.flags = types.SimpleNamespace(
            npi_route_params={"project_id": PROJECT, "change_id": CHANGE}
        )
        frappe.conf = {
            "npi_runtime_disposable_marker": "npi-one-local-runtime-disposable-v1"
        }
        frappe.local = types.SimpleNamespace(
            form_dict={},
            response=types.SimpleNamespace(http_status_code=200),
            request=types.SimpleNamespace(
                method="POST",
                headers=self.headers,
                args={},
                path=(
                    "/api/npi/v1/integration/erpnext/engineering-change-events"
                ),
                host="127.0.0.1:8003",
                remote_addr="127.0.0.1",
                is_secure=False,
            ),
        )
        frappe.db = types.SimpleNamespace(
            commit=lambda: self.events.append("commit"),
            rollback=lambda: self.events.append("rollback"),
        )
        frappe.get_hooks = lambda _name: []
        frappe.get_attr = lambda _path: None
        frappe.enqueue = lambda path, **values: self.events.append(
            ("enqueue", path, values)
        )

        def whitelist(*, allow_guest=False, methods=None):
            def decorate(function):
                function.allow_guest = allow_guest
                function.allowed_methods = tuple(methods or ())
                return function

            return decorate

        frappe.whitelist = whitelist
        sys.modules["frappe"] = frappe
        self.frappe = frappe

        errors = types.ModuleType("npi_core.foundation.errors")

        class NpiProblem(Exception):
            def __init__(self, status=500, code="PROBLEM", title=None, detail=None, retryable=False):
                super().__init__(title)
                self.status = status
                self.code = code
                self.retryable = retryable

        class RequestValidationFailed(NpiProblem):
            pass

        errors.NpiProblem = NpiProblem
        errors.RequestValidationFailed = RequestValidationFailed
        sys.modules[errors.__name__] = errors
        self.RequestValidationFailed = RequestValidationFailed

        api = types.ModuleType("npi_core.api")

        def domain_call(handle, *, success_status=200, response_headers=None, **_values):
            result = handle()
            frappe.local.response.http_status_code = success_status
            frappe.local.response.headers = dict(response_headers or {})
            return result

        api.frappe_domain_call = domain_call
        api.record_safe_diagnostic = lambda **values: self.events.append(
            ("diagnostic", values)
        )
        sys.modules[api.__name__] = api
        security = types.ModuleType("npi_core.foundation.security")
        security.Principal = lambda **values: types.SimpleNamespace(**values)
        security.ProjectAccess = types.SimpleNamespace(ADMINISTER="administer")
        sys.modules[security.__name__] = security
        tracing = types.ModuleType("npi_core.foundation.tracing")
        tracing.current_trace_id = ContextVar("p901-api-trace", default="trace-p901-api")
        sys.modules[tracing.__name__] = tracing
        project = types.ModuleType("npi_core.project.domain")
        project.actor_idempotency_key_hash = lambda actor, key: "a" * 64
        sys.modules[project.__name__] = project
        request_security = types.ModuleType("npi_core.request_security")
        request_security.authenticated_user = lambda: "operator@example.invalid"
        request_security.authenticated_principal = lambda actor: types.SimpleNamespace(
            user_id=actor,
            tenant_id="tenant-p901",
            roles=frozenset({"NPI API User"}),
            is_external=False,
        )
        request_security.configured_tenant_id = lambda: "tenant-p901"
        request_security.require_csrf_token = lambda: self.events.append("csrf")
        request_security.response_request_id = lambda: REQUEST

        def reject(allowed, supplied):
            unexpected = set(supplied) - set(allowed)
            if unexpected:
                raise RequestValidationFailed(422, "REQUEST_VALIDATION_FAILED")

        def require(required, supplied):
            present = set(supplied) | set(frappe.local.form_dict)
            if any(name not in present for name in required):
                raise RequestValidationFailed(422, "REQUEST_VALIDATION_FAILED")

        request_security.reject_unexpected_request_fields = reject
        request_security.require_request_fields = require
        sys.modules[request_security.__name__] = request_security
        self.module = importlib.import_module(
            "npi_integration.engineering_change_api"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def test_inbound_diagnostic_requires_exact_runtime_request_shape(self) -> None:
        trace = "trace-" + "d" * 32
        request = self.frappe.local.request
        request.path = self.module.WEBHOOK_PATH
        request.args = {}
        request.headers.update(
            {
                self.module.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_HEADER: (
                    self.module.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_SCOPE
                ),
                self.module.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_TRACE_HEADER: trace,
            }
        )
        with patch.object(
            self.module,
            "ENGINEERING_CHANGE_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED",
            True,
        ), patch.dict(
            os.environ,
            {
                "NPI_P9_01C_RUNTIME_ENABLED": "1",
                "NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": (
                    "/tmp/p9-01-engineering-change-runtime-diagnostic.json"
                ),
            },
            clear=False,
        ):
            self.assertTrue(
                self.module._engineering_change_inbound_diagnostic_active(trace)
            )
            request.method = "GET"
            self.assertFalse(
                self.module._engineering_change_inbound_diagnostic_active(trace)
            )
            request.method = "POST"
            request.headers.pop(
                self.module.ENGINEERING_CHANGE_INBOUND_SERVER_DIAGNOSTIC_HEADER
            )
            self.assertFalse(
                self.module._engineering_change_inbound_diagnostic_active(trace)
            )

    def test_inbound_transport_accepts_only_exact_disposable_loopback_http(self) -> None:
        request = self.frappe.local.request
        with patch.dict(
            os.environ,
            {"NPI_P9_01C_RUNTIME_ENABLED": "1"},
            clear=False,
        ):
            self.assertTrue(self.module._request_is_secure(request))
            for field, value in (
                ("host", "localhost:8003"),
                ("remote_addr", "192.0.2.1"),
                ("method", "GET"),
                ("path", "/api/method/ping"),
            ):
                original = getattr(request, field)
                with self.subTest(field=field):
                    setattr(request, field, value)
                    self.assertFalse(self.module._request_is_secure(request))
                    setattr(request, field, original)
            request.headers["X-Forwarded-Proto"] = "https"
            request.host = "localhost:8003"
            self.assertFalse(self.module._request_is_secure(request))
            request.host = "127.0.0.1:8003"
            request.is_secure = True
            self.assertTrue(self.module._request_is_secure(request))

    def test_inbound_diagnostic_stages_follow_handler_order(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/engineering_change_api.py"
        ).read_text(encoding="utf-8")
        codes = (
            "P901_CHANGE_INBOUND_API_CALL",
            "P901_CHANGE_INBOUND_API_FIELDS",
            "P901_CHANGE_INBOUND_API_REQUEST",
            "P901_CHANGE_INBOUND_API_AUTHENTICATE",
            "P901_CHANGE_INBOUND_API_PRINCIPAL",
            "P901_CHANGE_INBOUND_API_REPOSITORY_INIT",
            "P901_CHANGE_INBOUND_API_REPOSITORY_CALL",
            "P901_CHANGE_INBOUND_API_COMMIT",
            "P901_CHANGE_INBOUND_API_ENQUEUE",
            "P901_CHANGE_INBOUND_API_OUTCOME",
            "P901_CHANGE_INBOUND_API_RESPONSE",
        )
        positions = [source.index(code) for code in codes]
        self.assertEqual(positions, sorted(positions))
        self.assertFalse(
            self.module.ENGINEERING_CHANGE_INBOUND_FULL_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.module.ENGINEERING_CHANGE_POST_RAW_BODY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.module.ENGINEERING_CHANGE_POST_MARKER_REPAIR_DIAGNOSTICS_ENABLED
        )
        self.assertTrue(
            self.module.ENGINEERING_CHANGE_POST_LOOPBACK_REPAIR_DIAGNOSTICS_ENABLED
        )

    def test_inbound_handler_keeps_raw_signed_json_out_of_keyword_fields(self) -> None:
        command = (
            "npi_integration.engineering_change_api."
            "receive_engineering_change_event"
        )
        self.frappe.local.form_dict = {
            "cmd": command,
            "event_type": "npi.erp-engineering-change.v1",
            "payload": {"change": "signed-raw-body"},
        }
        self.assertEqual(
            tuple(
                inspect.signature(
                    self.module.receive_engineering_change_event
                ).parameters
            ),
            (),
        )
        with patch.object(
            self.module,
            "_receive_engineering_change_event",
            return_value={"state": "pending"},
        ) as receive:
            self.assertEqual(
                self.module.receive_engineering_change_event(),
                {"state": "pending"},
            )
        receive.assert_called_once_with()

    def test_summary_route_requires_csrf_exact_predecessor_and_actor_idempotency(self) -> None:
        self.frappe.local.form_dict = {
            "expectedRevision": 4,
            "expectedRevisionGlobalId": REVISION,
            "expectedRevisionSnapshotHash": "b" * 64,
        }
        outcome = types.SimpleNamespace(
            response={"state": "queued", "requestGlobalId": REQUEST},
            replayed=False,
            should_enqueue=True,
            queue_id=REQUEST,
        )

        class Repository:
            def authorize_scope(_self, project):
                self.events.append(("authorize", str(project)))
                return True

            def create_summary_request(_self, project, change, **values):
                self.events.append(("create", str(project), str(change), values))
                return outcome

        with patch.object(self.module, "_repository", return_value=Repository()):
            response = self.module.request_change_implementation_summary(
                expectedRevision=4,
                expectedRevisionGlobalId=REVISION,
                expectedRevisionSnapshotHash="b" * 64,
            )
        self.assertEqual(response, outcome.response)
        self.assertEqual(self.frappe.local.response.http_status_code, 202)
        self.assertEqual(self.events[:3], ["csrf", ("authorize", PROJECT), ("create", PROJECT, CHANGE, {
            "expected_revision": 4,
            "expected_revision_global_id": self.module.UUID(REVISION),
            "expected_revision_snapshot_hash": "b" * 64,
            "idempotency_key_hash": "a" * 64,
        })])
        self.assertIn("commit", self.events)
        enqueue = next(value for value in self.events if isinstance(value, tuple) and value[0] == "enqueue")
        self.assertEqual(enqueue[1], "npi_integration.engineering_change.worker.execute_change_implementation_summary")
        self.assertFalse(enqueue[2]["enqueue_after_commit"])
        self.assertTrue(enqueue[2]["deduplicate"])

    def test_summary_replay_returns_200_and_does_not_enqueue(self) -> None:
        self.frappe.local.form_dict = {
            "expectedRevision": 4,
            "expectedRevisionGlobalId": REVISION,
            "expectedRevisionSnapshotHash": "b" * 64,
        }
        outcome = types.SimpleNamespace(
            response={"state": "succeeded", "requestGlobalId": REQUEST},
            replayed=True,
            should_enqueue=False,
            queue_id=None,
        )
        repository = types.SimpleNamespace(
            authorize_scope=lambda _project: True,
            create_summary_request=lambda *_args, **_kwargs: outcome,
        )
        with patch.object(self.module, "_repository", return_value=repository):
            self.module.request_change_implementation_summary(
                expectedRevision=4,
                expectedRevisionGlobalId=REVISION,
                expectedRevisionSnapshotHash="b" * 64,
            )
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(
            self.frappe.local.response.headers["Idempotency-Replayed"], "true"
        )
        self.assertFalse(any(isinstance(value, tuple) and value[0] == "enqueue" for value in self.events))

    def test_invalid_route_predecessor_hash_idempotency_or_hook_shape_fails_closed(self) -> None:
        for function, args in (
            (self.module._uuid, ("not-a-uuid", "changeId")),
            (self.module._positive, (0, "expectedRevision")),
            (self.module._hash, ("A" * 64, "expectedRevisionSnapshotHash")),
        ):
            with self.subTest(function=function.__name__), self.assertRaises(
                self.RequestValidationFailed
            ):
                function(*args)
        self.headers["Idempotency-Key"] = "short"
        with self.assertRaises(self.RequestValidationFailed):
            self.module._idempotency_key()
        self.frappe.get_hooks = lambda _name: ["one", "two"]
        with self.assertRaises(Exception):
            self.module._hook("npi_engineering_change_profile_resolver")


if __name__ == "__main__":
    unittest.main()
