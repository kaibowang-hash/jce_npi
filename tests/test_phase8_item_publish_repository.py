from __future__ import annotations

import ast
import importlib
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_core.foundation.security import Principal
from npi_integration.item_publish.config import ItemExecutionProfile
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_ACKNOWLEDGEMENT,
    ITEM_PUBLISH_OPERATION,
    CurrentItemMapping,
    ItemTargetMode,
)
from npi_integration.publish_request.domain import (
    PublishLineInput,
    PublishPolicyReference,
    ReleasedEbomEvidence,
    create_mock_publish_request,
)


NOW = datetime(2026, 8, 16, 14, 0, tzinfo=UTC)
PROJECT_ID = UUID("00000000-0000-4000-8000-000000008311")
PHASE5_REQUEST_ID = UUID("00000000-0000-4000-8000-000000008312")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000008313")
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        return self.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeDocument(AttrDict):
    def __init__(
        self,
        owner: "Phase8ItemPublishRepositoryTest",
        values: dict[str, Any],
    ) -> None:
        super().__init__(values)
        object.__setattr__(self, "_owner", owner)
        self.flags = SimpleNamespace()

    def insert(self):
        doctype = str(self.doctype)
        required_flag = {
            "NPI Item Publish Request": "npi_item_publish_request_write",
            "NPI Item Publish Command Idempotency": (
                "npi_item_publish_idempotency_write"
            ),
            "NPI Outbox Message": "npi_item_outbox_write",
            "NPI Audit Event": "npi_audit_append",
        }.get(doctype)
        if required_flag is not None and not getattr(
            self._owner.frappe.flags,
            required_flag,
            False,
        ):
            raise AssertionError(f"missing controlled write flag {required_flag}")
        if self._owner.fail_on == doctype:
            raise RuntimeError(f"injected {doctype} insert failure")
        identity_field = {
            "NPI Item Publish Request": "global_id",
            "NPI Item Publish Command Idempotency": "scope_key_hash",
            "NPI Outbox Message": "event_id",
            "NPI Audit Event": "event_id",
        }[doctype]
        self.name = str(self[identity_field])
        bucket = self._owner.documents.setdefault(doctype, {})
        if self.name in bucket:
            raise self._owner.frappe.DuplicateEntryError()
        bucket[self.name] = self
        self._owner.pending.append((doctype, self.name))
        self._owner.events.append(f"insert:{doctype}")
        return self


class FakeDatabase:
    def __init__(self, owner: "Phase8ItemPublishRepositoryTest") -> None:
        self.owner = owner

    def get_value(
        self,
        doctype: str,
        filters: object,
        fieldname: str,
        **_kwargs: Any,
    ) -> object | None:
        if doctype == "NPI Item Mapping Head" and fieldname == "name":
            for row in self.owner.documents.get(doctype, {}).values():
                if all(row.get(key) == value for key, value in dict(filters).items()):
                    return row.name
            return None
        raise AssertionError((doctype, filters, fieldname))

    def commit(self) -> None:
        self.owner.events.append("commit")
        self.owner.pending.clear()

    def rollback(self) -> None:
        self.owner.events.append("rollback")
        for doctype, name in reversed(self.owner.pending):
            self.owner.documents.get(doctype, {}).pop(name, None)
        self.owner.pending.clear()


class Phase8ItemPublishRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision",
        "npi_core.documents.frappe_repository",
        "npi_core.ebom.frappe_repository",
        "npi_integration.publish_request.frappe_repository",
        "npi_integration.item_publish.frappe_validation",
        "npi_integration.item_publish.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.documents: dict[str, dict[str, FakeDocument]] = {}
        self.pending: list[tuple[str, str]] = []
        self.events: list[str] = []
        self.fail_on: str | None = None
        self.frappe = types.ModuleType("frappe")
        self.frappe.__path__ = []
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.session = types.SimpleNamespace(
            user="publisher@example.invalid"
        )
        self.frappe.set_user = lambda user: setattr(
            self.frappe.session, "user", user
        )
        self.frappe.DoesNotExistError = type(
            "DoesNotExistError", (Exception,), {}
        )
        self.frappe.DuplicateEntryError = type(
            "DuplicateEntryError", (Exception,), {}
        )
        self.frappe.UniqueValidationError = type(
            "UniqueValidationError", (Exception,), {}
        )
        self.frappe.db = FakeDatabase(self)

        def get_doc(doctype_or_values, name=None, **_kwargs):
            if isinstance(doctype_or_values, dict):
                return FakeDocument(self, dict(doctype_or_values))
            row = self.documents.get(str(doctype_or_values), {}).get(str(name))
            if row is None:
                raise self.frappe.DoesNotExistError()
            return row

        self.frappe.get_doc = get_doc
        sys.modules["frappe"] = self.frappe
        model = types.ModuleType("frappe.model")
        model.__path__ = []
        document = types.ModuleType("frappe.model.document")
        document.Document = object
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document

        self.module = importlib.import_module(
            "npi_integration.item_publish.frappe_repository"
        )
        self.project = AttrDict(
            tenant_id="TENANT-A",
            global_id=str(PROJECT_ID),
            lifecycle_state="draft",
        )
        self.phase5 = self.phase5_request()
        self.phase5_row = AttrDict(global_id=str(PHASE5_REQUEST_ID))
        self.current_mapping: CurrentItemMapping | None = None
        self.repository = self.new_repository(self.mock_profile())

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def phase5_request(self, *, divergent: bool = False):
        release_id = UUID("00000000-0000-4000-8000-000000008314")
        first = PublishLineInput(
            global_id=UUID("00000000-0000-4000-8000-000000008315"),
            line_key="ITEM-10-A",
            parent_line_key=None,
            engineering_item_id="ENG-ITEM-001",
            description="Synthetic released item",
            quantity="1",
            engineering_uom="Nos",
            attributes=(("material", "PA66"),),
        )
        second = PublishLineInput(
            global_id=UUID("00000000-0000-4000-8000-000000008316"),
            line_key="ITEM-10-B",
            parent_line_key="ITEM-10-A",
            engineering_item_id="ENG-ITEM-001",
            description=(
                "Divergent released item"
                if divergent
                else "Synthetic released item"
            ),
            quantity="2",
            engineering_uom="Nos",
            attributes=(("material", "PA66"),),
        )
        return create_mock_publish_request(
            policy=PublishPolicyReference(
                UUID("00000000-0000-4000-8000-000000008317"),
                1,
                HASH_D,
            ),
            evidence=ReleasedEbomEvidence(
                project_global_id=PROJECT_ID,
                ebom_global_id=UUID(
                    "00000000-0000-4000-8000-000000008318"
                ),
                ebom_version=3,
                revision_global_id=UUID(
                    "00000000-0000-4000-8000-000000008319"
                ),
                revision_number=2,
                revision_snapshot_hash=HASH_A,
                lifecycle_version=4,
                release_event_global_id=release_id,
                release_event_hash=HASH_B,
                ebom_policy_global_id=UUID(
                    "00000000-0000-4000-8000-000000008320"
                ),
                ebom_policy_version=1,
                ebom_policy_snapshot_hash=HASH_C,
                approval_evidence_ids=(release_id,),
                released_at=NOW,
            ),
            lines=(first, second),
            actor_user_id="publisher@example.invalid",
            request_id=REQUEST_ID,
            trace_id="trace-p803-item-repository",
            idempotency_key_hash=HASH_A,
            global_id=PHASE5_REQUEST_ID,
            created_at=NOW,
        )

    @staticmethod
    def mock_profile(
        *,
        requester_user_ids: tuple[str, ...] = (
            "publisher@example.invalid",
        ),
    ) -> ItemExecutionProfile:
        return ItemExecutionProfile(
            profile_id="item-mock-v1",
            profile_version=1,
            tenant_id="TENANT-A",
            project_global_id=str(PROJECT_ID),
            target_mode=ItemTargetMode.MOCK,
            environment_code="mock",
            requester_user_ids=requester_user_ids,
            service_actor_user_id="item-worker@example.invalid",
        )

    @staticmethod
    def synthetic_profile() -> ItemExecutionProfile:
        return ItemExecutionProfile(
            profile_id="item-synthetic-v1",
            profile_version=1,
            tenant_id="TENANT-A",
            project_global_id=str(PROJECT_ID),
            target_mode=ItemTargetMode.SYNTHETIC,
            environment_code="disposable-test",
            requester_user_ids=("publisher@example.invalid",),
            service_actor_user_id="item-worker@example.invalid",
            allowed_operations=(ITEM_PUBLISH_OPERATION,),
            adapter_resolver=(
                "npi_integration.item_publish.runtime_fixture.synthetic_adapter"
            ),
            synthetic_test_only=True,
            disposable_runtime_marker=True,
        )

    def new_repository(
        self,
        profile: ItemExecutionProfile | None,
    ):
        repository = self.module.FrappeItemPublishRepository(
            principal=Principal(
                user_id="publisher@example.invalid",
                roles=frozenset({"NPI API User"}),
                tenant_id="TENANT-A",
            ),
            request_id=str(REQUEST_ID),
            trace_id="trace-p803-item-repository",
            profile_resolver=lambda _tenant, _project: profile,
        )
        repository._locked_command_project = lambda _project_id: self.project
        repository._authorized_project = lambda _project_id: self.project
        repository._current_actor_member = lambda _project: object()
        repository._phase5_request_for_project = (
            lambda _project, _request_id, lock: self.phase5_row
        )
        repository._exact_released_phase5_request = (
            lambda _project, _row: self.phase5
        )
        repository._current_mapping_for_source = (
            lambda _project, _source, lock: self.current_mapping
        )

        def bounded_documents(
            doctype: str,
            filters: dict[str, object],
            *,
            order_by: str,
            maximum: int,
        ):
            rows = [
                row
                for row in self.documents.get(doctype, {}).values()
                if all(
                    str(row.get(key)) == str(value)
                    for key, value in filters.items()
                )
            ]
            if doctype == "NPI Item Publish Attempt":
                rows.sort(
                    key=lambda row: (
                        int(row.attempt_number),
                        str(row.global_id),
                    )
                )
            else:
                rows.sort(
                    key=lambda row: (
                        str(row.get("created_at") or ""),
                        str(row.global_id),
                    ),
                    reverse=True,
                )
            if len(rows) > maximum:
                raise RuntimeError(
                    f"Persisted {doctype} collection exceeds its safe bound."
                )
            return tuple(rows)

        repository._bounded_documents = bounded_documents

        def append_audit(**values: object) -> None:
            self.frappe.get_doc(
                {
                    "doctype": "NPI Audit Event",
                    "event_id": str(
                        UUID(int=9000 + len(self.documents.get("NPI Audit Event", {})))
                    ),
                    **values,
                }
            ).insert()

        repository._append_audit = append_audit
        return repository

    def create(self, *, expected_mapping_version: int = 0):
        return self.repository.create_item_publish_request(
            PROJECT_ID,
            publish_request_id=PHASE5_REQUEST_ID,
            selected_publish_node_id=self.phase5.nodes[0].global_id,
            expected_mapping_version=expected_mapping_version,
            idempotency_key_hash=HASH_A,
            acknowledgement=ITEM_PUBLISH_ACKNOWLEDGEMENT,
        )

    def count(self, doctype: str) -> int:
        return len(self.documents.get(doctype, {}))

    def only(self, doctype: str) -> FakeDocument:
        values = tuple(self.documents.get(doctype, {}).values())
        self.assertEqual(len(values), 1, doctype)
        return values[0]

    def test_mock_atomically_freezes_request_receipt_and_audit_without_outbox(self) -> None:
        outcome = self.create()
        self.assertIsNotNone(outcome)
        self.assertIsNone(outcome.problem)
        self.assertFalse(outcome.replayed)
        self.assertFalse(outcome.should_enqueue)
        self.assertIsNone(outcome.outbox_event_id)
        self.assertEqual(self.count("NPI Item Publish Request"), 1)
        self.assertEqual(self.count("NPI Item Publish Command Idempotency"), 1)
        self.assertEqual(self.count("NPI Audit Event"), 1)
        self.assertEqual(self.count("NPI Outbox Message"), 0)
        request = self.only("NPI Item Publish Request")
        self.assertEqual(request.state, "validated_mock")
        self.assertFalse(bool(request.dispatch_allowed))
        self.assertIsNone(request.outbox_event_id)
        self.assertEqual(len(request.source_snapshot["occurrences"]), 2)
        serialized = repr(self.documents).casefold()
        for forbidden in (
            "quantity",
            "parentline",
            "endpoint",
            "credential",
            "item-caller",
        ):
            self.assertNotIn(str(forbidden).casefold(), serialized)

    def test_synthetic_adds_one_versioned_outbox_in_the_same_write_scope(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        outcome = self.create()
        self.assertEqual(self.frappe.session.user, "publisher@example.invalid")
        self.assertIsNone(outcome.problem)
        self.assertTrue(outcome.should_enqueue)
        self.assertIsNotNone(outcome.outbox_event_id)
        self.assertEqual(self.count("NPI Item Publish Request"), 1)
        self.assertEqual(self.count("NPI Outbox Message"), 1)
        self.assertEqual(self.count("NPI Item Publish Command Idempotency"), 1)
        outbox = self.only("NPI Outbox Message")
        request = self.only("NPI Item Publish Request")
        self.assertEqual(request.state, "queued")
        self.assertEqual(request.outbox_event_id, outbox.event_id)
        self.assertTrue(request.flags.ignore_links)
        self.assertEqual(outbox.event_type, "npi.item_publish_request.ready")
        self.assertEqual(outbox.operation, "publish_released_item")
        self.assertEqual(outbox.state, "pending")
        self.assertFalse(bool(outbox.adapter_boundary_crossed))
        self.assertEqual(outbox.attempt_count, 0)
        self.assertNotIn("adapter_resolver", repr(outbox.payload))

    def test_exact_actor_key_payload_replays_one_request_without_reenqueue(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        first = self.create()
        self.frappe.db.commit()
        second = self.create()
        self.assertEqual(second.response, first.response)
        self.assertTrue(second.replayed)
        self.assertFalse(second.should_enqueue)
        self.assertEqual(self.count("NPI Item Publish Request"), 1)
        self.assertEqual(self.count("NPI Outbox Message"), 1)
        self.assertEqual(self.count("NPI Item Publish Command Idempotency"), 1)
        self.assertEqual(self.count("NPI Audit Event"), 2)

        self.project.lifecycle_state = "completed"
        third = self.create()
        self.assertTrue(third.replayed)
        self.assertFalse(third.should_enqueue)
        self.assertEqual(self.count("NPI Item Publish Request"), 1)

    def test_same_actor_key_different_payload_is_audited_conflict(self) -> None:
        first = self.create()
        self.frappe.db.commit()
        conflict = self.repository.create_item_publish_request(
            PROJECT_ID,
            publish_request_id=PHASE5_REQUEST_ID,
            selected_publish_node_id=self.phase5.nodes[0].global_id,
            expected_mapping_version=1,
            idempotency_key_hash=HASH_A,
            acknowledgement=ITEM_PUBLISH_ACKNOWLEDGEMENT,
        )
        self.assertIsNotNone(first.response)
        self.assertEqual(conflict.problem.code, "ITEM_PUBLISH_IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.count("NPI Item Publish Request"), 1)
        self.assertEqual(self.count("NPI Item Publish Command Idempotency"), 1)
        self.assertEqual(self.count("NPI Audit Event"), 2)

    def test_stale_mapping_profile_and_profile_authority_create_no_request(self) -> None:
        self.current_mapping = CurrentItemMapping(
            2,
            "ITEM-SANDBOX-0001",
            "7",
            HASH_B,
        )
        stale = self.create(expected_mapping_version=1)
        self.assertEqual(stale.problem.code, "ITEM_PUBLISH_STATE_CONFLICT")
        self.assertEqual(self.count("NPI Item Publish Request"), 0)

        self.documents.clear()
        self.pending.clear()
        self.current_mapping = None
        self.repository = self.new_repository(None)
        missing = self.create()
        self.assertEqual(
            missing.problem.code,
            "ITEM_EXECUTION_PROFILE_UNAVAILABLE",
        )
        self.assertEqual(self.count("NPI Item Publish Request"), 0)

        self.documents.clear()
        self.pending.clear()
        self.repository = self.new_repository(
            self.mock_profile(requester_user_ids=("other@example.invalid",))
        )
        denied = self.create()
        self.assertEqual(
            denied.problem.code,
            "ITEM_PUBLISH_AUTHORITY_UNAVAILABLE",
        )
        self.assertEqual(self.count("NPI Item Publish Request"), 0)

    def test_missing_node_is_opaque_and_divergent_occurrences_are_explicit(self) -> None:
        missing = self.repository.create_item_publish_request(
            PROJECT_ID,
            publish_request_id=PHASE5_REQUEST_ID,
            selected_publish_node_id=UUID(
                "00000000-0000-4000-8000-000000008399"
            ),
            expected_mapping_version=0,
            idempotency_key_hash=HASH_A,
            acknowledgement=ITEM_PUBLISH_ACKNOWLEDGEMENT,
        )
        self.assertEqual(
            missing.problem.code,
            "ITEM_PUBLISH_REQUEST_UNAVAILABLE",
        )
        self.assertEqual(self.count("NPI Item Publish Request"), 0)

        self.documents.clear()
        self.pending.clear()
        self.phase5 = self.phase5_request(divergent=True)
        divergent = self.create()
        self.assertEqual(
            divergent.problem.code,
            "SOURCE_ENGINEERING_ITEM_CONFLICT",
        )
        self.assertEqual(self.count("NPI Item Publish Request"), 0)
        self.assertEqual(self.count("NPI Outbox Message"), 0)

    def test_missing_phase5_source_is_audited_without_request_or_outbox(self) -> None:
        self.repository._phase5_request_for_project = (
            lambda _project, _request_id, lock: None
        )
        outcome = self.create()
        self.assertEqual(
            outcome.problem.code,
            "ITEM_PUBLISH_REQUEST_UNAVAILABLE",
        )
        self.assertEqual(self.count("NPI Audit Event"), 1)
        self.assertEqual(self.count("NPI Item Publish Request"), 0)
        self.assertEqual(self.count("NPI Outbox Message"), 0)

    def test_partial_insert_failure_rolls_back_every_command_row(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        self.fail_on = "NPI Outbox Message"
        with self.assertRaisesRegex(RuntimeError, "injected"):
            self.create()
        self.assertEqual(self.count("NPI Item Publish Request"), 1)
        self.frappe.db.rollback()
        for doctype in (
            "NPI Item Publish Request",
            "NPI Outbox Message",
            "NPI Item Publish Command Idempotency",
            "NPI Audit Event",
        ):
            self.assertEqual(self.count(doctype), 0)

    def test_list_and_detail_are_project_contained_and_exactly_filterable(self) -> None:
        outcome = self.create()
        self.frappe.db.commit()
        listed = self.repository.list_item_publish_requests(
            PROJECT_ID,
            publish_request_id=PHASE5_REQUEST_ID,
            selected_publish_node_id=self.phase5.nodes[0].global_id,
        )
        self.assertEqual(len(listed["items"]), 1)
        self.assertEqual(listed["items"][0]["globalId"], outcome.response["requestGlobalId"])
        self.assertEqual(
            listed["mappingExpectation"],
            {
                "mappingVersion": 0,
                "formalItemCode": None,
                "targetVersion": None,
                "observationHash": None,
            },
        )
        self.current_mapping = CurrentItemMapping(2, "ITEM-SANDBOX-0001", "7", HASH_B)
        preview = self.repository.list_item_publish_requests(
            PROJECT_ID,
            publish_request_id=PHASE5_REQUEST_ID,
            selected_publish_node_id=self.phase5.nodes[0].global_id,
        )
        self.assertEqual(preview["mappingExpectation"]["mappingVersion"], 2)
        self.assertEqual(preview["mappingExpectation"]["formalItemCode"], "ITEM-SANDBOX-0001")
        self.current_mapping = None
        detail = self.repository.item_publish_request_detail(
            PROJECT_ID,
            UUID(outcome.response["requestGlobalId"]),
        )
        self.assertEqual(detail, outcome.response)

        self.project.global_id = str(
            UUID("00000000-0000-4000-8000-000000008398")
        )
        hidden = self.repository.item_publish_request_detail(
            UUID(self.project.global_id),
            UUID(outcome.response["requestGlobalId"]),
        )
        self.assertIsNone(hidden)

    def test_invalid_current_profile_does_not_hide_retained_request_history(self) -> None:
        outcome = self.create()
        self.frappe.db.commit()

        def invalid_profile(_tenant: str, _project: UUID):
            raise RuntimeError("invalid current profile")

        self.repository._profile_resolver = invalid_profile
        listed = self.repository.list_item_publish_requests(PROJECT_ID)
        self.assertEqual(len(listed["items"]), 1)
        self.assertIsNone(listed["executionProfile"])
        self.assertFalse(listed["permissions"]["canExecute"])
        detail = self.repository.item_publish_request_detail(
            PROJECT_ID,
            UUID(outcome.response["requestGlobalId"]),
        )
        self.assertEqual(
            detail["requestGlobalId"],
            outcome.response["requestGlobalId"],
        )
        self.assertFalse(detail["permissions"]["canExecute"])

    def test_detail_exposes_only_verified_attempt_and_result_history(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        outcome = self.create()
        self.frappe.db.commit()
        request = self.only("NPI Item Publish Request")
        attempt_id = UUID("00000000-0000-4000-8000-000000008321")
        result_id = UUID("00000000-0000-4000-8000-000000008322")
        attempt_snapshot = {
            "schemaVersion": 1,
            "globalId": str(attempt_id),
            "requestGlobalId": str(request.global_id),
            "outboxEventId": str(request.outbox_event_id),
            "attemptNumber": 1,
            "claimToken": "private-claim-token",
            "targetIdempotencyKeyHash": HASH_B,
            "sourceHash": str(request.source_hash),
            "profileId": str(request.profile_id),
            "profileVersion": int(request.profile_version),
            "state": "synthetic_verified",
            "adapterBoundaryCrossed": False,
            "connectTimeoutSeconds": None,
            "readTimeoutSeconds": None,
            "requestSnapshotHash": HASH_C,
            "transportDisposition": "synthetic_verified",
            "targetStatusCode": None,
            "responseHash": HASH_D,
            "faultKind": "none",
            "reconciliationRequired": False,
            "safeErrorCode": None,
            "startedAt": "2026-08-16T14:00:00Z",
            "finishedAt": "2026-08-16T14:00:01Z",
        }
        self.documents["NPI Item Publish Attempt"] = {
            str(attempt_id): AttrDict(
                global_id=str(attempt_id),
                request_global_id=str(request.global_id),
                outbox_event_id=str(request.outbox_event_id),
                attempt_number=1,
                source_hash=str(request.source_hash),
                attempt_snapshot=attempt_snapshot,
                attempt_hash=self.module.canonical_hash(attempt_snapshot),
            )
        }
        result_snapshot = {
            "schemaVersion": 1,
            "globalId": str(result_id),
            "requestGlobalId": str(request.global_id),
            "outboxEventId": str(request.outbox_event_id),
            "attemptGlobalId": str(attempt_id),
            "attemptNumber": 1,
            "idempotencyKeyHash": HASH_B,
            "sourceHash": str(request.source_hash),
            "expectedTargetVersion": None,
            "state": "synthetic_verified",
            "authority": "synthetic",
            "responseAuthenticated": False,
            "responseHash": HASH_D,
            "formalItemCode": None,
            "targetVersion": None,
            "faultKind": "none",
            "observedAt": "2026-08-16T14:00:01Z",
        }
        self.documents["NPI Item Publish Result"] = {
            str(result_id): AttrDict(
                global_id=str(result_id),
                request_global_id=str(request.global_id),
                outbox_event_id=str(request.outbox_event_id),
                attempt_global_id=str(attempt_id),
                attempt_number=1,
                source_hash=str(request.source_hash),
                result_snapshot=result_snapshot,
                result_hash=self.module.canonical_hash(result_snapshot),
            )
        }
        request.result_global_id = str(result_id)
        request.state = "synthetic_verified"

        detail = self.repository.item_publish_request_detail(
            PROJECT_ID,
            UUID(outcome.response["requestGlobalId"]),
        )

        self.assertEqual(detail["attempts"][0]["attemptNumber"], 1)
        self.assertNotIn("claimToken", detail["attempts"][0])
        self.assertEqual(detail["result"]["authority"], "synthetic")
        self.assertIsNone(detail["result"]["formalItemCode"])

        self.only("NPI Item Publish Attempt").attempt_hash = HASH_A
        with self.assertRaisesRegex(RuntimeError, "attempt is invalid"):
            self.repository.item_publish_request_detail(
                PROJECT_ID,
                UUID(outcome.response["requestGlobalId"]),
            )

    def test_source_revalidation_and_atomic_write_order_are_explicit(self) -> None:
        path = (
            ROOT
            / "apps/npi_integration/npi_integration/item_publish/frappe_repository.py"
        )
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        def function(name: str) -> str:
            matches = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name
            ]
            self.assertEqual(len(matches), 1, name)
            value = ast.get_source_segment(source, matches[0])
            self.assertIsNotNone(value)
            return value

        exact = function("_exact_released_phase5_request")
        for marker in (
            "self._request_value(project, row)",
            "PublishTargetMode.MOCK",
            "PublishRequestState.VALIDATED",
            "self._load_exact_publish_policy(",
            "self._released_context(",
            "self._approval_evidence_ids(",
            "revision.snapshot_hash",
            "release.event_hash",
            "evidence.approval_evidence_ids",
        ):
            self.assertIn(marker, exact)
        create = function("create_item_publish_request")
        order = (
            "self._locked_command_project(project_id)",
            "self._idempotency_receipt(scope_key)",
            "require_mutable_project(project)",
            "self._phase5_request_for_project(",
            "self._exact_released_phase5_request(",
            "self._item_source(",
            "self._current_mapping_for_source(project, source, lock=True)",
            "self._required_profile(project)",
            "value = create_item_publish_request(",
            "with item_request_transaction_write()",
            "self._insert_item_request(",
            "self._insert_outbox(",
            "self._append_audit(",
            "self._insert_idempotency_receipt(",
        )
        positions = [create.index(marker) for marker in order]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("commit()", create)
        lowered = source.casefold()
        for forbidden in (
            "requests.",
            "httpx.",
            "urllib.request",
            "socket.",
            "frappe.db." + "sql",
            "ignore_" + "permissions",
        ):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
