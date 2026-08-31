from __future__ import annotations

import copy
import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


sys.path.insert(0, "apps/npi_core")

from npi_core.change_control.request_validation import parse_revision_content
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from tests.test_phase9_change_control_domain import revision


PROJECT_ID = "00000000-0000-0000-0000-000000000003"
CHANGE_ID = "00000000-0000-0000-0000-000000000002"
REQUEST_ID = "00000000-0000-0000-0000-000000000004"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def command_response(operation: str) -> dict[str, object]:
    value = revision()
    current = {**value.revision_payload(), "snapshotHash": value.snapshot_hash}
    change = {
        "globalId": str(value.change_global_id),
        "projectGlobalId": str(value.project_global_id),
        "title": value.title,
        "state": value.state.value,
        "optimisticVersion": value.revision,
        "currentRevisionGlobalId": str(value.global_id),
        "currentRevisionNumber": value.revision,
        "currentRevisionSnapshotHash": value.snapshot_hash,
        "formalChange": value.formal_change.payload(),
        "readyToClose": value.ready_to_close,
    }
    return {"operation": operation, "change": change, "currentRevision": current}


def content_payload() -> dict[str, object]:
    value = revision().revision_payload()
    return {
        "title": value["title"],
        "reason": value["reason"],
        "impactAssessments": value["impactAssessments"],
        "affectedObjects": value["affectedObjects"],
        "implementationTasks": value["implementationTasks"],
        "effectivityRules": value["effectivityRules"],
        "dispositions": value["dispositions"],
        "revalidationRequirements": value["revalidationRequirements"],
        "costSummary": value["costSummary"],
        "closureEvidence": value["closureEvidence"],
    }


class MockRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.replayed = False

    def _command(self, name: str, operation: str, *args: object, **kwargs: object):
        self.calls.append((name, args, kwargs))
        return types.SimpleNamespace(response=command_response(operation), replayed=self.replayed)

    def create_change(self, *args: object, **kwargs: object):
        return self._command("create_change", "engineering_change.create", *args, **kwargs)

    def revise_change(self, *args: object, **kwargs: object):
        return self._command("revise_change", "engineering_change.revise", *args, **kwargs)

    def link_formal_observation(self, *args: object, **kwargs: object):
        return self._command("link_formal_observation", "engineering_change.link_formal_observation", *args, **kwargs)

    def close_change(self, *args: object, **kwargs: object):
        return self._command("close_change", "engineering_change.close", *args, **kwargs)

    def list_changes(self, *_args: object, **_kwargs: object):
        return {"projectGlobalId": PROJECT_ID, "items": [], "permissions": {"canView": True, "canCreate": True, "canRevise": True, "canLinkFormalObservation": True, "canClose": True}}

    def get_change(self, *_args: object, **_kwargs: object):
        return None


class Phase9ChangeControlApiTest(unittest.TestCase):
    MODULES = ("frappe", "npi_core.api", "npi_core.change_control_api", "npi_core.bff")

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p9-change-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-" + "a" * 32,
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = AttrDict(npi_route_params={"project_id": PROJECT_ID, "change_id": CHANGE_ID})
        frappe.conf = AttrDict(npi_p9_01_routes_disabled=False)
        frappe.local = types.SimpleNamespace(form_dict=AttrDict(), response=AttrDict(), request=types.SimpleNamespace(path="/", method="GET"))
        frappe.request = frappe.local.request
        frappe.get_request_header = lambda name: self.headers.get(name)
        frappe.whitelist = lambda *, methods, allow_guest=False: (lambda function: function)
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.api = importlib.import_module("npi_core.change_control_api")
        self.repository = MockRepository()
        principal = Principal(
            "owner@example.invalid",
            frozenset({"NPI API User", "System Manager"}),
            tenant_id="tenant-a",
        )
        self.api._repository_factory = lambda **_values: self.repository
        self.api.authenticated_user = lambda: principal.user_id
        self.api.authenticated_principal = lambda _actor: principal
        self.api.require_csrf_token = lambda: None
        self.api.frappe_domain_call = lambda handle, **_values: handle()
        from npi_core.foundation.tracing import current_trace_id

        self.trace_token = current_trace_id.set(self.headers["X-Trace-ID"])

    def tearDown(self) -> None:
        from npi_core.foundation.tracing import current_trace_id

        current_trace_id.reset(self.trace_token)
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_request_parser_builds_exact_typed_content_and_rejects_server_truth(self) -> None:
        parsed = parse_revision_content(content_payload())
        self.assertEqual(len(parsed["impact_assessments"]), 12)
        self.assertEqual(parsed["cost_summary"].currency, "CNY")
        malformed = {**content_payload(), "formalChange": revision().formal_change.payload()}
        with self.assertRaises(RequestValidationFailed):
            parse_revision_content(malformed)

    def test_create_revise_link_and_close_forward_only_closed_typed_values(self) -> None:
        create = self.call(self.api.create_engineering_change, {"content": content_payload()})
        self.assertEqual(create["operation"], "engineering_change.create")
        predecessor = {
            "expectedRevision": 1,
            "expectedRevisionGlobalId": str(revision().global_id),
            "expectedRevisionSnapshotHash": revision().snapshot_hash,
        }
        revise = self.call(self.api.revise_engineering_change, {"predecessor": predecessor, "content": content_payload()})
        self.assertEqual(revise["operation"], "engineering_change.revise")
        link = self.call(
            self.api.link_engineering_change_formal_observation,
            {"predecessor": predecessor, "formalChange": revision().formal_change.payload()},
        )
        self.assertEqual(link["operation"], "engineering_change.link_formal_observation")
        close = self.call(self.api.close_engineering_change, {"predecessor": predecessor})
        self.assertEqual(close["operation"], "engineering_change.close")
        self.assertEqual([call[0] for call in self.repository.calls], ["create_change", "revise_change", "link_formal_observation", "close_change"])
        self.assertTrue(all("idempotency_key_hash" in call[2] for call in self.repository.calls))

    def test_queries_and_commands_require_internal_npi_api_authority(self) -> None:
        self.api.authenticated_principal = lambda _actor: Principal(
            "outside@example.invalid",
            frozenset({"NPI API User", "System Manager"}),
            is_external=True,
            tenant_id="tenant-a",
        )
        with self.assertRaises(PermissionDenied):
            self.call(self.api.get_engineering_changes)
        with self.assertRaises(PermissionDenied):
            self.call(self.api.create_engineering_change, {"content": content_payload()})

    def test_formal_observation_command_requires_system_manager(self) -> None:
        self.api.authenticated_principal = lambda _actor: Principal(
            "member@example.invalid",
            frozenset({"NPI API User"}),
            tenant_id="tenant-a",
        )
        predecessor = {"expectedRevision": 1, "expectedRevisionGlobalId": str(revision().global_id), "expectedRevisionSnapshotHash": revision().snapshot_hash}
        with self.assertRaises(PermissionDenied):
            self.call(self.api.link_engineering_change_formal_observation, {"predecessor": predecessor, "formalChange": revision().formal_change.payload()})

    def test_default_disabled_route_fails_closed(self) -> None:
        self.frappe.conf.npi_p9_01_routes_disabled = True
        with self.assertRaises(self.api.ChangeControlRoutesDisabled):
            self.call(self.api.get_engineering_changes)

    def test_revise_server_diagnostic_requires_exact_runtime_request_shape(self) -> None:
        trace = "trace-" + "b" * 32
        diagnostic_path = "/tmp/p9-01-engineering-change-runtime-diagnostic.json"
        self.headers.update(
            {
                self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER: (
                    self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_SCOPE
                ),
                self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_TRACE_HEADER: trace,
            }
        )
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = AttrDict()
        self.frappe.local.form_dict = AttrDict(
            {
                "predecessor": {},
                "content": {},
                "cmd": "npi_core.change_control_api.revise_engineering_change",
            }
        )
        with patch.dict(
            os.environ,
            {
                "NPI_P9_01C_RUNTIME_ENABLED": "1",
                "NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": diagnostic_path,
            },
            clear=False,
        ), patch.object(
            self.api,
            "ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTICS_ENABLED",
            True,
        ):
            self.assertTrue(
                self.api._engineering_change_revise_server_diagnostic_active(
                    "engineering_change.revise",
                    trace,
                )
            )
            for mutation in (
                lambda: self.headers.pop(
                    self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER
                ),
                lambda: setattr(self.frappe.local.request, "method", "GET"),
                lambda: self.frappe.local.form_dict.__setitem__("unexpected", True),
            ):
                saved_headers = dict(self.headers)
                saved_method = self.frappe.local.request.method
                saved_form = AttrDict(self.frappe.local.form_dict)
                mutation()
                self.assertFalse(
                    self.api._engineering_change_revise_server_diagnostic_active(
                        "engineering_change.revise",
                        trace,
                    )
                )
                self.headers.clear()
                self.headers.update(saved_headers)
                self.frappe.local.request.method = saved_method
                self.frappe.local.form_dict = saved_form
            self.assertFalse(
                self.api._engineering_change_revise_server_diagnostic_active(
                    "engineering_change.create",
                    trace,
                )
            )

    def test_revise_server_diagnostic_is_dormant_without_runtime_environment(self) -> None:
        self.assertFalse(
            self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.api.ENGINEERING_CHANGE_POST_ROOT_SAVE_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.api.ENGINEERING_CHANGE_POST_OPTIONAL_EMPTY_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.api.ENGINEERING_CHANGE_INBOUND_FULL_DIAGNOSTICS_ENABLED
        )
        self.assertFalse(
            self.api.ENGINEERING_CHANGE_POST_RAW_BODY_DIAGNOSTICS_ENABLED
        )
        trace = "trace-" + "c" * 32
        self.headers.update(
            {
                self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_HEADER: (
                    self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_SCOPE
                ),
                self.api.ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_TRACE_HEADER: trace,
            }
        )
        self.frappe.local.request.method = "POST"
        self.frappe.local.request.args = AttrDict()
        self.frappe.local.form_dict = AttrDict(
            {
                "predecessor": {},
                "content": {},
                "cmd": "npi_core.change_control_api.revise_engineering_change",
            }
        )
        with patch.dict(
            os.environ,
            {
                "NPI_P9_01C_RUNTIME_ENABLED": "0",
                "NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH": (
                    "/tmp/p9-01-engineering-change-runtime-diagnostic.json"
                ),
            },
            clear=False,
        ):
            self.assertFalse(
                self.api._engineering_change_revise_server_diagnostic_active(
                    "engineering_change.revise",
                    trace,
                )
            )

    def test_bff_source_freezes_exact_routes_and_default_disabled_handler(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        for handler in (
            "get_engineering_changes", "get_engineering_change", "create_engineering_change",
            "revise_engineering_change", "link_engineering_change_formal_observation",
            "close_engineering_change",
        ):
            self.assertIn(f"npi_core.change_control_api.{handler}", source)
        self.assertIn("npi_core.change_control_api.engineering_change_routes_disabled", source)
        self.assertIn('configuration.get("npi_p9_01_routes_disabled")', source)


if __name__ == "__main__":
    unittest.main()
