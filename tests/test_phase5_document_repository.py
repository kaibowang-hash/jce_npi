from __future__ import annotations

import ast
import base64
import importlib
import sys
import tempfile
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "npi_core" / "npi_core" / "documents" / "frappe_repository.py"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class CallbackQueue:
    def __init__(self) -> None:
        self.functions: list[Any] = []

    def add(self, function) -> None:
        self.functions.append(function)


class Phase5DocumentRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.utils",
        "frappe.utils.file_manager",
        "npi_core.documents.frappe_repository",
        "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.temp = tempfile.TemporaryDirectory()
        self.site_path = Path(self.temp.name)
        (self.site_path / "private" / "files").mkdir(parents=True)
        self.remaining_file: str | None = None

        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.conf = AttrDict(
            encryption_key=base64.urlsafe_b64encode(b"k" * 32).decode("ascii")
        )
        frappe.local = types.SimpleNamespace(conf=frappe.conf)
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.UniqueValidationError = type(
            "UniqueValidationError",
            (Exception,),
            {},
        )
        frappe.DuplicateEntryError = type(
            "DuplicateEntryError",
            (Exception,),
            {},
        )
        frappe.get_site_path = lambda *parts: str(self.site_path.joinpath(*parts))

        class StubDatabase:
            def __init__(database_self) -> None:
                database_self.after_rollback = CallbackQueue()
                database_self.rollback_count = 0

            def get_value(database_self, doctype, filters, fieldname, **_kwargs):
                if (
                    doctype == "File"
                    and isinstance(filters, dict)
                    and fieldname == "name"
                ):
                    return self.remaining_file
                raise AssertionError((doctype, filters, fieldname))

            def rollback(database_self) -> None:
                database_self.rollback_count += 1

        frappe.db = StubDatabase()
        sys.modules["frappe"] = frappe
        file_revision = types.ModuleType(
            "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision"
        )
        file_revision.file_revision_source_snapshot = lambda document: document.snapshot
        file_revision.has_live_private_file_identity = lambda _document: True
        sys.modules[file_revision.__name__] = file_revision
        self.frappe = frappe
        self.repository = importlib.import_module(
            "npi_core.documents.frappe_repository"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def test_signed_cursor_is_canonical_query_bound_and_tamper_evident(self) -> None:
        global_id = "2e96f421-5872-4c96-a0dd-718d5c970a21"
        query_hash = "a" * 64
        cursor = self.repository._encode_cursor(
            global_id,
            query_hash=query_hash,
        )
        self.assertEqual(
            self.repository._decode_cursor(
                cursor,
                expected_query_hash=query_hash,
            ),
            global_id,
        )
        for candidate, expected_hash in (
            (cursor[:-1] + ("A" if cursor[-1] != "A" else "B"), query_hash),
            (cursor, "b" * 64),
            ("not-a-cursor", query_hash),
        ):
            with self.subTest(candidate=candidate, expected_hash=expected_hash):
                with self.assertRaises(
                    self.repository.RequestValidationFailed
                ) as raised:
                    self.repository._decode_cursor(
                        candidate,
                        expected_query_hash=expected_hash,
                    )
                self.assertEqual(
                    raised.exception.field_errors[0]["path"],
                    "cursor",
                )

    def test_file_metadata_response_is_url_and_storage_identity_free(self) -> None:
        document = types.SimpleNamespace(
            snapshot={
                "globalId": "590b332e-1ec4-44d8-8778-8b84eaf079bc",
                "documentGlobalId": "62d6ac02-b85f-4ae0-a522-953c4ebc2de4",
                "revision": 1,
                "fileOptimisticVersion": 2,
                "fileName": "drawing.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 128,
                "sha256": "a" * 64,
                "scanState": "clean",
                "scanObservedAt": "2026-07-25T12:00:00Z",
                "isPrivate": True,
                "released": False,
                "fileId": "FILE-0001",
                "fileContentHash": "b" * 32,
            }
        )
        response = self.repository._file_metadata_response(document)
        self.assertEqual(response["fileName"], "drawing.pdf")
        serialized = str(response)
        self.assertNotIn("fileId", serialized)
        self.assertNotIn("fileContentHash", serialized)
        self.assertNotIn("file_url", serialized)
        self.assertNotIn("/private/files/", serialized)
        renamed = self.repository._file_metadata_response(
            document,
            display_file_name="original drawing.pdf",
        )
        self.assertEqual(renamed["fileName"], "original drawing.pdf")

    def test_frozen_file_association_accepts_new_scanner_observation_version(
        self,
    ) -> None:
        file_revision_id = UUID("590b332e-1ec4-44d8-8778-8b84eaf079bc")
        file_document_id = UUID("62d6ac02-b85f-4ae0-a522-953c4ebc2de4")
        revision_id = UUID("c74bd8c6-1a36-4367-a43f-1a6cbfe3a9c8")
        association_id = UUID("77932078-9512-428e-b9d7-863303661059")
        project_id = UUID("2e96f421-5872-4c96-a0dd-718d5c970a21")
        document_id = UUID("a6bfd0bf-8ab3-4a92-b49e-818735db4f55")
        frozen_file = self.repository.FileRevisionSnapshot(
            global_id=file_revision_id,
            file_document_global_id=file_document_id,
            file_revision=1,
            optimistic_version=1,
            file_name="drawinga1b2c3.pdf",
            mime_type="application/pdf",
            size_bytes=128,
            sha256="a" * 64,
            scan_state=self.repository.FileScanState.PENDING,
            frappe_file_id="FILE-0001",
            frappe_content_hash="b" * 32,
            is_private=True,
            released=False,
        )
        frozen_association = self.repository.DocumentRevisionFile(
            global_id=association_id,
            document_revision_global_id=revision_id,
            file_revision=frozen_file,
            display_file_name="drawing.pdf",
            role=self.repository.DocumentFileRole.PRIMARY,
            provenance="manual_upload",
            connector_state=self.repository.ConnectorState.UNAVAILABLE,
            connector_reason_code="provider_not_configured",
        )
        project = types.SimpleNamespace(
            tenant_id="TENANT-A",
            global_id=str(project_id),
        )
        document = types.SimpleNamespace(global_id=str(document_id))
        revision = types.SimpleNamespace(global_id=str(revision_id))
        snapshot = {
            "schemaVersion": 1,
            "tenantId": project.tenant_id,
            "projectGlobalId": str(project_id),
            "documentGlobalId": str(document_id),
            "association": frozen_association.canonical_dict(),
        }
        association = types.SimpleNamespace(
            global_id=str(association_id),
            tenant_id=project.tenant_id,
            project_global_id=str(project_id),
            document_global_id=str(document_id),
            document_revision=str(revision_id),
            document_revision_global_id=str(revision_id),
            file_revision=str(file_revision_id),
            file_revision_global_id=str(file_revision_id),
            file_document_global_id=str(file_document_id),
            file_revision_number=1,
            file_optimistic_version=1,
            display_file_name="drawing.pdf",
            frappe_file_id="FILE-0001",
            frappe_content_hash="b" * 32,
            file_name="drawinga1b2c3.pdf",
            mime_type="application/pdf",
            size_bytes=128,
            sha256="a" * 64,
            scan_state="pending",
            scan_observed_at=None,
            is_private=1,
            released=0,
            file_role="primary",
            provenance="manual_upload",
            connector_state="unavailable",
            connector_reason_code="provider_not_configured",
            file_revision_source_snapshot=frozen_file.canonical_dict(),
            association_snapshot=snapshot,
            snapshot_hash=self.repository.sha256_json(snapshot),
        )
        live = types.SimpleNamespace(
            global_id=str(file_revision_id),
            tenant_id=project.tenant_id,
            project_global_id=str(project_id),
            document_global_id=str(file_document_id),
            revision=1,
            optimistic_version=2,
            frappe_file_id="FILE-0001",
            frappe_content_hash="b" * 32,
            file_name="drawinga1b2c3.pdf",
            mime_type="application/pdf",
            size_bytes=128,
            sha256="a" * 64,
            scan_state="clean",
            scan_observed_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
            is_private=1,
            released=0,
        )
        self.assertTrue(
            self.repository._association_matches_live_file(
                project,
                document,
                revision,
                association,
                live,
            )
        )
        live.sha256 = "c" * 64
        self.assertFalse(
            self.repository._association_matches_live_file(
                project,
                document,
                revision,
                association,
                live,
            )
        )

    def test_history_capabilities_never_materialize_binary_content(self) -> None:
        principal = self.repository.Principal(
            user_id="Administrator",
            roles=frozenset({"System Manager"}),
            tenant_id="TENANT-A",
        )
        adapter = self.repository.FrappeDocumentRepository(
            principal=principal,
            request_id="request-document-0001",
            trace_id="trace-document-0001",
        )
        file_revision = types.SimpleNamespace(
            global_id="590b332e-1ec4-44d8-8778-8b84eaf079bc",
            document_global_id="62d6ac02-b85f-4ae0-a522-953c4ebc2de4",
            revision=1,
            optimistic_version=2,
            file_name="drawing.pdf",
            mime_type="application/pdf",
            size_bytes=128,
            sha256="a" * 64,
            scan_state="clean",
            frappe_file_id="FILE-0001",
            frappe_content_hash="b" * 32,
            is_private=1,
            released=0,
            scan_observed_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        )
        self.frappe.get_doc = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("history must not read a File document or its content")
        )

        capability = adapter._history_capability_observation(
            types.SimpleNamespace(
                preview_mime_types=("application/pdf",),
            ),
            file_revision,
        )

        self.assertEqual(
            capability["integrity"],
            {
                "state": "unavailable",
                "reasonCode": "verification_required",
            },
        )
        self.assertEqual(
            capability["preview"],
            {
                "state": "unavailable",
                "reasonCode": "verification_required",
                "mode": "none",
            },
        )
        self.assertEqual(
            capability["download"],
            {
                "state": "unavailable",
                "reasonCode": "verification_required",
            },
        )

    def test_storage_capacity_uses_the_pinned_frappe_limit(self) -> None:
        frappe_utils = types.ModuleType("frappe.utils")
        file_manager = types.ModuleType("frappe.utils.file_manager")
        file_manager.get_max_file_size = lambda: 10
        sys.modules["frappe.utils"] = frappe_utils
        sys.modules["frappe.utils.file_manager"] = file_manager

        self.repository._require_storage_capacity(10)
        with self.assertRaises(self.repository.RequestValidationFailed) as raised:
            self.repository._require_storage_capacity(11)
        self.assertEqual(
            raised.exception.field_errors,
            [
                {
                    "path": "file",
                    "message": "The file exceeds the configured upload limit.",
                }
            ],
        )

    def test_idempotency_scope_and_duplicate_collisions_fail_without_rollback(
        self,
    ) -> None:
        principal = self.repository.Principal(
            user_id="Administrator",
            roles=frozenset({"System Manager"}),
            tenant_id="TENANT-A",
        )
        adapter = self.repository.FrappeDocumentRepository(
            principal=principal,
            request_id="request-document-0001",
            trace_id="trace-document-0001",
        )
        project = types.SimpleNamespace(
            tenant_id="TENANT-A",
            global_id="2e96f421-5872-4c96-a0dd-718d5c970a21",
        )
        self.frappe.db.get_value = lambda *_args, **_kwargs: AttrDict(
            actor="Administrator",
            tenant_id="TENANT-A",
            project_global_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
            document_global_id=None,
            operation="document.create",
            payload_hash="a" * 64,
            response_snapshot={},
            response_sealed=1,
        )
        with self.assertRaises(self.repository.DocumentIdempotencyConflict):
            adapter._idempotency_replay(
                "b" * 64,
                "a" * 64,
                project=project,
                document_id=None,
                operation="document.create",
            )

        class DuplicateReceipt:
            def insert(receipt_self):
                raise self.frappe.DuplicateEntryError()

        self.frappe.get_doc = lambda *_args, **_kwargs: DuplicateReceipt()
        with self.assertRaises(self.repository.DocumentIdempotencyConflict):
            adapter._insert_idempotency(
                "b" * 64,
                "a" * 64,
                project=project,
                document_id=None,
                operation="document.create",
            )
        self.assertEqual(self.frappe.db.rollback_count, 0)

    def test_rollback_cleanup_is_bounded_and_preserves_referenced_content(self) -> None:
        path = self.site_path / "private" / "files" / "drawing.pdf"
        path.write_bytes(b"synthetic")
        document = types.SimpleNamespace(
            name="FILE-0001",
            file_url="/private/files/drawing.pdf",
        )
        self.repository._register_orphan_cleanup(document)
        callbacks = self.frappe.db.after_rollback.functions
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertFalse(path.exists())

        path.write_bytes(b"synthetic")
        self.remaining_file = "FILE-COMMITTED"
        self.repository._register_orphan_cleanup(document)
        self.frappe.db.after_rollback.functions[-1]()
        self.assertTrue(path.exists())

        self.remaining_file = None
        self.repository._register_orphan_cleanup(document)
        self.frappe.db.get_value = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic cleanup failure")
        )
        self.frappe.db.after_rollback.functions[-1]()
        self.assertTrue(path.exists())

        unsafe = types.SimpleNamespace(
            name="FILE-UNSAFE",
            file_url="/private/files/../outside.pdf",
        )
        with self.assertRaisesRegex(ValueError, "path is invalid"):
            self.repository._register_orphan_cleanup(unsafe)

    def test_controlled_write_scope_restores_all_flags(self) -> None:
        self.frappe.flags.npi_audit_append = "previous"
        with self.repository._controlled_document_write_scope():
            self.assertTrue(self.frappe.flags.npi_document_command_write)
            self.assertTrue(self.frappe.flags.npi_file_revision_command_write)
            self.assertTrue(self.frappe.flags.npi_audit_append)
        self.assertFalse(hasattr(self.frappe.flags, "npi_document_command_write"))
        self.assertFalse(hasattr(self.frappe.flags, "npi_file_revision_command_write"))
        self.assertEqual(self.frappe.flags.npi_audit_append, "previous")

    def test_lock_snapshot_binds_exact_request_trace_and_prior_event(self) -> None:
        lock_id = UUID("6e38c507-d2cc-4f39-95b0-cd62d75d14dc")
        event_id = UUID("ba94e31a-fe62-4c00-8aaf-c3e6dfbd3804")
        prior_id = UUID("c74bd8c6-1a36-4367-a43f-1a6cbfe3a9c8")
        project = types.SimpleNamespace(
            tenant_id="tenant-a",
            global_id="ee7193f7-a704-4ed3-9ac0-85c2b1b45184",
        )
        document = types.SimpleNamespace(
            global_id="927466bd-a55d-48a1-9ddb-637e4ccb88c0"
        )
        lock = self.repository.DocumentEditLock(
            global_id=lock_id,
            document_global_id=UUID(document.global_id),
            version=2,
            holder_user_id="engineer@example.invalid",
            acquired_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
            expires_at=datetime(2026, 7, 25, 12, 30, tzinfo=UTC),
            state=self.repository.DocumentLockState.RECOVERED,
            closed_at=datetime(2026, 7, 25, 12, 10, tzinfo=UTC),
            closed_by="Administrator",
            reason="Administrative recovery",
        )
        snapshot = self.repository._lock_event_snapshot(
            event_id=event_id,
            project=project,
            document=document,
            lock=lock,
            event_type="recovered",
            actor="Administrator",
            occurred_at=lock.closed_at,
            prior_event_id=prior_id,
            request_id="request-document-0001",
            trace_id="trace-document-0001",
        )
        self.assertEqual(snapshot["lockGlobalId"], str(lock_id))
        self.assertEqual(snapshot["priorEventGlobalId"], str(prior_id))
        self.assertEqual(snapshot["requestId"], "request-document-0001")
        self.assertEqual(snapshot["traceId"], "trace-document-0001")
        self.assertEqual(snapshot["closureReason"], "Administrative recovery")

    def test_checkout_stage_diagnostics_are_closed_sanitized_and_secondary(
        self,
    ) -> None:
        expected_codes = {
            "DOCUMENT_CHECKOUT_RECEIPT_INSERT",
            "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
            "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
            "DOCUMENT_CHECKOUT_AUDIT_APPEND",
            "DOCUMENT_CHECKOUT_RESPONSE_BUILD",
            "DOCUMENT_CHECKOUT_RECEIPT_SEAL",
        }
        self.assertEqual(
            self.repository._CHECKOUT_STAGE_DIAGNOSTIC_CODES,
            expected_codes,
        )
        error = self.frappe.UniqueValidationError(
            "password=controlled-fixture-password"
        )
        with patch("npi_core.api.record_safe_diagnostic") as record:
            self.repository._record_checkout_stage_failure(
                "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
                error,
                "trace-0123456789abcdef0123456789abcdef",
            )
            record.assert_called_once_with(
                code="DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
                title="NPI Document checkout stage failed",
                exception_type="UniqueValidationError",
                trace_id="trace-0123456789abcdef0123456789abcdef",
            )
            self.assertNotIn(
                "controlled-fixture-password",
                repr(record.call_args),
            )

            record.reset_mock()
            self.repository._record_checkout_stage_failure(
                "UNREVIEWED_CHECKOUT_STAGE",
                error,
                "trace-0123456789abcdef0123456789abcdef",
            )
            record.assert_not_called()

            self.repository._record_checkout_stage_failure(
                "DOCUMENT_CHECKOUT_RECEIPT_INSERT",
                self.repository.DocumentIdempotencyConflict(),
                "trace-0123456789abcdef0123456789abcdef",
            )
            record.assert_not_called()

            record.side_effect = RuntimeError("synthetic diagnostic failure")
            self.repository._record_checkout_stage_failure(
                "DOCUMENT_CHECKOUT_RECEIPT_SEAL",
                error,
                "trace-0123456789abcdef0123456789abcdef",
            )

    def test_checkout_has_one_diagnostic_for_each_authorized_stage(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        checkout = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "check_out"
        )
        checkout_source = ast.get_source_segment(source, checkout) or ""
        for stage_code in self.repository._CHECKOUT_STAGE_DIAGNOSTIC_CODES:
            with self.subTest(stage_code=stage_code):
                self.assertEqual(checkout_source.count(f'"{stage_code}"'), 1)
        self.assertEqual(
            checkout_source.count("_record_checkout_stage_failure("),
            len(self.repository._CHECKOUT_STAGE_DIAGNOSTIC_CODES),
        )
        self.assertEqual(
            checkout_source.count(
                "document_projection_validation_diagnostics(self.trace_id)"
            ),
            1,
        )
        self.assertEqual(
            checkout_source.count("record_projection_validation_fallback(error)"),
            1,
        )

    def test_revision_stage_diagnostics_are_closed_sanitized_and_secondary(
        self,
    ) -> None:
        expected_codes = {
            "DOCUMENT_REVISION_RECEIPT_INSERT",
            "DOCUMENT_REVISION_PRIVATE_FILE_SAVE",
            "DOCUMENT_REVISION_FILE_REVISION_INSERT",
            "DOCUMENT_REVISION_DOMAIN_APPEND",
            "DOCUMENT_REVISION_RECORD_INSERT",
            "DOCUMENT_REVISION_FILE_ASSOCIATION_INSERT",
            "DOCUMENT_REVISION_PROJECTION_SAVE",
            "DOCUMENT_REVISION_AUDIT_APPEND",
            "DOCUMENT_REVISION_RESPONSE_BUILD",
            "DOCUMENT_REVISION_RECEIPT_SEAL",
        }
        self.assertEqual(
            self.repository._REVISION_STAGE_DIAGNOSTIC_CODES,
            expected_codes,
        )
        error = RuntimeError("cookie=controlled-fixture-cookie")
        with patch("npi_core.api.record_safe_diagnostic") as record:
            self.repository._record_revision_stage_failure(
                "DOCUMENT_REVISION_PRIVATE_FILE_SAVE",
                error,
                "trace-0123456789abcdef0123456789abcdef",
            )
            record.assert_called_once_with(
                code="DOCUMENT_REVISION_PRIVATE_FILE_SAVE",
                title="NPI Document revision stage failed",
                exception_type="RuntimeError",
                trace_id="trace-0123456789abcdef0123456789abcdef",
            )
            self.assertNotIn("controlled-fixture-cookie", repr(record.call_args))

            record.reset_mock()
            self.repository._record_revision_stage_failure(
                "UNREVIEWED_REVISION_STAGE",
                error,
                "trace-0123456789abcdef0123456789abcdef",
            )
            record.assert_not_called()

            self.repository._record_revision_stage_failure(
                "DOCUMENT_REVISION_RECEIPT_INSERT",
                self.repository.DocumentIdempotencyConflict(),
                "trace-0123456789abcdef0123456789abcdef",
            )
            record.assert_not_called()

            record.side_effect = RuntimeError("synthetic diagnostic failure")
            self.repository._record_revision_stage_failure(
                "DOCUMENT_REVISION_RECEIPT_SEAL",
                error,
                "trace-0123456789abcdef0123456789abcdef",
            )

    def test_revision_has_one_diagnostic_for_each_authorized_stage_in_order(
        self,
    ) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        create_revision = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "create_revision"
        )
        revision_source = ast.get_source_segment(source, create_revision) or ""
        expected_order = (
            "DOCUMENT_REVISION_RECEIPT_INSERT",
            "DOCUMENT_REVISION_PRIVATE_FILE_SAVE",
            "DOCUMENT_REVISION_FILE_REVISION_INSERT",
            "DOCUMENT_REVISION_DOMAIN_APPEND",
            "DOCUMENT_REVISION_RECORD_INSERT",
            "DOCUMENT_REVISION_FILE_ASSOCIATION_INSERT",
            "DOCUMENT_REVISION_PROJECTION_SAVE",
            "DOCUMENT_REVISION_AUDIT_APPEND",
            "DOCUMENT_REVISION_RESPONSE_BUILD",
            "DOCUMENT_REVISION_RECEIPT_SEAL",
        )
        positions: list[int] = []
        for stage_code in expected_order:
            with self.subTest(stage_code=stage_code):
                self.assertEqual(revision_source.count(f'"{stage_code}"'), 1)
                positions.append(revision_source.index(f'"{stage_code}"'))
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(
            revision_source.count("_record_revision_stage_failure("),
            len(expected_order),
        )

    def test_repository_uses_public_frappe_apis_and_never_commits_content(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertNotIn("ignore_" "permissions", source)
        self.assertNotIn("frappe.db." "sql", source)
        self.assertNotIn(
            "/private/files/",
            source.replace(
                'file_url.startswith("/private/files/")',
                "",
            ),
        )
        commits = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
        ]
        self.assertFalse(commits)
        content = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "content"
        )
        content_source = ast.get_source_segment(source, content) or ""
        self.assertIn("_append_audit(", content_source)
        self.assertIn("_seal_idempotency(", content_source)
        self.assertNotIn("file_url", content_source)


if __name__ == "__main__":
    unittest.main()
