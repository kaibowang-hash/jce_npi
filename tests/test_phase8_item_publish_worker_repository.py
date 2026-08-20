from __future__ import annotations

import importlib
import sys
import types
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.item_publish.adapters import (
    ItemAdapterResponse,
    classify_item_adapter_response,
)
from npi_integration.item_publish.config import ItemExecutionProfile
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_OPERATION,
    CurrentItemMapping,
    ItemTargetMode,
)
import tests.test_phase8_item_publish_repository as command_test


NOW = datetime(2026, 8, 16, 16, 0, tzinfo=UTC)


class WorkerDatabase(command_test.FakeDatabase):
    def __init__(self, owner: "Phase8ItemPublishWorkerRepositoryTest") -> None:
        super().__init__(owner.harness)
        self.worker_owner = owner

    def get_value(self, doctype, filters, fieldname, **kwargs):
        if doctype == "User" and isinstance(fieldname, list):
            enabled, user_type = self.worker_owner.users.get(
                str(filters), (0, None)
            )
            value = {"enabled": enabled, "user_type": user_type}
            return types.SimpleNamespace(**value) if kwargs.get("as_dict") else value
        return super().get_value(doctype, filters, fieldname, **kwargs)


class Phase8ItemPublishWorkerRepositoryTest(unittest.TestCase):
    MODULE = "npi_integration.item_publish.worker_repository"

    def setUp(self) -> None:
        self.saved_module = sys.modules.pop(self.MODULE, None)
        self.harness = command_test.Phase8ItemPublishRepositoryTest(
            methodName=(
                "test_synthetic_adds_one_versioned_outbox_in_the_same_write_scope"
            )
        )
        self.harness.setUp()
        self.original_insert = command_test.FakeDocument.insert
        self.original_save = getattr(command_test.FakeDocument, "save", None)
        command_test.FakeDocument.insert = type(self)._insert  # type: ignore[method-assign]
        command_test.FakeDocument.save = type(self)._save  # type: ignore[attr-defined]
        self.users = {
            "item-worker@example.invalid": (1, "System User"),
        }
        self.harness.frappe.db = WorkerDatabase(self)
        self.harness.frappe.get_roles = lambda actor: (
            ["NPI API User"] if actor in self.users else []
        )
        self.module = importlib.import_module(self.MODULE)
        self.repository = self.module.FrappeItemPublishWorkerRepository()
        self.profile = self.harness.synthetic_profile()
        self.harness.repository = self.harness.new_repository(self.profile)
        outcome = self.harness.create()
        assert outcome.outbox_event_id is not None
        self.outbox_id = outcome.outbox_event_id
        self.harness.frappe.db.commit()

    def tearDown(self) -> None:
        command_test.FakeDocument.insert = self.original_insert
        if self.original_save is None:
            delattr(command_test.FakeDocument, "save")
        else:
            command_test.FakeDocument.save = self.original_save  # type: ignore[attr-defined]
        sys.modules.pop(self.MODULE, None)
        self.harness.tearDown()
        if self.saved_module is not None:
            sys.modules[self.MODULE] = self.saved_module

    def _insert(document):
        owner = document._owner
        doctype = str(document.doctype)
        required_flag = {
            "NPI Item Publish Request": "npi_item_publish_request_write",
            "NPI Item Publish Command Idempotency": (
                "npi_item_publish_idempotency_write"
            ),
            "NPI Outbox Message": "npi_item_outbox_write",
            "NPI Item Publish Attempt": "npi_item_publish_attempt_write",
            "NPI Item Publish Result": "npi_item_publish_result_write",
            "NPI Item Mapping Observation": "npi_item_mapping_write",
            "NPI Item Mapping Head": "npi_item_mapping_write",
            "NPI Audit Event": "npi_audit_append",
        }.get(doctype)
        if required_flag is not None and not getattr(
            owner.frappe.flags, required_flag, False
        ):
            raise AssertionError(f"missing controlled write flag {required_flag}")
        identity = {
            "NPI Item Publish Request": "global_id",
            "NPI Item Publish Command Idempotency": "scope_key_hash",
            "NPI Outbox Message": "event_id",
            "NPI Item Publish Attempt": "global_id",
            "NPI Item Publish Result": "global_id",
            "NPI Item Mapping Observation": "global_id",
            "NPI Item Mapping Head": "global_id",
            "NPI Audit Event": "event_id",
        }[doctype]
        document.name = str(document[identity])
        bucket = owner.documents.setdefault(doctype, {})
        if document.name in bucket:
            raise owner.frappe.DuplicateEntryError()
        bucket[document.name] = document
        owner.pending.append((doctype, document.name))
        owner.events.append(f"insert:{doctype}")
        return document

    def _save(document):
        owner = document._owner
        required_flag = {
            "NPI Item Publish Request": "npi_item_publish_request_write",
            "NPI Outbox Message": "npi_item_outbox_write",
            "NPI Item Publish Attempt": "npi_item_publish_attempt_write",
            "NPI Item Mapping Head": "npi_item_mapping_write",
        }.get(str(document.doctype))
        if required_flag is not None and not getattr(
            owner.frappe.flags, required_flag, False
        ):
            raise AssertionError(f"missing controlled write flag {required_flag}")
        owner.events.append(f"save:{document.doctype}")
        return document

    def outbox(self):
        return self.harness.documents["NPI Outbox Message"][str(self.outbox_id)]

    def request(self):
        values = tuple(
            self.harness.documents["NPI Item Publish Request"].values()
        )
        return values[-1]

    def attempt(self, global_id: UUID):
        return self.harness.documents["NPI Item Publish Attempt"][str(global_id)]

    def count(self, doctype: str) -> int:
        return len(self.harness.documents.get(doctype, {}))

    @staticmethod
    def sandbox_profile() -> ItemExecutionProfile:
        return ItemExecutionProfile(
            profile_id="item-sandbox-v1",
            profile_version=1,
            tenant_id="TENANT-A",
            project_global_id=str(command_test.PROJECT_ID),
            target_mode=ItemTargetMode.SANDBOX,
            environment_code="sandbox",
            requester_user_ids=("publisher@example.invalid",),
            service_actor_user_id="item-worker@example.invalid",
            allowed_operations=(ITEM_PUBLISH_OPERATION,),
            adapter_resolver="npi_integration.item_publish.sandbox_adapter.resolve",
            base_url="https://erpnext.sandbox.example.invalid",
            allowed_hostnames=("erpnext.sandbox.example.invalid",),
            secret_reference="secrets/item-sandbox-v1",
            response_authentication="hmac-sha256-v1",
            connect_timeout_seconds=10,
            read_timeout_seconds=30,
            non_production_attested=True,
        )

    def classify(self, claim, profile, **changes: object):
        values: dict[str, object] = {
            "request_global_id": claim.command.request_global_id,
            "attempt_global_id": claim.command.attempt_global_id,
            "attempt_number": claim.command.attempt_number,
            "target_idempotency_key_hash": (
                claim.command.target_idempotency_key_hash
            ),
            "source_hash": claim.command.source_hash,
            "response_hash": "e" * 64,
        }
        values.update(changes)
        return classify_item_adapter_response(
            profile=profile,
            command=claim.command,
            response=ItemAdapterResponse(**values),  # type: ignore[arg-type]
            observed_at=NOW + timedelta(seconds=3),
        )

    def test_pending_live_and_expired_pre_boundary_claims_are_bounded(self) -> None:
        first = self.repository.claim(self.outbox_id, now=NOW)
        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(first.command.attempt_number, 1)
        self.assertEqual(self.outbox().state, "processing")
        self.assertEqual(self.request().state, "processing")
        self.assertEqual(self.count("NPI Item Publish Attempt"), 1)
        self.assertIsNone(
            self.repository.claim(
                self.outbox_id,
                now=NOW + timedelta(seconds=299),
            )
        )
        recovered = self.repository.claim(
            self.outbox_id,
            now=NOW + timedelta(seconds=300),
        )
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertTrue(recovered.expired_recovery)
        self.assertFalse(recovered.recovered_after_adapter_boundary)
        self.assertEqual(recovered.command.attempt_number, 2)
        self.assertEqual(self.count("NPI Item Publish Attempt"), 2)
        old = self.attempt(first.command.attempt_global_id)
        self.assertEqual(old.state, "observed_failure")
        self.assertFalse(bool(old.adapter_boundary_crossed))

    def test_worker_write_scopes_use_service_user_and_restore_caller(self) -> None:
        validation = importlib.import_module(
            "npi_integration.item_publish.frappe_validation"
        )
        for scope_factory in (
            validation.item_claim_write,
            validation.item_result_transaction_write,
            validation.item_mapping_write,
        ):
            with self.subTest(scope=scope_factory.__name__):
                with scope_factory():
                    self.assertEqual(
                        self.harness.frappe.session.user,
                        "Administrator",
                    )
                self.assertEqual(
                    self.harness.frappe.session.user,
                    "publisher@example.invalid",
                )

    def test_claim_rejects_request_and_outbox_state_drift(self) -> None:
        self.request().state = "synthetic_verified"
        with self.assertRaisesRegex(RuntimeError, "states are inconsistent"):
            self.repository.claim(self.outbox_id, now=NOW)
        self.assertEqual(self.count("NPI Item Publish Attempt"), 0)

    def test_expired_crossed_boundary_reuses_attempt_without_redispatch_claim(self) -> None:
        claim = self.repository.claim(self.outbox_id, now=NOW)
        assert claim is not None
        self.assertTrue(
            self.repository.mark_adapter_boundary(
                claim,
                profile=self.profile,
                now=NOW + timedelta(seconds=1),
            )
        )
        recovered = self.repository.claim(
            self.outbox_id,
            now=NOW + timedelta(seconds=300),
        )
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertTrue(recovered.recovered_after_adapter_boundary)
        self.assertEqual(
            recovered.command.attempt_global_id,
            claim.command.attempt_global_id,
        )
        self.assertEqual(recovered.command.attempt_number, 1)
        self.assertEqual(self.count("NPI Item Publish Attempt"), 1)

    def test_synthetic_result_is_atomic_terminal_truth_without_mapping(self) -> None:
        claim = self.repository.claim(self.outbox_id, now=NOW)
        assert claim is not None
        self.repository.require_execution_profile(claim, self.profile)
        self.repository.mark_adapter_boundary(
            claim,
            profile=self.profile,
            now=NOW + timedelta(seconds=1),
        )
        classified = self.classify(claim, self.profile)
        outcome = self.repository.seal_result(
            claim,
            profile=self.profile,
            result=classified,
            now=NOW + timedelta(seconds=4),
        )
        self.assertEqual(outcome.state, "synthetic_verified")
        self.assertFalse(outcome.mapping_advanced)
        self.assertEqual(self.request().state, "synthetic_verified")
        self.assertEqual(self.outbox().state, "succeeded")
        attempt = self.attempt(claim.command.attempt_global_id)
        self.assertEqual(attempt.state, "synthetic_verified")
        self.assertEqual(self.count("NPI Item Publish Result"), 1)
        self.assertEqual(self.count("NPI Item Mapping Observation"), 0)
        self.assertEqual(self.count("NPI Item Mapping Head"), 0)
        self.assertNotIn("formal_item_code", repr(self.outbox()))

    def test_authenticated_authoritative_result_advances_one_mapping_head(self) -> None:
        sandbox = self.sandbox_profile()
        self.harness.documents.clear()
        self.harness.pending.clear()
        self.harness.repository = self.harness.new_repository(sandbox)
        created = self.harness.create()
        assert created.outbox_event_id is not None
        self.outbox_id = created.outbox_event_id
        claim = self.repository.claim(self.outbox_id, now=NOW)
        assert claim is not None
        self.repository.mark_adapter_boundary(
            claim,
            profile=sandbox,
            now=NOW + timedelta(seconds=1),
        )
        attempt = self.attempt(claim.command.attempt_global_id)
        self.assertEqual(attempt.connect_timeout_seconds, 10)
        self.assertEqual(attempt.read_timeout_seconds, 30)
        classified = self.classify(
            claim,
            sandbox,
            http_status=200,
            response_authenticated=True,
            formal_item_code="ITEM-SANDBOX-001",
            target_version="1",
        )
        outcome = self.repository.seal_result(
            claim,
            profile=sandbox,
            result=classified,
            now=NOW + timedelta(seconds=4),
        )
        self.assertEqual(outcome.state, "succeeded")
        self.assertTrue(outcome.mapping_advanced)
        self.assertEqual(self.count("NPI Item Mapping Observation"), 1)
        self.assertEqual(self.count("NPI Item Mapping Head"), 1)
        head = next(iter(self.harness.documents["NPI Item Mapping Head"].values()))
        self.assertEqual(head.mapping_version, 1)
        self.assertEqual(head.formal_item_code, "ITEM-SANDBOX-001")
        self.assertEqual(head.target_version, "1")

    def test_late_authoritative_result_records_conflict_without_overwriting_head(self) -> None:
        sandbox = self.sandbox_profile()
        self.harness.documents.clear()
        self.harness.pending.clear()
        self.harness.repository = self.harness.new_repository(sandbox)
        first_created = self.harness.create()
        second_created = self.harness.repository.create_item_publish_request(
            command_test.PROJECT_ID,
            publish_request_id=command_test.PHASE5_REQUEST_ID,
            selected_publish_node_id=self.harness.phase5.nodes[0].global_id,
            expected_mapping_version=0,
            idempotency_key_hash=command_test.HASH_B,
            acknowledgement=command_test.ITEM_PUBLISH_ACKNOWLEDGEMENT,
        )
        assert first_created.outbox_event_id is not None
        assert second_created.outbox_event_id is not None

        first = self.repository.claim(first_created.outbox_event_id, now=NOW)
        assert first is not None
        self.repository.mark_adapter_boundary(
            first,
            profile=sandbox,
            now=NOW + timedelta(seconds=1),
        )
        first_result = self.classify(
            first,
            sandbox,
            http_status=200,
            response_authenticated=True,
            formal_item_code="ITEM-SANDBOX-001",
            target_version="1",
        )
        self.repository.seal_result(
            first,
            profile=sandbox,
            result=first_result,
            now=NOW + timedelta(seconds=2),
        )
        head = next(iter(self.harness.documents["NPI Item Mapping Head"].values()))
        retained_hash = head.head_hash

        second = self.repository.claim(
            second_created.outbox_event_id,
            now=NOW + timedelta(seconds=3),
        )
        assert second is not None
        self.repository.mark_adapter_boundary(
            second,
            profile=sandbox,
            now=NOW + timedelta(seconds=4),
        )
        late_result = self.classify(
            second,
            sandbox,
            http_status=200,
            response_authenticated=True,
            formal_item_code="ITEM-SANDBOX-001",
            target_version="2",
        )
        late = self.repository.seal_result(
            second,
            profile=sandbox,
            result=late_result,
            now=NOW + timedelta(seconds=5),
        )
        self.assertEqual(late.state, "mapping_conflict")
        self.assertFalse(late.mapping_advanced)
        self.assertEqual(self.count("NPI Item Mapping Observation"), 2)
        second_result = next(
            row
            for row in self.harness.documents["NPI Item Publish Result"].values()
            if row.request_global_id == str(second.request_global_id)
        )
        self.assertEqual(second_result.state, "succeeded")
        self.assertEqual(second_result.authority, "authoritative_sandbox")
        self.assertTrue(bool(second_result.response_authenticated))
        self.assertEqual(second_result.result_snapshot["state"], "succeeded")
        self.assertEqual(self.count("NPI Item Mapping Head"), 1)
        self.assertEqual(head.mapping_version, 1)
        self.assertEqual(head.target_version, "1")
        self.assertEqual(head.head_hash, retained_hash)
        second_request = self.harness.documents["NPI Item Publish Request"][
            str(second.request_global_id)
        ]
        self.assertEqual(second_request.state, "mapping_conflict")
        second_outbox = self.harness.documents["NPI Outbox Message"][
            str(second.outbox_event_id)
        ]
        self.assertEqual(second_outbox.state, "succeeded")
        self.assertEqual(second_outbox.disposition, "mapping_conflict")

    def test_profile_binding_and_service_actor_fail_closed(self) -> None:
        claim = self.repository.claim(self.outbox_id, now=NOW)
        assert claim is not None
        self.users["item-worker@example.invalid"] = (0, "System User")
        with self.assertRaisesRegex(
            self.module.ItemPublishWorkerFinalFailure,
            "EXECUTION_PROFILE_UNAVAILABLE",
        ):
            self.repository.require_execution_profile(claim, self.profile)
        self.users["item-worker@example.invalid"] = (1, "System User")
        mismatched = replace(self.profile, profile_version=2)
        with self.assertRaises(self.module.ItemPublishWorkerFinalFailure):
            self.repository.require_execution_profile(claim, mismatched)


if __name__ == "__main__":
    unittest.main()
