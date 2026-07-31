from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.controlled_evidence_validation import FILE_REVISION_COMMAND_FLAG
from npi_core.documents.domain import (
    CapabilityState,
    ConnectorState,
    ControlledDocument,
    DocumentEditLock,
    DocumentFileRole,
    DocumentIdempotencyConflict,
    DocumentLockConflict,
    DocumentLockState,
    DocumentNumberConflict,
    DocumentPolicyReference,
    DocumentPolicyState,
    DocumentPolicyUnavailable,
    DocumentPolicyVersion,
    DocumentRevisionFile,
    DocumentRelationshipKind,
    DocumentTypeRule,
    DocumentUnavailable,
    DocumentVersionConflict,
    FileRevisionSnapshot,
    FileScanState,
    acquire_document_lock,
    append_document_revision,
    build_document_relationship,
    canonical_json,
    command_payload_hash,
    create_controlled_document,
    file_capabilities,
    observe_upload,
    recover_document_lock,
    release_document_lock,
    sha256_json,
)
from npi_core.documents.frappe_validation import (
    DOCUMENT_COMMAND_FLAG,
    document_projection_validation_diagnostics,
    record_projection_validation_fallback,
)
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import (
    CursorSigningUnavailable,
    NpiProblem,
    RequestValidationFailed,
)
from npi_core.foundation.security import Principal
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    file_revision_source_snapshot,
    has_live_private_file_identity,
)
from npi_core.project_controls.terminal_guard import require_mutable_project


_MAX_DOCUMENTS = 1_000
_MAX_DOCUMENT_HISTORY = 256
_MAX_MEMBERS = 256
_MAX_POLICIES = 64
_CURSOR_VERSION = 1
_CURSOR_KEY_CONTEXT = b"npi-one:documents:list-cursor:v1"
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_CHECKOUT_STAGE_DIAGNOSTIC_CODES = frozenset(
    {
        "DOCUMENT_CHECKOUT_RECEIPT_INSERT",
        "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
        "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
        "DOCUMENT_CHECKOUT_AUDIT_APPEND",
        "DOCUMENT_CHECKOUT_RESPONSE_BUILD",
        "DOCUMENT_CHECKOUT_RECEIPT_SEAL",
    }
)


@dataclass(frozen=True, slots=True)
class DocumentCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class DocumentContentOutcome:
    content: bytes
    file_name: str
    mime_type: str
    disposition: str
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class _LockRecord:
    lock: DocumentEditLock
    acquisition_event_global_id: UUID


class FrappeDocumentRepository:
    """Frappe adapter for the bounded P5-01 controlled-document aggregate."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id

    def authorize_scope(
        self,
        project_id: UUID,
        document_id: UUID | None = None,
        *,
        administer: bool,
    ) -> bool:
        """Opaque preflight; command methods still lock and reauthorize."""
        project = _optional_doc("NPI Engineering Project", str(project_id))
        if project is None:
            return False
        permitted = (
            self._can_administer_project(project, project_id)
            if administer
            else self._can_view_project(project, project_id)
        )
        if not permitted:
            return False
        return bool(
            document_id is None
            or self._document_for_project(project, document_id) is not None
        )

    def list_documents(
        self,
        project_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        relationship_kind: str | None,
        target_identity: str | None,
        target_version: int | None,
        project_reference_type: str | None,
        target_source_system: str | None,
        target_reference_global_id: UUID | None,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        query_identity = {
            "projectId": str(project_id),
            "relationshipKind": relationship_kind,
            "targetIdentity": target_identity,
            "targetVersion": target_version,
            "projectReferenceType": project_reference_type,
            "targetSourceSystem": target_source_system,
            "targetReferenceGlobalId": (
                str(target_reference_global_id)
                if target_reference_global_id is not None
                else None
            ),
        }
        query_hash = sha256_json(query_identity)
        after_global_id = (
            _decode_cursor(cursor, expected_query_hash=query_hash)
            if cursor is not None
            else None
        )
        related_document_ids = self._related_document_ids(
            project,
            relationship_kind=relationship_kind,
            target_identity=target_identity,
            target_version=target_version,
            project_reference_type=project_reference_type,
            target_source_system=target_source_system,
            target_reference_global_id=target_reference_global_id,
        )
        if related_document_ids == ():
            documents: tuple[Any, ...] = ()
        else:
            filters: dict[str, object] = {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            }
            if after_global_id is not None:
                filters["global_id"] = [">", after_global_id]
            if related_document_ids is not None:
                filters["name"] = ["in", list(related_document_ids)]
            names = frappe.get_all(
                "NPI Controlled Document",
                filters=filters,
                pluck="name",
                order_by="global_id asc",
                limit_page_length=limit + 1,
            )
            documents = tuple(
                frappe.get_doc("NPI Controlled Document", str(name)) for name in names
            )
        has_more = len(documents) > limit
        page = documents[:limit]
        next_cursor = (
            _encode_cursor(
                str(page[-1].global_id),
                query_hash=query_hash,
            )
            if has_more and page
            else None
        )
        return {
            "project": _project_response(project),
            "permissions": self._permissions(),
            "policies": self._published_policy_options(project),
            "items": [self._document_summary(value) for value in page],
            "nextCursor": next_cursor,
        }

    def document_detail(
        self,
        project_id: UUID,
        document_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        document = self._document_for_project(project, document_id)
        if document is None:
            return None
        return self._detail_for(project, document)

    def create_document(
        self,
        project_id: UUID,
        *,
        idempotency_key: str,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        document_type_key: str,
        title: str,
        confidentiality_key: str,
        object_links: Sequence[Mapping[str, object]],
    ) -> DocumentCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "policyGlobalId": str(policy_global_id),
            "policyVersion": policy_version,
            "policySnapshotHash": policy_snapshot_hash,
            "documentTypeKey": document_type_key,
            "title": title,
            "confidentialityKey": confidentiality_key,
            "objectLinks": [dict(value) for value in object_links],
        }
        payload_hash = self._payload_hash(
            operation="document.create",
            project=project,
            document_id=None,
            payload=payload,
        )
        replay = self._idempotency_replay(
            idempotency_key,
            payload_hash,
            project=project,
            document_id=None,
            operation="document.create",
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        policy = self._load_exact_policy(
            project,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            snapshot_hash=policy_snapshot_hash,
        )
        document_id = uuid4()
        domain = create_controlled_document(
            document_id=document_id,
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            policy=policy,
            document_type_key=document_type_key,
            title=title,
            confidentiality_key=confidentiality_key,
        )
        created_at = datetime.now(UTC)
        with _controlled_document_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project=project,
                document_id=None,
                operation="document.create",
            )
            if isinstance(receipt, dict):
                return DocumentCommandOutcome(receipt, replayed=True)
            try:
                document = frappe.get_doc(
                    {
                        "doctype": "NPI Controlled Document",
                        "global_id": str(domain.global_id),
                        "tenant_id": domain.tenant_id,
                        "project_global_id": str(domain.project_global_id),
                        "policy_global_id": str(domain.policy_ref.global_id),
                        "policy_version": domain.policy_ref.version,
                        "policy_snapshot_hash": domain.policy_ref.snapshot_hash,
                        "document_number": domain.document_number,
                        "document_number_key": domain.document_number_key,
                        "document_type_key": domain.document_type_key,
                        "title": domain.title,
                        "confidentiality_key": domain.confidentiality_key,
                        "optimistic_version": domain.version,
                        "created_by_user_id": self.actor,
                        "created_at": _database_datetime(created_at),
                    }
                ).insert()
            except (frappe.UniqueValidationError, frappe.DuplicateEntryError) as error:
                raise DocumentNumberConflict() from error
            for link in object_links:
                self._insert_relationship(
                    project,
                    document,
                    link,
                    created_at=created_at,
                )
            self._append_audit(
                operation="document.create",
                global_id=document_id,
                object_version=1,
                result="created",
                summary={
                    "documentNumber": domain.document_number,
                    "documentTypeKey": domain.document_type_key,
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "relationshipCount": len(object_links),
                },
            )
            response = self._detail_for(project, document)
            self._seal_idempotency(receipt, response)
        return DocumentCommandOutcome(response)

    def check_out(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
    ) -> DocumentCommandOutcome | None:
        context = self._locked_command_context(project_id, document_id)
        if context is None:
            return None
        project, document = context
        payload = {"expectedDocumentVersion": expected_document_version}
        payload_hash = self._payload_hash(
            operation="document.lock.acquire",
            project=project,
            document_id=document_id,
            payload=payload,
        )
        replay = self._idempotency_replay(
            idempotency_key,
            payload_hash,
            project=project,
            document_id=document_id,
            operation="document.lock.acquire",
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_document_version(document, expected_document_version)
        current = self._current_lock_record(document)
        policy = self._policy_for_document(project, document)
        now = datetime.now(UTC)
        acquisition = acquire_document_lock(
            _controlled_document_value(document),
            current.lock if current is not None else None,
            lock_id=uuid4(),
            actor=self.actor,
            now=now,
            lease_minutes=policy.lock_lease_minutes,
        )
        with _controlled_document_write_scope():
            try:
                receipt = self._insert_idempotency(
                    idempotency_key,
                    payload_hash,
                    project=project,
                    document_id=document_id,
                    operation="document.lock.acquire",
                )
            except Exception as error:
                _record_checkout_stage_failure(
                    "DOCUMENT_CHECKOUT_RECEIPT_INSERT",
                    error,
                    self.trace_id,
                )
                raise
            if isinstance(receipt, dict):
                return DocumentCommandOutcome(receipt, replayed=True)
            try:
                if acquisition.expired_lock is not None:
                    assert current is not None
                    self._insert_lock_event(
                        project,
                        document,
                        acquisition.expired_lock,
                        event_type="expired",
                        actor=self.actor,
                        occurred_at=now,
                        prior_event_id=current.acquisition_event_global_id,
                    )
                self._insert_lock_event(
                    project,
                    document,
                    acquisition.active_lock,
                    event_type="acquired",
                    actor=self.actor,
                    occurred_at=now,
                    prior_event_id=None,
                )
            except Exception as error:
                _record_checkout_stage_failure(
                    "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
                    error,
                    self.trace_id,
                )
                raise
            try:
                _apply_document_projection(document, acquisition.document)
                with document_projection_validation_diagnostics(self.trace_id):
                    try:
                        document.save()
                    except Exception as error:
                        record_projection_validation_fallback(error)
                        raise
            except Exception as error:
                _record_checkout_stage_failure(
                    "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
                    error,
                    self.trace_id,
                )
                raise
            try:
                self._append_audit(
                    operation="document.lock.acquire",
                    global_id=acquisition.active_lock.global_id,
                    object_version=1,
                    result="created",
                    summary={
                        "documentId": str(document_id),
                        "expiresAt": _datetime_iso(
                            acquisition.active_lock.expires_at
                        ),
                        "projectId": str(project_id),
                        "requestId": self.request_id,
                    },
                )
            except Exception as error:
                _record_checkout_stage_failure(
                    "DOCUMENT_CHECKOUT_AUDIT_APPEND",
                    error,
                    self.trace_id,
                )
                raise
            try:
                response = self._detail_for(project, document)
            except Exception as error:
                _record_checkout_stage_failure(
                    "DOCUMENT_CHECKOUT_RESPONSE_BUILD",
                    error,
                    self.trace_id,
                )
                raise
            try:
                self._seal_idempotency(receipt, response)
            except Exception as error:
                _record_checkout_stage_failure(
                    "DOCUMENT_CHECKOUT_RECEIPT_SEAL",
                    error,
                    self.trace_id,
                )
                raise
        return DocumentCommandOutcome(response)

    def check_in(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lock_version: int,
    ) -> DocumentCommandOutcome | None:
        return self._close_lock(
            project_id,
            document_id,
            idempotency_key=idempotency_key,
            expected_document_version=expected_document_version,
            expected_lock_version=expected_lock_version,
            operation="document.lock.release",
            reason=None,
        )

    def recover_lock(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lock_version: int,
        reason: str,
    ) -> DocumentCommandOutcome | None:
        return self._close_lock(
            project_id,
            document_id,
            idempotency_key=idempotency_key,
            expected_document_version=expected_document_version,
            expected_lock_version=expected_lock_version,
            operation="document.lock.recover",
            reason=reason,
        )

    def create_revision(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lock_version: int,
        major: int,
        minor: int,
        reason: str,
        effective_date: date | None,
        predecessor_revision_id: UUID | None,
        file_name: str,
        content: bytes,
    ) -> DocumentCommandOutcome | None:
        context = self._locked_command_context(project_id, document_id)
        if context is None:
            return None
        project, document = context
        policy = self._policy_for_document(project, document)
        observation = observe_upload(file_name, content, policy)
        payload = {
            "expectedDocumentVersion": expected_document_version,
            "expectedLockVersion": expected_lock_version,
            "major": major,
            "minor": minor,
            "reason": reason,
            "effectiveDate": effective_date.isoformat() if effective_date else None,
            "predecessorRevisionId": (
                str(predecessor_revision_id)
                if predecessor_revision_id is not None
                else None
            ),
            "fileName": observation.file_name,
        }
        payload_hash = self._payload_hash(
            operation="document.revision.create",
            project=project,
            document_id=document_id,
            payload=payload,
            file_sha256=observation.sha256,
        )
        replay = self._idempotency_replay(
            idempotency_key,
            payload_hash,
            project=project,
            document_id=document_id,
            operation="document.revision.create",
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        _require_storage_capacity(observation.size_bytes)
        require_mutable_project(project)
        self._require_document_version(document, expected_document_version)
        current = self._current_lock_record(document)
        if current is None or current.lock.version != expected_lock_version:
            raise DocumentLockConflict()
        now = datetime.now(UTC)
        revision_id = uuid4()
        revision_file_id = uuid4()
        file_document_id = uuid4()
        file_document = None
        with _controlled_document_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project=project,
                document_id=document_id,
                operation="document.revision.create",
            )
            if isinstance(receipt, dict):
                return DocumentCommandOutcome(receipt, replayed=True)
            try:
                from frappe.utils.file_manager import save_file

                file_document = save_file(
                    observation.file_name,
                    content,
                    "NPI Controlled Document",
                    str(document_id),
                    is_private=1,
                )
                _register_orphan_cleanup(file_document)
                file_revision = frappe.get_doc(
                    {
                        "doctype": "NPI File Revision",
                        "global_id": str(uuid4()),
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project_id),
                        "document_global_id": str(file_document_id),
                        "revision": 1,
                        "frappe_file_id": str(file_document.name),
                        "scan_state": FileScanState.PENDING.value,
                        "released": 0,
                        "optimistic_version": 1,
                    }
                ).insert()
                file_snapshot = _file_revision_value(file_revision)
                if (
                    file_snapshot.mime_type != observation.mime_type
                    or file_snapshot.size_bytes != observation.size_bytes
                    or file_snapshot.sha256 != observation.sha256
                    or file_snapshot.frappe_content_hash
                    != observation.frappe_content_hash
                ):
                    raise ValueError(
                        "Persisted File Revision does not match the observed upload."
                    )
                append = append_document_revision(
                    _controlled_document_value(document),
                    current.lock,
                    file_snapshot,
                    display_file_name=observation.file_name,
                    revision_id=revision_id,
                    revision_file_id=revision_file_id,
                    actor=self.actor,
                    now=now,
                    major=major,
                    minor=minor,
                    reason=reason,
                    effective_date=effective_date,
                    predecessor_revision_id=predecessor_revision_id,
                    request_id=self.request_id,
                    trace_id=self.trace_id,
                )
                revision_snapshot = _revision_snapshot(
                    append,
                    current_lock=current.lock,
                    created_by=self.actor,
                    created_at=now,
                    request_id=self.request_id,
                    trace_id=self.trace_id,
                )
                if sha256_json(revision_snapshot) != append.revision.snapshot_hash:
                    raise ValueError("Document Revision snapshot generation drifted.")
                revision = frappe.get_doc(
                    {
                        "doctype": "NPI Document Revision",
                        "global_id": str(append.revision.global_id),
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project_id),
                        "controlled_document": str(document_id),
                        "document_global_id": str(document_id),
                        "major": append.revision.major,
                        "minor": append.revision.minor,
                        "revision_key": append.revision.revision_key,
                        "reason": append.revision.reason,
                        "effective_date": (
                            append.revision.effective_date.isoformat()
                            if append.revision.effective_date
                            else None
                        ),
                        "predecessor_revision_global_id": (
                            str(append.revision.predecessor_revision_id)
                            if append.revision.predecessor_revision_id
                            else None
                        ),
                        "lock_global_id": str(current.lock.global_id),
                        "lock_version": current.lock.version,
                        "revision_state": append.revision.state.value,
                        "policy_global_id": str(append.revision.policy_ref.global_id),
                        "policy_version": append.revision.policy_ref.version,
                        "policy_snapshot_hash": (
                            append.revision.policy_ref.snapshot_hash
                        ),
                        "revision_snapshot": revision_snapshot,
                        "snapshot_hash": append.revision.snapshot_hash,
                        "optimistic_version": append.revision.version,
                        "created_by_user_id": self.actor,
                        "created_at": _database_datetime(now),
                        "request_id": self.request_id,
                        "trace_id": self.trace_id,
                    }
                ).insert()
                self._insert_revision_file(
                    project,
                    document,
                    revision,
                    file_revision,
                    append.file,
                    created_at=now,
                )
                _apply_document_projection(document, append.document)
                document.save()
                self._append_audit(
                    operation="document.revision.create",
                    global_id=append.revision.global_id,
                    object_version=1,
                    result="created",
                    summary={
                        "documentId": str(document_id),
                        "fileRevisionId": str(file_snapshot.global_id),
                        "fileSha256": file_snapshot.sha256,
                        "projectId": str(project_id),
                        "requestId": self.request_id,
                        "revision": f"{append.revision.major}.{append.revision.minor}",
                    },
                )
                response = self._detail_for(project, document)
                self._seal_idempotency(receipt, response)
            except Exception:
                # The registered callback removes only an unreferenced physical
                # file after the transaction is rolled back.
                raise
        return DocumentCommandOutcome(response)

    def file_capability(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        file_revision_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        document = self._document_for_project(project, document_id)
        if document is None:
            return None
        exact = self._exact_revision_file(
            project,
            document,
            revision_id,
            file_revision_id,
        )
        if exact is None:
            raise DocumentUnavailable()
        _revision, association, file_revision = exact
        policy = self._policy_for_document(project, document)
        capability, _content = self._capability_observation(
            policy,
            file_revision,
        )
        return {
            "projectId": str(project_id),
            "documentId": str(document_id),
            "revisionId": str(revision_id),
            "fileRevisionId": str(file_revision_id),
            "file": _file_metadata_response(
                file_revision,
                display_file_name=str(association.display_file_name),
            ),
            "capabilities": _capability_response(capability),
        }

    def content(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        file_revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_file_version: int,
        disposition: str,
    ) -> DocumentContentOutcome | None:
        context = self._locked_command_context(project_id, document_id)
        if context is None:
            return None
        project, document = context
        payload = {
            "revisionId": str(revision_id),
            "fileRevisionId": str(file_revision_id),
            "expectedDocumentVersion": expected_document_version,
            "expectedFileVersion": expected_file_version,
            "disposition": disposition,
        }
        payload_hash = self._payload_hash(
            operation="document.content",
            project=project,
            document_id=document_id,
            payload=payload,
        )
        replay = self._idempotency_replay(
            idempotency_key,
            payload_hash,
            project=project,
            document_id=document_id,
            operation="document.content",
        )
        exact = self._exact_revision_file(
            project,
            document,
            revision_id,
            file_revision_id,
        )
        if exact is None:
            raise DocumentUnavailable()
        _revision, association, file_revision = exact
        if replay is None:
            self._require_document_version(
                document,
                expected_document_version,
            )
            if int(file_revision.optimistic_version) != expected_file_version:
                raise DocumentVersionConflict()
        policy = self._policy_for_document(project, document)
        capability, content = self._capability_observation(policy, file_revision)
        selected = (
            capability.preview if disposition == "inline" else capability.download
        )
        if selected.state is not CapabilityState.AVAILABLE or content is None:
            from npi_core.documents.domain import DocumentFileUnavailable

            raise DocumentFileUnavailable()
        response = {
            "documentId": str(document_id),
            "revisionId": str(revision_id),
            "fileRevisionId": str(file_revision_id),
            "fileOptimisticVersion": int(file_revision.optimistic_version),
            "sha256": str(file_revision.sha256),
            "disposition": disposition,
        }
        if replay is None:
            with _controlled_document_write_scope():
                receipt = self._insert_idempotency(
                    idempotency_key,
                    payload_hash,
                    project=project,
                    document_id=document_id,
                    operation="document.content",
                )
                if isinstance(receipt, dict):
                    replay = receipt
                else:
                    self._append_audit(
                        operation=f"document.content.{disposition}",
                        global_id=file_revision_id,
                        object_version=int(file_revision.optimistic_version),
                        result="authorized",
                        summary={
                            "documentId": str(document_id),
                            "fileRevisionId": str(file_revision_id),
                            "projectId": str(project_id),
                            "requestId": self.request_id,
                            "sha256": str(file_revision.sha256),
                        },
                    )
                    self._seal_idempotency(receipt, response)
        return DocumentContentOutcome(
            content=content,
            file_name=str(association.display_file_name),
            mime_type=str(file_revision.mime_type),
            disposition=disposition,
            response=response,
            replayed=replay is not None,
        )

    def _close_lock(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lock_version: int,
        operation: str,
        reason: str | None,
    ) -> DocumentCommandOutcome | None:
        context = self._locked_command_context(project_id, document_id)
        if context is None:
            return None
        project, document = context
        payload = {
            "expectedDocumentVersion": expected_document_version,
            "expectedLockVersion": expected_lock_version,
            "reason": reason,
        }
        payload_hash = self._payload_hash(
            operation=operation,
            project=project,
            document_id=document_id,
            payload=payload,
        )
        replay = self._idempotency_replay(
            idempotency_key,
            payload_hash,
            project=project,
            document_id=document_id,
            operation=operation,
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        self._require_document_version(document, expected_document_version)
        current = self._current_lock_record(document)
        if current is None or current.lock.version != expected_lock_version:
            raise DocumentLockConflict()
        now = datetime.now(UTC)
        if operation == "document.lock.release":
            updated, closed = release_document_lock(
                _controlled_document_value(document),
                current.lock,
                actor=self.actor,
                now=now,
            )
            event_type = "released"
        else:
            assert reason is not None
            updated, closed = recover_document_lock(
                _controlled_document_value(document),
                current.lock,
                actor=self.actor,
                reason=reason,
                now=now,
            )
            event_type = "recovered"
        with _controlled_document_write_scope():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project=project,
                document_id=document_id,
                operation=operation,
            )
            if isinstance(receipt, dict):
                return DocumentCommandOutcome(receipt, replayed=True)
            self._insert_lock_event(
                project,
                document,
                closed,
                event_type=event_type,
                actor=self.actor,
                occurred_at=now,
                prior_event_id=current.acquisition_event_global_id,
            )
            _apply_document_projection(document, updated)
            document.save()
            self._append_audit(
                operation=operation,
                global_id=closed.global_id,
                object_version=closed.version,
                result="created",
                summary={
                    "documentId": str(document_id),
                    "lockId": str(closed.global_id),
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    **({"reason": reason} if reason is not None else {}),
                },
            )
            response = self._detail_for(project, document)
            self._seal_idempotency(receipt, response)
        return DocumentCommandOutcome(response)

    def _locked_command_context(
        self,
        project_id: UUID,
        document_id: UUID,
    ) -> tuple[Any, Any] | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        try:
            document = frappe.get_doc(
                "NPI Controlled Document",
                str(document_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not _document_matches_project(document, project, document_id):
            return None
        return project, document

    def _authorized_project(self, project_id: UUID):
        project = _optional_doc("NPI Engineering Project", str(project_id))
        if project is None or not self._can_view_project(project, project_id):
            return None
        return project

    def _locked_authorized_project(self, project_id: UUID):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not self._can_administer_project(project, project_id):
            return None
        return project

    def _can_view_project(self, project, project_id: UUID) -> bool:
        if (
            str(project.global_id) != str(project_id)
            or not self._tenant_matches(project)
            or self.principal.is_external
        ):
            return False
        return bool(
            self._is_internal_system_manager()
            or str(project.owner_user_id).casefold() == self.actor.casefold()
            or self._current_actor_member(project) is not None
        )

    def _can_administer_project(self, project, project_id: UUID) -> bool:
        return bool(
            self._tenant_matches(project)
            and str(project.global_id) == str(project_id)
            and self._is_internal_system_manager()
        )

    def _tenant_matches(self, project) -> bool:
        return bool(
            not self.principal.is_external
            and self.principal.tenant_id
            and self.principal.tenant_id == str(project.tenant_id)
        )

    def _is_internal_system_manager(self) -> bool:
        return bool(
            not self.principal.is_external and "System Manager" in self.principal.roles
        )

    def _current_actor_member(self, project):
        names = frappe.get_all(
            "NPI Project Member",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "user_id": self.actor,
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_MEMBERS + 1,
        )
        if len(names) > _MAX_MEMBERS:
            raise ValueError(
                "Persisted Project member collection exceeds its safe bound."
            )
        today = datetime.now(UTC).date()
        matches = []
        for name in names:
            member = frappe.get_doc("NPI Project Member", str(name))
            if not _member_effective(member, today):
                continue
            user = frappe.db.get_value(
                "User",
                self.actor,
                ["enabled", "user_type"],
                as_dict=True,
            )
            if (
                user
                and int(_record_value(user, "enabled") or 0) == 1
                and str(_record_value(user, "user_type")) == "System User"
            ):
                matches.append(member)
        return matches[0] if len(matches) == 1 else None

    def _document_for_project(self, project, document_id: UUID):
        document = _optional_doc("NPI Controlled Document", str(document_id))
        return (
            document
            if document is not None
            and _document_matches_project(document, project, document_id)
            else None
        )

    def _permissions(self) -> dict[str, bool]:
        administer = self._is_internal_system_manager()
        return {
            "view": True,
            "create": administer,
            "revise": administer,
            "lock": administer,
            "recoverLock": administer,
            "preview": administer,
            "download": administer,
            "share": False,
            "review": False,
            "release": False,
        }

    def _may_preview(self) -> bool:
        return self._is_internal_system_manager()

    def _may_download(self) -> bool:
        return self._is_internal_system_manager()

    def _published_policy_options(self, project) -> list[dict[str, Any]]:
        names = frappe.get_all(
            "NPI Document Policy Version",
            filters={
                "tenant_id": str(project.tenant_id),
                "publication_state": DocumentPolicyState.PUBLISHED.value,
            },
            pluck="name",
            order_by="policy_key asc, policy_version desc, global_id asc",
            limit_page_length=_MAX_POLICIES + 1,
        )
        if len(names) > _MAX_POLICIES:
            raise ValueError(
                "Persisted Document Policy collection exceeds its safe bound."
            )
        result = []
        for name in names:
            row = frappe.get_doc("NPI Document Policy Version", str(name))
            root = frappe.db.get_value(
                "NPI Document Policy",
                str(row.policy_global_id),
                ["global_id", "tenant_id", "enabled"],
                as_dict=True,
            )
            if (
                not root
                or str(_record_value(root, "tenant_id")) != str(project.tenant_id)
                or int(_record_value(root, "enabled") or 0) != 1
            ):
                continue
            policy = _policy_value(row)
            result.append(_policy_option(policy))
        return result

    def _load_exact_policy(
        self,
        project,
        *,
        policy_global_id: UUID,
        policy_version: int,
        snapshot_hash: str,
    ) -> DocumentPolicyVersion:
        root = frappe.db.get_value(
            "NPI Document Policy",
            str(policy_global_id),
            ["global_id", "tenant_id", "enabled"],
            as_dict=True,
        )
        row = frappe.db.get_value(
            "NPI Document Policy Version",
            {
                "policy_global_id": str(policy_global_id),
                "policy_version": policy_version,
            },
            [
                "global_id",
                "tenant_id",
                "policy_global_id",
                "policy_key",
                "policy_version",
                "title",
                "publication_state",
                "document_types",
                "confidentiality_keys",
                "allowed_mime_types",
                "preview_mime_types",
                "maximum_file_bytes",
                "lock_lease_minutes",
                "snapshot_hash",
            ],
            as_dict=True,
        )
        if (
            not root
            or not row
            or str(_record_value(root, "global_id")) != str(policy_global_id)
            or str(_record_value(root, "tenant_id")) != str(project.tenant_id)
            or int(_record_value(root, "enabled") or 0) != 1
            or str(_record_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_record_value(row, "publication_state"))
            != DocumentPolicyState.PUBLISHED.value
            or str(_record_value(row, "snapshot_hash")) != snapshot_hash
        ):
            raise DocumentPolicyUnavailable()
        try:
            return _policy_value(row)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentPolicyUnavailable() from error

    def _policy_for_document(self, project, document) -> DocumentPolicyVersion:
        return self._load_exact_policy(
            project,
            policy_global_id=UUID(str(document.policy_global_id)),
            policy_version=int(document.policy_version),
            snapshot_hash=str(document.policy_snapshot_hash),
        )

    def _related_document_ids(
        self,
        project,
        *,
        relationship_kind: str | None,
        target_identity: str | None,
        target_version: int | None,
        project_reference_type: str | None,
        target_source_system: str | None,
        target_reference_global_id: UUID | None,
    ) -> tuple[str, ...] | None:
        if relationship_kind is None:
            return None
        filters: dict[str, object] = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "relationship_kind": relationship_kind,
            "target_identity": target_identity,
            "target_version": target_version,
        }
        if relationship_kind == DocumentRelationshipKind.PROJECT_REFERENCE.value:
            filters.update(
                {
                    "project_reference_type": project_reference_type,
                    "target_source_system": target_source_system,
                    "target_reference_global_id": (
                        str(target_reference_global_id)
                        if target_reference_global_id is not None
                        else ["is", "not set"]
                    ),
                }
            )
        names = frappe.get_all(
            "NPI Document Relationship",
            filters=filters,
            pluck="document_global_id",
            order_by="document_global_id asc",
            limit_page_length=_MAX_DOCUMENTS + 1,
        )
        if len(names) > _MAX_DOCUMENTS:
            raise ValueError(
                "Persisted Document Relationship collection exceeds its safe bound."
            )
        return tuple(dict.fromkeys(str(value) for value in names))

    def _insert_relationship(
        self,
        project,
        document,
        value: Mapping[str, object],
        *,
        created_at: datetime,
    ) -> Any:
        kind = DocumentRelationshipKind(str(value["kind"]))
        relationship = build_document_relationship(
            relationship_id=uuid4(),
            document=_controlled_document_value(document),
            kind=kind,
            target_identity=value["targetIdentity"],
            target_version=value["targetVersion"],
            project_reference_type=value.get("projectReferenceType"),
            target_source_system=value.get("targetSourceSystem"),
            target_reference_global_id=(
                UUID(str(value["targetReferenceGlobalId"]))
                if value.get("targetReferenceGlobalId") is not None
                else None
            ),
        )
        target_snapshot = _relationship_snapshot(relationship)
        return frappe.get_doc(
            {
                "doctype": "NPI Document Relationship",
                "global_id": str(relationship.global_id),
                "relationship_key": relationship.relationship_key,
                "tenant_id": relationship.tenant_id,
                "project_global_id": str(relationship.project_global_id),
                "controlled_document": str(document.global_id),
                "document_global_id": str(document.global_id),
                "relationship_kind": relationship.kind.value,
                "project_reference_type": relationship.project_reference_type,
                "target_source_system": relationship.target_source_system,
                "target_reference_global_id": (
                    str(relationship.target_reference_global_id)
                    if relationship.target_reference_global_id
                    else None
                ),
                "target_identity": relationship.target_identity,
                "target_version": relationship.target_version,
                "target_snapshot": target_snapshot,
                "snapshot_hash": sha256_json(target_snapshot),
                "optimistic_version": 1,
                "created_by_user_id": self.actor,
                "created_at": _database_datetime(created_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    def _insert_lock_event(
        self,
        project,
        document,
        lock: DocumentEditLock,
        *,
        event_type: str,
        actor: str,
        occurred_at: datetime,
        prior_event_id: UUID | None,
    ):
        event_id = uuid4()
        snapshot = _lock_event_snapshot(
            event_id=event_id,
            project=project,
            document=document,
            lock=lock,
            event_type=event_type,
            actor=actor,
            occurred_at=occurred_at,
            prior_event_id=prior_event_id,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        return frappe.get_doc(
            {
                "doctype": "NPI Document Lock Event",
                "global_id": str(event_id),
                "event_key": f"{lock.global_id}:{lock.version}",
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "controlled_document": str(document.global_id),
                "document_global_id": str(document.global_id),
                "lock_global_id": str(lock.global_id),
                "lock_version": lock.version,
                "event_type": event_type,
                "holder_user_id": lock.holder_user_id,
                "acquired_at": _database_datetime(lock.acquired_at),
                "expires_at": _database_datetime(lock.expires_at),
                "actor_user_id": actor,
                "occurred_at": _database_datetime(occurred_at),
                "prior_event_global_id": (
                    str(prior_event_id) if prior_event_id else None
                ),
                "closure_reason": lock.reason,
                "request_id": self.request_id,
                "trace_id": self.trace_id,
                "event_snapshot": snapshot,
                "snapshot_hash": sha256_json(snapshot),
            }
        ).insert()

    def _insert_revision_file(
        self,
        project,
        document,
        revision,
        file_revision,
        association,
        *,
        created_at: datetime,
    ):
        source_snapshot = association.file_revision.canonical_dict()
        snapshot = {
            "schemaVersion": 1,
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project.global_id),
            "documentGlobalId": str(document.global_id),
            "association": association.canonical_dict(),
        }
        return frappe.get_doc(
            {
                "doctype": "NPI Document Revision File",
                "global_id": str(association.global_id),
                "association_key": sha256_json(
                    {
                        "documentRevisionGlobalId": str(revision.global_id),
                        "fileRevisionGlobalId": str(file_revision.global_id),
                    }
                ),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
                "document_revision": str(revision.global_id),
                "document_revision_global_id": str(revision.global_id),
                "file_revision": str(file_revision.global_id),
                "file_revision_global_id": str(file_revision.global_id),
                "file_document_global_id": str(
                    association.file_revision.file_document_global_id
                ),
                "file_revision_number": association.file_revision.file_revision,
                "file_optimistic_version": (
                    association.file_revision.optimistic_version
                ),
                "display_file_name": association.display_file_name,
                "frappe_file_id": association.file_revision.frappe_file_id,
                "frappe_content_hash": (association.file_revision.frappe_content_hash),
                "file_name": association.file_revision.file_name,
                "mime_type": association.file_revision.mime_type,
                "size_bytes": association.file_revision.size_bytes,
                "sha256": association.file_revision.sha256,
                "scan_state": association.file_revision.scan_state.value,
                "scan_observed_at": (
                    _database_datetime(association.file_revision.scan_observed_at)
                    if association.file_revision.scan_observed_at
                    else None
                ),
                "is_private": 1,
                "released": int(association.file_revision.released),
                "file_role": association.role.value,
                "provenance": association.provenance,
                "connector_state": association.connector_state.value,
                "connector_reason_code": association.connector_reason_code,
                "file_revision_source_snapshot": source_snapshot,
                "association_snapshot": snapshot,
                "snapshot_hash": sha256_json(snapshot),
                "optimistic_version": 1,
                "created_by_user_id": self.actor,
                "created_at": _database_datetime(created_at),
                "request_id": self.request_id,
                "trace_id": self.trace_id,
            }
        ).insert()

    def _current_lock_record(self, document) -> _LockRecord | None:
        if not document.current_lock_global_id:
            return None
        event = frappe.db.get_value(
            "NPI Document Lock Event",
            {
                "lock_global_id": str(document.current_lock_global_id),
                "lock_version": int(document.current_lock_version),
                "event_type": "acquired",
            },
            [
                "global_id",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "lock_global_id",
                "lock_version",
                "holder_user_id",
                "acquired_at",
                "expires_at",
            ],
            as_dict=True,
        )
        if not event or (
            str(_record_value(event, "tenant_id")) != str(document.tenant_id)
            or str(_record_value(event, "project_global_id"))
            != str(document.project_global_id)
            or str(_record_value(event, "document_global_id"))
            != str(document.global_id)
            or str(_record_value(event, "holder_user_id"))
            != str(document.current_lock_holder_user_id)
            or _datetime_value(_record_value(event, "expires_at"))
            != _datetime_value(document.current_lock_expires_at)
        ):
            raise ValueError("Persisted current Document lock identity drifted.")
        return _LockRecord(
            lock=DocumentEditLock(
                global_id=UUID(str(_record_value(event, "lock_global_id"))),
                document_global_id=UUID(str(document.global_id)),
                version=int(_record_value(event, "lock_version")),
                holder_user_id=str(_record_value(event, "holder_user_id")),
                acquired_at=_datetime_value(_record_value(event, "acquired_at")),
                expires_at=_datetime_value(_record_value(event, "expires_at")),
                state=DocumentLockState.ACTIVE,
            ),
            acquisition_event_global_id=UUID(str(_record_value(event, "global_id"))),
        )

    def _exact_revision_file(
        self,
        project,
        document,
        revision_id: UUID,
        file_revision_id: UUID,
    ) -> tuple[Any, Any, Any] | None:
        revision = _optional_doc("NPI Document Revision", str(revision_id))
        if revision is None or any(
            (
                str(revision.tenant_id) != str(project.tenant_id),
                str(revision.project_global_id) != str(project.global_id),
                str(revision.document_global_id) != str(document.global_id),
                str(revision.global_id) != str(revision_id),
            )
        ):
            return None
        association_name = frappe.db.get_value(
            "NPI Document Revision File",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
                "document_revision_global_id": str(revision_id),
                "file_revision_global_id": str(file_revision_id),
            },
            "name",
        )
        if not association_name:
            return None
        association = frappe.get_doc(
            "NPI Document Revision File",
            str(association_name),
        )
        file_revision = _optional_doc("NPI File Revision", str(file_revision_id))
        if file_revision is None or not _association_matches_live_file(
            project,
            document,
            revision,
            association,
            file_revision,
        ):
            return None
        return revision, association, file_revision

    def _capability_observation(
        self,
        policy: DocumentPolicyVersion,
        file_revision,
    ):
        snapshot = _file_revision_value(file_revision)
        live_identity_matches = has_live_private_file_identity(file_revision)
        content: bytes | None = None
        live_sha_matches = False
        if live_identity_matches:
            try:
                file_document = frappe.get_doc(
                    "File",
                    str(file_revision.frappe_file_id),
                )
                candidate = file_document.get_content()
                if isinstance(candidate, str):
                    candidate = candidate.encode("utf-8")
                if isinstance(candidate, bytes) and len(candidate) == int(
                    file_revision.size_bytes
                ):
                    content = candidate
                    live_sha_matches = hashlib.sha256(candidate).hexdigest() == str(
                        file_revision.sha256
                    )
            except (frappe.DoesNotExistError, frappe.PermissionError, OSError):
                content = None
        capability = file_capabilities(
            policy=policy,
            file_revision=snapshot,
            live_identity_matches=live_identity_matches,
            live_sha256_matches=live_sha_matches,
            preview_authorized=self._may_preview(),
            download_authorized=self._may_download(),
        )
        if capability.integrity_state is not CapabilityState.AVAILABLE:
            content = None
        return capability, content

    def _history_capability_observation(
        self,
        policy: DocumentPolicyVersion,
        file_revision,
    ) -> dict[str, Any]:
        """Return safe summary truth without reading every historical binary."""
        snapshot = _file_revision_value(file_revision)
        identity_matches = has_live_private_file_identity(file_revision)
        integrity = {
            "state": "unavailable" if identity_matches else "blocked",
            "reasonCode": (
                "verification_required" if identity_matches else "file_identity_drift"
            ),
        }

        def action_capability(*, preview: bool) -> dict[str, str]:
            authorized = self._may_preview() if preview else self._may_download()
            if not authorized:
                return {"state": "blocked", "reasonCode": "permission_required"}
            if not identity_matches:
                return {
                    "state": "blocked",
                    "reasonCode": "file_identity_drift",
                }
            if snapshot.scan_state is not FileScanState.CLEAN:
                return {
                    "state": "blocked",
                    "reasonCode": f"scan_{snapshot.scan_state.value}",
                }
            if preview and snapshot.mime_type not in policy.preview_mime_types:
                return {
                    "state": "unavailable",
                    "reasonCode": "format_not_supported",
                }
            return {
                "state": "unavailable",
                "reasonCode": "verification_required",
            }

        preview = action_capability(preview=True)
        return {
            "integrity": integrity,
            "preview": {**preview, "mode": "none"},
            "download": action_capability(preview=False),
            "externalRetrieval": {
                "state": "unavailable",
                "reasonCode": "external_access_policy_unavailable",
            },
            "connector": {
                "state": "unavailable",
                "reasonCode": "provider_not_configured",
            },
        }

    def _document_summary(self, document) -> dict[str, Any]:
        return {
            "globalId": str(document.global_id),
            "documentNumber": str(document.document_number),
            "documentTypeKey": str(document.document_type_key),
            "title": str(document.title),
            "confidentialityKey": str(document.confidentiality_key),
            "documentPolicyRef": {
                "globalId": str(document.policy_global_id),
                "version": int(document.policy_version),
                "snapshotHash": str(document.policy_snapshot_hash),
            },
            "currentRevision": (
                {
                    "globalId": str(document.current_revision_global_id),
                    "major": int(document.current_revision_major),
                    "minor": int(document.current_revision_minor),
                    "snapshotHash": str(document.current_revision_snapshot_hash),
                }
                if document.current_revision_global_id
                else None
            ),
            "currentLock": (
                {
                    "globalId": str(document.current_lock_global_id),
                    "version": int(document.current_lock_version),
                    "holderUserId": str(document.current_lock_holder_user_id),
                    "expiresAt": _datetime_iso(document.current_lock_expires_at),
                }
                if document.current_lock_global_id
                else None
            ),
            "source": {
                "sourceSystem": "NPI_ONE",
                "editableIn": "NPI_ONE",
                "syncState": "local",
            },
            "optimisticVersion": int(document.optimistic_version),
        }

    def _detail_for(self, project, document) -> dict[str, Any]:
        revisions = _bounded_documents(
            "NPI Document Revision",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
            },
            order_by="major desc, minor desc, global_id asc",
            maximum=_MAX_DOCUMENT_HISTORY,
        )
        associations = _bounded_documents(
            "NPI Document Revision File",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
            },
            order_by="created_at desc, global_id asc",
            maximum=_MAX_DOCUMENT_HISTORY,
        )
        associations_by_revision: dict[str, list[Any]] = {}
        for association in associations:
            associations_by_revision.setdefault(
                str(association.document_revision_global_id),
                [],
            ).append(association)
        policy = self._policy_for_document(project, document)
        revision_responses = []
        for revision in revisions:
            files = []
            for association in associations_by_revision.get(
                str(revision.global_id),
                [],
            ):
                file_revision = _optional_doc(
                    "NPI File Revision",
                    str(association.file_revision_global_id),
                )
                if file_revision is None:
                    raise ValueError(
                        "Persisted Document file association is unavailable."
                    )
                if not _association_matches_live_file(
                    project,
                    document,
                    revision,
                    association,
                    file_revision,
                ):
                    raise ValueError("Persisted Document file association drifted.")
                capability = self._history_capability_observation(
                    policy,
                    file_revision,
                )
                files.append(
                    {
                        "associationId": str(association.global_id),
                        "role": str(association.file_role),
                        "provenance": str(association.provenance),
                        "connector": {
                            "state": str(association.connector_state),
                            "reasonCode": str(association.connector_reason_code),
                        },
                        **_file_metadata_response(
                            file_revision,
                            display_file_name=str(association.display_file_name),
                        ),
                        "capabilities": capability,
                    }
                )
            revision_responses.append(
                {
                    "globalId": str(revision.global_id),
                    "major": int(revision.major),
                    "minor": int(revision.minor),
                    "state": str(revision.revision_state),
                    "reason": str(revision.reason),
                    "effectiveDate": (
                        _date_value(revision.effective_date).isoformat()
                        if revision.effective_date
                        else None
                    ),
                    "predecessorRevisionId": (
                        str(revision.predecessor_revision_global_id)
                        if revision.predecessor_revision_global_id
                        else None
                    ),
                    "snapshotHash": str(revision.snapshot_hash),
                    "optimisticVersion": int(revision.optimistic_version),
                    "createdByUserId": str(revision.created_by_user_id),
                    "createdAt": _datetime_iso(revision.created_at),
                    "files": files,
                }
            )
        relationships = _bounded_documents(
            "NPI Document Relationship",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
            },
            order_by="relationship_kind asc, target_identity asc, global_id asc",
            maximum=_MAX_DOCUMENT_HISTORY,
        )
        locks = _bounded_documents(
            "NPI Document Lock Event",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
            },
            order_by="occurred_at desc, global_id asc",
            maximum=_MAX_DOCUMENT_HISTORY,
        )
        return {
            "project": _project_response(project),
            "permissions": self._permissions(),
            "document": self._document_summary(document),
            "revisions": revision_responses,
            "relationships": [
                {
                    "globalId": str(value.global_id),
                    "kind": str(value.relationship_kind),
                    "projectReferenceType": (
                        str(value.project_reference_type)
                        if value.project_reference_type
                        else None
                    ),
                    "targetSourceSystem": (
                        str(value.target_source_system)
                        if value.target_source_system
                        else None
                    ),
                    "targetReferenceGlobalId": (
                        str(value.target_reference_global_id)
                        if value.target_reference_global_id
                        else None
                    ),
                    "targetIdentity": str(value.target_identity),
                    "targetVersion": int(value.target_version),
                    "snapshotHash": str(value.snapshot_hash),
                }
                for value in relationships
            ],
            "lockHistory": [
                {
                    "globalId": str(value.global_id),
                    "lockId": str(value.lock_global_id),
                    "version": int(value.lock_version),
                    "eventType": str(value.event_type),
                    "holderUserId": str(value.holder_user_id),
                    "actorUserId": str(value.actor_user_id),
                    "acquiredAt": _datetime_iso(value.acquired_at),
                    "expiresAt": _datetime_iso(value.expires_at),
                    "occurredAt": _datetime_iso(value.occurred_at),
                    "reason": (
                        str(value.closure_reason) if value.closure_reason else None
                    ),
                    "snapshotHash": str(value.snapshot_hash),
                }
                for value in locks
            ],
            "externalRetrieval": {
                "state": "unavailable",
                "reasonCode": "external_access_policy_unavailable",
            },
        }

    @staticmethod
    def _require_document_version(document, expected_version: int) -> None:
        if int(document.optimistic_version) != expected_version:
            raise DocumentVersionConflict()

    def _payload_hash(
        self,
        *,
        operation: str,
        project,
        document_id: UUID | None,
        payload: Mapping[str, object],
        file_sha256: str | None = None,
    ) -> str:
        return command_payload_hash(
            operation=operation,
            actor=self.actor,
            tenant_id=str(project.tenant_id),
            project_id=UUID(str(project.global_id)),
            document_id=document_id,
            payload=payload,
            file_sha256=file_sha256,
        )

    def _idempotency_replay(
        self,
        actor_key_hash: str,
        payload_hash: str,
        *,
        project,
        document_id: UUID | None,
        operation: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI Document Command Idempotency",
            {"actor_key_hash": actor_key_hash},
            [
                "actor",
                "tenant_id",
                "project_global_id",
                "document_global_id",
                "operation",
                "payload_hash",
                "response_snapshot",
                "response_sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        expected_document_id = str(document_id) if document_id is not None else None
        actual_document_id = _record_value(row, "document_global_id") or None
        if (
            str(_record_value(row, "actor")) != self.actor
            or str(_record_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_record_value(row, "project_global_id")) != str(project.global_id)
            or actual_document_id != expected_document_id
            or str(_record_value(row, "operation")) != operation
        ):
            raise DocumentIdempotencyConflict()
        if str(_record_value(row, "payload_hash")) != payload_hash:
            raise DocumentIdempotencyConflict()
        if int(_record_value(row, "response_sealed") or 0) != 1:
            raise RuntimeError("Persisted Document idempotency response is unsealed.")
        return _json_object(_record_value(row, "response_snapshot"))

    def _insert_idempotency(
        self,
        actor_key_hash: str,
        payload_hash: str,
        *,
        project,
        document_id: UUID | None,
        operation: str,
    ):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Document Command Idempotency",
                    "record_id": str(uuid4()),
                    "actor": self.actor,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "document_global_id": (
                        str(document_id) if document_id is not None else None
                    ),
                    "operation": operation,
                    "actor_key_hash": actor_key_hash,
                    "payload_hash": payload_hash,
                    "request_id": self.request_id,
                    "trace_id": self.trace_id,
                    "created_at": _database_datetime(datetime.now(UTC)),
                    "response_snapshot": {},
                    "response_sealed": 0,
                }
            ).insert()
        except (
            frappe.UniqueValidationError,
            frappe.DuplicateEntryError,
        ) as error:
            # Project→Document locks serialize same-root races. Any remaining
            # actor-key collision is cross-scope reuse and must not roll back
            # or release the outer aggregate transaction.
            raise DocumentIdempotencyConflict() from error

    @staticmethod
    def _seal_idempotency(receipt, response: Mapping[str, object]) -> None:
        receipt.response_snapshot = dict(response)
        receipt.response_sealed = 1
        receipt.save()

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        result: str,
        summary: Mapping[str, object],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result=result,
            input_summary=summary,
        )
        frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(event.event_id),
                "global_id": str(event.global_id),
                "object_version": event.object_version,
                "actor": event.actor,
                "trace_id": event.trace_id,
                "operation": event.operation,
                "result": event.result,
                "input_summary": dict(event.input_summary),
            }
        ).insert()


def _controlled_document_value(document) -> ControlledDocument:
    return ControlledDocument(
        global_id=UUID(str(document.global_id)),
        tenant_id=str(document.tenant_id),
        project_global_id=UUID(str(document.project_global_id)),
        policy_ref=DocumentPolicyReference(
            global_id=UUID(str(document.policy_global_id)),
            version=int(document.policy_version),
            snapshot_hash=str(document.policy_snapshot_hash),
        ),
        document_number=str(document.document_number),
        document_number_key=str(document.document_number_key),
        document_type_key=str(document.document_type_key),
        title=str(document.title),
        confidentiality_key=str(document.confidentiality_key),
        version=int(document.optimistic_version),
        current_revision_id=(
            UUID(str(document.current_revision_global_id))
            if document.current_revision_global_id
            else None
        ),
        current_revision_major=(
            int(document.current_revision_major)
            if document.current_revision_global_id
            else None
        ),
        current_revision_minor=(
            int(document.current_revision_minor)
            if document.current_revision_global_id
            else None
        ),
        current_revision_hash=(
            str(document.current_revision_snapshot_hash)
            if document.current_revision_global_id
            else None
        ),
        current_lock_id=(
            UUID(str(document.current_lock_global_id))
            if document.current_lock_global_id
            else None
        ),
        current_lock_version=(
            int(document.current_lock_version)
            if document.current_lock_global_id
            else None
        ),
        current_lock_holder=(
            str(document.current_lock_holder_user_id)
            if document.current_lock_global_id
            else None
        ),
        current_lock_expires_at=(
            _datetime_value(document.current_lock_expires_at)
            if document.current_lock_global_id
            else None
        ),
    )


def _apply_document_projection(document, value: ControlledDocument) -> None:
    document.current_revision_global_id = (
        str(value.current_revision_id) if value.current_revision_id else None
    )
    document.current_revision_major = value.current_revision_major
    document.current_revision_minor = value.current_revision_minor
    document.current_revision_snapshot_hash = value.current_revision_hash
    document.current_lock_global_id = (
        str(value.current_lock_id) if value.current_lock_id else None
    )
    document.current_lock_version = value.current_lock_version
    document.current_lock_holder_user_id = value.current_lock_holder
    document.current_lock_expires_at = (
        _database_datetime(value.current_lock_expires_at)
        if value.current_lock_expires_at
        else None
    )
    document.optimistic_version = value.version


def _record_checkout_stage_failure(
    stage_code: str,
    error: Exception,
    trace_id: str,
) -> None:
    """Record only an allowlisted checkout stage, exception type and trace."""

    if (
        stage_code not in _CHECKOUT_STAGE_DIAGNOSTIC_CODES
        or isinstance(error, NpiProblem)
    ):
        return
    try:
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=stage_code,
            title="NPI Document checkout stage failed",
            exception_type=type(error).__name__,
            trace_id=trace_id,
        )
    except Exception:
        # Diagnostics must never replace the original checkout failure.
        pass


def _policy_value(row: object) -> DocumentPolicyVersion:
    document_types = _json_array(_record_value(row, "document_types"))
    return DocumentPolicyVersion(
        global_id=UUID(str(_record_value(row, "global_id"))),
        policy_global_id=UUID(str(_record_value(row, "policy_global_id"))),
        policy_key=str(_record_value(row, "policy_key")),
        policy_version=int(_record_value(row, "policy_version")),
        title=str(_record_value(row, "title")),
        state=DocumentPolicyState(str(_record_value(row, "publication_state"))),
        document_types=tuple(
            DocumentTypeRule(
                key=value["key"],
                prefix=value["prefix"],
                title_source=value["titleSource"],
            )
            for value in document_types
            if isinstance(value, dict)
            and set(value) == {"key", "prefix", "titleSource"}
        ),
        confidentiality_keys=tuple(
            str(value)
            for value in _json_array(_record_value(row, "confidentiality_keys"))
        ),
        allowed_mime_types=tuple(
            str(value)
            for value in _json_array(_record_value(row, "allowed_mime_types"))
        ),
        preview_mime_types=tuple(
            str(value)
            for value in _json_array(_record_value(row, "preview_mime_types"))
        ),
        maximum_file_bytes=int(_record_value(row, "maximum_file_bytes")),
        lock_lease_minutes=int(_record_value(row, "lock_lease_minutes")),
        snapshot_hash=str(_record_value(row, "snapshot_hash")),
    )


def _policy_option(policy: DocumentPolicyVersion) -> dict[str, Any]:
    return {
        "globalId": str(policy.policy_global_id),
        "versionId": str(policy.global_id),
        "version": policy.policy_version,
        "snapshotHash": policy.snapshot_hash,
        "key": policy.policy_key,
        "title": policy.title,
        "documentTypes": [
            value.canonical_dict()
            for value in sorted(policy.document_types, key=lambda item: item.key)
        ],
        "confidentialityKeys": sorted(policy.confidentiality_keys),
        "allowedMimeTypes": sorted(policy.allowed_mime_types),
        "previewMimeTypes": sorted(policy.preview_mime_types),
        "maximumFileBytes": policy.maximum_file_bytes,
        "lockLeaseMinutes": policy.lock_lease_minutes,
    }


def _association_matches_live_file(
    project,
    document,
    revision,
    association,
    file_revision,
) -> bool:
    """Validate the frozen association while allowing scanner observations to advance."""
    try:
        frozen_file = FileRevisionSnapshot(
            global_id=UUID(str(association.file_revision_global_id)),
            file_document_global_id=UUID(str(association.file_document_global_id)),
            file_revision=int(association.file_revision_number),
            optimistic_version=int(association.file_optimistic_version),
            file_name=str(association.file_name),
            mime_type=str(association.mime_type),
            size_bytes=int(association.size_bytes),
            sha256=str(association.sha256),
            scan_state=FileScanState(str(association.scan_state)),
            scan_observed_at=(
                _datetime_value(association.scan_observed_at)
                if association.scan_observed_at not in (None, "")
                else None
            ),
            frappe_file_id=str(association.frappe_file_id),
            frappe_content_hash=str(association.frappe_content_hash),
            is_private=int(association.is_private or 0) == 1,
            released=int(association.released or 0) == 1,
        )
        frozen_association = DocumentRevisionFile(
            global_id=UUID(str(association.global_id)),
            document_revision_global_id=UUID(
                str(association.document_revision_global_id)
            ),
            file_revision=frozen_file,
            display_file_name=str(association.display_file_name),
            role=DocumentFileRole(str(association.file_role)),
            provenance=str(association.provenance),
            connector_state=ConnectorState(str(association.connector_state)),
            connector_reason_code=str(association.connector_reason_code),
        )
        expected_source = frozen_file.canonical_dict()
        expected_snapshot = {
            "schemaVersion": 1,
            "tenantId": str(project.tenant_id),
            "projectGlobalId": str(project.global_id),
            "documentGlobalId": str(document.global_id),
            "association": frozen_association.canonical_dict(),
        }
        snapshots_match = bool(
            _json_object(association.file_revision_source_snapshot) == expected_source
            and _json_object(association.association_snapshot) == expected_snapshot
            and str(association.snapshot_hash) == sha256_json(expected_snapshot)
        )
    except (RequestValidationFailed, TypeError, ValueError):
        return False
    return bool(
        snapshots_match
        and str(association.tenant_id) == str(project.tenant_id)
        and str(association.project_global_id) == str(project.global_id)
        and str(association.document_global_id) == str(document.global_id)
        and str(association.document_revision) == str(revision.global_id)
        and str(association.document_revision_global_id) == str(revision.global_id)
        and str(association.file_revision) == str(file_revision.global_id)
        and str(file_revision.global_id) == str(association.file_revision_global_id)
        and str(file_revision.tenant_id) == str(project.tenant_id)
        and str(file_revision.project_global_id) == str(project.global_id)
        and str(file_revision.document_global_id)
        == str(association.file_document_global_id)
        and int(file_revision.revision) == int(association.file_revision_number)
        and str(file_revision.frappe_file_id) == str(association.frappe_file_id)
        and str(file_revision.frappe_content_hash)
        == str(association.frappe_content_hash)
        and str(file_revision.file_name) == str(association.file_name)
        and str(file_revision.mime_type) == str(association.mime_type)
        and int(file_revision.size_bytes) == int(association.size_bytes)
        and str(file_revision.sha256) == str(association.sha256)
        and int(file_revision.is_private or 0) == 1
    )


def _file_revision_value(document) -> FileRevisionSnapshot:
    observed_at = _record_value(document, "scan_observed_at")
    return FileRevisionSnapshot(
        global_id=UUID(str(_record_value(document, "global_id"))),
        file_document_global_id=UUID(
            str(_record_value(document, "document_global_id"))
        ),
        file_revision=int(_record_value(document, "revision")),
        optimistic_version=int(_record_value(document, "optimistic_version")),
        file_name=str(_record_value(document, "file_name")),
        mime_type=str(_record_value(document, "mime_type")),
        size_bytes=int(_record_value(document, "size_bytes")),
        sha256=str(_record_value(document, "sha256")),
        scan_state=FileScanState(str(_record_value(document, "scan_state"))),
        frappe_file_id=str(_record_value(document, "frappe_file_id")),
        frappe_content_hash=str(_record_value(document, "frappe_content_hash")),
        is_private=int(_record_value(document, "is_private") or 0) == 1,
        released=int(_record_value(document, "released") or 0) == 1,
        scan_observed_at=(
            _datetime_value(observed_at) if observed_at not in (None, "") else None
        ),
    )


def _file_metadata_response(
    document,
    *,
    display_file_name: str | None = None,
) -> dict[str, Any]:
    snapshot = file_revision_source_snapshot(document)
    return {
        "globalId": str(snapshot["globalId"]),
        "fileDocumentId": str(snapshot["documentGlobalId"]),
        "revision": int(snapshot["revision"]),
        "optimisticVersion": int(snapshot["fileOptimisticVersion"]),
        "fileName": (
            display_file_name
            if display_file_name is not None
            else str(snapshot["fileName"])
        ),
        "mimeType": str(snapshot["mimeType"]),
        "sizeBytes": int(snapshot["sizeBytes"]),
        "sha256": str(snapshot["sha256"]),
        "scanState": str(snapshot["scanState"]),
        "scanObservedAt": snapshot["scanObservedAt"],
        "private": snapshot["isPrivate"] is True,
        "released": snapshot["released"] is True,
    }


def _capability_response(value) -> dict[str, Any]:
    return {
        "integrity": {
            "state": value.integrity_state.value,
            "reasonCode": value.integrity_reason_code,
        },
        "preview": {
            "state": value.preview.state.value,
            "reasonCode": value.preview.reason_code,
            "mode": value.preview.mode.value,
        },
        "download": {
            "state": value.download.state.value,
            "reasonCode": value.download.reason_code,
        },
        "externalRetrieval": {
            "state": value.external_retrieval.state.value,
            "reasonCode": value.external_retrieval.reason_code,
        },
        "connector": {
            "state": value.connector.state.value,
            "reasonCode": value.connector.reason_code,
        },
    }


def _revision_snapshot(
    append,
    *,
    current_lock: DocumentEditLock,
    created_by: str,
    created_at: datetime,
    request_id: str,
    trace_id: str,
) -> dict[str, object]:
    revision = append.revision
    return {
        "schemaVersion": 1,
        "globalId": str(revision.global_id),
        "documentGlobalId": str(revision.document_global_id),
        "major": revision.major,
        "minor": revision.minor,
        "reason": revision.reason,
        "effectiveDate": (
            revision.effective_date.isoformat() if revision.effective_date else None
        ),
        "predecessorRevisionId": (
            str(revision.predecessor_revision_id)
            if revision.predecessor_revision_id
            else None
        ),
        "state": revision.state.value,
        "documentPolicyRef": revision.policy_ref.canonical_dict(),
        "lockRef": {
            "globalId": str(current_lock.global_id),
            "version": current_lock.version,
            "holderUserId": current_lock.holder_user_id,
        },
        "file": append.file.canonical_dict(),
        "createdByUserId": created_by,
        "createdAt": _datetime_iso(created_at),
        "requestId": request_id,
        "traceId": trace_id,
    }


def _relationship_snapshot(relationship) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "tenantId": relationship.tenant_id,
        "projectGlobalId": str(relationship.project_global_id),
        "kind": relationship.kind.value,
        "projectReferenceType": relationship.project_reference_type,
        "targetSourceSystem": relationship.target_source_system,
        "targetReferenceGlobalId": (
            str(relationship.target_reference_global_id)
            if relationship.target_reference_global_id
            else None
        ),
        "targetIdentity": relationship.target_identity,
        "targetVersion": relationship.target_version,
    }


def _lock_event_snapshot(
    *,
    event_id: UUID,
    project,
    document,
    lock: DocumentEditLock,
    event_type: str,
    actor: str,
    occurred_at: datetime,
    prior_event_id: UUID | None,
    request_id: str,
    trace_id: str,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "globalId": str(event_id),
        "tenantId": str(project.tenant_id),
        "projectGlobalId": str(project.global_id),
        "documentGlobalId": str(document.global_id),
        "lockGlobalId": str(lock.global_id),
        "lockVersion": lock.version,
        "eventType": event_type,
        "holderUserId": lock.holder_user_id,
        "acquiredAt": _datetime_iso(lock.acquired_at),
        "expiresAt": _datetime_iso(lock.expires_at),
        "actorUserId": actor,
        "occurredAt": _datetime_iso(occurred_at),
        "priorEventGlobalId": str(prior_event_id) if prior_event_id else None,
        "closureReason": lock.reason,
        "requestId": request_id,
        "traceId": trace_id,
    }


def _document_matches_project(document, project, document_id: UUID) -> bool:
    return bool(
        str(document.global_id) == str(document_id)
        and str(document.tenant_id) == str(project.tenant_id)
        and str(document.project_global_id) == str(project.global_id)
    )


def _project_response(project) -> dict[str, Any]:
    return {
        "globalId": str(project.global_id),
        "businessCode": str(project.business_code),
        "title": str(project.title),
        "lifecycleState": str(project.lifecycle_state),
        "optimisticVersion": int(project.optimistic_version),
    }


def _member_effective(member, at: date) -> bool:
    start = _date_value(member.effective_from)
    end = _date_value(member.effective_to) if member.effective_to else None
    return start <= at and (end is None or at <= end)


def _bounded_documents(
    doctype: str,
    filters: Mapping[str, object],
    *,
    order_by: str,
    maximum: int,
) -> tuple[Any, ...]:
    names = frappe.get_all(
        doctype,
        filters=dict(filters),
        pluck="name",
        order_by=order_by,
        limit_page_length=maximum + 1,
    )
    if len(names) > maximum:
        raise ValueError(f"Persisted {doctype} collection exceeds its safe bound.")
    return tuple(frappe.get_doc(doctype, str(name)) for name in names)


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _json_array(value: object) -> list[Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Persisted Document JSON value must be an array.")
    return parsed


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("Persisted Document JSON value must be an object.")
    return parsed


def _record_value(record: object, fieldname: str) -> object:
    if isinstance(record, dict):
        return record.get(fieldname)
    return getattr(record, fieldname, None)


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _datetime_iso(value: object) -> str:
    return _datetime_value(value).isoformat().replace("+00:00", "Z")


def _database_datetime(value: datetime) -> str:
    return (
        _datetime_value(value)
        .replace(tzinfo=None)
        .isoformat(sep=" ", timespec="microseconds")
    )


def _encode_cursor(global_id: str, *, query_hash: str) -> str:
    if _SHA256_PATTERN.fullmatch(query_hash) is None:
        raise ValueError("A Document cursor query hash must be a SHA-256 value.")
    payload = canonical_json(
        {
            "globalId": str(UUID(global_id)),
            "queryHash": query_hash,
            "version": _CURSOR_VERSION,
        }
    ).encode("utf-8")
    signature = hmac.new(_cursor_signing_key(), payload, hashlib.sha256).digest()
    result = f"{_base64url_encode(payload)}.{_base64url_encode(signature)}"
    if len(result) > 500:
        raise ValueError("The generated Document cursor exceeds the API limit.")
    return result


def _decode_cursor(value: str, *, expected_query_hash: str) -> str:
    try:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 500
            or _SHA256_PATTERN.fullmatch(expected_query_hash) is None
        ):
            raise ValueError
        encoded_payload, encoded_signature = value.split(".")
        payload = _base64url_decode(encoded_payload)
        signature = _base64url_decode(encoded_signature)
        expected_signature = hmac.new(
            _cursor_signing_key(),
            payload,
            hashlib.sha256,
        ).digest()
        if len(signature) != hashlib.sha256().digest_size or not hmac.compare_digest(
            signature, expected_signature
        ):
            raise ValueError
        parsed = json.loads(payload.decode("utf-8"))
        if (
            not isinstance(parsed, dict)
            or set(parsed) != {"globalId", "queryHash", "version"}
            or parsed["queryHash"] != expected_query_hash
            or parsed["version"] != _CURSOR_VERSION
        ):
            raise ValueError
        global_id = str(UUID(str(parsed["globalId"])))
        if (
            _base64url_encode(
                canonical_json(
                    {
                        "globalId": global_id,
                        "queryHash": expected_query_hash,
                        "version": _CURSOR_VERSION,
                    }
                ).encode("utf-8")
            )
            != encoded_payload
        ):
            raise ValueError
        return global_id
    except (
        binascii.Error,
        TypeError,
        UnicodeError,
        ValueError,
    ) as error:
        raise RequestValidationFailed(
            [{"path": "cursor", "message": _("Enter a valid cursor.")}]
        ) from error


def _cursor_signing_key() -> bytes:
    try:
        local = getattr(frappe, "local", None)
        configuration = getattr(local, "conf", None)
        if configuration is None:
            configuration = getattr(frappe, "conf", None)
        persisted_key = (
            configuration.get("encryption_key")
            if hasattr(configuration, "get")
            else None
        )
        if not isinstance(persisted_key, str):
            raise ValueError
        encoded_key = persisted_key.encode("ascii")
        decoded_key = base64.b64decode(
            encoded_key,
            altchars=b"-_",
            validate=True,
        )
        if (
            len(decoded_key) != 32
            or base64.urlsafe_b64encode(decoded_key) != encoded_key
        ):
            raise ValueError
    except (binascii.Error, TypeError, UnicodeError, ValueError) as error:
        raise CursorSigningUnavailable() from error
    return hmac.new(
        decoded_key,
        _CURSOR_KEY_CONTEXT,
        hashlib.sha256,
    ).digest()


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError
    return base64.b64decode(
        value + ("=" * (-len(value) % 4)),
        altchars=b"-_",
        validate=True,
    )


def _require_storage_capacity(size_bytes: int) -> None:
    from frappe.utils.file_manager import get_max_file_size

    configured_limit = get_max_file_size()
    if type(configured_limit) is not int or configured_limit < 1:
        raise RuntimeError("The configured Frappe upload limit is invalid.")
    if size_bytes > configured_limit:
        raise RequestValidationFailed(
            [
                {
                    "path": "file",
                    "message": _("The file exceeds the configured upload limit."),
                }
            ]
        )


def _register_orphan_cleanup(file_document) -> None:
    file_id = str(file_document.name)
    file_url = str(file_document.file_url)
    parsed = PurePosixPath(file_url)
    if (
        not file_url.startswith("/private/files/")
        or len(parsed.parts) != 4
        or parsed.parts[:3] != ("/", "private", "files")
        or parsed.name in {"", ".", ".."}
    ):
        raise ValueError("The newly saved private File path is invalid.")
    private_directory = Path(frappe.get_site_path("private", "files")).resolve()
    file_path = (private_directory / parsed.name).resolve()
    if file_path.parent != private_directory:
        raise ValueError("The newly saved private File path escaped its boundary.")

    def cleanup_after_rollback() -> None:
        try:
            remaining = frappe.db.get_value(
                "File",
                {"file_url": file_url},
                "name",
            )
            if remaining:
                return
            file_path.unlink(missing_ok=True)
        except Exception as error:
            from npi_core.api import record_safe_diagnostic

            record_safe_diagnostic(
                code="DOCUMENT_ORPHAN_FILE_CLEANUP_FAILED",
                title="NPI Document orphan file cleanup failed",
                exception_type=type(error).__name__,
            )

    frappe.db.after_rollback.add(cleanup_after_rollback)
    if str(file_document.name) != file_id:
        raise ValueError("The newly saved private File identity drifted.")


@contextmanager
def _controlled_document_write_scope() -> Iterator[None]:
    flags = frappe.flags
    missing = object()
    names = (
        DOCUMENT_COMMAND_FLAG,
        FILE_REVISION_COMMAND_FLAG,
        "npi_audit_append",
    )
    previous = {name: getattr(flags, name, missing) for name in names}
    for name in names:
        setattr(flags, name, True)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is missing:
                try:
                    delattr(flags, name)
                except AttributeError:
                    pass
            else:
                setattr(flags, name, value)
