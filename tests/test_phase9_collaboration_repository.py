from __future__ import annotations

import importlib
import inspect
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.security import Principal


NOW = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


class Row(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class Document(Row):
    def __init__(self, store: list[Document], values: dict[str, object]) -> None:
        super().__init__(values)
        self._store = store

    def insert(self):
        self.setdefault("creation", NOW.replace(tzinfo=None))
        self._store.append(self)
        return self

    def save(self):
        return self


def assignment(number: int, **overrides: object) -> Row:
    values: dict[str, object] = {
        "global_id": f"00000000-0000-4000-8000-{number:012d}",
        "tenant_id": "TENANT-A",
        "actor_user_id": "owner@example.invalid",
        "project_global_id": "00000000-0000-4000-8000-000000000201",
        "source_type": "domain_work_item",
        "source_global_id": f"00000000-0000-4000-8000-{number + 100:012d}",
        "source_version": 2,
        "category": "work",
        "due_at": NOW + timedelta(days=1),
        "priority_value": "medium",
        "blocking": 0,
        "active": 1,
    }
    values.update(overrides)
    return Row(values)


class Phase9CollaborationRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.collaboration.frappe_validation",
        "npi_core.collaboration.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.rows = [
            assignment(1),
            assignment(
                2,
                source_global_id="00000000-0000-4000-8000-000000000102",
                priority_value="critical",
                blocking=1,
            ),
        ]
        self.documents: list[Document] = []
        self.sent: list[dict[str, object]] = []
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source, **_values: source
        frappe.flags = types.SimpleNamespace()
        frappe.conf = Row()
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.get_all = lambda doctype, **_values: list(self.rows) if doctype == "NPI My Work Assignment" else []
        frappe.get_doc = self.get_doc
        frappe.sendmail = lambda **values: self.sent.append(values)
        frappe.db = types.SimpleNamespace(
            exists=lambda *_args, **_kwargs: False,
            get_value=lambda doctype, name, field, **_values: "zh" if doctype == "User" else None,
            rollback=lambda: None,
        )
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.module = importlib.import_module("npi_core.collaboration.frappe_repository")

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def get_doc(self, doctype_or_values, name=None, **_values):
        if isinstance(doctype_or_values, dict):
            return Document(self.documents, doctype_or_values)
        raise self.frappe.DoesNotExistError()

    def test_scheduler_creates_recipient_projection_and_queues_requested_email(self) -> None:
        result = self.module.refresh_due_notifications(NOW)
        notifications = [item for item in self.documents if item.doctype == "NPI Internal Notification"]
        audits = [item for item in self.documents if item.doctype == "NPI Audit Event"]
        self.assertEqual(result, {"created": 2, "emailQueued": 2, "emailFailed": 0})
        self.assertEqual(len(notifications), 2)
        self.assertEqual(len({item.delivery_key_hash for item in notifications}), 2)
        self.assertEqual({item.email_delivery_state for item in notifications}, {"queued"})
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(all("Notification:" in str(item["message"]) for item in self.sent))
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].operation, "notification.critical_blocker.created")

    def test_email_queue_failure_is_explicit_and_does_not_claim_delivery(self) -> None:
        self.rows = [assignment(3)]

        def fail(**_values):
            raise RuntimeError("queue unavailable")

        self.frappe.sendmail = fail
        result = self.module.refresh_due_notifications(NOW)
        notification = next(item for item in self.documents if item.doctype == "NPI Internal Notification")
        self.assertEqual(result, {"created": 1, "emailQueued": 0, "emailFailed": 1})
        self.assertEqual(notification.email_delivery_state, "failed")
        self.assertEqual(notification.failure_code, "email_queue_failed")
        self.assertNotEqual(notification.email_delivery_state, "sent")

    def test_preference_identity_is_tenant_scoped_and_critical_is_always_emailed(self) -> None:
        first = self.module.FrappeCollaborationRepository(
            principal=Principal(user_id="owner@example.invalid", tenant_id="TENANT-A"),
            request_id="00000000-0000-4000-8000-000000000001",
            trace_id="00000000-0000-4000-8000-000000000001",
        )
        second = self.module.FrappeCollaborationRepository(
            principal=Principal(user_id="owner@example.invalid", tenant_id="TENANT-B"),
            request_id="00000000-0000-4000-8000-000000000002",
            trace_id="00000000-0000-4000-8000-000000000002",
        )
        self.assertNotEqual(first._preference_id(), second._preference_id())
        self.assertIn(self.module.NotificationKind.CRITICAL_BLOCKER, {
            self.module.notification_kind(self.rows[1], NOW)[0]
        })

    def test_meeting_command_owns_receipt_minute_work_links_audit_and_seal_order(self) -> None:
        source = inspect.getsource(self.module.FrappeCollaborationRepository.create_meeting)
        positions = [
            source.index("self._insert_idempotency("),
            source.index('"doctype": "NPI Meeting Minute"'),
            source.index("create_domain_work_items_in_parent_command("),
            source.index('"doctype": "NPI Meeting Work Link"'),
            source.index("self._append_audit("),
            source.index("self._seal_idempotency("),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("with collaboration_write_scope(audit=True)", source)
        work_source = inspect.getsource(
            self.module.FrappeProjectWorkRepository.create_domain_work_items_in_parent_command
        )
        self.assertIn('"meeting_minute.create"', work_source)
        self.assertIn('"decision_request"', work_source)

    def test_repository_never_uses_sql_permission_bypass_or_fake_sent_state(self) -> None:
        source = inspect.getsource(self.module)
        for forbidden in (
            "frappe.db." + "sql",
            "frappe.db." + "commit",
            "ignore_permissions",
            "requests.",
            "httpx.",
            'EmailDeliveryState("sent")',
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("serverFiltered", source)
        self.assertIn("MAX_NOTIFICATION_ROWS + 1", source)


if __name__ == "__main__":
    unittest.main()
