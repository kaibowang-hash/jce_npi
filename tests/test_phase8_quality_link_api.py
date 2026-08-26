from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "00000000-0000-4000-8000-00000000c601"
LINK = "00000000-0000-4000-8000-00000000c602"
SOURCE = "00000000-0000-4000-8000-00000000c603"
OBSERVATION = "00000000-0000-4000-8000-00000000c604"
PROJECTION_HEAD = "00000000-0000-4000-8000-00000000c605"
REQUEST = "00000000-0000-4000-8000-00000000c606"
ACKNOWLEDGEMENT = (
    "I confirm this links only the exact observed formal quality reference. "
    "It does not write ERPNext or interpret a formal pass."
)


class FakeRepository:
    def __init__(self, owner: "Phase8QualityLinkApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def authorize_scope(self, *args: object, **kwargs: object) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def list_quality_links(self, *args: object, **kwargs: object):
        self.calls.append(("list", args, kwargs))
        return {
            "projectGlobalId": PROJECT,
            "permissions": {"view": True, "link": False},
            "items": [],
        }

    def quality_link_detail(self, *args: object, **kwargs: object):
        self.calls.append(("detail", args, kwargs))
        return {
            "projectGlobalId": PROJECT,
            "permissions": {"view": True, "link": False},
            "link": {
                "reconciliation": {
                    "state": "current",
                    "reasonCode": "linked_truth_current",
                }
            },
        }

    def link_observed_formal_quality_reference(self, *args: object, **kwargs: object):
        self.calls.append(("link", args, kwargs))
        return types.SimpleNamespace(
            replayed=self.owner.replayed,
            response={
                "projectGlobalId": PROJECT,
                "operation": "link_observed_formal_quality_reference",
                "linkRevision": {"globalId": LINK},
                "linkHead": {"globalId": LINK},
                "formalQualityInterpretation": {
                    "state": "unavailable",
                    "reasonCode": "raw_formal_quality_codes_not_interpreted",
                },
            },
        )


class Phase8QualityLinkApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.foundation.errors",
        "npi_core.foundation.security",
        "npi_core.foundation.tracing",
        "npi_core.project.domain",
        "npi_core.request_security",
        "npi_integration.quality_link.problems",
        "npi_integration.quality_link_api",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.replayed = False
        self.external = False
        self.events: list[str] = []
        self.headers = {"X-Request-ID": REQUEST, "Idempotency-Key": "quality-link-command"}
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda value: value
        self.frappe.flags = types.SimpleNamespace(
            npi_route_params={"project_id": PROJECT, "formal_quality_link_id": LINK}
        )
        self.frappe.session = types.SimpleNamespace(user="quality@example.invalid")
        self.frappe.local = types.SimpleNamespace(
            response=types.SimpleNamespace(http_status_code=200),
            form_dict={},
        )
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.db = types.SimpleNamespace(
            commit=lambda: self.events.append("commit"),
            rollback=lambda: self.events.append("rollback"),
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function
            return decorate

        self.frappe.whitelist = whitelist
        sys.modules["frappe"] = self.frappe

        errors = types.ModuleType("npi_core.foundation.errors")

        class NpiProblem(Exception):
            def __init__(self, status: int = 500, code: str = "PROBLEM", title: object = None):
                super().__init__(title)
                self.status = status
                self.code = code
                self.title = title

        class PermissionDenied(NpiProblem):
            pass

        class RequestValidationFailed(NpiProblem):
            def __init__(self, fields: object):
                super().__init__(422, "REQUEST_VALIDATION_FAILED", fields)
                self.fields = fields

        errors.NpiProblem = NpiProblem
        errors.PermissionDenied = PermissionDenied
        errors.RequestValidationFailed = RequestValidationFailed
        sys.modules["npi_core.foundation.errors"] = errors

        api = types.ModuleType("npi_core.api")

        def domain_call(handle, *, success_status=200, response_headers=None, **_kwargs):
            result = handle()
            self.frappe.local.response.http_status_code = success_status
            self.frappe.local.response.headers = dict(response_headers or {})
            return result

        api.frappe_domain_call = domain_call
        sys.modules["npi_core.api"] = api
        security = types.ModuleType("npi_core.foundation.security")
        security.Principal = object
        sys.modules["npi_core.foundation.security"] = security
        tracing = types.ModuleType("npi_core.foundation.tracing")
        tracing.current_trace_id = ContextVar("quality-link-api-trace", default="trace-quality-link-api")
        sys.modules["npi_core.foundation.tracing"] = tracing
        project = types.ModuleType("npi_core.project.domain")
        project.actor_idempotency_key_hash = lambda actor, key: "c" * 64 if actor and key else None
        sys.modules["npi_core.project.domain"] = project

        request_security = types.ModuleType("npi_core.request_security")
        request_security.TRANSPORT_FIELDS = frozenset({"cmd"})
        request_security.authenticated_user = lambda: self.frappe.session.user
        request_security.authenticated_principal = lambda _actor: types.SimpleNamespace(
            is_external=self.external
        )
        request_security.require_csrf_token = lambda: self.events.append("csrf")
        request_security.response_request_id = lambda: REQUEST

        def reject(allowed, supplied):
            form = set(self.frappe.local.form_dict)
            unexpected = (form | set(supplied)) - set(allowed) - {"cmd"}
            if unexpected:
                raise RequestValidationFailed({name: "unexpected" for name in sorted(unexpected)})

        def require(required, supplied):
            missing = [name for name in required if supplied.get(name) is None]
            if missing:
                raise RequestValidationFailed({name: "required" for name in missing})

        request_security.reject_unexpected_request_fields = reject
        request_security.require_request_fields = require
        sys.modules["npi_core.request_security"] = request_security

        self.repository = FakeRepository(self)
        self.module = importlib.import_module("npi_integration.quality_link_api")
        self.factory = patch.object(self.module, "_repository_factory", return_value=self.repository)
        self.factory.start()

    def tearDown(self) -> None:
        self.factory.stop()
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def command(self, **overrides: object):
        values = {
            "sourceKind": "trial_defect",
            "sourceGlobalId": SOURCE,
            "expectedSourceVersion": 2,
            "expectedSourceSnapshotHash": "a" * 64,
            "formalObservationGlobalId": OBSERVATION,
            "expectedProjectionHeadGlobalId": PROJECTION_HEAD,
            "expectedProjectionHeadVersion": 3,
            "expectedProjectionHeadHash": "b" * 64,
            "expectedLinkHeadVersion": 0,
            "acknowledgement": ACKNOWLEDGEMENT,
        }
        values.update(overrides)
        return self.module.link_observed_formal_quality_reference(**values)

    def test_project_first_list_detail_and_command_are_fixed(self) -> None:
        self.assertEqual(self.module.get_formal_quality_links()["items"], [])
        detail = self.module.get_formal_quality_link()
        self.assertEqual(detail["projectGlobalId"], PROJECT)
        self.assertEqual(detail["link"]["reconciliation"]["state"], "current")
        result = self.command()
        self.assertEqual(result["operation"], "link_observed_formal_quality_reference")
        self.assertEqual(self.events, ["csrf", "commit"])
        call = [item for item in self.repository.calls if item[0] == "link"][0]
        self.assertEqual(call[1], (self.module.UUID(PROJECT),))
        self.assertEqual(
            set(call[2]),
            {
                "source_kind", "source_global_id", "expected_source_version",
                "expected_source_snapshot_hash", "observation_global_id",
                "expected_projection_head_global_id", "expected_projection_head_version",
                "expected_projection_head_hash", "expected_link_head_version",
                "idempotency_key_hash",
            },
        )

    def test_replay_is_200_and_commit_precedes_response(self) -> None:
        self.replayed = True
        self.command()
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(self.frappe.local.response.headers["Idempotency-Replayed"], "true")
        self.assertEqual(self.events[-1], "commit")

    def test_unknown_fields_bad_ack_and_unavailable_scope_fail_closed(self) -> None:
        self.frappe.local.form_dict = {"unknown": "hidden"}
        with self.assertRaises(Exception):
            self.command()
        self.frappe.local.form_dict = {}
        with self.assertRaises(Exception):
            self.command(acknowledgement="yes")
        self.repository.scope = False
        with self.assertRaises(Exception):
            self.module.get_formal_quality_links()
        self.assertNotIn("commit", self.events)

    def test_external_actor_and_foreign_detail_are_permission_safe(self) -> None:
        self.external = True
        with self.assertRaises(Exception):
            self.module.get_formal_quality_links()
        self.external = False
        self.repository.quality_link_detail = lambda *_args, **_kwargs: None
        with self.assertRaises(Exception):
            self.module.get_formal_quality_link()
        self.assertNotIn("commit", self.events)

    def test_commit_failure_rolls_back_and_never_reports_success(self) -> None:
        def fail_commit():
            self.events.append("commit")
            raise RuntimeError("synthetic commit failure")

        self.frappe.db.commit = fail_commit
        with self.assertRaisesRegex(RuntimeError, "synthetic commit failure"):
            self.command()
        self.assertEqual(self.events[-2:], ["commit", "rollback"])

    def test_route_and_source_contracts_are_closed(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for marker in (
            "_PROJECT_FORMAL_QUALITY_LINKS_ROUTE",
            "_PROJECT_FORMAL_QUALITY_LINK_ROUTE",
            "_PROJECT_FORMAL_QUALITY_LINK_COMMAND_ROUTE",
            "npi_integration.quality_link_api.get_formal_quality_links",
            "npi_integration.quality_link_api.link_observed_formal_quality_reference",
        ):
            self.assertIn(marker, source)
        api_source = (ROOT / "apps/npi_integration/npi_integration/quality_link_api.py").read_text(encoding="utf-8")
        self.assertNotIn("enqueue(", api_source)
        self.assertNotIn("ignore_permissions", api_source)

    def test_query_reconciliation_shape_is_closed_before_serialization(self) -> None:
        original = self.repository.quality_link_detail
        for reconciliation in (
            None,
            {"state": "latest", "reasonCode": "linked_truth_current"},
            {"state": "current", "reasonCode": "linked_source_advanced"},
            {
                "state": "unavailable",
                "reasonCode": "current_truth_unavailable",
                "currentGlobalId": SOURCE,
            },
        ):
            with self.subTest(reconciliation=reconciliation):
                self.repository.quality_link_detail = lambda *_args, **_kwargs: {
                    "projectGlobalId": PROJECT,
                    "permissions": {"view": True, "link": False},
                    "link": {"reconciliation": reconciliation},
                }
                with self.assertRaisesRegex(RuntimeError, "reconciliation"):
                    self.module.get_formal_quality_link()
        self.repository.quality_link_detail = original
        result = self.module.get_formal_quality_link()
        self.assertEqual(
            set(result["link"]["reconciliation"]),
            {"state", "reasonCode"},
        )
        self.assertNotIn("commit", self.events)

    def test_query_capability_is_server_supplied_boolean_and_shape_is_closed(self) -> None:
        self.repository.list_quality_links = lambda *_args, **_kwargs: {
            "projectGlobalId": PROJECT,
            "permissions": {"view": True, "link": True},
            "items": [],
        }
        result = self.module.get_formal_quality_links()
        self.assertEqual(result["permissions"], {"view": True, "link": True})
        for permissions in (
            {"view": True},
            {"view": True, "link": "yes"},
            {"view": True, "link": True, "approve": True},
        ):
            with self.subTest(permissions=permissions):
                self.repository.list_quality_links = lambda *_args, **_kwargs: {
                    "projectGlobalId": PROJECT,
                    "permissions": permissions,
                    "items": [],
                }
                with self.assertRaisesRegex(RuntimeError, "permissions"):
                    self.module.get_formal_quality_links()
        self.assertNotIn("commit", self.events)


if __name__ == "__main__":
    unittest.main()
