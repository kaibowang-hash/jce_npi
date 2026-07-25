from __future__ import annotations

import hashlib
import importlib
import json
import sys
import types
import unittest
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5


sys.path.insert(0, "apps/npi_core")

POLICY_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_ID = UUID("22222222-2222-4222-8222-222222222222")
VERSION_NAMESPACE = UUID("479fe5c8-cda3-4a07-ab48-6c649592f95a")
PUBLISHED_AT = datetime(2026, 7, 25, 10, 30, tzinfo=UTC)
_UNSET = object()


class AttrDict(dict):
    def __getattr__(self, fieldname: str) -> Any:
        try:
            return self[fieldname]
        except KeyError as error:
            raise AttributeError(fieldname) from error


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def get_doc_before_save(self) -> Any:
        return self._previous


class ProjectControlPolicyVersionControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        (
            "npi_core.npi_core.doctype.npi_project_control_policy_version"
            ".npi_project_control_policy_version"
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
        self.root = AttrDict(
            global_id=str(POLICY_ID),
            policy_code="synthetic_project_control",
            enabled=1,
        )
        self.version_rows: dict[str, AttrDict] = {}

        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = self.PermissionError

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        def get_value(
            doctype: str,
            name: object,
            fields: list[str],
            *,
            as_dict: bool,
        ) -> AttrDict | None:
            self.assertTrue(as_dict)
            if doctype == "NPI Project Control Policy":
                self.assertEqual(
                    fields,
                    ["global_id", "policy_code", "enabled"],
                )
                return self.root
            self.assertEqual(
                doctype,
                "NPI Project Control Policy Version",
            )
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
            self.assertEqual(
                fields,
                self.module._PRIOR_FIELDS,
            )
            return self.version_rows.get(str(name))

        frappe.throw = throw
        frappe.db = types.SimpleNamespace(get_value=get_value)
        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        utils = types.ModuleType("frappe.utils")
        utils.now_datetime = lambda: PUBLISHED_AT
        frappe.model = model
        frappe.utils = utils

        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document
        sys.modules["frappe.utils"] = utils

        self.module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_project_control_policy_version"
            ".npi_project_control_policy_version"
        )
        self.Controller = self.module.NPIProjectControlPolicyVersion

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    @staticmethod
    def health_rules() -> list[dict[str, object]]:
        return [
            {
                "dimension": "progress",
                "mode": "higher_is_better",
                "greenThreshold": 80,
                "yellowThreshold": 60,
            },
            {
                "dimension": "cost",
                "mode": "lower_is_better",
                "greenThreshold": 100,
                "yellowThreshold": 120,
            },
            {
                "dimension": "quality",
                "mode": "manual",
                "greenThreshold": None,
                "yellowThreshold": None,
            },
            {
                "dimension": "risk",
                "mode": "unavailable",
                "greenThreshold": None,
                "yellowThreshold": None,
            },
        ]

    @staticmethod
    def transitions() -> list[dict[str, object]]:
        return [
            {
                "sourceState": "active",
                "action": "pause",
                "targetState": "on_hold",
                "authoritySlot": "project_controller",
                "prerequisites": [],
            },
            {
                "sourceState": "active",
                "action": "cancel",
                "targetState": "cancelled",
                "authoritySlot": "project_sponsor",
                "prerequisites": ["open_blockers"],
            },
            {
                "sourceState": "on_hold",
                "action": "resume",
                "targetState": "active",
                "authoritySlot": "project_controller",
                "prerequisites": [],
            },
            {
                "sourceState": "active",
                "action": "complete",
                "targetState": "completed",
                "authoritySlot": "project_controller",
                "prerequisites": [
                    "open_blockers",
                    "controlled_files",
                    "handover",
                    "cost",
                ],
            },
        ]

    def version_document(
        self,
        *,
        policy_version: int = 1,
        publication_state: str = "published",
        global_id: object = None,
        policy_global_id: object = None,
        policy_code: object = None,
        prior_version_ref: object = None,
        authority_slots: object = _UNSET,
        health_rules: object = _UNSET,
        require_all_dimensions: object = 1,
        lifecycle_transitions: object = _UNSET,
    ) -> StubDocument:
        document = self.Controller(
            {
                "global_id": global_id,
                "project_control_policy": str(POLICY_ID),
                "policy_global_id": policy_global_id,
                "policy_code": policy_code,
                "policy_version": policy_version,
                "version_key": None,
                "optimistic_version": 1,
                "title": "  Synthetic Project control policy  ",
                "publication_state": publication_state,
                "prior_version_ref": prior_version_ref,
                "authority_slots": json.dumps(
                    (
                        ["project_controller", "project_sponsor"]
                        if authority_slots is _UNSET
                        else authority_slots
                    )
                ),
                "health_assessment_slot": "project_controller",
                "health_rules": json.dumps(
                    (self.health_rules() if health_rules is _UNSET else health_rules)
                ),
                "require_all_dimensions": require_all_dimensions,
                "lifecycle_transitions": json.dumps(
                    (
                        self.transitions()
                        if lifecycle_transitions is _UNSET
                        else lifecycle_transitions
                    )
                ),
                "snapshot": None,
                "snapshot_hash": None,
                "published_at": None,
            }
        )
        document.before_validate()
        return document

    @staticmethod
    def previous(document: StubDocument) -> AttrDict:
        return AttrDict(
            {
                fieldname: getattr(document, fieldname, None)
                for fieldname in (
                    "global_id",
                    "project_control_policy",
                    "policy_global_id",
                    "policy_code",
                    "policy_version",
                    "version_key",
                    "optimistic_version",
                    "title",
                    "publication_state",
                    "prior_version_ref",
                    "published_at",
                )
            }
        )

    def persist(self, document: StubDocument) -> AttrDict:
        row = AttrDict(
            name=document.version_key,
            global_id=document.global_id,
            policy_global_id=document.policy_global_id,
            policy_code=document.policy_code,
            policy_version=document.policy_version,
            publication_state=document.publication_state,
            snapshot=document.snapshot,
            snapshot_hash=document.snapshot_hash,
        )
        self.version_rows[document.version_key] = row
        return row

    def test_published_policy_writes_canonical_domain_snapshot(self) -> None:
        document = self.version_document()
        document.autoname()
        document.validate()
        snapshot = json.loads(document.snapshot)

        expected_global_id = uuid5(
            VERSION_NAMESPACE,
            f"{POLICY_ID}:1",
        )
        self.assertEqual(document.name, f"{POLICY_ID}:1")
        self.assertEqual(document.global_id, str(expected_global_id))
        self.assertEqual(document.policy_global_id, str(POLICY_ID))
        self.assertEqual(
            document.policy_code,
            "synthetic_project_control",
        )
        self.assertEqual(document.optimistic_version, 2)
        self.assertEqual(
            document.title,
            "Synthetic Project control policy",
        )
        self.assertEqual(document.publication_state, "published")
        self.assertIsNone(document.prior_version_ref)
        self.assertEqual(
            json.loads(document.authority_slots),
            ["project_controller", "project_sponsor"],
        )
        self.assertEqual(
            [item["dimension"] for item in snapshot["healthRules"]],
            ["cost", "progress", "quality", "risk"],
        )
        self.assertEqual(
            snapshot["aggregation"],
            {"mode": "worst_status", "requireAll": True},
        )
        self.assertEqual(document.published_at, PUBLISHED_AT)
        self.assertEqual(
            document.snapshot_hash,
            hashlib.sha256(document.snapshot.encode("utf-8")).hexdigest(),
        )

    def test_draft_updates_then_publishes_and_becomes_immutable(self) -> None:
        document = self.version_document(publication_state="draft")
        document.validate()
        self.assertEqual(document.optimistic_version, 1)
        self.assertIsNone(document.published_at)

        document._previous = self.previous(document)
        document.title = "Revised synthetic policy"
        document.validate()
        self.assertEqual(document.optimistic_version, 2)
        self.assertEqual(document.title, "Revised synthetic policy")

        document._previous = self.previous(document)
        document.publication_state = "published"
        document.validate()
        self.assertEqual(document.optimistic_version, 3)
        self.assertEqual(document.publication_state, "published")
        self.assertEqual(document.published_at, PUBLISHED_AT)

        document._previous = self.previous(document)
        with self.assertRaises(self.ValidationError):
            document.validate()
        with self.assertRaises(self.PermissionError):
            document.on_trash()

        draft = self.version_document(publication_state="draft")
        draft.on_trash()

    def test_enabled_root_and_exact_root_identity_are_required(self) -> None:
        self.root.enabled = 0
        with self.assertRaises(self.ValidationError):
            self.version_document()

        self.root.enabled = 1
        with self.assertRaises(self.ValidationError):
            self.version_document(policy_global_id=str(OTHER_ID))
        with self.assertRaises(self.ValidationError):
            self.version_document(policy_code="another_policy")
        with self.assertRaises(self.ValidationError):
            self.version_document(global_id=str(OTHER_ID))

        self.root.global_id = str(OTHER_ID)
        with self.assertRaises(self.ValidationError):
            self.version_document()

    def test_versions_are_contiguous_and_prior_reference_is_frozen(
        self,
    ) -> None:
        with self.assertRaises(self.ValidationError):
            self.version_document(policy_version=2).validate()

        first = self.version_document()
        first.validate()
        prior = self.persist(first)
        second = self.version_document(
            policy_version=2,
            publication_state="draft",
        )
        second.validate()
        expected_reference = {
            "globalId": first.global_id,
            "version": 1,
            "snapshotHash": first.snapshot_hash,
        }
        self.assertEqual(
            json.loads(second.prior_version_ref),
            expected_reference,
        )

        wrong_reference = {
            **expected_reference,
            "snapshotHash": "f" * 64,
        }
        with self.assertRaises(self.ValidationError):
            self.version_document(
                policy_version=2,
                publication_state="draft",
                prior_version_ref=json.dumps(wrong_reference),
            ).validate()

        second._previous = self.previous(second)
        second.prior_version_ref = None
        with self.assertRaises(self.ValidationError):
            second.validate()

        prior.snapshot = "{}"
        with self.assertRaises(self.ValidationError):
            self.version_document(
                policy_version=2,
                publication_state="draft",
            ).validate()

    def test_unpublished_predecessor_and_duplicate_first_version_fail(
        self,
    ) -> None:
        first = self.version_document()
        first.validate()
        prior = self.persist(first)
        prior.publication_state = "draft"

        with self.assertRaises(self.ValidationError):
            self.version_document(
                policy_version=2,
                publication_state="draft",
            ).validate()
        with self.assertRaises(self.ValidationError):
            self.version_document(
                policy_version=1,
                publication_state="draft",
            ).validate()

    def test_closed_json_shapes_and_aggregation_reject_unknown_input(
        self,
    ) -> None:
        invalid_health_field = self.health_rules()
        invalid_health_field[0]["script"] = "return true"
        invalid_health_mode = self.health_rules()
        invalid_health_mode[0]["mode"] = "script"
        invalid_transition_field = self.transitions()
        invalid_transition_field[0]["script"] = "return true"
        invalid_prerequisites = self.transitions()
        invalid_prerequisites[0]["prerequisites"] = "open_blockers"

        invalid_documents = (
            self.version_document(
                authority_slots=["project_controller", 1],
            ),
            self.version_document(health_rules=invalid_health_field),
            self.version_document(health_rules=invalid_health_mode),
            self.version_document(require_all_dimensions=2),
            self.version_document(
                lifecycle_transitions=invalid_transition_field,
            ),
            self.version_document(
                lifecycle_transitions=invalid_prerequisites,
            ),
        )
        for index, document in enumerate(invalid_documents):
            with (
                self.subTest(index=index),
                self.assertRaises(self.ValidationError),
            ):
                document.validate()

    def test_draft_can_be_incomplete_but_publication_cannot(self) -> None:
        partial_rules = self.health_rules()[:1]
        draft = self.version_document(
            publication_state="draft",
            health_rules=partial_rules,
            lifecycle_transitions=[],
        )
        draft.validate()
        self.assertEqual(draft.publication_state, "draft")

        published = self.version_document(
            publication_state="published",
            health_rules=partial_rules,
            lifecycle_transitions=[],
        )
        with self.assertRaises(self.ValidationError):
            published.validate()


if __name__ == "__main__":
    unittest.main()
