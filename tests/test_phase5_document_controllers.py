from __future__ import annotations

import hashlib
import importlib
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid5


sys.path.insert(0, "apps/npi_core")

TENANT_ID = "tenant-a"
PROJECT_ID = UUID("ee7193f7-a704-4ed3-9ac0-85c2b1b45184")
POLICY_ID = UUID("83cdca19-f649-4a18-8a5b-9d263d97a911")
POLICY_VERSION_ID = uuid5(POLICY_ID, "version:1")
DOCUMENT_ID = UUID("927466bd-a55d-48a1-9ddb-637e4ccb88c0")
REVISION_ID = UUID("66997315-516a-4a5d-800b-0933f70a1e7d")
REVISION_FILE_ID = UUID("2f4f7899-0fb4-483e-8660-e0ff79c09584")
FILE_DOCUMENT_ID = UUID("7b8942df-0a2f-4712-b4fd-71840b0937a0")
FILE_REVISION_ID = UUID("56b90190-26c4-4ba6-b9e4-6495347621c9")
LOCK_ID = UUID("6e38c507-d2cc-4f39-95b0-cd62d75d14dc")
ACQUIRE_EVENT_ID = UUID("ba94e31a-fe62-4c00-8aaf-c3e6dfbd3804")
NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


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
    return document.__class__(
        {
            fieldname: value
            for fieldname, value in vars(document).items()
            if fieldname != "_previous"
        }
    )


class Phase5DocumentControllerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.documents.frappe_validation",
        "npi_core.npi_core.doctype.npi_document_policy.npi_document_policy",
        (
            "npi_core.npi_core.doctype.npi_document_policy_version"
            ".npi_document_policy_version"
        ),
        (
            "npi_core.npi_core.doctype.npi_controlled_document"
            ".npi_controlled_document"
        ),
        ("npi_core.npi_core.doctype.npi_document_revision" ".npi_document_revision"),
        (
            "npi_core.npi_core.doctype.npi_document_revision_file"
            ".npi_document_revision_file"
        ),
        (
            "npi_core.npi_core.doctype.npi_document_relationship"
            ".npi_document_relationship"
        ),
        (
            "npi_core.npi_core.doctype.npi_document_lock_event"
            ".npi_document_lock_event"
        ),
        (
            "npi_core.npi_core.doctype.npi_document_share_grant"
            ".npi_document_share_grant"
        ),
        (
            "npi_core.npi_core.doctype.npi_document_command_idempotency"
            ".npi_document_command_idempotency"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.ValidationError = type("ValidationError", (Exception,), {})
        self.PermissionError = type("PermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = self.PermissionError
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user="Administrator")
        frappe.get_request_header = lambda name: (
            "trace-document-delete-001" if name == "X-Trace-ID" else None
        )
        self.audit_inserts: list[dict[str, Any]] = []
        self.transaction_events: list[str] = []

        class CallbackQueue:
            def __init__(queue_self) -> None:
                queue_self.functions: list[Any] = []

            def add(queue_self, function) -> None:
                queue_self.functions.append(function)

            def run(queue_self) -> None:
                while queue_self.functions:
                    queue_self.functions.pop(0)()

            def reset(queue_self) -> None:
                queue_self.functions.clear()

        class StubDatabase:
            def __init__(database_self) -> None:
                database_self.after_rollback = CallbackQueue()

            def get_value(
                database_self,
                doctype: str,
                name: str,
                fields: list[str],
                *,
                as_dict: bool,
            ) -> dict[str, object] | None:
                if (
                    doctype == "NPI Document Policy"
                    and name == str(POLICY_ID)
                    and as_dict
                ):
                    return {
                        "global_id": str(POLICY_ID),
                        "tenant_id": TENANT_ID,
                        "policy_key": "synthetic_document_policy",
                        "enabled": 1,
                    }
                if (
                    doctype == "NPI Document Policy Version"
                    and isinstance(name, dict)
                    and name.get("policy_global_id") == str(POLICY_ID)
                    and name.get("policy_version") == 1
                ):
                    return {
                        "global_id": str(POLICY_VERSION_ID),
                        "policy_global_id": str(POLICY_ID),
                        "policy_key": "synthetic_document_policy",
                        "policy_version": 1,
                        "title": "Synthetic document policy",
                        "publication_state": "published",
                        "document_types": [
                            {
                                "key": "drawing",
                                "prefix": "SYN-DWG",
                                "titleSource": "Drawing",
                            }
                        ],
                        "confidentiality_keys": ["project_internal"],
                        "allowed_mime_types": ["application/pdf"],
                        "preview_mime_types": ["application/pdf"],
                        "maximum_file_bytes": 1_048_576,
                        "lock_lease_minutes": 30,
                        "snapshot_hash": self.policy.snapshot_hash,
                    }
                if doctype == "NPI Engineering Project" and name == str(PROJECT_ID):
                    return {
                        "global_id": str(PROJECT_ID),
                        "tenant_id": TENANT_ID,
                        "optimistic_version": 1,
                    }
                if doctype == "NPI Controlled Document" and name == str(DOCUMENT_ID):
                    return {
                        "global_id": str(DOCUMENT_ID),
                        "tenant_id": TENANT_ID,
                        "project_global_id": str(PROJECT_ID),
                        "policy_global_id": str(POLICY_ID),
                        "policy_version": 1,
                        "policy_snapshot_hash": self.policy.snapshot_hash,
                        "current_lock_global_id": str(LOCK_ID),
                        "current_lock_version": 1,
                        "current_lock_holder_user_id": "engineer@example.invalid",
                        "current_revision_global_id": None,
                        "current_revision_major": None,
                        "current_revision_minor": None,
                    }
                if (
                    doctype == "NPI Document Lock Event"
                    and isinstance(name, dict)
                    and name.get("lock_global_id") == str(LOCK_ID)
                    and name.get("lock_version") == 1
                ):
                    return {
                        "tenant_id": TENANT_ID,
                        "project_global_id": str(PROJECT_ID),
                        "document_global_id": str(DOCUMENT_ID),
                        "event_type": "acquired",
                        "holder_user_id": "engineer@example.invalid",
                        "expires_at": NOW + timedelta(minutes=30),
                    }
                if doctype == "NPI Document Lock Event" and name == str(
                    ACQUIRE_EVENT_ID
                ):
                    return {
                        "global_id": str(ACQUIRE_EVENT_ID),
                        "tenant_id": TENANT_ID,
                        "project_global_id": str(PROJECT_ID),
                        "document_global_id": str(DOCUMENT_ID),
                        "lock_global_id": str(LOCK_ID),
                        "lock_version": 1,
                        "event_type": "acquired",
                        "holder_user_id": "engineer@example.invalid",
                        "acquired_at": NOW,
                        "expires_at": NOW + timedelta(minutes=30),
                    }
                if doctype == "NPI Document Revision" and name == str(REVISION_ID):
                    return {
                        "global_id": str(REVISION_ID),
                        "tenant_id": TENANT_ID,
                        "project_global_id": str(PROJECT_ID),
                        "document_global_id": str(DOCUMENT_ID),
                        "snapshot_hash": "a" * 64,
                    }
                if (
                    doctype == "NPI Gate Shell"
                    and name == "af04c815-6a92-4db2-a0dd-1b2f7771c2f1"
                ):
                    return {
                        "global_id": "af04c815-6a92-4db2-a0dd-1b2f7771c2f1",
                        "project_global_id": str(PROJECT_ID),
                        "optimistic_version": 1,
                    }
                if doctype == "NPI File Revision" and name == str(FILE_REVISION_ID):
                    return {
                        "global_id": str(FILE_REVISION_ID),
                        "tenant_id": TENANT_ID,
                        "project_global_id": str(PROJECT_ID),
                        "document_global_id": str(FILE_DOCUMENT_ID),
                        "revision": 1,
                        "optimistic_version": 1,
                        "frappe_file_id": "synthetic-file-id",
                        "frappe_content_hash": "c" * 32,
                        "file_name": "synthetic.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 20,
                        "sha256": "b" * 64,
                        "scan_state": "pending",
                        "scan_observed_at": None,
                        "is_private": 1,
                        "released": 0,
                    }
                if doctype == "NPI Document Revision File" and name == str(
                    REVISION_FILE_ID
                ):
                    return {
                        "global_id": str(REVISION_FILE_ID),
                        "file_revision_global_id": str(FILE_REVISION_ID),
                        "tenant_id": TENANT_ID,
                        "project_global_id": str(PROJECT_ID),
                        "document_global_id": str(DOCUMENT_ID),
                        "document_revision_global_id": str(REVISION_ID),
                        "snapshot_hash": "e" * 64,
                    }
                return None

            def commit(database_self) -> None:
                self.transaction_events.append("commit")
                database_self.after_rollback.reset()

            def rollback(database_self) -> None:
                self.transaction_events.append("rollback")
                database_self.after_rollback.run()

        frappe.db = StubDatabase()

        class AuditDocument:
            def __init__(audit_self, values: dict[str, Any]) -> None:
                audit_self.values = values

            def insert(audit_self):
                self.transaction_events.append("audit_insert")
                self.audit_inserts.append(dict(audit_self.values))
                return audit_self

        frappe.get_doc = lambda values: AuditDocument(values)

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
            "npi_core.documents.frappe_validation"
        )
        self.Policy = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_policy.npi_document_policy"
        ).NPIDocumentPolicy
        self.PolicyVersion = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_policy_version"
            ".npi_document_policy_version"
        ).NPIDocumentPolicyVersion
        self.ControlledDocument = importlib.import_module(
            "npi_core.npi_core.doctype.npi_controlled_document"
            ".npi_controlled_document"
        ).NPIControlledDocument
        self.Revision = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_revision" ".npi_document_revision"
        ).NPIDocumentRevision
        self.RevisionFile = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_revision_file"
            ".npi_document_revision_file"
        ).NPIDocumentRevisionFile
        self.Relationship = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_relationship"
            ".npi_document_relationship"
        ).NPIDocumentRelationship
        self.LockEvent = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_lock_event"
            ".npi_document_lock_event"
        ).NPIDocumentLockEvent
        self.ShareGrant = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_share_grant"
            ".npi_document_share_grant"
        ).NPIDocumentShareGrant
        self.Idempotency = importlib.import_module(
            "npi_core.npi_core.doctype.npi_document_command_idempotency"
            ".npi_document_command_idempotency"
        ).NPIDocumentCommandIdempotency

        domain = importlib.import_module("npi_core.documents.domain")
        self.domain = domain
        self.policy = domain.DocumentPolicyVersion(
            global_id=POLICY_VERSION_ID,
            policy_global_id=POLICY_ID,
            policy_key="synthetic_document_policy",
            policy_version=1,
            title="Synthetic document policy",
            state=domain.DocumentPolicyState.PUBLISHED,
            document_types=(domain.DocumentTypeRule("drawing", "SYN-DWG", "Drawing"),),
            confidentiality_keys=("project_internal",),
            allowed_mime_types=("application/pdf",),
            preview_mime_types=("application/pdf",),
            maximum_file_bytes=1_048_576,
            lock_lease_minutes=30,
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def policy_version(self) -> StubDocument:
        return self.PolicyVersion(
            {
                "doctype": "NPI Document Policy Version",
                "name": str(POLICY_VERSION_ID),
                "global_id": str(POLICY_VERSION_ID),
                "document_policy": str(POLICY_ID),
                "tenant_id": TENANT_ID,
                "policy_global_id": str(POLICY_ID),
                "policy_key": "synthetic_document_policy",
                "policy_version": 1,
                "version_key": f"{POLICY_ID}:1",
                "title": "Synthetic document policy",
                "publication_state": "draft",
                "document_types": [
                    {
                        "key": "drawing",
                        "prefix": "SYN-DWG",
                        "titleSource": "Drawing",
                    }
                ],
                "confidentiality_keys": ["project_internal"],
                "allowed_mime_types": ["application/pdf"],
                "preview_mime_types": ["application/pdf"],
                "maximum_file_bytes": 1_048_576,
                "lock_lease_minutes": 30,
                "snapshot_hash": "",
                "policy_snapshot": None,
                "published_at": None,
                "optimistic_version": 1,
            }
        )

    def controlled_document(self) -> StubDocument:
        value = self.domain.create_controlled_document(
            document_id=DOCUMENT_ID,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            policy=self.policy,
            document_type_key="drawing",
            title="Synthetic drawing",
            confidentiality_key="project_internal",
        )
        return self.ControlledDocument(
            {
                "doctype": "NPI Controlled Document",
                "name": str(DOCUMENT_ID),
                "global_id": str(DOCUMENT_ID),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "policy_global_id": str(value.policy_ref.global_id),
                "policy_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "document_number": value.document_number,
                "document_number_key": value.document_number_key,
                "document_type_key": value.document_type_key,
                "title": value.title,
                "confidentiality_key": value.confidentiality_key,
                "current_revision_global_id": None,
                "current_revision_major": None,
                "current_revision_minor": None,
                "current_revision_snapshot_hash": None,
                "current_lock_global_id": None,
                "current_lock_version": None,
                "current_lock_holder_user_id": None,
                "current_lock_expires_at": None,
                "optimistic_version": 1,
                "created_by_user_id": "engineer@example.invalid",
                "created_at": NOW,
            }
        )

    def revision(self) -> StubDocument:
        file_snapshot = self.domain.FileRevisionSnapshot(
            global_id=FILE_REVISION_ID,
            file_document_global_id=FILE_DOCUMENT_ID,
            file_revision=1,
            optimistic_version=1,
            file_name="synthetic.pdf",
            mime_type="application/pdf",
            size_bytes=20,
            sha256="b" * 64,
            scan_state=self.domain.FileScanState.PENDING,
            frappe_file_id="synthetic-file-id",
            frappe_content_hash="c" * 32,
            is_private=True,
            released=False,
        )
        association = self.domain.DocumentRevisionFile(
            global_id=REVISION_FILE_ID,
            document_revision_global_id=REVISION_ID,
            file_revision=file_snapshot,
            display_file_name="synthetic drawing.pdf",
            role=self.domain.DocumentFileRole.PRIMARY,
            provenance="manual_upload",
            connector_state=self.domain.ConnectorState.UNAVAILABLE,
            connector_reason_code="provider_not_configured",
        )
        revision_snapshot = {
            "schemaVersion": 1,
            "globalId": str(REVISION_ID),
            "documentGlobalId": str(DOCUMENT_ID),
            "major": 1,
            "minor": 0,
            "reason": "Initial synthetic revision.",
            "effectiveDate": None,
            "predecessorRevisionId": None,
            "state": "draft",
            "documentPolicyRef": {
                "globalId": str(POLICY_ID),
                "version": 1,
                "snapshotHash": self.policy.snapshot_hash,
            },
            "lockRef": {
                "globalId": str(LOCK_ID),
                "version": 1,
                "holderUserId": "engineer@example.invalid",
            },
            "file": association.canonical_dict(),
            "createdByUserId": "engineer@example.invalid",
            "createdAt": NOW.isoformat().replace("+00:00", "Z"),
            "requestId": "request-revision-001",
            "traceId": "trace-revision-001",
        }
        return self.Revision(
            {
                "doctype": "NPI Document Revision",
                "name": str(REVISION_ID),
                "global_id": str(REVISION_ID),
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "controlled_document": str(DOCUMENT_ID),
                "document_global_id": str(DOCUMENT_ID),
                "major": 1,
                "minor": 0,
                "revision_key": self.domain.sha256_json(
                    {
                        "documentGlobalId": str(DOCUMENT_ID),
                        "major": 1,
                        "minor": 0,
                    }
                ),
                "reason": "Initial synthetic revision.",
                "effective_date": None,
                "predecessor_revision_global_id": None,
                "lock_global_id": str(LOCK_ID),
                "lock_version": 1,
                "revision_state": "draft",
                "policy_global_id": str(POLICY_ID),
                "policy_version": 1,
                "policy_snapshot_hash": self.policy.snapshot_hash,
                "revision_snapshot": revision_snapshot,
                "snapshot_hash": self.domain.sha256_json(revision_snapshot),
                "optimistic_version": 1,
                "created_by_user_id": "engineer@example.invalid",
                "created_at": NOW,
                "request_id": "request-revision-001",
                "trace_id": "trace-revision-001",
            }
        )

    def revision_file(self) -> StubDocument:
        file_snapshot = self.domain.FileRevisionSnapshot(
            global_id=FILE_REVISION_ID,
            file_document_global_id=FILE_DOCUMENT_ID,
            file_revision=1,
            optimistic_version=1,
            file_name="synthetic.pdf",
            mime_type="application/pdf",
            size_bytes=20,
            sha256="b" * 64,
            scan_state=self.domain.FileScanState.PENDING,
            frappe_file_id="synthetic-file-id",
            frappe_content_hash="c" * 32,
            is_private=True,
            released=False,
        )
        association = self.domain.DocumentRevisionFile(
            global_id=REVISION_FILE_ID,
            document_revision_global_id=REVISION_ID,
            file_revision=file_snapshot,
            display_file_name="synthetic drawing.pdf",
            role=self.domain.DocumentFileRole.PRIMARY,
            provenance="manual_upload",
            connector_state=self.domain.ConnectorState.UNAVAILABLE,
            connector_reason_code="provider_not_configured",
        )
        snapshot = {
            "schemaVersion": 1,
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "documentGlobalId": str(DOCUMENT_ID),
            "association": association.canonical_dict(),
        }
        return self.RevisionFile(
            {
                "doctype": "NPI Document Revision File",
                "name": str(REVISION_FILE_ID),
                "global_id": str(REVISION_FILE_ID),
                "association_key": self.domain.sha256_json(
                    {
                        "documentRevisionGlobalId": str(REVISION_ID),
                        "fileRevisionGlobalId": str(FILE_REVISION_ID),
                    }
                ),
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(DOCUMENT_ID),
                "document_revision": str(REVISION_ID),
                "document_revision_global_id": str(REVISION_ID),
                "file_revision": str(FILE_REVISION_ID),
                "file_revision_global_id": str(FILE_REVISION_ID),
                "file_document_global_id": str(FILE_DOCUMENT_ID),
                "file_revision_number": 1,
                "file_optimistic_version": 1,
                "display_file_name": "synthetic drawing.pdf",
                "frappe_file_id": "synthetic-file-id",
                "frappe_content_hash": "c" * 32,
                "file_name": "synthetic.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 20,
                "sha256": "b" * 64,
                "scan_state": "pending",
                "scan_observed_at": None,
                "is_private": 1,
                "released": 0,
                "file_role": "primary",
                "provenance": "manual_upload",
                "connector_state": "unavailable",
                "connector_reason_code": "provider_not_configured",
                "file_revision_source_snapshot": file_snapshot.canonical_dict(),
                "association_snapshot": snapshot,
                "snapshot_hash": self.domain.sha256_json(snapshot),
                "optimistic_version": 1,
                "created_by_user_id": "engineer@example.invalid",
                "created_at": NOW,
                "request_id": "request-revision-file-001",
                "trace_id": "trace-revision-file-001",
            }
        )

    def test_direct_generic_history_writes_are_blocked(self) -> None:
        controlled = (
            self.controlled_document(),
            self.revision(),
            self.revision_file(),
        )
        for value in controlled:
            with self.subTest(doctype=value.doctype), self.assertRaises(
                self.PermissionError
            ):
                value.before_insert()
        with self.validation.document_command_write():
            for value in controlled:
                value.before_insert()

    def test_policy_version_is_exact_and_rejects_unknown_rule_shape(self) -> None:
        value = self.policy_version()
        value.publication_state = "draft"
        value.before_validate()
        value.validate()
        draft_hash = value.snapshot_hash
        published = clone(value)
        published._previous = clone(value)
        published.publication_state = "published"
        published.before_validate()
        published.validate()
        self.assertNotEqual(draft_hash, published.snapshot_hash)
        self.assertEqual(published.snapshot_hash, self.policy.snapshot_hash)
        self.assertIsNotNone(published.published_at)
        self.assertEqual(value.document_policy, str(POLICY_ID))
        malformed = self.policy_version()
        malformed.publication_state = "draft"
        malformed.document_types[0]["unapproved"] = True
        malformed.before_validate()
        with self.assertRaises(self.ValidationError):
            malformed.validate()
        invalid_state = self.policy_version()
        invalid_state.publication_state = "released"
        invalid_state.before_validate()
        with self.assertRaises(self.ValidationError):
            invalid_state.validate()

    def test_controlled_document_starts_empty_and_advances_exactly_once(self) -> None:
        value = self.controlled_document()
        value.before_validate()
        value.validate()
        current = clone(value)
        current._previous = clone(value)
        current.current_lock_global_id = str(LOCK_ID)
        current.current_lock_version = 1
        current.current_lock_holder_user_id = "engineer@example.invalid"
        current.current_lock_expires_at = NOW + timedelta(minutes=30)
        current.optimistic_version = 2
        current.before_validate()
        current.validate()
        self.assertEqual(current.current_lock_global_id, str(LOCK_ID))
        stale = clone(current)
        stale._previous = clone(current)
        stale.title = "Changed outside the immutable root"
        stale.optimistic_version = 3
        stale.before_validate()
        with self.assertRaises(self.PermissionError):
            stale.validate()

    def test_revision_and_file_association_are_append_only_exact_snapshots(
        self,
    ) -> None:
        revision = self.revision()
        revision.before_validate()
        revision.validate()
        self.assertEqual(revision.revision_state, "draft")
        changed = clone(revision)
        changed._previous = clone(revision)
        changed.reason = "Attempted rewrite."
        changed.before_validate()
        with self.assertRaises(self.PermissionError):
            changed.validate()

        association = self.revision_file()
        association.before_validate()
        association.validate()
        self.assertNotEqual(
            association.file_document_global_id,
            association.document_global_id,
        )
        drifted = self.revision_file()
        drifted.association_snapshot["association"]["file"]["sha256"] = "c" * 64
        drifted.before_validate()
        with self.assertRaises(self.ValidationError):
            drifted.validate()

    def test_relationship_is_typed_and_server_keyed(self) -> None:
        relationship_id = UUID("41c0cdd9-9919-4ead-91f7-d1f6d625e008")
        target_snapshot = {
            "schemaVersion": 1,
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "kind": "gate",
            "projectReferenceType": None,
            "targetSourceSystem": None,
            "targetReferenceGlobalId": None,
            "targetIdentity": "af04c815-6a92-4db2-a0dd-1b2f7771c2f1",
            "targetVersion": 1,
        }
        value = self.Relationship(
            {
                "doctype": "NPI Document Relationship",
                "name": str(relationship_id),
                "global_id": str(relationship_id),
                "relationship_key": "",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "controlled_document": str(DOCUMENT_ID),
                "document_global_id": str(DOCUMENT_ID),
                "relationship_kind": "gate",
                "project_reference_type": None,
                "target_source_system": None,
                "target_reference_global_id": None,
                "target_identity": "af04c815-6a92-4db2-a0dd-1b2f7771c2f1",
                "target_version": 1,
                "target_snapshot": target_snapshot,
                "snapshot_hash": self.domain.sha256_json(target_snapshot),
                "optimistic_version": 1,
                "created_by_user_id": "engineer@example.invalid",
                "created_at": NOW,
                "request_id": "request-relationship-001",
                "trace_id": "trace-relationship-001",
            }
        )
        value.before_validate()
        value.validate()
        self.assertEqual(len(value.relationship_key), 64)
        invalid = clone(value)
        invalid._previous = None
        invalid.relationship_kind = "doctype"
        invalid.before_validate()
        with self.assertRaises(self.ValidationError):
            invalid.validate()

    def lock_event(
        self,
        *,
        event_id: UUID,
        event_type: str,
        lock_version: int,
        actor: str,
        occurred_at: datetime,
        reason: str | None,
        prior_event_id: UUID | None = None,
    ) -> StubDocument:
        snapshot = {
            "schemaVersion": 1,
            "globalId": str(event_id),
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "documentGlobalId": str(DOCUMENT_ID),
            "lockGlobalId": str(LOCK_ID),
            "lockVersion": lock_version,
            "eventType": event_type,
            "holderUserId": "engineer@example.invalid",
            "acquiredAt": NOW.isoformat().replace("+00:00", "Z"),
            "expiresAt": (NOW + timedelta(minutes=30))
            .isoformat()
            .replace("+00:00", "Z"),
            "actorUserId": actor,
            "occurredAt": occurred_at.isoformat().replace("+00:00", "Z"),
            "priorEventGlobalId": (str(prior_event_id) if prior_event_id else None),
            "closureReason": reason,
            "requestId": f"request-lock-{event_type}-001",
            "traceId": f"trace-lock-{event_type}-001",
        }
        return self.LockEvent(
            {
                "doctype": "NPI Document Lock Event",
                "name": str(event_id),
                "global_id": str(event_id),
                "event_key": f"{LOCK_ID}:{lock_version}",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "controlled_document": str(DOCUMENT_ID),
                "document_global_id": str(DOCUMENT_ID),
                "lock_global_id": str(LOCK_ID),
                "lock_version": lock_version,
                "event_type": event_type,
                "holder_user_id": "engineer@example.invalid",
                "acquired_at": NOW,
                "expires_at": NOW + timedelta(minutes=30),
                "actor_user_id": actor,
                "occurred_at": occurred_at,
                "prior_event_global_id": (
                    str(prior_event_id) if prior_event_id else None
                ),
                "closure_reason": reason,
                "request_id": f"request-lock-{event_type}-001",
                "trace_id": f"trace-lock-{event_type}-001",
                "event_snapshot": snapshot,
                "snapshot_hash": self.domain.sha256_json(snapshot),
            }
        )

    def test_lock_history_is_append_only_and_preserves_holder(self) -> None:
        value = self.lock_event(
            event_id=ACQUIRE_EVENT_ID,
            event_type="acquired",
            lock_version=1,
            actor="engineer@example.invalid",
            occurred_at=NOW,
            reason=None,
        )
        value.before_validate()
        value.validate()
        recovered = self.lock_event(
            event_id=UUID("4596dc6a-71bd-46cd-adfc-3017a90a5fb7"),
            event_type="recovered",
            lock_version=2,
            actor="Administrator",
            occurred_at=NOW + timedelta(minutes=5),
            reason="Abandoned editing session.",
            prior_event_id=ACQUIRE_EVENT_ID,
        )
        recovered.before_validate()
        recovered.validate()
        self.assertEqual(recovered.holder_user_id, "engineer@example.invalid")
        self.assertNotEqual(value.global_id, recovered.global_id)
        changed = clone(value)
        changed._previous = clone(value)
        changed.holder_user_id = "other@example.invalid"
        changed.before_validate()
        with self.assertRaises(self.PermissionError):
            changed.validate()

    def test_share_grant_never_produces_external_retrieval_authority(self) -> None:
        grant_id = UUID("5f9eddd0-305b-4a9c-b388-fe51650e1779")
        label = "Synthetic customer review"
        label_hash = hashlib.sha256(label.casefold().encode("utf-8")).hexdigest()
        grant_snapshot = {
            "schemaVersion": 1,
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "documentGlobalId": str(DOCUMENT_ID),
            "documentRevisionGlobalId": str(REVISION_ID),
            "documentRevisionSnapshotHash": "a" * 64,
            "revisionFileGlobalId": str(REVISION_FILE_ID),
            "revisionFileSnapshotHash": "e" * 64,
            "fileRevisionGlobalId": str(FILE_REVISION_ID),
            "shareLabelHash": label_hash,
            "expiresAt": (NOW + timedelta(days=7)).isoformat().replace("+00:00", "Z"),
            "retrievalState": "unavailable",
            "retrievalReasonCode": "external_access_policy_unavailable",
            "createdByUserId": "engineer@example.invalid",
            "createdAt": NOW.isoformat().replace("+00:00", "Z"),
            "requestId": "request-share-grant-001",
            "traceId": "trace-share-grant-001",
        }
        value = self.ShareGrant(
            {
                "doctype": "NPI Document Share Grant",
                "name": str(grant_id),
                "global_id": str(grant_id),
                "grant_key": "",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(DOCUMENT_ID),
                "document_revision_global_id": str(REVISION_ID),
                "document_revision_snapshot_hash": "a" * 64,
                "revision_file_global_id": str(REVISION_FILE_ID),
                "revision_file_snapshot_hash": "e" * 64,
                "file_revision_global_id": str(FILE_REVISION_ID),
                "share_label": label,
                "share_label_hash": label_hash,
                "expires_at": NOW + timedelta(days=7),
                "share_state": "prepared",
                "retrieval_state": "unavailable",
                "retrieval_reason_code": "external_access_policy_unavailable",
                "grant_snapshot": grant_snapshot,
                "snapshot_hash": self.domain.sha256_json(grant_snapshot),
                "closed_at": None,
                "closed_by_user_id": None,
                "closure_reason": None,
                "optimistic_version": 1,
                "created_by_user_id": "engineer@example.invalid",
                "created_at": NOW,
                "request_id": "request-share-grant-001",
                "trace_id": "trace-share-grant-001",
            }
        )
        value.before_validate()
        value.validate()
        self.assertEqual(value.retrieval_state, "unavailable")
        unsafe = clone(value)
        unsafe._previous = None
        unsafe.retrieval_state = "available"
        unsafe.before_validate()
        with self.assertRaises(self.ValidationError):
            unsafe.validate()
        revoked = clone(value)
        revoked._previous = clone(value)
        revoked.share_state = "revoked"
        revoked.closed_at = NOW + timedelta(hours=1)
        revoked.closed_by_user_id = "Administrator"
        revoked.closure_reason = "Synthetic revocation."
        revoked.optimistic_version = 2
        revoked.before_validate()
        revoked.validate()
        self.assertEqual(revoked.share_state, "revoked")

    def test_actor_scoped_receipt_seals_once(self) -> None:
        record_id = UUID("8ac881d8-e1fe-4a4b-836b-966ec4f29811")
        value = self.Idempotency(
            {
                "doctype": "NPI Document Command Idempotency",
                "name": str(record_id),
                "record_id": str(record_id),
                "actor": "engineer@example.invalid",
                "tenant_id": TENANT_ID,
                "project_global_id": str(PROJECT_ID),
                "document_global_id": None,
                "operation": "document.create",
                "actor_key_hash": "c" * 64,
                "payload_hash": "d" * 64,
                "request_id": "request-document-create-001",
                "trace_id": "trace-document-create-001",
                "created_at": NOW,
                "response_snapshot": {},
                "response_sealed": 0,
            }
        )
        value.before_validate()
        value.validate()
        sealed = clone(value)
        sealed._previous = clone(value)
        sealed.response_snapshot = {"status": 201, "documentId": str(DOCUMENT_ID)}
        sealed.response_sealed = 1
        sealed.before_validate()
        sealed.validate()
        replay = clone(sealed)
        replay._previous = clone(sealed)
        replay.before_validate()
        with self.assertRaises(self.PermissionError):
            replay.validate()

    def test_denied_delete_is_audited_after_transaction_rollback(self) -> None:
        value = self.revision()
        with self.assertRaises(self.PermissionError):
            value.on_trash()
        self.assertEqual(self.audit_inserts, [])
        self.frappe.db.rollback()
        self.assertEqual(len(self.audit_inserts), 1)
        self.assertEqual(
            self.audit_inserts[0]["operation"],
            "document.history.delete_attempt",
        )
        self.assertEqual(self.audit_inserts[0]["result"], "denied")
        self.assertEqual(
            self.transaction_events,
            ["rollback", "audit_insert", "commit"],
        )


if __name__ == "__main__":
    unittest.main()
