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


PREVIEW_ID = "00000000-0000-4000-8000-000000000001"
JOB_ID = "00000000-0000-4000-8000-000000000002"
FILE_ID = "00000000-0000-4000-8000-000000000003"
REQUEST_ID = "00000000-0000-4000-8000-000000000004"


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
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _outcome(self, name: str, response: dict[str, object], *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return types.SimpleNamespace(response=response, replayed=False)

    def workspace(self):
        self.calls.append(("workspace", (), {}))
        return {"kind": "workspace"}

    def create_preview(self, **kwargs):
        return self._outcome("create_preview", {"globalId": PREVIEW_ID}, **kwargs)

    def queue_execution(self, **kwargs):
        return self._outcome("queue_execution", {"globalId": JOB_ID}, **kwargs)

    def job(self, job_id):
        self.calls.append(("job", (job_id,), {}))
        return {"globalId": JOB_ID, "optimisticVersion": 2, "snapshotHash": "b" * 64}

    def create_correction(self, job_id, **kwargs):
        return self._outcome("create_correction", {"jobGlobalId": JOB_ID}, job_id, **kwargs)

    def reconcile(self, job_id, **kwargs):
        return self._outcome("reconcile", {"globalId": JOB_ID}, job_id, **kwargs)

    def rollback(self, job_id, **kwargs):
        return self._outcome("rollback", {"globalId": JOB_ID}, job_id, **kwargs)


class Phase9HistoricalMigrationApiTest(unittest.TestCase):
    MODULES = ("frappe", "npi_core.api", "npi_core.historical_migration_api", "npi_core.bff")

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p9-05-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-" + "a" * 32,
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = AttrDict(npi_route_params={"preview_id": PREVIEW_ID, "job_id": JOB_ID})
        frappe.conf = AttrDict(npi_p9_05_routes_disabled=False, npi_p9_05_non_production_rehearsal=True)
        frappe.local = types.SimpleNamespace(
            form_dict=AttrDict(), response=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
        )
        frappe.request = frappe.local.request
        frappe.get_request_header = lambda name: self.headers.get(name)
        frappe.whitelist = lambda *, methods, allow_guest=False: (lambda function: function)
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.api = importlib.import_module("npi_core.historical_migration_api")
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

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    def test_query_preview_execution_and_job_commands_forward_only_exact_values(self) -> None:
        self.assertEqual(self.call(self.api.get_historical_migration_workspace), {"kind": "workspace"})
        created = self.call(self.api.create_historical_migration_preview, {
            "tenantId": "tenant-a", "fileRevisionGlobalId": FILE_ID,
            "fileOptimisticVersion": 3, "sha256": "a" * 64,
        })
        self.assertEqual(created["globalId"], PREVIEW_ID)
        queued = self.call(self.api.execute_historical_migration_preview, {
            "expectedVersion": 1, "expectedSnapshotHash": "b" * 64,
        })
        self.assertEqual(queued["globalId"], JOB_ID)
        self.assertEqual(self.call(self.api.get_historical_migration_job)["globalId"], JOB_ID)
        self.assertEqual(self.call(self.api.create_historical_migration_correction)["jobGlobalId"], JOB_ID)
        version = {"expectedVersion": 2, "expectedSnapshotHash": "b" * 64}
        self.assertEqual(self.call(self.api.reconcile_historical_migration_job, version)["globalId"], JOB_ID)
        self.assertEqual(self.call(self.api.rollback_historical_migration_job, version)["globalId"], JOB_ID)
        self.assertEqual(
            [call[0] for call in self.repository.calls],
            ["workspace", "create_preview", "queue_execution", "job", "create_correction", "reconcile", "rollback"],
        )

    def test_external_or_non_manager_and_default_disabled_route_fail_closed(self) -> None:
        self.api.authenticated_principal = lambda _actor: Principal(
            "outside@example.invalid", frozenset({"System Manager"}), is_external=True, tenant_id="tenant-a"
        )
        with self.assertRaises(PermissionDenied):
            self.call(self.api.get_historical_migration_workspace)
        self.api.authenticated_principal = lambda _actor: Principal(
            "member@example.invalid", frozenset({"NPI API User"}), tenant_id="tenant-a"
        )
        with self.assertRaises(PermissionDenied):
            self.call(self.api.get_historical_migration_workspace)
        self.frappe.conf.npi_p9_05_routes_disabled = True
        with self.assertRaises(self.api.HistoricalMigrationRoutesDisabled):
            self.call(self.api.get_historical_migration_workspace)

    def test_unknown_fields_invalid_hashes_and_stale_versions_are_rejected(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            self.call(self.api.create_historical_migration_preview, {
                "tenantId": "tenant-a", "fileRevisionGlobalId": FILE_ID,
                "fileOptimisticVersion": 3, "sha256": "not-a-hash", "doctype": "User",
            })
        with self.assertRaises(RequestValidationFailed):
            self.call(self.api.reconcile_historical_migration_job, {
                "expectedVersion": 0, "expectedSnapshotHash": "b" * 64,
            })

    def test_bff_routes_only_the_exact_fixed_surface(self) -> None:
        self.frappe.local.request.path = f"/api/npi/v1/administration/historical-migration-rehearsals/{PREVIEW_ID}:execute"
        self.frappe.local.request.method = "POST"
        bff = importlib.import_module("npi_core.bff")
        bff.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.historical_migration_api.execute_historical_migration_preview",
        )
        self.assertEqual(self.frappe.flags.npi_route_params, {"preview_id": PREVIEW_ID})


if __name__ == "__main__":
    unittest.main()
