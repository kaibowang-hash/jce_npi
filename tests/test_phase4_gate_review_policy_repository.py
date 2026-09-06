from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from typing import Any
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.gate_review.domain import (
    ActivationKind,
    DependencyEvaluator,
    ExceptionRule,
    ReviewPolicyVersion,
    ReviewStep,
)

POLICY_ID = UUID("2e61347c-313a-4443-b531-b605e90d5f45")
GATE_TEMPLATE_ID = UUID("27a34964-9987-4e3c-b010-2e5165782c62")


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


def _policy() -> ReviewPolicyVersion:
    return ReviewPolicyVersion.create_draft(
        policy_global_id=POLICY_ID,
        policy_code="SYNTHETIC-P4-04",
        gate_template_global_id=GATE_TEMPLATE_ID,
        gate_template_version=1,
        gate_template_hash="b" * 64,
        steps=(
            ReviewStep("engineering", 1, "engineering_reviewer"),
            ReviewStep(
                "quality",
                2,
                "quality_reviewer",
                ActivationKind.REQUIREMENT_PRIORITY_PRESENT,
                "P0",
            ),
        ),
        decision_authority_slot="gate_decider",
        reopen_authority_slot="gate_reopener",
        exception_rules=(
            ExceptionRule(
                "p1_evidence_timing",
                ("supplier_timing",),
                "exception_approver",
                14,
                "action",
            ),
        ),
        dependency_evaluators=(DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
    ).publish(1)


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class GateReviewPolicyRepositoryTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "npi_core.gate_template.frappe_repository",
        "npi_core.gate_review.frappe_policy_repository",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        frappe = types.ModuleType("frappe")
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.registry: dict[tuple[str, str], AttrDict] = {}

        def get_doc(doctype: str, name: str):
            try:
                return self.registry[(doctype, name)]
            except KeyError as error:
                raise frappe.DoesNotExistError() from error

        frappe.get_doc = get_doc
        sys.modules["frappe"] = frappe

        self.template_available = True
        self.template_calls: list[tuple[UUID, int, str]] = []
        gate_repository = types.ModuleType("npi_core.gate_template.frappe_repository")

        def load_published_gate_template_version(
            gate_template_global_id: UUID,
            gate_template_version: int,
            expected_snapshot_hash: str,
            *,
            require_enabled_root: bool = False,
        ) -> object | None:
            self.assertFalse(require_enabled_root)
            self.template_calls.append(
                (
                    gate_template_global_id,
                    gate_template_version,
                    expected_snapshot_hash,
                )
            )
            return object() if self.template_available else None

        gate_repository.load_published_gate_template_version = (
            load_published_gate_template_version
        )
        sys.modules["npi_core.gate_template.frappe_repository"] = gate_repository
        self.repository = importlib.import_module(
            "npi_core.gate_review.frappe_policy_repository"
        )
        self.persist(_policy())

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def persist(self, policy: ReviewPolicyVersion) -> AttrDict:
        snapshot = policy.canonical_dict()
        root = AttrDict(
            global_id=str(policy.policy_global_id),
            policy_code=policy.policy_code,
            enabled=1,
        )
        version = AttrDict(
            global_id=str(policy.global_id),
            gate_review_policy=str(policy.policy_global_id),
            policy_global_id=str(policy.policy_global_id),
            policy_code=policy.policy_code,
            policy_version=policy.policy_version,
            version_key=f"{policy.policy_global_id}:{policy.policy_version}",
            optimistic_version=policy.version,
            publication_state=policy.state.value,
            gate_template_global_id=str(policy.gate_template_global_id),
            gate_template_version=policy.gate_template_version,
            gate_template_snapshot_hash=policy.gate_template_hash,
            review_steps=_canonical(snapshot["steps"]),
            decision_authority_slot=policy.decision_authority_slot,
            reopen_authority_slot=policy.reopen_authority_slot,
            exception_rules=_canonical(snapshot["exceptionRules"]),
            dependency_evaluators=_canonical(snapshot["dependencyEvaluators"]),
            snapshot=_canonical(snapshot),
            snapshot_hash=policy.snapshot_hash,
            published_at="2026-07-24 08:00:00",
        )
        self.registry[("NPI Gate Review Policy", str(policy.policy_global_id))] = root
        self.registry[
            (
                "NPI Gate Review Policy Version",
                f"{policy.policy_global_id}:{policy.policy_version}",
            )
        ] = version
        return version

    def test_exact_loader_hydrates_domain_and_disabled_root_remains_historical(
        self,
    ) -> None:
        expected = _policy()
        loaded = self.repository.load_exact_gate_review_policy_version(
            POLICY_ID,
            1,
            expected.snapshot_hash,
        )
        self.assertEqual(loaded, expected)
        self.assertEqual(
            self.template_calls,
            [(GATE_TEMPLATE_ID, 1, "b" * 64)],
        )

        root = self.registry[("NPI Gate Review Policy", str(POLICY_ID))]
        root.enabled = 0
        historical = self.repository.load_exact_gate_review_policy_version(
            POLICY_ID,
            1,
            expected.snapshot_hash,
        )
        self.assertEqual(historical, expected)
        self.assertIsNone(
            self.repository.load_available_gate_review_policy_version(
                POLICY_ID,
                1,
                expected.snapshot_hash,
            )
        )

    def test_missing_and_drifted_policy_fail_closed(self) -> None:
        expected = _policy()
        self.assertIsNone(
            self.repository.load_exact_gate_review_policy_version(
                UUID("00000000-0000-4000-8000-000000000001"),
                1,
                expected.snapshot_hash,
            )
        )
        version = self.registry[("NPI Gate Review Policy Version", f"{POLICY_ID}:1")]
        cases = (
            ("snapshot_hash", "f" * 64),
            ("snapshot", "{}"),
            (
                "review_steps",
                json.dumps(expected.canonical_dict()["steps"]),
            ),
            ("publication_state", "draft"),
            ("published_at", None),
        )
        for fieldname, invalid in cases:
            with self.subTest(fieldname=fieldname):
                original = version[fieldname]
                version[fieldname] = invalid
                with self.assertRaises(ValueError):
                    self.repository.load_exact_gate_review_policy_version(
                        POLICY_ID,
                        1,
                        expected.snapshot_hash,
                    )
                version[fieldname] = original

        with self.assertRaises(ValueError):
            self.repository.load_exact_gate_review_policy_version(
                POLICY_ID,
                1,
                "f" * 64,
            )
        self.template_available = False
        with self.assertRaises(ValueError):
            self.repository.load_exact_gate_review_policy_version(
                POLICY_ID,
                1,
                expected.snapshot_hash,
            )


if __name__ == "__main__":
    unittest.main()
