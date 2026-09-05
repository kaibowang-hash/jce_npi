from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]


class ERPNextConnectionStatusTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.erp_connection_status_api",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.now = datetime(2026, 9, 5, 17, 10, tzinfo=UTC)
        self.applied_at = self.now - timedelta(minutes=5)
        self.master_heads: list[dict[str, object]] = []
        self.counts = {
            "NPI Project Source Binding": 0,
            "NPI ERP Projection Head": 0,
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.conf = self.configuration()
        frappe.session = types.SimpleNamespace(user="member@example.invalid")
        frappe.flags = types.SimpleNamespace(npi_bff_request=False)
        frappe.local = types.SimpleNamespace(
            form_dict={},
            response=types.SimpleNamespace(http_status_code=200),
        )
        frappe.get_request_header = lambda _name: None
        frappe.get_all = self.get_all
        frappe.get_roles = lambda _user: []
        frappe.logger = lambda _name: types.SimpleNamespace(error=lambda *_args: None)
        frappe.log_error = lambda **_values: None
        frappe.db = types.SimpleNamespace(count=self.count, rollback=lambda: None)

        def whitelist(*, allow_guest=False, methods=None):
            def decorate(function):
                function.allow_guest = allow_guest
                function.allowed_methods = tuple(methods or ())
                return function

            return decorate

        frappe.whitelist = whitelist
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.module = importlib.import_module(
            "npi_integration.erp_connection_status_api"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def configuration() -> dict[str, object]:
        return {
            "npi_item_publish_sandbox_enabled": True,
            "npi_item_publish_sandbox_profiles": [
                {
                    "profileId": "erpnext-test-item-v1",
                    "profileVersion": 1,
                    "tenantId": "TENANT-SANDBOX",
                    "projectGlobalId": "00000000-0000-4000-8000-000000002001",
                    "environmentCode": "test",
                    "requesterUserIds": ["publisher@example.invalid"],
                    "serviceActorUserId": "worker@example.invalid",
                    "baseUrl": "https://erpnext.test.example.invalid",
                    "allowedHostnames": ["erpnext.test.example.invalid"],
                    "secretReference": "secrets/erpnext-test-item-v1",
                    "connectTimeoutSeconds": 3,
                    "readTimeoutSeconds": 10,
                }
            ],
        }

    def get_all(self, doctype: str, **_kwargs: object) -> list[dict[str, object]]:
        if doctype == "NPI Authorization Projection":
            return [{"applied_at": self.applied_at.replace(tzinfo=None)}]
        if doctype == "NPI ERP Master Catalog Head":
            return self.master_heads
        raise AssertionError(f"unexpected DocType {doctype}")

    def count(self, doctype: str, filters=None) -> int:
        if doctype == "NPI ERP Projection Head":
            self.assertEqual(filters, {"availability": "available"})
        if doctype == "NPI Project Source Binding":
            self.assertEqual(
                filters,
                {"source_object_type": "Project", "stream_state": "bound"},
            )
        return self.counts[doctype]

    def test_reports_recent_bidirectional_test_evidence_without_claiming_features(self) -> None:
        result = self.module._status(now=self.now)
        self.assertEqual(result["connectionState"], "connected")
        self.assertEqual(result["targetEnvironment"], "test")
        self.assertEqual(result["lastConfirmedAt"], "2026-09-05T17:05:00Z")
        self.assertEqual(
            result["capabilities"],
            {
                "authorizationSynchronization": True,
                "itemCommands": True,
                "projectSynchronization": False,
                "masterDataSynchronization": False,
                "reportingSynchronization": False,
            },
        )

    def test_status_changes_only_when_persisted_capability_truth_changes(self) -> None:
        self.counts["NPI Project Source Binding"] = 1
        self.counts["NPI ERP Projection Head"] = 2
        result = self.module._status(now=self.now)
        self.assertTrue(result["capabilities"]["projectSynchronization"])
        self.assertTrue(result["capabilities"]["reportingSynchronization"])

        self.applied_at = self.now - timedelta(hours=3)
        stale = self.module._status(now=self.now)
        self.assertEqual(stale["connectionState"], "partially_connected")
        self.assertFalse(stale["capabilities"]["authorizationSynchronization"])

    def test_master_data_requires_all_four_fresh_catalogs(self) -> None:
        self.master_heads = [
            {
                "catalog_kind": kind,
                "source_environment": "test",
                "last_synchronized_at": self.now - timedelta(minutes=10),
            }
            for kind in ("customer", "supplier", "item_group", "item")
        ]
        result = self.module._status(now=self.now)
        self.assertTrue(result["capabilities"]["masterDataSynchronization"])
        self.assertTrue(result["capabilities"]["reportingSynchronization"])

        self.master_heads.pop()
        partial = self.module._status(now=self.now)
        self.assertFalse(partial["capabilities"]["masterDataSynchronization"])

    def test_invalid_or_ambiguous_configuration_returns_safe_unavailable(self) -> None:
        self.frappe.conf["npi_item_publish_sandbox_profiles"].append(
            {
                **self.frappe.conf["npi_item_publish_sandbox_profiles"][0],
                "profileId": "other-test-profile",
                "environmentCode": "sandbox",
            }
        )
        result = self.module._safe_status(clock=lambda: self.now)
        self.assertEqual(result["connectionState"], "unavailable")
        self.assertIsNone(result["targetEnvironment"])
        self.assertFalse(any(result["capabilities"].values()))


if __name__ == "__main__":
    unittest.main()
