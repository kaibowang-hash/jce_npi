from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal


PROFILE_ID = "00000000-0000-4000-8000-000000000081"
POLICY_ID = "00000000-0000-4000-8000-000000000082"
SOURCE_ID = "00000000-0000-4000-8000-000000000083"
ARCHIVE_ID = "00000000-0000-4000-8000-000000000084"
EXPORT_ID = "00000000-0000-4000-8000-000000000085"
REQUEST_ID = "00000000-0000-4000-8000-000000000086"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class Repository:
    def __init__(self) -> None:
        self.calls = []

    def workspace(self):
        self.calls.append(("workspace", {}))
        return {"kind": "workspace"}

    def _outcome(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return types.SimpleNamespace(response={"kind": name}, replayed=False)

    def publish_profile(self, **kwargs):
        return self._outcome("profile", **kwargs)

    def create_export(self, **kwargs):
        return self._outcome("export", **kwargs)

    def publish_policy(self, **kwargs):
        return self._outcome("policy", **kwargs)

    def create_archive(self, **kwargs):
        return self._outcome("archive", **kwargs)


class Phase9DataExchangeApiTest(unittest.TestCase):
    MODULES = ("frappe", "npi_core.api", "npi_core.data_exchange_api", "npi_core.bff")

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p9-06-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-" + "a" * 32,
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = AttrDict(npi_route_params={"export_id": EXPORT_ID})
        frappe.conf = AttrDict(npi_p9_06_routes_disabled=False)
        frappe.local = types.SimpleNamespace(
            form_dict=AttrDict(), response=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
        )
        frappe.request = frappe.local.request
        frappe.get_request_header = lambda name: self.headers.get(name)
        frappe.whitelist = lambda *, methods, allow_guest=False: (lambda function: function)
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.api = importlib.import_module("npi_core.data_exchange_api")
        self.repository = Repository()
        principal = Principal("manager@example.invalid", frozenset({"System Manager"}), tenant_id="tenant-a")
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

    def call(self, function, payload=None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_fixed_queries_and_commands_forward_typed_exact_values(self) -> None:
        self.assertEqual(self.call(self.api.get_data_exchange_workspace), {"kind": "workspace"})
        self.assertEqual(self.call(self.api.publish_data_exchange_profile, {
            "globalId": PROFILE_ID, "version": 1, "datasetId": "project_portfolio.v1",
            "columns": ["projectCode", "title"], "language": "en", "redactionProfile": "minimum_disclosure.v1",
            "query": {}, "maxRows": 100, "maxBytes": 100000,
        })["kind"], "profile")
        self.assertEqual(self.call(self.api.create_data_exchange_export, {
            "profileId": PROFILE_ID, "profileVersion": 1, "profileHash": "a" * 64,
        })["kind"], "export")
        years = {key: 7 for key in ("project", "quality", "change", "file", "data_exchange_export", "controlled_print")}
        self.assertEqual(self.call(self.api.publish_retention_policy, {
            "globalId": POLICY_ID, "version": 1, "scope": "tenant", "scopeReference": None,
            "effectiveFrom": "2026-01-01", "effectiveUntil": None, "retentionYears": years,
        })["kind"], "policy")
        self.assertEqual(self.call(self.api.create_retention_archive, {
            "globalId": ARCHIVE_ID, "sourceKind": "file_revision", "sourceId": SOURCE_ID,
            "sourceVersion": 2, "sourceHash": "b" * 64, "policyId": POLICY_ID,
            "policyVersion": 1, "policyHash": "c" * 64, "scope": "tenant", "scopeReference": None,
        })["kind"], "archive")
        self.assertEqual([name for name, _payload in self.repository.calls], ["workspace", "profile", "export", "policy", "archive"])

    def test_default_disabled_external_and_unknown_inputs_fail_closed(self) -> None:
        self.frappe.conf.npi_p9_06_routes_disabled = True
        with self.assertRaises(self.api.DataExchangeRoutesDisabled):
            self.call(self.api.get_data_exchange_workspace)
        self.frappe.conf.npi_p9_06_routes_disabled = False
        self.api.authenticated_principal = lambda _actor: Principal("outside@example.invalid", frozenset({"System Manager"}), is_external=True, tenant_id="tenant-a")
        with self.assertRaises(PermissionDenied):
            self.call(self.api.get_data_exchange_workspace)
        self.api.authenticated_principal = lambda _actor: Principal("manager@example.invalid", frozenset({"System Manager"}), tenant_id="tenant-a")
        with self.assertRaises(RequestValidationFailed):
            self.call(self.api.create_data_exchange_export, {"profileId": PROFILE_ID, "profileVersion": 1, "profileHash": "bad", "doctype": "User"})

    def test_bff_maps_only_exact_data_exchange_routes(self) -> None:
        bff = importlib.import_module("npi_core.bff")
        self.frappe.local.request.path = f"/api/npi/v1/administration/data-exchange/exports/{EXPORT_ID}:content"
        self.frappe.local.request.method = "POST"
        bff.route_request()
        self.assertEqual(self.frappe.local.form_dict.cmd, "npi_core.data_exchange_api.download_data_exchange_export")
        self.assertEqual(self.frappe.flags.npi_route_params, {"export_id": EXPORT_ID})


if __name__ == "__main__":
    unittest.main()
