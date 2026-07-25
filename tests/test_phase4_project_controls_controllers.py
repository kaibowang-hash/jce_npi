from __future__ import annotations

import hashlib
import importlib
import json
import sys
import types
import unittest
from typing import Any


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
POLICY_ID = "77932078-9512-428e-b9d7-863303661059"
MEMBER_ID = "4b5e2ed1-0e5a-41b6-a217-6f84a809ba36"
BINDING_ID = "44f7b429-a527-4304-865d-d61e6a42320b"
RECORD_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"


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

    def set(self, fieldname: str, value: Any) -> None:
        setattr(self, fieldname, value)

    def get_doc_before_save(self) -> Any:
        return self._previous


class Phase4ProjectControlsControllerTest(unittest.TestCase):
    PROJECT_MODULE_PATH = (
        "npi_core.npi_core.doctype.npi_engineering_project" ".npi_engineering_project"
    )
    MY_WORK_MODULE_PATH = (
        "npi_core.npi_core.doctype.npi_my_work_assignment"
        ".npi_my_work_assignment"
    )
    MODULE_PATHS = {
        "binding": (
            "npi_core.npi_core.doctype.npi_project_control_binding"
            ".npi_project_control_binding"
        ),
        "health": (
            "npi_core.npi_core.doctype.npi_project_health_assessment"
            ".npi_project_health_assessment"
        ),
        "activity": (
            "npi_core.npi_core.doctype.npi_project_activity_event"
            ".npi_project_activity_event"
        ),
        "follower": (
            "npi_core.npi_core.doctype.npi_project_follower" ".npi_project_follower"
        ),
        "learning": (
            "npi_core.npi_core.doctype.npi_project_learning" ".npi_project_learning"
        ),
        "idempotency": (
            "npi_core.npi_core.doctype.npi_project_control_idempotency"
            ".npi_project_control_idempotency"
        ),
    }
    SUPPORT_MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.project.frappe_validation",
        "npi_core.project_controls.frappe_validation",
    )

    def setUp(self) -> None:
        module_names = (
            *self.SUPPORT_MODULES,
            self.PROJECT_MODULE_PATH,
            self.MY_WORK_MODULE_PATH,
            *self.MODULE_PATHS.values(),
        )
        self.saved_modules = {name: sys.modules.get(name) for name in module_names}
        for name in module_names:
            sys.modules.pop(name, None)

        self.ValidationError = type("ValidationError", (Exception,), {})
        self.PermissionError = type("PermissionError", (Exception,), {})
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.ValidationError = self.ValidationError
        self.frappe.PermissionError = self.PermissionError
        self.frappe.flags = types.SimpleNamespace(
            npi_project_control_command_write=False,
            npi_my_work_projection_write=False,
        )

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        self.frappe.throw = throw
        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        self.frappe.model = model
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document

        self.modules = {
            name: importlib.import_module(path)
            for name, path in self.MODULE_PATHS.items()
        }
        self.project_module = importlib.import_module(self.PROJECT_MODULE_PATH)
        self.my_work_module = importlib.import_module(self.MY_WORK_MODULE_PATH)
        self.my_work_controller = self.my_work_module.NPIMyWorkAssignment
        self.controllers = {
            "binding": self.modules["binding"].NPIProjectControlBinding,
            "health": self.modules["health"].NPIProjectHealthAssessment,
            "activity": self.modules["activity"].NPIProjectActivityEvent,
            "follower": self.modules["follower"].NPIProjectFollower,
            "learning": self.modules["learning"].NPIProjectLearning,
            "idempotency": self.modules["idempotency"].NPIProjectControlIdempotency,
        }

    def tearDown(self) -> None:
        module_names = (
            *self.SUPPORT_MODULES,
            self.PROJECT_MODULE_PATH,
            self.MY_WORK_MODULE_PATH,
            *self.MODULE_PATHS.values(),
        )
        for name in module_names:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def project_document(
        self,
        *,
        project_version: int,
        assessment_project_version: int,
    ) -> StubDocument:
        assessed_at = "2026-07-25T10:00:00.000000Z"
        template_snapshot = {
            "templateGlobalId": POLICY_ID,
            "templateCode": "STD-NPI",
            "templateVersion": 1,
            "applicableProjectTypes": ["new_tool"],
            "referenceRules": [],
            "gates": [],
        }
        health_snapshot = {
            "schemaVersion": 1,
            "globalId": RECORD_ID,
            "projectGlobalId": PROJECT_ID,
            "projectVersion": assessment_project_version,
            "assessedAt": assessed_at,
            "evaluation": {"overallStatus": "green"},
        }
        return self.project_module.NPIEngineeringProject(
            {
                "global_id": PROJECT_ID,
                "tenant_id": "TENANT-A",
                "business_code": "NPI-2026-001",
                "title": "Health snapshot regression",
                "project_type": "new_tool",
                "owner_user_id": "owner@example.invalid",
                "target_sop": None,
                "source_system": "NPI_ONE",
                "template_global_id": POLICY_ID,
                "template_code": "STD-NPI",
                "template_version": 1,
                "template_snapshot_hash": self.project_module.sha256_json(
                    template_snapshot
                ),
                "template_snapshot": template_snapshot,
                "creation_payload_hash": "b" * 64,
                "optimistic_version": project_version,
                "work_plan_revision": 0,
                "lifecycle_state": "active",
                "control_binding_global_id": BINDING_ID,
                "control_policy_global_id": POLICY_ID,
                "control_policy_version": 1,
                "control_policy_snapshot_hash": "a" * 64,
                "control_binding_version": 1,
                "current_health_assessment_global_id": RECORD_ID,
                "current_health_status": "green",
                "current_health_snapshot": health_snapshot,
                "current_health_at": assessed_at,
                "work_policy_global_id": None,
                "work_policy_version": None,
                "work_policy_snapshot_hash": None,
                "active_plan_baseline_global_id": None,
                "references": [],
            }
        )

    def test_project_accepts_historical_health_snapshot_after_version_advance(
        self,
    ) -> None:
        document = self.project_document(
            project_version=6,
            assessment_project_version=5,
        )
        document.validate()

        future = self.project_document(
            project_version=6,
            assessment_project_version=7,
        )
        with self.assertRaisesRegex(
            self.ValidationError,
            "Current Health Snapshot does not match the Project",
        ):
            future.validate()

    def test_command_owned_records_reject_desk_writes_and_all_deletes(
        self,
    ) -> None:
        for name, controller in self.controllers.items():
            with self.subTest(controller=name):
                document = controller({})
                with self.assertRaises(self.PermissionError):
                    document.before_insert()
                with self.assertRaises(self.PermissionError):
                    document.before_save()

                self.frappe.flags.npi_project_control_command_write = True
                document.before_insert()
                if name not in {
                    "binding",
                    "health",
                    "activity",
                    "learning",
                }:
                    document.before_save()
                with self.assertRaises(self.PermissionError):
                    document.on_trash()
                self.frappe.flags.npi_project_control_command_write = False

    def my_work_assignment_document(self) -> StubDocument:
        document = self.my_work_controller(
            {
                "global_id": RECORD_ID,
                "assignment_key": (
                    "gate_review_assignment:"
                    f"{POLICY_ID}:decision:owner-index"
                ),
                "tenant_id": "TENANT-A",
                "actor_user_id": "Owner@Example.Invalid",
                "project_global_id": PROJECT_ID,
                "source_type": "gate_review_assignment",
                "source_global_id": POLICY_ID,
                "source_version": 7,
                "assignment_code": "gate_final_decision",
                "category": "approval",
                "due_at": None,
                "priority_scheme": None,
                "priority_value": None,
                "blocking": 0,
                "active": 1,
                "source_snapshot": "{}",
                "snapshot_hash": "0" * 64,
                "indexed_at": "2026-07-25T12:00:00.000000Z",
            }
        )
        self.sync_my_work_snapshot(document)
        return document

    @staticmethod
    def sync_my_work_snapshot(document: StubDocument) -> None:
        priority = (
            None
            if not document.priority_scheme
            else {
                "scheme": document.priority_scheme,
                "value": document.priority_value,
            }
        )
        snapshot = {
            "schemaVersion": 1,
            "assignmentGlobalId": document.global_id,
            "assignmentKey": document.assignment_key,
            "tenantId": document.tenant_id,
            "actorUserId": document.actor_user_id.casefold(),
            "projectGlobalId": document.project_global_id,
            "sourceType": document.source_type,
            "sourceGlobalId": document.source_global_id,
            "sourceVersion": document.source_version,
            "assignmentCode": document.assignment_code,
            "category": document.category,
            "dueAt": document.due_at,
            "priority": priority,
            "blocking": bool(document.blocking),
            "active": bool(document.active),
            "sourceDetail": {
                "cycleGlobalId": POLICY_ID,
                "authoritySlot": "gate_decider",
            },
        }
        serialized = json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        document.source_snapshot = serialized
        document.snapshot_hash = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def test_my_work_projection_rejects_raw_writes_and_all_deletes(self) -> None:
        document = self.my_work_assignment_document()
        with self.assertRaises(self.PermissionError):
            document.before_insert()
        with self.assertRaises(self.PermissionError):
            document.before_save()

        self.frappe.flags.npi_my_work_projection_write = True
        document.before_insert()
        document.before_save()
        with self.assertRaises(self.PermissionError):
            document.on_trash()
        self.frappe.flags.npi_my_work_projection_write = False
        with self.assertRaises(self.PermissionError):
            document.on_trash()

    def test_my_work_projection_identity_cannot_be_mutated(self) -> None:
        mutations = {
            "global_id": POLICY_ID,
            "assignment_key": "changed-projection-identity",
            "tenant_id": "TENANT-B",
            "actor_user_id": "another@example.invalid",
            "project_global_id": POLICY_ID,
            "source_type": "gate_review_invalidation",
            "source_global_id": PROJECT_ID,
        }
        for fieldname, value in mutations.items():
            with self.subTest(fieldname=fieldname):
                document = self.my_work_assignment_document()
                document.validate()
                document._previous = AttrDict(
                    {
                        identity: document.get(identity)
                        for identity in document._IDENTITY_FIELDS
                    }
                )
                setattr(document, fieldname, value)
                if fieldname == "source_type":
                    document.assignment_code = "gate_dependency_change"
                    document.category = "blocker"
                    document.blocking = 1
                self.sync_my_work_snapshot(document)
                with self.assertRaisesRegex(
                    self.ValidationError,
                    "protected field",
                ):
                    document.validate()

    def test_binding_health_activity_and_learning_are_append_only(
        self,
    ) -> None:
        self.frappe.flags.npi_project_control_command_write = True
        for name in ("binding", "health", "activity", "learning"):
            with self.subTest(controller=name):
                document = self.controllers[name]({})
                document._previous = AttrDict(name="existing-record")
                with self.assertRaises(self.PermissionError):
                    document.before_save()

    def idempotency_document(self) -> StubDocument:
        return self.controllers["idempotency"](
            {
                "record_id": RECORD_ID,
                "actor": "Owner@Example.Invalid",
                "tenant_id": "TENANT-A",
                "project_global_id": PROJECT_ID,
                "operation": "project.lifecycle.pause",
                "actor_key_hash": "a" * 64,
                "payload_hash": "b" * 64,
                "response_json": "{}",
                "response_sealed": 0,
            }
        )

    def idempotency_previous(
        self,
        document: StubDocument,
        *,
        sealed: int,
    ) -> AttrDict:
        fields = self.modules["idempotency"].NPIProjectControlIdempotency
        values = {
            fieldname: document.get(fieldname) for fieldname in fields._IMMUTABLE_FIELDS
        }
        values.update(
            response_json=document.response_json,
            response_sealed=sealed,
        )
        return AttrDict(values)

    def test_idempotency_record_is_actor_bound_and_sealed_once(self) -> None:
        document = self.idempotency_document()
        document.validate()
        self.assertEqual(document.actor, "owner@example.invalid")
        self.assertEqual(document.response_json, "{}")
        self.assertEqual(document.response_sealed, 0)

        document._previous = self.idempotency_previous(
            document,
            sealed=0,
        )
        document.response_json = json.dumps(
            {"projectId": PROJECT_ID},
            separators=(",", ":"),
        )
        document.response_sealed = 1
        document.validate()
        self.assertEqual(
            json.loads(document.response_json),
            {"projectId": PROJECT_ID},
        )

        document._previous = self.idempotency_previous(
            document,
            sealed=1,
        )
        with self.assertRaises(self.PermissionError):
            document.validate()

        changed = self.idempotency_document()
        changed.validate()
        changed._previous = self.idempotency_previous(
            changed,
            sealed=0,
        )
        changed.actor = "another@example.invalid"
        changed.response_json = '{"ok":true}'
        changed.response_sealed = 1
        with self.assertRaises(self.ValidationError):
            changed.validate()

    def test_actor_identity_preserves_frappe_administrator_exactly(self) -> None:
        validation = sys.modules["npi_core.project_controls.frappe_validation"]
        self.assertEqual(
            validation.require_actor("Administrator", "Actor"),
            "Administrator",
        )
        self.assertEqual(
            validation.require_actor("Owner@Example.Invalid", "Actor"),
            "owner@example.invalid",
        )
        for invalid in ("", "invalid user", "invalid\nuser"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(self.ValidationError):
                    validation.require_actor(invalid, "Actor")

    def test_administrator_activity_and_learning_snapshots_round_trip(
        self,
    ) -> None:
        occurred_at = "2026-07-25T12:00:00.000000Z"
        activity_payload = {
            "schemaVersion": 1,
            "globalId": RECORD_ID,
            "eventKey": f"{PROJECT_ID}:{occurred_at}:{RECORD_ID}",
            "tenantId": "TENANT-A",
            "projectGlobalId": PROJECT_ID,
            "eventType": "comment_added",
            "actorUserId": "Administrator",
            "occurredAt": occurred_at,
            "requestId": RECORD_ID,
            "traceId": "trace-administrator-activity",
            "detail": {
                "body": "Administrator retains an exact Frappe identity.",
                "mentions": [],
                "attachments": [],
                "objectLinks": [],
            },
        }
        activity_json = json.dumps(
            activity_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        activity = self.controllers["activity"](
            {
                "global_id": RECORD_ID,
                "event_key": activity_payload["eventKey"],
                "tenant_id": "TENANT-A",
                "project_global_id": PROJECT_ID,
                "event_type": "comment_added",
                "actor_user_id": "Administrator",
                "occurred_at": occurred_at,
                "request_id": RECORD_ID,
                "trace_id": "trace-administrator-activity",
                "payload": activity_json,
                "payload_hash": hashlib.sha256(
                    activity_json.encode("utf-8")
                ).hexdigest(),
            }
        )
        activity.validate()
        self.assertEqual(activity.actor_user_id, "Administrator")

        learning_snapshot = {
            "schemaVersion": 1,
            "globalId": RECORD_ID,
            "tenantId": "TENANT-A",
            "projectGlobalId": PROJECT_ID,
            "kind": "lesson",
            "title": "Exact administrator identity",
            "content": "Preserve the canonical Frappe user identifier.",
            "recommendation": "",
            "tags": [],
            "templateGlobalId": POLICY_ID,
            "templateVersion": 1,
            "templateSnapshotHash": "a" * 64,
            "createdBy": "Administrator",
            "createdAt": occurred_at,
            "requestId": RECORD_ID,
            "traceId": "trace-administrator-learning",
        }
        learning_json = json.dumps(
            learning_snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        learning = self.controllers["learning"](
            {
                "global_id": RECORD_ID,
                "tenant_id": "TENANT-A",
                "project_global_id": PROJECT_ID,
                "kind": "lesson",
                "title": "Exact administrator identity",
                "content": "Preserve the canonical Frappe user identifier.",
                "recommendation": "",
                "tags": "[]",
                "template_global_id": POLICY_ID,
                "template_version": 1,
                "template_snapshot_hash": "a" * 64,
                "created_by": "Administrator",
                "created_at": occurred_at,
                "optimistic_version": 1,
                "request_id": RECORD_ID,
                "trace_id": "trace-administrator-learning",
                "record_snapshot": learning_json,
                "snapshot_hash": hashlib.sha256(
                    learning_json.encode("utf-8")
                ).hexdigest(),
            }
        )
        learning.validate()
        self.assertEqual(learning.created_by, "Administrator")

    def test_idempotency_cannot_be_created_presealed_or_with_response(
        self,
    ) -> None:
        for sealed, response in (
            (1, "{}"),
            (0, '{"projectId":"' + PROJECT_ID + '"}'),
        ):
            with self.subTest(sealed=sealed, response=response):
                document = self.idempotency_document()
                document.response_sealed = sealed
                document.response_json = response
                with self.assertRaises(self.ValidationError):
                    document.validate()

    def follower_document(self, *, active: int, version: int) -> StubDocument:
        actor = "owner@example.invalid"
        return self.controllers["follower"](
            {
                "global_id": RECORD_ID,
                "follower_key": f"{PROJECT_ID}:{actor}",
                "tenant_id": "TENANT-A",
                "project_global_id": PROJECT_ID,
                "user_id": actor,
                "active": active,
                "optimistic_version": version,
                "last_changed_by": actor,
                "request_id": RECORD_ID,
                "trace_id": "trace-project-follower",
            }
        )

    @staticmethod
    def follower_previous(document: StubDocument) -> AttrDict:
        return AttrDict(
            {
                fieldname: document.get(fieldname)
                for fieldname in (
                    "global_id",
                    "follower_key",
                    "tenant_id",
                    "project_global_id",
                    "user_id",
                    "active",
                    "optimistic_version",
                )
            }
        )

    def test_follower_identity_is_fixed_and_version_advances_once(
        self,
    ) -> None:
        document = self.follower_document(active=1, version=99)
        document.validate()
        self.assertEqual(document.optimistic_version, 1)

        previous = self.follower_previous(document)
        document._previous = previous
        document.active = 0
        document.optimistic_version = 2
        document.validate()
        self.assertEqual(document.optimistic_version, 2)

        document._previous = self.follower_previous(document)
        document.optimistic_version = 3
        with self.assertRaises(self.ValidationError):
            document.validate()

        changed = self.follower_document(active=0, version=2)
        changed._previous = previous
        changed.project_global_id = POLICY_ID
        changed.follower_key = f"{changed.project_global_id}:owner@example.invalid"
        with self.assertRaises(self.ValidationError):
            changed.validate()

    def test_health_persistence_requires_all_dimensions_and_red_recovery(
        self,
    ) -> None:
        policy_ref = {
            "globalId": POLICY_ID,
            "version": 1,
            "snapshotHash": "a" * 64,
        }
        results = [
            {
                "dimension": dimension,
                "ruleMode": "manual",
                "status": "red" if dimension == "risk" else "green",
                "numericValue": None,
            }
            for dimension in ("progress", "cost", "quality", "risk")
        ]
        invalid = {
            "policyRef": policy_ref,
            "dimensionResults": results,
            "overallStatus": "red",
            "reason": None,
            "recoveryPlan": None,
        }
        with self.assertRaises(self.ValidationError):
            self.modules["health"]._validate_evaluation(
                invalid,
                policy_ref,
            )

        valid = {
            **invalid,
            "reason": "Critical supplied material risk.",
            "recoveryPlan": "Qualify an approved alternate source.",
        }
        self.modules["health"]._validate_evaluation(valid, policy_ref)

        duplicate = [
            {
                "dimension": "risk",
                "numericValue": None,
                "manualStatus": "red",
            },
            {
                "dimension": "risk",
                "numericValue": None,
                "manualStatus": "yellow",
            },
        ]
        with self.assertRaises(self.ValidationError):
            self.modules["health"]._validate_measurements(duplicate)

    def test_health_assessment_round_trips_exact_frozen_authority(
        self,
    ) -> None:
        policy_ref = {
            "globalId": POLICY_ID,
            "version": 1,
            "snapshotHash": "a" * 64,
        }
        actor = {
            "slot": "project_controller",
            "memberGlobalId": MEMBER_ID,
            "userId": "owner@example.invalid",
            "displayName": "Synthetic Owner",
        }
        dimensions = [
            {
                "dimension": dimension,
                "ruleMode": ("unavailable" if dimension == "risk" else "manual"),
                "status": ("unavailable" if dimension == "risk" else "green"),
                "numericValue": None,
            }
            for dimension in ("progress", "cost", "quality", "risk")
        ]
        snapshot = {
            "schemaVersion": 1,
            "globalId": RECORD_ID,
            "tenantId": "TENANT-A",
            "projectGlobalId": PROJECT_ID,
            "bindingGlobalId": BINDING_ID,
            "policyRef": policy_ref,
            "actor": actor,
            "assessedAt": "2026-07-25T12:00:00.000000Z",
            "projectVersion": 5,
            "measurements": [
                {
                    "dimension": "quality",
                    "numericValue": None,
                    "manualStatus": "green",
                }
            ],
            "evaluation": {
                "policyRef": policy_ref,
                "dimensionResults": dimensions,
                "overallStatus": "unavailable",
                "reason": None,
                "recoveryPlan": None,
            },
            "requestId": RECORD_ID,
            "traceId": "trace-project-health",
        }
        serialized = json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        document = self.controllers["health"](
            {
                "global_id": RECORD_ID,
                "tenant_id": "TENANT-A",
                "project_global_id": PROJECT_ID,
                "binding_global_id": BINDING_ID,
                "policy_global_id": POLICY_ID,
                "policy_version": 1,
                "policy_snapshot_hash": "a" * 64,
                "actor_authority_slot": "project_controller",
                "actor_member_global_id": MEMBER_ID,
                "actor_user_id": "owner@example.invalid",
                "actor_display_name": "Synthetic Owner",
                "assessed_at": "2026-07-25 12:00:00",
                "project_version": 5,
                "request_id": RECORD_ID,
                "trace_id": "trace-project-health",
                "assessment_snapshot": serialized,
                "snapshot_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            }
        )
        document.validate()
        self.assertEqual(
            json.loads(document.assessment_snapshot)["actor"],
            actor,
        )

        document.actor_authority_slot = "project_sponsor"
        with self.assertRaises(self.ValidationError):
            document.validate()

    def test_binding_freezes_one_exact_identity_per_policy_slot(self) -> None:
        valid = [
            {
                "slot": "project_controller",
                "memberGlobalId": MEMBER_ID,
                "userId": "owner@example.invalid",
                "displayName": "Synthetic Owner",
            }
        ]
        self.modules["binding"]._validate_bindings(valid)

        with self.assertRaises(self.ValidationError):
            self.modules["binding"]._validate_bindings(valid + valid)
        with self.assertRaises(self.ValidationError):
            self.modules["binding"]._validate_bindings(
                [{**valid[0], "userId": "Owner@Example.Invalid"}]
            )
        with self.assertRaises(self.ValidationError):
            self.modules["binding"]._validate_bindings(
                [
                    {
                        key: value
                        for key, value in valid[0].items()
                        if key != "displayName"
                    }
                ]
            )

    def test_activity_detail_rejects_raw_or_untyped_attachment_data(
        self,
    ) -> None:
        detail = {
            "body": "Synthetic activity",
            "mentions": [],
            "attachments": [
                {
                    "globalId": RECORD_ID,
                    "version": 1,
                    "fileName": "evidence.pdf",
                    "mimeType": "application/pdf",
                    "sizeBytes": 10,
                    "sha256": "a" * 64,
                    "scanState": "clean",
                }
            ],
            "objectLinks": [],
        }
        self.modules["activity"]._validate_detail(
            "comment_added",
            detail,
        )
        detail["attachments"][0]["url"] = "/private/files/evidence.pdf"
        with self.assertRaises(self.ValidationError):
            self.modules["activity"]._validate_detail(
                "comment_added",
                detail,
            )


if __name__ == "__main__":
    unittest.main()
