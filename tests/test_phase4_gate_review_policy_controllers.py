from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

sys.path.insert(0, "apps/npi_core")


POLICY_ID = UUID("2e61347c-313a-4443-b531-b605e90d5f45")
GATE_TEMPLATE_ID = UUID("27a34964-9987-4e3c-b010-2e5165782c62")


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def get_doc_before_save(self) -> Any:
        return self._previous


class GateReviewPolicyControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        "npi_core.gate_review.frappe_validation",
        "npi_core.project.frappe_validation",
        "npi_core.gate_template.frappe_repository",
        ("npi_core.npi_core.doctype.npi_gate_review_policy.npi_gate_review_policy"),
        (
            "npi_core.npi_core.doctype.npi_gate_review_policy_version"
            ".npi_gate_review_policy_version"
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
        self.version_rows: dict[str, AttrDict] = {}
        self.root_has_versions = False

        def get_value(
            doctype: str,
            name: object,
            fields: list[str],
            *,
            as_dict: bool,
        ) -> AttrDict | None:
            self.assertTrue(as_dict)
            if doctype == "NPI Gate Review Policy":
                self.assertEqual(name, str(POLICY_ID))
                self.assertEqual(fields, ["global_id", "policy_code"])
                return AttrDict(
                    global_id=str(POLICY_ID),
                    policy_code="SYNTHETIC-P4-04",
                )
            self.assertEqual(doctype, "NPI Gate Review Policy Version")
            if isinstance(name, dict):
                self.assertEqual(
                    name,
                    {"policy_global_id": str(POLICY_ID)},
                )
                self.assertEqual(fields, ["name"])
                return (
                    AttrDict(name=next(iter(self.version_rows)))
                    if self.version_rows
                    else None
                )
            self.assertEqual(fields, ["publication_state"])
            return self.version_rows.get(str(name))

        def exists(doctype: str, filters: dict[str, object]) -> bool:
            self.assertEqual(doctype, "NPI Gate Review Policy Version")
            self.assertEqual(filters, {"policy_global_id": str(POLICY_ID)})
            return self.root_has_versions

        frappe.db = types.SimpleNamespace(get_value=get_value, exists=exists)
        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        utils = types.ModuleType("frappe.utils")
        utils.now_datetime = lambda: datetime(2026, 7, 24, 8, 0, 0, tzinfo=UTC)
        frappe.model = model
        frappe.utils = utils
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document
        sys.modules["frappe.utils"] = utils

        self.template_available = True
        self.template_calls: list[tuple[UUID, int, str, bool]] = []
        gate_repository = types.ModuleType("npi_core.gate_template.frappe_repository")

        def load_published_gate_template_version(
            gate_template_global_id: UUID,
            gate_template_version: int,
            expected_snapshot_hash: str,
            *,
            require_enabled_root: bool = False,
        ) -> object | None:
            self.template_calls.append(
                (
                    gate_template_global_id,
                    gate_template_version,
                    expected_snapshot_hash,
                    require_enabled_root,
                )
            )
            return object() if self.template_available else None

        gate_repository.load_published_gate_template_version = (
            load_published_gate_template_version
        )
        sys.modules["npi_core.gate_template.frappe_repository"] = gate_repository

        root_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_review_policy.npi_gate_review_policy"
        )
        version_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_review_policy_version"
            ".npi_gate_review_policy_version"
        )
        self.RootController = root_module.NPIGateReviewPolicy
        self.VersionController = version_module.NPIGateReviewPolicyVersion

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def version_document(
        self,
        *,
        publication_state: str = "published",
        policy_version: int = 1,
        global_id: object = None,
        review_steps: object = None,
        exception_rules: object = None,
        dependency_evaluators: object = None,
    ) -> StubDocument:
        value = self.VersionController(
            {
                "global_id": global_id,
                "gate_review_policy": str(POLICY_ID),
                "policy_global_id": None,
                "policy_code": None,
                "policy_version": policy_version,
                "version_key": None,
                "optimistic_version": 1,
                "title": "  Synthetic Gate review policy  ",
                "publication_state": publication_state,
                "gate_template_global_id": str(GATE_TEMPLATE_ID),
                "gate_template_version": 1,
                "gate_template_snapshot_hash": "b" * 64,
                "review_steps": (
                    review_steps
                    if review_steps is not None
                    else [
                        {
                            "key": "engineering",
                            "sequence": 1,
                            "authoritySlot": "engineering_reviewer",
                            "activation": "always",
                            "activationPriority": None,
                        },
                        {
                            "key": "quality",
                            "sequence": 2,
                            "authoritySlot": "quality_reviewer",
                            "activation": "requirement_priority_present",
                            "activationPriority": "P0",
                        },
                    ]
                ),
                "decision_authority_slot": "gate_decider",
                "reopen_authority_slot": "gate_reopener",
                "exception_rules": (
                    exception_rules
                    if exception_rules is not None
                    else [
                        {
                            "kind": "p1_evidence_timing",
                            "eligibleRequirementKeys": ["supplier_timing"],
                            "approvalAuthoritySlot": "exception_approver",
                            "maximumValidityDays": 14,
                            "requiredClosureActionKind": "action",
                        }
                    ]
                ),
                "dependency_evaluators": (
                    dependency_evaluators
                    if dependency_evaluators is not None
                    else ["gate_input_snapshot"]
                ),
                "snapshot": None,
                "snapshot_hash": None,
                "published_at": None,
            }
        )
        value.before_validate()
        return value

    @staticmethod
    def previous(document: StubDocument) -> AttrDict:
        return AttrDict(
            {
                fieldname: getattr(document, fieldname)
                for fieldname in (
                    "global_id",
                    "gate_review_policy",
                    "policy_global_id",
                    "policy_code",
                    "policy_version",
                    "version_key",
                    "optimistic_version",
                    "publication_state",
                    "published_at",
                )
            }
        )

    def test_root_and_published_version_normalize_exact_identity_and_snapshot(
        self,
    ) -> None:
        root = self.RootController(
            {
                "global_id": str(POLICY_ID),
                "policy_code": "  SYNTHETIC-P4-04  ",
                "title": "  Synthetic policy  ",
                "enabled": 1,
            }
        )
        root.validate()
        self.assertEqual(root.policy_code, "SYNTHETIC-P4-04")
        self.assertEqual(root.title, "Synthetic policy")

        version = self.version_document()
        version.validate()
        self.assertEqual(version.global_id, str(uuid5(POLICY_ID, "version:1")))
        self.assertEqual(version.version_key, f"{POLICY_ID}:1")
        self.assertEqual(version.optimistic_version, 2)
        self.assertEqual(version.title, "Synthetic Gate review policy")
        self.assertEqual(version.publication_state, "published")
        self.assertEqual(len(version.snapshot_hash), 64)
        self.assertEqual(
            json.loads(version.snapshot)["dependencyEvaluators"],
            ["gate_input_snapshot"],
        )
        self.assertEqual(
            version.published_at,
            datetime(2026, 7, 24, 8, 0, 0, tzinfo=UTC),
        )
        self.assertEqual(
            self.template_calls,
            [(GATE_TEMPLATE_ID, 1, "b" * 64, True)],
        )
        with self.assertRaises(self.ValidationError):
            self.version_document(
                global_id="00000000-0000-4000-8000-000000000001",
            )

    def test_draft_optimistic_version_and_published_immutability(self) -> None:
        draft = self.version_document(publication_state="draft")
        draft.validate()
        self.assertEqual(draft.optimistic_version, 1)
        self.assertIsNone(draft.published_at)
        draft._previous = self.previous(draft)
        draft.title = "Revised synthetic policy"
        draft.validate()
        self.assertEqual(draft.optimistic_version, 2)

        published = self.version_document()
        published.validate()
        published._previous = self.previous(published)
        with self.assertRaises(self.ValidationError):
            published.validate()
        with self.assertRaises(self.PermissionError):
            published.on_trash()

    def test_versions_are_contiguous_and_follow_a_published_version(self) -> None:
        with self.assertRaises(self.ValidationError):
            self.version_document(policy_version=2).validate()
        first_key = f"{POLICY_ID}:1"
        self.version_rows[first_key] = AttrDict(publication_state="draft")
        with self.assertRaises(self.ValidationError):
            self.version_document(policy_version=2).validate()
        self.version_rows[first_key].publication_state = "published"
        second = self.version_document(
            publication_state="draft",
            policy_version=2,
        )
        second.validate()
        self.assertEqual(second.global_id, str(uuid5(POLICY_ID, "version:2")))
        self.assertEqual(second.version_key, f"{POLICY_ID}:2")
        with self.assertRaises(self.ValidationError):
            self.version_document(policy_version=1).validate()

    def test_closed_json_template_and_root_history_fail_closed(self) -> None:
        valid_step = {
            "key": "engineering",
            "sequence": 1,
            "authoritySlot": "engineering_reviewer",
            "activation": "always",
            "activationPriority": None,
        }
        invalid_documents = (
            self.version_document(
                review_steps=[{**valid_step, "script": "return true"}]
            ),
            self.version_document(
                exception_rules=[
                    {
                        "kind": "timing",
                        "eligibleRequirementKeys": "abc",
                        "approvalAuthoritySlot": "approver",
                        "maximumValidityDays": 14,
                        "requiredClosureActionKind": "action",
                    }
                ]
            ),
            self.version_document(dependency_evaluators=["script"]),
        )
        for index, document in enumerate(invalid_documents):
            with (
                self.subTest(index=index),
                self.assertRaises(self.ValidationError),
            ):
                document.validate()

        self.template_available = False
        with self.assertRaises(self.ValidationError):
            self.version_document().validate()

        root = self.RootController(
            {
                "global_id": str(POLICY_ID),
                "policy_code": "SYNTHETIC-P4-04",
                "title": "Synthetic policy",
                "enabled": 1,
            }
        )
        self.root_has_versions = True
        with self.assertRaises(self.PermissionError):
            root.on_trash()


if __name__ == "__main__":
    unittest.main()
