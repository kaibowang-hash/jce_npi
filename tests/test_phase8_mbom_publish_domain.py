from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.mbom_publish.domain import (  # noqa: E402
    MBOM_PUBLISH_API_VERSION,
    MBOM_PUBLISH_OPERATION,
    CurrentMbomMapping,
    ItemMappingReadiness,
    ItemReadinessDisposition,
    MbomExecutionProfileReference,
    MbomFaultKind,
    MbomMappingDisposition,
    MbomMappingExpectation,
    MbomNodeObservation,
    MbomNodeResultState,
    MbomPublishContractError,
    MbomPublishRequestState,
    MbomResultAuthority,
    MbomSourceLine,
    MbomSourceRole,
    MbomSourceSnapshot,
    MbomTargetMode,
    MbomTargetSubmissionState,
    aggregate_node_results,
    canonical_hash,
    classify_adapter_fault,
    classify_mapping_observation,
    create_mbom_publish_request,
    item_mapping_set_hash,
    mbom_mapping_set_hash,
    synthetic_item_readiness,
)


NOW = datetime(2026, 8, 21, 13, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def line(
    value: int,
    key: str,
    parent: str | None,
    item: str,
    *,
    quantity: str = "1.000",
) -> MbomSourceLine:
    return MbomSourceLine(
        line_global_id=uid(value),
        stable_line_key=key,
        parent_line_key=parent,
        engineering_item_id=item,
        quantity=quantity,
        engineering_uom="Nos",
        alternates=(),
        effectivity=(("fromRevision", "A"),),
        attributes=(("material", "PA66"),),
        line_hash=f"{value:064x}",
    )


def source(*, lines: tuple[MbomSourceLine, ...] | None = None) -> MbomSourceSnapshot:
    return MbomSourceSnapshot(
        tenant_id="tenant-synthetic",
        project_global_id=uid(1),
        ebom_global_id=uid(2),
        phase5_publish_request_global_id=uid(3),
        phase5_publish_request_payload_hash="3" * 64,
        publish_policy_global_id=uid(4),
        publish_policy_version=2,
        publish_policy_snapshot_hash="4" * 64,
        revision_global_id=uid(5),
        revision_number=3,
        revision_snapshot_hash="5" * 64,
        lifecycle_version=4,
        release_event_global_id=uid(6),
        release_event_hash="6" * 64,
        approval_evidence_ids=(uid(6), uid(7)),
        released_at=NOW,
        lines=lines
        or (
            line(10, "ROOT", None, "ENG-ROOT"),
            line(11, "SUB", "ROOT", "ENG-SUB"),
            line(12, "LEAF-A", "SUB", "ENG-A", quantity="2.5000"),
            line(13, "LEAF-B", "ROOT", "ENG-B"),
        ),
    )


def profile(mode: MbomTargetMode) -> MbomExecutionProfileReference:
    return MbomExecutionProfileReference(
        profile_id=f"mbom-{mode.value}-v1",
        profile_version=1,
        target_mode=mode,
        environment_code=("disposable-test" if mode is MbomTargetMode.SYNTHETIC else mode.value),
        projection_policy_id="mbom-projection-v1",
        projection_policy_version=1,
        projection_policy_hash="7" * 64,
        snapshot_hash="8" * 64,
    )


def advanced_readiness(
    source_value: MbomSourceSnapshot,
    value: int,
    engineering_item_id: str,
) -> ItemMappingReadiness:
    return ItemMappingReadiness(
        engineering_item_id=engineering_item_id,
        disposition=ItemReadinessDisposition.ADVANCED,
        item_stream_key_hash=canonical_hash(
            {
                "schemaVersion": 1,
                "tenantId": source_value.tenant_id,
                "projectGlobalId": str(source_value.project_global_id),
                "engineeringItemId": engineering_item_id,
            }
        ),
        mapping_version=value,
        formal_item_code=f"ITEM-{value:04d}",
        target_version=str(value),
        observation_hash=f"{200 + value:064x}",
        authority=MbomResultAuthority.AUTHORITATIVE_SANDBOX,
        response_authenticated=True,
    )


def expectations(value: MbomSourceSnapshot) -> tuple[MbomMappingExpectation, ...]:
    return tuple(
        MbomMappingExpectation(
            assembly_source_key=value.assembly_source_key(key),
            stable_line_key=key,
            mapping_version=0,
            submission_state=MbomTargetSubmissionState.UNMAPPED_CREATE,
        )
        for key in value.assembly_line_keys
    )


class Phase8MbomPublishDomainTest(unittest.TestCase):
    def test_topology_is_deterministic_and_direct_parent_lines_are_assemblies(self) -> None:
        first = source()
        second = source(lines=tuple(reversed(first.lines)))
        self.assertEqual(first.source_hash, second.source_hash)
        self.assertEqual(first.topology_hash, second.topology_hash)
        self.assertEqual(first.assembly_line_keys, ("ROOT", "SUB"))
        self.assertEqual(first.roles["ROOT"], MbomSourceRole.ASSEMBLY)
        self.assertEqual(first.roles["SUB"], MbomSourceRole.ASSEMBLY)
        self.assertEqual(first.roles["LEAF-A"], MbomSourceRole.COMPONENT_ONLY)
        self.assertEqual(next(x for x in first.lines if x.stable_line_key == "LEAF-A").quantity, "2.5")
        self.assertNotEqual(first.assembly_source_key("ROOT"), first.assembly_source_key("SUB"))
        with self.assertRaisesRegex(MbomPublishContractError, "Only an assembly"):
            first.assembly_source_key("LEAF-A")

    def test_topology_rejects_missing_parent_multiple_root_duplicate_and_cycle(self) -> None:
        invalid_sets = (
            (line(1, "ROOT", None, "I-1"), line(2, "A", "MISSING", "I-2")),
            (line(1, "ROOT", None, "I-1"), line(2, "OTHER", None, "I-2")),
            (line(1, "ROOT", None, "I-1"), line(2, "ROOT", None, "I-2")),
            (
                line(1, "ROOT", None, "I-1"),
                line(2, "A", "B", "I-2"),
                line(3, "B", "A", "I-3"),
            ),
        )
        for values in invalid_sets:
            with self.subTest(values=values), self.assertRaises(MbomPublishContractError):
                source(lines=values)

    def test_source_hash_changes_for_release_topology_quantity_and_item_truth(self) -> None:
        base = source()
        changed_quantity = source(
            lines=tuple(
                replace(value, quantity="3", line_hash="f" * 64)
                if value.stable_line_key == "LEAF-A"
                else value
                for value in base.lines
            )
        )
        changed_release = replace(
            base,
            release_event_hash="a" * 64,
            source_hash="",
        )
        self.assertNotEqual(base.topology_hash, changed_quantity.topology_hash)
        self.assertNotEqual(base.source_hash, changed_quantity.source_hash)
        self.assertNotEqual(base.source_hash, changed_release.source_hash)

    def test_item_readiness_requires_exact_coverage_and_authoritative_sandbox_truth(self) -> None:
        value = source()
        ready = tuple(
            advanced_readiness(value, index + 1, item)
            for index, item in enumerate(value.engineering_item_ids)
        )
        digest = item_mapping_set_hash(value, tuple(reversed(ready)), target_mode=MbomTargetMode.SANDBOX)
        self.assertEqual(digest, item_mapping_set_hash(value, ready, target_mode=MbomTargetMode.SANDBOX))
        with self.assertRaisesRegex(MbomPublishContractError, "stream key"):
            item_mapping_set_hash(
                value,
                (replace(ready[0], item_stream_key_hash="0" * 64), *ready[1:]),
                target_mode=MbomTargetMode.SANDBOX,
            )
        with self.assertRaisesRegex(MbomPublishContractError, "cover every exact"):
            item_mapping_set_hash(value, ready[:-1], target_mode=MbomTargetMode.SANDBOX)
        with self.assertRaisesRegex(MbomPublishContractError, "every Item mapping"):
            item_mapping_set_hash(
                value,
                (*ready[:-1], replace(synthetic_item_readiness(value)[-1])),
                target_mode=MbomTargetMode.SANDBOX,
            )
        with self.assertRaisesRegex(MbomPublishContractError, "authenticated authoritative"):
            replace(ready[0], response_authenticated=False)

    def test_synthetic_item_references_are_source_derived_non_authoritative_and_deterministic(self) -> None:
        value = source()
        first = synthetic_item_readiness(value)
        second = synthetic_item_readiness(value)
        self.assertEqual(first, second)
        self.assertTrue(all(item.formal_item_code is None for item in first))
        self.assertTrue(all(item.mapping_version == 0 for item in first))
        self.assertTrue(all(item.synthetic_item_reference.startswith("synthetic-item-") for item in first))
        item_mapping_set_hash(value, first, target_mode=MbomTargetMode.SYNTHETIC)
        with self.assertRaisesRegex(MbomPublishContractError, "source-derived"):
            item_mapping_set_hash(
                value,
                tuple(
                    advanced_readiness(value, index + 1, item)
                    for index, item in enumerate(value.engineering_item_ids)
                ),
                target_mode=MbomTargetMode.SYNTHETIC,
            )

    def test_mapping_expectations_cover_only_assemblies_and_submitted_is_blocked(self) -> None:
        value = source()
        create = expectations(value)
        digest = mbom_mapping_set_hash(value, create)
        self.assertRegex(digest, r"^[a-f0-9]{64}$")
        update = replace(
            create[0],
            mapping_version=2,
            submission_state=MbomTargetSubmissionState.EDITABLE_DRAFT,
            formal_bom_id="BOM-SANDBOX-0001",
            target_version="2",
            observation_hash="a" * 64,
        )
        submitted = replace(
            update,
            submission_state=MbomTargetSubmissionState.SUBMITTED_IMMUTABLE,
        )
        self.assertEqual(update.intent.value, "update_draft")
        self.assertTrue(submitted.dispatch_blocked)
        mbom_mapping_set_hash(value, (submitted, create[1]))
        with self.assertRaisesRegex(MbomPublishContractError, "cover every exact"):
            mbom_mapping_set_hash(value, create[:1])
        with self.assertRaisesRegex(MbomPublishContractError, "unmapped"):
            replace(create[0], formal_bom_id="BOM-INVALID")

    def test_mock_request_is_local_only_and_synthetic_event_is_closed(self) -> None:
        value = source()
        not_ready = tuple(
            ItemMappingReadiness(
                engineering_item_id=item,
                disposition=ItemReadinessDisposition.NOT_READY,
                item_stream_key_hash=canonical_hash(
                    {
                        "schemaVersion": 1,
                        "tenantId": value.tenant_id,
                        "projectGlobalId": str(value.project_global_id),
                        "engineeringItemId": item,
                    }
                ),
                mapping_version=0,
            )
            for item in value.engineering_item_ids
        )
        mock = create_mbom_publish_request(
            source=value,
            item_readiness=not_ready,
            mbom_expectations=expectations(value),
            profile=profile(MbomTargetMode.MOCK),
            actor_user_id="engineer@example.invalid",
            service_actor_user_id=None,
            request_id=uid(30),
            trace_id="trace-mbom-domain-001",
            idempotency_key_hash="b" * 64,
            global_id=uid(31),
            created_at=NOW,
        )
        self.assertEqual(mock.state, MbomPublishRequestState.VALIDATED_MOCK)
        self.assertFalse(mock.dispatch_allowed)
        self.assertEqual(mock.payload_hash, canonical_hash(mock.payload()))
        with self.assertRaisesRegex(MbomPublishContractError, "Mock MBOM"):
            mock.event_payload()
        synthetic = create_mbom_publish_request(
            source=value,
            item_readiness=synthetic_item_readiness(value),
            mbom_expectations=expectations(value),
            profile=profile(MbomTargetMode.SYNTHETIC),
            actor_user_id="engineer@example.invalid",
            service_actor_user_id="worker@example.invalid",
            request_id=uid(32),
            trace_id="trace-mbom-domain-002",
            idempotency_key_hash="c" * 64,
            global_id=uid(33),
            created_at=NOW,
        )
        event = synthetic.event_payload()
        self.assertEqual(event["api_version"], MBOM_PUBLISH_API_VERSION)
        self.assertEqual(event["operation"], MBOM_PUBLISH_OPERATION)
        self.assertEqual(event["assembly_count"], 2)
        self.assertNotIn("formal_bom_id", str(event).casefold())
        self.assertNotIn("endpoint", str(event).casefold())
        self.assertEqual(synthetic.payload_hash, canonical_hash(synthetic.payload()))
        for changes in (
            {"item_mapping_set_hash": "0" * 64},
            {"mbom_mapping_set_hash": "0" * 64},
            {"semantic_effect_hash": "0" * 64},
            {"target_idempotency_key_hash": "0" * 64},
            {"payload_hash": "0" * 64},
            {"dispatch_allowed": False},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                MbomPublishContractError
            ):
                replace(synthetic, **changes)

    def test_request_payload_hash_stays_bound_to_create_command_across_legal_states(
        self,
    ) -> None:
        source_value = source()
        created = create_mbom_publish_request(
            source=source_value,
            item_readiness=synthetic_item_readiness(source_value),
            mbom_expectations=expectations(source_value),
            profile=profile(MbomTargetMode.SYNTHETIC),
            actor_user_id="engineer@example.invalid",
            service_actor_user_id="worker@example.invalid",
            request_id=uid(34),
            trace_id="trace-mbom-domain-state-hash",
            idempotency_key_hash="d" * 64,
            global_id=uid(35),
            created_at=NOW,
        )
        self.assertEqual(created.state, MbomPublishRequestState.QUEUED)
        self.assertEqual(created.payload_hash, canonical_hash(created.payload()))

        legal_states = tuple(
            state
            for state in MbomPublishRequestState
            if state is not MbomPublishRequestState.VALIDATED_MOCK
        )
        for state in legal_states:
            with self.subTest(state=state):
                rehydrated = replace(created, state=state)
                self.assertEqual(rehydrated.payload_hash, created.payload_hash)
                self.assertEqual(rehydrated.payload()["state"], state.value)

        with self.assertRaises(MbomPublishContractError):
            replace(created, trace_id="trace-mbom-domain-state-hash-tampered")

    def test_submitted_expectation_and_no_assembly_block_executable_request(self) -> None:
        value = source()
        mapped = replace(
            expectations(value)[0],
            mapping_version=1,
            submission_state=MbomTargetSubmissionState.SUBMITTED_IMMUTABLE,
            formal_bom_id="BOM-SANDBOX-0001",
            target_version="1",
            observation_hash="d" * 64,
        )
        with self.assertRaisesRegex(MbomPublishContractError, "submitted"):
            create_mbom_publish_request(
                source=value,
                item_readiness=synthetic_item_readiness(value),
                mbom_expectations=(mapped, expectations(value)[1]),
                profile=profile(MbomTargetMode.SYNTHETIC),
                actor_user_id="engineer@example.invalid",
                service_actor_user_id="worker@example.invalid",
                request_id=uid(40),
                trace_id="trace-mbom-domain-003",
                idempotency_key_hash="e" * 64,
                global_id=uid(41),
                created_at=NOW,
            )
        leaf_only = source(lines=(line(50, "ROOT", None, "ENG-ONLY"),))
        with self.assertRaisesRegex(MbomPublishContractError, "no assembly"):
            create_mbom_publish_request(
                source=leaf_only,
                item_readiness=synthetic_item_readiness(leaf_only),
                mbom_expectations=(),
                profile=profile(MbomTargetMode.SYNTHETIC),
                actor_user_id="engineer@example.invalid",
                service_actor_user_id="worker@example.invalid",
                request_id=uid(42),
                trace_id="trace-mbom-domain-004",
                idempotency_key_hash="f" * 64,
                global_id=uid(43),
                created_at=NOW,
            )

    def test_aggregate_preserves_partial_and_uncertain_node_truth(self) -> None:
        value = source()
        keys = value.assembly_line_keys
        synthetic = tuple(
            MbomNodeObservation(
                stable_line_key=key,
                assembly_source_key=value.assembly_source_key(key),
                state=MbomNodeResultState.SYNTHETIC_VERIFIED,
                authority=MbomResultAuthority.SYNTHETIC,
                response_authenticated=False,
                response_hash=f"{60 + index:064x}",
            )
            for index, key in enumerate(keys)
        )
        self.assertEqual(
            aggregate_node_results(synthetic),
            MbomPublishRequestState.SYNTHETIC_VERIFIED,
        )
        failed = replace(
            synthetic[1],
            state=MbomNodeResultState.FAILED_FINAL,
            authority=MbomResultAuthority.NONE,
            fault_kind=MbomFaultKind.BUSINESS_VALIDATION,
        )
        self.assertEqual(
            aggregate_node_results((synthetic[0], failed)),
            MbomPublishRequestState.PARTIALLY_SUCCEEDED,
        )
        uncertain = replace(
            failed,
            state=MbomNodeResultState.UNCERTAIN_AFTER_TIMEOUT,
            fault_kind=MbomFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
        )
        self.assertEqual(
            aggregate_node_results((synthetic[0], uncertain)),
            MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
        )
        for changes in (
            {"target_submission_state": MbomTargetSubmissionState.EDITABLE_DRAFT},
            {
                "authority": MbomResultAuthority.AUTHORITATIVE_SANDBOX,
                "response_authenticated": True,
            },
            {"fault_kind": MbomFaultKind.NONE},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                MbomPublishContractError
            ):
                replace(failed, **changes)
        with self.assertRaises(MbomPublishContractError):
            replace(uncertain, fault_kind=MbomFaultKind.BUSINESS_VALIDATION)

    def test_only_authenticated_authoritative_editable_draft_can_advance_mapping(self) -> None:
        value = source()
        expected = expectations(value)[0]
        synthetic = MbomNodeObservation(
            stable_line_key=expected.stable_line_key,
            assembly_source_key=expected.assembly_source_key,
            state=MbomNodeResultState.SYNTHETIC_VERIFIED,
            authority=MbomResultAuthority.SYNTHETIC,
            response_authenticated=False,
            response_hash="a" * 64,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=expected,
                current=None,
                observation=synthetic,
            ),
            MbomMappingDisposition.RESULT_NOT_SUCCESS,
        )
        authoritative = replace(
            synthetic,
            state=MbomNodeResultState.SUCCEEDED_AUTHORITATIVE,
            authority=MbomResultAuthority.AUTHORITATIVE_SANDBOX,
            response_authenticated=True,
            formal_bom_id="BOM-SANDBOX-0001",
            target_version="1",
            target_submission_state=MbomTargetSubmissionState.EDITABLE_DRAFT,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=expected,
                current=None,
                observation=authoritative,
            ),
            MbomMappingDisposition.ADVANCE,
        )
        with self.assertRaisesRegex(MbomPublishContractError, "Synthetic MBOM proof"):
            replace(synthetic, formal_bom_id="BOM-FAKE")

    def test_mapping_compare_and_set_blocks_stale_identity_and_submitted_truth(self) -> None:
        value = source()
        create = expectations(value)[0]
        expected = replace(
            create,
            mapping_version=2,
            submission_state=MbomTargetSubmissionState.EDITABLE_DRAFT,
            formal_bom_id="BOM-SANDBOX-0001",
            target_version="2",
            observation_hash="b" * 64,
        )
        current = CurrentMbomMapping(
            2,
            "BOM-SANDBOX-0001",
            "2",
            MbomTargetSubmissionState.EDITABLE_DRAFT,
            "b" * 64,
        )
        observed = MbomNodeObservation(
            stable_line_key=expected.stable_line_key,
            assembly_source_key=expected.assembly_source_key,
            state=MbomNodeResultState.SUCCEEDED_AUTHORITATIVE,
            authority=MbomResultAuthority.AUTHORITATIVE_SANDBOX,
            response_authenticated=True,
            response_hash="c" * 64,
            formal_bom_id="BOM-SANDBOX-0001",
            target_version="3",
            target_submission_state=MbomTargetSubmissionState.EDITABLE_DRAFT,
        )
        self.assertEqual(
            classify_mapping_observation(expectation=expected, current=current, observation=observed),
            MbomMappingDisposition.ADVANCE,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=expected,
                current=current,
                observation=replace(
                    observed,
                    stable_line_key="OTHER",
                    assembly_source_key="0" * 64,
                ),
            ),
            MbomMappingDisposition.EXPECTATION_CONFLICT,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=replace(expected, mapping_version=3),
                current=current,
                observation=observed,
            ),
            MbomMappingDisposition.EXPECTATION_CONFLICT,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=expected,
                current=current,
                observation=replace(observed, formal_bom_id="BOM-OTHER"),
            ),
            MbomMappingDisposition.TARGET_IDENTITY_CONFLICT,
        )
        self.assertEqual(
            classify_mapping_observation(
                expectation=replace(expected, submission_state=MbomTargetSubmissionState.SUBMITTED_IMMUTABLE),
                current=replace(current, submission_state=MbomTargetSubmissionState.SUBMITTED_IMMUTABLE),
                observation=observed,
            ),
            MbomMappingDisposition.SUBMITTED_BLOCK,
        )

    def test_fault_matrix_never_authorizes_redispatch(self) -> None:
        uncertain = classify_adapter_fault(adapter_boundary_crossed=True, timed_out=True)
        self.assertEqual(uncertain.request_state, MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT)
        self.assertTrue(uncertain.reconciliation_required)
        self.assertFalse(uncertain.redispatch_allowed)
        invalid = classify_adapter_fault(
            adapter_boundary_crossed=True,
            http_status=200,
            response_contract_valid=False,
        )
        self.assertEqual(invalid.fault_kind, MbomFaultKind.RESPONSE_CONTRACT_INVALID)
        self.assertFalse(invalid.redispatch_allowed)
        rate = classify_adapter_fault(adapter_boundary_crossed=False, http_status=429)
        self.assertEqual(rate.request_state, MbomPublishRequestState.FAILED_RETRYABLE)
        self.assertFalse(rate.redispatch_allowed)
        success = classify_adapter_fault(adapter_boundary_crossed=True, http_status=200)
        self.assertEqual(success.request_state, MbomPublishRequestState.SUCCEEDED)
        self.assertEqual(success.fault_kind, MbomFaultKind.NONE)
        pre_boundary_timeout = classify_adapter_fault(
            adapter_boundary_crossed=False,
            timed_out=True,
        )
        self.assertEqual(
            pre_boundary_timeout.request_state,
            MbomPublishRequestState.FAILED_RETRYABLE,
        )
        self.assertFalse(pre_boundary_timeout.redispatch_allowed)
        for changes in (
            {"adapter_boundary_crossed": 1},
            {"adapter_boundary_crossed": False, "timed_out": "yes"},
            {"adapter_boundary_crossed": False, "http_status": 99},
            {"adapter_boundary_crossed": False, "http_status": 600},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                MbomPublishContractError
            ):
                classify_adapter_fault(**changes)


if __name__ == "__main__":
    unittest.main()
