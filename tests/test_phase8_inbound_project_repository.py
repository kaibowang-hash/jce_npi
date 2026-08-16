from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.inbound_project.domain import canonical_json_hash
from npi_integration.inbound_project.ingress import authenticate_project_source_request
from npi_integration.inbound_project.signature import WEBHOOK_METHOD, WEBHOOK_PATH
from tests.test_phase8_inbound_project_domain import event, raw, uid
from tests.test_phase8_inbound_project_ingress import headers_for
from tests.test_phase8_inbound_project_signature_config import NOW, SECRET_OLD, profile


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeDocument(AttrDict):
    def __init__(self, owner: "Phase8InboundProjectRepositoryTest", values: dict[str, Any]):
        super().__init__(values)
        object.__setattr__(self, "_owner", owner)

    def insert(self):
        identity_field = {
            "NPI Inbox Message": "receipt_id",
            "NPI Project Source Binding": "source_key_hash",
            "NPI Audit Event": "event_id",
        }[str(self.doctype)]
        self.name = str(self[identity_field])
        self._owner.events.append(("insert", str(self.doctype), self.name))
        if self._owner.fail_on == ("insert", str(self.doctype)):
            raise RuntimeError(f"Injected failure at insert {self.doctype}")
        bucket = self._owner.documents.setdefault(str(self.doctype), {})
        if self.name in bucket:
            raise self._owner.frappe.DuplicateEntryError()
        if self.doctype == "NPI Inbox Message" and any(
            str(document.event_id) == str(self.event_id)
            for document in bucket.values()
        ):
            raise self._owner.frappe.DuplicateEntryError()
        bucket[self.name] = self
        return self

    def save(self):
        self._owner.events.append(("save", str(self.doctype), str(self.name)))
        if self._owner.fail_on == ("save", str(self.doctype)):
            raise RuntimeError(f"Injected failure at save {self.doctype}")
        self._owner.documents[str(self.doctype)][str(self.name)] = self
        return self


class Phase8InboundProjectRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.inbound_project.frappe_validation",
        "npi_integration.inbound_project.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.documents: dict[str, dict[str, FakeDocument]] = {}
        self.events: list[tuple[str, str, str]] = []
        self.locked: list[tuple[str, str]] = []
        self.fail_on: tuple[str, str] | None = None
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        self.frappe.get_all = self.get_all
        self.frappe.get_doc = self.get_doc
        sys.modules["frappe"] = self.frappe
        self.module = importlib.import_module(
            "npi_integration.inbound_project.frappe_repository"
        )
        self.repository = self.module.FrappeInboundProjectRepository()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved_modules[name] is not None:
                sys.modules[name] = self.saved_modules[name]

    def get_doc(self, doctype_or_values, name: str | None = None, **kwargs: Any):
        if isinstance(doctype_or_values, dict):
            return FakeDocument(self, dict(doctype_or_values))
        if kwargs.get("for_update"):
            self.locked.append((str(doctype_or_values), str(name)))
        document = self.documents.get(str(doctype_or_values), {}).get(str(name))
        if document is None:
            raise self.frappe.DoesNotExistError()
        return document

    def get_all(
        self,
        doctype: str,
        *,
        filters: dict[str, object],
        fields: list[str],
        **_kwargs: Any,
    ) -> list[AttrDict]:
        rows = []
        for document in self.documents.get(doctype, {}).values():
            if all(str(document.get(key)) == str(value) for key, value in filters.items()):
                rows.append(AttrDict({field: document.get(field) for field in fields}))
        return rows

    def authenticated(
        self,
        *,
        event_id: int = 1,
        object_version: int = 1,
        title: str = "Synthetic Quotation Project",
        indent: int | None = None,
    ):
        candidate = event(object_version=object_version)
        candidate["event_id"] = uid(event_id)
        payload = dict(candidate["payload"])
        payload["title"] = title
        candidate["payload"] = payload
        candidate["payload_hash"] = canonical_json_hash(payload)
        body = raw(candidate, indent=indent)
        headers = headers_for(body, request_id=uid(1000 + event_id))
        return authenticate_project_source_request(
            method=WEBHOOK_METHOD,
            path=WEBHOOK_PATH,
            content_type="application/json",
            content_encoding=None,
            raw_body=body,
            request_id=headers.request_id,
            key_id=headers.key_id,
            timestamp=headers.timestamp,
            signature=headers.signature,
            is_secure=False,
            site_tenant_id="tenant-synthetic",
            now=NOW,
            profile_resolver=profile,
            secret_resolver=lambda _reference: SECRET_OLD,
        )

    def only(self, doctype: str) -> FakeDocument:
        values = tuple(self.documents.get(doctype, {}).values())
        self.assertEqual(len(values), 1)
        return values[0]

    def test_first_landing_freezes_receipt_source_head_and_audit_without_business_rows(self) -> None:
        authenticated = self.authenticated()
        outcome = self.repository.land(authenticated)
        self.assertEqual(outcome.disposition.value, "accepted")
        self.assertEqual(outcome.state, "pending")
        self.assertTrue(outcome.should_enqueue)
        self.assertFalse(outcome.exact_duplicate)
        inbox = self.only("NPI Inbox Message")
        binding = self.only("NPI Project Source Binding")
        audit = self.only("NPI Audit Event")
        self.assertEqual(inbox.receipt_id, str(outcome.receipt_id))
        self.assertEqual(inbox.raw_body, authenticated.raw_body.decode("utf-8"))
        self.assertEqual(inbox.canonical_event_hash, authenticated.event.canonical_event_hash)
        self.assertEqual(inbox.policy_hash, authenticated.policy.snapshot_hash)
        self.assertNotIn("signature", inbox)
        self.assertEqual(binding.highest_inbox_message, inbox.receipt_id)
        self.assertEqual(binding.highest_received_version, 1)
        self.assertEqual(binding.stream_state, "unbound")
        self.assertEqual(audit.operation, "inbound_project.land")
        for forbidden in (
            "NPI Engineering Project",
            "NPI Gate Shell",
            "NPI Domain Work Item",
            "NPI Outbox Message",
            "NPI Execution Request",
        ):
            self.assertNotIn(forbidden, self.documents)
        for flag in (
            "npi_inbound_project_inbox_write",
            "npi_project_source_binding_write",
            "npi_audit_append",
        ):
            self.assertFalse(hasattr(self.frappe.flags, flag))

    def test_event_exact_replay_returns_original_and_conflict_never_overwrites_it(self) -> None:
        first = self.repository.land(self.authenticated(indent=2))
        inbox = self.only("NPI Inbox Message")
        original = dict(inbox)
        replay = self.repository.land(self.authenticated(indent=None))
        self.assertTrue(replay.exact_duplicate)
        self.assertEqual(replay.receipt_id, first.receipt_id)
        self.assertFalse(replay.should_enqueue)
        self.assertEqual(dict(inbox), original)
        conflict = self.repository.land(self.authenticated(title="Conflicting title"))
        self.assertEqual(conflict.conflict_code, "INBOUND_PROJECT_EVENT_CONFLICT")
        self.assertFalse(conflict.exact_duplicate)
        self.assertEqual(conflict.receipt_id, first.receipt_id)
        self.assertEqual(dict(inbox), original)
        self.assertEqual(len(self.documents["NPI Inbox Message"]), 1)
        self.assertEqual(len(self.documents["NPI Audit Event"]), 3)

    def test_source_order_retains_lower_equal_and_conflict_truth(self) -> None:
        first = self.repository.land(self.authenticated(event_id=1, object_version=2))
        lower = self.repository.land(self.authenticated(event_id=2, object_version=1))
        equal = self.repository.land(self.authenticated(event_id=3, object_version=2))
        conflict = self.repository.land(
            self.authenticated(event_id=4, object_version=2, title="Version conflict")
        )
        higher_after_conflict = self.repository.land(
            self.authenticated(event_id=5, object_version=3, title="Higher event")
        )
        self.assertTrue(first.should_enqueue)
        self.assertEqual(lower.disposition.value, "source_superseded")
        self.assertEqual(lower.state, "superseded")
        self.assertEqual(equal.disposition.value, "source_exact_replay")
        self.assertEqual(equal.state, "superseded")
        self.assertEqual(conflict.conflict_code, "INBOUND_PROJECT_SOURCE_CONFLICT")
        self.assertEqual(conflict.state, "quarantined")
        self.assertEqual(
            higher_after_conflict.conflict_code,
            "INBOUND_PROJECT_SOURCE_CONFLICT",
        )
        binding = self.only("NPI Project Source Binding")
        self.assertEqual(binding.highest_received_version, 2)
        self.assertEqual(binding.stream_state, "conflicted")
        self.assertEqual(len(self.documents["NPI Inbox Message"]), 5)
        self.assertTrue(
            all(
                not outcome.should_enqueue
                for outcome in (lower, equal, conflict, higher_after_conflict)
            )
        )

    def test_higher_version_after_bound_project_is_retained_without_rewrite(self) -> None:
        self.repository.land(self.authenticated(event_id=1, object_version=1))
        binding = self.only("NPI Project Source Binding")
        binding.stream_state = "bound"
        binding.bound_project_global_id = uid(700)
        before = binding.bound_project_global_id
        later = self.repository.land(self.authenticated(event_id=2, object_version=2))
        self.assertEqual(later.state, "received_after_creation")
        self.assertEqual(later.disposition.value, "received_after_creation")
        self.assertFalse(later.should_enqueue)
        self.assertEqual(binding.highest_received_version, 2)
        self.assertEqual(binding.bound_project_global_id, before)
        self.assertNotIn("NPI Engineering Project", self.documents)

    def test_failure_audit_contains_only_bounded_hash_evidence(self) -> None:
        self.repository.append_ingress_failure_audit(
            request_id=UUID(int=900),
            trace_id="inbound-safe-trace-900",
            code="INBOUND_PROJECT_AUTHENTICATION_FAILED",
            received_at=datetime(2026, 8, 16, 6, 0, tzinfo=UTC),
            body_size=128,
            raw_hash="a" * 64,
            key_id_hash="b" * 64,
        )
        audit = self.only("NPI Audit Event")
        summary = audit.input_summary
        self.assertEqual(summary["bodySize"], 128)
        self.assertEqual(summary["rawBodyHash"], "a" * 64)
        self.assertEqual(summary["signingKeyIdHash"], "b" * 64)
        serialized = repr(dict(audit)).casefold()
        for forbidden in ("signature", "authorization", "cookie", "secret/"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
