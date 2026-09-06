from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector"
if str(ERP_APP) not in sys.path:
    sys.path.insert(0, str(ERP_APP))


class ERPNextProjectWorkerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_erpnext_connector.project_repository",
        "npi_erpnext_connector.project_worker",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.conf = {}
        frappe.enqueue = self.enqueue
        frappe.whitelist = lambda **_kwargs: lambda function: function
        sys.modules["frappe"] = frappe
        self.module = importlib.import_module(
            "npi_erpnext_connector.project_worker"
        )
        self.saved_states: list[dict[str, object]] = []
        self.enqueued: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.document = types.SimpleNamespace(
            name=str(UUID(int=901)),
            event_id=str(UUID(int=901)),
            source_project_id="PROJ-0027",
            source_version=1,
            status="pending",
            attempt_count=0,
            next_attempt_at=None,
            receipt_id=None,
            response_state=None,
            response_disposition=None,
            target_project_global_id=None,
            last_error_code=None,
        )
        self.module.project_sender_is_disabled = lambda _conf: False
        self.module.load_project_sender_profile = lambda _conf: object()
        self.module.get_project_delivery = lambda _delivery_id: self.document
        self.module.restore_delivery_event = lambda _document: object()
        self.module.save_project_delivery = self.save

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def enqueue(self, *args: object, **kwargs: object) -> None:
        self.enqueued.append((args, kwargs))

    def save(self, document: object) -> None:
        self.saved_states.append(dict(vars(document)))

    def test_accepts_polls_maps_and_reconciles_authorization(self) -> None:
        from npi_erpnext_connector.project_transport import (
            AcceptedProjectReceipt,
            ProjectReceiptStatus,
        )

        self.module.submit_project_event = lambda _profile, _event: (
            AcceptedProjectReceipt(UUID(int=902), "pending", False)
        )
        self.module.get_project_receipt_status = lambda _profile, _receipt: (
            ProjectReceiptStatus(
                receipt_id=UUID(int=902),
                state="succeeded",
                terminal=True,
                disposition="project_created",
                project_global_id=UUID(int=903),
                error_code=None,
            )
        )
        mappings: list[UUID] = []
        self.module.persist_project_mapping = (
            lambda _document, target, **_kwargs: mappings.append(target) or True
        )

        self.module.deliver_project(str(UUID(int=901)))

        self.assertEqual(self.document.status, "succeeded")
        self.assertEqual(self.document.receipt_id, str(UUID(int=902)))
        self.assertEqual(self.document.target_project_global_id, str(UUID(int=903)))
        self.assertEqual(mappings, [UUID(int=903)])
        self.assertEqual(self.saved_states[0]["status"], "accepted")
        self.assertEqual(self.saved_states[-1]["status"], "succeeded")
        self.assertEqual(
            self.enqueued[-1][0],
            ("npi_erpnext_connector.worker.reconcile_all_users",),
        )

    def test_pending_receipt_is_retried_without_resubmitting_event(self) -> None:
        from npi_erpnext_connector.project_transport import ProjectReceiptStatus

        self.document.status = "accepted"
        self.document.receipt_id = str(UUID(int=902))
        self.module.submit_project_event = lambda *_args: self.fail("must not resubmit")
        self.module.get_project_receipt_status = lambda _profile, _receipt: (
            ProjectReceiptStatus(
                receipt_id=UUID(int=902),
                state="processing",
                terminal=False,
                disposition="pending",
                project_global_id=None,
                error_code=None,
            )
        )
        self.module.persist_project_mapping = lambda *_args, **_kwargs: self.fail(
            "must not map"
        )

        self.module.deliver_project(str(UUID(int=901)))

        self.assertEqual(self.document.status, "retry")
        self.assertEqual(self.document.last_error_code, "PROCESSING")
        self.assertIsNotNone(self.document.next_attempt_at)


if __name__ == "__main__":
    unittest.main()
