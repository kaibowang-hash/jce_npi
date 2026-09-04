from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_integration.mbom_publish.domain import (  # noqa: E402
    MbomMappingDisposition,
    MbomPublishRequestState,
    MbomTargetMode,
    create_mbom_publish_request,
    synthetic_item_readiness,
)
from npi_integration.mbom_publish.adapters import (  # noqa: E402
    failed_before_mbom_adapter_boundary_result,
)
from tests.test_phase8_mbom_publish_adapters import command  # noqa: E402
from tests.test_phase8_mbom_publish_domain import expectations, profile, source  # noqa: E402


NOW = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)


def value():
    source_value = source()
    return create_mbom_publish_request(
        source=source_value,
        item_readiness=synthetic_item_readiness(source_value),
        mbom_expectations=expectations(source_value),
        profile=profile(MbomTargetMode.SYNTHETIC),
        actor_user_id="publisher@example.invalid",
        service_actor_user_id="worker@example.invalid",
        request_id=UUID(int=51),
        trace_id="trace-p804-worker-repository",
        idempotency_key_hash="9" * 64,
        global_id=UUID(int=52),
        created_at=NOW,
    )


class FakeDb:
    def __init__(self):
        self.rows = []

    def get_value(self, *_args, **_kwargs):
        return None

    def get_all(self, *_args, **_kwargs):
        return list(self.rows)


class Phase8MbomPublishWorkerRepositoryTest(unittest.TestCase):
    MODULE = "npi_integration.mbom_publish.worker_repository"

    @classmethod
    def setUpClass(cls):
        module_names = (
            "frappe",
            "npi_core.documents.frappe_repository",
            "npi_core.foundation.audit",
            "npi_integration.mbom_publish.frappe_repository",
            "npi_integration.mbom_publish.diagnostics",
            cls.MODULE,
        )
        cls.saved = {name: sys.modules.get(name) for name in module_names}
        sys.modules.pop(cls.MODULE, None)
        sys.modules.pop("npi_integration.mbom_publish.diagnostics", None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.db = FakeDb()
        frappe.flags = types.SimpleNamespace()
        frappe.get_request_header = lambda _name: None
        frappe.get_doc = lambda *args, **kwargs: None
        frappe.get_all = frappe.db.get_all
        sys.modules["frappe"] = frappe
        documents = types.ModuleType("npi_core.documents.frappe_repository")
        documents._database_datetime = lambda item: item
        documents._json_object = lambda item: item
        documents._json_array = lambda item: item
        sys.modules[documents.__name__] = documents
        audit = types.ModuleType("npi_core.foundation.audit")
        audit.create_audit_event = lambda **values: types.SimpleNamespace(
            event_id=UUID(int=999), input_summary=values.pop("input_summary"), **values
        )
        sys.modules[audit.__name__] = audit
        repository = types.ModuleType(
            "npi_integration.mbom_publish.frappe_repository"
        )
        repository._request_value = lambda _project, row: row
        sys.modules[repository.__name__] = repository
        cls.module = importlib.import_module(cls.MODULE)
        cls.diagnostics = importlib.import_module(
            "npi_integration.mbom_publish.diagnostics"
        )

    @classmethod
    def tearDownClass(cls):
        for name, saved in cls.saved.items():
            sys.modules.pop(name, None)
            if saved is not None:
                sys.modules[name] = saved

    def setUp(self):
        self.repository = self.module.FrappeMbomPublishWorkerRepository()
        self.value = value()
        self.route = self.module.MbomPublishExecutionRoute(
            UUID(int=53),
            self.value.global_id,
            self.value.source.tenant_id,
            self.value.source.project_global_id,
            self.value.source.source_stream_key_hash,
            "worker@example.invalid",
            self.value.target_idempotency_key_hash,
            self.value.semantic_effect_hash,
        )
        self.guard = types.SimpleNamespace(
            active_request_global_id=str(self.value.global_id),
            active_target_idempotency_key_hash=self.value.target_idempotency_key_hash,
            active_state="processing",
            optimistic_version=1,
        )
        self.request = types.SimpleNamespace(
            tenant_id=self.value.source.tenant_id,
            project_global_id=str(self.value.source.project_global_id),
            state=self.value.state.value,
            optimistic_version=1,
            updated_at=NOW,
        )
        self.attempt = types.SimpleNamespace(
            global_id=str(UUID(int=55)),
            request_global_id=str(self.value.global_id),
            outbox_event_id=str(self.route.outbox_event_id),
            attempt_number=1,
            claim_token=str(UUID(int=56)),
            target_idempotency_key_hash=self.value.target_idempotency_key_hash,
            source_hash=self.value.source.source_hash,
            topology_hash=self.value.source.topology_hash,
            item_mapping_set_hash=self.value.item_mapping_set_hash,
            mbom_mapping_set_hash=self.value.mbom_mapping_set_hash,
            node_manifest_hash="a" * 64,
            profile_id=self.value.profile.profile_id,
            profile_version=self.value.profile.profile_version,
            state="started",
            adapter_boundary_crossed=0,
            request_snapshot={},
            request_snapshot_hash="0" * 64,
            started_at=NOW - timedelta(minutes=10),
        )
        self.outbox = types.SimpleNamespace(
            event_id=str(self.route.outbox_event_id),
            state="processing",
            attempt_count=1,
            mbom_last_attempt_global_id=self.attempt.global_id,
            adapter_boundary_crossed=0,
            claim_token=self.attempt.claim_token,
            lease_expires_at=NOW + timedelta(minutes=2),
            mbom_node_manifest_hash="a" * 64,
        )
        self.nodes = [types.SimpleNamespace(state="processing", optimistic_version=1)]
        self.saves = []
        self.inserts = []
        self.originals = {}
        self.patch("_read_execution_route", lambda _event: self.route)
        self.patch("_is_mbom_outbox", lambda _row: True)
        self.patch("_locked_guard", lambda _route: self.guard)
        self.patch("_optional_locked_doc", lambda doctype, _name: self.outbox if doctype == "NPI Outbox Message" else None)
        self.patch("_required_locked_request", lambda _outbox: self.request)
        self.patch("_request_value", lambda _project, _request: self.value)
        self.patch("_require_outbox_binding", lambda *_args: None)
        self.patch("_require_active_guard", lambda *_args: None)
        self.patch("_require_attempt_binding", lambda *_args: None)
        self.patch("_required_attempt", lambda _outbox: self.attempt)
        self.patch("_locked_assembly_nodes", lambda _request: tuple(self.nodes))
        self.patch("_command", lambda *_args, **_kwargs: command())
        self.patch("_command_from_attempt", lambda *_args: command())
        self.patch("_insert_attempt", lambda *_args: self.inserts.append("attempt"))
        self.patch("_append_audit", lambda *_args, **_kwargs: None)
        self.patch("mbom_claim_write", lambda _actor: nullcontext(object()))
        self.patch("save_mbom_support_document", lambda doc, **_kwargs: self.saves.append(doc))
        self.patch("_set_guard_active", lambda *_args: self.saves.append(self.guard))

    def tearDown(self):
        for name, original in self.originals.items():
            setattr(self.module, name, original)

    def patch(self, name, value):
        if name not in self.originals:
            self.originals[name] = getattr(self.module, name)
        setattr(self.module, name, value)

    def test_live_lease_is_not_claimed_and_performs_no_write(self):
        self.assertIsNone(self.repository.claim(self.route.outbox_event_id, now=NOW))
        self.assertEqual(self.saves, [])
        self.assertEqual(self.inserts, [])

    def test_expired_pre_boundary_closes_old_attempt_and_creates_new_batch_attempt(self):
        self.outbox.lease_expires_at = NOW - timedelta(seconds=1)
        self.nodes[0].state = "queued"
        claimed = self.repository.claim(self.route.outbox_event_id, now=NOW)
        self.assertIsNotNone(claimed)
        self.assertTrue(claimed.expired_recovery)
        self.assertFalse(claimed.recovered_after_adapter_boundary)
        self.assertEqual(self.inserts, ["attempt"])
        self.assertEqual(self.attempt.safe_error_code, "MBOM_PUBLISH_EXPIRED_BEFORE_BOUNDARY")
        self.assertEqual(self.outbox.attempt_count, 2)
        self.assertEqual(self.nodes[0].state, "processing")

    def test_expired_post_boundary_reuses_attempt_and_never_creates_new_one(self):
        self.outbox.lease_expires_at = NOW - timedelta(seconds=1)
        self.outbox.adapter_boundary_crossed = 1
        self.attempt.adapter_boundary_crossed = 1
        claimed = self.repository.claim(self.route.outbox_event_id, now=NOW)
        self.assertTrue(claimed.recovered_after_adapter_boundary)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.outbox.attempt_count, 1)

    def test_terminal_states_require_retained_truth_and_never_claim(self):
        self.patch("_require_terminal_guard", lambda *_args: self.saves.append("checked"))
        for state in sorted(self.module._TERMINAL_OUTBOX_STATES):
            with self.subTest(state=state):
                self.saves.clear()
                self.outbox.state = state
                self.assertIsNone(
                    self.repository.claim(self.route.outbox_event_id, now=NOW)
                )
                self.assertEqual(self.saves, ["checked"])

    def test_recovery_is_bounded_to_pending_and_expired_processing(self):
        self.module.frappe.get_all = lambda *_args, **kwargs: [
            {"event_id": str(UUID(int=61)), "state": "pending", "lease_expires_at": None},
            {"event_id": str(UUID(int=62)), "state": "processing", "lease_expires_at": NOW - timedelta(seconds=1)},
            {"event_id": str(UUID(int=63)), "state": "processing", "lease_expires_at": NOW + timedelta(seconds=1)},
        ]
        self.assertEqual(
            self.repository.recoverable_outbox_event_ids(now=NOW),
            (UUID(int=61), UUID(int=62)),
        )

    def test_deterministic_result_and_node_result_ids_are_stable_and_distinct(self):
        attempt = UUID(int=70)
        first = self.module.deterministic_mbom_result_id(attempt)
        self.assertEqual(first, self.module.deterministic_mbom_result_id(attempt))
        root = self.module.deterministic_mbom_node_result_id(attempt, "ROOT")
        sub = self.module.deterministic_mbom_node_result_id(attempt, "SUB")
        self.assertNotEqual(first, root)
        self.assertNotEqual(root, sub)

    def test_real_command_freezes_exact_request_and_node_manifest(self):
        original_command = self.originals["_command"]
        readiness = {
            item.engineering_item_id: item for item in self.value.item_readiness
        }
        expectations_by_key = {
            item.stable_line_key: item for item in self.value.mbom_expectations
        }
        roles = self.value.source.roles
        nodes = []
        manifest = []
        for index, line in enumerate(self.value.source.lines):
            expectation = expectations_by_key.get(line.stable_line_key)
            if expectation is None:
                continue
            snapshot = {
                "line": line.canonical_mapping(roles[line.stable_line_key]),
                "itemReadiness": readiness[line.engineering_item_id].canonical_mapping(),
                "mbomExpectation": expectation.canonical_mapping(),
            }
            node_id = UUID(int=80 + index)
            nodes.append(
                types.SimpleNamespace(
                    global_id=str(node_id),
                    stable_line_key=line.stable_line_key,
                    line_snapshot=snapshot["line"],
                    item_readiness_snapshot=snapshot["itemReadiness"],
                    mbom_expectation_snapshot=snapshot["mbomExpectation"],
                )
            )
            from npi_integration.mbom_publish.domain import canonical_hash

            manifest.append(
                {
                    "globalId": str(node_id),
                    "stableLineKey": line.stable_line_key,
                    "nodeSnapshotHash": canonical_hash(snapshot),
                }
            )
        from npi_integration.mbom_publish.domain import canonical_hash

        self.patch("_locked_assembly_nodes", lambda _request: tuple(nodes))
        component_line = next(
            line
            for line in self.value.source.lines
            if line.stable_line_key not in expectations_by_key
        )
        component_manifest = manifest + [
            {
                "globalId": str(UUID(int=99)),
                "stableLineKey": component_line.stable_line_key,
                "nodeSnapshotHash": "f" * 64,
            }
        ]
        self.patch(
            "_outbox_for_request",
            lambda _request: types.SimpleNamespace(
                mbom_node_manifest_hash=canonical_hash(
                    {
                        "requestGlobalId": str(self.value.global_id),
                        "nodes": component_manifest,
                    }
                )
            ),
        )
        from npi_integration.mbom_publish.domain import MbomPublishContractError

        with self.assertRaises(MbomPublishContractError):
            original_command(self.value, self.request, attempt_number=1)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.saves, [])

        self.patch(
            "_outbox_for_request",
            lambda _request: types.SimpleNamespace(
                mbom_node_manifest_hash=canonical_hash(
                    {"requestGlobalId": str(self.value.global_id), "nodes": manifest}
                )
            ),
        )
        frozen = original_command(self.value, self.request, attempt_number=1)
        self.assertEqual(frozen.request_snapshot, self.value.payload())
        self.assertEqual(
            tuple(node.stable_line_key for node in frozen.nodes),
            self.value.source.assembly_line_keys,
        )
        self.assertEqual(frozen.node_manifest_hash, canonical_hash({
            "requestGlobalId": str(self.value.global_id), "nodes": manifest
        }))

    def test_submitted_and_stale_conflicts_strip_formal_truth_from_node_result(self):
        from npi_integration.mbom_publish.domain import (
            MbomFaultKind,
            MbomNodeObservation,
            MbomNodeResultState,
            MbomResultAuthority,
            MbomTargetSubmissionState,
        )

        observed = MbomNodeObservation(
            "ROOT",
            "1" * 64,
            MbomNodeResultState.SUCCEEDED_AUTHORITATIVE,
            MbomResultAuthority.AUTHORITATIVE_SANDBOX,
            True,
            "2" * 64,
            "BOM-SBX-1",
            "2",
            MbomTargetSubmissionState.EDITABLE_DRAFT,
        )
        for state, fault in (
            (MbomNodeResultState.BLOCKED_SUBMITTED, MbomFaultKind.SUBMITTED_BOM),
            (MbomNodeResultState.OBSERVED_CONFLICT, MbomFaultKind.STALE_MAPPING),
        ):
            result = self.module._conflict_observation(observed, state, fault)
            self.assertIsNone(result.formal_bom_id)
            self.assertFalse(result.response_authenticated)
            self.assertEqual(result.fault_kind, fault)

    def test_current_mapping_rejects_self_consistent_wrong_request_identity(self):
        from npi_integration.mbom_publish.domain import canonical_hash

        expectation = self.value.mbom_expectations[0]
        observation_id = UUID(int=120)
        base = {
            "global_id": str(UUID(int=121)),
            "tenant_id": self.value.source.tenant_id,
            "project_global_id": str(self.value.source.project_global_id),
            "ebom_global_id": str(self.value.source.ebom_global_id),
            "assembly_source_key": expectation.assembly_source_key,
            "stable_line_key": expectation.stable_line_key,
            "mapping_version": 1,
            "formal_bom_id": "BOM-SBX-1",
            "target_version": "1",
            "target_submission_state": "editable_draft",
            "current_observation": str(observation_id),
            "current_observation_hash": "b" * 64,
            "updated_at": NOW,
        }

        def row(values):
            snapshot = {
                "schemaVersion": 1,
                "globalId": values["global_id"],
                "tenantId": values["tenant_id"],
                "projectGlobalId": values["project_global_id"],
                "ebomGlobalId": values["ebom_global_id"],
                "assemblySourceKey": values["assembly_source_key"],
                "stableLineKey": values["stable_line_key"],
                "mappingVersion": values["mapping_version"],
                "formalBomId": values["formal_bom_id"],
                "targetVersion": values["target_version"],
                "targetSubmissionState": values["target_submission_state"],
                "currentObservationGlobalId": values["current_observation"],
                "currentObservationHash": values["current_observation_hash"],
                "updatedAt": self.module._utc_text(values["updated_at"]),
            }
            return types.SimpleNamespace(
                **values,
                head_snapshot=snapshot,
                head_hash=canonical_hash(snapshot),
            )

        current = row(base)
        original_get_value = self.module.frappe.db.get_value
        self.addCleanup(
            setattr, self.module.frappe.db, "get_value", original_get_value
        )
        self.module.frappe.db.get_value = lambda *_args, **_kwargs: "mapping-head"
        self.patch("_optional_locked_doc", lambda *_args: current)
        locked, value = self.module._locked_current_mapping(self.value, expectation)
        self.assertIs(locked, current)
        self.assertEqual(value.mapping_version, 1)

        wrong_values = {
            "tenant_id": "tenant-other",
            "project_global_id": str(UUID(int=122)),
            "ebom_global_id": str(UUID(int=123)),
            "assembly_source_key": "c" * 64,
            "stable_line_key": "FORGED-STABLE-LINE",
        }
        for field, forged in wrong_values.items():
            with self.subTest(field=field):
                current = row({**base, field: forged})
                with self.assertRaisesRegex(
                    RuntimeError, "Current MBOM mapping head is invalid[.]"
                ):
                    self.module._locked_current_mapping(self.value, expectation)
                self.assertEqual(self.saves, [])
                self.assertEqual(self.inserts, [])

    def test_worker_repository_contains_no_target_client_or_direct_sql(self):
        import ast

        source_text = (
            ROOT
            / "apps/npi_integration/npi_integration/mbom_publish/worker_repository.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        direct_sql_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sql"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "db"
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "frappe"
        ]
        self.assertEqual(direct_sql_calls, [])
        for forbidden in ("requests.", "httpx.", "submit_bom"):
            self.assertNotIn(forbidden, source_text.casefold())

    def test_process_validation_diagnostic_is_exact_inner_wins_and_dormant(self):
        records: list[dict[str, object]] = []
        package = types.ModuleType("npi_core")
        package.__path__ = []
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: records.append(values)
        private = "private actor payload /tmp/secret"
        error = type("PinnedValidationError", (Exception,), {})(private)

        with patch.dict(
            sys.modules, {"npi_core": package, "npi_core.api": api}
        ):
            with self.diagnostics.mbom_process_validation_diagnostics(
                "trace-0123456789abcdef0123456789abcdef",
                enabled=True,
            ) as state:
                with self.assertRaises(type(error)) as raised:
                    with self.diagnostics.mbom_process_validation_step(
                        "P804_PROCESS_CLAIM_OUTBOX_SAVE"
                    ):
                        with self.diagnostics.mbom_process_validation_step(
                            "P804_PROCESS_CLAIM_ATTEMPT_INSERT"
                        ):
                            raise error
                self.assertTrue(state["recorded"])
        self.assertIs(raised.exception, error)
        self.assertEqual(
            records,
            [
                {
                    "code": "P804_PROCESS_CLAIM_ATTEMPT_INSERT",
                    "title": "NPI MBOM publish process validation stage failed",
                    "exception_type": "PinnedValidationError",
                    "trace_id": "trace-0123456789abcdef0123456789abcdef",
                }
            ],
        )
        self.assertNotIn("private", str(records))
        self.assertFalse(
            hasattr(
                self.module.frappe.flags,
                "npi_p804_mbom_process_validation_diagnostic",
            )
        )

        for trace_id, enabled, code in (
            ("trace-private", True, "P804_PROCESS_CLAIM_OUTBOX_SAVE"),
            ("trace-0123456789abcdef0123456789abcdef", False, "P804_PROCESS_CLAIM_OUTBOX_SAVE"),
            ("trace-0123456789abcdef0123456789abcdef", 1, "P804_PROCESS_CLAIM_OUTBOX_SAVE"),
            ("trace-0123456789abcdef0123456789abcdef", True, "P804_PROCESS_NOT_ALLOWED"),
        ):
            with self.subTest(trace_id=trace_id, enabled=enabled, code=code):
                records.clear()
                with self.diagnostics.mbom_process_validation_diagnostics(
                    trace_id, enabled=enabled
                ):
                    with self.assertRaises(type(error)) as closed:
                        with self.diagnostics.mbom_process_validation_step(code):
                            raise error
                self.assertIs(closed.exception, error)
                self.assertEqual(records, [])

    def test_real_claim_write_wrapper_records_exact_boundary_without_extra_write(self):
        records: list[dict[str, object]] = []
        package = types.ModuleType("npi_core")
        package.__path__ = []
        api = types.ModuleType("npi_core.api")
        api.record_safe_diagnostic = lambda **values: records.append(values)
        error = type("PinnedValidationError", (Exception,), {})("private business value")
        self.outbox.state = "pending"
        self.request.state = MbomPublishRequestState.QUEUED.value

        def fail_outbox_save(doc, **_kwargs):
            self.saves.append(doc)
            if doc is self.outbox:
                raise error

        self.patch("save_mbom_support_document", fail_outbox_save)
        with patch.dict(
            sys.modules, {"npi_core": package, "npi_core.api": api}
        ), self.diagnostics.mbom_process_validation_diagnostics(
            "trace-0123456789abcdef0123456789abcdef", enabled=True
        ), self.assertRaises(type(error)) as raised:
            self.repository.claim(self.route.outbox_event_id, now=NOW)
        self.assertIs(raised.exception, error)
        self.assertEqual(self.inserts, ["attempt"])
        self.assertEqual(self.saves, [self.outbox])
        self.assertEqual(records[0]["code"], "P804_PROCESS_CLAIM_OUTBOX_SAVE")
        self.assertNotIn("private", str(records))

    def test_real_seal_retains_complete_claim_and_saves_outbox_once_in_order(self):
        frozen = command()
        result = failed_before_mbom_adapter_boundary_result(
            command=frozen,
            safe_error_code="MBOM_PUBLISH_TEST_BOUNDARY",
        )
        self.outbox.doctype = "NPI Outbox Message"
        self.outbox.claimed_at = NOW - timedelta(minutes=1)
        self.request.doctype = "NPI MBOM Publish Request"
        self.attempt.doctype = "NPI MBOM Publish Attempt"
        self.nodes = [
            types.SimpleNamespace(
                doctype="NPI MBOM Publish Node",
                global_id=str(node.node_global_id),
                stable_line_key=node.stable_line_key,
                state="processing",
                optimistic_version=1,
            )
            for node in frozen.nodes
        ]
        claim = self.module.ClaimedMbomPublishMessage(
            self.route.outbox_event_id,
            self.value.global_id,
            self.value.source.tenant_id,
            self.value.source.project_global_id,
            "trace-p804-worker-repository",
            UUID(self.outbox.claim_token),
            self.outbox.lease_expires_at,
            frozen,
            self.value.profile,
            "worker@example.invalid",
            False,
            False,
        )
        claim_fields = (
            self.outbox.claim_token,
            self.outbox.claimed_at,
            self.outbox.lease_expires_at,
        )
        order: list[str] = []

        def get_doc(value):
            return types.SimpleNamespace(**value)

        original_get_doc = self.module.frappe.get_doc
        self.addCleanup(setattr, self.module.frappe, "get_doc", original_get_doc)
        self.module.frappe.get_doc = get_doc
        self.patch(
            "_required_current_claim",
            lambda _claim: (self.outbox, self.request, self.attempt, self.guard),
        )
        self.patch("_existing_result", lambda _result_id: None)
        self.patch("_locked_assembly_nodes", lambda _request: tuple(self.nodes))
        self.patch("_locked_current_mapping", lambda *_args: (None, None))
        self.patch(
            "classify_mapping_observation",
            lambda **_kwargs: MbomMappingDisposition.RESULT_NOT_SUCCESS,
        )
        self.patch("mbom_result_transaction_write", lambda _actor: nullcontext(object()))
        self.patch(
            "insert_mbom_support_document",
            lambda document, **_kwargs: order.append(f"insert:{document.doctype}"),
        )
        self.patch(
            "save_mbom_support_document",
            lambda document, **_kwargs: order.append(f"save:{document.doctype}"),
        )
        self.patch("_record_mapping_observation", lambda **_kwargs: False)
        self.patch(
            "_set_guard_terminal",
            lambda *_args: order.append("save:NPI MBOM Publish Stream Guard"),
        )
        self.patch("_append_audit", lambda *_args, **_kwargs: order.append("insert:NPI Audit Event"))

        outcome = self.repository.seal_result(
            claim,
            profile=None,
            result=result,
            now=NOW,
        )

        self.assertEqual(outcome.state, MbomPublishRequestState.FAILED_FINAL.value)
        self.assertEqual(
            (
                self.outbox.claim_token,
                self.outbox.claimed_at,
                self.outbox.lease_expires_at,
            ),
            claim_fields,
        )
        self.assertEqual(order.count("save:NPI Outbox Message"), 1)
        self.assertEqual(
            order,
            [
                "insert:NPI MBOM Publish Result",
                "insert:NPI MBOM Publish Node Result",
                "insert:NPI MBOM Publish Node Result",
                "save:NPI MBOM Publish Node",
                "save:NPI MBOM Publish Node",
                "save:NPI MBOM Publish Attempt",
                "save:NPI MBOM Publish Request",
                "save:NPI Outbox Message",
                "save:NPI MBOM Publish Stream Guard",
                "insert:NPI Audit Event",
            ],
        )

    def test_result_parent_precedes_node_children_and_mapping_writes(self):
        import ast

        source_text = (
            ROOT
            / "apps/npi_integration/npi_integration/mbom_publish/worker_repository.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "seal_result"
        )
        segment = ast.get_source_segment(source_text, method) or ""
        positions = [
            segment.index(marker)
            for marker in (
                '"doctype": "NPI MBOM Publish Result"',
                '"doctype": "NPI MBOM Publish Node Result"',
                "_record_mapping_observation(",
                "_finish_attempt(",
            )
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("with mbom_result_transaction_write(", segment)


if __name__ == "__main__":
    unittest.main()
