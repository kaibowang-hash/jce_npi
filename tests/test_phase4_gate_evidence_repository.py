from __future__ import annotations

import copy
import importlib
import inspect
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
BASELINE_ID = UUID("1ba71ee3-c1fe-46d9-b9c6-67fb3c06aff2")
BASELINE_MEMBER_IDS = (
    UUID("1087d97c-f111-45b8-8822-87300ccda9e2"),
    UUID("f301cb8e-2bf0-410b-90e0-1b8b541d0d1c"),
)
BASELINE_DOCUMENT_IDS = (
    UUID("344a0a84-bac9-4b04-8f6d-730ec3398b00"),
    UUID("cb50ea84-94c5-4088-8328-7641487e90d3"),
)
BASELINE_REVISION_IDS = (
    UUID("45909373-97de-4931-824c-bc12a259f780"),
    UUID("0bf29e7c-6a8e-46fa-ab8b-0084d2b2dc03"),
)
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
            "NPI Baseline Gate Dependency": "global_id",
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
        "npi_core.documents.baseline_diagnostics",
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
        self.baseline_load_calls: list[tuple[str, UUID, bool]] = []
        self.baseline = self._release_baseline()

        def load_document_baseline(project, baseline_id: UUID, *, lock: bool):
            self.baseline_load_calls.append((str(project.global_id), baseline_id, lock))
            return self.baseline if baseline_id == BASELINE_ID else None

        self.repository_module.load_document_baseline = load_document_baseline
        self.repository_module.document_baseline_response = (
            self._baseline_response
        )
        self.repository_module.load_project_baseline_impacts = (
            lambda project, *, gate_global_id: ()
        )
        self._seed()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def test_attach_evidence_has_closed_server_diagnostic_boundaries(self) -> None:
        source = inspect.getsource(
            self.repository_module.FrappeGateEvidenceRepository.attach_evidence
        )
        expected = {
            "P503_GATE_EVIDENCE_ATTACH_PROJECT_LOCK",
            "P503_GATE_EVIDENCE_ATTACH_GATE_LOCK",
            "P503_GATE_EVIDENCE_ATTACH_IDEMPOTENCY_REPLAY",
            "P503_GATE_EVIDENCE_ATTACH_PRECONDITION",
            "P503_GATE_EVIDENCE_ATTACH_SOURCE_RESOLVE",
            "P503_GATE_EVIDENCE_ATTACH_RECEIPT_INSERT",
            "P503_GATE_EVIDENCE_ATTACH_REFERENCE_INSERT",
            "P503_GATE_EVIDENCE_ATTACH_DEPENDENCY_INSERT",
            "P503_GATE_EVIDENCE_ATTACH_GATE_SAVE",
            "P503_GATE_EVIDENCE_ATTACH_REVIEW_REFRESH",
            "P503_GATE_EVIDENCE_ATTACH_AUDIT_APPEND",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_BUILD",
            "P503_GATE_EVIDENCE_ATTACH_RECEIPT_SEAL",
        }
        for code in expected:
            with self.subTest(code=code):
                self.assertEqual(source.count(f'"{code}"'), 1)

    def _template_snapshot(self, *, include_release_baseline: bool = True):
        EvidenceKind = self.template_domain.EvidenceKind
        Classification = self.template_domain.GateRequirementClassification
        Priority = self.template_domain.GateRequirementPriority
        Requirement = self.template_domain.GateRequirementDefinition
        ProjectType = importlib.import_module("npi_core.project.domain").ProjectType
        allowed_evidence_kinds = [
            EvidenceKind.WBS_ITEM,
            EvidenceKind.FILE_REVISION,
        ]
        if include_release_baseline:
            allowed_evidence_kinds.append(EvidenceKind.RELEASE_BASELINE)
        requirement = Requirement(
            key="drawing",
            title="Released drawing",
            classification=Classification.REQUIRED,
            priority=Priority.P0,
            allowed_evidence_kinds=tuple(allowed_evidence_kinds),
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

    @staticmethod
    def _release_baseline():
        snapshot = {
            "schemaVersion": 1,
            "globalId": str(BASELINE_ID),
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "label": "G2 release package",
            "version": 1,
            "members": [
                {
                    "globalId": str(member_id),
                    "sequence": index,
                    "documentGlobalId": str(document_id),
                    "revisionGlobalId": str(revision_id),
                    "revisionSnapshotHash": hash_value,
                }
                for index, (member_id, document_id, revision_id, hash_value) in enumerate(
                    zip(
                        BASELINE_MEMBER_IDS,
                        BASELINE_DOCUMENT_IDS,
                        BASELINE_REVISION_IDS,
                        ("e" * 64, "f" * 64),
                        strict=True,
                    ),
                    start=1,
                )
            ],
        }
        return types.SimpleNamespace(
            global_id=BASELINE_ID,
            version=1,
            snapshot_hash="d" * 64,
            snapshot_payload=lambda: snapshot,
            members=tuple(
                types.SimpleNamespace(
                    global_id=member_id,
                    sequence=index,
                    document_global_id=document_id,
                    revision_global_id=revision_id,
                    revision_snapshot_hash=hash_value,
                )
                for index, (member_id, document_id, revision_id, hash_value) in enumerate(
                    zip(
                        BASELINE_MEMBER_IDS,
                        BASELINE_DOCUMENT_IDS,
                        BASELINE_REVISION_IDS,
                        ("e" * 64, "f" * 64),
                        strict=True,
                    ),
                    start=1,
                )
            ),
        )

    @staticmethod
    def _baseline_response(baseline) -> dict[str, object]:
        return {
            "globalId": str(baseline.global_id),
            "label": "G2 release package",
            "version": baseline.version,
            "snapshotHash": baseline.snapshot_hash,
            "policy": {
                "globalId": str(TEMPLATE_ID),
                "version": 1,
                "snapshotHash": "a" * 64,
            },
            "createdByUserId": "Administrator",
            "createdAt": "2026-07-31T12:00:00Z",
            "members": [],
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
        self.assertEqual(outcome.response["baselineImpacts"], [])
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

    def test_workspace_exposes_gate_scoped_validated_baseline_impacts(self) -> None:
        repository = self._repository()
        outcome = self._freeze(repository)
        self.assertIsNotNone(outcome)
        impact = object()
        response = {
            "globalId": "1fb3ebaf-e053-4e0b-9955-8233563a65f7",
            "eventType": "invalidated",
        }
        calls: list[tuple[str, UUID]] = []

        def load_impacts(project, *, gate_global_id: UUID):
            calls.append((str(project.global_id), gate_global_id))
            return (impact,)

        self.repository_module.load_project_baseline_impacts = load_impacts
        self.repository_module.document_baseline_impact_response = (
            lambda value: response if value is impact else None
        )

        workspace = repository.evidence_workspace(PROJECT_ID, GATE_ID)

        self.assertIsNotNone(workspace)
        assert workspace is not None
        self.assertEqual(calls, [(str(PROJECT_ID), GATE_ID)])
        self.assertEqual(workspace["baselineImpacts"], [response])

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

    def test_release_baseline_registers_each_member_dependency_in_same_command(
        self,
    ) -> None:
        repository = self._repository()
        self._freeze(repository)
        outcome = repository.attach_evidence(
            PROJECT_ID,
            GATE_ID,
            "drawing",
            idempotency_key="baseline-gate-evidence-attach",
            expected_gate_version=2,
            evidence_kind="release_baseline",
            source_global_id=BASELINE_ID,
            source_version=1,
            source_hash=self.baseline.snapshot_hash,
        )

        self.assertIsNotNone(outcome)
        assert outcome is not None
        evidence = outcome.response["requirements"][0]["evidence"][0]
        self.assertEqual(evidence["kind"], "release_baseline")
        self.assertEqual(evidence["baseline"]["globalId"], str(BASELINE_ID))
        self.assertNotIn("url", str(evidence).casefold())
        self.assertEqual(
            self.baseline_load_calls,
            [
                (str(PROJECT_ID), BASELINE_ID, True),
                (str(PROJECT_ID), BASELINE_ID, False),
            ],
        )
        dependencies = tuple(
            self.store.documents["NPI Baseline Gate Dependency"].values()
        )
        self.assertEqual(len(dependencies), len(BASELINE_REVISION_IDS))
        reference = next(
            iter(self.store.documents["NPI Gate Evidence Reference"].values())
        )
        for dependency, document_id, revision_id, revision_hash in zip(
            dependencies,
            BASELINE_DOCUMENT_IDS,
            BASELINE_REVISION_IDS,
            ("e" * 64, "f" * 64),
            strict=True,
        ):
            self.assertEqual(dependency.baseline_global_id, str(BASELINE_ID))
            self.assertEqual(dependency.input_document_global_id, str(document_id))
            self.assertEqual(dependency.input_revision_global_id, str(revision_id))
            self.assertEqual(dependency.input_revision_snapshot_hash, revision_hash)
            self.assertEqual(
                dependency.evidence_reference_global_id,
                reference.global_id,
            )
            self.assertRegex(dependency.dependency_key, r"^[a-f0-9]{64}$")
            self.assertRegex(dependency.snapshot_hash, r"^[a-f0-9]{64}$")
        self.assertFalse(
            hasattr(self.frappe.flags, "npi_baseline_dependency_system_write")
        )
        with self.assertRaises(
            importlib.import_module(
                "npi_core.gate_evidence.domain"
            ).EvidenceAlreadyAttached
        ):
            repository.attach_evidence(
                PROJECT_ID,
                GATE_ID,
                "drawing",
                idempotency_key="duplicate-baseline-gate-evidence",
                expected_gate_version=3,
                evidence_kind="release_baseline",
                source_global_id=BASELINE_ID,
                source_version=1,
                source_hash=self.baseline.snapshot_hash,
            )
        self.assertEqual(
            len(self.store.documents["NPI Baseline Gate Dependency"]),
            len(BASELINE_REVISION_IDS),
        )

    def test_baseline_reference_dependencies_gate_audit_and_receipt_share_scope(
        self,
    ) -> None:
        source = inspect.getsource(
            self.repository_module.FrappeGateEvidenceRepository.attach_evidence
        )
        scope = source.index("with _controlled_gate_write_scope():")
        order = (
            "self._insert_idempotency(",
            '"doctype": "NPI Gate Evidence Reference"',
            "self._insert_baseline_dependencies(",
            "gate.save()",
            "self._refresh_gate_review_locked(project, gate)",
            "self._append_audit(",
            "response = self._workspace_for(project, gate)",
            "self._seal_idempotency(idempotency, response)",
        )
        positions = [source.index(fragment, scope) for fragment in order]
        self.assertEqual(positions, sorted(positions))

    def test_release_baseline_rejects_missing_tampered_version_or_hash(self) -> None:
        repository = self._repository()
        self._freeze(repository)
        EvidenceSourceUnavailable = importlib.import_module(
            "npi_core.gate_evidence.domain"
        ).EvidenceSourceUnavailable
        EvidenceVersionConflict = importlib.import_module(
            "npi_core.gate_evidence.domain"
        ).EvidenceVersionConflict

        for version, snapshot_hash in (
            (2, self.baseline.snapshot_hash),
            (1, "0" * 64),
        ):
            with self.subTest(version=version, snapshot_hash=snapshot_hash):
                with self.assertRaises(EvidenceVersionConflict):
                    repository.attach_evidence(
                        PROJECT_ID,
                        GATE_ID,
                        "drawing",
                        idempotency_key=f"baseline-conflict-{version}-{snapshot_hash[:1]}",
                        expected_gate_version=2,
                        evidence_kind="release_baseline",
                        source_global_id=BASELINE_ID,
                        source_version=version,
                        source_hash=snapshot_hash,
                    )

        def unavailable_baseline(*_args, **_kwargs):
            raise self.repository_module.DocumentBaselineInputUnavailable()

        self.repository_module.load_document_baseline = unavailable_baseline
        with self.assertRaises(EvidenceSourceUnavailable):
            repository.attach_evidence(
                PROJECT_ID,
                GATE_ID,
                "drawing",
                idempotency_key="baseline-tampered-member",
                expected_gate_version=2,
                evidence_kind="release_baseline",
                source_global_id=BASELINE_ID,
                source_version=1,
                source_hash=self.baseline.snapshot_hash,
            )
        self.assertEqual(self.gate.optimistic_version, 2)
        self.assertNotIn(
            "NPI Gate Evidence Reference",
            self.store.documents,
        )
        self.assertNotIn(
            "NPI Baseline Gate Dependency",
            self.store.documents,
        )

    def test_historical_template_remains_valid_without_baseline_kind(self) -> None:
        legacy = self._template_snapshot(include_release_baseline=False)
        self.template_snapshot = legacy
        self.gate.gate_template_snapshot_hash = legacy.snapshot_hash
        repository = self._repository()
        outcome = self._freeze(repository)
        self.assertIsNotNone(outcome)
        assert outcome is not None
        requirement = outcome.response["requirements"][0]
        self.assertEqual(
            requirement["allowedEvidenceKinds"],
            ["file_revision", "wbs_item"],
        )
        with self.assertRaises(
            importlib.import_module(
                "npi_core.foundation.errors"
            ).RequestValidationFailed
        ):
            repository.attach_evidence(
                PROJECT_ID,
                GATE_ID,
                "drawing",
                idempotency_key="legacy-template-baseline-denied",
                expected_gate_version=2,
                evidence_kind="release_baseline",
                source_global_id=BASELINE_ID,
                source_version=1,
                source_hash=self.baseline.snapshot_hash,
            )
        self.assertEqual(self.baseline_load_calls, [])

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
