from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

sys.path[:0] = ["apps/npi_core", "apps/npi_integration"]

from npi_core.foundation.errors import RequestValidationFailed
from npi_integration.publish_request.domain import (
    FutureRetryDirective,
    MappingObservation,
    PublishLineInput,
    PublishMappingState,
    PublishNodeOperation,
    PublishNodeResultState,
    PublishPolicyReference,
    PublishRequestState,
    PublishTargetMode,
    ReleasedEbomEvidence,
    TargetFaultKind,
    classify_target_fault,
    create_mock_publish_request,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
NOW = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)


class Phase5PublishRequestDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = UUID("00000000-0000-4000-8000-000000000501")
        self.ebom_id = UUID("00000000-0000-4000-8000-000000000502")
        self.revision_id = UUID("00000000-0000-4000-8000-000000000503")
        self.release_event_id = UUID("00000000-0000-4000-8000-000000000504")
        self.policy_id = UUID("00000000-0000-4000-8000-000000000505")
        self.request_policy_id = UUID("00000000-0000-4000-8000-000000000506")
        self.line_a_id = UUID("00000000-0000-4000-8000-000000000507")
        self.line_b_id = UUID("00000000-0000-4000-8000-000000000508")
        self.request_id = UUID("00000000-0000-4000-8000-000000000509")
        self.global_id = UUID("00000000-0000-4000-8000-000000000510")

    def evidence(self, **changes: object) -> ReleasedEbomEvidence:
        values: dict[str, object] = {
            "project_global_id": self.project_id,
            "ebom_global_id": self.ebom_id,
            "ebom_version": 5,
            "revision_global_id": self.revision_id,
            "revision_number": 2,
            "revision_snapshot_hash": HASH_A,
            "lifecycle_version": 4,
            "release_event_global_id": self.release_event_id,
            "release_event_hash": HASH_B,
            "ebom_policy_global_id": self.policy_id,
            "ebom_policy_version": 1,
            "ebom_policy_snapshot_hash": HASH_C,
            "approval_evidence_ids": (self.release_event_id,),
            "released_at": NOW,
        }
        values.update(changes)
        return ReleasedEbomEvidence(**values)  # type: ignore[arg-type]

    @staticmethod
    def policy() -> PublishPolicyReference:
        return PublishPolicyReference(
            UUID("00000000-0000-4000-8000-000000000506"),
            1,
            HASH_D,
        )

    def lines(self) -> tuple[PublishLineInput, PublishLineInput]:
        return (
            PublishLineInput(
                global_id=self.line_b_id,
                line_key="B-20",
                parent_line_key="A-10",
                engineering_item_id="ENG-B-20",
                description="Retainer",
                quantity="2",
                engineering_uom="pcs",
                alternate_for_line_key=None,
                alternate_group_key="ALT-1",
                attributes=(("material", "P20"),),
            ),
            PublishLineInput(
                global_id=self.line_a_id,
                line_key="A-10",
                parent_line_key=None,
                engineering_item_id="ENG-A-10",
                description="Mold base",
                quantity="1.25",
                engineering_uom="pcs",
                attributes=(("finish", "ground"), ("material", "steel")),
            ),
        )

    def request(self, **changes: object):
        values: dict[str, object] = {
            "policy": self.policy(),
            "evidence": self.evidence(),
            "lines": self.lines(),
            "actor_user_id": "engineer@example.invalid",
            "request_id": self.request_id,
            "trace_id": "trace-p505-domain-001",
            "idempotency_key_hash": HASH_A,
            "global_id": self.global_id,
            "created_at": NOW,
        }
        values.update(changes)
        return create_mock_publish_request(**values)  # type: ignore[arg-type]

    def test_mock_request_binds_exact_release_and_sorts_stable_nodes(self) -> None:
        request = self.request()

        self.assertEqual(request.state, PublishRequestState.VALIDATED)
        self.assertEqual(request.target_mode, PublishTargetMode.MOCK)
        self.assertFalse(request.dispatch_allowed)
        self.assertEqual(
            [node.line.line_key for node in request.nodes],
            ["A-10", "B-20"],
        )
        self.assertTrue(
            all(
                node.operations
                == (
                    PublishNodeOperation.CREATE_ITEM,
                    PublishNodeOperation.CREATE_OR_UPDATE_MBOM,
                )
                for node in request.nodes
            )
        )
        body = request.public_dict()
        self.assertEqual(body["operation"], "publish_released_ebom_item_mbom")
        self.assertEqual(body["state"], "validated")
        self.assertEqual(body["targetMode"], "mock")
        self.assertFalse(body["dispatchAllowed"])
        self.assertEqual(body["capabilities"]["dispatch"], False)  # type: ignore[index]
        self.assertEqual(body["capabilities"]["retry"], False)  # type: ignore[index]
        self.assertEqual(len(body["ownedFields"]), 8)  # type: ignore[arg-type]
        first_result = body["nodes"][0]["results"][0]  # type: ignore[index]
        self.assertEqual(first_result["state"], "validated")
        self.assertEqual(first_result["attemptNumber"], 0)
        self.assertFalse(first_result["phase5DispatchAllowed"])
        self.assertIsNone(first_result["formalItemCode"])
        self.assertIsNone(first_result["formalMbomId"])
        self.assertEqual(
            body["releasedEbom"]["revisionGlobalId"],  # type: ignore[index]
            str(self.revision_id),
        )

    def test_payload_hash_is_order_independent_but_exact_input_sensitive(self) -> None:
        first = self.request()
        second = self.request(lines=tuple(reversed(self.lines())))
        changed = self.request(evidence=self.evidence(revision_snapshot_hash=HASH_D))

        self.assertEqual(first.payload_hash, second.payload_hash)
        self.assertNotEqual(first.payload_hash, changed.payload_hash)

    def test_mock_public_result_never_exposes_known_formal_identifiers(self) -> None:
        mapping = MappingObservation(
            state=PublishMappingState.CURRENT,
            version=3,
            formal_item_code="ITEM-SANDBOX-001",
            formal_mbom_id="BOM-SANDBOX-001",
            target_version="7",
            observed_at=NOW,
        )
        request = self.request(mappings={self.line_a_id: mapping})
        first = request.public_dict()["nodes"][0]  # type: ignore[index]

        self.assertEqual(
            request.nodes[0].operations,
            (
                PublishNodeOperation.UPDATE_ITEM_ENGINEERING_FIELDS,
                PublishNodeOperation.CREATE_OR_UPDATE_MBOM,
            ),
        )
        self.assertIsNone(first["mapping"]["formalItemCode"])
        self.assertIsNone(first["mapping"]["formalMbomId"])
        self.assertIsNone(first["mapping"]["targetVersion"])
        self.assertNotIn("credential", str(request.public_dict()).casefold())
        self.assertNotIn("endpoint", str(request.public_dict()).casefold())

    def test_stale_mapping_is_visible_and_blocks_only_its_node(self) -> None:
        request = self.request(
            mappings={
                self.line_a_id: MappingObservation(
                    state=PublishMappingState.STALE,
                    version=4,
                    formal_item_code="ITEM-OLD-001",
                    target_version="6",
                    observed_at=NOW,
                )
            }
        )

        self.assertEqual(request.state, PublishRequestState.MANUAL_INTERVENTION)
        self.assertEqual(request.nodes[0].operations, ())
        self.assertEqual(
            request.nodes[0].result_state,
            PublishNodeResultState.BLOCKED_MAPPING,
        )
        self.assertEqual(
            request.nodes[1].result_state,
            PublishNodeResultState.VALIDATED,
        )

    def test_mock_state_and_dispatch_validation_raises(self) -> None:
        request = self.request()
        with self.assertRaises(RequestValidationFailed):
            replace(request, state=PublishRequestState.SUCCEEDED)
        with self.assertRaises(RequestValidationFailed):
            replace(request, dispatch_allowed=True)
        with self.assertRaises(ValueError):
            PublishTargetMode("production")

    def test_release_event_must_be_part_of_approval_snapshot(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            self.evidence(approval_evidence_ids=(uuid4(),))

    def test_line_hash_tampering_and_noncanonical_quantity_fail_closed(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            PublishLineInput(
                global_id=self.line_a_id,
                line_key="A-10",
                parent_line_key=None,
                engineering_item_id="ENG-A-10",
                description="Mold base",
                quantity="1",
                engineering_uom="pcs",
                line_hash=HASH_A,
            )
        fixed_scale = replace(self.lines()[1], quantity="1.000", line_hash="")
        self.assertEqual(fixed_scale.quantity, "1.000")
        for quantity in ("0", "01", " 1", "-1", "NaN"):
            with self.subTest(quantity=quantity), self.assertRaises(
                RequestValidationFailed
            ):
                replace(self.lines()[1], quantity=quantity, line_hash="")

    def test_mapping_and_request_membership_are_exact(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            MappingObservation(
                state=PublishMappingState.UNMAPPED,
                formal_item_code="ITEM-INVALID",
            )
        with self.assertRaises(RequestValidationFailed):
            MappingObservation(state=PublishMappingState.CURRENT)
        with self.assertRaises(RequestValidationFailed):
            self.request(mappings={uuid4(): MappingObservation()})

    def test_actor_trace_and_evidence_versions_are_strict(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            self.request(actor_user_id="external user")
        with self.assertRaises(RequestValidationFailed):
            self.request(trace_id="short")
        with self.assertRaises(RequestValidationFailed):
            self.evidence(lifecycle_version=0)

    def test_required_fault_taxonomy_is_closed_and_never_dispatches(self) -> None:
        classifications = {
            kind: classify_target_fault(kind) for kind in TargetFaultKind
        }
        self.assertEqual(len(classifications), 10)
        self.assertTrue(
            all(not item.phase5_dispatch_allowed for item in classifications.values())
        )

        timeout = classifications[TargetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT]
        self.assertEqual(
            timeout.request_state,
            PublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
        )
        self.assertEqual(
            timeout.future_retry_directive,
            FutureRetryDirective.RECONCILE_BEFORE_RETRY,
        )
        self.assertTrue(timeout.reconciliation_required)
        self.assertFalse(timeout.future_retryable)

        limited = classifications[TargetFaultKind.RATE_LIMITED]
        self.assertEqual(limited.future_retry_directive, FutureRetryDirective.RETRY_AFTER)
        self.assertTrue(limited.future_retryable)
        self.assertTrue(limited.retry_after_required)

        business = classifications[TargetFaultKind.BUSINESS_VALIDATION]
        self.assertEqual(business.request_state, PublishRequestState.FAILED_FINAL)
        self.assertEqual(
            business.future_retry_directive,
            FutureRetryDirective.MANUAL_CORRECTION,
        )

        partial = classifications[TargetFaultKind.PARTIAL_NODE_SUCCESS]
        self.assertEqual(
            partial.request_state,
            PublishRequestState.PARTIALLY_SUCCEEDED,
        )
        self.assertEqual(
            partial.future_retry_directive,
            FutureRetryDirective.RETRY_FAILED_NODES_ONLY,
        )

        replay = classifications[TargetFaultKind.RESTART_REPLAY]
        self.assertEqual(
            replay.future_retry_directive,
            FutureRetryDirective.REPLAY_ORIGINAL_REQUEST,
        )


if __name__ == "__main__":
    unittest.main()
