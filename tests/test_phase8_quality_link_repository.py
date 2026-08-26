from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

ROOT = Path(__file__).resolve().parents[1]
PROJECT = UUID("00000000-0000-4000-8000-00000000c611")
TENANT = "tenant-quality-link"
SOURCE = UUID("00000000-0000-4000-8000-00000000c612")
OBSERVATION = UUID("00000000-0000-4000-8000-00000000c613")
PROJECTION_HEAD = UUID("00000000-0000-4000-8000-00000000c614")
LINK_HEAD = UUID("00000000-0000-4000-8000-00000000c615")
SOURCE_HASH = "a" * 64
PROJECTION_HASH = "b" * 64


class Phase8QualityLinkRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.documents.frappe_repository",
        "npi_core.foundation.audit",
        "npi_core.foundation.security",
        "npi_core.project_controls.terminal_guard",
        "npi_core.readiness.frappe_repository",
        "npi_core.trial.quality_repository",
        "npi_core.trial.review_repository",
        "npi_integration.quality_link.frappe_validation",
        "npi_integration.quality_link.problems",
        "npi_integration.quality_link.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.events: list[str] = []
        frappe = types.ModuleType("frappe")
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.db = types.SimpleNamespace(get_value=lambda *_args, **_kwargs: None)
        frappe.get_all = lambda *_args, **_kwargs: []
        frappe.get_doc = lambda *_args, **_kwargs: None
        self.frappe = frappe
        sys.modules["frappe"] = frappe

        base = types.ModuleType("npi_core.documents.frappe_repository")

        class FrappeDocumentRepository:
            pass

        base.FrappeDocumentRepository = FrappeDocumentRepository
        sys.modules[base.__name__] = base
        audit = types.ModuleType("npi_core.foundation.audit")
        audit.create_audit_event = lambda **_kwargs: None
        sys.modules[audit.__name__] = audit
        security = types.ModuleType("npi_core.foundation.security")
        security.Principal = object
        sys.modules[security.__name__] = security
        guard = types.ModuleType("npi_core.project_controls.terminal_guard")
        guard.require_mutable_project = lambda _project: self.events.append("mutable")
        sys.modules[guard.__name__] = guard
        readiness = types.ModuleType("npi_core.readiness.frappe_repository")
        readiness.FrappeReadinessRepository = object
        readiness._project_revision_chain = lambda _project: []
        sys.modules[readiness.__name__] = readiness
        quality = types.ModuleType("npi_core.trial.quality_repository")
        quality.FrappeTrialQualityRepository = object
        sys.modules[quality.__name__] = quality
        review = types.ModuleType("npi_core.trial.review_repository")
        review.FrappeTrialReviewRepository = object
        sys.modules[review.__name__] = review
        validation = types.ModuleType("npi_integration.quality_link.frappe_validation")

        @contextmanager
        def command_write(*, scope: str):
            self.events.append(f"capability:{scope}")
            yield object()

        validation.quality_link_command_write = command_write
        sys.modules[validation.__name__] = validation
        problems = types.ModuleType("npi_integration.quality_link.problems")
        for name in (
            "FormalQualityLinkAuthorityUnavailable",
            "FormalQualityLinkHeadConflict",
            "FormalQualityLinkIdempotencyConflict",
            "FormalQualityLinkSourceConflict",
            "FormalQualityProjectionConflict",
        ):
            setattr(problems, name, type(name, (RuntimeError,), {}))
        sys.modules[problems.__name__] = problems

        self.module = importlib.import_module("npi_integration.quality_link.frappe_repository")
        self.repository = object.__new__(self.module.FrappeFormalQualityLinkRepository)
        self.repository.actor = "quality@example.invalid"
        self.repository.trace_id = "trace-quality-link-repository"
        self.repository.request_id = "request-quality-link-repository"
        self.repository.principal = object()
        self.project = types.SimpleNamespace(global_id=PROJECT, tenant_id=TENANT)
        self.source = self.module.QualitySourceReference(
            TENANT,
            PROJECT,
            self.module.QualitySourceKind.TRIAL_DEFECT,
            SOURCE,
            2,
            "open",
            SOURCE_HASH,
        )
        self.observation = self.module.FormalQualityObservationReference(
            TENANT,
            PROJECT,
            "trial_round",
            UUID("00000000-0000-4000-8000-00000000c616"),
            OBSERVATION,
            PROJECTION_HEAD,
            3,
            "Quality Inspection",
            "QI-opaque",
            "7",
            self.module.FormalQualityRecordKind.QUALITY_INSPECTION,
            "Completed",
            "Accepted",
            "c" * 64,
            "d" * 64,
            PROJECTION_HASH,
            "formal_quality_v1",
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def invoke(self, *, expected_link_head_version: int = 0):
        return self.repository.link_observed_formal_quality_reference(
            PROJECT,
            source_kind=self.module.QualitySourceKind.TRIAL_DEFECT,
            source_global_id=SOURCE,
            expected_source_version=2,
            expected_source_snapshot_hash=SOURCE_HASH,
            observation_global_id=OBSERVATION,
            expected_projection_head_global_id=PROJECTION_HEAD,
            expected_projection_head_version=3,
            expected_projection_head_hash=PROJECTION_HASH,
            expected_link_head_version=expected_link_head_version,
            idempotency_key_hash="e" * 64,
        )

    def command_patches(self, *, replay: dict[str, object] | None = None, head: object | None = None):
        resolved = self.module._ResolvedSource(
            self.source,
            "trial_round",
            self.observation.scope_global_id,
        )
        return patch.multiple(
            self.repository,
            create=True,
            _locked_authorized_project=lambda _project: self.project,
            _receipt_replay=lambda _project, _identity: replay,
            _resolve_source=lambda *_args, **_kwargs: resolved,
            _resolve_observation=lambda *_args, **_kwargs: self.observation,
            _locked_link_head=lambda _stream: head,
            _insert_receipt=lambda *_args: self.events.append("receipt-insert") or object(),
            _insert_revision=lambda *_args: self.events.append("revision-insert"),
            _insert_head=lambda *_args: self.events.append("head-insert"),
            _advance_head=lambda *_args: self.events.append("head-save"),
            _append_audit=lambda *_args, **_kwargs: self.events.append("audit-insert"),
            _seal_receipt=lambda *_args: self.events.append("receipt-save"),
        )

    def test_create_is_one_closed_atomic_write_order(self) -> None:
        with self.command_patches():
            outcome = self.invoke()
        self.assertFalse(outcome.replayed)
        self.assertEqual(
            self.events,
            [
                "mutable",
                f"capability:link_observed_formal_quality_reference:{PROJECT}",
                "receipt-insert",
                "revision-insert",
                "head-insert",
                "audit-insert",
                "receipt-save",
            ],
        )
        self.assertEqual(outcome.response["formalQualityInterpretation"]["state"], "unavailable")
        self.assertEqual(outcome.response["linkRevision"]["source"]["sourceSnapshotHash"], SOURCE_HASH)
        self.assertEqual(outcome.response["linkHead"]["currentProjectionHeadVersion"], 3)

    def test_exact_replay_short_circuits_all_resolution_and_writes(self) -> None:
        replay = {"projectGlobalId": str(PROJECT), "operation": "link_observed_formal_quality_reference"}
        with self.command_patches(replay=replay):
            outcome = self.invoke()
        self.assertTrue(outcome.replayed)
        self.assertEqual(outcome.response, replay)
        self.assertEqual(self.events, ["mutable"])

    def test_missing_head_with_nonzero_version_conflicts_before_writes(self) -> None:
        with self.command_patches():
            with self.assertRaises(self.module.FormalQualityLinkHeadConflict):
                self.invoke(expected_link_head_version=1)
        self.assertEqual(self.events, ["mutable"])

    def test_same_key_different_payload_conflicts_before_any_write(self) -> None:
        identity = self.module.QualityLinkCommandIdentity(
            TENANT,
            PROJECT,
            "quality@example.invalid",
            self.module.QUALITY_LINK_OPERATION,
            "e" * 64,
            "f" * 64,
            SOURCE_HASH,
            PROJECTION_HASH,
        )
        receipt = types.SimpleNamespace(
            tenant_id=TENANT,
            project_global_id=PROJECT,
            actor_user_id="quality@example.invalid",
            operation=self.module.QUALITY_LINK_OPERATION,
            idempotency_key_hash="e" * 64,
            payload_hash="0" * 64,
            source_snapshot_hash=SOURCE_HASH,
            projection_head_hash=PROJECTION_HASH,
        )
        self.frappe.db.get_value = lambda *_args, **_kwargs: "receipt"
        self.frappe.get_doc = lambda *_args, **_kwargs: receipt
        with self.assertRaises(self.module.FormalQualityLinkIdempotencyConflict):
            self.repository._receipt_replay(self.project, identity)
        self.assertEqual(self.events, [])

    def test_existing_head_advances_once_without_rewriting_history(self) -> None:
        head = types.SimpleNamespace(
            global_id=LINK_HEAD,
            current_revision=UUID("00000000-0000-4000-8000-00000000c617"),
            revision_number=4,
            optimistic_version=4,
        )
        with self.command_patches(head=head), patch.object(
            self.module.FrappeFormalQualityLinkRepository,
            "_require_link_head_identity",
            return_value=None,
        ):
            outcome = self.invoke(expected_link_head_version=4)
        self.assertEqual(outcome.response["linkRevision"]["revisionNumber"], 5)
        self.assertEqual(outcome.response["linkHead"]["optimisticVersion"], 5)
        self.assertIn("head-save", self.events)
        self.assertNotIn("head-insert", self.events)

    def test_observation_lock_requires_exact_sandbox_current_head_truth(self) -> None:
        scope_id = self.observation.scope_global_id
        head_snapshot = {"head": "exact"}
        observation_snapshot = {"observation": "exact"}
        head = types.SimpleNamespace(
            global_id=PROJECTION_HEAD,
            tenant_id=TENANT,
            project_global_id=PROJECT,
            scope_kind="trial_round",
            scope_global_id=scope_id,
            projection_kind="formal_quality_status",
            current_observation=OBSERVATION,
            optimistic_version=3,
            head_hash=self.module.canonical_payload_hash(head_snapshot),
            availability="available",
            freshness="fresh",
            freshness_policy_ref="formal_quality_v1",
            source_object_type="Quality Inspection",
            source_object_id="QI-opaque",
            current_source_version="7",
            current_payload_hash="c" * 64,
            head_snapshot=head_snapshot,
        )
        observation = types.SimpleNamespace(
            global_id=OBSERVATION,
            tenant_id=TENANT,
            project_global_id=PROJECT,
            scope_kind="trial_round",
            scope_global_id=scope_id,
            projection_kind="formal_quality_status",
            source_system="ERPNEXT",
            target_system="NPI_ONE",
            adapter_mode="sandbox",
            availability="available",
            freshness="fresh",
            disposition="applied_current",
            source_object_type="Quality Inspection",
            source_object_id="QI-opaque",
            source_version="7",
            payload_hash="c" * 64,
            observation_hash=self.module.canonical_payload_hash(observation_snapshot),
            observation_snapshot=observation_snapshot,
            payload={
                "values": {
                    "recordKind": "quality_inspection",
                    "statusCode": "Completed",
                    "resultCode": "Accepted",
                    "observedAt": "2026-08-26T00:00:00Z",
                }
            },
        )
        resolved = self.module._ResolvedSource(self.source, "trial_round", scope_id)

        def document(doctype: str, *_args: object, **_kwargs: object):
            return head if doctype == "NPI ERP Projection Head" else observation

        with patch.object(self.module, "_optional_doc", side_effect=document):
            result = self.repository._resolve_observation(
                self.project,
                source=resolved,
                observation_global_id=OBSERVATION,
                expected_head_global_id=PROJECTION_HEAD,
                expected_head_version=3,
                expected_head_hash=head.head_hash,
            )
            self.assertEqual(result.observation_global_id, OBSERVATION)
            observation.adapter_mode = "synthetic"
            with self.assertRaises(self.module.FormalQualityProjectionConflict):
                self.repository._resolve_observation(
                    self.project,
                    source=resolved,
                    observation_global_id=OBSERVATION,
                    expected_head_global_id=PROJECTION_HEAD,
                    expected_head_version=3,
                    expected_head_hash=head.head_hash,
                )

    def test_repository_has_no_target_outbox_or_direct_sql_surface(self) -> None:
        source = (ROOT / "apps/npi_integration/npi_integration/quality_link/frappe_repository.py").read_text(encoding="utf-8")
        for forbidden in ("frappe.db." "sql", "ignore_permissions", "enqueue(", "Outbox", "requests.", "httpx."):
            self.assertNotIn(forbidden, source)
        for marker in (
            "manageDefects",
            "manageReviewReferences",
            "canRevise",
            'str(observation.adapter_mode) != "sandbox"',
            "canonical_payload_hash(_json_object(head.head_snapshot))",
            "canonical_payload_hash(_json_object(observation.observation_snapshot))",
            "FormalQualityLinkAuthorityUnavailable",
            "require_mutable_project(project)",
        ):
            self.assertIn(marker, source)

    def test_unproved_source_kinds_remain_unavailable_without_role_fallback(self) -> None:
        for source_kind in (
            self.module.QualitySourceKind.TRIAL_ROUND,
            self.module.QualitySourceKind.CONTROLLED_QUALITY_REPORT,
        ):
            with self.subTest(source_kind=source_kind.value):
                with self.assertRaises(self.module.FormalQualityLinkAuthorityUnavailable):
                    self.repository._resolve_source(
                        self.project,
                        source_kind=source_kind,
                        source_global_id=SOURCE,
                        expected_version=1,
                        expected_snapshot_hash=SOURCE_HASH,
                    )
        source = (ROOT / "apps/npi_integration/npi_integration/quality_link/frappe_repository.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("workspace[\"permissions\"].get(\"manageDefects\") is True"), 1)
        self.assertEqual(source.count("workspace[\"permissions\"].get(\"manageReviewReferences\") is True"), 1)
        self.assertEqual(source.count("workspace[\"permissions\"].get(\"canRevise\") is True"), 1)

    def test_source_currentness_is_exact_version_hash_and_project_containment(self) -> None:
        current = types.SimpleNamespace(
            tenant_id=TENANT,
            project_global_id=PROJECT,
            defect_global_id=SOURCE,
            trial_round_global_id=self.observation.scope_global_id,
            defect_version=2,
            snapshot_hash=SOURCE_HASH,
        )
        source_repository = types.SimpleNamespace(
            _trial_defect_chain=lambda *_args, **_kwargs: (current,)
        )
        with patch.object(
            self.module,
            "FrappeTrialQualityRepository",
            return_value=source_repository,
        ):
            self.assertEqual(
                self.repository._source_currentness(
                    self.project,
                    self.source,
                    self.observation,
                ),
                self.module.QualityLinkReconciliationState.CURRENT,
            )
            current.defect_version = 3
            current.snapshot_hash = "f" * 64
            self.assertEqual(
                self.repository._source_currentness(
                    self.project,
                    self.source,
                    self.observation,
                ),
                self.module.QualityLinkReconciliationState.DRIFTED,
            )
            current.defect_version = 2
            self.assertEqual(
                self.repository._source_currentness(
                    self.project,
                    self.source,
                    self.observation,
                ),
                self.module.QualityLinkReconciliationState.UNAVAILABLE,
            )
            current.project_global_id = UUID(int=99)
            self.assertEqual(
                self.repository._source_currentness(
                    self.project,
                    self.source,
                    self.observation,
                ),
                self.module.QualityLinkReconciliationState.UNAVAILABLE,
            )

    def test_projection_currentness_uses_one_exact_p8_01_stream(self) -> None:
        head, observation, linked = self.projection_truth(version=3)
        calls: list[tuple[object, ...]] = []

        def get_all(doctype: str, **kwargs: object):
            calls.append((doctype, kwargs))
            return [str(PROJECTION_HEAD)]

        def get_doc(doctype: str, _name: str, **_kwargs: object):
            return head if doctype == "NPI ERP Projection Head" else observation

        with patch.object(self.frappe, "get_all", side_effect=get_all), patch.object(
            self.frappe,
            "get_doc",
            side_effect=get_doc,
        ):
            self.assertEqual(
                self.repository._projection_currentness(self.project, linked),
                self.module.QualityLinkReconciliationState.CURRENT,
            )
        filters = calls[0][1]["filters"]
        self.assertEqual(
            filters,
            {
                "tenant_id": TENANT,
                "project_global_id": str(PROJECT),
                "scope_kind": "trial_round",
                "scope_global_id": str(linked.scope_global_id),
                "projection_kind": "formal_quality_status",
                "source_object_type": "Quality Inspection",
                "source_object_id": "QI-opaque",
            },
        )
        self.assertNotIn("status_code", filters)
        self.assertNotIn("result_code", filters)

    def test_projection_advance_is_drift_and_ambiguous_or_corrupt_is_unavailable(self) -> None:
        _linked_head, _linked_observation, linked = self.projection_truth(version=3)
        head, observation, _current = self.projection_truth(
            version=4,
            observation_id=UUID("00000000-0000-4000-8000-00000000c618"),
        )

        def get_doc(doctype: str, _name: str, **_kwargs: object):
            return head if doctype == "NPI ERP Projection Head" else observation

        with patch.object(self.frappe, "get_all", return_value=[str(PROJECTION_HEAD)]), patch.object(
            self.frappe,
            "get_doc",
            side_effect=get_doc,
        ):
            self.assertEqual(
                self.repository._projection_currentness(self.project, linked),
                self.module.QualityLinkReconciliationState.DRIFTED,
            )
            head.tenant_id = "foreign-tenant"
            self.assertEqual(
                self.repository._projection_currentness(self.project, linked),
                self.module.QualityLinkReconciliationState.UNAVAILABLE,
            )
        with patch.object(
            self.frappe,
            "get_all",
            return_value=[str(PROJECTION_HEAD), str(UUID(int=99))],
        ):
            self.assertEqual(
                self.repository._projection_currentness(self.project, linked),
                self.module.QualityLinkReconciliationState.UNAVAILABLE,
            )

    def test_reconciliation_is_one_closed_fact_and_never_substitutes_identity(self) -> None:
        revision = self.module.QualityLinkRevision(
            UUID("00000000-0000-4000-8000-00000000c619"),
            "e" * 64,
            1,
            None,
            self.source,
            self.observation,
            self.module.QualityLinkState.LINKED,
            "quality@example.invalid",
            "trace-quality-link-repository",
            datetime(2026, 8, 26, tzinfo=UTC),
        )
        for source_state, projection_state, expected in (
            ("current", "current", "current"),
            ("drifted", "current", "drifted"),
            ("current", "unavailable", "unavailable"),
        ):
            with self.subTest(expected=expected), patch.object(
                self.repository,
                "_source_currentness",
                return_value=self.module.QualityLinkReconciliationState(source_state),
            ), patch.object(
                self.repository,
                "_projection_currentness",
                return_value=self.module.QualityLinkReconciliationState(projection_state),
            ):
                result = self.repository._link_reconciliation(
                    self.project,
                    revision.payload(),
                )
                self.assertEqual(result["state"], expected)
                self.assertEqual(set(result), {"state", "reasonCode"})
                self.assertNotIn("global", str(result).casefold())
                self.assertNotIn("pass", str(result).casefold())
        malformed = {**revision.payload(), "source": {"unexpected": "value"}}
        self.assertEqual(
            self.repository._link_reconciliation(self.project, malformed),
            {
                "state": "unavailable",
                "reasonCode": "current_truth_unavailable",
            },
        )

    def projection_truth(
        self,
        *,
        version: int,
        observation_id: UUID = OBSERVATION,
    ) -> tuple[object, object, object]:
        scope_id = self.observation.scope_global_id
        stream = {
            "tenantId": TENANT,
            "projectGlobalId": str(PROJECT),
            "scopeKind": "trial_round",
            "scopeGlobalId": str(scope_id),
            "projectionKind": "formal_quality_status",
            "sourceObjectType": "Quality Inspection",
            "sourceObjectId": "QI-opaque",
        }
        observation_snapshot = {"observation": str(observation_id)}
        observation_hash = self.module.canonical_payload_hash(observation_snapshot)
        head_snapshot = {
            "schemaVersion": 1,
            "globalId": str(PROJECTION_HEAD),
            **stream,
            "streamKeyHash": self.module.canonical_payload_hash(stream),
            "currentObservationGlobalId": str(observation_id),
            "lastRefreshObservationGlobalId": str(observation_id),
            "currentSourceVersion": str(version + 4),
            "currentSourceModifiedAt": "2026-08-26T00:00:00Z",
            "currentPayloadHash": "c" * 64,
            "availability": "available",
            "freshness": "fresh",
            "freshnessPolicyRef": "formal_quality_v1",
            "optimisticVersion": version,
            "updatedAt": "2026-08-26T00:00:00Z",
        }
        head_hash = self.module.canonical_payload_hash(head_snapshot)
        head = types.SimpleNamespace(
            global_id=PROJECTION_HEAD,
            tenant_id=TENANT,
            project_global_id=PROJECT,
            scope_kind="trial_round",
            scope_global_id=scope_id,
            projection_kind="formal_quality_status",
            source_object_type="Quality Inspection",
            source_object_id="QI-opaque",
            stream_key_hash=head_snapshot["streamKeyHash"],
            current_observation=observation_id,
            current_source_version=str(version + 4),
            current_payload_hash="c" * 64,
            availability="available",
            freshness="fresh",
            freshness_policy_ref="formal_quality_v1",
            optimistic_version=version,
            head_snapshot=head_snapshot,
            head_hash=head_hash,
        )
        observation = types.SimpleNamespace(
            global_id=observation_id,
            tenant_id=TENANT,
            project_global_id=PROJECT,
            scope_kind="trial_round",
            scope_global_id=scope_id,
            projection_kind="formal_quality_status",
            source_object_type="Quality Inspection",
            source_object_id="QI-opaque",
            source_system="ERPNEXT",
            target_system="NPI_ONE",
            adapter_mode="sandbox",
            availability="available",
            freshness="fresh",
            disposition="applied_current",
            source_version=str(version + 4),
            payload_hash="c" * 64,
            observation_snapshot=observation_snapshot,
            observation_hash=observation_hash,
            payload={
                "values": {
                    "recordKind": "quality_inspection",
                    "statusCode": "Completed",
                    "resultCode": "Accepted",
                    "observedAt": "2026-08-26T00:00:00Z",
                }
            },
        )
        linked = replace(
            self.observation,
            observation_global_id=observation_id,
            head_optimistic_version=version,
            source_version=str(version + 4),
            observation_hash=observation_hash,
            head_hash=head_hash,
        )
        return head, observation, linked


if __name__ == "__main__":
    unittest.main()
