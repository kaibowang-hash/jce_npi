from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.master_data.domain import canonical_hash


REQUEST_ID = str(UUID(int=995))


def payload() -> dict[str, object]:
    records = [
        {
            "sourceKey": "ITEM-001",
            "displayName": "Item 001",
            "enabled": True,
            "groupKey": "Products",
            "stockUom": "Nos",
            "isStockItem": True,
            "sourceModifiedAt": "2026-09-06T02:00:00Z",
        }
    ]
    snapshot = {
        "catalogKind": "item",
        "sourceEnvironment": "test",
        "sourceVersion": 2,
        "sourceModifiedAt": "2026-09-06T02:00:00Z",
        "records": records,
    }
    return {
        "schemaVersion": 1,
        "operation": "replace_master_catalog",
        "sourceSystem": "ERPNEXT",
        "targetSystem": "NPI_ONE",
        "eventId": str(UUID(int=996)),
        **snapshot,
        "issuedAt": "2026-09-06T02:01:00Z",
        "traceId": "trace-master-api-996",
        "payloadHash": canonical_hash(snapshot),
    }


class ERPNextMasterDataApiTest(unittest.TestCase):
    MODULES = ("frappe", "npi_integration.master_data_api")

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.rollbacks = 0
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace(npi_bff_request=False)
        frappe.local = types.SimpleNamespace(
            response=types.SimpleNamespace(http_status_code=200),
            form_dict={},
        )
        frappe.conf = {
            "npi_erp_master_data_routes_disabled": False,
            "npi_tenant_id": "tenant-master-api",
        }
        frappe.session = types.SimpleNamespace(user="service@example.invalid")
        frappe.get_request_header = lambda name: (
            REQUEST_ID if name == "X-Request-ID" else None
        )
        frappe.get_hooks = lambda _name: []
        frappe.get_attr = lambda _path: None
        frappe.get_roles = lambda _actor: ["NPI API User"]
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.db = types.SimpleNamespace(rollback=self.rollback)
        frappe.logger = lambda _name: types.SimpleNamespace(error=lambda *_args: None)
        frappe.log_error = lambda **_values: None

        def whitelist(*, allow_guest=False, methods=None):
            def decorate(function):
                function.allow_guest = allow_guest
                function.allowed_methods = tuple(methods or ())
                return function

            return decorate

        frappe.whitelist = whitelist
        self.frappe = frappe
        sys.modules["frappe"] = frappe
        self.module = importlib.import_module("npi_integration.master_data_api")
        self.module.authenticated_user = lambda: frappe.session.user
        self.module.authenticated_principal = lambda: types.SimpleNamespace(
            is_external=False,
            tenant_id="tenant-master-api",
            roles=frozenset({"NPI Engineer"}),
            organization_scopes={
                "Customer": frozenset({"CUSTOMER-001"}),
                "Supplier": frozenset({"SUPPLIER-001"}),
            },
        )
        self.module.configured_tenant_id = lambda: "tenant-master-api"
        self.module.response_request_id = lambda: REQUEST_ID
        self.module.require_service_actor = lambda actor: self.assertEqual(
            actor, frappe.session.user
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def rollback(self) -> None:
        self.rollbacks += 1

    def test_route_is_default_disabled_before_authentication(self) -> None:
        self.frappe.conf.clear()
        self.module.authenticated_user = lambda: self.fail(
            "Disabled route must stop before authentication."
        )
        result = self.module.replace_master_catalog(**payload())
        self.assertEqual(result["code"], "ERP_MASTER_DATA_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)
        self.assertEqual(self.rollbacks, 1)

    def test_replace_retries_one_unique_race_and_returns_bound_receipt(self) -> None:
        calls = 0

        def apply_snapshot(event, **values):
            nonlocal calls
            calls += 1
            self.assertEqual(values["actor"], self.frappe.session.user)
            if calls == 1:
                raise self.frappe.DuplicateEntryError()
            return types.SimpleNamespace(
                snapshot_id=UUID(int=997),
                source_version=event.source_version,
                record_count=len(event.records),
                payload_hash=event.payload_hash,
                exact_replay=True,
            )

        self.module.apply_snapshot = apply_snapshot
        result = self.module.replace_master_catalog(**payload())
        self.assertEqual(calls, 2)
        self.assertEqual(self.rollbacks, 1)
        self.assertEqual(result["snapshotId"], str(UUID(int=997)))
        self.assertEqual(result["catalogKind"], "item")
        self.assertEqual(result["recordCount"], 1)
        self.assertTrue(result["exactReplay"])
        self.assertEqual(result["requestId"], REQUEST_ID)

    def test_query_is_authenticated_bounded_and_operation_specific(self) -> None:
        calls: list[dict[str, object]] = []

        def catalog_collection(**values):
            calls.append(values)
            return {
                "schemaVersion": 1,
                "catalogKind": "item",
                "sourceVersion": 2,
                "sourceModifiedAt": "2026-09-06T02:00:00Z",
                "lastSynchronizedAt": "2026-09-06T02:01:00Z",
                "total": 1,
                "offset": 0,
                "limit": 20,
                "items": [],
            }

        self.module.catalog_collection = catalog_collection
        result = self.module.get_master_catalog(
            kind="item", query="ITEM", limit="20", offset="0"
        )
        self.assertEqual(result["sourceVersion"], 2)
        self.assertEqual(calls[0]["tenant_id"], "tenant-master-api")
        self.assertEqual(calls[0]["kind"].value, "item")
        self.assertEqual(calls[0]["query"], "ITEM")
        self.assertEqual(calls[0]["limit"], 20)
        self.assertIsNone(calls[0]["allowed_source_keys"])

        self.module.get_master_catalog(kind="customer")
        self.assertEqual(
            calls[1]["allowed_source_keys"], frozenset({"CUSTOMER-001"})
        )

    def test_unknown_or_invalid_snapshot_is_rejected(self) -> None:
        for changes in ({"unexpected": True}, {"payloadHash": "0" * 64}):
            with self.subTest(changes=changes):
                result = self.module.replace_master_catalog(
                    **{**payload(), **changes}
                )
                self.assertEqual(result["code"], "VALIDATION_FAILED")
                self.assertEqual(self.frappe.local.response.http_status_code, 422)


if __name__ == "__main__":
    unittest.main()
