from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path
from uuid import uuid5

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.production_transition.request_validation import (
    HANDOVER_SOURCE_KINDS,
    MANDATORY_EXTERNAL_PROVIDER_KINDS,
    MANDATORY_EXTERNAL_PROVIDER_ORDER,
    assert_mandatory_provider_kinds,
    parse_acknowledgement_intent,
    parse_create_handover_request,
    parse_create_observation_request,
    parse_create_policy_request,
    parse_edit_policy_request,
    parse_exact_source_selection,
    parse_handover_revision_request,
    parse_manifest_source_selection,
    parse_manifest_source_selections,
    parse_next_policy_version_request,
    parse_observation_revision_request,
    parse_publish_policy_request,
)
from npi_core.production_transition.response_validation import (
    ProductionTransitionResponseInvalid,
    validate_acknowledgement_response,
    validate_command_response,
    validate_fully_acknowledged_projection,
    validate_handover_acknowledgement_projection,
    validate_handover_package_response,
    validate_observation_projection,
    validate_observation_revision_response,
    validate_policy_catalog_response,
    validate_policy_version_response,
    validate_receipt_response,
    validate_unavailable_provider_responses,
    validate_workspace_response,
)


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")

UUID_1 = "11111111-1111-4111-8111-111111111111"
UUID_2 = "22222222-2222-4222-8222-222222222222"
HASH_1 = "a" * 64


def schema(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  schemas:\n"))
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 :])
    return OPENAPI[start:] if match is None else OPENAPI[start : start + 1 + match.start()]


def path_block(path: str) -> str:
    paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
    start = paths.index(f"  {path}:\n")
    match = re.search(r"\n  /[^\n]+:\n", paths[start + 1 :])
    return paths[start:] if match is None else paths[start : start + 1 + match.start()]


def response(name: str) -> str:
    start = OPENAPI.index(f"    {name}:\n", OPENAPI.index("  responses:\n"))
    schemas_start = OPENAPI.index("  schemas:\n")
    match = re.search(r"\n    [A-Z][A-Za-z0-9]+:\n", OPENAPI[start + 1 : schemas_start])
    return (
        OPENAPI[start:schemas_start]
        if match is None
        else OPENAPI[start : start + 1 + match.start()]
    )


def inline_required_fields(name: str) -> set[str]:
    match = re.search(r"^      required: \[([^\]]+)\]$", schema(name), re.MULTILINE)
    if match is None:
        raise AssertionError(f"{name} must declare one inline closed required list")
    return {value.strip() for value in match.group(1).split(",")}


def unavailable_providers() -> list[dict[str, str]]:
    return [
        {
            "kind": "actual_sop",
            "state": "unavailable",
            "reasonCode": "actual_sop_provider_unavailable",
            "sourceIdentity": None,
            "observedAt": None,
            "value": None,
            "unit": None,
        },
        {
            "kind": "first_batch_yield",
            "state": "unavailable",
            "reasonCode": "first_batch_yield_provider_unavailable",
            "sourceIdentity": None,
            "observedAt": None,
            "value": None,
            "unit": None,
        },
        {
            "kind": "customer_complaint",
            "state": "unavailable",
            "reasonCode": "customer_complaint_provider_unavailable",
            "sourceIdentity": None,
            "observedAt": None,
            "value": None,
            "unit": None,
        },
        {
            "kind": "production_cycle_time",
            "state": "unavailable",
            "reasonCode": "production_cycle_time_provider_unavailable",
            "sourceIdentity": None,
            "observedAt": None,
            "value": None,
            "unit": None,
        },
        {
            "kind": "tooling_stability",
            "state": "unavailable",
            "reasonCode": "tooling_stability_provider_unavailable",
            "sourceIdentity": None,
            "observedAt": None,
            "value": None,
            "unit": None,
        },
    ]


def policy_definition_payload() -> dict[str, object]:
    from tests.test_phase7_production_transition_domain import draft_policy

    snapshot = draft_policy().snapshot_payload()
    return {
        "applicability": copy.deepcopy(snapshot["applicability"]),
        "receivingGroups": copy.deepcopy(snapshot["receivingGroups"]),
        "acknowledgementSlots": copy.deepcopy(snapshot["acknowledgementSlots"]),
        "handoverRequirements": copy.deepcopy(snapshot["handoverRequirements"]),
        "observationSourceRules": copy.deepcopy(snapshot["observationSourceRules"]),
        "observationWindowDays": snapshot["observationWindowDays"],
    }


class Phase7ProductionTransitionContractTest(unittest.TestCase):
    def test_receipt_validation_binds_all_operations_target_project_and_hash(self) -> None:
        from tests.test_phase7_production_transition_domain import (
            ACTION,
            CONTEXT_SOURCE,
            NOW,
            PROJECT_ID,
            RECEIVER_MEMBER,
            SENDER_MEMBER,
            SENDER_ROLE,
            SOURCE,
            draft_policy,
            package,
            policy,
            project,
            slots,
            uid,
        )
        from npi_core.production_transition.domain import (
            create_handover_acknowledgement,
            create_handover_package_successor,
            create_observation_period_revision,
            create_observation_period_successor,
        )

        def response_value(value: object) -> dict[str, object]:
            return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}

        created_policy = draft_policy()
        edited_policy = created_policy.edit_draft(
            expected_version=1,
            title="Receipt edit",
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(110),
            trace_id="trace-p706-receipt-edit",
        )
        published_policy = policy()
        next_policy = published_policy.next_draft(
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(111),
            trace_id="trace-p706-receipt-next",
        )
        created_package = package()
        revised_package = create_handover_package_successor(
            created_package,
            project=project(),
            policy=published_policy,
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset(
                {SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}
            ),
            reason="Verify receipt successor binding.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(112),
            trace_id="trace-p706-receipt-handover",
        )
        acknowledgement = create_handover_acknowledgement(
            revised_package,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(113),
            trace_id="trace-p706-receipt-ack",
        )
        created_observation = create_observation_period_revision(
            observation_global_id=uid(114),
            tenant_id="tenant-a",
            project=project(),
            policy=published_policy,
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Verify observation receipt binding.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(115),
            trace_id="trace-p706-receipt-observation",
        )
        revised_observation = create_observation_period_successor(
            created_observation,
            project=project(),
            policy=published_policy,
            handover_package_ref=None,
            context_references=(CONTEXT_SOURCE,),
            retrospective_references=(),
            retrospective_note="Review context only.",
            reason="Verify observation receipt successor binding.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(116),
            trace_id="trace-p706-receipt-observation-next",
        )
        project_id = str(PROJECT_ID)
        cases = (
            (
                "production_transition_policy.create",
                response_value(created_policy),
                str(created_policy.policy_global_id),
                None,
            ),
            (
                "production_transition_policy.edit",
                response_value(edited_policy),
                str(edited_policy.global_id),
                None,
            ),
            (
                "production_transition_policy.publish",
                response_value(published_policy),
                str(published_policy.global_id),
                None,
            ),
            (
                "production_transition_policy.next_version",
                response_value(next_policy),
                str(next_policy.global_id),
                None,
            ),
            (
                "production_handover.create",
                {
                    "projectGlobalId": project_id,
                    "handoverPackage": response_value(created_package),
                },
                str(created_package.global_id),
                project_id,
            ),
            (
                "production_handover.revise",
                {
                    "projectGlobalId": project_id,
                    "handoverPackage": response_value(revised_package),
                },
                str(revised_package.global_id),
                project_id,
            ),
            (
                "production_handover.acknowledge",
                {
                    "projectGlobalId": project_id,
                    "handoverPackage": response_value(revised_package),
                    "acknowledgement": response_value(acknowledgement),
                },
                str(acknowledgement.global_id),
                project_id,
            ),
            (
                "observation_period.create",
                {
                    "projectGlobalId": project_id,
                    "observationPeriod": response_value(created_observation),
                },
                str(created_observation.global_id),
                project_id,
            ),
            (
                "observation_period.revise",
                {
                    "projectGlobalId": project_id,
                    "observationPeriod": response_value(revised_observation),
                },
                str(revised_observation.global_id),
                project_id,
            ),
        )
        for operation, value, target_id, scoped_project_id in cases:
            with self.subTest(operation=operation):
                validate_receipt_response(
                    operation,
                    value,
                    target_global_id=target_id,
                    project_global_id=scoped_project_id,
                    tenant_id="tenant-a",
                )
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_receipt_response(
                        operation,
                        value,
                        target_global_id=target_id,
                        project_global_id=scoped_project_id,
                        tenant_id="tenant-b",
                    )
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_receipt_response(
                        operation,
                        {**value, "secret": "must-not-seal"},
                        target_global_id=target_id,
                        project_global_id=scoped_project_id,
                        tenant_id="tenant-a",
                    )
                missing = dict(value)
                missing.pop(next(iter(missing)))
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_receipt_response(
                        operation,
                        missing,
                        target_global_id=target_id,
                        project_global_id=scoped_project_id,
                        tenant_id="tenant-a",
                    )
                tampered = copy.deepcopy(value)
                if operation.startswith("production_transition_policy."):
                    tampered["snapshotHash"] = "0" * 64
                elif operation.startswith("production_handover"):
                    tampered["handoverPackage"]["snapshotHash"] = "0" * 64
                else:
                    tampered["observationPeriod"]["snapshotHash"] = "0" * 64
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_receipt_response(
                        operation,
                        tampered,
                        target_global_id=target_id,
                        project_global_id=scoped_project_id,
                        tenant_id="tenant-a",
                    )
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_receipt_response(
                        operation,
                        value,
                        target_global_id=str(uid(999)),
                        project_global_id=scoped_project_id,
                        tenant_id="tenant-a",
                    )
                if scoped_project_id is not None:
                    with self.assertRaises(ProductionTransitionResponseInvalid):
                        validate_receipt_response(
                            operation,
                            value,
                            target_global_id=target_id,
                            project_global_id=str(uid(998)),
                            tenant_id="tenant-a",
                        )
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_receipt_response(
                "production_handover.delete",
                cases[4][1],
                target_global_id=cases[4][2],
                project_global_id=project_id,
                tenant_id="tenant-a",
            )

    def test_checkpoint_two_request_parsers_are_closed_and_domain_compatible(self) -> None:
        from tests.test_phase7_production_transition_domain import policy

        published = policy()
        definition = policy_definition_payload()
        create = parse_create_policy_request(
            {
                "policyCode": "PROD-TRANSITION",
                "title": "Production transition policy",
                "definition": definition,
            }
        )
        self.assertEqual(create.policy_code, "PROD-TRANSITION")
        self.assertEqual(
            create.definition.applicability.snapshot_payload(),
            definition["applicability"],
        )
        self.assertEqual(
            [item.snapshot_payload() for item in create.definition.receiving_groups],
            definition["receivingGroups"],
        )
        self.assertEqual(
            [
                item.snapshot_payload()
                for item in create.definition.acknowledgement_slots
            ],
            definition["acknowledgementSlots"],
        )
        self.assertEqual(
            [item.snapshot_payload() for item in create.definition.handover_requirements],
            definition["handoverRequirements"],
        )
        self.assertEqual(
            [item.snapshot_payload() for item in create.definition.observation_source_rules],
            definition["observationSourceRules"],
        )

        edit = parse_edit_policy_request(
            {
                "expectedOptimisticVersion": 2,
                "title": "Edited production transition policy",
                "definition": definition,
            }
        )
        self.assertEqual(edit.expected_optimistic_version, 2)
        self.assertEqual(
            parse_publish_policy_request(
                {
                    "expectedOptimisticVersion": 2,
                    "expectedSnapshotHash": HASH_1,
                }
            ).expected_snapshot_hash,
            HASH_1,
        )
        self.assertEqual(
            parse_next_policy_version_request(
                {
                    "expectedPublishedVersion": 1,
                    "expectedPublishedSnapshotHash": HASH_1,
                }
            ).expected_published_version,
            1,
        )

        policy_ref = {
            "policyGlobalId": str(published.policy_global_id),
            "policyVersion": published.policy_version,
            "policySnapshotHash": published.snapshot_hash,
        }
        slot_assignments = [
            {
                "slotKey": "sender",
                "memberGlobalId": UUID_1,
                "memberExpectedVersion": 2,
                "roleAssignmentGlobalId": UUID_2,
                "roleExpectedVersion": 3,
            },
            {
                "slotKey": "receiver",
                "memberGlobalId": "33333333-3333-4333-8333-333333333333",
                "memberExpectedVersion": 2,
                "roleAssignmentGlobalId": "44444444-4444-4444-8444-444444444444",
                "roleExpectedVersion": 3,
            },
        ]
        manifest = [
            {
                "requirementKey": "open_work",
                "kind": "domain_work_item",
                "globalId": "55555555-5555-4555-8555-555555555555",
                "expectedVersion": 4,
            }
        ]
        handover_body = {
            "expectedProjectVersion": 7,
            "policy": policy_ref,
            "slotAssignments": slot_assignments,
            "manifestSources": manifest,
            "reason": "Freeze one exact package.",
        }
        handover = parse_create_handover_request(handover_body)
        self.assertEqual(handover.expected_project_version, 7)
        self.assertEqual(handover.policy.policy_snapshot_hash, published.snapshot_hash)
        self.assertEqual(
            tuple(item.slot_key for item in handover.slot_assignments),
            ("sender", "receiver"),
        )
        revised = parse_handover_revision_request(
            {
                "expectedRevisionGlobalId": UUID_1,
                "expectedSnapshotHash": HASH_1,
                "content": handover_body,
            }
        )
        self.assertEqual(revised.content, handover)

        observation_source = {
            "kind": "domain_work_item",
            "globalId": "55555555-5555-4555-8555-555555555555",
            "expectedVersion": 4,
        }
        observation = parse_create_observation_request(
            {
                "expectedProjectVersion": 7,
                "policy": policy_ref,
                "handover": None,
                "contextSources": [observation_source],
                "retrospectiveSources": [observation_source],
                "retrospectiveNote": "Review the retained evidence.",
                "reason": "Start the technical observation.",
            }
        )
        self.assertIsNone(observation.handover)
        self.assertEqual(
            observation.context_sources[0].expected_version,
            observation.retrospective_sources[0].expected_version,
        )

        nested_extras = []
        for field, nested in (
            ("applicability", "actualSop"),
            ("receivingGroups", "formalDepartmentId"),
            ("acknowledgementSlots", "quorum"),
            ("handoverRequirements", "callerRole"),
            ("observationSourceRules", "actualValue"),
        ):
            invalid = copy.deepcopy(definition)
            if isinstance(invalid[field], list):
                invalid[field][0][nested] = "forbidden"
            else:
                invalid[field][nested] = "forbidden"
            nested_extras.append(invalid)
        for invalid in nested_extras:
            with self.subTest(invalid_definition=invalid):
                with self.assertRaises(RequestValidationFailed):
                    parse_create_policy_request(
                        {
                            "policyCode": "PROD-TRANSITION",
                            "title": "Production transition policy",
                            "definition": invalid,
                        }
                    )

        duplicate_slot = copy.deepcopy(handover_body)
        duplicate_slot["slotAssignments"][1]["slotKey"] = "sender"
        with self.assertRaises(RequestValidationFailed):
            parse_create_handover_request(duplicate_slot)
        caller_owned = copy.deepcopy(handover_body)
        caller_owned["manifestSources"][0]["role"] = "caller_role"
        with self.assertRaises(RequestValidationFailed):
            parse_create_handover_request(caller_owned)
        conflicting_observation = {
            "expectedProjectVersion": 7,
            "policy": policy_ref,
            "handover": None,
            "contextSources": [observation_source],
            "retrospectiveSources": [
                {**observation_source, "expectedVersion": 5}
            ],
            "retrospectiveNote": None,
            "reason": "Reject conflicting exact versions.",
        }
        with self.assertRaises(RequestValidationFailed):
            parse_create_observation_request(conflicting_observation)
        external_truth = copy.deepcopy(conflicting_observation)
        external_truth["actualSop"] = "2026-08-14"
        with self.assertRaises(RequestValidationFailed):
            parse_create_observation_request(external_truth)

    def test_checkpoint_two_catalog_workspace_and_command_bindings_fail_closed(self) -> None:
        from tests.test_phase7_production_transition_domain import (
            ACTION,
            CONTEXT_SOURCE,
            NOW,
            PROJECT_ID,
            RECEIVER_MEMBER,
            SENDER_MEMBER,
            SENDER_ROLE,
            SOURCE,
            TENANT,
            draft_policy,
            package,
            policy,
            project,
            slots,
            uid,
        )
        from npi_core.production_transition.domain import (
            ExactVersionReference,
            create_handover_acknowledgement,
            create_handover_package_successor,
            create_observation_period_revision,
            create_observation_period_successor,
        )

        def response_value(value: object) -> dict[str, object]:
            return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}

        published = policy()
        catalog = {
            "projectGlobalId": str(PROJECT_ID),
            "policies": [response_value(published)],
        }
        self.assertEqual(
            validate_policy_catalog_response(
                catalog,
                project_global_id=str(PROJECT_ID),
                tenant_id=TENANT,
            ),
            catalog,
        )
        invalid_catalog = copy.deepcopy(catalog)
        invalid_catalog["policies"][0]["publicationState"] = "draft"
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_policy_catalog_response(invalid_catalog, tenant_id=TENANT)

        first_package = package()
        second_package = create_handover_package_successor(
            first_package,
            project=project(),
            policy=published,
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset(
                {SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}
            ),
            reason="Retain an exact handover successor.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(710),
            trace_id="trace-p706-workspace-handover",
        )
        handover_ref = ExactVersionReference(
            second_package.global_id,
            second_package.handover_version,
            second_package.snapshot_hash,
        )
        first_observation = create_observation_period_revision(
            observation_global_id=uid(711),
            tenant_id=TENANT,
            project=project(),
            policy=published,
            handover_package_ref=handover_ref,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Start one independent observation stream.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(712),
            trace_id="trace-p706-workspace-observation",
        )
        second_observation = create_observation_period_successor(
            first_observation,
            project=project(),
            policy=published,
            handover_package_ref=handover_ref,
            context_references=(CONTEXT_SOURCE,),
            retrospective_references=(),
            retrospective_note="Retain technical review context.",
            reason="Append one exact observation successor.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(713),
            trace_id="trace-p706-workspace-observation-next",
        )

        def view(value: object) -> dict[str, object]:
            return {
                "revision": response_value(value),
                "acknowledgements": [],
                "fullyAcknowledged": False,
            }

        workspace = {
            "projectGlobalId": str(PROJECT_ID),
            "currentHandover": view(second_package),
            "handoverHistory": [view(first_package), view(second_package)],
            "currentObservation": response_value(second_observation),
            "observationHistory": [
                response_value(first_observation),
                response_value(second_observation),
            ],
            "unavailableProviders": unavailable_providers(),
            "permissions": {
                "canManagePolicies": True,
                "canCreateHandover": True,
                "canReviseHandover": True,
                "canAcknowledgeSlots": ["sender"],
                "canCreateObservation": True,
                "canReviseObservation": True,
            },
        }
        validated = validate_workspace_response(
            workspace,
            project_global_id=str(PROJECT_ID),
            tenant_id=TENANT,
        )
        self.assertEqual(validated, workspace)
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_workspace_response(
                workspace,
                project_global_id=str(PROJECT_ID),
                tenant_id="tenant-b",
            )
        for mutation in ("history_order", "current_not_tip", "provider_order", "permission_shape"):
            invalid = copy.deepcopy(workspace)
            if mutation == "history_order":
                invalid["handoverHistory"].reverse()
            elif mutation == "current_not_tip":
                invalid["currentObservation"] = invalid["observationHistory"][0]
            elif mutation == "provider_order":
                invalid["unavailableProviders"].reverse()
            else:
                invalid["permissions"]["canApprove"] = True
            with self.subTest(mutation=mutation):
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_workspace_response(invalid, tenant_id=TENANT)

        created_policy = draft_policy()
        edited_policy = created_policy.edit_draft(
            expected_version=1,
            title="Edited policy",
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(714),
            trace_id="trace-p706-command-edit",
        )
        next_policy = published.next_draft(
            changed_by_user_id="editor@example.invalid",
            changed_at=NOW,
            request_id=uid(715),
            trace_id="trace-p706-command-next",
        )
        acknowledgement = create_handover_acknowledgement(
            second_package,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(716),
            trace_id="trace-p706-command-ack",
        )
        project_id = str(PROJECT_ID)
        validate_command_response(
            "production_transition_policy.create",
            response_value(created_policy),
            target_global_id=str(created_policy.policy_global_id),
            tenant_id=TENANT,
        )
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_command_response(
                "production_transition_policy.create",
                response_value(created_policy),
                target_global_id=str(created_policy.policy_global_id),
                tenant_id="tenant-b",
            )
        validate_command_response(
            "production_transition_policy.edit",
            response_value(edited_policy),
            target_global_id=str(edited_policy.global_id),
            tenant_id=TENANT,
            policy_global_id=str(edited_policy.policy_global_id),
            policy_version=edited_policy.policy_version,
        )
        validate_command_response(
            "production_transition_policy.publish",
            response_value(published),
            target_global_id=str(published.global_id),
            tenant_id=TENANT,
            policy_global_id=str(published.policy_global_id),
            policy_version=published.policy_version,
            policy_snapshot_hash=created_policy.snapshot_hash,
        )
        validate_command_response(
            "production_transition_policy.next_version",
            response_value(next_policy),
            target_global_id=str(next_policy.global_id),
            tenant_id=TENANT,
            policy_global_id=str(published.policy_global_id),
            policy_version=published.policy_version,
            policy_snapshot_hash=published.snapshot_hash,
        )
        validate_command_response(
            "production_handover.create",
            {
                "projectGlobalId": project_id,
                "handoverPackage": response_value(first_package),
            },
            target_global_id=str(first_package.global_id),
            tenant_id=TENANT,
            project_global_id=project_id,
            policy_global_id=str(published.policy_global_id),
            policy_version=published.policy_version,
            policy_snapshot_hash=published.snapshot_hash,
        )
        validate_command_response(
            "production_handover.revise",
            {
                "projectGlobalId": project_id,
                "handoverPackage": response_value(second_package),
            },
            target_global_id=str(second_package.global_id),
            tenant_id=TENANT,
            project_global_id=project_id,
            policy_global_id=str(published.policy_global_id),
            policy_version=published.policy_version,
            policy_snapshot_hash=published.snapshot_hash,
            handover_global_id=str(second_package.handover_global_id),
            expected_revision_global_id=str(first_package.global_id),
            expected_snapshot_hash=first_package.snapshot_hash,
        )
        validate_command_response(
            "production_handover.acknowledge",
            {
                "projectGlobalId": project_id,
                "handoverPackage": response_value(second_package),
                "acknowledgement": response_value(acknowledgement),
            },
            target_global_id=str(acknowledgement.global_id),
            tenant_id=TENANT,
            project_global_id=project_id,
            handover_global_id=str(second_package.handover_global_id),
            handover_version=second_package.handover_version,
            expected_revision_global_id=str(second_package.global_id),
            expected_snapshot_hash=second_package.snapshot_hash,
            slot_key="sender",
        )
        validate_command_response(
            "observation_period.create",
            {
                "projectGlobalId": project_id,
                "observationPeriod": response_value(first_observation),
            },
            target_global_id=str(first_observation.global_id),
            tenant_id=TENANT,
            project_global_id=project_id,
            policy_global_id=str(published.policy_global_id),
            policy_version=published.policy_version,
            policy_snapshot_hash=published.snapshot_hash,
            handover_global_id=str(second_package.handover_global_id),
            handover_version=second_package.handover_version,
            handover_revision_global_id=str(second_package.global_id),
            handover_snapshot_hash=second_package.snapshot_hash,
        )
        validate_command_response(
            "observation_period.revise",
            {
                "projectGlobalId": project_id,
                "observationPeriod": response_value(second_observation),
            },
            target_global_id=str(second_observation.global_id),
            tenant_id=TENANT,
            project_global_id=project_id,
            observation_global_id=str(second_observation.observation_global_id),
            expected_revision_global_id=str(first_observation.global_id),
            expected_snapshot_hash=first_observation.snapshot_hash,
        )

        wrong_binding = {
            "operation": "production_handover.revise",
            "value": {
                "projectGlobalId": project_id,
                "handoverPackage": response_value(second_package),
            },
            "target_global_id": str(second_package.global_id),
            "tenant_id": TENANT,
            "project_global_id": project_id,
            "policy_global_id": str(published.policy_global_id),
            "policy_version": published.policy_version,
            "policy_snapshot_hash": published.snapshot_hash,
            "handover_global_id": str(second_package.handover_global_id),
            "expected_revision_global_id": str(first_package.global_id),
            "expected_snapshot_hash": "0" * 64,
        }
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_command_response(**wrong_binding)

    def test_response_required_fields_match_domain_canonical_snapshots_exactly(self) -> None:
        from tests.test_phase7_production_transition_domain import (
            CONTEXT_SOURCE,
            NOW,
            SENDER_MEMBER,
            SENDER_ROLE,
            SOURCE,
            TENANT,
            package,
            policy,
            project,
            uid,
        )
        from npi_core.production_transition.domain import (
            ExactVersionReference,
            create_handover_acknowledgement,
            create_observation_period_revision,
            sha256_json,
        )

        policy_payload = policy().snapshot_payload()
        package_value = package()
        package_payload = package_value.snapshot_payload()
        acknowledgement_payload = create_handover_acknowledgement(
            package_value,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(98),
            trace_id="trace-p706-contract-ack",
        ).snapshot_payload()
        observation_payload = create_observation_period_revision(
            observation_global_id=uid(99),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=ExactVersionReference(
                package_value.global_id,
                package_value.handover_version,
                package_value.snapshot_hash,
            ),
            context_references=(CONTEXT_SOURCE,),
            retrospective_references=(),
            retrospective_note=None,
            reason="Verify the exact closed response contract.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(100),
            trace_id="trace-p706-contract-observation",
        ).snapshot_payload()
        cases = (
            ("ProductionTransitionPolicyVersion", policy_payload),
            (
                "ProductionTransitionHandoverObjectRequirement",
                policy_payload["handoverRequirements"][0],
            ),
            ("HandoverPackageRevision", package_payload),
            ("HandoverAcknowledgement", acknowledgement_payload),
            ("ObservationPeriodRevision", observation_payload),
            ("ProductionTransitionProjectSnapshot", package_payload["project"]),
            ("ProductionTransitionFrozenSlot", package_payload["slots"][0]),
            ("ProductionTransitionExactSourceReference", package_payload["manifest"][0]),
            (
                "ProductionTransitionObservationSourceReference",
                observation_payload["contextReferences"][0],
            ),
            (
                "ProductionTransitionUnresolvedWorkItemSnapshot",
                package_payload["unresolvedActions"][0],
            ),
        )
        for name, payload in cases:
            expected = set(payload)
            if name in {
                "ProductionTransitionPolicyVersion",
                "HandoverPackageRevision",
                "HandoverAcknowledgement",
                "ObservationPeriodRevision",
            }:
                expected.add("snapshotHash")
            with self.subTest(name=name):
                self.assertEqual(inline_required_fields(name), expected)

        response_cases = (
            (validate_policy_version_response, policy_payload, policy().snapshot_hash),
            (
                validate_handover_package_response,
                package_payload,
                package_value.snapshot_hash,
            ),
            (
                validate_acknowledgement_response,
                acknowledgement_payload,
                create_handover_acknowledgement(
                    package_value,
                    slot_key="sender",
                    acknowledgement_intent=True,
                    actor_user_id=SENDER_MEMBER.user_id,
                    actor_user_enabled=True,
                    current_member=SENDER_MEMBER,
                    current_role=SENDER_ROLE,
                    acknowledged_at=NOW,
                    request_id=uid(98),
                    trace_id="trace-p706-contract-ack",
                ).snapshot_hash,
            ),
            (
                validate_observation_revision_response,
                observation_payload,
                create_observation_period_revision(
                    observation_global_id=uid(99),
                    tenant_id=TENANT,
                    project=project(),
                    policy=policy(),
                    handover_package_ref=ExactVersionReference(
                        package_value.global_id,
                        package_value.handover_version,
                        package_value.snapshot_hash,
                    ),
                    context_references=(CONTEXT_SOURCE,),
                    retrospective_references=(),
                    retrospective_note=None,
                    reason="Verify the exact closed response contract.",
                    created_by_user_id="admin@example.invalid",
                    created_at=NOW,
                    request_id=uid(100),
                    trace_id="trace-p706-contract-observation",
                ).snapshot_hash,
            ),
        )
        for validator, payload, snapshot_hash in response_cases:
            response_value = {**payload, "snapshotHash": snapshot_hash}
            validator(response_value)
            with self.assertRaises(ProductionTransitionResponseInvalid):
                validator({**response_value, "secret": "must-not-leak"})
            with self.assertRaises(ProductionTransitionResponseInvalid):
                validator({**response_value, "snapshotHash": "0" * 64})

        for mutate in ("wrong_usage", "handover_fields"):
            with self.subTest(mutate=mutate):
                invalid_observation = copy.deepcopy(observation_payload)
                reference = invalid_observation["contextReferences"][0]
                if mutate == "wrong_usage":
                    reference["usage"] = "retrospective"
                else:
                    reference["requirementKey"] = "open_work"
                    reference["role"] = "unresolved_action"
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_observation_revision_response(
                        {
                            **invalid_observation,
                            "snapshotHash": sha256_json(invalid_observation),
                        }
                    )

    def test_checkpoint_two_freezes_exactly_eleven_operations_and_next_version(self) -> None:
        paths = OPENAPI[: OPENAPI.index("\ncomponents:")]
        expected = {
            "/production-transition/policies": {"get", "post"},
            "/production-transition/policies/{policyId}/versions/{policyVersion}": {"put"},
            "/production-transition/policies/{policyId}/versions/{policyVersion}:publish": {"post"},
            "/production-transition/policies/{policyId}/versions": {"post"},
            "/projects/{projectId}/production-transition": {"get"},
            "/projects/{projectId}/production-handover": {"post"},
            "/projects/{projectId}/production-handover/{handoverId}/revisions": {"post"},
            (
                "/projects/{projectId}/production-handover/{handoverId}/revisions/"
                "{handoverVersion}/acknowledgements"
            ): {"post"},
            "/projects/{projectId}/observation-periods": {"post"},
            "/projects/{projectId}/observation-periods/{observationId}/revisions": {"post"},
        }
        actual_paths = set(
            re.findall(
                (
                    r"^  (/(?:production-transition|projects/\{projectId\}/"
                    r"(?:production-transition|production-handover|"
                    r"observation-periods))[^\n]*):$"
                ),
                paths,
                flags=re.MULTILINE,
            )
        )
        self.assertEqual(actual_paths, set(expected))
        operation_count = 0
        for path, methods in expected.items():
            actual = set(
                re.findall(
                    r"^    (get|post|put|patch|delete):$",
                    path_block(path),
                    flags=re.MULTILINE,
                )
            )
            with self.subTest(path=path):
                self.assertEqual(actual, methods)
            operation_count += len(actual)
        self.assertEqual(operation_count, 11)
        next_version = path_block(
            "/production-transition/policies/{policyId}/versions"
        )
        self.assertIn("operationId: createNextProductionTransitionPolicyVersion", next_version)
        self.assertIn(
            "x-audit-operation: production_transition_policy.next_version",
            next_version,
        )

    def test_all_commands_are_closed_audited_actor_bound_transactions(self) -> None:
        command_paths = (
            "/production-transition/policies",
            "/production-transition/policies/{policyId}/versions/{policyVersion}",
            "/production-transition/policies/{policyId}/versions/{policyVersion}:publish",
            "/production-transition/policies/{policyId}/versions",
            "/projects/{projectId}/production-handover",
            "/projects/{projectId}/production-handover/{handoverId}/revisions",
            (
                "/projects/{projectId}/production-handover/{handoverId}/revisions/"
                "{handoverVersion}/acknowledgements"
            ),
            "/projects/{projectId}/observation-periods",
            "/projects/{projectId}/observation-periods/{observationId}/revisions",
        )
        for path in command_paths:
            block = path_block(path)
            command_start = max(block.find("\n    post:\n"), block.find("\n    put:\n"))
            command = block[command_start:]
            with self.subTest(path=path):
                self.assertIn("#/components/parameters/IdempotencyKey", command)
                self.assertIn("#/components/parameters/RequestId", command)
                self.assertIn("#/components/parameters/CsrfToken", command)
                self.assertIn("x-required-roles:", command)
                self.assertIn("x-transaction-boundary:", command)
                self.assertRegex(
                    command,
                    (
                        r"x-audit-operation: (?:production_transition_policy|"
                        r"production_handover|observation_period)\."
                    ),
                )

    def test_production_transition_schemas_are_closed(self) -> None:
        names = (
            "ProductionTransitionApplicability",
            "ProductionTransitionReceivingGroupDefinition",
            "ProductionTransitionAcknowledgementSlotDefinition",
            "ProductionTransitionHandoverObjectRequirement",
            "ProductionTransitionActualSopRule",
            "ProductionTransitionCustomerComplaintRule",
            "ProductionTransitionFirstBatchYieldRule",
            "ProductionTransitionCycleTimeRule",
            "ProductionTransitionToolingStabilityRule",
            "ProductionTransitionPolicyDefinition",
            "ProductionTransitionPolicyVersion",
            "ProductionTransitionPolicyCatalog",
            "CreateProductionTransitionPolicy",
            "EditProductionTransitionPolicy",
            "PublishProductionTransitionPolicy",
            "CreateNextProductionTransitionPolicyVersion",
            "ProductionTransitionExactVersionReference",
            "ProductionTransitionUnresolvedActionSelector",
            "ProductionTransitionExactSourceSelection",
            "ProductionTransitionManifestSourceSelection",
            "ProductionTransitionExactSourceReference",
            "ProductionTransitionObservationSourceReference",
            "ProductionTransitionSlotAssignmentSelection",
            "ProductionTransitionPolicyReferenceRequest",
            "ProductionHandoverRequestContent",
            "ReviseProductionHandoverPackage",
            "AcknowledgeProductionHandoverSlot",
            "ProductionTransitionProjectSnapshot",
            "ProductionTransitionMemberSnapshot",
            "ProductionTransitionRoleSnapshot",
            "ProductionTransitionFrozenSlot",
            "ProductionTransitionUnresolvedWorkItemSnapshot",
            "HandoverAcknowledgement",
            "HandoverPackageRevision",
            "HandoverPackageView",
            "ProductionTransitionActualSopUnavailable",
            "ProductionTransitionFirstBatchYieldUnavailable",
            "ProductionTransitionCustomerComplaintUnavailable",
            "ProductionTransitionCycleTimeUnavailable",
            "ProductionTransitionToolingStabilityUnavailable",
            "ProductionTransitionHandoverReferenceRequest",
            "CreateObservationPeriod",
            "ReviseObservationPeriod",
            "ObservationPeriodRevision",
            "ProductionHandoverCommandResponse",
            "ProductionHandoverAcknowledgementCommandResponse",
            "ObservationPeriodCommandResponse",
            "ProductionTransitionPermissions",
            "ProductionTransitionWorkspace",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIn("additionalProperties: false", schema(name))
        self.assertIn("unevaluatedProperties: false", schema("CreateProductionHandoverPackage"))

    def test_source_selections_separate_handover_requirement_from_observation_usage(self) -> None:
        kind = schema("ProductionTransitionSourceKind")
        for source_kind in sorted(HANDOVER_SOURCE_KINDS):
            self.assertIn(source_kind, kind)

        observation_selection = schema("ProductionTransitionExactSourceSelection")
        self.assertIn(
            "required: [kind, globalId, expectedVersion]",
            observation_selection,
        )
        for server_owned in (
            "requirementKey:",
            "role:",
            "snapshotHash:",
            "projection:",
            "state:",
            "disposition:",
            "sourceVersion:",
            "usage:",
        ):
            self.assertNotIn(server_owned, observation_selection)
        for caller_owned in ("requirementKey", "role", "snapshotHash", "usage"):
            with self.subTest(observation_caller_owned=caller_owned):
                with self.assertRaises(RequestValidationFailed):
                    parse_exact_source_selection(
                        {
                            "kind": "domain_work_item",
                            "globalId": UUID_1,
                            "expectedVersion": 2,
                            caller_owned: (
                                HASH_1
                                if caller_owned == "snapshotHash"
                                else "context"
                            ),
                        }
                    )

        manifest_selection = schema("ProductionTransitionManifestSourceSelection")
        self.assertIn(
            "required: [requirementKey, kind, globalId, expectedVersion]",
            manifest_selection,
        )
        self.assertIn(
            "#/components/schemas/ProductionTransitionManifestSourceSelection",
            schema("ProductionHandoverRequestContent"),
        )
        for server_owned in (
            "role:",
            "snapshotHash:",
            "projection:",
            "state:",
            "disposition:",
            "sourceVersion:",
            "usage:",
        ):
            self.assertNotIn(server_owned, manifest_selection)
        parsed = parse_manifest_source_selection(
            {
                "requirementKey": "trial:result/required",
                "kind": "trial_conclusion",
                "globalId": UUID_1,
                "expectedVersion": 2,
            }
        )
        self.assertEqual(parsed.requirement_key, "trial:result/required")
        self.assertEqual(parsed.kind, "trial_conclusion")
        for caller_owned in ("role", "snapshotHash", "projection"):
            with self.subTest(caller_owned=caller_owned):
                with self.assertRaises(RequestValidationFailed):
                    parse_manifest_source_selection(
                        {
                            "requirementKey": "trial_result",
                            "kind": "trial_conclusion",
                            "globalId": UUID_1,
                            "expectedVersion": 2,
                            caller_owned: (
                                "handover_evidence"
                                if caller_owned == "role"
                                else HASH_1
                            ),
                        }
                    )
        with self.assertRaises(RequestValidationFailed):
            parse_manifest_source_selections(())
        with self.assertRaises(RequestValidationFailed):
            parse_manifest_source_selections(
                (
                    {
                        "requirementKey": "first_requirement",
                        "kind": "domain_work_item",
                        "globalId": UUID_1,
                        "expectedVersion": 2,
                    },
                    {
                        "requirementKey": "second_requirement",
                        "kind": "domain_work_item",
                        "globalId": UUID_1,
                        "expectedVersion": 2,
                    },
                )
            )

    def test_policy_injects_handover_role_and_observation_references_fix_usage(self) -> None:
        requirement = schema("ProductionTransitionHandoverObjectRequirement")
        self.assertIn(
            "required: [key, acceptedSourceKinds, manifestRole, minimumCount]",
            requirement,
        )
        self.assertIn("manifestRole:", requirement)
        handover_reference = schema("ProductionTransitionExactSourceReference")
        self.assertIn(
            "required: [requirementKey, kind, globalId, sourceVersion, snapshotHash, role]",
            handover_reference,
        )

        observation_reference = schema(
            "ProductionTransitionObservationSourceReference"
        )
        self.assertIn(
            "required: [kind, globalId, sourceVersion, snapshotHash, usage]",
            observation_reference,
        )
        self.assertIn("enum: [context, retrospective]", observation_reference)
        self.assertNotIn("requirementKey:", observation_reference)
        self.assertNotIn("role:", observation_reference)
        observation = schema("ObservationPeriodRevision")
        self.assertEqual(
            observation.count(
                "#/components/schemas/ProductionTransitionObservationSourceReference"
            ),
            2,
        )
        self.assertIn("usage: { type: string, const: context }", observation)
        self.assertIn(
            "usage: { type: string, const: retrospective }",
            observation,
        )
        request_schemas = schema("CreateObservationPeriod") + schema(
            "ReviseObservationPeriod"
        )
        self.assertEqual(
            request_schemas.count(
                "#/components/schemas/ProductionTransitionExactSourceSelection"
            ),
            4,
        )
        self.assertNotIn("ProductionTransitionManifestSourceSelection", request_schemas)

    def test_contract_lengths_patterns_and_project_vocabulary_match_domain(self) -> None:
        applicability = schema("ProductionTransitionApplicability")
        self.assertIn("maxItems: 20", applicability)
        self.assertIn(
            "enum: [customer_owned_tool, new_tool, tool_change]",
            applicability,
        )
        policy = schema("ProductionTransitionPolicyVersion")
        create = schema("CreateProductionTransitionPolicy")
        edit = schema("EditProductionTransitionPolicy")
        code_pattern = 'pattern: "^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$"'
        self.assertIn(code_pattern, policy)
        self.assertIn(code_pattern, create)
        self.assertIn("maxLength: 200", create)
        self.assertIn("maxLength: 200", edit)
        project_schema = schema("ProductionTransitionProjectSnapshot")
        self.assertIn(code_pattern, project_schema)
        self.assertIn("maxLength: 200", project_schema)
        self.assertIn(
            "enum: [customer_owned_tool, new_tool, tool_change]",
            project_schema,
        )
        self.assertIn("maxLength: 256", project_schema)
        key_pattern = 'pattern: "^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$"'
        for name in (
            "ProductionTransitionReceivingGroupDefinition",
            "ProductionTransitionAcknowledgementSlotDefinition",
            "ProductionTransitionHandoverObjectRequirement",
            "ProductionTransitionManifestSourceSelection",
            "ProductionTransitionExactSourceReference",
            "ProductionTransitionSlotAssignmentSelection",
            "AcknowledgeProductionHandoverSlot",
            "ProductionTransitionRoleSnapshot",
            "ProductionTransitionFrozenSlot",
            "HandoverAcknowledgement",
        ):
            with self.subTest(name=name):
                self.assertIn(key_pattern, schema(name))

    def test_unresolved_actions_are_server_fixed_and_not_caller_selected(self) -> None:
        package = schema("HandoverPackageRevision")
        selector = schema("ProductionTransitionUnresolvedActionSelector")
        for marker in (
            "const: all_non_terminal",
            "const: action",
            "const: decision_request",
            "const: issue",
            "const: risk",
            "ownerUserId:",
            "dueDate:",
        ):
            target = (
                schema("ProductionTransitionUnresolvedWorkItemSnapshot")
                if marker in {"ownerUserId:", "dueDate:"}
                else selector
            )
            self.assertIn(marker, target)
        self.assertIn("maxItems: 10000", package)
        requests = schema("ProductionHandoverRequestContent") + schema(
            "ReviseProductionHandoverPackage"
        )
        for forbidden in ("unresolvedSelector:", "unresolvedWorkItems:", "workItemIds:"):
            self.assertNotIn(forbidden, requests)

    def test_fully_acknowledged_is_response_only_query_derivation(self) -> None:
        from tests.test_phase7_production_transition_domain import (
            NOW,
            RECEIVER_MEMBER,
            RECEIVER_ROLE,
            SENDER_MEMBER,
            SENDER_ROLE,
            package,
            uid,
        )
        from npi_core.production_transition.domain import create_handover_acknowledgement

        self.assertNotIn("fullyAcknowledged:", schema("HandoverPackageRevision"))
        self.assertIn("fullyAcknowledged:", schema("HandoverPackageView"))
        self.assertIn("readOnly: true", schema("HandoverPackageView"))
        request_schemas = "\n".join(
            schema(name)
            for name in (
                "ProductionHandoverRequestContent",
                "ReviseProductionHandoverPackage",
                "AcknowledgeProductionHandoverSlot",
            )
        )
        self.assertNotIn("fullyAcknowledged:", request_schemas)
        package_value = package()
        acknowledgement_value = create_handover_acknowledgement(
            package_value,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(101),
            trace_id="trace-p706-derived-ack",
        )
        acknowledgement = {
            **acknowledgement_value.snapshot_payload(),
            "snapshotHash": acknowledgement_value.snapshot_hash,
        }
        receiver_acknowledgement_value = create_handover_acknowledgement(
            package_value,
            slot_key="receiver",
            acknowledgement_intent=True,
            actor_user_id=RECEIVER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=RECEIVER_MEMBER,
            current_role=RECEIVER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(102),
            trace_id="trace-p706-derived-receiver-ack",
        )
        receiver_acknowledgement = {
            **receiver_acknowledgement_value.snapshot_payload(),
            "snapshotHash": receiver_acknowledgement_value.snapshot_hash,
        }
        package_response = {
            **package_value.snapshot_payload(),
            "snapshotHash": package_value.snapshot_hash,
        }
        valid = validate_fully_acknowledged_projection(
            {
                "acknowledgements": [
                    acknowledgement,
                    receiver_acknowledgement,
                ],
                "fullyAcknowledged": True,
            },
            handover_package=package_response,
        )
        self.assertTrue(valid["fullyAcknowledged"])
        partial = validate_fully_acknowledged_projection(
            {"acknowledgements": [acknowledgement], "fullyAcknowledged": False},
            handover_package=package_response,
        )
        self.assertFalse(partial["fullyAcknowledged"])
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_fully_acknowledged_projection(
                {"acknowledgements": [], "fullyAcknowledged": True},
                handover_package=package_response,
            )
        tampered_package = copy.deepcopy(package_response)
        tampered_package["snapshotHash"] = "0" * 64
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_fully_acknowledged_projection(
                {
                    "acknowledgements": [acknowledgement],
                    "fullyAcknowledged": False,
                },
                handover_package=tampered_package,
            )
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_fully_acknowledged_projection(
                {
                    "acknowledgements": [acknowledgement, acknowledgement],
                    "fullyAcknowledged": False,
                },
                handover_package=package_response,
            )
        unknown = {**acknowledgement, "slotKey": "unknown.slot"}
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_fully_acknowledged_projection(
                {"acknowledgements": [unknown], "fullyAcknowledged": False},
                handover_package=package_response,
            )

    def test_acknowledgement_receipt_and_projection_bind_the_exact_frozen_slot(
        self,
    ) -> None:
        from tests.test_phase7_production_transition_domain import (
            NOW,
            package,
            uid,
        )
        from npi_core.production_transition.domain import HandoverAcknowledgement

        package_value = package()
        package_response = {
            **package_value.snapshot_payload(),
            "snapshotHash": package_value.snapshot_hash,
        }

        def acknowledgement(slot_key: str) -> dict[str, object]:
            value = HandoverAcknowledgement(
                global_id=uuid5(
                    package_value.global_id,
                    f"npi-handover-acknowledgement:{slot_key}",
                ),
                handover_global_id=package_value.handover_global_id,
                package_revision_global_id=package_value.global_id,
                package_version=package_value.handover_version,
                package_snapshot_hash=package_value.snapshot_hash,
                slot_key=slot_key,
                actor_user_id="attacker@example.invalid",
                member_global_id=uid(901),
                member_optimistic_version=1,
                member_snapshot_hash="a" * 64,
                role_global_id=uid(902),
                role_optimistic_version=1,
                role_snapshot_hash="b" * 64,
                acknowledged_at=NOW,
                request_id=uid(903),
                trace_id="trace-p706-wrong-frozen-slot",
            )
            return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}

        wrong_binding = acknowledgement("sender")
        unknown_slot = acknowledgement("unknown.slot")
        for invalid_acknowledgement in (wrong_binding, unknown_slot):
            with self.subTest(slot=invalid_acknowledgement["slotKey"]):
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_handover_acknowledgement_projection(
                        invalid_acknowledgement,
                        handover_package=package_response,
                    )
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_fully_acknowledged_projection(
                        {
                            "acknowledgements": [invalid_acknowledgement],
                            "fullyAcknowledged": False,
                        },
                        handover_package=package_response,
                    )
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_receipt_response(
                        "production_handover.acknowledge",
                        {
                            "projectGlobalId": str(package_value.project.global_id),
                            "handoverPackage": package_response,
                            "acknowledgement": invalid_acknowledgement,
                        },
                        target_global_id=invalid_acknowledgement["globalId"],
                        project_global_id=str(package_value.project.global_id),
                        tenant_id=package_value.tenant_id,
                    )

    def test_acknowledgement_request_has_no_actor_proxy_signature_or_gate_authority(self) -> None:
        request = schema("AcknowledgeProductionHandoverSlot")
        self.assertIn("const: acknowledge", request)
        for forbidden_property in (
            "actoruserid:",
            "acknowledgedat:",
            "proxyuserid:",
            "delegateuserid:",
            "signature:",
            "approval:",
            "gate:",
            "g7:",
        ):
            self.assertNotIn(forbidden_property, request.casefold())
        parsed = parse_acknowledgement_intent(
            {
                "expectedRevisionGlobalId": UUID_1,
                "expectedSnapshotHash": HASH_1,
                "slotKey": "receiver.production",
                "intent": "acknowledge",
            }
        )
        self.assertEqual(parsed.slot_key, "receiver.production")
        with self.assertRaises(RequestValidationFailed):
            parse_acknowledgement_intent(
                {
                    "expectedRevisionGlobalId": UUID_1,
                    "expectedSnapshotHash": HASH_1,
                    "slotKey": "receiver.production",
                    "intent": "acknowledge",
                    "actorUserId": UUID_2,
                }
            )

    def test_five_external_providers_are_mandatory_identity_free_and_unavailable(self) -> None:
        self.assertEqual(
            MANDATORY_EXTERNAL_PROVIDER_ORDER,
            (
                "actual_sop",
                "first_batch_yield",
                "customer_complaint",
                "production_cycle_time",
                "tooling_stability",
            ),
        )
        self.assertEqual(
            MANDATORY_EXTERNAL_PROVIDER_KINDS,
            {
                "actual_sop",
                "first_batch_yield",
                "customer_complaint",
                "production_cycle_time",
                "tooling_stability",
            },
        )
        for name in (
            "ProductionTransitionActualSopUnavailable",
            "ProductionTransitionFirstBatchYieldUnavailable",
            "ProductionTransitionCustomerComplaintUnavailable",
            "ProductionTransitionCycleTimeUnavailable",
            "ProductionTransitionToolingStabilityUnavailable",
        ):
            value = schema(name)
            self.assertIn("state: { type: string, const: unavailable }", value)
            for required_null in (
                "sourceIdentity: { type: \"null\" }",
                "value: { type: \"null\" }",
                "observedAt: { type: \"null\" }",
                "unit: { type: \"null\" }",
            ):
                self.assertIn(required_null, value)
            for forbidden in ("globalId:", "sourceVersion:", "snapshotHash:", "score:", "pass:"):
                self.assertNotIn(forbidden, value)
        provider_tuple = schema("ProductionTransitionExternalUnavailableProviders")
        provider_order = (
            "ProductionTransitionActualSopUnavailable",
            "ProductionTransitionFirstBatchYieldUnavailable",
            "ProductionTransitionCustomerComplaintUnavailable",
            "ProductionTransitionCycleTimeUnavailable",
            "ProductionTransitionToolingStabilityUnavailable",
        )
        self.assertEqual(
            sorted(provider_order, key=provider_tuple.index),
            list(provider_order),
        )
        self.assertIn("prefixItems:", provider_tuple)
        self.assertIn("items: false", provider_tuple)
        self.assertIn(
            "#/components/schemas/ProductionTransitionExternalUnavailableProviders",
            schema("ObservationPeriodRevision"),
        )
        self.assertIn(
            "#/components/schemas/ProductionTransitionExternalUnavailableProviders",
            schema("ProductionTransitionWorkspace"),
        )
        assert_mandatory_provider_kinds(MANDATORY_EXTERNAL_PROVIDER_ORDER)
        with self.assertRaises(RequestValidationFailed):
            assert_mandatory_provider_kinds(
                tuple(reversed(MANDATORY_EXTERNAL_PROVIDER_ORDER))
            )
        self.assertEqual(len(validate_unavailable_provider_responses(unavailable_providers())), 5)
        invalid = unavailable_providers()
        invalid[0]["globalId"] = UUID_1
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_unavailable_provider_responses(invalid)
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_unavailable_provider_responses(list(reversed(unavailable_providers())))
        non_null = unavailable_providers()
        non_null[0]["value"] = "2026-08-14"
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_unavailable_provider_responses(non_null)

    def test_policy_provider_rules_are_closed_and_use_canonical_order(self) -> None:
        source_rules = schema("ProductionTransitionObservationSourceRules")
        canonical_rule_order = (
            "ProductionTransitionActualSopRule",
            "ProductionTransitionCustomerComplaintRule",
            "ProductionTransitionFirstBatchYieldRule",
            "ProductionTransitionCycleTimeRule",
            "ProductionTransitionToolingStabilityRule",
        )
        self.assertEqual(
            sorted(canonical_rule_order, key=source_rules.index),
            list(canonical_rule_order),
        )
        self.assertIn("prefixItems:", source_rules)
        self.assertIn("items: false", source_rules)
        for policy_schema in (
            "ProductionTransitionPolicyDefinition",
            "ProductionTransitionPolicyVersion",
        ):
            self.assertIn(
                "#/components/schemas/ProductionTransitionObservationSourceRules",
                schema(policy_schema),
            )

        actual_sop = schema("ProductionTransitionActualSopRule")
        self.assertIn("const: actual_sop", actual_sop)
        self.assertEqual(actual_sop.count('{ type: "null" }'), 3)
        for metric_rule, provider_kind in (
            ("ProductionTransitionCustomerComplaintRule", "customer_complaint"),
            ("ProductionTransitionFirstBatchYieldRule", "first_batch_yield"),
            ("ProductionTransitionCycleTimeRule", "production_cycle_time"),
            ("ProductionTransitionToolingStabilityRule", "tooling_stability"),
        ):
            value = schema(metric_rule)
            with self.subTest(provider_kind=provider_kind):
                self.assertIn(f"const: {provider_kind}", value)
                self.assertNotIn('type: "null"', value)
                self.assertIn("maxLength: 32", value)
                self.assertIn("greater_than_or_equal", value)
                self.assertIn('pattern: "^-?[0-9]+', value)
        allowed = schema("ProductionTransitionAllowedDispositions")
        self.assertIn("contains: { const: not_evaluable }", allowed)
        self.assertIn("minContains: 1", allowed)
        self.assertIn("maxContains: 1", allowed)

    def test_observation_requests_exclude_external_truth_and_result_authority(self) -> None:
        requests = schema("CreateObservationPeriod") + schema("ReviseObservationPeriod")
        for forbidden in (
            "providers:",
            "actualSop:",
            "observedStart:",
            "observedEnd:",
            "metricValue:",
            "score:",
            "status:",
            "pass:",
            "technicalDisposition:",
            "conclusion:",
            "gate:",
            "erp",
        ):
            self.assertNotIn(forbidden, requests)
        parsed = parse_observation_revision_request(
            {
                "contextSources": [],
                "retrospectiveSources": [],
                "retrospectiveNote": None,
                "reason": "Create observation context.",
            },
            successor=False,
        )
        self.assertEqual(parsed.retrospective_sources, ())
        shared_source = {
            "kind": "domain_work_item",
            "globalId": UUID_1,
            "expectedVersion": 2,
        }
        shared = parse_observation_revision_request(
            {
                "contextSources": [shared_source],
                "retrospectiveSources": [shared_source],
                "retrospectiveNote": None,
                "reason": "Reuse the same exact source for two fixed usages.",
            },
            successor=False,
        )
        self.assertEqual(
            shared.context_sources[0].expected_version,
            shared.retrospective_sources[0].expected_version,
        )
        with self.assertRaises(RequestValidationFailed):
            parse_observation_revision_request(
                {
                    "contextSources": [shared_source],
                    "retrospectiveSources": [
                        {**shared_source, "expectedVersion": 3}
                    ],
                    "retrospectiveNote": None,
                    "reason": "Reject contradictory exact versions.",
                },
                successor=False,
            )
        with self.assertRaises(RequestValidationFailed):
            parse_observation_revision_request(
                {
                    "retrospectiveSources": [],
                    "contextSources": [],
                    "retrospectiveNote": None,
                    "reason": "Create observation context.",
                    "technicalDisposition": "stable",
                },
                successor=False,
            )
        projection = validate_observation_projection(
            {
                "providers": unavailable_providers(),
                "observedStart": None,
                "observedEnd": None,
                "technicalDisposition": "not_evaluable",
            }
        )
        self.assertEqual(projection["technicalDisposition"], "not_evaluable")

    def test_responses_preserve_security_headers_and_problem_details(self) -> None:
        for name in (
            "ProductionTransitionPolicyCatalogResult",
            "ProductionTransitionPolicyCommandResult",
            "ProductionTransitionQueryResult",
            "ProductionHandoverCommandResult",
            "ProductionHandoverAcknowledgementCommandResult",
            "ObservationPeriodCommandResult",
        ):
            value = response(name)
            self.assertIn("X-Request-ID:", value)
            self.assertIn("X-Trace-ID:", value)
            self.assertIn('const: "private, no-store"', value)
        self.assertNotIn(
            "Idempotency-Replayed:",
            response("ProductionTransitionPolicyCatalogResult"),
        )
        self.assertNotIn(
            "Idempotency-Replayed:", response("ProductionTransitionQueryResult")
        )
        self.assertIn(
            "Idempotency-Replayed:",
            response("ProductionTransitionPolicyCommandResult"),
        )
        for name in (
            "ProductionHandoverCommandResult",
            "ProductionHandoverAcknowledgementCommandResult",
            "ObservationPeriodCommandResult",
        ):
            self.assertIn("Idempotency-Replayed:", response(name))

    def test_ownership_separates_npi_snapshots_external_actuals_and_gate_authority(self) -> None:
        self.assertIn(
            "stable_policy_identity_tenant_scoped_code_title_and_optimistic_version",
            OWNERSHIP,
        )
        self.assertIn(
            "conflict: GUARDED_SAME_TENANT_OPTIMISTIC_COMMAND_ONLY",
            OWNERSHIP,
        )
        self.assertIn(
            "exact_policy_version_tenant_and_project_applicability",
            OWNERSHIP,
        )
        self.assertNotIn(
            "stable_policy_identity_code_title_and_optimistic_version",
            OWNERSHIP,
        )
        self.assertNotIn(
            "stable_policy_identity_code_title_and_enabled_selection",
            OWNERSHIP,
        )
        for object_name in (
            "ProductionTransitionPolicy",
            "ProductionTransitionPolicyVersion",
            "HandoverPackageRevision",
            "HandoverAcknowledgement",
            "ObservationPeriodRevision",
            "ProductionTransitionCommandIdempotency",
        ):
            self.assertIn(f"  {object_name}:\n", OWNERSHIP)
        for boundary in (
            "conflict: NOT_INSTALLED_BY_METADATA",
            "conflict: NEVER_PERSIST_OR_REHASH_PACKAGE",
            "conflict: SERVER_ENUMERATED_ALL_NON_TERMINAL",
            "conflict: UNAVAILABLE_NO_PROXY_OR_SIGNATURE",
            "conflict: UNAVAILABLE_IDENTITY_FREE_NO_CALLER_VALUE",
            "conflict: NOT_EVALUABLE_WHILE_ANY_PROVIDER_UNAVAILABLE",
            "conflict: NO_AUTOMATIC_MUTATION_IN_P7_06",
        ):
            self.assertIn(boundary, OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
