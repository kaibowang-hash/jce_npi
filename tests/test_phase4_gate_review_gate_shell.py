from __future__ import annotations

import hashlib
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

ROOT = Path(__file__).resolve().parents[1]
GATE_SHELL_METADATA = (
    ROOT
    / "apps/npi_core/npi_core/npi_core/doctype"
    / "npi_gate_shell/npi_gate_shell.json"
)

PROJECT_ID = UUID("54bccb5c-f681-4e9e-aa6b-57e995b26eb4")
GATE_ID = UUID("7f5c61f7-09eb-41d1-808f-359f788e806c")
TEMPLATE_ID = UUID("fa877c7d-ce33-46ba-9a2c-7a962f68a47d")
GATE_TEMPLATE_ID = UUID("e0cb8528-0ddd-434f-88fb-fdfe2a2d5164")
REQUIREMENT_ID = UUID("ef828729-44da-4ef4-8117-c66a9300ae35")
OWNER_ID = UUID("999d691f-b337-4cf4-b192-f96cc59ed08e")
REVIEWER_ID = UUID("f696c526-abaa-4752-9821-af58a62fe104")
CYCLE_ID = UUID("61b3ed2c-e78a-4c59-9390-42b3009e3f6a")
SUCCESSOR_CYCLE_ID = UUID("0e16ba6d-1325-4e3d-9dd5-c5aec674b8a4")
SECOND_SUCCESSOR_CYCLE_ID = UUID("bf3bb8d0-bbc8-4184-937e-b49c4972fb68")
POLICY_ID = UUID("084fd500-d4a5-4a61-8e29-66db7d504b8a")
DECISION_ID = UUID("d1545350-98d2-4fd8-9212-a6d213ea0fc3")


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
    return type(document)(
        {
            fieldname: value
            for fieldname, value in vars(document).items()
            if fieldname != "_previous"
        }
    )


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def snapshot_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class GateReviewGateShellMetadataTest(unittest.TestCase):
    def test_review_fields_are_additive_read_only_and_compatible(self) -> None:
        metadata = json.loads(GATE_SHELL_METADATA.read_text(encoding="utf-8"))
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        expected = {
            "review_state",
            "current_review_cycle",
            "current_review_cycle_global_id",
            "latest_decision_snapshot",
            "latest_decision_snapshot_global_id",
            "latest_decision_snapshot_hash",
            "latest_decision_outcome",
            "review_policy_global_id",
            "review_policy_version",
            "review_policy_snapshot_hash",
        }
        self.assertTrue(expected.issubset(fields))
        self.assertIn("review_input_version", fields)
        for fieldname in expected:
            with self.subTest(fieldname=fieldname):
                self.assertEqual(fields[fieldname].get("read_only"), 1)
                self.assertNotIn("reqd", fields[fieldname])
        self.assertEqual(
            fields["review_state"].get("options"),
            "not_started\nin_review\ndecided\nrequires_review",
        )
        self.assertEqual(fields["review_state"].get("default"), "not_started")
        self.assertEqual(fields["review_input_version"].get("read_only"), 1)
        self.assertEqual(fields["review_input_version"].get("reqd"), 1)
        self.assertEqual(fields["review_input_version"].get("default"), "1")
        self.assertEqual(
            fields["current_review_cycle"].get("options"),
            "NPI Gate Review Cycle",
        )
        self.assertEqual(
            fields["latest_decision_snapshot"].get("options"),
            "NPI Gate Decision Snapshot",
        )
        self.assertEqual(
            fields["latest_decision_outcome"].get("options"),
            "pass\nconditional_pass\nreject",
        )


class GateReviewGateShellControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.controlled_evidence_validation",
        "npi_core.gate_review.frappe_validation",
        "npi_core.project.frappe_validation",
        "npi_core.npi_core.doctype.npi_gate_shell.npi_gate_shell",
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

        project = types.SimpleNamespace(
            global_id=str(PROJECT_ID),
            template_global_id=str(TEMPLATE_ID),
            template_version=1,
            template_snapshot_hash="a" * 64,
        )

        def get_value(
            doctype: str,
            name: str,
            _fields: list[str],
            *,
            as_dict: bool,
        ) -> object | None:
            self.assertTrue(as_dict)
            if doctype == "NPI Engineering Project" and name == str(PROJECT_ID):
                return project
            return None

        frappe.throw = throw
        frappe.db = types.SimpleNamespace(get_value=get_value)
        model = types.ModuleType("frappe.model")
        document_module = types.ModuleType("frappe.model.document")
        document_module.Document = StubDocument
        model.document = document_module
        frappe.model = model

        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document_module

        self.frappe = frappe
        self.Controller = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_shell.npi_gate_shell"
        ).NPIGateShell

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def shell(
        self,
        *,
        frozen: bool,
        include_review_defaults: bool = True,
    ) -> StubDocument:
        gate_template_ref = {
            "globalId": str(GATE_TEMPLATE_ID),
            "version": 1,
            "snapshotHash": "b" * 64,
        }
        gate_snapshot = {
            "key": "G0",
            "sequence": 1,
            "title": "Synthetic Gate",
            "gateTemplateRef": gate_template_ref,
        }
        requirement_snapshot = {
            "schemaVersion": 1,
            "gateTemplateRef": gate_template_ref,
            "gateDueDate": "2026-08-01",
            "requirements": [
                {
                    "globalId": str(REQUIREMENT_ID),
                    "key": "drawing",
                    "title": "Drawing",
                    "classification": "required",
                    "priority": "P0",
                    "allowedEvidenceKinds": ["file_revision"],
                    "ownerMemberId": str(OWNER_ID),
                    "reviewerMemberIds": [str(REVIEWER_ID)],
                    "dueDate": "2026-08-01",
                }
            ],
        }
        values: dict[str, Any] = {
            "global_id": str(GATE_ID),
            "engineering_project": str(PROJECT_ID),
            "project_global_id": str(PROJECT_ID),
            "gate_key": "G0",
            "shell_key": f"{PROJECT_ID}:G0",
            "title": "Synthetic Gate",
            "sequence": 1,
            "state": "not_started",
            "optimistic_version": 1,
            "template_global_id": str(TEMPLATE_ID),
            "template_version": 1,
            "template_snapshot_hash": "a" * 64,
            "template_gate_snapshot": canonical_json(gate_snapshot),
            "gate_template_global_id": str(GATE_TEMPLATE_ID),
            "gate_template_version": 1,
            "gate_template_snapshot_hash": "b" * 64,
            "requirements_frozen": 1 if frozen else 0,
            "gate_due_date": "2026-08-01" if frozen else None,
            "requirement_snapshot": (
                canonical_json(requirement_snapshot) if frozen else None
            ),
            "requirement_snapshot_hash": (
                snapshot_hash(requirement_snapshot) if frozen else None
            ),
            "requirements_frozen_at": (
                "2026-07-24 08:30:00.000000" if frozen else None
            ),
            "requirements_frozen_by": ("owner@example.invalid" if frozen else None),
        }
        if include_review_defaults:
            values.update(
                {
                    "review_input_version": 1,
                    "review_state": "not_started",
                    "current_review_cycle": None,
                    "current_review_cycle_global_id": None,
                    "latest_decision_snapshot": None,
                    "latest_decision_snapshot_global_id": None,
                    "latest_decision_snapshot_hash": None,
                    "latest_decision_outcome": None,
                    "review_policy_global_id": None,
                    "review_policy_version": None,
                    "review_policy_snapshot_hash": None,
                }
            )
        return self.Controller(values)

    def set_review_context(
        self,
        document: StubDocument,
        *,
        cycle_id: UUID = CYCLE_ID,
    ) -> None:
        document.current_review_cycle = str(cycle_id)
        document.current_review_cycle_global_id = str(cycle_id)
        document.review_policy_global_id = str(POLICY_ID)
        document.review_policy_version = 1
        document.review_policy_snapshot_hash = "c" * 64

    def validate_existing(
        self,
        document: StubDocument,
        previous: StubDocument,
        *,
        review: bool = False,
        evidence: bool = False,
        dependency_input: bool = False,
    ) -> None:
        document._previous = previous
        self.frappe.flags = types.SimpleNamespace(
            npi_gate_review_command_write=review,
            npi_gate_evidence_command_write=evidence,
            npi_project_command_write=evidence,
            npi_gate_review_dependency_input_write=dependency_input,
        )
        document.before_validate()
        document.validate()
        document.before_save()

    def test_new_legacy_shell_and_first_evidence_freeze_remain_valid(self) -> None:
        new_shell = self.shell(frozen=False, include_review_defaults=False)
        new_shell._previous = None
        self.frappe.flags.npi_project_command_write = True
        new_shell.before_validate()
        new_shell.validate()
        new_shell.before_insert()
        new_shell.before_save()
        self.assertEqual(new_shell.review_state, "not_started")
        self.assertEqual(new_shell.review_input_version, 1)
        self.assertIsNone(new_shell.current_review_cycle)

        legacy = self.shell(frozen=False, include_review_defaults=False)
        frozen = self.shell(frozen=True, include_review_defaults=False)
        frozen.optimistic_version = 2
        self.validate_existing(frozen, legacy, evidence=True)
        self.assertEqual(frozen.review_state, "not_started")
        self.assertEqual(frozen.optimistic_version, 2)
        self.assertEqual(frozen.review_input_version, 2)

    def test_generic_and_evidence_commands_cannot_set_review_pointers(self) -> None:
        previous = self.shell(frozen=True)
        attempted = clone(previous)
        attempted.optimistic_version = 2
        attempted.review_state = "in_review"
        self.set_review_context(attempted)
        attempted._previous = previous

        self.frappe.flags = types.SimpleNamespace(
            npi_project_command_write=True,
        )
        with self.assertRaises(self.PermissionError):
            attempted.before_validate()

        attempted._previous = previous
        self.frappe.flags = types.SimpleNamespace(
            npi_project_command_write=True,
            npi_gate_evidence_command_write=True,
        )
        attempted.before_validate()
        with self.assertRaises(self.ValidationError):
            attempted.validate()

        project_drift = clone(previous)
        project_drift.optimistic_version = 2
        project_drift.review_input_version = 99
        project_drift._previous = previous
        self.frappe.flags = types.SimpleNamespace(
            npi_project_command_write=True,
        )
        with self.assertRaises(self.PermissionError):
            project_drift.before_validate()

    def test_evidence_commands_advance_only_the_review_input_version(self) -> None:
        previous = self.shell(frozen=True)
        previous.optimistic_version = 2
        previous.review_input_version = 2

        attached = clone(previous)
        attached.optimistic_version = 3
        attached.review_input_version = 99
        self.validate_existing(attached, previous, evidence=True)
        self.assertEqual(attached.optimistic_version, 3)
        self.assertEqual(attached.review_input_version, 3)
        self.assertEqual(attached.review_state, "not_started")
        self.assertIsNone(attached.current_review_cycle)

        stale_gate_version = clone(attached)
        stale_gate_version.review_input_version = 99
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                stale_gate_version,
                attached,
                evidence=True,
            )

    def test_dependency_input_command_advances_only_the_input_version(self) -> None:
        previous = self.shell(frozen=True)
        previous.optimistic_version = 3
        previous.review_input_version = 4
        previous.review_state = "decided"
        self.set_review_context(previous)
        previous.latest_decision_snapshot = str(DECISION_ID)
        previous.latest_decision_snapshot_global_id = str(DECISION_ID)
        previous.latest_decision_snapshot_hash = "d" * 64
        previous.latest_decision_outcome = "conditional_pass"

        advanced = clone(previous)
        advanced.optimistic_version = 4
        advanced.review_input_version = 99
        self.validate_existing(
            advanced,
            previous,
            dependency_input=True,
        )
        self.assertEqual(advanced.review_input_version, 5)
        self.assertEqual(advanced.review_state, "decided")
        self.assertEqual(
            advanced.current_review_cycle_global_id,
            previous.current_review_cycle_global_id,
        )
        self.assertEqual(
            advanced.latest_decision_snapshot_hash,
            previous.latest_decision_snapshot_hash,
        )

        invalidated = clone(previous)
        invalidated.optimistic_version = 4
        invalidated.review_input_version = 99
        invalidated.review_state = "requires_review"
        invalidated.current_review_cycle = str(SUCCESSOR_CYCLE_ID)
        invalidated.current_review_cycle_global_id = str(SUCCESSOR_CYCLE_ID)
        self.validate_existing(
            invalidated,
            previous,
            review=True,
            dependency_input=True,
        )
        self.assertEqual(invalidated.review_input_version, 5)
        self.assertEqual(invalidated.optimistic_version, 4)
        self.assertEqual(invalidated.review_state, "requires_review")

        ordinary_review = clone(previous)
        ordinary_review.optimistic_version = 4
        ordinary_review.review_input_version = 5
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                ordinary_review,
                previous,
                review=True,
            )

    def test_review_command_can_start_decide_invalidate_and_reopen(self) -> None:
        not_started = self.shell(frozen=True)

        active = clone(not_started)
        active.optimistic_version = 2
        active.review_state = "in_review"
        self.set_review_context(active)
        self.validate_existing(active, not_started, review=True)
        self.assertEqual(active.review_input_version, 1)

        decided = clone(active)
        decided.optimistic_version = 3
        decided.review_state = "decided"
        decided.latest_decision_snapshot = str(DECISION_ID)
        decided.latest_decision_snapshot_global_id = str(DECISION_ID)
        decided.latest_decision_snapshot_hash = "d" * 64
        decided.latest_decision_outcome = "conditional_pass"
        self.validate_existing(decided, active, review=True)
        self.assertEqual(decided.review_input_version, 1)

        manual_reopen = clone(decided)
        manual_reopen.optimistic_version = 4
        manual_reopen.review_state = "in_review"
        manual_reopen.current_review_cycle = str(SUCCESSOR_CYCLE_ID)
        manual_reopen.current_review_cycle_global_id = str(SUCCESSOR_CYCLE_ID)
        self.validate_existing(manual_reopen, decided, review=True)
        self.assertEqual(manual_reopen.review_input_version, 1)

        requires_review = clone(decided)
        requires_review.optimistic_version = 4
        requires_review.review_state = "requires_review"
        requires_review.current_review_cycle = str(SUCCESSOR_CYCLE_ID)
        requires_review.current_review_cycle_global_id = str(SUCCESSOR_CYCLE_ID)
        self.validate_existing(requires_review, decided, review=True)
        self.assertEqual(requires_review.review_input_version, 1)

        reopened = clone(requires_review)
        reopened.optimistic_version = 5
        reopened.review_state = "in_review"
        self.validate_existing(reopened, requires_review, review=True)
        self.assertEqual(reopened.review_input_version, 1)

        active_requires_review = clone(active)
        active_requires_review.optimistic_version = 3
        active_requires_review.review_state = "requires_review"
        active_requires_review.current_review_cycle = str(SUCCESSOR_CYCLE_ID)
        active_requires_review.current_review_cycle_global_id = str(SUCCESSOR_CYCLE_ID)
        self.validate_existing(active_requires_review, active, review=True)

        refreshed_requires_review = clone(active_requires_review)
        refreshed_requires_review.optimistic_version = 4
        refreshed_requires_review.current_review_cycle = str(SECOND_SUCCESSOR_CYCLE_ID)
        refreshed_requires_review.current_review_cycle_global_id = str(
            SECOND_SUCCESSOR_CYCLE_ID
        )
        self.validate_existing(
            refreshed_requires_review,
            active_requires_review,
            review=True,
        )

    def test_review_pointer_drift_and_incoherent_decision_fail_closed(self) -> None:
        not_started = self.shell(frozen=True)
        active = clone(not_started)
        active.optimistic_version = 2
        active.review_state = "in_review"
        self.set_review_context(active)
        self.validate_existing(active, not_started, review=True)

        drifted = clone(active)
        drifted.optimistic_version = 3
        drifted.current_review_cycle = str(SUCCESSOR_CYCLE_ID)
        drifted.current_review_cycle_global_id = str(SUCCESSOR_CYCLE_ID)
        with self.assertRaises(self.ValidationError):
            self.validate_existing(drifted, active, review=True)

        context_drift_at_decision = clone(active)
        context_drift_at_decision.optimistic_version = 3
        context_drift_at_decision.review_state = "decided"
        self.set_review_context(
            context_drift_at_decision,
            cycle_id=SUCCESSOR_CYCLE_ID,
        )
        context_drift_at_decision.latest_decision_snapshot = str(DECISION_ID)
        context_drift_at_decision.latest_decision_snapshot_global_id = str(DECISION_ID)
        context_drift_at_decision.latest_decision_snapshot_hash = "d" * 64
        context_drift_at_decision.latest_decision_outcome = "pass"
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                context_drift_at_decision,
                active,
                review=True,
            )

        input_version_drift = clone(active)
        input_version_drift.optimistic_version = 3
        input_version_drift.review_input_version = 2
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                input_version_drift,
                active,
                review=True,
            )

        stray_decision = clone(active)
        stray_decision.optimistic_version = 3
        stray_decision.latest_decision_snapshot = str(DECISION_ID)
        stray_decision.latest_decision_snapshot_global_id = str(DECISION_ID)
        stray_decision.latest_decision_snapshot_hash = "d" * 64
        stray_decision.latest_decision_outcome = "pass"
        with self.assertRaises(self.ValidationError):
            self.validate_existing(stray_decision, active, review=True)

        incomplete = clone(active)
        incomplete.optimistic_version = 3
        incomplete.review_state = "decided"
        incomplete.latest_decision_snapshot = str(DECISION_ID)
        incomplete.latest_decision_snapshot_global_id = str(DECISION_ID)
        incomplete.latest_decision_outcome = "pass"
        with self.assertRaises(self.ValidationError):
            self.validate_existing(incomplete, active, review=True)

        invented_invalidation = clone(active)
        invented_invalidation.optimistic_version = 3
        invented_invalidation.review_state = "requires_review"
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                invented_invalidation,
                active,
                review=True,
            )

        policy_drift_at_invalidation = clone(active)
        policy_drift_at_invalidation.optimistic_version = 3
        policy_drift_at_invalidation.review_state = "requires_review"
        policy_drift_at_invalidation.current_review_cycle = str(SUCCESSOR_CYCLE_ID)
        policy_drift_at_invalidation.current_review_cycle_global_id = str(
            SUCCESSOR_CYCLE_ID
        )
        policy_drift_at_invalidation.review_policy_version = 2
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                policy_drift_at_invalidation,
                active,
                review=True,
            )

        decided = clone(active)
        decided.optimistic_version = 3
        decided.review_state = "decided"
        decided.latest_decision_snapshot = str(DECISION_ID)
        decided.latest_decision_snapshot_global_id = str(DECISION_ID)
        decided.latest_decision_snapshot_hash = "d" * 64
        decided.latest_decision_outcome = "pass"
        self.validate_existing(decided, active, review=True)

        same_cycle_reopen = clone(decided)
        same_cycle_reopen.optimistic_version = 4
        same_cycle_reopen.review_state = "in_review"
        with self.assertRaises(self.ValidationError):
            self.validate_existing(same_cycle_reopen, decided, review=True)

        requires_review = clone(decided)
        requires_review.optimistic_version = 4
        requires_review.review_state = "requires_review"
        requires_review.current_review_cycle = str(SUCCESSOR_CYCLE_ID)
        requires_review.current_review_cycle_global_id = str(SUCCESSOR_CYCLE_ID)
        self.validate_existing(requires_review, decided, review=True)

        cleared_history = clone(requires_review)
        cleared_history.optimistic_version = 5
        cleared_history.latest_decision_snapshot = None
        cleared_history.latest_decision_snapshot_global_id = None
        cleared_history.latest_decision_snapshot_hash = None
        cleared_history.latest_decision_outcome = None
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                cleared_history,
                requires_review,
                review=True,
            )

        changed_successor = clone(requires_review)
        changed_successor.optimistic_version = 5
        changed_successor.review_state = "in_review"
        changed_successor.current_review_cycle = str(CYCLE_ID)
        changed_successor.current_review_cycle_global_id = str(CYCLE_ID)
        with self.assertRaises(self.ValidationError):
            self.validate_existing(
                changed_successor,
                requires_review,
                review=True,
            )

    def test_review_cannot_start_before_requirements_are_frozen(self) -> None:
        not_started = self.shell(frozen=False)
        active = clone(not_started)
        active.optimistic_version = 2
        active.review_state = "in_review"
        self.set_review_context(active)
        with self.assertRaises(self.ValidationError):
            self.validate_existing(active, not_started, review=True)


if __name__ == "__main__":
    unittest.main()
