from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid5

sys.path.insert(0, "apps/npi_core")

TENANT_ID = "tenant-a"
PROJECT_ID = UUID("54bccb5c-f681-4e9e-aa6b-57e995b26eb4")
GATE_ID = UUID("7f5c61f7-09eb-41d1-808f-359f788e806c")
CYCLE_ID = uuid5(GATE_ID, "review-cycle:1")
POLICY_ID = UUID("084fd500-d4a5-4a61-8e29-66db7d504b8a")
REVIEWER_ID = UUID("f696c526-abaa-4752-9821-af58a62fe104")
DECIDER_ID = UUID("f34fcaaf-5d34-4e1d-b11f-d611553032b7")
REOPENER_ID = UUID("9008d33a-7640-4979-a47d-03449a2043a2")
REQUIREMENT_ID = UUID("ef828729-44da-4ef4-8117-c66a9300ae35")
EXCEPTION_ID = UUID("4aca9b21-776e-49eb-ad8c-e38ed2dbbdb2")
ACTION_ID = UUID("976b69a2-8d38-4129-80ed-1b06190fb0f8")
SUCCESSOR_CYCLE_ID = uuid5(GATE_ID, "review-cycle:2")
PRIOR_DECISION_ID = uuid5(CYCLE_ID, "decision-snapshot")
OCCURRED_AT = datetime(2026, 7, 24, 8, 30, tzinfo=timezone.utc)


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def set(self, fieldname: str, value: Any) -> None:
        setattr(self, fieldname, value)

    def get_doc_before_save(self) -> Any:
        return self._previous

    def is_new(self) -> bool:
        return self._previous is None


def clone(document: StubDocument) -> StubDocument:
    return StubDocument(
        {
            fieldname: value
            for fieldname, value in vars(document).items()
            if fieldname != "_previous"
        }
    )


class GateReviewHistoryControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.gate_review.frappe_validation",
        ("npi_core.npi_core.doctype.npi_gate_review_cycle" ".npi_gate_review_cycle"),
        ("npi_core.npi_core.doctype.npi_gate_review_record" ".npi_gate_review_record"),
        (
            "npi_core.npi_core.doctype.npi_gate_review_exception"
            ".npi_gate_review_exception"
        ),
        ("npi_core.npi_core.doctype.npi_gate_review_event" ".npi_gate_review_event"),
        (
            "npi_core.npi_core.doctype.npi_gate_decision_snapshot"
            ".npi_gate_decision_snapshot"
        ),
        (
            "npi_core.npi_core.doctype.npi_gate_review_idempotency"
            ".npi_gate_review_idempotency"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.ValidationError = type("ValidationError", (Exception,), {})
        self.PermissionError = type("PermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = self.PermissionError
        frappe.flags = types.SimpleNamespace()

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        frappe.throw = throw
        model = types.ModuleType("frappe.model")
        document_module = types.ModuleType("frappe.model.document")
        document_module.Document = StubDocument
        model.document = document_module
        frappe.model = model
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document_module

        self.frappe = frappe
        self.validation = importlib.import_module(
            "npi_core.gate_review.frappe_validation"
        )
        self.Cycle = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_review_cycle" ".npi_gate_review_cycle"
        ).NPIGateReviewCycle
        self.Record = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_review_record" ".npi_gate_review_record"
        ).NPIGateReviewRecord
        self.Exception = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_review_exception"
            ".npi_gate_review_exception"
        ).NPIGateReviewException
        self.Event = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_review_event" ".npi_gate_review_event"
        ).NPIGateReviewEvent
        self.Decision = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_decision_snapshot"
            ".npi_gate_decision_snapshot"
        ).NPIGateDecisionSnapshot
        self.Idempotency = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_review_idempotency"
            ".npi_gate_review_idempotency"
        ).NPIGateReviewIdempotency

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def policy_snapshot(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "policyGlobalId": str(POLICY_ID),
            "policyCode": "synthetic-gate-review",
            "policyVersion": 1,
            "gateTemplateGlobalId": "e0cb8528-0ddd-434f-88fb-fdfe2a2d5164",
            "gateTemplateVersion": 1,
            "gateTemplateHash": "1" * 64,
            "steps": [
                {
                    "key": "technical-review",
                    "sequence": 1,
                    "authoritySlot": "technical-reviewer",
                    "activation": "always",
                    "activationPriority": None,
                }
            ],
            "decisionAuthoritySlot": "gate-decider",
            "reopenAuthoritySlot": "gate-reopener",
        }

    def input_snapshot(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "gateGlobalId": str(GATE_ID),
            "requirements": [{"key": "drawing", "priority": "P0"}],
            "evidence": [{"hash": "2" * 64}],
            "blockers": [],
        }

    def cycle(self) -> StubDocument:
        policy = self.policy_snapshot()
        input_snapshot = self.input_snapshot()
        return self.Cycle(
            {
                "global_id": str(CYCLE_ID),
                "cycle_key": "spoofed",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "gate_global_id": str(GATE_ID),
                "gate_shell": str(GATE_ID),
                "cycle_number": 1,
                "trigger": "manual_start",
                "policy_global_id": str(POLICY_ID),
                "policy_version": 1,
                "policy_snapshot_hash": self.validation.canonical_json_hash(policy),
                "policy_snapshot": json.dumps(policy, indent=2),
                "authority_bindings": [
                    {
                        "slot": "technical-reviewer",
                        "memberGlobalId": str(REVIEWER_ID),
                        "userId": "reviewer@example.invalid",
                        "displayName": "Synthetic Reviewer",
                    },
                    {
                        "slot": "gate-decider",
                        "memberGlobalId": str(DECIDER_ID),
                        "userId": "decider@example.invalid",
                        "displayName": "Synthetic Decider",
                    },
                    {
                        "slot": "gate-reopener",
                        "memberGlobalId": str(REOPENER_ID),
                        "userId": "reopener@example.invalid",
                        "displayName": "Synthetic Reopener",
                    },
                ],
                "selected_steps": [
                    {
                        "key": "technical-review",
                        "sequence": 1,
                        "authoritySlot": "technical-reviewer",
                        "activation": "always",
                        "activationPriority": None,
                    }
                ],
                "input_snapshot": json.dumps(input_snapshot, indent=2),
                "input_hash": self.validation.canonical_json_hash(input_snapshot),
                "prior_cycle_global_id": None,
                "prior_decision_snapshot_global_id": None,
                "prior_decision_hash": None,
                "state": "invalidated",
                "optimistic_version": 99,
                "started_by": "starter@example.invalid",
                "started_at": OCCURRED_AT,
            }
        )

    def record(self) -> StubDocument:
        return self.Record(
            {
                "global_id": "b686089d-f5cd-4322-810e-e5facd788fa4",
                "review_key": "spoofed",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "gate_global_id": str(GATE_ID),
                "cycle_global_id": str(CYCLE_ID),
                "cycle_number": 1,
                "policy_global_id": str(POLICY_ID),
                "policy_version": 1,
                "policy_snapshot_hash": self.validation.canonical_json_hash(
                    self.policy_snapshot()
                ),
                "review_step_key": "technical-review",
                "review_step_sequence": 1,
                "authority_slot": "technical-reviewer",
                "assigned_member_global_id": str(REVIEWER_ID),
                "assigned_user_id": "reviewer@example.invalid",
                "assigned_display_name": "Synthetic Reviewer",
                "actor_user_id": "reviewer@example.invalid",
                "outcome": "approved",
                "opinion": "The exact controlled evidence is acceptable.",
                "occurred_at": OCCURRED_AT,
                "reviewed_input_hash": self.validation.canonical_json_hash(
                    self.input_snapshot()
                ),
                "cycle_version_before": 1,
                "cycle_version_after": 2,
                "request_id": "request-review-001",
                "trace_id": "trace-review-001",
                "record_snapshot": None,
                "record_snapshot_hash": None,
            }
        )

    def exception(self) -> StubDocument:
        return self.Exception(
            {
                "global_id": str(EXCEPTION_ID),
                "exception_key": "spoofed",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "gate_global_id": str(GATE_ID),
                "cycle_global_id": str(CYCLE_ID),
                "policy_global_id": str(POLICY_ID),
                "policy_version": 1,
                "policy_snapshot_hash": self.validation.canonical_json_hash(
                    self.policy_snapshot()
                ),
                "requirement_global_id": str(REQUIREMENT_ID),
                "requirement_key": "secondary-report",
                "exception_kind": "bounded-deviation",
                "reason": "The secondary report awaits a controlled laboratory run.",
                "risk": "The non-safety summary may be delayed.",
                "requester_member_global_id": str(REVIEWER_ID),
                "requester_user_id": "requester@example.invalid",
                "requested_at": OCCURRED_AT,
                "expires_at": datetime(
                    2026,
                    7,
                    31,
                    8,
                    30,
                    tzinfo=timezone.utc,
                ),
                "closure_action_global_id": str(ACTION_ID),
                "closure_action_version": 4,
                "closure_action_snapshot_hash": "8" * 64,
                "state": "rejected",
                "approver_authority_slot": "exception-approver",
                "approver_member_global_id": str(DECIDER_ID),
                "approver_user_id": "approver@example.invalid",
                "approval_opinion": None,
                "decided_at": None,
                "optimistic_version": 99,
                "request_snapshot": None,
                "request_snapshot_hash": None,
                "decision_snapshot": None,
                "decision_snapshot_hash": None,
            }
        )

    def invalidation_event(
        self,
        *,
        event_type: str = "invalidated",
        action_global_id: str | None = None,
    ) -> StubDocument:
        occurred = OCCURRED_AT.isoformat()
        detail = {
            "reason": "GATE_INPUT_CHANGED",
            "oldInputHash": "3" * 64,
            "newInputHash": "4" * 64,
            "priorDecisionSnapshotGlobalId": str(PRIOR_DECISION_ID),
            "priorDecisionHash": "5" * 64,
            "initiatedByUserId": "initiator@example.invalid",
        }
        payload = {
            "schemaVersion": 1,
            "globalId": "b2924a46-4423-4527-a821-82857013d66d",
            "eventKey": "invalidation:cycle-001",
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "gateGlobalId": str(GATE_ID),
            "cycleGlobalId": str(CYCLE_ID),
            "successorCycleGlobalId": str(SUCCESSOR_CYCLE_ID),
            "actionGlobalId": action_global_id,
            "eventType": event_type,
            "actorUserId": "system@example.invalid",
            "occurredAt": occurred,
            "requestId": "request-event-001",
            "traceId": "trace-event-001",
            "detail": detail,
        }
        return self.Event(
            {
                "global_id": payload["globalId"],
                "event_key": payload["eventKey"],
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "gate_global_id": str(GATE_ID),
                "cycle_global_id": str(CYCLE_ID),
                "successor_cycle_global_id": str(SUCCESSOR_CYCLE_ID),
                "action_global_id": action_global_id,
                "event_type": event_type,
                "actor_user_id": "system@example.invalid",
                "occurred_at": OCCURRED_AT,
                "request_id": "request-event-001",
                "trace_id": "trace-event-001",
                "payload": payload,
                "payload_hash": None,
            }
        )

    def decision(self, *, outcome: str = "pass") -> StubDocument:
        input_snapshot = self.input_snapshot()
        return self.Decision(
            {
                "global_id": "spoofed",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "gate_global_id": str(GATE_ID),
                "cycle_global_id": str(CYCLE_ID),
                "cycle_number": 1,
                "outcome": outcome,
                "actor_user_id": "decider@example.invalid",
                "occurred_at": OCCURRED_AT,
                "policy_global_id": str(POLICY_ID),
                "policy_version": 1,
                "policy_snapshot_hash": self.validation.canonical_json_hash(
                    self.policy_snapshot()
                ),
                "decision_snapshot": None,
                "snapshot_hash": None,
                "input_snapshot": input_snapshot,
                "input_hash": self.validation.canonical_json_hash(input_snapshot),
                "review_hashes": ["6" * 64],
                "exception_hashes": ["7" * 64] if outcome == "conditional_pass" else [],
                "cycle_version": 3,
                "request_id": "request-decision-001",
                "trace_id": "trace-decision-001",
            }
        )

    def idempotency(self) -> StubDocument:
        return self.Idempotency(
            {
                "record_id": "956409fe-12bf-487b-869b-2b38be6db1cb",
                "actor": "reviewer@example.invalid",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "gate_global_id": str(GATE_ID),
                "operation": "gate.review.submit",
                "actor_key_hash": "8" * 64,
                "payload_hash": "9" * 64,
                "response_json": {},
                "response_sealed": 0,
            }
        )

    def persist_new(self, document: StubDocument) -> None:
        setattr(
            self.frappe.flags,
            self.validation.GATE_REVIEW_COMMAND_FLAG,
            True,
        )
        document.autoname()
        document.before_insert()
        document.before_validate()
        document.validate()
        document.before_save()

    def test_command_flag_and_delete_denial_apply_to_every_history_type(self) -> None:
        documents = (
            self.cycle(),
            self.record(),
            self.exception(),
            self.invalidation_event(),
            self.decision(),
            self.idempotency(),
        )
        for document in documents:
            with self.subTest(document=document.__class__.__name__):
                with self.assertRaises(self.PermissionError):
                    document.before_insert()
                with self.assertRaises(self.PermissionError):
                    document.on_trash()

    def test_cycle_freezes_exact_snapshots_and_allows_only_controlled_transitions(
        self,
    ) -> None:
        cycle = self.cycle()
        self.persist_new(cycle)
        self.assertEqual(cycle.name, str(CYCLE_ID))
        self.assertEqual(cycle.cycle_key, f"{GATE_ID}:1")
        self.assertEqual(cycle.state, "active")
        self.assertEqual(cycle.optimistic_version, 1)
        self.assertEqual(
            cycle.policy_snapshot,
            json.dumps(
                self.policy_snapshot(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

        active = clone(cycle)
        cycle._previous = active
        cycle.optimistic_version = 2
        cycle.before_validate()
        cycle.validate()

        active = clone(cycle)
        cycle._previous = active
        cycle.state = "decided"
        cycle.optimistic_version = 3
        cycle.before_validate()
        cycle.validate()

        decided = clone(cycle)
        cycle._previous = decided
        cycle.state = "invalidated"
        cycle.optimistic_version = 4
        cycle.before_validate()
        cycle.validate()

        invalid = self.cycle()
        self.persist_new(invalid)
        invalid._previous = clone(invalid)
        invalid.state = "invalidated"
        invalid.optimistic_version = 2
        invalid.before_validate()
        with self.assertRaises(self.ValidationError):
            invalid.validate()

        superseded = self.cycle()
        self.persist_new(superseded)
        superseded._previous = clone(superseded)
        superseded.state = "superseded"
        superseded.optimistic_version = 2
        superseded.before_validate()
        superseded.validate()

        successor_without_decision = self.cycle()
        successor_without_decision.global_id = str(SUCCESSOR_CYCLE_ID)
        successor_without_decision.cycle_number = 2
        successor_without_decision.trigger = "dependency_change"
        successor_without_decision.prior_cycle_global_id = str(CYCLE_ID)
        successor_without_decision.prior_decision_snapshot_global_id = None
        successor_without_decision.prior_decision_hash = None
        self.persist_new(successor_without_decision)
        self.assertEqual(successor_without_decision.state, "active")

    def test_active_refresh_event_allows_exact_empty_decision_lineage(
        self,
    ) -> None:
        event = self.invalidation_event(event_type="refreshed")
        event.payload["detail"]["priorDecisionSnapshotGlobalId"] = None
        event.payload["detail"]["priorDecisionHash"] = None
        self.persist_new(event)
        payload = json.loads(event.payload)
        self.assertIsNone(payload["detail"]["priorDecisionSnapshotGlobalId"])
        self.assertIsNone(payload["detail"]["priorDecisionHash"])
        self.assertIsNone(payload["actionGlobalId"])

    def test_dependency_events_require_successor_but_allow_nullable_legacy_action(
        self,
    ) -> None:
        for event_type in ("invalidated", "refreshed"):
            with self.subTest(event_type=event_type, action="none"):
                current = self.invalidation_event(event_type=event_type)
                self.persist_new(current)
                self.assertIsNone(current.action_global_id)
                self.assertIsNone(json.loads(current.payload)["actionGlobalId"])

            with self.subTest(event_type=event_type, action="legacy"):
                legacy = self.invalidation_event(
                    event_type=event_type,
                    action_global_id=str(ACTION_ID),
                )
                self.persist_new(legacy)
                self.assertEqual(legacy.action_global_id, str(ACTION_ID))
                self.assertEqual(
                    json.loads(legacy.payload)["actionGlobalId"],
                    str(ACTION_ID),
                )

            with self.subTest(event_type=event_type, successor="missing"):
                missing_successor = self.invalidation_event(event_type=event_type)
                missing_successor.successor_cycle_global_id = None
                missing_successor.payload["successorCycleGlobalId"] = None
                with self.assertRaises(self.ValidationError):
                    self.persist_new(missing_successor)

        invalid_action = self.invalidation_event(action_global_id="not-a-uuid")
        with self.assertRaises(self.ValidationError):
            self.persist_new(invalid_action)

        other_event = self.invalidation_event(action_global_id=str(ACTION_ID))
        other_event.event_type = "reopened"
        other_event.payload["eventType"] = "reopened"
        with self.assertRaises(self.ValidationError):
            self.persist_new(other_event)

    def test_idempotency_receipt_is_empty_then_sealed_exactly_once(self) -> None:
        receipt = self.idempotency()
        setattr(
            self.frappe.flags,
            self.validation.GATE_REVIEW_COMMAND_FLAG,
            True,
        )
        receipt.before_insert()
        receipt.validate()
        receipt.before_save()
        self.assertEqual(receipt.response_json, "{}")
        self.assertEqual(receipt.response_sealed, 0)

        receipt._previous = clone(receipt)
        receipt.response_json = {"ok": True}
        receipt.response_sealed = 1
        receipt.validate()
        receipt.before_save()
        self.assertEqual(receipt.response_json, '{"ok":true}')

        receipt._previous = clone(receipt)
        receipt.response_json = {"ok": False}
        with self.assertRaises(self.PermissionError):
            receipt.validate()

    def test_cycle_rejects_mutated_frozen_input_even_with_a_matching_hash(self) -> None:
        cycle = self.cycle()
        self.persist_new(cycle)
        cycle._previous = clone(cycle)
        changed = {**self.input_snapshot(), "blockers": [{"key": "open-risk"}]}
        cycle.input_snapshot = changed
        cycle.input_hash = self.validation.canonical_json_hash(changed)
        cycle.state = "decided"
        cycle.optimistic_version = 2
        cycle.before_validate()
        with self.assertRaises(self.ValidationError):
            cycle.validate()

    def test_review_record_is_actor_bound_canonical_and_append_only(self) -> None:
        record = self.record()
        self.persist_new(record)
        snapshot = json.loads(record.record_snapshot)
        self.assertEqual(
            record.review_key,
            f"{CYCLE_ID}:technical-review",
        )
        self.assertEqual(snapshot["assignment"]["memberGlobalId"], str(REVIEWER_ID))
        self.assertEqual(
            record.record_snapshot_hash,
            self.validation.canonical_json_hash(snapshot),
        )
        record._previous = clone(record)
        with self.assertRaises(self.PermissionError):
            record.validate()

        wrong_actor = self.record()
        wrong_actor.actor_user_id = "different@example.invalid"
        with self.assertRaises(self.ValidationError):
            wrong_actor.autoname()

    def test_exception_request_is_immutable_and_decision_is_one_way(self) -> None:
        exception = self.exception()
        self.persist_new(exception)
        self.assertEqual(exception.state, "pending")
        self.assertEqual(exception.optimistic_version, 1)
        request_snapshot = json.loads(exception.request_snapshot)
        self.assertEqual(
            request_snapshot["closureActionRef"],
            {
                "globalId": str(ACTION_ID),
                "version": 4,
                "snapshotHash": "8" * 64,
            },
        )
        self.assertEqual(
            exception.request_snapshot_hash,
            self.validation.canonical_json_hash(request_snapshot),
        )

        pending = clone(exception)
        exception._previous = pending
        exception.state = "approved"
        exception.optimistic_version = 2
        exception.approval_opinion = "The bounded exception is accepted."
        exception.decided_at = OCCURRED_AT
        exception.before_validate()
        exception.validate()
        self.assertEqual(
            exception.decision_snapshot_hash,
            self.validation.canonical_json_hash(
                json.loads(exception.decision_snapshot)
            ),
        )

        terminal = clone(exception)
        exception._previous = terminal
        exception.state = "rejected"
        exception.optimistic_version = 3
        exception.before_validate()
        with self.assertRaises(self.ValidationError):
            exception.validate()

        changed = self.exception()
        self.persist_new(changed)
        changed._previous = clone(changed)
        changed.reason = "A changed request is not the same exception."
        changed.state = "approved"
        changed.optimistic_version = 2
        changed.approval_opinion = "Invalid mutation."
        changed.decided_at = OCCURRED_AT
        changed.before_validate()
        with self.assertRaises(self.ValidationError):
            changed.validate()

    def test_event_and_decision_snapshots_are_full_hashed_and_append_only(self) -> None:
        event = self.invalidation_event()
        self.persist_new(event)
        payload = json.loads(event.payload)
        self.assertEqual(payload["detail"]["oldInputHash"], "3" * 64)
        self.assertIsNone(payload["actionGlobalId"])
        self.assertEqual(
            event.payload_hash,
            self.validation.canonical_json_hash(payload),
        )
        event._previous = clone(event)
        with self.assertRaises(self.PermissionError):
            event.validate()

        decision = self.decision(outcome="conditional_pass")
        self.persist_new(decision)
        expected_id = str(uuid5(CYCLE_ID, "decision-snapshot"))
        self.assertEqual(decision.global_id, expected_id)
        snapshot = json.loads(decision.decision_snapshot)
        self.assertEqual(snapshot["inputSnapshot"], self.input_snapshot())
        self.assertEqual(
            decision.snapshot_hash,
            self.validation.canonical_json_hash(snapshot),
        )
        decision._previous = clone(decision)
        with self.assertRaises(self.PermissionError):
            decision.validate()

        incomplete_conditional = self.decision(outcome="conditional_pass")
        incomplete_conditional.exception_hashes = []
        with self.assertRaises(self.ValidationError):
            incomplete_conditional.autoname()


if __name__ == "__main__":
    unittest.main()
