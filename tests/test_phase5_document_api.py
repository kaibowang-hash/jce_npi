from __future__ import annotations

import copy
import importlib
import io
import sys
import types
import unittest
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
DOCUMENT_ID = "62d6ac02-b85f-4ae0-a522-953c4ebc2de4"
REVISION_ID = "590b332e-1ec4-44d8-8778-8b84eaf079bc"
FILE_REVISION_ID = "c74bd8c6-1a36-4367-a43f-1a6cbfe3a9c8"
POLICY_ID = "77932078-9512-428e-b9d7-863303661059"
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


class StubCallbacks:
    def __init__(self) -> None:
        self.callbacks: list[Any] = []

    def add(self, callback) -> None:
        self.callbacks.append(callback)

    def run(self) -> None:
        while self.callbacks:
            callback = self.callbacks.pop(0)
            callback()

    def reset(self) -> None:
        self.callbacks.clear()


class StubDatabase:
    def __init__(self, user_types: dict[str, str]) -> None:
        self.user_types = user_types
        self.rollback_count = 0
        self.rollback_failures_remaining = 0
        self.commit_count = 0
        self.commit_failure: str | None = None
        self.durable_receipt = False
        self.events: list[str] = []
        self.after_commit = StubCallbacks()

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
        if self.rollback_failures_remaining:
            self.rollback_failures_remaining -= 1
            raise RuntimeError("synthetic rollback failure")
        self.after_commit.reset()

    def commit(self) -> None:
        self.commit_count += 1
        self.events.append("commit")
        if self.commit_failure == "sql":
            raise RuntimeError("synthetic SQL commit failure")
        self.durable_receipt = True
        self.after_commit.run()


class StubHttpResponse:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.data = b""
        self.status_code = 200

    def set_data(self, data: str) -> None:
        self.data = data.encode("utf-8")


class FailOnDownloadTypeResponse(StubResponse):
    def __init__(self) -> None:
        super().__init__()
        self._failed = False

    def __setitem__(self, name: str, value: Any) -> None:
        if name == "type" and value == "download" and not self._failed:
            self._failed = True
            raise RuntimeError("synthetic response assembly failure")
        super().__setitem__(name, value)


class RecordingResponse(StubResponse):
    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self._events = events

    def __setitem__(self, name: str, value: Any) -> None:
        if name in {"filecontent", "type"}:
            self._events.append(name)
        super().__setitem__(name, value)


class UploadedFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self.stream = io.BytesIO(content)


class FileMap(dict):
    def getlist(self, key: str) -> list[object]:
        value = self.get(key)
        return value if isinstance(value, list) else [value]


class MockDocumentRepository:
    def __init__(self, owner: "Phase5DocumentApiTest") -> None:
        self.owner = owner
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []
        self.unavailable = False
        self.scope_authorized = True
        self.replayed = False

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope_authorized

    def _response(self) -> dict[str, Any] | None:
        return None if self.unavailable else copy.deepcopy(self.owner.workspace)

    def list_documents(self, *args: object, **kwargs: Any):
        self.calls.append(("list", args, kwargs))
        return self._response()

    def document_detail(self, *args: object, **kwargs: Any):
        self.calls.append(("detail", args, kwargs))
        return self._response()

    def create_document(self, *args: object, **kwargs: Any):
        self.calls.append(("create", args, kwargs))
        response = self._response()
        return (
            None
            if response is None
            else types.SimpleNamespace(
                response=response,
                replayed=self.replayed,
            )
        )

    def check_out(self, *args: object, **kwargs: Any):
        return self._command("check_out", args, kwargs)

    def check_in(self, *args: object, **kwargs: Any):
        return self._command("check_in", args, kwargs)

    def recover_lock(self, *args: object, **kwargs: Any):
        return self._command("recover", args, kwargs)

    def create_revision(self, *args: object, **kwargs: Any):
        return self._command("revision", args, kwargs)

    def file_capability(self, *args: object, **kwargs: Any):
        self.calls.append(("capability", args, kwargs))
        return self._response()

    def content(self, *args: object, **kwargs: Any):
        self.calls.append(("content", args, kwargs))
        if self.unavailable:
            return None
        self.owner.frappe.db.events.extend(("handler", "audit", "seal"))
        if self.owner.frappe.db.commit_failure == "after_commit":

            def fail_after_commit() -> None:
                raise RuntimeError("synthetic after-commit failure")

            self.owner.frappe.db.after_commit.add(fail_after_commit)
            self.owner.frappe.db.after_commit.add(
                lambda: self.owner.frappe.db.events.append("tail")
            )
        return types.SimpleNamespace(
            content=b"%PDF-1.7\nsynthetic",
            file_name="drawing.pdf",
            mime_type="application/pdf",
            disposition=kwargs["disposition"],
            replayed=self.replayed or self.owner.frappe.db.durable_receipt,
        )

    def _command(
        self,
        name: str,
        args: tuple[object, ...],
        kwargs: dict[str, Any],
    ):
        self.calls.append((name, args, kwargs))
        response = self._response()
        return (
            None
            if response is None
            else types.SimpleNamespace(
                response=response,
                replayed=self.replayed,
            )
        )


class Phase5DocumentApiTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.document_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p5-document-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase5-document-api",
        }
        self.roles = {
            "Administrator": ["System Manager"],
            "manager@example.invalid": ["System Manager"],
            "member@example.invalid": ["NPI API User"],
            "external@example.invalid": ["System Manager"],
        }
        self.user_types = {
            "Administrator": "System User",
            "manager@example.invalid": "System User",
            "member@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="Administrator")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p5_01_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "document_id": DOCUMENT_ID,
                "revision_id": REVISION_ID,
                "file_revision_id": FILE_REVISION_ID,
            },
        )
        self.frappe.local = types.SimpleNamespace(
            response=StubResponse(),
            request=types.SimpleNamespace(
                path="/",
                method="GET",
                files=FileMap(),
            ),
            form_dict=AttrDict(),
        )
        self.frappe.request = self.frappe.local.request
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda user: self.roles.get(user, [])
        self.frappe.db = StubDatabase(self.user_types)
        self.safe_logs: list[str] = []
        self.frappe.log_error = lambda **values: self.safe_logs.append(
            str(values.get("message", ""))
        )
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda message, *_args, **_kwargs: self.safe_logs.append(str(message))
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

        self.api = importlib.import_module("npi_core.document_api")
        self.core_api = importlib.import_module("npi_core.api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockDocumentRepository(self)
        self.factory_calls: list[dict[str, Any]] = []

        def repository_factory(**values: Any):
            self.factory_calls.append(values)
            return self.repository

        self.api._repository_factory = repository_factory
        self.workspace = {
            "project": {"globalId": PROJECT_ID},
            "permissions": {"view": True},
            "items": [],
            "nextCursor": None,
        }

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def reset(self, *, user: str = "Administrator") -> None:
        self.frappe.session.user = user
        self.frappe.local.response = StubResponse()
        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path="/",
            method="GET",
            files=FileMap(),
        )
        self.frappe.request = self.frappe.local.request
        self.frappe.flags.npi_bff_request = False
        self.frappe.flags.npi_response_headers = None
        self.frappe.flags.npi_response_body = None
        self.frappe.flags.npi_route_params = {
            "project_id": PROJECT_ID,
            "document_id": DOCUMENT_ID,
            "revision_id": REVISION_ID,
            "file_revision_id": FILE_REVISION_ID,
        }
        self.repository.calls.clear()
        self.repository.scope_authorized = True

    def call(self, command: str, function, payload: dict[str, Any]):
        self.frappe.local.form_dict = AttrDict({"cmd": command, **payload})
        return function(**payload)

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
        return result

    @staticmethod
    def create_payload() -> dict[str, object]:
        return {
            "policyGlobalId": POLICY_ID,
            "policyVersion": 1,
            "policySnapshotHash": "a" * 64,
            "documentTypeKey": "product_drawing",
            "title": "Synthetic drawing",
            "confidentialityKey": "internal",
            "objectLinks": [
                {
                    "kind": "project",
                    "targetIdentity": PROJECT_ID,
                    "targetVersion": 3,
                }
            ],
        }

    def test_query_authenticates_then_passes_closed_relationship_filter(self) -> None:
        self.reset(user="member@example.invalid")
        payload = {
            "limit": 25,
            "relationshipKind": "gate",
            "targetIdentity": REVISION_ID,
            "targetVersion": "2",
        }
        result = self.call(
            "npi_core.document_api.get_documents",
            self.api.get_documents,
            payload,
        )
        self.assertEqual(result, self.workspace)
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "list")
        self.assertEqual(args, (UUID(PROJECT_ID),))
        self.assertEqual(values["limit"], 25)
        self.assertEqual(values["relationship_kind"], "gate")
        self.assertEqual(values["target_identity"], REVISION_ID)
        self.assertEqual(values["target_version"], 2)

        self.reset(user="Guest")
        problem = self.assert_problem(
            self.call(
                "npi_core.document_api.get_documents",
                self.api.get_documents,
                {"relationshipKind": "not-supported"},
            ),
            401,
            "AUTHENTICATION_REQUIRED",
        )
        self.assertNotIn("fieldErrors", problem)
        self.assertFalse(self.repository.calls)

    def test_relationship_query_integer_is_canonical_and_bounded(self) -> None:
        for value in (
            "02",
            "+2",
            "2.0",
            " 2",
            "2147483648",
            2.0,
            True,
        ):
            with self.subTest(value=value):
                self.reset(user="member@example.invalid")
                problem = self.assert_problem(
                    self.call(
                        "npi_core.document_api.get_documents",
                        self.api.get_documents,
                        {
                            "relationshipKind": "gate",
                            "targetIdentity": REVISION_ID,
                            "targetVersion": value,
                        },
                    ),
                    422,
                    "VALIDATION_FAILED",
                )
                self.assertEqual(
                    problem["fieldErrors"][0]["path"],
                    "targetVersion",
                )
                self.assertNotIn(
                    "list",
                    [call[0] for call in self.repository.calls],
                )

        self.assertEqual(
            self.api._positive_query_integer(2, "targetVersion"),
            2,
        )

    def test_create_requires_internal_system_manager_csrf_and_closed_body(self) -> None:
        for user, status, code in (
            ("Guest", 401, "AUTHENTICATION_REQUIRED"),
            ("member@example.invalid", 403, "PERMISSION_DENIED"),
            ("external@example.invalid", 403, "PERMISSION_DENIED"),
        ):
            with self.subTest(user=user):
                self.reset(user=user)
                self.assert_problem(
                    self.call(
                        "npi_core.document_api.create_document",
                        self.api.create_document,
                        self.create_payload(),
                    ),
                    status,
                    code,
                )

        self.reset()
        self.headers.pop("X-Frappe-CSRF-Token")
        self.assert_problem(
            self.call(
                "npi_core.document_api.create_document",
                self.api.create_document,
                self.create_payload(),
            ),
            403,
            "CSRF_TOKEN_INVALID",
        )
        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + ("a" * 48)

        self.reset()
        invalid = self.create_payload()
        invalid["unexpected"] = True
        problem = self.assert_problem(
            self.call(
                "npi_core.document_api.create_document",
                self.api.create_document,
                invalid,
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "unexpected")

    def test_scope_authorization_precedes_body_filter_and_file_validation(
        self,
    ) -> None:
        self.reset(user="member@example.invalid")
        self.repository.scope_authorized = False
        problem = self.assert_problem(
            self.call(
                "npi_core.document_api.get_documents",
                self.api.get_documents,
                {"relationshipKind": "not-supported"},
            ),
            404,
            "DOCUMENT_UNAVAILABLE",
        )
        self.assertNotIn("fieldErrors", problem)
        self.assertEqual(self.repository.calls[-1][0], "authorize")

        self.reset()
        self.repository.scope_authorized = False
        self.frappe.local.request.files = FileMap(
            {
                "file": UploadedFile(
                    "../must-not-be-read.pdf",
                    b"%PDF-1.7\nmust-not-be-read",
                )
            }
        )
        problem = self.assert_problem(
            self.call(
                "npi_core.document_api.create_document_revision",
                self.api.create_document_revision,
                {"metadata": "not-json"},
            ),
            404,
            "DOCUMENT_UNAVAILABLE",
        )
        self.assertNotIn("fieldErrors", problem)
        self.assertEqual(self.repository.calls[-1][0], "authorize")

    def test_create_normalizes_exact_links_and_actor_bound_idempotency(self) -> None:
        result = self.call(
            "npi_core.document_api.create_document",
            self.api.create_document,
            self.create_payload(),
        )
        self.assertEqual(result, self.workspace)
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "create")
        self.assertEqual(args, (UUID(PROJECT_ID),))
        self.assertEqual(values["policy_global_id"], UUID(POLICY_ID))
        self.assertEqual(values["object_links"][0]["kind"], "project")
        self.assertEqual(len(values["idempotency_key"]), 64)
        self.assertNotEqual(
            values["idempotency_key"],
            self.headers["Idempotency-Key"],
        )
        self.assertEqual(self.frappe.local.response.http_status_code, 201)

        self.reset()
        duplicate = self.create_payload()
        duplicate["objectLinks"] = [
            duplicate["objectLinks"][0],
            copy.deepcopy(duplicate["objectLinks"][0]),
        ]
        problem = self.assert_problem(
            self.call(
                "npi_core.document_api.create_document",
                self.api.create_document,
                duplicate,
            ),
            422,
            "VALIDATION_FAILED",
        )
        self.assertEqual(problem["fieldErrors"][0]["path"], "objectLinks[1]")

    def test_revision_accepts_only_one_bounded_binary_and_closed_metadata(self) -> None:
        metadata = {
            "expectedDocumentVersion": 2,
            "expectedLockVersion": 1,
            "major": 1,
            "minor": 0,
            "reason": "Initial controlled revision",
            "effectiveDate": None,
            "predecessorRevisionId": None,
        }
        payload = {"metadata": __import__("json").dumps(metadata)}
        self.frappe.local.request.files = FileMap(
            {"file": UploadedFile("drawing.pdf", b"%PDF-1.7\nsynthetic")}
        )
        result = self.call(
            "npi_core.document_api.create_document_revision",
            self.api.create_document_revision,
            payload,
        )
        self.assertEqual(result, self.workspace)
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "revision")
        self.assertEqual(args, (UUID(PROJECT_ID), UUID(DOCUMENT_ID)))
        self.assertEqual(values["major"], 1)
        self.assertEqual(values["content"], b"%PDF-1.7\nsynthetic")
        self.assertEqual(values["file_name"], "drawing.pdf")

        self.reset()
        self.frappe.local.request.files = FileMap(
            {
                "file": UploadedFile("drawing.pdf", b"%PDF-1.7\nsynthetic"),
                "extra": UploadedFile("extra.pdf", b"%PDF-1.7\nextra"),
            }
        )
        self.assert_problem(
            self.call(
                "npi_core.document_api.create_document_revision",
                self.api.create_document_revision,
                payload,
            ),
            422,
            "VALIDATION_FAILED",
        )

        self.reset()
        metadata["sha256"] = "b" * 64
        self.frappe.local.request.files = FileMap(
            {"file": UploadedFile("drawing.pdf", b"%PDF-1.7\nsynthetic")}
        )
        self.assert_problem(
            self.call(
                "npi_core.document_api.create_document_revision",
                self.api.create_document_revision,
                {"metadata": __import__("json").dumps(metadata)},
            ),
            422,
            "VALIDATION_FAILED",
        )

    def test_content_commits_audit_before_binary_and_sets_safe_headers(self) -> None:
        self.frappe.local.response = RecordingResponse(self.frappe.db.events)
        payload = {
            "expectedDocumentVersion": 3,
            "expectedFileVersion": 1,
            "disposition": "inline",
        }
        result = self.call(
            "npi_core.document_api.get_file_content",
            self.api.get_file_content,
            payload,
        )
        self.assertIsNone(result)
        self.assertEqual(self.frappe.db.commit_count, 1)
        self.assertEqual(
            self.frappe.db.events,
            ["handler", "audit", "seal", "commit", "filecontent", "type"],
        )
        self.assertEqual(self.frappe.local.response.type, "download")
        self.assertEqual(
            self.frappe.local.response.content_type,
            "application/pdf",
        )
        self.assertEqual(
            self.frappe.local.response.filecontent,
            b"%PDF-1.7\nsynthetic",
        )
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(
            headers["Content-Length"],
            str(len(b"%PDF-1.7\nsynthetic")),
        )
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("filename*=UTF-8''drawing.pdf", headers["Content-Disposition"])
        self.assertNotIn("/private/files/", str(headers))

    def test_invalid_binary_payload_never_commits_or_exposes_bytes(self) -> None:
        with self.assertRaises(self.core_api._BinaryResponseFailure):
            self.core_api.frappe_binary_call(
                lambda: object(),
                response_headers={
                    "X-Request-ID": REQUEST_ID,
                    "Idempotency-Replayed": "true",
                },
            )
        self.frappe.db.rollback()

        self.assertEqual(self.frappe.db.commit_count, 0)
        self.assertEqual(self.frappe.db.rollback_count, 1)
        self.assertEqual(
            self.frappe.flags.npi_response_body["code"],
            "INTERNAL_SERVER_ERROR",
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )
        self.assertNotIn(
            "Idempotency-Replayed",
            self.frappe.flags.npi_response_headers,
        )
        self.assertNotIn("filecontent", self.frappe.local.response)
        self.assertNotIn("type", self.frappe.local.response)
        response = StubHttpResponse()
        self.router.attach_response_headers(response=response)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.headers["Content-Type"],
            "application/problem+json",
        )

    def test_transient_binary_problem_rollback_failure_is_safely_contained(
        self,
    ) -> None:
        self.repository.unavailable = True
        self.frappe.db.rollback_failures_remaining = 1

        with self.assertRaises(self.core_api._BinaryResponseFailure):
            self.call(
                "npi_core.document_api.get_file_content",
                self.api.get_file_content,
                {
                    "expectedDocumentVersion": 3,
                    "expectedFileVersion": 1,
                    "disposition": "inline",
                },
            )
        self.frappe.db.rollback()

        self.assertEqual(self.frappe.db.rollback_count, 2)
        self.assertEqual(self.frappe.db.commit_count, 0)
        self.assertTrue(
            any("BINARY_ROLLBACK_FAILED" in item for item in self.safe_logs)
        )
        self.assertEqual(
            self.frappe.flags.npi_response_body["code"],
            "INTERNAL_SERVER_ERROR",
        )
        self.assertNotIn("filecontent", self.frappe.local.response)
        response = StubHttpResponse()
        self.router.attach_response_headers(response=response)
        self.assertEqual(response.status_code, 500)

    def test_binary_sql_commit_failure_is_unknown_and_skips_second_commit(
        self,
    ) -> None:
        self.frappe.db.commit_failure = "sql"
        with self.assertRaises(self.core_api._BinaryResponseFailure):
            self.call(
                "npi_core.document_api.get_file_content",
                self.api.get_file_content,
                {
                    "expectedDocumentVersion": 3,
                    "expectedFileVersion": 1,
                    "disposition": "inline",
                },
            )
        # This models Frappe's exception finalizer. A normal return would cause
        # its unsafe-method success path to call commit a second time.
        self.frappe.db.rollback()

        self.assertEqual(self.frappe.db.commit_count, 1)
        self.assertEqual(self.frappe.db.rollback_count, 1)
        self.assertTrue(
            any("BINARY_COMMIT_OUTCOME_UNCERTAIN" in item for item in self.safe_logs)
        )
        self.assertEqual(
            self.frappe.flags.npi_response_body["code"],
            "INTERNAL_SERVER_ERROR",
        )
        self.assertNotIn("filecontent", self.frappe.local.response)
        response = StubHttpResponse()
        self.router.attach_response_headers(response=response)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["X-Request-ID"], REQUEST_ID)
        self.assertEqual(
            response.headers["X-Trace-ID"],
            "trace-phase5-document-api",
        )
        self.assertEqual(
            response.headers["Content-Type"],
            "application/problem+json",
        )
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        for name in (
            "Content-Disposition",
            "Content-Length",
            "Idempotency-Replayed",
        ):
            self.assertNotIn(name, response.headers)
        self.assertNotIn("synthetic", response.data.decode("utf-8"))

    def test_binary_after_commit_failure_is_recorded_and_retry_replays(
        self,
    ) -> None:
        self.frappe.db.commit_failure = "after_commit"
        with self.assertRaises(self.core_api._BinaryResponseFailure):
            self.call(
                "npi_core.document_api.get_file_content",
                self.api.get_file_content,
                {
                    "expectedDocumentVersion": 3,
                    "expectedFileVersion": 1,
                    "disposition": "attachment",
                },
            )
        self.frappe.db.rollback()

        self.assertEqual(self.frappe.db.commit_count, 1)
        self.assertTrue(self.frappe.db.durable_receipt)
        self.assertFalse(self.frappe.db.after_commit.callbacks)
        self.assertNotIn("tail", self.frappe.db.events)
        self.assertTrue(
            any("BINARY_AFTER_COMMIT_FAILED" in item for item in self.safe_logs)
        )
        self.assertNotIn("filecontent", self.frappe.local.response)
        failed_response = StubHttpResponse()
        self.router.attach_response_headers(response=failed_response)
        self.assertEqual(failed_response.status_code, 500)
        self.assertEqual(
            failed_response.headers["Content-Type"],
            "application/problem+json",
        )
        self.assertNotIn("Idempotency-Replayed", failed_response.headers)

        self.reset()
        self.frappe.db.commit_failure = None
        self.call(
            "npi_core.document_api.get_file_content",
            self.api.get_file_content,
            {
                "expectedDocumentVersion": 3,
                "expectedFileVersion": 1,
                "disposition": "attachment",
            },
        )
        self.assertEqual(self.frappe.db.commit_count, 2)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )
        self.assertEqual(self.frappe.local.response.type, "download")

    def test_post_commit_response_failure_clears_bytes_and_sets_problem_status(
        self,
    ) -> None:
        self.frappe.local.response = FailOnDownloadTypeResponse()
        with self.assertRaises(self.core_api._BinaryResponseFailure):
            self.call(
                "npi_core.document_api.get_file_content",
                self.api.get_file_content,
                {
                    "expectedDocumentVersion": 3,
                    "expectedFileVersion": 1,
                    "disposition": "inline",
                },
            )
        self.frappe.db.rollback()

        self.assertEqual(self.frappe.db.commit_count, 1)
        self.assertTrue(
            any("BINARY_RESPONSE_ASSEMBLY_FAILED" in item for item in self.safe_logs)
        )
        for name in (
            "type",
            "filename",
            "filecontent",
            "display_content_as",
            "content_type",
        ):
            self.assertNotIn(name, self.frappe.local.response)
        response = StubHttpResponse()
        self.router.attach_response_headers(response=response)
        self.assertEqual(response.status_code, 500)
        problem = __import__("json").loads(response.data)
        self.assertEqual(problem["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(
            response.headers["Cache-Control"],
            "private, no-store",
        )

    def test_success_body_status_field_does_not_override_http_status(self) -> None:
        self.frappe.flags.npi_response_body = {
            "status": 201,
            "result": "synthetic",
        }
        self.frappe.flags.npi_response_headers = {
            "Content-Type": "application/json",
        }
        response = StubHttpResponse()

        self.router.attach_response_headers(response=response)

        self.assertEqual(response.status_code, 200)

    def test_unavailable_identity_uses_one_document_problem(self) -> None:
        self.repository.unavailable = True
        self.assert_problem(
            self.call(
                "npi_core.document_api.get_document",
                self.api.get_document,
                {},
            ),
            404,
            "DOCUMENT_UNAVAILABLE",
        )
        self.reset()
        self.assert_problem(
            self.call(
                "npi_core.document_api.create_document",
                self.api.create_document,
                self.create_payload(),
            ),
            404,
            "DOCUMENT_UNAVAILABLE",
        )

    def test_routes_are_exact_request_correlated_and_independently_disabled(
        self,
    ) -> None:
        routes = (
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents",
                "get_documents",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents",
                "create_document",
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}",
                "get_document",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}:check-out",
                "check_out_document",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}:check-in",
                "check_in_document",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents/"
                f"{DOCUMENT_ID}:recover-lock",
                "recover_document_lock",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}/revisions",
                "create_document_revision",
            ),
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}"
                f"/revisions/{REVISION_ID}/files/{FILE_REVISION_ID}/capabilities",
                "get_file_capabilities",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/documents/{DOCUMENT_ID}"
                f"/revisions/{REVISION_ID}/files/{FILE_REVISION_ID}:content",
                "get_file_content",
            ),
        )
        for method, path, function_name in routes:
            with self.subTest(method=method, path=path):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                    files=FileMap(),
                )
                self.frappe.request = self.frappe.local.request
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    f"npi_core.document_api.{function_name}",
                )
                self.assertTrue(self.router._requires_project_request_id(method, path))

        self.frappe.conf.npi_p5_01_routes_disabled = True
        self.frappe.local.form_dict = AttrDict()
        path = f"/api/npi/v1/projects/{PROJECT_ID}/documents"
        self.frappe.local.request = types.SimpleNamespace(
            path=path,
            method="GET",
            files=FileMap(),
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.document_routes_disabled",
        )
        self.reset(user="member@example.invalid")
        self.assert_problem(
            self.call(
                "npi_core.document_api.get_documents",
                self.api.get_documents,
                {},
            ),
            503,
            "DOCUMENT_ROUTES_DISABLED",
        )

    def test_endpoint_methods_are_exact(self) -> None:
        expected = {
            self.api.get_documents: ("GET",),
            self.api.create_document: ("POST",),
            self.api.get_document: ("GET",),
            self.api.check_out_document: ("POST",),
            self.api.check_in_document: ("POST",),
            self.api.recover_document_lock: ("POST",),
            self.api.create_document_revision: ("POST",),
            self.api.get_file_capabilities: ("GET",),
            self.api.get_file_content: ("POST",),
        }
        for endpoint, methods in expected.items():
            self.assertTrue(endpoint.allow_guest)
            self.assertEqual(endpoint.allowed_methods, methods)


if __name__ == "__main__":
    unittest.main()
