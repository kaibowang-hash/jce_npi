from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

PROJECT_ID = UUID("2e96f421-5872-4c96-a0dd-718d5c970a21")
OTHER_PROJECT_ID = UUID("873f818c-cc37-48d7-a446-c32f8f92f330")
GATE_ID = UUID("62d6ac02-b85f-4ae0-a522-953c4ebc2de4")
OTHER_GATE_ID = UUID("8e497b7e-5090-4eb6-b118-25ecaee44390")
TEMPLATE_ID = UUID("77932078-9512-428e-b9d7-863303661059")
OWNER_MEMBER_ID = UUID("4b5e2ed1-0e5a-41b6-a217-6f84a809ba36")
REVIEWER_MEMBER_ID = UUID("44f7b429-a527-4304-865d-d61e6a42320b")
WBS_ID = UUID("590b332e-1ec4-44d8-8778-8b84eaf079bc")
FILE_REVISION_ID = UUID("2579bd55-bd84-461a-ae82-9f4f2f31a6f3")
TENANT_ID = "TENANT-A"


class AttrDoc(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def set(self, name: str, value: Any) -> None:
        self[name] = value

    def insert(self):
        self._store._insert(self)
        return self

    def save(self):
        self._store._save(self)
        return self

    def get_doc_before_save(self):
        return None

    def is_new(self) -> bool:
        return not self.get("_persisted", False)


class FakeStore:
    def __init__(self, frappe_module: types.ModuleType) -> None:
        self.frappe = frappe_module
        self.documents: dict[str, dict[str, AttrDoc]] = {}
        self.users: dict[str, AttrDoc] = {}
        self.rollback_count = 0
        self.get_doc_calls: list[tuple[str, str, bool]] = []

    def add(self, doctype: str, name: str, **values: object) -> AttrDoc:
        document = AttrDoc(
            doctype=doctype,
            name=name,
            _store=self,
            _persisted=True,
            **values,
        )
        self.documents.setdefault(doctype, {})[name] = document
        return document

    def get_doc(
        self,
        doctype_or_values: object,
        name: object = None,
        *,
        for_update: bool = False,
    ) -> AttrDoc:
        if isinstance(doctype_or_values, dict):
            return AttrDoc(
                copy.deepcopy(doctype_or_values),
                _store=self,
                _persisted=False,
            )
        doctype = str(doctype_or_values)
        key = str(name)
        self.get_doc_calls.append((doctype, key, for_update))
        document = self.documents.get(doctype, {}).get(key)
        if document is None:
            raise self.frappe.DoesNotExistError()
        return document

    def get_all(
        self,
        doctype: str,
        *,
        filters: dict[str, object],
        pluck: str,
        order_by: str,
        limit_page_length: int,
    ) -> list[str]:
        self.assertEqual(pluck, "name")
        values = [
            document
            for document in self.documents.get(doctype, {}).values()
            if all(document.get(key) == value for key, value in filters.items())
        ]
        fields = [item.strip().split()[0] for item in order_by.split(",")]
        values.sort(
            key=lambda document: tuple(
                str(document.get(field) or "") for field in fields
            )
        )
        return [str(document.name) for document in values[:limit_page_length]]

    @staticmethod
    def assertEqual(left: object, right: object) -> None:
        if left != right:
            raise AssertionError((left, right))

    def _insert(self, document: AttrDoc) -> None:
        doctype = str(document.doctype)
        name_field = {
            "NPI Project Work Idempotency": "record_id",
            "NPI Gate Evidence Reference": "global_id",
            "NPI Audit Event": "event_id",
        }.get(doctype, "name")
        name = str(document.get(name_field) or document.get("name"))
        if doctype == "NPI Project Work Idempotency":
            actor_key_hash = document.actor_key_hash
            if any(
                existing.actor_key_hash == actor_key_hash
                for existing in self.documents.get(doctype, {}).values()
            ):
                raise self.frappe.UniqueValidationError()
        if doctype == "NPI Gate Evidence Reference":
            reference_key = document.reference_key
            if any(
                existing.reference_key == reference_key
                for existing in self.documents.get(doctype, {}).values()
            ):
                raise self.frappe.UniqueValidationError()
        document.name = name
        document._persisted = True
        self.documents.setdefault(doctype, {})[name] = document

    def _save(self, document: AttrDoc) -> None:
        document._persisted = True
        self.documents.setdefault(str(document.doctype), {})[
            str(document.name)
        ] = document

    def get_value(
        self,
        doctype: str,
        name_or_filters: object,
        fieldname: object,
        *,
        as_dict: bool = False,
        for_update: bool = False,
    ) -> object:
        if doctype == "User":
            document = self.users.get(str(name_or_filters))
        else:
            values = self.documents.get(doctype, {}).values()
            if isinstance(name_or_filters, dict):
                document = next(
                    (
                        candidate
                        for candidate in values
                        if all(
                            candidate.get(key) == value
                            for key, value in name_or_filters.items()
                        )
                    ),
                    None,
                )
            else:
                document = self.documents.get(doctype, {}).get(str(name_or_filters))
        if document is None:
            return None
        if isinstance(fieldname, list):
            result = AttrDoc({field: document.get(field) for field in fieldname})
            return result if as_dict else tuple(result.values())
        return document.get(str(fieldname))

    def count(self, doctype: str, *, filters: dict[str, object]) -> int:
        return sum(
            1
            for document in self.documents.get(doctype, {}).values()
            if all(document.get(key) == value for key, value in filters.items())
        )

    def rollback(self) -> None:
        self.rollback_count += 1


class Phase4GateEvidenceRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        "npi_core.controlled_evidence_validation",
        "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision",
        (
            "npi_core.npi_core.doctype.npi_gate_evidence_reference."
            "npi_gate_evidence_reference"
        ),
        "npi_core.gate_evidence.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.session = types.SimpleNamespace(user="Administrator")
        self.frappe.DoesNotExistError = type(
            "DoesNotExistError",
            (Exception,),
            {},
        )
        self.frappe.UniqueValidationError = type(
            "UniqueValidationError",
            (Exception,),
            {},
        )
        self.frappe.DuplicateEntryError = type(
            "DuplicateEntryError",
            (Exception,),
            {},
        )
        self.frappe.ValidationError = type(
            "ValidationError",
            (Exception,),
            {},
        )
        self.frappe.PermissionError = type(
            "PermissionError",
            (Exception,),
            {},
        )

        def throw(message: str, exception_type: type[Exception]) -> None:
            raise exception_type(message)

        self.frappe.throw = throw
        self.store = FakeStore(self.frappe)
        self.frappe.get_doc = self.store.get_doc
        self.frappe.get_all = self.store.get_all
        self.frappe.db = self.store

        model = types.ModuleType("frappe.model")
        document_module = types.ModuleType("frappe.model.document")
        document_module.Document = AttrDoc
        model.document = document_module
        utils = types.ModuleType("frappe.utils")
        utils.now_datetime = lambda: datetime(2026, 7, 23, 12, 0)
        self.frappe.model = model
        self.frappe.utils = utils
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document_module
        sys.modules["frappe.utils"] = utils

        self.repository_module = importlib.import_module(
            "npi_core.gate_evidence.frappe_repository"
        )
        self.security = importlib.import_module("npi_core.foundation.security")
        self.template_domain = importlib.import_module("npi_core.gate_template.domain")
        self.template_snapshot = self._template_snapshot()
        self.repository_module.load_exact_gate_template_snapshot = (
            lambda global_id, version, snapshot_hash: (
                self.template_snapshot
                if (
                    global_id == TEMPLATE_ID
                    and version == 1
                    and snapshot_hash == self.template_snapshot.snapshot_hash
                )
                else None
            )
        )
        self.repository_module.has_complete_file_revision_identity = (
            lambda document: bool(document.get("complete_identity"))
        )
        self.repository_module.has_live_private_file_identity = lambda document: bool(
            document.get("live_private_identity")
        )
        self.repository_module.file_revision_source_snapshot = (
            self._file_source_snapshot
        )
        self._seed()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def _template_snapshot(self):
        EvidenceKind = self.template_domain.EvidenceKind
        Classification = self.template_domain.GateRequirementClassification
        Priority = self.template_domain.GateRequirementPriority
        Requirement = self.template_domain.GateRequirementDefinition
        ProjectType = importlib.import_module("npi_core.project.domain").ProjectType
        requirement = Requirement(
            key="drawing",
            title="Released drawing",
            classification=Classification.REQUIRED,
            priority=Priority.P0,
            allowed_evidence_kinds=(
                EvidenceKind.WBS_ITEM,
                EvidenceKind.FILE_REVISION,
            ),
        )
        draft = self.template_domain.GateTemplateVersion.create_draft(
            gate_template_global_id=TEMPLATE_ID,
            gate_template_code="SYN-GATE",
            gate_template_version=1,
            title="Synthetic Gate",
            applicable_project_types=(ProjectType.NEW_TOOL,),
            requirements=(requirement,),
        )
        return draft.publish(expected_version=1).snapshot()

    def _seed(self) -> None:
        self.project = self.store.add(
            "NPI Engineering Project",
            str(PROJECT_ID),
            global_id=str(PROJECT_ID),
            tenant_id=TENANT_ID,
            lifecycle_state="active",
            business_code="SYN-P403",
            title="Synthetic P4-03 Project",
            owner_user_id="owner@example.invalid",
            project_type="new_tool",
        )
        self.store.add(
            "NPI Engineering Project",
            str(OTHER_PROJECT_ID),
            global_id=str(OTHER_PROJECT_ID),
            tenant_id=TENANT_ID,
            lifecycle_state="active",
            business_code="OTHER",
            title="Other Project",
            owner_user_id="other@example.invalid",
            project_type="new_tool",
        )
        self.gate = self.store.add(
            "NPI Gate Shell",
            str(GATE_ID),
            global_id=str(GATE_ID),
            engineering_project=str(PROJECT_ID),
            project_global_id=str(PROJECT_ID),
            gate_key="G1",
            title="Synthetic Gate",
            state="not_started",
            optimistic_version=1,
            gate_template_global_id=str(TEMPLATE_ID),
            gate_template_version=1,
            gate_template_snapshot_hash=self.template_snapshot.snapshot_hash,
            requirements_frozen=0,
            gate_due_date=None,
            requirement_snapshot=None,
            requirement_snapshot_hash=None,
            requirements_frozen_at=None,
            requirements_frozen_by=None,
        )
        self.store.add(
            "NPI Gate Shell",
            str(OTHER_GATE_ID),
            global_id=str(OTHER_GATE_ID),
            engineering_project=str(OTHER_PROJECT_ID),
            project_global_id=str(OTHER_PROJECT_ID),
            gate_key="G1",
            title="Other Gate",
            state="not_started",
            optimistic_version=1,
            gate_template_global_id=str(TEMPLATE_ID),
            gate_template_version=1,
            gate_template_snapshot_hash=self.template_snapshot.snapshot_hash,
            requirements_frozen=0,
        )
        for member_id, user_id in (
            (OWNER_MEMBER_ID, "owner@example.invalid"),
            (REVIEWER_MEMBER_ID, "reviewer@example.invalid"),
        ):
            self.store.add(
                "NPI Project Member",
                str(member_id),
                global_id=str(member_id),
                tenant_id=TENANT_ID,
                project_global_id=str(PROJECT_ID),
                user_id=user_id,
            )
            self.store.users[user_id] = AttrDoc(
                enabled=1,
                user_type="System User",
                full_name=user_id.split("@")[0].title(),
            )
        self.store.users["owner@example.invalid"].full_name = "Project Owner"
        self.store.add(
            "NPI WBS Item",
            str(WBS_ID),
            global_id=str(WBS_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            work_policy_global_id=str(TEMPLATE_ID),
            work_policy_version=1,
            work_policy_snapshot_hash="b" * 64,
            wbs_code="1.2",
            title="Release drawing",
            parent_global_id=None,
            owner_role_assignment_global_id=None,
            planned_start=date(2026, 8, 1),
            planned_end=date(2026, 8, 5),
            actual_start=None,
            actual_end=None,
            milestone=1,
            status_key="planned",
            status_label_source="Not started",
            progress_percent=0,
            critical_task=1,
            plan_revision=2,
            optimistic_version=3,
        )
        self.file_revision = self.store.add(
            "NPI File Revision",
            str(FILE_REVISION_ID),
            global_id=str(FILE_REVISION_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            document_global_id=str(TEMPLATE_ID),
            frappe_file_id="safe-file-id",
            frappe_content_hash="d" * 32,
            file_name="drawing.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            sha256="c" * 64,
            is_private=1,
            revision=2,
            optimistic_version=1,
            scan_state="pending",
            released=0,
            complete_identity=True,
            live_private_identity=True,
        )

    def _repository(
        self,
        *,
        user_id: str = "Administrator",
        roles: frozenset[str] = frozenset({"System Manager"}),
        tenant_id: str = TENANT_ID,
        is_external: bool = False,
    ):
        Principal = self.security.Principal
        return self.repository_module.FrappeGateEvidenceRepository(
            principal=Principal(
                user_id=user_id,
                roles=roles,
                tenant_id=tenant_id,
                is_external=is_external,
            ),
            request_id="a6bfd0bf-8ab3-4a92-b49e-818735db4f55",
            trace_id="trace-gate-repository",
        )

    @staticmethod
    def _assignments() -> tuple[dict[str, object], ...]:
        return (
            {
                "key": "drawing",
                "owner_member_id": OWNER_MEMBER_ID,
                "reviewer_member_ids": (REVIEWER_MEMBER_ID,),
                "due_date": date(2026, 8, 28),
            },
        )

    @staticmethod
    def _file_source_snapshot(document: AttrDoc) -> dict[str, object]:
        return {
            "documentGlobalId": str(document.document_global_id),
            "fileContentHash": str(document.frappe_content_hash),
            "fileId": str(document.frappe_file_id),
            "fileName": str(document.file_name),
            "fileOptimisticVersion": int(document.optimistic_version),
            "globalId": str(document.global_id),
            "isPrivate": True,
            "mimeType": str(document.mime_type),
            "released": bool(document.released),
            "revision": int(document.revision),
            "scanObservedAt": None,
            "scanState": str(document.scan_state),
            "sha256": str(document.sha256),
            "sizeBytes": int(document.size_bytes),
        }

    def _freeze(self, repository=None, *, key: str = "f" * 64):
        return (repository or self._repository()).freeze_requirements(
            PROJECT_ID,
            GATE_ID,
            idempotency_key=key,
            expected_gate_version=1,
            gate_due_date=date(2026, 8, 31),
            assignments=self._assignments(),
        )

    def test_freeze_is_exact_atomic_audited_and_idempotent(self) -> None:
        repository = self._repository()
        outcome = self._freeze(repository)
        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertFalse(outcome.replayed)
        self.assertEqual(self.gate.optimistic_version, 2)
        self.assertEqual(self.gate.requirements_frozen, 1)
        snapshot = self.gate.requirement_snapshot
        self.assertEqual(
            snapshot["gateTemplateRef"]["globalId"],
            str(TEMPLATE_ID),
        )
        self.assertEqual(
            snapshot["requirements"][0]["ownerMemberId"],
            str(OWNER_MEMBER_ID),
        )
        self.assertEqual(outcome.response["summary"]["missingRequiredCount"], 1)
        self.assertEqual(outcome.response["requirements"][0]["priority"], "P0")
        self.assertEqual(
            outcome.response["requirements"][0]["owner"]["displayName"],
            "Project Owner",
        )
        idempotency = tuple(
            self.store.documents["NPI Project Work Idempotency"].values()
        )
        self.assertEqual(len(idempotency), 1)
        self.assertEqual(idempotency[0].response_sealed, 1)
        self.assertEqual(
            idempotency[0].operation,
            "gate.requirements.freeze",
        )
        self.assertEqual(
            len(self.store.documents["NPI Audit Event"]),
            1,
        )
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_gate_evidence_command_write",
            )
        )

        replay = self._freeze(repository)
        self.assertIsNotNone(replay)
        assert replay is not None
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.response, outcome.response)
        self.assertEqual(self.gate.optimistic_version, 2)
        self.assertEqual(
            len(self.store.documents["NPI Audit Event"]),
            1,
        )

    def test_terminal_workspace_is_read_only_and_sealed_replay_survives(self) -> None:
        repository = self._repository()
        outcome = self._freeze(repository)
        self.assertIsNotNone(outcome)
        assert outcome is not None
        source = self.store.documents["NPI WBS Item"][str(WBS_ID)]
        source_snapshot = self.repository_module.wbs_item_source_snapshot(source)
        source_hash = self.repository_module.canonical_snapshot_hash(source_snapshot)
        attached = repository.attach_evidence(
            PROJECT_ID,
            GATE_ID,
            "drawing",
            idempotency_key="terminal-attach-replay",
            expected_gate_version=2,
            evidence_kind="wbs_item",
            source_global_id=WBS_ID,
            source_version=3,
            source_hash=source_hash,
        )
        self.assertIsNotNone(attached)
        assert attached is not None

        self.project.lifecycle_state = "cancelled"
        workspace = repository.evidence_workspace(PROJECT_ID, GATE_ID)
        self.assertIsNotNone(workspace)
        assert workspace is not None
        self.assertTrue(workspace["permissions"]["canView"])
        self.assertFalse(workspace["permissions"]["canAttachEvidence"])
        self.assertFalse(workspace["permissions"]["canAdminister"])

        replay = self._freeze(repository)
        self.assertIsNotNone(replay)
        assert replay is not None
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.response, outcome.response)
        attach_replay = repository.attach_evidence(
            PROJECT_ID,
            GATE_ID,
            "drawing",
            idempotency_key="terminal-attach-replay",
            expected_gate_version=2,
            evidence_kind="wbs_item",
            source_global_id=WBS_ID,
            source_version=3,
            source_hash=source_hash,
        )
        self.assertIsNotNone(attach_replay)
        assert attach_replay is not None
        self.assertTrue(attach_replay.replayed)
        self.assertEqual(attach_replay.response, attached.response)

        ProjectHistoryLocked = importlib.import_module(
            "npi_core.project_controls.terminal_guard"
        ).ProjectHistoryLocked
        with self.assertRaises(ProjectHistoryLocked):
            repository.freeze_requirements(
                PROJECT_ID,
                GATE_ID,
                idempotency_key="terminal-new-freeze",
                expected_gate_version=3,
                gate_due_date=date(2026, 8, 31),
                assignments=self._assignments(),
            )

    def test_freeze_rejects_stale_duplicate_and_invalid_members(self) -> None:
        VersionConflict = importlib.import_module(
            "npi_core.foundation.errors"
        ).VersionConflict
        with self.assertRaises(VersionConflict):
            self._repository().freeze_requirements(
                PROJECT_ID,
                GATE_ID,
                idempotency_key="a" * 64,
                expected_gate_version=2,
                gate_due_date=date(2026, 8, 31),
                assignments=self._assignments(),
            )

        member = self.store.documents["NPI Project Member"][str(REVIEWER_MEMBER_ID)]
        member.project_global_id = str(OTHER_PROJECT_ID)
        with self.assertRaises(
            importlib.import_module(
                "npi_core.foundation.errors"
            ).RequestValidationFailed
        ):
            self._freeze(key="b" * 64)
        member.project_global_id = str(PROJECT_ID)

        self._freeze(key="c" * 64)
        with self.assertRaises(
            importlib.import_module(
                "npi_core.gate_evidence.domain"
            ).GateRequirementsAlreadyFrozen
        ):
            self._repository().freeze_requirements(
                PROJECT_ID,
                GATE_ID,
                idempotency_key="d" * 64,
                expected_gate_version=2,
                gate_due_date=date(2026, 8, 31),
                assignments=self._assignments(),
            )

    def test_workspace_rejects_gate_column_and_frozen_snapshot_drift(self) -> None:
        repository = self._repository()
        self._freeze(repository)

        self.gate.gate_due_date = "2026-09-01"
        with self.assertRaises(ValueError):
            repository.evidence_workspace(PROJECT_ID, GATE_ID)
        self.gate.gate_due_date = "2026-08-31"

        self.gate.gate_template_snapshot_hash = "0" * 64
        with self.assertRaises(ValueError):
            repository.evidence_workspace(PROJECT_ID, GATE_ID)

    def test_authorization_precedes_gate_resolution_and_is_idor_safe(self) -> None:
        repository = self._repository(
            user_id="unrelated@example.invalid",
            roles=frozenset({"NPI User"}),
        )
        self.store.get_doc_calls.clear()
        self.assertIsNone(repository.evidence_workspace(PROJECT_ID, GATE_ID))
        doctypes = [doctype for doctype, _name, _lock in self.store.get_doc_calls]
        self.assertEqual(doctypes, ["NPI Engineering Project"])

        owner = self._repository(
            user_id="owner@example.invalid",
            roles=frozenset({"NPI User"}),
        )
        self._freeze()
        workspace = owner.evidence_workspace(PROJECT_ID, GATE_ID)
        self.assertIsNotNone(workspace)
        assert workspace is not None
        self.assertFalse(workspace["permissions"]["canAttachEvidence"])
        self.assertIsNone(owner.evidence_workspace(PROJECT_ID, OTHER_GATE_ID))
        self.assertIsNone(
            self._repository(tenant_id="TENANT-B").evidence_workspace(
                PROJECT_ID,
                GATE_ID,
            )
        )
        self.store.get_doc_calls.clear()
        external_owner = self._repository(
            user_id="owner@example.invalid",
            roles=frozenset({"NPI User"}),
            is_external=True,
        )
        self.assertIsNone(
            external_owner.evidence_workspace(
                PROJECT_ID,
                GATE_ID,
            )
        )
        self.assertEqual(
            [doctype for doctype, _name, _lock in self.store.get_doc_calls],
            ["NPI Engineering Project"],
        )

    def test_wbs_evidence_is_exact_append_only_and_updates_gate_version(self) -> None:
        repository = self._repository()
        self._freeze(repository)
        source = self.store.documents["NPI WBS Item"][str(WBS_ID)]
        snapshot = self.repository_module.wbs_item_source_snapshot(source)
        source_hash = self.repository_module.canonical_snapshot_hash(snapshot)
        outcome = repository.attach_evidence(
            PROJECT_ID,
            GATE_ID,
            "drawing",
            idempotency_key="e" * 64,
            expected_gate_version=2,
            evidence_kind="wbs_item",
            source_global_id=WBS_ID,
            source_version=3,
            source_hash=source_hash,
        )
        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertEqual(self.gate.optimistic_version, 3)
        self.assertEqual(outcome.response["summary"]["evidenceCount"], 1)
        self.assertEqual(outcome.response["summary"]["missingRequiredCount"], 0)
        requirement = outcome.response["requirements"][0]
        self.assertEqual(requirement["evidenceState"], "attached")
        self.assertEqual(requirement["evidence"][0]["revision"], 3)
        evidence = tuple(self.store.documents["NPI Gate Evidence Reference"].values())[
            0
        ]
        self.assertNotIn("/private/files/", str(evidence.source_snapshot))
        self.assertEqual(evidence.source_hash, source_hash)

        with self.assertRaises(
            importlib.import_module(
                "npi_core.gate_evidence.domain"
            ).EvidenceAlreadyAttached
        ):
            repository.attach_evidence(
                PROJECT_ID,
                GATE_ID,
                "drawing",
                idempotency_key="1" * 64,
                expected_gate_version=3,
                evidence_kind="wbs_item",
                source_global_id=WBS_ID,
                source_version=3,
                source_hash=source_hash,
            )

    def test_file_scan_state_remains_live_without_exposing_raw_url(self) -> None:
        repository = self._repository()
        self._freeze(repository)
        outcome = repository.attach_evidence(
            PROJECT_ID,
            GATE_ID,
            "drawing",
            idempotency_key="2" * 64,
            expected_gate_version=2,
            evidence_kind="file_revision",
            source_global_id=FILE_REVISION_ID,
            source_version=2,
            source_hash="c" * 64,
        )
        self.assertIsNotNone(outcome)
        assert outcome is not None
        requirement = outcome.response["requirements"][0]
        self.assertEqual(requirement["evidenceState"], "scan_pending")
        self.assertEqual(outcome.response["summary"]["unsafeScanCount"], 1)
        file_metadata = requirement["evidence"][0]["file"]
        self.assertEqual(
            set(file_metadata),
            {"fileName", "mimeType", "sizeBytes", "scanState"},
        )
        self.assertNotIn("url", str(outcome.response).casefold())

        self.file_revision.scan_state = "clean"
        self.file_revision.optimistic_version = 2
        workspace = repository.evidence_workspace(PROJECT_ID, GATE_ID)
        self.assertIsNotNone(workspace)
        assert workspace is not None
        self.assertEqual(
            workspace["requirements"][0]["evidenceState"],
            "scan_clean",
        )
        self.assertEqual(workspace["summary"]["unsafeScanCount"], 0)

        self.file_revision.scan_state = "infected"
        workspace = repository.evidence_workspace(PROJECT_ID, GATE_ID)
        assert workspace is not None
        self.assertEqual(
            workspace["requirements"][0]["evidenceState"],
            "scan_infected",
        )

        self.file_revision.live_private_identity = False
        with self.assertRaises(ValueError):
            repository.evidence_workspace(PROJECT_ID, GATE_ID)

    def test_evidence_rejects_cross_project_and_stale_source(self) -> None:
        repository = self._repository()
        self._freeze(repository)
        source = self.store.documents["NPI WBS Item"][str(WBS_ID)]
        snapshot = self.repository_module.wbs_item_source_snapshot(source)
        source_hash = self.repository_module.canonical_snapshot_hash(snapshot)
        source.project_global_id = str(OTHER_PROJECT_ID)
        with self.assertRaises(
            importlib.import_module(
                "npi_core.gate_evidence.domain"
            ).EvidenceSourceUnavailable
        ):
            repository.attach_evidence(
                PROJECT_ID,
                GATE_ID,
                "drawing",
                idempotency_key="3" * 64,
                expected_gate_version=2,
                evidence_kind="wbs_item",
                source_global_id=WBS_ID,
                source_version=3,
                source_hash=source_hash,
            )
        source.project_global_id = str(PROJECT_ID)
        with self.assertRaises(
            importlib.import_module(
                "npi_core.gate_evidence.domain"
            ).EvidenceVersionConflict
        ):
            repository.attach_evidence(
                PROJECT_ID,
                GATE_ID,
                "drawing",
                idempotency_key="4" * 64,
                expected_gate_version=2,
                evidence_kind="wbs_item",
                source_global_id=WBS_ID,
                source_version=2,
                source_hash=source_hash,
            )


if __name__ == "__main__":
    unittest.main()
