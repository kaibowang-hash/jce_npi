from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector"
if str(ERP_APP) not in sys.path:
    sys.path.insert(0, str(ERP_APP))


class ERPNextMasterDataWorkerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_erpnext_connector.master_data_repository",
        "npi_erpnext_connector.master_data_worker",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.conf = {}
        frappe.enqueue = self.enqueue
        frappe.whitelist = lambda **_kwargs: lambda function: function
        sys.modules["frappe"] = frappe
        self.module = importlib.import_module(
            "npi_erpnext_connector.master_data_worker"
        )
        self.enqueued: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.saved_states: list[dict[str, object]] = []
        self.document = types.SimpleNamespace(
            name=str(UUID(int=991)),
            status="pending",
            attempt_count=0,
            next_attempt_at=None,
            last_attempt_at=None,
            delivered_at=None,
            last_error_code=None,
            target_snapshot_id=None,
            response_payload_hash=None,
        )
        self.module.master_data_sender_is_disabled = lambda _conf: False
        self.module.load_master_data_profile = lambda _conf: object()
        self.module.get_delivery = lambda _delivery_id: self.document
        self.module.restore_delivery_event = lambda _document: object()
        self.module.save_delivery = self.save

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved_modules[name] is not None:
                sys.modules[name] = self.saved_modules[name]

    def enqueue(self, *args: object, **kwargs: object) -> None:
        self.enqueued.append((args, kwargs))

    def save(self, document: object) -> None:
        self.saved_states.append(dict(vars(document)))

    def test_delivery_success_persists_the_bound_receipt(self) -> None:
        self.module.deliver_master_snapshot = lambda _profile, _event: (
            types.SimpleNamespace(
                snapshot_id=str(UUID(int=992)),
                payload_hash="a" * 64,
                exact_replay=False,
            )
        )

        self.module.deliver_master_data(str(UUID(int=991)))

        self.assertEqual(self.document.status, "delivered")
        self.assertEqual(self.document.attempt_count, 1)
        self.assertEqual(self.document.target_snapshot_id, str(UUID(int=992)))
        self.assertEqual(self.document.response_payload_hash, "a" * 64)
        self.assertIsNotNone(self.document.delivered_at)

    def test_retryable_failure_uses_bounded_backoff_and_final_limit(self) -> None:
        from npi_erpnext_connector.master_data_transport import (
            RetryableMasterDataDeliveryError,
        )

        def fail(_profile, _event):
            raise RetryableMasterDataDeliveryError("NETWORK_OR_TIMEOUT")

        self.module.deliver_master_snapshot = fail
        self.module.deliver_master_data(str(UUID(int=991)))
        self.assertEqual(self.document.status, "retry")
        self.assertEqual(self.document.attempt_count, 1)
        self.assertEqual(self.document.last_error_code, "NETWORK_OR_TIMEOUT")
        self.assertIsNotNone(self.document.next_attempt_at)

        self.document.status = "retry"
        self.document.next_attempt_at = None
        self.document.attempt_count = self.module.MAX_ATTEMPTS - 1
        self.module.deliver_master_data(str(UUID(int=991)))
        self.assertEqual(self.document.status, "permanent_failure")
        self.assertEqual(self.document.attempt_count, self.module.MAX_ATTEMPTS)
        self.assertIsNone(self.document.next_attempt_at)

    def test_reconciliation_queues_each_closed_catalog_kind(self) -> None:
        self.module.reconcile_master_catalogs()
        self.assertEqual(len(self.enqueued), 4)
        self.assertEqual(
            {call[1]["catalog_kind"] for call in self.enqueued},
            {"customer", "supplier", "item_group", "item"},
        )
        self.assertTrue(
            all(call[1]["enqueue_after_commit"] for call in self.enqueued)
        )

    def test_display_names_normalize_erp_edge_spaces_without_changing_keys(self) -> None:
        repository = sys.modules["npi_erpnext_connector.master_data_repository"]
        record = repository._record(
            repository.MasterCatalogKind.CUSTOMER,
            {
                "name": "CUSTOMER-001",
                "customer_name": " Customer\nname ",
                "disabled": 0,
                "customer_group": "Primary",
                "modified": datetime(2026, 9, 6, 2, 0),
            },
        )
        self.assertEqual(record["sourceKey"], "CUSTOMER-001")
        self.assertEqual(record["displayName"], "Customer name")


if __name__ == "__main__":
    unittest.main()
