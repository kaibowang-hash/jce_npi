from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.documents.domain import (  # noqa: E402
    CapabilityState,
    ConnectorState,
    DocumentFileRole,
    DocumentLockConflict,
    DocumentLockState,
    DocumentPolicyState,
    DocumentPolicyUnavailable,
    DocumentPolicyVersion,
    DocumentRelationshipKind,
    DocumentRevisionState,
    DocumentTypeRule,
    DocumentVersionConflict,
    FileRevisionSnapshot,
    FileScanState,
    PreviewMode,
    RequestValidationFailed,
    acquire_document_lock,
    append_document_revision,
    build_document_relationship,
    command_payload_hash,
    create_controlled_document,
    file_capabilities,
    observe_upload,
    recover_document_lock,
    release_document_lock,
    validate_file_name,
)


POLICY_ID = UUID("83cdca19-f649-4a18-8a5b-9d263d97a911")
POLICY_VERSION_ID = UUID("44119863-2738-4674-8889-5f822475be57")
PROJECT_ID = UUID("ee7193f7-a704-4ed3-9ac0-85c2b1b45184")
DOCUMENT_ID = UUID("927466bd-a55d-48a1-9ddb-637e4ccb88c0")
LOCK_ID = UUID("6e38c507-d2cc-4f39-95b0-cd62d75d14dc")
REVISION_ID = UUID("66997315-516a-4a5d-800b-0933f70a1e7d")
REVISION_FILE_ID = UUID("2f4f7899-0fb4-483e-8660-e0ff79c09584")
FILE_DOCUMENT_ID = UUID("7b8942df-0a2f-4712-b4fd-71840b0937a0")
FILE_REVISION_ID = UUID("56b90190-26c4-4ba6-b9e4-6495347621c9")
NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def policy(
    *,
    state: DocumentPolicyState = DocumentPolicyState.PUBLISHED,
    snapshot_hash: str = "",
    allowed_mime_types: tuple[str, ...] = (
        "application/pdf",
        "image/png",
        "application/octet-stream",
    ),
    preview_mime_types: tuple[str, ...] = (
        "application/pdf",
        "image/png",
    ),
) -> DocumentPolicyVersion:
    return DocumentPolicyVersion(
        global_id=POLICY_VERSION_ID,
        policy_global_id=POLICY_ID,
        policy_key="synthetic_document_policy",
        policy_version=1,
        title="Synthetic document policy",
        state=state,
        document_types=(
            DocumentTypeRule(
                key="drawing",
                prefix="SYN-DWG",
                title_source="Drawing",
            ),
            DocumentTypeRule(
                key="specification",
                prefix="SYN-SPEC",
                title_source="Specification",
            ),
        ),
        confidentiality_keys=("project_internal", "customer_confidential"),
        allowed_mime_types=allowed_mime_types,
        preview_mime_types=preview_mime_types,
        maximum_file_bytes=1_048_576,
        lock_lease_minutes=30,
        snapshot_hash=snapshot_hash,
    )


def document():
    selected = policy()
    return create_controlled_document(
        document_id=DOCUMENT_ID,
        tenant_id="TENANT-A",
        project_id=PROJECT_ID,
        policy=selected,
        document_type_key="drawing",
        title="Synthetic design drawing",
        confidentiality_key="customer_confidential",
    )


def clean_file(
    *,
    mime_type: str = "application/pdf",
    scan_state: FileScanState = FileScanState.CLEAN,
) -> FileRevisionSnapshot:
    return FileRevisionSnapshot(
        global_id=FILE_REVISION_ID,
        file_document_global_id=FILE_DOCUMENT_ID,
        file_revision=1,
        optimistic_version=2,
        file_name="synthetic-drawing.pdf",
        mime_type=mime_type,
        size_bytes=20,
        sha256="a" * 64,
        scan_state=scan_state,
        frappe_file_id="synthetic-file-id",
        frappe_content_hash="b" * 32,
        is_private=True,
        released=False,
        scan_observed_at=(NOW if scan_state is not FileScanState.PENDING else None),
    )


class Phase5DocumentDomainTest(unittest.TestCase):
    def test_policy_snapshot_is_deterministic_and_exact(self) -> None:
        left = policy()
        right = policy()
        self.assertEqual(left.snapshot_hash, right.snapshot_hash)
        self.assertEqual(left.reference.snapshot_hash, left.snapshot_hash)
        with self.assertRaises(RequestValidationFailed):
            policy(snapshot_hash="f" * 64)

    def test_policy_rejects_duplicate_rules_and_unsupported_preview(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(
                policy(),
                document_types=(
                    DocumentTypeRule("drawing", "SYN-DWG", "Drawing"),
                    DocumentTypeRule("drawing", "SYN-ALT", "Drawing"),
                ),
                snapshot_hash="",
            )
        with self.assertRaises(RequestValidationFailed):
            policy(
                allowed_mime_types=("application/pdf", "application/msword"),
                preview_mime_types=("application/msword",),
            )

    def test_draft_policy_cannot_create_document(self) -> None:
        with self.assertRaises(DocumentPolicyUnavailable):
            create_controlled_document(
                document_id=DOCUMENT_ID,
                tenant_id="TENANT-A",
                project_id=PROJECT_ID,
                policy=policy(state=DocumentPolicyState.DRAFT),
                document_type_key="drawing",
                title="Synthetic design drawing",
                confidentiality_key="project_internal",
            )

    def test_document_number_is_server_derived_and_policy_scoped(self) -> None:
        value = document()
        self.assertEqual(value.document_number, "SYN-DWG-927466BDA55D")
        self.assertEqual(len(value.document_number_key), 64)
        self.assertEqual(value.version, 1)
        self.assertIsNone(value.current_revision_id)
        self.assertIsNone(value.current_lock_id)

    def test_document_rejects_unknown_type_and_confidentiality(self) -> None:
        values = {
            "document_id": DOCUMENT_ID,
            "tenant_id": "TENANT-A",
            "project_id": PROJECT_ID,
            "policy": policy(),
            "document_type_key": "drawing",
            "title": "Synthetic design drawing",
            "confidentiality_key": "project_internal",
        }
        with self.assertRaises(RequestValidationFailed):
            create_controlled_document(**{**values, "document_type_key": "cad"})
        with self.assertRaises(RequestValidationFailed):
            create_controlled_document(**{**values, "confidentiality_key": "public"})

    def test_lock_acquisition_release_and_recovery_preserve_history(self) -> None:
        acquired = acquire_document_lock(
            document(),
            None,
            lock_id=LOCK_ID,
            actor="engineer@example.invalid",
            now=NOW,
            lease_minutes=30,
        )
        self.assertEqual(acquired.document.version, 2)
        self.assertEqual(acquired.active_lock.state, DocumentLockState.ACTIVE)
        self.assertEqual(acquired.document.current_lock_id, LOCK_ID)
        self.assertIsNone(acquired.expired_lock)

        released_document, released = release_document_lock(
            acquired.document,
            acquired.active_lock,
            actor="engineer@example.invalid",
            now=NOW + timedelta(minutes=5),
        )
        self.assertEqual(released_document.version, 3)
        self.assertIsNone(released_document.current_lock_id)
        self.assertEqual(released.state, DocumentLockState.RELEASED)
        self.assertEqual(released.version, 2)
        self.assertEqual(released.holder_user_id, "engineer@example.invalid")

        second = acquire_document_lock(
            released_document,
            None,
            lock_id=UUID("bb88d24a-5106-421c-9d56-8d794fcbf2bd"),
            actor="engineer@example.invalid",
            now=NOW + timedelta(minutes=6),
            lease_minutes=30,
        )
        recovered_document, recovered = recover_document_lock(
            second.document,
            second.active_lock,
            actor="Administrator",
            reason="Synthetic recovery after an abandoned editing session.",
            now=NOW + timedelta(minutes=7),
        )
        self.assertIsNone(recovered_document.current_lock_id)
        self.assertEqual(recovered.state, DocumentLockState.RECOVERED)
        self.assertEqual(recovered.closed_by, "Administrator")
        self.assertIn("abandoned", recovered.reason or "")

    def test_active_lock_conflict_and_wrong_holder_fail_closed(self) -> None:
        acquired = acquire_document_lock(
            document(),
            None,
            lock_id=LOCK_ID,
            actor="engineer@example.invalid",
            now=NOW,
            lease_minutes=30,
        )
        with self.assertRaises(DocumentLockConflict):
            acquire_document_lock(
                acquired.document,
                acquired.active_lock,
                lock_id=UUID("95e6c025-613f-4df4-92b2-b7ca8cb63888"),
                actor="other@example.invalid",
                now=NOW + timedelta(minutes=1),
                lease_minutes=30,
            )
        with self.assertRaises(DocumentLockConflict):
            release_document_lock(
                acquired.document,
                acquired.active_lock,
                actor="other@example.invalid",
                now=NOW + timedelta(minutes=2),
            )
        with self.assertRaises(DocumentLockConflict):
            release_document_lock(
                acquired.document,
                acquired.active_lock,
                actor="engineer@example.invalid",
                now=NOW + timedelta(minutes=31),
            )

    def test_expired_lock_is_closed_before_new_lock(self) -> None:
        acquired = acquire_document_lock(
            document(),
            None,
            lock_id=LOCK_ID,
            actor="first@example.invalid",
            now=NOW,
            lease_minutes=10,
        )
        replacement = acquire_document_lock(
            acquired.document,
            acquired.active_lock,
            lock_id=UUID("7538ce3d-1285-493a-9cfa-1bde77704047"),
            actor="second@example.invalid",
            now=NOW + timedelta(minutes=11),
            lease_minutes=20,
        )
        self.assertIsNotNone(replacement.expired_lock)
        assert replacement.expired_lock is not None
        self.assertEqual(replacement.expired_lock.state, DocumentLockState.EXPIRED)
        self.assertEqual(
            replacement.active_lock.holder_user_id, "second@example.invalid"
        )

    def test_upload_observation_uses_bytes_and_rejects_paths_or_policy_mismatch(
        self,
    ) -> None:
        content = b"%PDF-1.7\nsynthetic"
        observed = observe_upload("drawing.pdf", content, policy())
        self.assertEqual(observed.mime_type, "application/pdf")
        self.assertEqual(observed.size_bytes, len(content))
        self.assertEqual(len(observed.sha256), 64)
        self.assertEqual(len(observed.frappe_content_hash), 32)
        for unsafe in ("../drawing.pdf", "folder/drawing.pdf", "a\r\n.pdf"):
            with self.subTest(unsafe=unsafe), self.assertRaises(
                RequestValidationFailed
            ):
                validate_file_name(unsafe)
        with self.assertRaises(RequestValidationFailed):
            observe_upload(
                "macro.doc",
                b"not a supported document",
                policy(
                    allowed_mime_types=("application/pdf",),
                    preview_mime_types=("application/pdf",),
                ),
            )
        with self.assertRaises(RequestValidationFailed):
            observe_upload("drawing.bin", content, policy())

    def test_first_revision_is_immutable_draft_with_distinct_file_identity(
        self,
    ) -> None:
        acquired = acquire_document_lock(
            document(),
            None,
            lock_id=LOCK_ID,
            actor="engineer@example.invalid",
            now=NOW,
            lease_minutes=30,
        )
        appended = append_document_revision(
            acquired.document,
            acquired.active_lock,
            clean_file(scan_state=FileScanState.PENDING),
            display_file_name="synthetic drawing.pdf",
            revision_id=REVISION_ID,
            revision_file_id=REVISION_FILE_ID,
            actor="engineer@example.invalid",
            now=NOW + timedelta(minutes=1),
            major=1,
            minor=0,
            reason="Initial synthetic design revision.",
            effective_date=None,
            predecessor_revision_id=None,
            request_id="request-revision-001",
            trace_id="trace-revision-001",
        )
        self.assertEqual(appended.document.current_revision_id, REVISION_ID)
        self.assertEqual(appended.document.version, 3)
        self.assertEqual(appended.revision.state, DocumentRevisionState.DRAFT)
        self.assertEqual(appended.revision.version, 1)
        self.assertEqual(appended.file.role, DocumentFileRole.PRIMARY)
        self.assertEqual(appended.file.file_revision.global_id, FILE_REVISION_ID)
        self.assertNotEqual(
            appended.file.file_revision.file_document_global_id,
            appended.revision.document_global_id,
        )
        self.assertEqual(appended.file.connector_state, ConnectorState.UNAVAILABLE)

    def test_successor_requires_exact_current_predecessor_and_later_version(
        self,
    ) -> None:
        acquired = acquire_document_lock(
            document(),
            None,
            lock_id=LOCK_ID,
            actor="engineer@example.invalid",
            now=NOW,
            lease_minutes=30,
        )
        first = append_document_revision(
            acquired.document,
            acquired.active_lock,
            clean_file(),
            display_file_name="synthetic drawing.pdf",
            revision_id=REVISION_ID,
            revision_file_id=REVISION_FILE_ID,
            actor="engineer@example.invalid",
            now=NOW + timedelta(minutes=1),
            major=1,
            minor=0,
            reason="Initial synthetic design revision.",
            effective_date=date(2026, 8, 1),
            predecessor_revision_id=None,
            request_id="request-revision-001",
            trace_id="trace-revision-001",
        )
        lock_for_updated_document = replace(
            acquired.active_lock,
            version=acquired.active_lock.version,
        )
        with self.assertRaises(DocumentVersionConflict):
            append_document_revision(
                first.document,
                lock_for_updated_document,
                replace(
                    clean_file(),
                    global_id=UUID("bd696f58-6170-475e-a543-7663227cfc08"),
                ),
                display_file_name="synthetic drawing.pdf",
                revision_id=UUID("e6eff050-0513-425a-9ee2-bac0f4098a85"),
                revision_file_id=UUID("8e49d6c4-6081-47ea-a159-3d1439f7a1ad"),
                actor="engineer@example.invalid",
                now=NOW + timedelta(minutes=2),
                major=1,
                minor=1,
                reason="Synthetic update.",
                effective_date=None,
                predecessor_revision_id=UUID("cf0ba819-b85e-4bcb-bcb3-8321800202ea"),
                request_id="request-revision-002",
                trace_id="trace-revision-002",
            )
        with self.assertRaises(RequestValidationFailed):
            append_document_revision(
                first.document,
                lock_for_updated_document,
                replace(
                    clean_file(),
                    global_id=UUID("bd696f58-6170-475e-a543-7663227cfc08"),
                ),
                display_file_name="synthetic drawing.pdf",
                revision_id=UUID("e6eff050-0513-425a-9ee2-bac0f4098a85"),
                revision_file_id=UUID("8e49d6c4-6081-47ea-a159-3d1439f7a1ad"),
                actor="engineer@example.invalid",
                now=NOW + timedelta(minutes=2),
                major=1,
                minor=0,
                reason="Synthetic update.",
                effective_date=None,
                predecessor_revision_id=REVISION_ID,
                request_id="request-revision-002",
                trace_id="trace-revision-002",
            )

    def test_relationship_identity_is_typed_and_project_scoped(self) -> None:
        value = build_document_relationship(
            relationship_id=UUID("41c0cdd9-9919-4ead-91f7-d1f6d625e008"),
            document=document(),
            kind=DocumentRelationshipKind.GATE,
            target_identity="af04c815-6a92-4db2-a0dd-1b2f7771c2f1",
            target_version=2,
        )
        self.assertEqual(value.kind, DocumentRelationshipKind.GATE)
        self.assertEqual(value.project_global_id, PROJECT_ID)
        self.assertEqual(len(value.relationship_key), 64)
        with self.assertRaises(RequestValidationFailed):
            build_document_relationship(
                relationship_id=UUID("41c0cdd9-9919-4ead-91f7-d1f6d625e008"),
                document=document(),
                kind=DocumentRelationshipKind.WBS_ITEM,
                target_identity="File",
                target_version=1,
            )

    def test_capabilities_fail_closed_for_scan_integrity_and_permission(self) -> None:
        available = file_capabilities(
            policy=policy(),
            file_revision=clean_file(),
            live_identity_matches=True,
            live_sha256_matches=True,
            preview_authorized=True,
            download_authorized=True,
        )
        self.assertEqual(available.preview.state, CapabilityState.AVAILABLE)
        self.assertEqual(available.preview.mode, PreviewMode.NATIVE_PDF)
        self.assertEqual(available.download.state, CapabilityState.AVAILABLE)
        self.assertEqual(
            available.external_retrieval.state,
            CapabilityState.UNAVAILABLE,
        )
        self.assertEqual(available.connector.state, CapabilityState.UNAVAILABLE)

        for snapshot, identity, sha, authorized, reason in (
            (
                clean_file(scan_state=FileScanState.PENDING),
                True,
                True,
                True,
                "scan_pending",
            ),
            (clean_file(), False, True, True, "file_identity_drift"),
            (clean_file(), True, False, True, "file_identity_drift"),
            (clean_file(), True, True, False, "permission_required"),
        ):
            with self.subTest(reason=reason):
                value = file_capabilities(
                    policy=policy(),
                    file_revision=snapshot,
                    live_identity_matches=identity,
                    live_sha256_matches=sha,
                    preview_authorized=authorized,
                    download_authorized=authorized,
                )
                self.assertEqual(value.download.state, CapabilityState.BLOCKED)
                self.assertEqual(value.download.reason_code, reason)

    def test_clean_unsupported_format_has_download_fallback_without_preview(
        self,
    ) -> None:
        value = file_capabilities(
            policy=policy(),
            file_revision=clean_file(mime_type="application/octet-stream"),
            live_identity_matches=True,
            live_sha256_matches=True,
            preview_authorized=True,
            download_authorized=True,
        )
        self.assertEqual(value.download.state, CapabilityState.AVAILABLE)
        self.assertEqual(value.preview.state, CapabilityState.UNAVAILABLE)
        self.assertEqual(value.preview.mode, PreviewMode.NONE)

    def test_preview_and_download_authorities_are_independent(self) -> None:
        value = file_capabilities(
            policy=policy(),
            file_revision=clean_file(),
            live_identity_matches=True,
            live_sha256_matches=True,
            preview_authorized=False,
            download_authorized=True,
        )
        self.assertEqual(value.preview.state, CapabilityState.BLOCKED)
        self.assertEqual(value.download.state, CapabilityState.AVAILABLE)

    def test_command_payload_hash_binds_operation_actor_scope_and_file(self) -> None:
        base = {
            "operation": "document.revision.create",
            "actor": "engineer@example.invalid",
            "tenant_id": "TENANT-A",
            "project_id": PROJECT_ID,
            "document_id": DOCUMENT_ID,
            "payload": {"major": 1, "minor": 0},
            "file_sha256": "a" * 64,
        }
        first = command_payload_hash(**base)
        self.assertEqual(first, command_payload_hash(**base))
        for change in (
            {"actor": "other@example.invalid"},
            {"operation": "document.lock.acquire"},
            {"file_sha256": "b" * 64},
            {"payload": {"major": 1, "minor": 1}},
        ):
            with self.subTest(change=change):
                self.assertNotEqual(first, command_payload_hash(**{**base, **change}))


if __name__ == "__main__":
    unittest.main()
