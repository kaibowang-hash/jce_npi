from __future__ import annotations

import ast
import json
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.mbom_publish.domain import (  # noqa: E402
    ItemMappingReadiness,
    ItemReadinessDisposition,
    MbomExecutionProfileReference,
    MbomMappingExpectation,
    MbomPublishRequestState,
    MbomResultAuthority,
    MbomTargetMode,
    MbomTargetSubmissionState,
    canonical_hash,
    create_mbom_publish_request,
)


def uid(value: int) -> UUID:
    return UUID(int=value)


def phase5_request() -> object:
    def node(value: int, key: str, parent: str | None, engineering_id: str):
        line = types.SimpleNamespace(
            global_id=uid(value),
            line_key=key,
            parent_line_key=parent,
            engineering_item_id=engineering_id,
            quantity="1.000",
            engineering_uom="Nos",
            alternate_for_line_key=None,
            alternate_group_key=None,
            effectivity_start="A",
            effectivity_end=None,
            attributes=(("material", "PA66"),),
            line_hash=f"{value:064x}",
        )
        return types.SimpleNamespace(global_id=uid(value + 100), line=line)

    return types.SimpleNamespace(
        global_id=uid(3),
        payload_hash="3" * 64,
        policy=types.SimpleNamespace(
            global_id=uid(4),
            version=2,
            snapshot_hash="4" * 64,
        ),
        evidence=types.SimpleNamespace(
            ebom_global_id=uid(2),
            revision_global_id=uid(5),
            revision_number=3,
            revision_snapshot_hash="5" * 64,
            lifecycle_version=4,
            release_event_global_id=uid(6),
            release_event_hash="6" * 64,
            approval_evidence_ids=(uid(6), uid(7)),
            released_at=datetime(2026, 8, 21, 15, 0, tzinfo=UTC),
        ),
        nodes=(
            node(10, "ROOT", None, "ENG-ROOT"),
            node(11, "SUB", "ROOT", "ENG-SUB"),
            node(12, "LEAF", "SUB", "ENG-LEAF"),
        ),
    )


class Phase8MbomPublishRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import frappe  # noqa: F401
        except ImportError:
            frappe = types.ModuleType("frappe")
            frappe._ = lambda source: source
            frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
            frappe.PermissionError = type("PermissionError", (Exception,), {})
            frappe.ValidationError = type("ValidationError", (Exception,), {})
            sys.modules["frappe"] = frappe
        documents = types.ModuleType("npi_core.documents.frappe_repository")
        documents._database_datetime = lambda value: value
        documents._json_object = lambda value: (
            value if isinstance(value, dict) else json.loads(value)
        )
        documents._json_array = lambda value: (
            value if isinstance(value, list) else json.loads(value)
        )
        sys.modules["npi_core.documents.frappe_repository"] = documents
        terminal = types.ModuleType("npi_core.project_controls.terminal_guard")
        terminal.require_mutable_project = lambda _project: None
        sys.modules["npi_core.project_controls.terminal_guard"] = terminal
        item_repository = types.ModuleType(
            "npi_integration.item_publish.frappe_repository"
        )
        item_repository.FrappeItemPublishRepository = object
        sys.modules[
            "npi_integration.item_publish.frappe_repository"
        ] = item_repository
        from npi_integration.mbom_publish import frappe_repository

        cls.repository = frappe_repository

    def test_phase5_projection_preserves_exact_topology_and_release_evidence(self) -> None:
        project = types.SimpleNamespace(tenant_id="tenant-a", global_id=uid(1))
        source = self.repository._source_from_phase5(project, phase5_request())
        self.assertEqual(source.assembly_line_keys, ("ROOT", "SUB"))
        self.assertEqual(source.roles["LEAF"].value, "component_only")
        self.assertEqual(source.phase5_publish_request_global_id, uid(3))
        self.assertEqual(source.revision_snapshot_hash, "5" * 64)
        self.assertEqual(source.lines[0].effectivity, (("start", "A"),))
        changed = phase5_request()
        changed.nodes[2].line.quantity = "2.000"
        changed_source = self.repository._source_from_phase5(project, changed)
        self.assertNotEqual(source.topology_hash, changed_source.topology_hash)
        self.assertNotEqual(source.source_hash, changed_source.source_hash)

    def test_item_stream_key_is_exact_p803_identity(self) -> None:
        self.assertEqual(
            self.repository._item_stream_key("tenant-a", uid(1), "ENG-ROOT"),
            canonical_hash(
                {
                    "schemaVersion": 1,
                    "tenantId": "tenant-a",
                    "projectGlobalId": str(uid(1)),
                    "engineeringItemId": "ENG-ROOT",
                }
            ),
        )

    def test_stream_guard_active_uncertain_retained_and_corrupt_truth_fail_closed(self) -> None:
        source = self.repository._source_from_phase5(
            types.SimpleNamespace(tenant_id="tenant-a", global_id=uid(1)),
            phase5_request(),
        )
        profile = MbomExecutionProfileReference(
            "mbom-synthetic-v1",
            1,
            MbomTargetMode.SYNTHETIC,
            "disposable-test",
            "projection-v1",
            1,
            "7" * 64,
            "8" * 64,
        )
        readiness = tuple(
            ItemMappingReadiness(
                engineering_item_id=item,
                disposition=ItemReadinessDisposition.SYNTHETIC_REFERENCE,
                item_stream_key_hash=self.repository._item_stream_key(
                    source.tenant_id,
                    source.project_global_id,
                    item,
                ),
                mapping_version=0,
                authority=MbomResultAuthority.SYNTHETIC,
                synthetic_item_reference="synthetic-item-" + canonical_hash({"item": item})[:24],
            )
            for item in source.engineering_item_ids
        )
        expectations = tuple(
            MbomMappingExpectation(
                source.assembly_source_key(key),
                key,
                0,
                MbomTargetSubmissionState.UNMAPPED_CREATE,
            )
            for key in source.assembly_line_keys
        )
        value = create_mbom_publish_request(
            source=source,
            item_readiness=readiness,
            mbom_expectations=expectations,
            profile=profile,
            actor_user_id="publisher@example.invalid",
            service_actor_user_id="worker@example.invalid",
            request_id=uid(20),
            trace_id="trace-p804-repository",
            idempotency_key_hash="9" * 64,
            global_id=uid(21),
            created_at=datetime(2026, 8, 21, 15, 0, tzinfo=UTC),
        )
        guard = types.SimpleNamespace(
            tenant_id=source.tenant_id,
            project_global_id=str(source.project_global_id),
            ebom_global_id=str(source.ebom_global_id),
            source_stream_key_hash=source.source_stream_key_hash,
            active_state="queued",
            last_state=None,
            last_target_idempotency_key_hash=None,
        )
        self.assertEqual(
            self.repository._stream_guard_problem(guard, value).code,
            "MBOM_PUBLISH_STREAM_ACTIVE",
        )
        guard.active_state = "uncertain_after_timeout"
        self.assertEqual(
            self.repository._stream_guard_problem(guard, value).code,
            "MBOM_PUBLISH_RECONCILIATION_REQUIRED",
        )
        guard.active_state = None
        guard.last_state = "succeeded"
        guard.last_target_idempotency_key_hash = value.target_idempotency_key_hash
        self.assertEqual(
            self.repository._stream_guard_problem(guard, value).code,
            "MBOM_PUBLISH_EFFECT_RETAINED",
        )
        guard.last_state = "queued"
        with self.assertRaises(RuntimeError):
            self.repository._stream_guard_problem(guard, value)

    def test_repository_has_one_atomic_write_order_and_no_target_boundary(self) -> None:
        path = ROOT / "apps/npi_integration/npi_integration/mbom_publish/frappe_repository.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_mbom_publish_request"
        )
        segment = ast.get_source_segment(source, method) or ""
        markers = (
            "self._insert_request(",
            "self._insert_nodes(",
            "self._insert_outbox(",
            "_activate_stream_guard(",
            "self._append_audit(",
            "self._insert_idempotency_receipt(",
        )
        positions = [segment.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("with mbom_request_transaction_write(self.actor)", segment)
        for forbidden in (
            "requests.",
            "httpx.",
            "frappe.db.sql",
            "adapter.call",
            "submit_bom",
        ):
            self.assertNotIn(forbidden, source.casefold())

    def test_request_row_roundtrip_revalidates_every_hash_and_scope(self) -> None:
        project = types.SimpleNamespace(tenant_id="tenant-a", global_id=uid(1))
        source = self.repository._source_from_phase5(project, phase5_request())
        profile = MbomExecutionProfileReference(
            "mbom-mock-v1",
            1,
            MbomTargetMode.MOCK,
            "mock",
            "projection-v1",
            1,
            "7" * 64,
            "8" * 64,
        )
        readiness = tuple(
            ItemMappingReadiness(
                item,
                ItemReadinessDisposition.NOT_READY,
                self.repository._item_stream_key(source.tenant_id, source.project_global_id, item),
                0,
            )
            for item in source.engineering_item_ids
        )
        expectations = tuple(
            MbomMappingExpectation(
                source.assembly_source_key(key),
                key,
                0,
                MbomTargetSubmissionState.UNMAPPED_CREATE,
            )
            for key in source.assembly_line_keys
        )
        value = create_mbom_publish_request(
            source=source,
            item_readiness=readiness,
            mbom_expectations=expectations,
            profile=profile,
            actor_user_id="publisher@example.invalid",
            service_actor_user_id=None,
            request_id=uid(30),
            trace_id="trace-p804-roundtrip",
            idempotency_key_hash="a" * 64,
            global_id=uid(31),
            created_at=datetime(2026, 8, 21, 15, 0, tzinfo=UTC),
        )
        row = types.SimpleNamespace(
            global_id=str(value.global_id),
            tenant_id=source.tenant_id,
            project_global_id=str(source.project_global_id),
            phase5_publish_request_global_id=str(source.phase5_publish_request_global_id),
            ebom_global_id=str(source.ebom_global_id),
            source_snapshot=source.canonical_mapping(),
            item_readiness_snapshot=json.dumps([item.canonical_mapping() for item in readiness]),
            mbom_expectation_snapshot=json.dumps([item.canonical_mapping() for item in expectations]),
            item_mapping_set_hash=value.item_mapping_set_hash,
            mbom_mapping_set_hash=value.mbom_mapping_set_hash,
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            target_mode=profile.target_mode.value,
            environment_code=profile.environment_code,
            projection_policy_id=profile.projection_policy_id,
            projection_policy_version=profile.projection_policy_version,
            projection_policy_hash=profile.projection_policy_hash,
            profile_snapshot_hash=profile.snapshot_hash,
            actor_user_id=value.actor_user_id,
            service_actor_user_id=None,
            request_id=str(value.request_id),
            trace_id=value.trace_id,
            idempotency_key_hash=value.idempotency_key_hash,
            target_idempotency_key_hash=value.target_idempotency_key_hash,
            semantic_effect_hash=value.semantic_effect_hash,
            state=value.state.value,
            dispatch_allowed=0,
            payload_hash=value.payload_hash,
            created_at=value.created_at,
        )
        self.assertEqual(self.repository._request_value(project, row), value)
        row.project_global_id = str(uid(99))
        with self.assertRaises(RuntimeError):
            self.repository._request_value(project, row)


if __name__ == "__main__":
    unittest.main()
