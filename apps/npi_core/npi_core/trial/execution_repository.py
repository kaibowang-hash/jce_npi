from __future__ import annotations

import hashlib
import json
import mimetypes
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.controlled_evidence_validation import FILE_REVISION_COMMAND_FLAG
from npi_core.documents.domain import validate_file_name
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.trial.domain import (
    TrialRound,
    TrialRoundState,
    sha256_json,
    transition_trial_round,
    trial_round_from_snapshot,
)
from npi_core.trial.execution_domain import (
    TrialAcquisitionMode,
    TrialActualResourceKind,
    TrialActualResourceObservation,
    TrialEnvironmentObservation,
    TrialEvidenceReference,
    TrialEvidenceRole,
    TrialExecutionConflict,
    TrialExecutionReferenceUnavailable,
    TrialLockedReference,
    TrialLockedReferenceKind,
    TrialMaterialObservation,
    TrialMeasurementState,
    TrialParameterDefinition,
    TrialParameterObservation,
    TrialParameterValueKind,
    TrialRoundActualRevision,
    TrialRoundInputLockRevision,
    TrialSampleBatchRevision,
    actual_revision_from_snapshot,
    evidence_reference_from_snapshot,
    input_lock_from_snapshot,
    sample_batch_from_snapshot,
    validate_sample_batch_successor,
    validate_trial_actual_against_lock,
    validate_trial_actual_successor,
)
from npi_core.trial.frappe_repository import (
    FrappeTrialRepository,
    _database_datetime,
    _datetime_iso,
    _json_object,
    _is_replay_response,
    _optional_doc,
    _payload_hash,
    _round_response,
)
from npi_core.trial.frappe_validation import trial_command_write


_MAX_INPUT_LOCKS = 1_000
_MAX_ACTUALS = 1_000
_MAX_SAMPLES = 5_000
_MAX_EVIDENCE = 5_000
_MAX_PENDING_FILES = 500
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_TRIAL_UPLOAD_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/csv",
        "video/mp4",
        "video/quicktime",
    }
)


@dataclass(frozen=True, slots=True)
class TrialExecutionCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class TrialEvidenceContentOutcome:
    content: bytes
    file_name: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class _UploadObservation:
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    frappe_content_hash: str


@dataclass(frozen=True, slots=True)
class _ResolvedReferenceDocument:
    document: Any
    optimistic_version: int
    snapshot_hash: str

    def __getattr__(self, name: str) -> Any:
        return getattr(self.document, name)


class FrappeTrialExecutionRepository(FrappeTrialRepository):
    """Project-first P7-02 execution, sample and private-evidence boundary."""

    def execution_workspace(
        self,
        project_id: UUID,
        round_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        round_pair = self._execution_round(project, round_id)
        if round_pair is None:
            return None
        return self._execution_workspace_for(project, round_pair[1])

    def prepare_round(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        references: Sequence[Mapping[str, Any]],
        material: Mapping[str, Any],
        parameter_definitions: Sequence[Mapping[str, Any]],
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "references": sorted(
                references,
                key=lambda value: (str(value["kind"]), str(value["globalId"])),
            ),
            "material": material,
            "parameterDefinitions": parameter_definitions,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_round.prepare",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialExecutionCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            return None
        round_document, trial_round = round_pair
        self._require_round_version(
            trial_round,
            expected_round_optimistic_version,
            TrialRoundState.PLANNED,
        )
        if self._current_input_lock(project, round_id, for_update=True) is not None:
            raise TrialExecutionConflict()
        locked_references = self._resolve_locked_references(
            project,
            trial_round,
            references,
        )
        now = datetime.now(UTC)
        input_lock = TrialRoundInputLockRevision(
            global_id=uuid4(),
            input_lock_global_id=uuid4(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            trial_round_global_id=round_id,
            trial_plan_revision_global_id=trial_round.trial_plan_revision_global_id,
            trial_plan_revision_snapshot_hash=(
                trial_round.trial_plan_revision_snapshot_hash
            ),
            lock_version=1,
            references=locked_references,
            material=self._material(material),
            parameter_definitions=self._parameter_definitions(parameter_definitions),
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        transitioned, event = transition_trial_round(
            trial_round,
            event_global_id=uuid4(),
            to_state=TrialRoundState.PREPARED,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_round.prepare",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            self._insert_input_lock(input_lock)
            self._insert_round_event(event)
            self._save_round(round_document, transitioned)
            self._append_audit(
                operation="trial_round.prepare",
                global_id=round_id,
                object_version=transitioned.optimistic_version,
                summary={
                    "inputLockRevisionGlobalId": str(input_lock.global_id),
                    "projectId": str(project_id),
                    "reason": reason,
                    "requestId": self.request_id,
                },
            )
            response = self._execution_workspace_for(project, transitioned)
            self._seal_receipt(
                receipt,
                target_object_type="trial_input_lock_revision",
                target_global_id=input_lock.global_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    def start_round(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_input_lock_revision_global_id: UUID,
        expected_input_lock_version: int,
        resources: Sequence[Mapping[str, Any]],
        material: Mapping[str, Any],
        environment: Sequence[Mapping[str, Any]],
        parameters: Sequence[Mapping[str, Any]],
        operator_user_id: str,
        execution_started_at: datetime,
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedInputLockRevisionGlobalId": expected_input_lock_revision_global_id,
            "expectedInputLockVersion": expected_input_lock_version,
            "resources": resources,
            "material": material,
            "environment": environment,
            "parameters": parameters,
            "operatorUserId": operator_user_id,
            "executionStartedAt": execution_started_at,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_round.start",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialExecutionCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            return None
        round_document, trial_round = round_pair
        self._require_round_version(
            trial_round,
            expected_round_optimistic_version,
            TrialRoundState.PREPARED,
        )
        input_lock = self._current_input_lock(project, round_id, for_update=True)
        if (
            input_lock is None
            or input_lock.global_id != expected_input_lock_revision_global_id
            or input_lock.lock_version != expected_input_lock_version
        ):
            raise TrialExecutionConflict()
        if self._current_actual(project, round_id, for_update=True) is not None:
            raise TrialExecutionConflict()
        now = datetime.now(UTC)
        actual = self._actual_revision(
            project,
            round_id,
            input_lock,
            actual_global_id=uuid4(),
            actual_version=1,
            resources=resources,
            material=material,
            environment=environment,
            parameters=parameters,
            operator_user_id=operator_user_id,
            execution_started_at=execution_started_at,
            reason=reason,
            created_at=now,
        )
        transitioned, event = transition_trial_round(
            trial_round,
            event_global_id=uuid4(),
            to_state=TrialRoundState.RUNNING,
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_round.start",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            self._insert_actual(actual)
            self._insert_round_event(event)
            self._save_round(round_document, transitioned)
            self._append_audit(
                operation="trial_round.start",
                global_id=round_id,
                object_version=transitioned.optimistic_version,
                summary={
                    "actualRevisionGlobalId": str(actual.global_id),
                    "inputLockRevisionGlobalId": str(input_lock.global_id),
                    "projectId": str(project_id),
                    "reason": reason,
                    "requestId": self.request_id,
                },
            )
            response = self._execution_workspace_for(project, transitioned)
            self._seal_receipt(
                receipt,
                target_object_type="trial_actual_revision",
                target_global_id=actual.global_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    def append_actual_revision(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_actual_revision_global_id: UUID,
        expected_actual_version: int,
        resources: Sequence[Mapping[str, Any]],
        material: Mapping[str, Any],
        environment: Sequence[Mapping[str, Any]],
        parameters: Sequence[Mapping[str, Any]],
        operator_user_id: str,
        execution_started_at: datetime,
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedActualRevisionGlobalId": expected_actual_revision_global_id,
            "expectedActualVersion": expected_actual_version,
            "resources": resources,
            "material": material,
            "environment": environment,
            "parameters": parameters,
            "operatorUserId": operator_user_id,
            "executionStartedAt": execution_started_at,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_actual.append",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialExecutionCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            return None
        trial_round = round_pair[1]
        self._require_round_version(
            trial_round,
            expected_round_optimistic_version,
            TrialRoundState.RUNNING,
        )
        predecessor = self._current_actual(project, round_id, for_update=True)
        if (
            predecessor is None
            or predecessor.global_id != expected_actual_revision_global_id
            or predecessor.actual_version != expected_actual_version
        ):
            raise TrialExecutionConflict()
        input_lock = self._exact_input_lock(
            project,
            round_id,
            predecessor.input_lock_revision_global_id,
        )
        if input_lock is None:
            raise TrialExecutionReferenceUnavailable()
        now = datetime.now(UTC)
        successor = self._actual_revision(
            project,
            round_id,
            input_lock,
            actual_global_id=predecessor.actual_global_id,
            actual_version=predecessor.actual_version + 1,
            resources=resources,
            material=material,
            environment=environment,
            parameters=parameters,
            operator_user_id=operator_user_id,
            execution_started_at=execution_started_at,
            reason=reason,
            created_at=now,
            predecessor=predecessor,
        )
        validate_trial_actual_successor(predecessor, successor)
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_actual.append",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            self._insert_actual(successor)
            self._append_audit(
                operation="trial_actual.append",
                global_id=successor.actual_global_id,
                object_version=successor.actual_version,
                summary={
                    "predecessorGlobalId": str(predecessor.global_id),
                    "projectId": str(project_id),
                    "reason": reason,
                    "requestId": self.request_id,
                    "trialRoundGlobalId": str(round_id),
                },
            )
            response = self._execution_workspace_for(project, trial_round)
            self._seal_receipt(
                receipt,
                target_object_type="trial_actual_revision",
                target_global_id=successor.global_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    def create_sample_batch(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_input_lock_revision_global_id: UUID,
        sample: Mapping[str, Any],
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        return self._write_sample(
            project_id,
            round_id,
            idempotency_key_hash=idempotency_key_hash,
            expected_round_optimistic_version=expected_round_optimistic_version,
            expected_input_lock_revision_global_id=expected_input_lock_revision_global_id,
            sample_batch_id=None,
            expected_revision_global_id=None,
            expected_sample_version=None,
            sample=sample,
            reason=reason,
        )

    def append_sample_batch_revision(
        self,
        project_id: UUID,
        round_id: UUID,
        sample_batch_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_revision_global_id: UUID,
        expected_sample_version: int,
        sample: Mapping[str, Any],
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        return self._write_sample(
            project_id,
            round_id,
            idempotency_key_hash=idempotency_key_hash,
            expected_round_optimistic_version=expected_round_optimistic_version,
            expected_input_lock_revision_global_id=None,
            sample_batch_id=sample_batch_id,
            expected_revision_global_id=expected_revision_global_id,
            expected_sample_version=expected_sample_version,
            sample=sample,
            reason=reason,
        )

    def _write_sample(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        expected_input_lock_revision_global_id: UUID | None,
        sample_batch_id: UUID | None,
        expected_revision_global_id: UUID | None,
        expected_sample_version: int | None,
        sample: Mapping[str, Any],
        reason: str,
    ) -> TrialExecutionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        operation = "trial_sample.create" if sample_batch_id is None else "trial_sample.revise"
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "sampleBatchId": sample_batch_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "expectedInputLockRevisionGlobalId": expected_input_lock_revision_global_id,
            "expectedRevisionGlobalId": expected_revision_global_id,
            "expectedSampleVersion": expected_sample_version,
            "sample": sample,
            "reason": reason,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            operation,
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialExecutionCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            return None
        trial_round = round_pair[1]
        self._require_round_version(
            trial_round,
            expected_round_optimistic_version,
            TrialRoundState.RUNNING,
        )
        predecessor = None
        if sample_batch_id is None:
            input_lock = self._current_input_lock(project, round_id, for_update=True)
            if (
                input_lock is None
                or input_lock.global_id != expected_input_lock_revision_global_id
            ):
                raise TrialExecutionConflict()
            stable_id = uuid4()
            version = 1
        else:
            predecessor = self._current_sample(
                project,
                round_id,
                sample_batch_id,
                for_update=True,
            )
            if (
                predecessor is None
                or predecessor.global_id != expected_revision_global_id
                or predecessor.sample_version != expected_sample_version
            ):
                raise TrialExecutionConflict()
            input_lock = self._exact_input_lock(
                project,
                round_id,
                predecessor.input_lock_revision_global_id,
            )
            if input_lock is None:
                raise TrialExecutionReferenceUnavailable()
            stable_id = sample_batch_id
            version = predecessor.sample_version + 1
        cavity_ids = tuple(sample["cavityGlobalIds"])
        locked_cavities = {
            value.global_id
            for value in input_lock.references
            if value.kind is TrialLockedReferenceKind.CAVITY
        }
        if not set(cavity_ids).issubset(locked_cavities):
            raise TrialExecutionReferenceUnavailable()
        if sample_batch_id is None and frappe.db.exists(
            "NPI Trial Sample Batch Revision",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project_id),
                "trial_round_global_id": str(round_id),
                "label": sample["label"],
            },
        ):
            raise TrialExecutionConflict()
        now = datetime.now(UTC)
        revision = TrialSampleBatchRevision(
            global_id=uuid4(),
            sample_batch_global_id=stable_id,
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            trial_round_global_id=round_id,
            input_lock_revision_global_id=input_lock.global_id,
            input_lock_revision_snapshot_hash=input_lock.snapshot_hash,
            sample_version=version,
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
            label=sample["label"],
            cavity_global_ids=cavity_ids,
            material_snapshot_hash=sha256_json(input_lock.material.snapshot_payload()),
            quantity=sample["quantity"],
            unit=sample["unit"],
            packaging=sample["packaging"],
            destination=sample["destination"],
            feedback_text=sample.get("feedbackText"),
            feedback_source=sample.get("feedbackSource"),
            feedback_observed_at=sample.get("feedbackObservedAt"),
            reason=reason,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        if predecessor is not None:
            validate_sample_batch_successor(predecessor, revision)
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            self._insert_sample(revision)
            self._append_audit(
                operation=operation,
                global_id=stable_id,
                object_version=version,
                summary={
                    "predecessorGlobalId": str(predecessor.global_id) if predecessor else None,
                    "projectId": str(project_id),
                    "reason": reason,
                    "requestId": self.request_id,
                    "trialRoundGlobalId": str(round_id),
                },
            )
            response = self._execution_workspace_for(project, trial_round)
            self._seal_receipt(
                receipt,
                target_object_type="trial_sample_batch_revision",
                target_global_id=revision.global_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    def upload_evidence_file(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        upload: Callable[[], tuple[str, bytes]],
    ) -> TrialExecutionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        file_name, content = upload()
        observation = _observe_trial_upload(file_name, content)
        payload_hash = _payload_hash(
            {
                "projectId": project_id,
                "trialRoundId": round_id,
                "expectedRoundOptimisticVersion": expected_round_optimistic_version,
                "fileName": observation.file_name,
                "fileSha256": observation.sha256,
            }
        )
        replay = self._idempotency_replay(
            project,
            "trial_file.upload",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialExecutionCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            return None
        trial_round = round_pair[1]
        self._require_round_version(
            trial_round,
            expected_round_optimistic_version,
            TrialRoundState.RUNNING,
        )
        _require_storage_capacity(observation.size_bytes)
        revision_number = self._next_file_revision(project, round_id)
        now = datetime.now(UTC)
        file_document = None
        with trial_command_write(), _file_revision_write_scope():
            receipt = self._insert_receipt(
                project,
                operation="trial_file.upload",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            from frappe.utils.file_manager import save_file

            file_document = save_file(
                observation.file_name,
                content,
                "NPI Trial Round",
                str(round_id),
                is_private=1,
            )
            _register_orphan_cleanup(file_document)
            file_revision = frappe.get_doc(
                {
                    "doctype": "NPI File Revision",
                    "global_id": str(uuid4()),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "document_global_id": str(round_id),
                    "revision": revision_number,
                    "frappe_file_id": str(file_document.name),
                    "scan_state": "pending",
                    "released": 0,
                    "optimistic_version": 1,
                }
            ).insert()
            snapshot = _file_revision_source_snapshot(file_revision)
            if (
                snapshot["mimeType"] != observation.mime_type
                or snapshot["sizeBytes"] != observation.size_bytes
                or snapshot["sha256"] != observation.sha256
                or snapshot["fileContentHash"] != observation.frappe_content_hash
                or snapshot["scanState"] != "pending"
                or snapshot["isPrivate"] is not True
            ):
                raise RuntimeError("Persisted Trial File Revision does not match the observed upload.")
            file_revision_id = UUID(str(snapshot["globalId"]))
            self._append_audit(
                operation="trial_file.upload",
                global_id=file_revision_id,
                object_version=1,
                summary={
                    "fileName": observation.file_name,
                    "fileSha256": observation.sha256,
                    "fileSizeBytes": observation.size_bytes,
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "trialRoundGlobalId": str(round_id),
                },
            )
            response = self._execution_workspace_for(project, trial_round)
            self._seal_receipt(
                receipt,
                target_object_type="trial_pending_file_revision",
                target_global_id=file_revision_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    def bind_evidence(
        self,
        project_id: UUID,
        round_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_round_optimistic_version: int,
        role: TrialEvidenceRole,
        file_revision_global_id: UUID,
        expected_file_optimistic_version: int,
        sample_batch_revision_global_id: UUID | None,
        expected_sample_version: int | None,
    ) -> TrialExecutionCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "trialRoundId": round_id,
            "expectedRoundOptimisticVersion": expected_round_optimistic_version,
            "role": role,
            "fileRevisionGlobalId": file_revision_global_id,
            "expectedFileOptimisticVersion": expected_file_optimistic_version,
            "sampleBatchRevisionGlobalId": sample_batch_revision_global_id,
            "expectedSampleVersion": expected_sample_version,
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            project,
            "trial_evidence.bind",
            idempotency_key_hash,
            payload_hash,
        )
        if replay is not None:
            return TrialExecutionCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        round_pair = self._execution_round(project, round_id, for_update=True)
        if round_pair is None:
            return None
        trial_round = round_pair[1]
        self._require_round_version(
            trial_round,
            expected_round_optimistic_version,
            TrialRoundState.RUNNING,
        )
        file_revision = _optional_doc("NPI File Revision", str(file_revision_global_id))
        if file_revision is None:
            raise TrialExecutionReferenceUnavailable()
        file_snapshot = _file_revision_source_snapshot(file_revision)
        if (
            str(file_snapshot["globalId"]) != str(file_revision_global_id)
            or str(file_revision.tenant_id) != str(project.tenant_id)
            or str(file_revision.project_global_id) != str(project_id)
            or str(file_revision.document_global_id) != str(round_id)
            or int(file_snapshot["fileOptimisticVersion"])
            != expected_file_optimistic_version
            or file_snapshot["scanState"] != "clean"
            or file_snapshot["isPrivate"] is not True
            or not _has_live_private_file_identity(file_revision)
        ):
            raise TrialExecutionReferenceUnavailable()
        if frappe.db.exists(
            "NPI Trial Evidence Reference",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project_id),
                "trial_round_global_id": str(round_id),
                "file_revision_global_id": str(file_revision_global_id),
            },
        ):
            raise TrialExecutionConflict()
        sample_revision = None
        if sample_batch_revision_global_id is not None:
            sample_revision = self._exact_sample_revision(
                project,
                round_id,
                sample_batch_revision_global_id,
            )
            if (
                sample_revision is None
                or sample_revision.sample_version != expected_sample_version
            ):
                raise TrialExecutionReferenceUnavailable()
        now = datetime.now(UTC)
        evidence = TrialEvidenceReference(
            global_id=uuid4(),
            tenant_id=str(project.tenant_id),
            project_global_id=project_id,
            trial_round_global_id=round_id,
            role=role,
            file_revision_global_id=file_revision_global_id,
            file_sha256=str(file_snapshot["sha256"]),
            file_size_bytes=int(file_snapshot["sizeBytes"]),
            file_mime_type=str(file_snapshot["mimeType"]),
            sample_batch_revision_global_id=(
                sample_revision.global_id if sample_revision else None
            ),
            sample_batch_revision_snapshot_hash=(
                sample_revision.snapshot_hash if sample_revision else None
            ),
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        with trial_command_write():
            receipt = self._insert_receipt(
                project,
                operation="trial_evidence.bind",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return TrialExecutionCommandOutcome(receipt, replayed=True)
            self._insert_evidence(evidence)
            self._append_audit(
                operation="trial_evidence.bind",
                global_id=evidence.global_id,
                object_version=1,
                summary={
                    "fileRevisionGlobalId": str(file_revision_global_id),
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "role": role.value,
                    "sampleBatchRevisionGlobalId": (
                        str(sample_revision.global_id) if sample_revision else None
                    ),
                    "trialRoundGlobalId": str(round_id),
                },
            )
            response = self._execution_workspace_for(project, trial_round)
            self._seal_receipt(
                receipt,
                target_object_type="trial_evidence_reference",
                target_global_id=evidence.global_id,
                response=response,
                updated_at=now,
            )
        return TrialExecutionCommandOutcome(response)

    def evidence_content(
        self,
        project_id: UUID,
        round_id: UUID,
        evidence_id: UUID,
    ) -> TrialEvidenceContentOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        if self._execution_round(project, round_id, for_update=True) is None:
            return None
        evidence_document = _optional_doc("NPI Trial Evidence Reference", str(evidence_id))
        if evidence_document is None:
            return None
        evidence = evidence_reference_from_snapshot(
            _json_object(evidence_document.evidence_snapshot)
        )
        if (
            evidence.global_id != evidence_id
            or evidence.tenant_id != str(project.tenant_id)
            or evidence.project_global_id != project_id
            or evidence.trial_round_global_id != round_id
            or evidence.snapshot_hash != str(evidence_document.snapshot_hash)
        ):
            return None
        file_revision = _optional_doc(
            "NPI File Revision",
            str(evidence.file_revision_global_id),
        )
        if file_revision is None or not _has_live_private_file_identity(file_revision):
            raise TrialExecutionReferenceUnavailable()
        snapshot = _file_revision_source_snapshot(file_revision)
        if (
            snapshot["scanState"] != "clean"
            or snapshot["isPrivate"] is not True
            or str(snapshot["sha256"]) != evidence.file_sha256
            or int(snapshot["sizeBytes"]) != evidence.file_size_bytes
            or str(snapshot["mimeType"]) != evidence.file_mime_type
            or str(file_revision.document_global_id) != str(round_id)
        ):
            raise TrialExecutionReferenceUnavailable()
        file_document = frappe.get_doc("File", str(snapshot["fileId"]))
        candidate = file_document.get_content()
        content = candidate.encode("utf-8") if isinstance(candidate, str) else candidate
        if (
            not isinstance(content, bytes)
            or not content
            or len(content) != evidence.file_size_bytes
            or hashlib.sha256(content).hexdigest() != evidence.file_sha256
        ):
            raise TrialExecutionReferenceUnavailable()
        with trial_command_write():
            self._append_access_audit(
                evidence,
                project_id=project_id,
                round_id=round_id,
            )
        return TrialEvidenceContentOutcome(
            content=content,
            file_name=str(snapshot["fileName"]),
            mime_type=str(snapshot["mimeType"]),
        )

    def _execution_workspace_for(
        self,
        project,
        trial_round: TrialRound,
    ) -> dict[str, Any]:
        round_id = trial_round.global_id
        input_locks = self._input_lock_history(project, round_id)
        actuals = self._actual_history(project, round_id)
        samples = self._sample_history(project, round_id)
        evidence = self._evidence_history(project, round_id)
        referenced_files = {value.file_revision_global_id for value in evidence}
        pending_files = []
        for document in self._file_history(project, round_id):
            snapshot = _file_revision_source_snapshot(document)
            if UUID(str(snapshot["globalId"])) in referenced_files:
                continue
            pending_files.append(
                {
                    "globalId": str(snapshot["globalId"]),
                    "optimisticVersion": int(snapshot["fileOptimisticVersion"]),
                    "fileName": str(snapshot["fileName"]),
                    "mimeType": str(snapshot["mimeType"]),
                    "sizeBytes": int(snapshot["sizeBytes"]),
                    "sha256": str(snapshot["sha256"]),
                    "scanState": str(snapshot["scanState"]),
                    "privacy": "private",
                }
            )
        return {
            "projectGlobalId": str(project.global_id),
            "round": _round_response(trial_round),
            "inputLocks": [value.snapshot_payload() | {"snapshotHash": value.snapshot_hash} for value in input_locks],
            "actualRevisions": [value.snapshot_payload() | {"snapshotHash": value.snapshot_hash} for value in actuals],
            "sampleBatchRevisions": [value.snapshot_payload() | {"snapshotHash": value.snapshot_hash} for value in samples],
            "evidence": [value.snapshot_payload() | {"snapshotHash": value.snapshot_hash} for value in evidence],
            "pendingFiles": pending_files,
            "missingFacts": self._missing_facts(input_locks, actuals, samples, evidence),
            "capabilities": {
                "machineImport": "unavailable",
                "erpQuality": "unavailable",
                "conclusion": "unavailable",
                "gateEffect": "unavailable",
                "approvedBaseline": "unavailable",
            },
            "permissions": self._execution_permissions(trial_round),
        }

    def _execution_permissions(self, trial_round: TrialRound) -> dict[str, bool]:
        allowed = self._is_internal_system_manager()
        return {
            "canPrepare": allowed and trial_round.current_state is TrialRoundState.PLANNED,
            "canStart": allowed and trial_round.current_state is TrialRoundState.PREPARED,
            "canRecordActual": allowed and trial_round.current_state is TrialRoundState.RUNNING,
            "canManageSamples": allowed and trial_round.current_state is TrialRoundState.RUNNING,
            "canManageEvidence": allowed and trial_round.current_state is TrialRoundState.RUNNING,
        }

    @staticmethod
    def _missing_facts(input_locks, actuals, samples, evidence) -> list[str]:
        missing: list[str] = []
        if not input_locks:
            missing.append("input_lock")
        if not actuals:
            missing.append("actual_context")
        else:
            latest = max(actuals, key=lambda value: value.actual_version)
            missing.extend(
                f"parameter:{value.definition_key}"
                for value in latest.parameters
                if value.state is TrialMeasurementState.NOT_MEASURED
            )
        if not samples:
            missing.append("sample_batch")
        if not evidence:
            missing.append("evidence")
        return sorted(missing)

    def _execution_round(
        self,
        project,
        round_id: UUID,
        *,
        for_update: bool = False,
    ) -> tuple[Any, TrialRound] | None:
        try:
            document = frappe.get_doc(
                "NPI Trial Round",
                str(round_id),
                for_update=for_update,
            )
        except frappe.DoesNotExistError:
            return None
        value = trial_round_from_snapshot(_json_object(document.round_snapshot))
        if (
            value.global_id != round_id
            or value.tenant_id != str(project.tenant_id)
            or value.project_global_id != UUID(str(project.global_id))
            or value.snapshot_hash != str(document.snapshot_hash)
        ):
            return None
        return document, value

    @staticmethod
    def _require_round_version(
        value: TrialRound,
        expected_version: int,
        expected_state: TrialRoundState,
    ) -> None:
        if value.optimistic_version != expected_version or value.current_state is not expected_state:
            raise TrialExecutionConflict()

    def _resolve_locked_references(
        self,
        project,
        trial_round: TrialRound,
        references: Sequence[Mapping[str, Any]],
    ) -> tuple[TrialLockedReference, ...]:
        requested: dict[TrialLockedReferenceKind, list[Mapping[str, Any]]] = {}
        for value in references:
            requested.setdefault(TrialLockedReferenceKind(value["kind"]), []).append(value)
        if any(
            len(values) != 1
            for kind, values in requested.items()
            if kind is not TrialLockedReferenceKind.CAVITY
        ):
            raise TrialExecutionReferenceUnavailable()
        tooling_requests = requested.get(TrialLockedReferenceKind.TOOLING_REVISION)
        tooling_request = tooling_requests[0] if tooling_requests else None
        if tooling_request is None:
            raise TrialExecutionReferenceUnavailable()
        tooling_document = self._reference_document(
            project,
            trial_round,
            TrialLockedReferenceKind.TOOLING_REVISION,
            tooling_request,
        )
        resolved = []
        documents: dict[TrialLockedReferenceKind, Any] = {
            TrialLockedReferenceKind.TOOLING_REVISION: tooling_document
        }
        for kind, values in requested.items():
            for request in values:
                if kind is not TrialLockedReferenceKind.CAVITY:
                    document = documents.get(kind)
                    if document is None:
                        document = self._reference_document(
                            project,
                            trial_round,
                            kind,
                            request,
                        )
                        documents[kind] = document
                    resolved.append(
                        TrialLockedReference(
                            global_id=request["globalId"],
                            kind=kind,
                            optimistic_version=_reference_version(kind, document),
                            snapshot_hash=str(document.snapshot_hash),
                        )
                    )
                    continue
                cavity_snapshot = _json_array(tooling_document.cavity_snapshot)
                match = next(
                    (
                        value
                        for value in cavity_snapshot
                        if str(value.get("globalId")) == str(request["globalId"])
                    ),
                    None,
                )
                if (
                    match is None
                    or int(tooling_document.revision_number)
                    != int(request["expectedOptimisticVersion"])
                ):
                    raise TrialExecutionReferenceUnavailable()
                resolved.append(
                    TrialLockedReference(
                        global_id=request["globalId"],
                        kind=kind,
                        optimistic_version=int(tooling_document.revision_number),
                        snapshot_hash=sha256_json(match),
                    )
                )
        self._validate_reference_set(trial_round, documents)
        return tuple(resolved)

    def _reference_document(self, project, trial_round, kind, request):
        doctype, project_field = {
            TrialLockedReferenceKind.DESIGN_BASELINE: ("NPI Document Baseline", "project_global_id"),
            TrialLockedReferenceKind.PART_REVISION: ("NPI Engineering Part Revision", "originating_project_global_id"),
            TrialLockedReferenceKind.TOOLING_REVISION: ("NPI Tooling Revision", "project_global_id"),
            TrialLockedReferenceKind.TOOLING_SET: ("NPI Tooling Set", "project_global_id"),
            TrialLockedReferenceKind.TOOLING_SET_BINDING: ("NPI Tooling Set Revision Binding", "project_global_id"),
            TrialLockedReferenceKind.PROCESS_CHAIN: ("NPI Tooling Process Chain Revision", "project_global_id"),
            TrialLockedReferenceKind.INSPECTION_DOCUMENT: ("NPI Document Revision", "project_global_id"),
        }.get(kind, (None, None))
        if doctype is None:
            raise TrialExecutionReferenceUnavailable()
        document = _optional_doc(doctype, str(request["globalId"]))
        if (
            document is None
            or str(document.global_id) != str(request["globalId"])
            or str(document.tenant_id) != str(project.tenant_id)
            or str(getattr(document, project_field)) != str(project.global_id)
            or _reference_version(kind, document)
            != int(request["expectedOptimisticVersion"])
            or not _valid_hash(getattr(document, "snapshot_hash", None))
        ):
            raise TrialExecutionReferenceUnavailable()
        if (
            kind is TrialLockedReferenceKind.TOOLING_REVISION
            and str(document.tooling_master_global_id)
            != str(trial_round.tooling_master_global_id)
        ):
            raise TrialExecutionReferenceUnavailable()
        if (
            kind is TrialLockedReferenceKind.TOOLING_SET
            and str(document.tooling_master_global_id)
            != str(trial_round.tooling_master_global_id)
        ):
            raise TrialExecutionReferenceUnavailable()
        resolved_hash = str(document.snapshot_hash)
        if kind is TrialLockedReferenceKind.INSPECTION_DOCUMENT:
            resolved_hash = self._released_inspection_snapshot(project, document)
        return _ResolvedReferenceDocument(
            document=document,
            optimistic_version=_reference_version(kind, document),
            snapshot_hash=resolved_hash,
        )

    @staticmethod
    def _released_inspection_snapshot(project, revision) -> str:
        try:
            lifecycle = frappe.get_doc(
                "NPI Document Revision Lifecycle",
                str(revision.global_id),
                for_update=True,
            )
        except frappe.DoesNotExistError as error:
            raise TrialExecutionReferenceUnavailable() from error
        lifecycle_version = getattr(lifecycle, "lifecycle_version", None)
        release_event_global_id = getattr(lifecycle, "release_event_global_id", None)
        release_snapshot_hash = getattr(lifecycle, "release_snapshot_hash", None)
        try:
            release_event_id = UUID(str(release_event_global_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise TrialExecutionReferenceUnavailable() from error
        if (
            str(lifecycle.revision_global_id) != str(revision.global_id)
            or str(lifecycle.tenant_id) != str(project.tenant_id)
            or str(lifecycle.project_global_id) != str(project.global_id)
            or str(lifecycle.document_global_id) != str(revision.document_global_id)
            or str(lifecycle.current_state) != "released"
            or type(lifecycle_version) is not int
            or lifecycle_version < 1
            or str(release_event_id) != str(release_event_global_id).casefold()
            or not _valid_hash(release_snapshot_hash)
        ):
            raise TrialExecutionReferenceUnavailable()
        return sha256_json(
            {
                "revisionSnapshotHash": str(revision.snapshot_hash),
                "lifecycleVersion": lifecycle_version,
                "releaseEventGlobalId": str(release_event_id),
                "releaseSnapshotHash": str(release_snapshot_hash),
            }
        )

    @staticmethod
    def _validate_reference_set(trial_round, documents) -> None:
        revision = documents.get(TrialLockedReferenceKind.TOOLING_REVISION)
        tooling_set = documents.get(TrialLockedReferenceKind.TOOLING_SET)
        binding = documents.get(TrialLockedReferenceKind.TOOLING_SET_BINDING)
        if revision is None or tooling_set is None or binding is None:
            raise TrialExecutionReferenceUnavailable()
        if (
            str(binding.tooling_master_global_id) != str(trial_round.tooling_master_global_id)
            or str(binding.tooling_set_global_id) != str(tooling_set.global_id)
            or str(binding.tooling_set_snapshot_hash) != str(tooling_set.snapshot_hash)
            or str(binding.tooling_revision_global_id) != str(revision.global_id)
            or str(binding.tooling_revision_snapshot_hash) != str(revision.snapshot_hash)
        ):
            raise TrialExecutionReferenceUnavailable()

    def _material(self, value: Mapping[str, Any]) -> TrialMaterialObservation:
        return TrialMaterialObservation(
            source_system=value["sourceSystem"],
            source_object_id=value["sourceObjectId"],
            lot_batch_code=value["lotBatchCode"],
            label=value["label"],
            color=value.get("color"),
            additive=value.get("additive"),
            observed_at=value["observedAt"],
            confirmed_by_user_id=self.actor,
        )

    @staticmethod
    def _parameter_definitions(values) -> tuple[TrialParameterDefinition, ...]:
        return tuple(
            TrialParameterDefinition(
                key=value["key"],
                category=value["category"],
                value_kind=TrialParameterValueKind(value["valueKind"]),
                required=value["required"],
                unit=value.get("unit"),
                target_value=value.get("targetValue"),
                lower_limit=value.get("lowerLimit"),
                upper_limit=value.get("upperLimit"),
            )
            for value in values
        )

    def _actual_revision(
        self,
        project,
        round_id,
        input_lock,
        *,
        actual_global_id,
        actual_version,
        resources,
        material,
        environment,
        parameters,
        operator_user_id,
        execution_started_at,
        reason,
        created_at,
        predecessor=None,
    ) -> TrialRoundActualRevision:
        value = TrialRoundActualRevision(
            global_id=uuid4(),
            actual_global_id=actual_global_id,
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            trial_round_global_id=round_id,
            input_lock_revision_global_id=input_lock.global_id,
            input_lock_revision_snapshot_hash=input_lock.snapshot_hash,
            actual_version=actual_version,
            predecessor_global_id=predecessor.global_id if predecessor else None,
            predecessor_snapshot_hash=predecessor.snapshot_hash if predecessor else None,
            acquisition_mode=TrialAcquisitionMode.MANUAL,
            resources=tuple(
                TrialActualResourceObservation(
                    kind=TrialActualResourceKind(item["kind"]),
                    source_system=item["sourceSystem"],
                    source_object_id=item["sourceObjectId"],
                    label=item["label"],
                )
                for item in resources
            ),
            material=self._material(material),
            environment=tuple(
                TrialEnvironmentObservation(
                    key=item["key"],
                    value=item["value"],
                    unit=item.get("unit"),
                    observed_at=item["observedAt"],
                )
                for item in environment
            ),
            parameters=tuple(
                TrialParameterObservation(
                    definition_key=item["definitionKey"],
                    state=TrialMeasurementState(item["state"]),
                    value=item.get("value"),
                    unit=item.get("unit"),
                    source=(
                        TrialAcquisitionMode(item["source"])
                        if item.get("source") is not None
                        else None
                    ),
                    observed_at=item.get("observedAt"),
                )
                for item in parameters
            ),
            operator_user_id=operator_user_id,
            confirmed_by_user_id=self.actor,
            execution_started_at=execution_started_at,
            reason=reason,
            created_at=created_at,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        validate_trial_actual_against_lock(input_lock, value)
        return value

    def _input_lock_history(self, project, round_id):
        return self._history(
            "NPI Trial Input Lock Revision",
            "lock_version asc, global_id asc",
            _MAX_INPUT_LOCKS,
            project,
            round_id,
            "lock_snapshot",
            input_lock_from_snapshot,
        )

    def _actual_history(self, project, round_id):
        return self._history(
            "NPI Trial Actual Revision",
            "actual_version asc, global_id asc",
            _MAX_ACTUALS,
            project,
            round_id,
            "actual_snapshot",
            actual_revision_from_snapshot,
        )

    def _sample_history(self, project, round_id):
        return self._history(
            "NPI Trial Sample Batch Revision",
            "sample_batch_global_id asc, sample_version asc, global_id asc",
            _MAX_SAMPLES,
            project,
            round_id,
            "sample_snapshot",
            sample_batch_from_snapshot,
        )

    def _evidence_history(self, project, round_id):
        return self._history(
            "NPI Trial Evidence Reference",
            "created_at asc, global_id asc",
            _MAX_EVIDENCE,
            project,
            round_id,
            "evidence_snapshot",
            evidence_reference_from_snapshot,
        )

    def _history(self, doctype, order_by, maximum, project, round_id, field, factory):
        names = frappe.get_all(
            doctype,
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "trial_round_global_id": str(round_id),
            },
            pluck="name",
            order_by=order_by,
            limit_page_length=maximum + 1,
        )
        if len(names) > maximum:
            raise RuntimeError(f"Persisted {doctype} collection exceeds its safe bound.")
        values = []
        for name in names:
            document = frappe.get_doc(doctype, str(name))
            value = factory(_json_object(getattr(document, field)))
            if (
                value.tenant_id != str(project.tenant_id)
                or value.project_global_id != UUID(str(project.global_id))
                or value.trial_round_global_id != round_id
                or value.snapshot_hash != str(document.snapshot_hash)
            ):
                raise RuntimeError(f"Persisted {doctype} integrity failed.")
            values.append(value)
        return values

    def _file_history(self, project, round_id):
        names = frappe.get_all(
            "NPI File Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(round_id),
            },
            pluck="name",
            order_by="revision asc, global_id asc",
            limit_page_length=_MAX_PENDING_FILES + 1,
        )
        if len(names) > _MAX_PENDING_FILES:
            raise RuntimeError("Persisted Trial File Revision collection exceeds its safe bound.")
        return [frappe.get_doc("NPI File Revision", str(name)) for name in names]

    def _current_input_lock(self, project, round_id, *, for_update):
        return self._latest(
            "NPI Trial Input Lock Revision",
            "lock_version desc, global_id desc",
            project,
            round_id,
            "lock_snapshot",
            input_lock_from_snapshot,
            for_update,
        )

    def _current_actual(self, project, round_id, *, for_update):
        return self._latest(
            "NPI Trial Actual Revision",
            "actual_version desc, global_id desc",
            project,
            round_id,
            "actual_snapshot",
            actual_revision_from_snapshot,
            for_update,
        )

    def _current_sample(self, project, round_id, batch_id, *, for_update):
        names = frappe.get_all(
            "NPI Trial Sample Batch Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "trial_round_global_id": str(round_id),
                "sample_batch_global_id": str(batch_id),
            },
            pluck="name",
            order_by="sample_version desc, global_id desc",
            limit_page_length=2,
        )
        if not names:
            return None
        document = frappe.get_doc(
            "NPI Trial Sample Batch Revision",
            str(names[0]),
            for_update=for_update,
        )
        value = sample_batch_from_snapshot(_json_object(document.sample_snapshot))
        return value if value.snapshot_hash == str(document.snapshot_hash) else None

    def _latest(self, doctype, order_by, project, round_id, field, factory, for_update):
        names = frappe.get_all(
            doctype,
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "trial_round_global_id": str(round_id),
            },
            pluck="name",
            order_by=order_by,
            limit_page_length=2,
        )
        if not names:
            return None
        document = frappe.get_doc(doctype, str(names[0]), for_update=for_update)
        value = factory(_json_object(getattr(document, field)))
        return value if value.snapshot_hash == str(document.snapshot_hash) else None

    def _exact_input_lock(self, project, round_id, revision_id):
        document = _optional_doc("NPI Trial Input Lock Revision", str(revision_id))
        if document is None:
            return None
        value = input_lock_from_snapshot(_json_object(document.lock_snapshot))
        if (
            value.global_id != revision_id
            or value.tenant_id != str(project.tenant_id)
            or value.project_global_id != UUID(str(project.global_id))
            or value.trial_round_global_id != round_id
            or value.snapshot_hash != str(document.snapshot_hash)
        ):
            return None
        return value

    def _exact_sample_revision(self, project, round_id, revision_id):
        document = _optional_doc("NPI Trial Sample Batch Revision", str(revision_id))
        if document is None:
            return None
        value = sample_batch_from_snapshot(_json_object(document.sample_snapshot))
        if (
            value.global_id != revision_id
            or value.tenant_id != str(project.tenant_id)
            or value.project_global_id != UUID(str(project.global_id))
            or value.trial_round_global_id != round_id
            or value.snapshot_hash != str(document.snapshot_hash)
        ):
            return None
        return value

    @staticmethod
    def _save_round(document, value: TrialRound) -> None:
        document.current_state = value.current_state.value
        document.current_event_global_id = str(value.current_event_global_id)
        document.optimistic_version = value.optimistic_version
        document.round_snapshot = value.snapshot_payload()
        document.snapshot_hash = value.snapshot_hash
        document.save()

    @staticmethod
    def _insert_input_lock(value) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Input Lock Revision",
                "global_id": str(value.global_id),
                "input_lock_global_id": str(value.input_lock_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "trial_plan_revision": str(value.trial_plan_revision_global_id),
                "trial_plan_revision_global_id": str(value.trial_plan_revision_global_id),
                "trial_plan_revision_snapshot_hash": value.trial_plan_revision_snapshot_hash,
                "lock_version": value.lock_version,
                "predecessor_global_id": None,
                "predecessor_snapshot_hash": None,
                "reference_snapshot": [item.snapshot_payload() for item in value.references],
                "material_snapshot": value.material.snapshot_payload(),
                "parameter_definition_snapshot": [item.snapshot_payload() for item in value.parameter_definitions],
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "lock_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_actual(value) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Actual Revision",
                "global_id": str(value.global_id),
                "actual_global_id": str(value.actual_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "input_lock_revision": str(value.input_lock_revision_global_id),
                "input_lock_revision_global_id": str(value.input_lock_revision_global_id),
                "input_lock_revision_snapshot_hash": value.input_lock_revision_snapshot_hash,
                "actual_version": value.actual_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "acquisition_mode": value.acquisition_mode.value,
                "resource_snapshot": [item.snapshot_payload() for item in value.resources],
                "material_snapshot": value.material.snapshot_payload(),
                "environment_snapshot": [item.snapshot_payload() for item in value.environment],
                "parameter_snapshot": [item.snapshot_payload() for item in value.parameters],
                "operator_user_id": value.operator_user_id,
                "confirmed_by_user_id": value.confirmed_by_user_id,
                "execution_started_at": _database_datetime(value.execution_started_at),
                "reason": value.reason,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "actual_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_sample(value) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Sample Batch Revision",
                "global_id": str(value.global_id),
                "sample_batch_global_id": str(value.sample_batch_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "input_lock_revision": str(value.input_lock_revision_global_id),
                "input_lock_revision_global_id": str(value.input_lock_revision_global_id),
                "input_lock_revision_snapshot_hash": value.input_lock_revision_snapshot_hash,
                "sample_version": value.sample_version,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "label": value.label,
                "cavity_snapshot": [str(item) for item in value.cavity_global_ids],
                "material_snapshot_hash": value.material_snapshot_hash,
                "quantity": value.quantity,
                "unit": value.unit,
                "packaging": value.packaging,
                "destination": value.destination,
                "feedback_text": value.feedback_text,
                "feedback_source": value.feedback_source,
                "feedback_observed_at": _database_datetime(value.feedback_observed_at) if value.feedback_observed_at else None,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "sample_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_evidence(value) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Trial Evidence Reference",
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "trial_round": str(value.trial_round_global_id),
                "trial_round_global_id": str(value.trial_round_global_id),
                "role": value.role.value,
                "sample_batch_revision": str(value.sample_batch_revision_global_id) if value.sample_batch_revision_global_id else None,
                "sample_batch_revision_global_id": str(value.sample_batch_revision_global_id) if value.sample_batch_revision_global_id else None,
                "sample_batch_revision_snapshot_hash": value.sample_batch_revision_snapshot_hash,
                "file_revision": str(value.file_revision_global_id),
                "file_revision_global_id": str(value.file_revision_global_id),
                "file_sha256": value.file_sha256,
                "file_size_bytes": value.file_size_bytes,
                "file_mime_type": value.file_mime_type,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "evidence_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    def _append_access_audit(self, evidence, *, project_id, round_id) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation="trial_evidence.content.read",
            global_id=evidence.global_id,
            object_version=1,
            result="accessed",
            input_summary={
                "fileRevisionGlobalId": str(evidence.file_revision_global_id),
                "projectId": str(project_id),
                "requestId": self.request_id,
                "trialRoundGlobalId": str(round_id),
            },
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

    def _next_file_revision(self, project, round_id) -> int:
        rows = frappe.get_all(
            "NPI File Revision",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(round_id),
            },
            fields=["revision"],
            order_by="revision desc, global_id desc",
            limit_page_length=1,
        )
        return int(rows[0].revision) + 1 if rows else 1


def _reference_version(kind: TrialLockedReferenceKind, document) -> int:
    if isinstance(document, _ResolvedReferenceDocument):
        return document.optimistic_version
    field = {
        TrialLockedReferenceKind.DESIGN_BASELINE: "baseline_version",
        TrialLockedReferenceKind.PART_REVISION: "revision_number",
        TrialLockedReferenceKind.TOOLING_REVISION: "revision_number",
        TrialLockedReferenceKind.PROCESS_CHAIN: "chain_version",
        TrialLockedReferenceKind.INSPECTION_DOCUMENT: "optimistic_version",
    }.get(kind)
    return 1 if field is None else int(getattr(document, field))


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def _json_array(value: object) -> list[dict[str, Any]]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise TrialExecutionReferenceUnavailable()
    return [dict(item) for item in parsed]


def _observe_trial_upload(file_name: object, content: object) -> _UploadObservation:
    normalized = validate_file_name(file_name)
    if not isinstance(content, bytes) or not content:
        raise RequestValidationFailed([{"path": "file", "message": _("Select a non-empty file.")}])
    if len(content) > _MAX_UPLOAD_BYTES:
        raise RequestValidationFailed([{"path": "file", "message": _("The file exceeds the supported infrastructure limit.")}])
    mime_type = (mimetypes.guess_type(normalized)[0] or "application/octet-stream").casefold()
    if mime_type == "text/csv":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RequestValidationFailed([{"path": "file", "message": _("The file name extension does not match the observed file content.")}]) from error
    elif mime_type in {"video/mp4", "video/quicktime"}:
        if len(content) < 12 or content[4:8] != b"ftyp":
            raise RequestValidationFailed([{"path": "file", "message": _("The file name extension does not match the observed file content.")}])
    else:
        signatures = {
            "application/pdf": content.startswith(b"%PDF-"),
            "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/jpeg": content.startswith(b"\xff\xd8\xff"),
            "image/gif": content.startswith((b"GIF87a", b"GIF89a")),
            "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
        }
        if mime_type not in signatures or not signatures[mime_type]:
            raise RequestValidationFailed([{"path": "file", "message": _("Select a supported value.")}])
    if mime_type not in _TRIAL_UPLOAD_MIME_TYPES:
        raise RequestValidationFailed([{"path": "file", "message": _("Select a supported value.")}])
    return _UploadObservation(
        file_name=normalized,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        frappe_content_hash=hashlib.md5(content, usedforsecurity=False).hexdigest(),
    )


def _require_storage_capacity(size_bytes: int) -> None:
    from frappe.utils.file_manager import get_max_file_size

    configured_limit = get_max_file_size()
    if type(configured_limit) is not int or configured_limit < 1:
        raise RuntimeError("The configured Frappe upload limit is invalid.")
    if size_bytes > configured_limit:
        raise RequestValidationFailed([{"path": "file", "message": _("The file exceeds the configured upload limit.")}])


def _register_orphan_cleanup(file_document) -> None:
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
            remaining = frappe.db.get_value("File", {"file_url": file_url}, "name")
            if not remaining:
                file_path.unlink(missing_ok=True)
        except Exception as error:
            from npi_core.api import record_safe_diagnostic

            record_safe_diagnostic(
                code="TRIAL_ORPHAN_FILE_CLEANUP_FAILED",
                title="NPI Trial orphan file cleanup failed",
                exception_type=type(error).__name__,
            )

    frappe.db.after_rollback.add(cleanup_after_rollback)


def _file_revision_source_snapshot(document) -> dict[str, Any]:
    from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
        file_revision_source_snapshot,
    )

    return file_revision_source_snapshot(document)


def _has_live_private_file_identity(document) -> bool:
    from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
        has_live_private_file_identity,
    )

    return has_live_private_file_identity(document)


@contextmanager
def _file_revision_write_scope() -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, missing)
    setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, FILE_REVISION_COMMAND_FLAG)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, previous)
