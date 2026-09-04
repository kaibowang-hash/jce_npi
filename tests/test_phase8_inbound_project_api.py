from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.inbound_project.signature import WEBHOOK_PATH
from tests.test_phase8_inbound_project_domain import raw, uid
from tests.test_phase8_inbound_project_ingress import headers_for
from tests.test_phase8_inbound_project_signature_config import NOW, profile


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeRequest:
    def __init__(
        self,
        body: bytes,
        *,
        content_type: str = "application/json",
        path: str = WEBHOOK_PATH,
        method: str = "POST",
        is_secure: bool = False,
        content_length: int | None = None,
        headers: dict[str, str] | None = None,
        event_log: list[str] | None = None,
    ) -> None:
        self.body = body
        self.content_type = content_type
        self.path = path
        self.method = method
        self.is_secure = is_secure
        self.content_length = len(body) if content_length is None else content_length
        self.headers = headers or {}
        self.event_log = event_log if event_log is not None else []
        self.read_forbidden = False

    def get_data(self, *, cache: bool, as_text: bool) -> bytes:
        self.event_log.append("read")
        if self.read_forbidden:
            raise AssertionError("Oversized body must not be read by the adapter.")
        if cache is not True or as_text is not False:
            raise AssertionError("Raw request bytes must be cached without decoding.")
        return self.body


class FakeDatabase:
    def __init__(self, owner: "Phase8InboundProjectApiTest") -> None:
        self.owner = owner
        self.events = owner.events
        self.fail_commit = False

    def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit:
            raise RuntimeError("synthetic commit failure with secret material")

    def rollback(self) -> None:
        self.events.append("rollback")
        self.owner.partial_rows.clear()


class FakeRepository:
    def __init__(self, owner: "Phase8InboundProjectApiTest") -> None:
        self.owner = owner
        self.mode = "accepted"
        self.land_calls: list[object] = []
        self.rejection_audits: list[dict[str, object]] = []

    def land(self, authenticated):
        self.owner.events.append("land")
        self.land_calls.append(authenticated)
        if self.mode == "primary_unique_race" and len(self.land_calls) == 1:
            raise self.owner.frappe.DuplicateEntryError()
        if self.mode == "field_unique_race" and len(self.land_calls) == 1:
            raise self.owner.frappe.UniqueValidationError()
        if self.mode == "partial_raise":
            self.owner.partial_rows.extend(
                ["NPI Inbox Message", "NPI Project Source Binding"]
            )
            raise RuntimeError("synthetic failure after partial transaction writes")
        if self.mode == "raise":
            raise RuntimeError("synthetic raw secret and signature failure")
        disposition = self.owner.repository_module.LandingDisposition.ACCEPTED
        exact_duplicate = False
        should_enqueue = True
        conflict_code = None
        state = "pending"
        if self.mode == "duplicate":
            disposition = (
                self.owner.repository_module.LandingDisposition.EVENT_EXACT_REPLAY
            )
            exact_duplicate = True
            should_enqueue = False
        elif self.mode == "conflict":
            disposition = self.owner.repository_module.LandingDisposition.SOURCE_CONFLICT
            should_enqueue = False
            conflict_code = "INBOUND_PROJECT_SOURCE_CONFLICT"
            state = "quarantined"
        return self.owner.repository_module.InboundProjectLandingOutcome(
            receipt_id=UUID(int=800),
            event_id=authenticated.event.event_id,
            state=state,
            trace_id=authenticated.event.trace_id,
            disposition=disposition,
            exact_duplicate=exact_duplicate,
            should_enqueue=should_enqueue,
            conflict_code=conflict_code,
        )

    def append_ingress_failure_audit(self, **values: object) -> None:
        self.owner.events.append("rejection_audit")
        self.rejection_audits.append(dict(values))


class Phase8InboundProjectApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.bff",
        "npi_integration.inbound_project.frappe_validation",
        "npi_integration.inbound_project.frappe_repository",
        "npi_integration.inbound_project_api",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        self.partial_rows: list[str] = []
        self.diagnostics: list[object] = []
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.local = types.SimpleNamespace(
            request=None,
            response=AttrDict(),
            form_dict=AttrDict(),
        )
        self.frappe.db = FakeDatabase(self)
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        self.frappe.UniqueValidationError = type(
            "UniqueValidationError", (Exception,), {}
        )
        self.frappe.whitelist = lambda **_kwargs: lambda function: function
        self.frappe.logger = lambda *_args, **_kwargs: types.SimpleNamespace(
            error=lambda *args, **kwargs: self.diagnostics.append((args, kwargs))
        )
        self.frappe.log_error = lambda **values: self.diagnostics.append(values)
        self.frappe.get_hooks = lambda _name: []
        self.frappe.get_attr = lambda _path: None
        self.frappe.enqueue = lambda *_args, **_kwargs: None
        sys.modules["frappe"] = self.frappe
        self.api = importlib.import_module("npi_integration.inbound_project_api")
        self.repository_module = importlib.import_module(
            "npi_integration.inbound_project.frappe_repository"
        )
        self.repository = FakeRepository(self)

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved_modules[name] is not None:
                sys.modules[name] = self.saved_modules[name]

    def request(
        self,
        body: bytes | None = None,
        *,
        valid_signature: bool = True,
        **changes: object,
    ) -> FakeRequest:
        candidate = raw() if body is None else body
        signed = headers_for(candidate, request_id=uid(500))
        headers = {
            "X-Request-ID": signed.request_id,
            "X-NPI-Key-ID": signed.key_id,
            "X-NPI-Timestamp": signed.timestamp,
            "X-NPI-Signature": (
                signed.signature if valid_signature else "v1=" + "0" * 64
            ),
        }
        values: dict[str, object] = {
            "content_type": "application/json",
            "path": WEBHOOK_PATH,
            "method": "POST",
            "is_secure": False,
            "headers": headers,
            "event_log": self.events,
        }
        values.update(changes)
        return FakeRequest(candidate, **values)  # type: ignore[arg-type]

    def execute(
        self,
        request: FakeRequest,
        *,
        profile_resolver=lambda: profile(),
        enqueue=None,
    ) -> None:
        enqueue_callback = enqueue or (
            lambda receipt_id: self.events.append(f"enqueue:{receipt_id}")
        )
        self.api._execute_inbound_request(
            request=request,
            repository=self.repository,
            profile_resolver=profile_resolver,
            secret_resolver=lambda _reference: (
                b"old-synthetic-secret-material-000000000001"
            ),
            site_tenant_resolver=lambda: "tenant-synthetic",
            clock=lambda: NOW,
            enqueue=enqueue_callback,
        )

    def reset_response(self) -> None:
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.local.response = AttrDict()
        self.events.clear()
        self.partial_rows.clear()
        self.repository = FakeRepository(self)
        self.frappe.db.fail_commit = False

    def assert_response(self, status: int, code: str | None = None) -> dict[str, object]:
        body = self.frappe.flags.npi_response_body
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(self.frappe.local.response.http_status_code, status)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Request-ID"], uid(500))
        self.assertEqual(headers["X-Trace-ID"], body["traceId"])
        if code is None:
            self.assertEqual(headers["Content-Type"], "application/json")
        else:
            self.assertEqual(headers["Content-Type"], "application/problem+json")
            self.assertEqual(body["code"], code)
            self.assertEqual(body["status"], status)
        return body

    def test_success_commits_before_202_and_enqueues_only_new_pending_receipt(self) -> None:
        self.execute(self.request())
        body = self.assert_response(202)
        self.assertEqual(body["receiptId"], str(UUID(int=800)))
        self.assertFalse(body["exactDuplicate"])
        self.assertEqual(
            self.events,
            ["read", "land", "commit", f"enqueue:{UUID(int=800)}"],
        )
        self.reset_response()
        self.repository.mode = "duplicate"
        self.execute(self.request())
        body = self.assert_response(202)
        self.assertTrue(body["exactDuplicate"])
        self.assertEqual(self.events, ["read", "land", "commit"])

    def test_closed_status_matrix_and_route_recovery(self) -> None:
        cases = (
            (
                401,
                "INBOUND_PROJECT_AUTHENTICATION_FAILED",
                lambda: self.request(valid_signature=False),
                lambda: profile(),
                "accepted",
            ),
            (
                415,
                "INBOUND_PROJECT_MEDIA_TYPE_UNSUPPORTED",
                lambda: self.request(content_type="text/plain"),
                lambda: profile(),
                "accepted",
            ),
            (
                413,
                "INBOUND_PROJECT_BODY_TOO_LARGE",
                lambda: self.request(content_length=262_145),
                lambda: profile(),
                "accepted",
            ),
            (
                422,
                "INBOUND_PROJECT_EVENT_INVALID",
                lambda: self.request(b'{"event_id":'),
                lambda: profile(),
                "accepted",
            ),
            (
                503,
                "INBOUND_PROJECT_INGRESS_UNAVAILABLE",
                self.request,
                lambda: None,
                "accepted",
            ),
            (
                409,
                "INBOUND_PROJECT_SOURCE_CONFLICT",
                self.request,
                lambda: profile(),
                "conflict",
            ),
            (
                500,
                "INTERNAL_SERVER_ERROR",
                self.request,
                lambda: profile(),
                "raise",
            ),
        )
        for status, code, request_factory, resolver, mode in cases:
            with self.subTest(status=status):
                self.reset_response()
                request = request_factory()
                if status == 413:
                    request.read_forbidden = True
                self.repository.mode = mode
                self.execute(request, profile_resolver=resolver)
                self.assert_response(status, code)
                if status not in {409}:
                    self.assertEqual(len(self.repository.rejection_audits), 1)
        self.reset_response()
        self.execute(self.request(), profile_resolver=lambda: profile())
        self.assert_response(202)

    def test_tls_uses_server_fact_and_generic_method_cannot_bypass_fixed_path(self) -> None:
        request = self.request()
        request.headers["X-Forwarded-Proto"] = "https"
        self.execute(
            request,
            profile_resolver=lambda: profile(trusted_tls_termination=False),
        )
        self.assert_response(401, "INBOUND_PROJECT_AUTHENTICATION_FAILED")
        self.assertFalse(self.repository.land_calls)
        self.reset_response()
        generic = self.request(
            path=(
                "/api/method/"
                "npi_integration.inbound_project_api.accept_project_source_event"
            )
        )
        self.execute(generic)
        self.assert_response(401, "INBOUND_PROJECT_AUTHENTICATION_FAILED")
        self.assertFalse(self.repository.land_calls)

    def test_invalid_request_id_is_never_echoed_or_used_as_trace_identity(self) -> None:
        request = self.request()
        request.headers["X-Request-ID"] = "not-a-canonical-request-id"
        self.execute(request)
        body = self.frappe.flags.npi_response_body
        headers = self.frappe.flags.npi_response_headers
        generated = UUID(headers["X-Request-ID"])
        self.assertNotEqual(str(generated), request.headers["X-Request-ID"])
        self.assertEqual(body["code"], "INBOUND_PROJECT_AUTHENTICATION_FAILED")
        self.assertEqual(body["traceId"], f"inbound-{generated}")
        self.assertNotIn(request.headers["X-Request-ID"], repr(body))

    def test_failure_rolls_back_and_never_exposes_raw_secret_signature_or_traceback(self) -> None:
        self.repository.mode = "partial_raise"
        request = self.request()
        request.headers["Authorization"] = "Bearer synthetic-secret"
        request.headers["Cookie"] = "sid=synthetic-secret"
        self.execute(request)
        body = self.assert_response(500, "INTERNAL_SERVER_ERROR")
        self.assertIn("rollback", self.events)
        self.assertFalse(self.partial_rows)
        self.assertEqual(len(self.repository.rejection_audits), 1)
        serialized = repr(
            {
                "body": body,
                "headers": self.frappe.flags.npi_response_headers,
                "audit": self.repository.rejection_audits,
                "diagnostics": self.diagnostics,
            }
        ).casefold()
        for forbidden in (
            "bearer synthetic-secret",
            "sid=synthetic-secret",
            request.headers["X-NPI-Signature"],
            request.body.decode("utf-8"),
            "traceback",
        ):
            self.assertNotIn(forbidden.casefold(), serialized)

    def test_commit_failure_never_acknowledges_or_enqueues(self) -> None:
        self.frappe.db.fail_commit = True
        with self.assertRaises(self.api._InboundProjectCommitFailure):
            self.execute(self.request())
        self.assert_response(500, "INTERNAL_SERVER_ERROR")
        self.assertIn("rollback", self.events)
        self.assertFalse(any(value.startswith("enqueue:") for value in self.events))
        self.reset_response()
        self.frappe.db.fail_commit = True
        with self.assertRaises(self.api._InboundProjectCommitFailure):
            self.execute(self.request(valid_signature=False))
        self.assert_response(500, "INTERNAL_SERVER_ERROR")
        self.assertFalse(any(value.startswith("enqueue:") for value in self.events))

    def test_unique_reservation_race_rolls_back_partial_truth_and_reclassifies_once(self) -> None:
        for mode in ("primary_unique_race", "field_unique_race"):
            with self.subTest(mode=mode):
                self.reset_response()
                self.repository.mode = mode
                self.execute(self.request())
                self.assert_response(202)
                self.assertEqual(len(self.repository.land_calls), 2)
                self.assertEqual(
                    self.events,
                    [
                        "read",
                        "land",
                        "rollback",
                        "land",
                        "commit",
                        f"enqueue:{UUID(int=800)}",
                    ],
                )

    def test_bff_maps_only_exact_post_and_closes_trailing_generic_and_options(self) -> None:
        bff = importlib.import_module("npi_core.bff")
        exact_command = "npi_integration.inbound_project_api.accept_project_source_event"
        for method, path, expected in (
            ("POST", WEBHOOK_PATH, exact_command),
            ("POST", WEBHOOK_PATH + "/", "npi_core.bff.route_not_found"),
            ("GET", WEBHOOK_PATH, "npi_core.bff.route_not_found"),
        ):
            with self.subTest(method=method, path=path):
                self.frappe.local.request = types.SimpleNamespace(
                    method=method,
                    path=path,
                )
                self.frappe.local.form_dict = AttrDict()
                self.frappe.flags = types.SimpleNamespace()
                bff.route_request()
                self.assertEqual(self.frappe.local.form_dict.cmd, expected)
        self.frappe.local.request = types.SimpleNamespace(
            method="OPTIONS",
            path=WEBHOOK_PATH,
        )
        self.frappe.local.form_dict = AttrDict()
        bff.route_request()
        self.assertNotIn("cmd", self.frappe.local.form_dict)


if __name__ == "__main__":
    unittest.main()
