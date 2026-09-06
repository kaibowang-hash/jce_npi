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
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_core.foundation.security import Principal
from npi_integration.item_publish.config import ItemExecutionProfile
from npi_integration.item_publish.domain import (
    ITEM_PUBLISH_ACKNOWLEDGEMENT,
    ITEM_PUBLISH_OPERATION,
    CurrentItemMapping,
    ItemExecutionProfileReference,
    ItemMappingExpectation,
    ItemTargetMode,
    canonical_hash,
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

    def insert(self, *, ignore_permissions: bool = False):
        doctype = str(self.doctype)
        required_flag = {
            "NPI Item Publish Request": "npi_item_publish_request_write",
            "NPI Item Publish Command Idempotency": (
                "npi_item_publish_idempotency_write"
            ),
            "NPI Outbox Message": "npi_item_outbox_write",
            "NPI Item Publish Stream Guard": (
                "npi_item_publish_stream_guard_write"
            ),
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
            "NPI Item Publish Stream Guard": "source_stream_key_hash",
            "NPI Audit Event": "event_id",
        }[doctype]
        self.name = str(self[identity_field])
        bucket = self._owner.documents.setdefault(doctype, {})
        if self.name in bucket:
            raise self._owner.frappe.DuplicateEntryError()
        self.owner = self._owner.frappe.session.user
        self.modified_by = self._owner.frappe.session.user
        bucket[self.name] = self
        self._owner.pending.append((doctype, self.name))
        self._owner.events.append(f"insert:{doctype}")
        return self

    def save(self, *, ignore_permissions: bool = False):
        doctype = str(self.doctype)
        if doctype != "NPI Item Publish Stream Guard":
            raise AssertionError(f"unexpected save for {doctype}")
        if not getattr(
            self._owner.frappe.flags,
            "npi_item_publish_stream_guard_write",
            False,
        ):
            raise AssertionError("missing controlled stream guard write flag")
        if self.name not in self._owner.documents.get(doctype, {}):
            raise AssertionError("stream guard must exist before save")
        self.modified_by = self._owner.frappe.session.user
        self._owner.events.append(f"save:{doctype}")
        return self


class FakeDatabase:
    def __init__(self, owner: "Phase8ItemPublishRepositoryTest") -> None:
        self.owner = owner
        self.savepoints: dict[str, int] = {}

    def get_value(
        self,
        doctype: str,
        filters: object,
        fieldname: str,
        **_kwargs: Any,
    ) -> object | None:
        if doctype == "User" and isinstance(fieldname, list):
            users = getattr(
                self.owner,
                "users",
                {
                    "publisher@example.invalid": (1, "System User"),
                    "item-worker@example.invalid": (1, "System User"),
                },
            )
            enabled, user_type = users.get(str(filters), (0, None))
            value = {"enabled": enabled, "user_type": user_type}
            return AttrDict(value) if _kwargs.get("as_dict") else value
        if doctype == "NPI Item Mapping Head" and fieldname == "name":
            for row in self.owner.documents.get(doctype, {}).values():
                if all(row.get(key) == value for key, value in dict(filters).items()):
                    return row.name
            return None
        if doctype == "NPI Item Publish Stream Guard" and fieldname == "name":
            for row in self.owner.documents.get(doctype, {}).values():
                if all(row.get(key) == value for key, value in dict(filters).items()):
                    return row.name
            return None
        raise AssertionError((doctype, filters, fieldname))

    def commit(self) -> None:
        self.owner.events.append("commit")
        self.owner.pending.clear()

    def savepoint(self, name: str) -> None:
        self.savepoints[name] = len(self.owner.pending)
        self.owner.events.append(f"savepoint:{name}")

    def rollback(self, save_point: str | None = None) -> None:
        self.owner.events.append("rollback")
        start = 0 if save_point is None else self.savepoints.get(save_point, 0)
        pending = self.owner.pending[start:]
        for doctype, name in reversed(pending):
            self.owner.documents.get(doctype, {}).pop(name, None)
        del self.owner.pending[start:]
        if save_point is not None:
            self.savepoints.pop(save_point, None)


class Phase8ItemPublishRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision",
        "npi_core.documents.frappe_repository",
        "npi_core.ebom.frappe_repository",
        "npi_integration.publish_request.frappe_repository",
        "npi_integration.item_publish.diagnostics",
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
        self.users = {
            "publisher@example.invalid": (1, "System User"),
            "item-worker@example.invalid": (1, "System User"),
        }
        self.frappe.get_roles = lambda actor: (
            ["NPI API User"] if actor in self.users else []
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

    @staticmethod
    def sandbox_profile() -> ItemExecutionProfile:
        return ItemExecutionProfile(
            profile_id="item-sandbox-v1",
            profile_version=1,
            tenant_id="TENANT-A",
            project_global_id=str(PROJECT_ID),
            target_mode=ItemTargetMode.SANDBOX,
            environment_code="sandbox",
            requester_user_ids=("publisher@example.invalid",),
            service_actor_user_id="item-worker@example.invalid",
            allowed_operations=(ITEM_PUBLISH_OPERATION,),
            adapter_resolver="npi_integration.item_publish.runtime_fixture.synthetic_adapter",
            base_url="https://sandbox.invalid",
            allowed_hostnames=("sandbox.invalid",),
            secret_reference="secret/item-sandbox",
            response_authentication="hmac-sha256-v1",
            connect_timeout_seconds=5,
            read_timeout_seconds=5,
            non_production_attested=True,
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
                    "actor": repository.actor,
                    "trace_id": repository.trace_id,
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
        self.assertFalse(request.flags.ignore_links)
        self.assertEqual(outbox.event_type, "npi.item_publish_request.ready")
        self.assertEqual(outbox.operation, "publish_released_item")
        self.assertEqual(outbox.state, "pending")
        self.assertFalse(bool(outbox.adapter_boundary_crossed))
        self.assertEqual(outbox.attempt_count, 0)
        self.assertNotIn("adapter_resolver", repr(outbox.payload))
        self.assertNotIn("service_actor_user_id", repr(outbox.payload))

    def test_nonmock_rows_bind_one_semantic_target_effect_and_service_actor(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        outcome = self.create()
        self.assertIsNone(outcome.problem)
        request = self.only("NPI Item Publish Request")
        outbox = self.only("NPI Outbox Message")
        self.assertEqual(
            request.target_idempotency_key_hash,
            request.semantic_effect_hash,
        )
        self.assertEqual(request.service_actor_user_id, "item-worker@example.invalid")
        self.assertEqual(request.owner, "publisher@example.invalid")
        self.assertEqual(request.modified_by, "publisher@example.invalid")
        self.assertEqual(
            outbox.target_idempotency_key_hash,
            request.target_idempotency_key_hash,
        )
        self.assertEqual(outbox.semantic_effect_hash, request.semantic_effect_hash)
        self.assertEqual(outbox.service_actor_user_id, request.service_actor_user_id)
        self.assertEqual(outbox.owner, "publisher@example.invalid")
        self.assertEqual(outbox.modified_by, "publisher@example.invalid")
        self.assertEqual(
            outbox.payload["target_idempotency_key_hash"],
            request.target_idempotency_key_hash,
        )
        self.assertNotIn("service_actor_user_id", repr(outcome.response))
        self.assertNotIn("serviceActorUserId", repr(outcome.response))
        audit_rows = tuple(self.documents["NPI Audit Event"].values())
        self.assertTrue(audit_rows)
        self.assertTrue(all(row.actor == "publisher@example.invalid" for row in audit_rows))
        self.assertTrue(all(row.owner == "publisher@example.invalid" for row in audit_rows))

    def test_selected_occurrence_filter_matches_any_sibling_occurrence(self) -> None:
        outcome = self.create()
        self.frappe.db.commit()
        sibling = self.phase5.nodes[1].global_id
        listed = self.repository.list_item_publish_requests(
            PROJECT_ID,
            selected_publish_node_id=sibling,
        )
        self.assertEqual(
            [item["globalId"] for item in listed["items"]],
            [outcome.response["requestGlobalId"]],
        )

    def test_stream_guard_problem_is_closed_for_active_retained_and_legacy_rows(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        outcome = self.create()
        request = self.only("NPI Item Publish Request")
        value = self.repository._item_request_value(self.project, request)
        helper = self.module._stream_guard_problem

        active = AttrDict(
            active_request_global_id=str(value.global_id),
            active_target_idempotency_key_hash=value.target_idempotency_key_hash,
            active_state="processing",
            last_request_global_id=None,
            last_target_idempotency_key_hash=None,
            last_state=None,
            blocked_reason_code=None,
        )
        self.assertEqual(helper(active, value).code, "ITEM_PUBLISH_STREAM_ACTIVE")

        retained = AttrDict(
            active_request_global_id=None,
            active_target_idempotency_key_hash=None,
            active_state=None,
            last_request_global_id=str(value.global_id),
            last_target_idempotency_key_hash=value.target_idempotency_key_hash,
            last_state="succeeded",
            blocked_reason_code=None,
        )
        self.assertEqual(
            helper(retained, value).code,
            "ITEM_PUBLISH_EFFECT_RETAINED",
        )

        legacy = AttrDict(
            active_request_global_id=None,
            active_target_idempotency_key_hash=None,
            active_state=None,
            last_request_global_id=str(value.global_id),
            last_target_idempotency_key_hash=value.target_idempotency_key_hash,
            last_state="failed_retryable",
            blocked_reason_code=None,
        )
        self.assertEqual(
            helper(legacy, value).code,
            "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED",
        )

    def test_missing_guard_scans_zero_one_or_two_rows_without_fabrication(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        source = self.repository._item_source(self.project, self.phase5, self.phase5.nodes[0].global_id)
        original_get_all = getattr(self.frappe, "get_all", None)
        original_get_doc = self.frappe.get_doc
        try:
            calls: list[dict[str, object]] = []

            def get_all(_doctype, **kwargs):
                calls.append(kwargs)
                return []

            self.frappe.get_all = get_all
            empty = self.module._legacy_stream_guard_state(source)
            self.assertIsNone(empty["blocked_reason_code"])
            self.assertIsNone(empty["active_request_global_id"])

            legacy = AttrDict(
                name="legacy-request",
                global_id="00000000-0000-4000-8000-000000008399",
                source_stream_key_hash=source.stream_key_hash,
                target_mode="sandbox",
                dispatch_allowed=1,
                state="queued",
                target_idempotency_key_hash=None,
                service_actor_user_id=None,
                semantic_source_effect_hash=None,
                semantic_effect_hash=None,
            )
            self.frappe.get_all = lambda _doctype, **kwargs: [{"name": legacy.name}]
            self.documents["NPI Item Publish Request"] = {legacy.name: legacy}
            blocked = self.module._legacy_stream_guard_state(source)
            self.assertEqual(
                blocked["blocked_reason_code"],
                "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED",
            )
            self.assertIsNone(blocked["active_target_idempotency_key_hash"])
            self.assertIsNone(blocked["last_target_idempotency_key_hash"])

            complete = AttrDict(
                legacy,
                global_id="00000000-0000-4000-8000-000000008400",
                name="new-request",
                tenant_id=source.tenant_id,
                project_global_id=str(source.project_global_id),
                engineering_item_id=source.engineering_item_id,
                target_idempotency_key_hash="a" * 64,
                service_actor_user_id="item-worker@example.invalid",
                semantic_source_effect_hash=source.semantic_source_effect_hash,
                semantic_effect_hash="a" * 64,
                state="processing",
            )
            self.frappe.get_all = lambda _doctype, **kwargs: [{"name": complete.name}]
            self.documents["NPI Item Publish Request"] = {complete.name: complete}
            blocked_complete = self.module._legacy_stream_guard_state(source)
            self.assertEqual(
                blocked_complete["blocked_reason_code"],
                "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED",
            )
            self.assertIsNone(blocked_complete["active_request_global_id"])
            self.assertIsNone(
                blocked_complete["active_target_idempotency_key_hash"]
            )

            self.frappe.get_all = lambda _doctype, **kwargs: [
                {"name": complete.name},
                {"name": legacy.name},
            ]
            ambiguous = self.module._legacy_stream_guard_state(source)
            self.assertEqual(
                ambiguous["blocked_reason_code"],
                "ITEM_PUBLISH_STREAM_RECONCILIATION_REQUIRED",
            )
            self.assertEqual(calls, [{
                "filters": {"source_stream_key_hash": source.stream_key_hash},
                "fields": ["name"],
                "order_by": "created_at asc, name asc",
                "limit_page_length": 2,
            }])
        finally:
            if original_get_all is None:
                try:
                    del self.frappe.get_all
                except AttributeError:
                    pass
            else:
                self.frappe.get_all = original_get_all
            self.frappe.get_doc = original_get_doc

    def test_legacy_query_diagnostic_stages_are_unique_and_read_only(self) -> None:
        source = (
            ROOT
            / "apps/npi_integration/npi_integration/item_publish/frappe_repository.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        codes = {
            value.value
            for value in ast.walk(tree)
            if isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and value.value.startswith("P803_LEGACY_QUERY_")
        }
        self.assertEqual(
            codes,
            {
                "P803_LEGACY_QUERY_PROJECT",
                "P803_LEGACY_QUERY_PROFILE",
                "P803_LEGACY_QUERY_ROWS",
                "P803_LEGACY_QUERY_ROW_CLASSIFY",
                "P803_LEGACY_QUERY_BINDING_STATE",
                "P803_LEGACY_QUERY_STRICT_LEGACY",
                "P803_LEGACY_QUERY_LEGACY_PROJECT",
                "P803_LEGACY_QUERY_CURRENT_PROJECT",
                "P803_LEGACY_QUERY_MAPPING_EXPECTATION",
            },
        )
        for code in codes:
            self.assertEqual(source.count(f'"{code}"'), 1)
        diagnostic_lines = "\n".join(
            line for line in source.splitlines() if "P803_LEGACY_QUERY_" in line
        )
        for forbidden in ("insert(", "save(", "commit(", "rollback(", "delete("):
            self.assertNotIn(forbidden, diagnostic_lines)

    def test_legacy_classifier_records_innermost_failure_without_writes(self) -> None:
        diagnostics = importlib.import_module(
            "npi_integration.item_publish.diagnostics"
        )
        cases = (
            (
                "partial",
                AttrDict(
                    target_mode="sandbox",
                    service_actor_user_id="item-worker@example.invalid",
                    target_idempotency_key_hash=None,
                    semantic_source_effect_hash=None,
                    semantic_effect_hash=None,
                ),
                "P803_LEGACY_QUERY_BINDING_STATE",
            ),
            (
                "strict-invalid",
                AttrDict(
                    target_mode="sandbox",
                    service_actor_user_id=None,
                    target_idempotency_key_hash=None,
                    semantic_source_effect_hash=None,
                    semantic_effect_hash=None,
                    schema_version=0,
                ),
                "P803_LEGACY_QUERY_STRICT_LEGACY",
            ),
        )
        for label, row, expected_code in cases:
            with self.subTest(context=label):
                repository = self.new_repository(self.synthetic_profile())
                repository._bounded_documents = lambda *_args, **_kwargs: [row]
                records: list[dict[str, object]] = []
                exception_class = (
                    self.module.ItemPublishStreamReconciliationRequired
                )
                original = exception_class()
                original.args = ("private actor payload /tmp/private",)
                before_events = list(self.events)
                setattr(
                    self.frappe.flags,
                    "npi_p803_item_legacy_query_diagnostic",
                    {"trace_id": "trace-" + "d" * 32, "recorded": False},
                )
                with patch(
                    "npi_core.api.record_safe_diagnostic",
                    side_effect=lambda **values: records.append(values),
                ), patch.object(
                    self.module,
                    "ItemPublishStreamReconciliationRequired",
                    return_value=original,
                ), self.assertRaises(exception_class) as failure:
                    repository.list_item_publish_requests(PROJECT_ID)
                self.assertIs(failure.exception, original)
                self.assertEqual(self.events, before_events)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["code"], expected_code)
                self.assertEqual(
                    records[0]["exception_type"],
                    type(original).__name__,
                )
                rendered = repr(records)
                self.assertNotIn("P803_LEGACY_QUERY_ROW_CLASSIFY", rendered)
                self.assertNotIn(str(original), rendered)
                self.assertNotIn("item-worker@example.invalid", rendered)
                delattr(
                    self.frappe.flags,
                    "npi_p803_item_legacy_query_diagnostic",
                )

    def test_legacy_nonmock_list_and_detail_are_read_only_projection(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        source = self.repository._item_source(self.project, self.phase5, self.phase5.nodes[0].global_id)
        evidence = self.repository._item_released_evidence(self.phase5)
        old = AttrDict(
            doctype="NPI Item Publish Request",
            name=str(PHASE5_REQUEST_ID),
            global_id=str(PHASE5_REQUEST_ID),
            schema_version=1,
            api_version="npi.erp-item-publish.v1",
            operation="publish_released_item",
            tenant_id="TENANT-A",
            project_global_id=str(PROJECT_ID),
            source_stream_key_hash=source.stream_key_hash,
            engineering_item_id=source.engineering_item_id,
            selected_publish_node_global_id=str(source.selected_publish_node_global_id),
            source_snapshot=source.canonical_mapping(),
            source_hash=source.source_hash,
            released_evidence_snapshot=evidence.canonical_mapping(),
            released_evidence_hash=canonical_hash(evidence.canonical_mapping()),
            profile_id="item-sandbox-v1",
            profile_version=1,
            profile_snapshot_hash=HASH_C,
            target_mode="sandbox",
            environment_code="sandbox",
            intent="create_item",
            expected_mapping_version=0,
            expected_formal_item_code=None,
            expected_target_version=None,
            expected_mapping_observation_hash=None,
            state="queued",
            dispatch_allowed=1,
            outbox_event_id="00000000-0000-4000-8000-000000008321",
            result_global_id=None,
            actor_user_id="publisher@example.invalid",
            request_id=str(REQUEST_ID),
            trace_id="trace-legacy-item",
            idempotency_key_hash=HASH_A,
            payload_hash=HASH_B,
            optimistic_version=1,
            created_at=NOW,
            updated_at=NOW,
            target_idempotency_key_hash=None,
            service_actor_user_id=None,
            semantic_source_effect_hash=None,
            semantic_effect_hash=None,
        )
        legacy_profile = ItemExecutionProfileReference(
            profile_id="item-sandbox-v1",
            profile_version=1,
            target_mode=ItemTargetMode.SANDBOX,
            environment_code="sandbox",
            snapshot_hash=HASH_C,
        )
        legacy_expectation = ItemMappingExpectation(0, None, None, None)
        old.payload_hash = canonical_hash(
            {
                "schemaVersion": 1,
                "apiVersion": "npi.erp-item-publish.v1",
                "operation": "publish_released_item",
                "source": source.canonical_mapping(),
                "releasedEvidence": evidence.canonical_mapping(),
                "profile": legacy_profile.canonical_mapping(),
                "mappingExpectation": legacy_expectation.canonical_mapping(),
                "intent": legacy_expectation.intent.value,
            }
        )
        legacy_payload = {
            "schema_version": 1,
            "api_version": "npi.erp-item-publish.v1",
            "operation": "publish_released_item",
            "request_global_id": str(PHASE5_REQUEST_ID),
            "request_payload_hash": old.payload_hash,
            "project_global_id": str(PROJECT_ID),
            "source_stream_key_hash": source.stream_key_hash,
            "source_hash": source.source_hash,
            "intent": legacy_expectation.intent.value,
            "expected_mapping_version": 0,
            "expected_target_version": None,
            "target_mode": "sandbox",
            "profile_id": legacy_profile.profile_id,
            "profile_version": legacy_profile.profile_version,
            "profile_snapshot_hash": legacy_profile.snapshot_hash,
            "idempotency_key_hash": HASH_A,
        }
        legacy_event_snapshot = {
            "schemaVersion": 1,
            "eventId": "00000000-0000-4000-8000-000000008321",
            "eventType": "npi.item_publish_request.ready",
            "globalId": str(PHASE5_REQUEST_ID),
            "objectVersion": 1,
            "tenantId": "TENANT-A",
            "projectGlobalId": str(PROJECT_ID),
            "requestGlobalId": str(PHASE5_REQUEST_ID),
            "operation": "publish_released_item",
            "profileId": legacy_profile.profile_id,
            "profileVersion": legacy_profile.profile_version,
            "profileSnapshotHash": legacy_profile.snapshot_hash,
            "sourceStreamKeyHash": source.stream_key_hash,
            "sourceHash": source.source_hash,
            "expectedMappingVersion": 0,
            "expectedTargetVersion": None,
            "actorUserId": "publisher@example.invalid",
            "requestId": str(REQUEST_ID),
            "traceId": "trace-legacy-item",
            "idempotencyKeyHash": HASH_A,
            "payloadHash": canonical_hash(legacy_payload),
        }
        old_outbox = AttrDict(
            doctype="NPI Outbox Message",
            name="00000000-0000-4000-8000-000000008321",
            event_id="00000000-0000-4000-8000-000000008321",
            event_type="npi.item_publish_request.ready",
            global_id=str(PHASE5_REQUEST_ID),
            object_version=1,
            trace_id="trace-legacy-item",
            payload_hash=canonical_hash(legacy_payload),
            payload=legacy_payload,
            state="pending",
            attempt_count=0,
            schema_version=1,
            operation="publish_released_item",
            tenant_id="TENANT-A",
            project_global_id=str(PROJECT_ID),
            request_global_id=str(PHASE5_REQUEST_ID),
            profile_id=legacy_profile.profile_id,
            profile_version=legacy_profile.profile_version,
            profile_snapshot_hash=legacy_profile.snapshot_hash,
            source_stream_key_hash=source.stream_key_hash,
            source_hash=source.source_hash,
            expected_mapping_version=0,
            expected_target_version=None,
            actor_user_id="publisher@example.invalid",
            request_id=str(REQUEST_ID),
            idempotency_key_hash=HASH_A,
            event_snapshot_hash=canonical_hash(legacy_event_snapshot),
            disposition="ready",
            adapter_boundary_crossed=0,
            claim_token=None,
            claimed_at=None,
            lease_expires_at=None,
            last_attempt_global_id=None,
            result_global_id=None,
            last_error_code=None,
            last_error_at=None,
            target_idempotency_key_hash=None,
            service_actor_user_id=None,
            semantic_source_effect_hash=None,
            semantic_effect_hash=None,
        )
        self.documents["NPI Outbox Message"] = {old_outbox.name: old_outbox}
        self.documents["NPI Item Publish Request"] = {old.name: old}
        original_value = self.module.ItemPublishRequest
        self.module.ItemPublishRequest = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy projection constructed executable request")
        )
        try:
            listed = self.repository.list_item_publish_requests(
                PROJECT_ID,
                selected_publish_node_id=self.phase5.nodes[1].global_id,
            )
            self.assertEqual(len(listed["items"]), 1)
            self.assertFalse(listed["items"][0]["dispatchAllowed"])
            self.assertTrue(listed["items"][0]["legacyReadOnly"])
            self.assertFalse(listed["items"][0]["current"])
            self.assertNotIn("targetIdempotencyKeyHash", repr(listed["items"][0]))
            detail = self.repository.item_publish_request_detail(
                PROJECT_ID,
                PHASE5_REQUEST_ID,
            )
            self.assertFalse(detail["permissions"]["canExecute"])
            self.assertTrue(detail["request"]["legacyReadOnly"])
            self.assertFalse(detail["request"]["current"])
            self.assertIsNone(detail["currentMapping"])
            self.assertEqual(detail["attempts"], [])
            self.assertIsNone(detail["result"])
            self.assertIsNone(old.target_idempotency_key_hash)
            self.assertIsNone(old.service_actor_user_id)

            for field, invalid_value in (
                ("state", "succeeded"),
                ("state", "processing"),
                ("optimistic_version", 2),
                ("updated_at", NOW.replace(second=1)),
            ):
                original_value = getattr(old, field)
                setattr(old, field, invalid_value)
                try:
                    with self.assertRaises(
                        self.module.ItemPublishStreamReconciliationRequired
                    ):
                        self.module._is_legacy_nonmock_request_row(old)
                    with self.assertRaises(
                        self.module.ItemPublishStreamReconciliationRequired
                    ):
                        self.repository.list_item_publish_requests(
                            PROJECT_ID,
                            selected_publish_node_id=self.phase5.nodes[1].global_id,
                        )
                    with self.assertRaises(
                        self.module.ItemPublishStreamReconciliationRequired
                    ):
                        self.repository.item_publish_request_detail(
                            PROJECT_ID,
                            PHASE5_REQUEST_ID,
                        )
                    self.assertEqual(self.events, [])
                    self.assertIsNone(old.target_idempotency_key_hash)
                    self.assertIsNone(old.service_actor_user_id)
                finally:
                    setattr(old, field, original_value)

            self.assertTrue(self.module._is_legacy_nonmock_request_row(old))
            old_outbox.trace_id = "trace-legacy-item-mismatch"
            self.assertFalse(self.module._strict_legacy_request_row(old))
            with self.assertRaises(
                self.module.ItemPublishStreamReconciliationRequired
            ):
                self.module._is_legacy_nonmock_request_row(old)
            old_outbox.trace_id = old.trace_id
            self.assertTrue(self.module._strict_legacy_request_row(old))
            old.target_idempotency_key_hash = HASH_A
            with self.assertRaises(
                self.module.ItemPublishStreamReconciliationRequired
            ):
                self.module._is_legacy_nonmock_request_row(old)
            old.target_idempotency_key_hash = None
            old.source_hash = HASH_D
            with self.assertRaises(
                self.module.ItemPublishStreamReconciliationRequired
            ):
                self.module._is_legacy_nonmock_request_row(old)
            old.source_hash = source.source_hash
            old.target_idempotency_key_hash = HASH_A
            old.service_actor_user_id = "item-worker@example.invalid"
            old.semantic_source_effect_hash = source.semantic_source_effect_hash
            old.semantic_effect_hash = HASH_A
            self.assertFalse(self.module._is_legacy_nonmock_request_row(old))
        finally:
            self.module.ItemPublishRequest = original_value

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
        self.assertEqual(detail["request"]["legacyReadOnly"], False)
        self.assertEqual(detail["request"]["current"], True)
        expected = dict(outcome.response)
        expected["request"] = dict(expected["request"])
        expected["request"].update(legacyReadOnly=False, current=True)
        self.assertEqual(detail, expected)

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
            "targetIdempotencyKeyHash": str(request.target_idempotency_key_hash),
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
            "idempotencyKeyHash": str(request.target_idempotency_key_hash),
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
                idempotency_key_hash=str(request.target_idempotency_key_hash),
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

    def test_detail_projects_verified_mapping_head_and_observation_provenance(self) -> None:
        self.repository = self.new_repository(self.sandbox_profile())
        outcome = self.create()
        self.frappe.db.commit()
        request = self.only("NPI Item Publish Request")
        request.state = "succeeded"
        request.result_global_id = str(UUID("00000000-0000-4000-8000-000000008323"))
        request.expected_mapping_version = 0
        request.expected_formal_item_code = None
        request.expected_target_version = None
        request.expected_mapping_observation_hash = None
        attempt_id = UUID("00000000-0000-4000-8000-000000008324")
        result_id = UUID(str(request.result_global_id))
        observed_at = "2026-08-16T14:00:02Z"
        result_snapshot = {
            "schemaVersion": 1,
            "globalId": str(result_id),
            "requestGlobalId": str(request.global_id),
            "outboxEventId": str(request.outbox_event_id),
            "attemptGlobalId": str(attempt_id),
            "attemptNumber": 1,
            "idempotencyKeyHash": str(request.target_idempotency_key_hash),
            "sourceHash": str(request.source_hash),
            "expectedTargetVersion": None,
            "state": "succeeded",
            "authority": "authoritative_sandbox",
            "responseAuthenticated": True,
            "responseHash": HASH_D,
            "formalItemCode": "ITEM-SANDBOX-0001",
            "targetVersion": "7",
            "faultKind": "none",
            "observedAt": observed_at,
        }
        result_hash = self.module.canonical_hash(result_snapshot)
        attempt_snapshot = {
            "schemaVersion": 1,
            "globalId": str(attempt_id),
            "requestGlobalId": str(request.global_id),
            "outboxEventId": str(request.outbox_event_id),
            "attemptNumber": 1,
            "claimToken": "00000000-0000-4000-8000-000000008325",
            "targetIdempotencyKeyHash": str(request.target_idempotency_key_hash),
            "sourceHash": str(request.source_hash),
            "profileId": str(request.profile_id),
            "profileVersion": int(request.profile_version),
            "state": "observed_success",
            "adapterBoundaryCrossed": True,
            "connectTimeoutSeconds": 5,
            "readTimeoutSeconds": 5,
            "requestSnapshotHash": HASH_C,
            "transportDisposition": "observed_success",
            "targetStatusCode": 201,
            "responseHash": HASH_D,
            "faultKind": "none",
            "reconciliationRequired": False,
            "safeErrorCode": None,
            "startedAt": "2026-08-16T14:00:01Z",
            "finishedAt": observed_at,
        }
        self.documents["NPI Item Publish Attempt"] = {
            str(attempt_id): AttrDict(
                global_id=str(attempt_id),
                request_global_id=str(request.global_id),
                outbox_event_id=str(request.outbox_event_id),
                attempt_number=1,
                source_hash=str(request.source_hash),
                profile_id=str(request.profile_id),
                profile_version=int(request.profile_version),
                target_idempotency_key_hash=str(request.target_idempotency_key_hash),
                state="observed_success",
                adapter_boundary_crossed=True,
                finished_at=observed_at,
                attempt_snapshot=attempt_snapshot,
                attempt_hash=self.module.canonical_hash(attempt_snapshot),
            )
        }
        self.documents["NPI Item Publish Result"] = {
            str(result_id): AttrDict(
                global_id=str(result_id),
                request_global_id=str(request.global_id),
                outbox_event_id=str(request.outbox_event_id),
                attempt_global_id=str(attempt_id),
                attempt_number=1,
                idempotency_key_hash=str(request.target_idempotency_key_hash),
                source_hash=str(request.source_hash),
                expected_target_version=None,
                observed_at=observed_at,
                result_snapshot=result_snapshot,
                result_hash=result_hash,
            )
        }
        observation_id = UUID("00000000-0000-4000-8000-000000008326")
        observation_snapshot = {
            "schemaVersion": 1,
            "globalId": str(observation_id),
            "tenantId": "TENANT-A",
            "projectGlobalId": str(PROJECT_ID),
            "sourceStreamKeyHash": str(request.source_stream_key_hash),
            "engineeringItemId": str(request.engineering_item_id),
            "mappingVersion": 1,
            "formalItemCode": "ITEM-SANDBOX-0001",
            "targetVersion": "7",
            "requestGlobalId": str(request.global_id),
            "outboxEventId": str(request.outbox_event_id),
            "attemptGlobalId": str(attempt_id),
            "resultGlobalId": str(result_id),
            "profileId": str(request.profile_id),
            "profileVersion": int(request.profile_version),
            "environmentCode": str(request.environment_code),
            "authority": "authoritative_sandbox",
            "disposition": "advanced",
            "previousMappingVersion": 0,
            "previousObservationHash": None,
            "targetResultHash": result_hash,
            "observedAt": observed_at,
        }
        observation_hash = self.module.canonical_hash(observation_snapshot)
        self.documents["NPI Item Mapping Observation"] = {
            str(observation_id): AttrDict(
                global_id=str(observation_id),
                tenant_id="TENANT-A",
                project_global_id=str(PROJECT_ID),
                source_stream_key_hash=str(request.source_stream_key_hash),
                engineering_item_id=str(request.engineering_item_id),
                mapping_version=1,
                formal_item_code="ITEM-SANDBOX-0001",
                target_version="7",
                request_global_id=str(request.global_id),
                outbox_event_id=str(request.outbox_event_id),
                attempt_global_id=str(attempt_id),
                result_global_id=str(result_id),
                profile_id=str(request.profile_id),
                profile_version=int(request.profile_version),
                environment_code=str(request.environment_code),
                authority="authoritative_sandbox",
                disposition="advanced",
                previous_mapping_version=0,
                previous_observation_hash=None,
                target_result_snapshot=result_snapshot,
                target_result_hash=result_hash,
                observation_snapshot=observation_snapshot,
                observation_hash=observation_hash,
                observed_at=observed_at,
            )
        }
        head_id = UUID("00000000-0000-4000-8000-000000008327")
        head_snapshot = {
            "schemaVersion": 1,
            "globalId": str(head_id),
            "tenantId": "TENANT-A",
            "projectGlobalId": str(PROJECT_ID),
            "sourceStreamKeyHash": str(request.source_stream_key_hash),
            "engineeringItemId": str(request.engineering_item_id),
            "mappingVersion": 1,
            "formalItemCode": "ITEM-SANDBOX-0001",
            "targetVersion": "7",
            "currentObservationGlobalId": str(observation_id),
            "currentObservationHash": observation_hash,
            "updatedAt": observed_at,
        }
        self.documents["NPI Item Mapping Head"] = {
            str(head_id): AttrDict(
                name=str(head_id),
                global_id=str(head_id),
                tenant_id="TENANT-A",
                project_global_id=str(PROJECT_ID),
                source_stream_key_hash=str(request.source_stream_key_hash),
                engineering_item_id=str(request.engineering_item_id),
                mapping_version=1,
                formal_item_code="ITEM-SANDBOX-0001",
                target_version="7",
                current_observation=str(observation_id),
                current_observation_hash=observation_hash,
                head_snapshot=head_snapshot,
                head_hash=self.module.canonical_hash(head_snapshot),
                updated_at=observed_at,
            )
        }
        self.repository._current_mapping_for_source = (
            self.module.FrappeItemPublishRepository._current_mapping_for_source.__get__(
                self.repository
            )
        )
        detail = self.repository.item_publish_request_detail(
            PROJECT_ID,
            UUID(outcome.response["requestGlobalId"]),
        )
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["currentMapping"]["head"]["mappingVersion"], 1)
        self.assertEqual(
            detail["currentMapping"]["observation"]["resultGlobalId"],
            str(result_id),
        )
        self.assertNotIn("serviceActorUserId", repr(detail))

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
            "item_request_transaction_write(self.actor) as capability",
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

    def test_guard_active_link_is_saved_only_after_request_and_outbox_inserts(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        original_guard = self.module._locked_stream_guard
        original_set_active = self.module._set_stream_guard_active
        guard = AttrDict(
            active_request_global_id=None,
            active_target_idempotency_key_hash=None,
            active_state=None,
            last_request_global_id=None,
            last_target_idempotency_key_hash=None,
            last_state=None,
            blocked_reason_code=None,
            optimistic_version=1,
        )
        try:
            self.module._locked_stream_guard = lambda *args, **kwargs: guard

            def set_active(*args, **kwargs):
                self.events.append("guard-active")

            self.module._set_stream_guard_active = set_active
            outcome = self.create()
            self.assertIsNone(outcome.problem)
            request_position = self.events.index("insert:NPI Item Publish Request")
            outbox_position = self.events.index("insert:NPI Outbox Message")
            active_position = self.events.index("guard-active")
            self.assertLess(request_position, outbox_position)
            self.assertLess(outbox_position, active_position)
        finally:
            self.module._locked_stream_guard = original_guard
            self.module._set_stream_guard_active = original_set_active

    def test_first_stream_guard_create_and_updates_use_aware_utc_database_time(self) -> None:
        self.repository = self.new_repository(self.synthetic_profile())
        self.frappe.get_meta = lambda _doctype: object()
        self.frappe.get_all = lambda _doctype, **_kwargs: []

        outcome = self.create()

        self.assertIsNone(outcome.problem)
        guard = self.only("NPI Item Publish Stream Guard")
        request = self.only("NPI Item Publish Request")
        self.assertRegex(
            guard.updated_at,
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.]\d{6}$",
        )
        self.assertEqual(guard.active_request_global_id, request.global_id)
        self.assertEqual(
            guard.active_target_idempotency_key_hash,
            request.target_idempotency_key_hash,
        )
        self.assertEqual(guard.active_state, "queued")

        offset_now = datetime.fromisoformat("2026-08-16T21:00:00+07:00")
        value = self.repository._item_request_value(self.project, request)
        with self.module.item_request_transaction_write(
            self.repository.actor
        ) as capability:
            self.module._set_stream_guard_active(
                guard,
                value,
                now=offset_now,
                capability=capability,
            )
            self.assertEqual(guard.updated_at, "2026-08-16 14:00:00.000000")
            self.module._clear_stream_guard_active(
                guard,
                request_global_id=value.global_id,
                target_idempotency_key_hash=value.target_idempotency_key_hash,
                state="synthetic_verified",
                now=offset_now,
                capability=capability,
            )
        self.assertEqual(guard.updated_at, "2026-08-16 14:00:00.000000")
        self.assertIsNone(guard.active_request_global_id)
        self.assertEqual(guard.last_request_global_id, str(value.global_id))
        self.assertEqual(guard.last_state, "synthetic_verified")
        self.assertGreaterEqual(
            self.events.count("save:NPI Item Publish Stream Guard"),
            3,
        )
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self.module._aware_utc(datetime(2026, 8, 16, 14, 0))


if __name__ == "__main__":
    unittest.main()
