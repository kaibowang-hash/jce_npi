from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import datetime
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

TENANT_ID = "tenant-a"
PROJECT_ID = UUID("54bccb5c-f681-4e9e-aa6b-57e995b26eb4")
GATE_ID = UUID("7f5c61f7-09eb-41d1-808f-359f788e806c")
REQUIREMENT_ID = UUID("890364b3-df64-5179-b4d4-81307737c6b3")
FILE_REVISION_ID = UUID("fe8d0b1b-87c1-4ad2-9e08-e88950731f2d")
DOCUMENT_ID = UUID("2a3cc6e2-e585-4b19-9239-c756e7b4b555")
WBS_ID = UUID("e2d8072c-65b9-47b9-92ee-98241f732a30")
BASELINE_ID = UUID("1ba71ee3-c1fe-46d9-b9c6-67fb3c06aff2")


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


class StubFile(StubDocument):
    def __init__(
        self,
        *,
        private: bool = True,
        content: bytes = b"controlled-file-content",
    ) -> None:
        super().__init__(
            {
                "name": "file-record-001",
                "file_url": (
                    "/private/files/drawing.pdf" if private else "/files/drawing.pdf"
                ),
                "file_name": "drawing.pdf",
                "file_size": len(content),
                "content_hash": __import__("hashlib")
                .md5(content, usedforsecurity=False)
                .hexdigest(),
                # Frappe v15 does not persist content_type; MIME must be
                # deterministically derived from the immutable file name.
                "content_type": "application/x-transient-value",
                "is_private": 1 if private else 0,
                "is_remote_file": 0,
                "_content": content,
            }
        )

    def get_content(self) -> bytes:
        return self._content


class GateEvidenceControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "frappe.utils",
        "npi_core.controlled_evidence_validation",
        "npi_core.project.frappe_validation",
        ("npi_core.npi_core.doctype.npi_file_revision" ".npi_file_revision"),
        (
            "npi_core.npi_core.doctype.npi_gate_evidence_reference"
            ".npi_gate_evidence_reference"
        ),
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
        self.documents: dict[tuple[str, str], StubDocument] = {}

        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = self.PermissionError
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user="Administrator")

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        def get_doc(doctype: str, name: str) -> StubDocument:
            document = self.documents.get((doctype, str(name)))
            if document is None:
                raise self.ValidationError("missing")
            return document

        project = types.SimpleNamespace(
            global_id=str(PROJECT_ID),
            tenant_id=TENANT_ID,
        )
        gate = types.SimpleNamespace(
            global_id=str(GATE_ID),
            project_global_id=str(PROJECT_ID),
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
            if doctype == "NPI Gate Shell" and name == str(GATE_ID):
                return gate
            return None

        frappe.throw = throw
        frappe.get_doc = get_doc
        frappe.db = types.SimpleNamespace(get_value=get_value)

        model = types.ModuleType("frappe.model")
        document_module = types.ModuleType("frappe.model.document")
        document_module.Document = StubDocument
        model.document = document_module
        utils = types.ModuleType("frappe.utils")
        utils.now_datetime = lambda: datetime(2026, 7, 23, 12, 0, 0)
        frappe.model = model
        frappe.utils = utils

        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document_module
        sys.modules["frappe.utils"] = utils

        self.frappe = frappe
        self.validation = importlib.import_module(
            "npi_core.controlled_evidence_validation"
        )
        self.file_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_file_revision" ".npi_file_revision"
        )
        self.evidence_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_evidence_reference"
            ".npi_gate_evidence_reference"
        )
        self.baseline_source: StubDocument | None = None
        self.baseline_load_calls: list[tuple[str, UUID, bool]] = []

        def load_document_baseline(project, baseline_id: UUID, *, lock: bool):
            self.baseline_load_calls.append((str(project.global_id), baseline_id, lock))
            if baseline_id == BASELINE_ID:
                return self.baseline_source
            return None

        self.evidence_module.load_document_baseline = load_document_baseline
        self.documents[("NPI Engineering Project", str(PROJECT_ID))] = StubDocument(
            {
                "global_id": str(PROJECT_ID),
                "tenant_id": TENANT_ID,
            }
        )
        self.gate_shell_module = importlib.import_module(
            "npi_core.npi_core.doctype.npi_gate_shell.npi_gate_shell"
        )
        self.FileController = self.file_module.NPIFileRevision
        self.EvidenceController = self.evidence_module.NPIGateEvidenceReference
        self.GateShellController = self.gate_shell_module.NPIGateShell

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def file_revision(self, *, file_id: str = "file-record-001") -> StubDocument:
        return self.FileController(
            {
                "global_id": str(FILE_REVISION_ID),
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(DOCUMENT_ID),
                "revision": 1,
                "revision_key": None,
                "frappe_file_id": file_id,
                "file": "/client/value/is/ignored",
                "file_name": None,
                "mime_type": None,
                "size_bytes": None,
                "sha256": "f" * 64,
                "is_private": 0,
                "scan_state": "clean",
                "scan_observed_at": datetime(2026, 7, 23, 11, 0, 0),
                "released": 1,
                "optimistic_version": None,
            }
        )

    def complete_new_file_revision(
        self,
        *,
        content: bytes = b"controlled-file-content",
    ) -> StubDocument:
        self.documents[("File", "file-record-001")] = StubFile(content=content)
        self.frappe.flags.npi_file_revision_command_write = True
        document = self.file_revision()
        document.autoname()
        document.before_insert()
        document.before_validate()
        document.validate()
        document.before_save()
        return document

    def wbs_item(self) -> StubDocument:
        return StubDocument(
            {
                "global_id": str(WBS_ID),
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "work_policy_global_id": "7f60c0ec-8e03-42d3-a89b-09fda884066c",
                "work_policy_version": 1,
                "work_policy_snapshot_hash": "a" * 64,
                "wbs_code": "WBS-001",
                "title": "Synthetic work",
                "parent_global_id": None,
                "owner_role_assignment_global_id": None,
                "planned_start": "2026-07-23",
                "planned_end": "2026-07-25",
                "actual_start": None,
                "actual_end": None,
                "milestone": 0,
                "status_key": "draft",
                "status_label_source": "Draft",
                "progress_percent": 0,
                "critical_task": 1,
                "plan_revision": 1,
                "optimistic_version": 3,
            }
        )

    def release_baseline(self) -> StubDocument:
        snapshot = {
            "schemaVersion": 1,
            "globalId": str(BASELINE_ID),
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "label": "G2 release package",
            "version": 1,
        }
        return StubDocument(
            {
                "global_id": str(BASELINE_ID),
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "version": 1,
                "snapshot_hash": self.validation.canonical_snapshot_hash(snapshot),
                "snapshot_payload": lambda: snapshot,
            }
        )

    def evidence(
        self,
        *,
        kind: str,
        source: StubDocument,
        source_hash: str,
        snapshot: dict[str, object],
    ) -> StubDocument:
        return self.EvidenceController(
            {
                "global_id": "217e0749-f503-49c0-8df9-9e51b2877229",
                "reference_key": None,
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "gate_global_id": str(GATE_ID),
                "requirement_global_id": str(REQUIREMENT_ID),
                "requirement_key": "Drawing",
                "evidence_kind": kind,
                "source_object_type": kind,
                "source_global_id": str(source.global_id),
                "source_version": (
                    int(source.revision)
                    if kind == "file_revision"
                    else (
                        int(source.version)
                        if kind == "release_baseline"
                        else int(source.optimistic_version)
                    )
                ),
                "source_hash": source_hash,
                "source_snapshot": snapshot,
                "created_by": "spoofed@example.invalid",
                "created_at": datetime(2020, 1, 1),
                "optimistic_version": 999,
            }
        )

    def persist_new_evidence(self, document: StubDocument) -> None:
        self.frappe.flags.npi_gate_evidence_command_write = True
        document.autoname()
        document.before_insert()
        document.before_validate()
        document.validate()
        document.before_save()

    def test_new_file_identity_is_server_derived_private_and_pending(self) -> None:
        document = self.complete_new_file_revision()
        expected_hash = (
            __import__("hashlib").sha256(b"controlled-file-content").hexdigest()
        )
        self.assertEqual(document.name, str(FILE_REVISION_ID))
        self.assertEqual(document.revision_key, f"{DOCUMENT_ID}:1")
        self.assertEqual(document.frappe_file_id, "file-record-001")
        self.assertEqual(
            document.frappe_content_hash,
            __import__("hashlib")
            .md5(b"controlled-file-content", usedforsecurity=False)
            .hexdigest(),
        )
        self.assertEqual(document.file, "/private/files/drawing.pdf")
        self.assertEqual(document.file_name, "drawing.pdf")
        self.assertEqual(document.mime_type, "application/pdf")
        self.assertEqual(document.size_bytes, len(b"controlled-file-content"))
        self.assertEqual(document.sha256, expected_hash)
        self.assertEqual(document.is_private, 1)
        self.assertEqual(document.scan_state, "pending")
        self.assertIsNone(document.scan_observed_at)
        self.assertEqual(document.released, 0)
        self.assertEqual(document.optimistic_version, 1)
        self.assertTrue(self.file_module.has_live_private_file_identity(document))

    def test_live_file_privacy_and_content_identity_drift_fail_closed(self) -> None:
        document = self.complete_new_file_revision()
        file_document = self.documents[("File", "file-record-001")]

        file_document.is_private = 0
        file_document.file_url = "/files/drawing.pdf"
        self.assertFalse(self.file_module.has_live_private_file_identity(document))

        file_document.is_private = 1
        file_document.file_url = "/private/files/drawing.pdf"
        file_document.content_hash = "0" * 32
        self.assertFalse(self.file_module.has_live_private_file_identity(document))

        empty = self.complete_new_file_revision(content=b"")
        self.assertEqual(empty.size_bytes, 0)
        self.assertTrue(self.file_module.has_live_private_file_identity(empty))

    def test_generic_or_public_file_creation_is_denied(self) -> None:
        with self.assertRaises(self.PermissionError):
            self.file_revision().before_insert()

        self.documents[("File", "public-file")] = StubFile(private=False)
        self.frappe.flags.npi_file_revision_command_write = True
        document = self.file_revision(file_id="public-file")
        document.before_validate()
        with self.assertRaises(self.ValidationError):
            document.validate()

    def test_generic_gate_update_is_denied_before_field_validation(self) -> None:
        document = self.GateShellController(
            {
                "project_global_id": str(PROJECT_ID),
                "gate_key": "G0",
            }
        )
        document._previous = StubDocument({})

        with self.assertRaises(self.PermissionError):
            document.before_validate()

        self.frappe.flags.npi_gate_evidence_command_write = True
        document.before_validate()
        self.assertEqual(document.shell_key, f"{PROJECT_ID}:G0")

    def test_legacy_incomplete_row_is_readable_but_not_complete_evidence(self) -> None:
        legacy = StubDocument(
            {
                "global_id": str(FILE_REVISION_ID),
                "revision": 1,
                "file": "/private/files/legacy.pdf",
                "sha256": "a" * 64,
                "scan_state": "pending",
            }
        )
        self.assertFalse(self.file_module.has_complete_file_revision_identity(legacy))
        with self.assertRaises(self.ValidationError):
            self.file_module.file_revision_source_snapshot(legacy)

        inconsistent = self.complete_new_file_revision()
        inconsistent.revision_key = f"{DOCUMENT_ID}:2"
        self.assertFalse(
            self.file_module.has_complete_file_revision_identity(inconsistent)
        )

    def test_scan_state_change_requires_the_dedicated_scanner_flag(self) -> None:
        previous = self.complete_new_file_revision()
        values = {
            fieldname: previous.get(fieldname)
            for fieldname in (
                "global_id",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "revision",
                "revision_key",
                "frappe_file_id",
                "frappe_content_hash",
                "file",
                "file_name",
                "mime_type",
                "size_bytes",
                "sha256",
                "is_private",
                "scan_state",
                "scan_observed_at",
                "released",
                "optimistic_version",
            )
        }
        current = self.FileController(values)
        current._previous = previous
        current.scan_state = "clean"
        current.scan_observed_at = datetime(2026, 7, 23, 12, 0, 0)

        self.frappe.flags.npi_file_scan_result_write = False
        with self.assertRaises(self.PermissionError):
            current.validate()

        self.frappe.flags.npi_file_scan_result_write = True
        current.validate()
        current.before_save()
        self.assertEqual(current.scan_state, "clean")
        self.assertEqual(current.optimistic_version, 2)

    def test_wbs_evidence_freezes_exact_snapshot_and_blocks_spoofed_hash(self) -> None:
        source = self.wbs_item()
        self.documents[("NPI WBS Item", str(WBS_ID))] = source
        snapshot = self.evidence_module.wbs_item_source_snapshot(source)
        source_hash = self.validation.canonical_snapshot_hash(snapshot)
        evidence = self.evidence(
            kind="wbs_item",
            source=source,
            source_hash=source_hash,
            snapshot=snapshot,
        )
        self.persist_new_evidence(evidence)

        self.assertEqual(evidence.created_by, "Administrator")
        self.assertEqual(evidence.requirement_key, "Drawing")
        self.assertEqual(evidence.optimistic_version, 1)
        self.assertRegex(evidence.reference_key, r"^[a-f0-9]{64}$")
        self.assertEqual(json.loads(evidence.source_snapshot), snapshot)

        spoofed = self.evidence(
            kind="wbs_item",
            source=source,
            source_hash="0" * 64,
            snapshot=snapshot,
        )
        spoofed.before_validate()
        with self.assertRaises(self.ValidationError):
            spoofed.validate()

    def test_file_evidence_uses_revision_sha_and_url_free_metadata(self) -> None:
        source = self.complete_new_file_revision()
        self.documents[("NPI File Revision", str(FILE_REVISION_ID))] = source
        snapshot = self.file_module.file_revision_source_snapshot(source)
        evidence = self.evidence(
            kind="file_revision",
            source=source,
            source_hash=source.sha256,
            snapshot=snapshot,
        )
        self.persist_new_evidence(evidence)

        persisted_snapshot = json.loads(evidence.source_snapshot)
        self.assertEqual(evidence.source_version, 1)
        self.assertEqual(evidence.source_hash, source.sha256)
        self.assertEqual(persisted_snapshot["scanState"], "pending")
        self.assertNotIn("/private/files/", evidence.source_snapshot)
        self.assertFalse(any("url" in key.casefold() for key in persisted_snapshot))

    def test_release_baseline_evidence_reloads_exact_immutable_snapshot(self) -> None:
        source = self.release_baseline()
        self.baseline_source = source
        snapshot = source.snapshot_payload()
        evidence = self.evidence(
            kind="release_baseline",
            source=source,
            source_hash=source.snapshot_hash,
            snapshot=snapshot,
        )
        self.persist_new_evidence(evidence)

        self.assertEqual(
            self.baseline_load_calls,
            [(str(PROJECT_ID), BASELINE_ID, False)],
        )
        self.assertEqual(json.loads(evidence.source_snapshot), snapshot)
        self.assertEqual(evidence.source_version, 1)
        self.assertEqual(evidence.source_hash, source.snapshot_hash)

        drifted = self.evidence(
            kind="release_baseline",
            source=source,
            source_hash=source.snapshot_hash,
            snapshot={**snapshot, "label": "Caller supplied drift"},
        )
        drifted.before_validate()
        with self.assertRaises(self.ValidationError):
            drifted.validate()

    def test_cross_tenant_raw_url_and_updates_are_rejected(self) -> None:
        source = self.wbs_item()
        self.documents[("NPI WBS Item", str(WBS_ID))] = source
        snapshot = self.evidence_module.wbs_item_source_snapshot(source)
        snapshot["fileUrl"] = "/private/files/secret.pdf"
        evidence = self.evidence(
            kind="wbs_item",
            source=source,
            source_hash="0" * 64,
            snapshot=snapshot,
        )
        with self.assertRaises(self.ValidationError):
            evidence.before_validate()

        clean_snapshot = self.evidence_module.wbs_item_source_snapshot(source)
        cross_tenant = self.evidence(
            kind="wbs_item",
            source=source,
            source_hash=self.validation.canonical_snapshot_hash(clean_snapshot),
            snapshot=clean_snapshot,
        )
        cross_tenant.tenant_id = "tenant-b"
        cross_tenant.before_validate()
        with self.assertRaises(self.ValidationError):
            cross_tenant.validate()

        immutable = self.evidence(
            kind="wbs_item",
            source=source,
            source_hash=self.validation.canonical_snapshot_hash(clean_snapshot),
            snapshot=clean_snapshot,
        )
        immutable._previous = StubDocument({})
        self.frappe.flags.npi_gate_evidence_command_write = True
        with self.assertRaises(self.PermissionError):
            immutable.before_save()
        with self.assertRaises(self.PermissionError):
            immutable.on_trash()


if __name__ == "__main__":
    unittest.main()
