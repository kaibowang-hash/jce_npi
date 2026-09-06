from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
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
        self.assertEqual(len(self.enqueued), 5)
        self.assertEqual(
            {call[1]["catalog_kind"] for call in self.enqueued},
            {"customer", "supplier", "item_group", "item", "machine"},
        )
        self.assertTrue(
            all(call[1]["enqueue_after_commit"] for call in self.enqueued)
        )

    def test_unchanged_catalog_is_refreshed_before_status_evidence_expires(self) -> None:
        repository = sys.modules["npi_erpnext_connector.master_data_repository"]
        now = datetime(2026, 9, 6, 2, 0, tzinfo=UTC)

        self.assertTrue(
            repository._delivered_snapshot_is_fresh(
                now - timedelta(minutes=59), now=now
            )
        )
        self.assertFalse(
            repository._delivered_snapshot_is_fresh(
                now - timedelta(minutes=61), now=now
            )
        )
        self.assertFalse(repository._delivered_snapshot_is_fresh(None, now=now))
        with self.assertRaises(repository.MasterDataSenderError):
            repository._delivered_snapshot_is_fresh(
                now + timedelta(minutes=6), now=now
            )

    def test_unchanged_stale_catalog_creates_the_next_heartbeat_delivery(self) -> None:
        repository = sys.modules["npi_erpnext_connector.master_data_repository"]
        now = datetime.now(UTC)
        latest = {
            "name": str(UUID(int=993)),
            "source_version": 4,
            "source_snapshot_hash": "a" * 64,
            "status": "delivered",
            "delivered_at": now,
        }
        repository.master_data_sender_is_disabled = lambda _conf: False
        repository.load_master_data_profile = lambda _conf: types.SimpleNamespace(
            environment_code="test"
        )
        repository.load_source_snapshot = lambda _kind: types.SimpleNamespace(
            snapshot_hash="a" * 64
        )
        repository._latest_delivery = lambda _kind: latest
        builds: list[dict[str, object]] = []

        def build_event(_snapshot: object, **values: object) -> object:
            builds.append(values)
            return types.SimpleNamespace(event_id=UUID(int=994))

        repository.build_event = build_event
        repository._insert_delivery = lambda _event: types.SimpleNamespace(
            name=str(UUID(int=994))
        )
        enqueued: list[str] = []
        repository._enqueue_delivery = enqueued.append

        fresh = repository.enqueue_master_catalog("item")
        self.assertEqual(fresh, str(UUID(int=993)))
        self.assertEqual(builds, [])

        latest["delivered_at"] = now - timedelta(hours=2)
        stale = repository.enqueue_master_catalog("item")
        self.assertEqual(stale, str(UUID(int=994)))
        self.assertEqual(builds[0]["source_version"], 5)
        self.assertEqual(builds[0]["source_environment"], "test")
        self.assertEqual(enqueued, [str(UUID(int=994))])

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

    def test_machine_mapping_preserves_the_erp_workstation_name(self) -> None:
        repository = sys.modules["npi_erpnext_connector.master_data_repository"]
        record = repository._record(repository.MasterCatalogKind.MACHINE, {
            "name": "机台 550-02", "workstation_name": "机台 550-02",
            "workstation_type": "Injection", "disabled": 1,
            "modified": datetime(2026, 9, 6, 2, 0),
        })
        self.assertEqual(record["sourceKey"], "机台 550-02")
        self.assertEqual(record["displayName"], "机台 550-02")
        self.assertEqual(record["groupKey"], "Injection")
        self.assertFalse(record["enabled"])


if __name__ == "__main__":
    unittest.main()
