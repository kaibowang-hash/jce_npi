from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.documents.domain import (
    DocumentUnavailable,
    DocumentVersionConflict,
    sha256_json,
)
from npi_core.documents.frappe_repository import (
    DocumentCommandOutcome,
    FrappeDocumentRepository,
    _association_matches_live_file,
    _bounded_documents,
    _controlled_document_write_scope,
    _database_datetime,
    _date_value,
    _datetime_value,
    _document_matches_project,
    _record_value,
)
from npi_core.documents.frappe_validation import (
    document_release_command_write,
)
from npi_core.documents.release_domain import (
    DocumentConfirmation,
    DocumentConfirmationType,
    DocumentLifecycleEvent,
    DocumentLifecycleEventType,
    DocumentLifecycleState,
    DocumentReleaseFileEvidence,
    DocumentReleaseIntegrityBlocked,
    DocumentReleasePolicyReference,
    DocumentReleasePolicyState,
    DocumentReleasePolicyUnavailable,
    DocumentReleasePolicyVersion,
    DocumentReviewCycle,
    DocumentReviewDecision,
    DocumentReviewEvidence,
    DocumentReviewStateConflict,
    DocumentRevisionLifecycle,
    confirm_document_review,
    release_document_revision,
    submit_document_review,
    terminate_released_document_revision,
)
from npi_core.documents.release_frappe import (
    confirmation_value,
    lifecycle_event_value,
    lifecycle_value,
    release_policy_value,
    review_cycle_value,
)
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
    has_live_private_file_identity,
)
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.request_security import document_release_routes_are_disabled


_MAX_RELEASE_ROWS = 64
_POLICY_FIELDS = [
    "global_id",
    "document_release_policy",
    "tenant_id",
    "project_global_id",
    "policy_global_id",
    "policy_key",
    "policy_version",
    "title",
    "publication_state",
    "submitter_user_ids",
    "reviewer_assignments",
    "required_approval_count",
    "release_authority_user_ids",
    "supersede_authority_user_ids",
    "obsolete_authority_user_ids",
    "confirmation_method",
    "required_scan_state",
    "require_live_private_identity",
    "require_sha256_match",
    "supersede_requires_released_successor",
    "supersede_requires_later_revision",
    "supersede_requires_successor_effective_date",
    "snapshot_hash",
]


class FrappeDocumentReleaseRepository(FrappeDocumentRepository):
    """Exact review/release transactions over immutable P5 document revisions."""

    def _detail_for(self, project, document) -> dict[str, Any]:
        detail = super()._detail_for(project, document)
        can_view_release = (
            not self.principal.is_external
            and "NPI API User" in self.principal.roles
        )
        release_routes_enabled = not document_release_routes_are_disabled()
        policy_options = (
            self._published_release_policy_options(project)
            if can_view_release
            else ()
        )
        revision_histories = (
            self._release_revision_histories(
                project,
                document,
                revision_ids=tuple(
                    str(value["globalId"]) for value in detail["revisions"]
                ),
                policy_options=policy_options,
                commands_enabled=release_routes_enabled,
            )
            if can_view_release
            else ()
        )
        permission_values = {
            key: any(
                bool(value["capabilities"][key])
                for value in revision_histories
            )
            for key in (
                "submitReview",
                "resubmitReview",
                "review",
                "approve",
                "release",
                "supersede",
                "obsolete",
            )
        }
        detail["permissions"].update(permission_values)
        detail["releaseWorkspace"] = {
            "available": can_view_release,
            "commandsEnabled": can_view_release and release_routes_enabled,
            "reasonCode": (
                "available"
                if can_view_release and release_routes_enabled
                else (
                    "routes_disabled"
                    if can_view_release
                    else "permission_unavailable"
                )
            ),
            "policies": list(policy_options),
            "revisions": list(revision_histories),
        }
        return detail

    def _published_release_policy_options(
        self,
        project,
    ) -> tuple[dict[str, Any], ...]:
        rows = _bounded_documents(
            "NPI Document Release Policy Version",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "publication_state": DocumentReleasePolicyState.PUBLISHED.value,
            },
            order_by="policy_key asc, policy_version desc, global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        result = []
        for row in rows:
            try:
                policy = self._load_exact_release_policy(
                    project,
                    policy_global_id=UUID(str(row.policy_global_id)),
                    policy_version=int(row.policy_version),
                    snapshot_hash=str(row.snapshot_hash),
                )
            except DocumentReleasePolicyUnavailable:
                continue
            if not policy.permits_submit(self.actor):
                continue
            result.append(
                {
                    "globalId": str(policy.policy_global_id),
                    "version": policy.policy_version,
                    "snapshotHash": policy.snapshot_hash,
                    "key": policy.policy_key,
                    "title": policy.title,
                    "requiredApprovalCount": policy.required_approval_count,
                    "confirmationMethod": policy.confirmation_method,
                }
            )
        return tuple(result)

    def _release_revision_histories(
        self,
        project,
        document,
        *,
        revision_ids: Sequence[str],
        policy_options: Sequence[Mapping[str, object]],
        commands_enabled: bool,
    ) -> tuple[dict[str, Any], ...]:
        scope = {
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "document_global_id": str(document.global_id),
        }
        lifecycle_rows = _bounded_documents(
            "NPI Document Revision Lifecycle",
            scope,
            order_by="revision_global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        cycle_rows = _bounded_documents(
            "NPI Document Review Cycle",
            scope,
            order_by="revision_global_id asc, cycle_number asc, global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        confirmation_rows = _bounded_documents(
            "NPI Document Confirmation",
            scope,
            order_by="confirmed_at asc, global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        event_rows = _bounded_documents(
            "NPI Document Lifecycle Event",
            scope,
            order_by="occurred_at asc, global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        lifecycles = {
            str(value.revision_global_id): self._query_lifecycle(value)
            for value in lifecycle_rows
        }
        cycles = tuple(self._query_cycle(value) for value in cycle_rows)
        confirmations = tuple(
            self._query_confirmation(value) for value in confirmation_rows
        )
        events = tuple(self._query_event(value) for value in event_rows)
        exact_revision_ids = set(revision_ids)
        if (
            set(lifecycles) - exact_revision_ids
            or {
                str(value.revision_global_id) for value in cycles
            } - exact_revision_ids
            or {
                str(value.revision_global_id) for value in confirmations
            } - exact_revision_ids
            or {
                str(value.revision_global_id) for value in events
            } - exact_revision_ids
        ):
            raise DocumentReviewStateConflict()
        result = []
        for revision_id in revision_ids:
            lifecycle = lifecycles.get(revision_id)
            revision_cycles = tuple(
                value
                for value in cycles
                if str(value.revision_global_id) == revision_id
            )
            revision_confirmations = tuple(
                value
                for value in confirmations
                if str(value.revision_global_id) == revision_id
            )
            revision_events = tuple(
                value
                for value in events
                if str(value.revision_global_id) == revision_id
            )
            capabilities = self._release_capabilities(
                lifecycle,
                revision_cycles,
                revision_confirmations,
                revision_events,
                policy_options=policy_options,
                commands_enabled=commands_enabled,
                project=project,
            )
            result.append(
                {
                    "revisionId": revision_id,
                    "lifecycle": self._lifecycle_response(lifecycle),
                    "capabilities": capabilities,
                    "cycles": [
                        self._cycle_response(
                            value,
                            lifecycle,
                            revision_confirmations,
                            revision_events,
                        )
                        for value in revision_cycles
                    ],
                    "confirmations": [
                        self._confirmation_response(value)
                        for value in revision_confirmations
                    ],
                    "events": [
                        self._event_response(value)
                        for value in revision_events
                    ],
                }
            )
        return tuple(result)

    @staticmethod
    def _query_lifecycle(document) -> DocumentRevisionLifecycle:
        try:
            value = lifecycle_value(document)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReviewStateConflict() from error
        if str(value.revision_global_id) != str(document.name):
            raise DocumentReviewStateConflict()
        return value

    @staticmethod
    def _query_cycle(document) -> DocumentReviewCycle:
        try:
            return review_cycle_value(document)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReviewStateConflict() from error

    @staticmethod
    def _query_confirmation(document) -> DocumentConfirmation:
        try:
            return confirmation_value(document)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReviewStateConflict() from error

    @staticmethod
    def _query_event(document) -> DocumentLifecycleEvent:
        try:
            return lifecycle_event_value(document)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReviewStateConflict() from error

    def _release_capabilities(
        self,
        lifecycle: DocumentRevisionLifecycle | None,
        cycles: Sequence[DocumentReviewCycle],
        confirmations: Sequence[DocumentConfirmation],
        events: Sequence[DocumentLifecycleEvent],
        *,
        policy_options: Sequence[Mapping[str, object]],
        commands_enabled: bool,
        project,
    ) -> dict[str, bool]:
        values = {
            "submitReview": False,
            "resubmitReview": False,
            "review": False,
            "approve": False,
            "release": False,
            "supersede": False,
            "obsolete": False,
        }
        if not commands_enabled:
            return values
        if lifecycle is None:
            values["submitReview"] = bool(policy_options)
            return values
        last_event = next(
            (
                value
                for value in reversed(events)
                if value.to_version == lifecycle.version
            ),
            None,
        )
        if lifecycle.state is DocumentLifecycleState.DRAFT:
            values["resubmitReview"] = bool(
                policy_options
                and last_event is not None
                and last_event.event_type
                is DocumentLifecycleEventType.REVIEW_REJECTED
            )
            return values
        active_cycle = next(
            (
                value
                for value in cycles
                if value.global_id
                in {
                    lifecycle.active_cycle_global_id,
                    lifecycle.approved_cycle_global_id,
                }
            ),
            None,
        )
        if active_cycle is None:
            return values
        try:
            policy = self._load_exact_release_policy(
                project,
                policy_global_id=active_cycle.policy_ref.global_id,
                policy_version=active_cycle.policy_ref.version,
                snapshot_hash=active_cycle.policy_ref.snapshot_hash,
            )
        except DocumentReleasePolicyUnavailable:
            return values
        if lifecycle.state is DocumentLifecycleState.IN_REVIEW:
            actor_slot = next(
                (
                    value.slot_key
                    for value in active_cycle.reviewer_assignments
                    if value.user_id.casefold() == self.actor.casefold()
                ),
                None,
            )
            already_confirmed = any(
                value.cycle_global_id == active_cycle.global_id
                and value.authority_slot == actor_slot
                for value in confirmations
            )
            values["review"] = bool(actor_slot and not already_confirmed)
            values["approve"] = values["review"]
        elif lifecycle.state is DocumentLifecycleState.APPROVED:
            values["release"] = policy.permits_release(self.actor)
        elif lifecycle.state is DocumentLifecycleState.RELEASED:
            values["supersede"] = policy.permits_supersede(self.actor)
            values["obsolete"] = policy.permits_obsolete(self.actor)
        return values

    @staticmethod
    def _lifecycle_response(
        lifecycle: DocumentRevisionLifecycle | None,
    ) -> dict[str, Any]:
        if lifecycle is None:
            return {
                "state": DocumentLifecycleState.DRAFT.value,
                "version": 0,
                "activeCycleId": None,
                "approvedCycleId": None,
                "approvedEventId": None,
                "releaseEventId": None,
                "releaseSnapshotHash": None,
                "replacementRevisionId": None,
                "replacementEffectiveDate": None,
                "terminalEventId": None,
            }
        return {
            "state": lifecycle.state.value,
            "version": lifecycle.version,
            "activeCycleId": (
                str(lifecycle.active_cycle_global_id)
                if lifecycle.active_cycle_global_id
                else None
            ),
            "approvedCycleId": (
                str(lifecycle.approved_cycle_global_id)
                if lifecycle.approved_cycle_global_id
                else None
            ),
            "approvedEventId": (
                str(lifecycle.approved_event_global_id)
                if lifecycle.approved_event_global_id
                else None
            ),
            "releaseEventId": (
                str(lifecycle.release_event_global_id)
                if lifecycle.release_event_global_id
                else None
            ),
            "releaseSnapshotHash": lifecycle.release_snapshot_hash,
            "replacementRevisionId": (
                str(lifecycle.replacement_revision_global_id)
                if lifecycle.replacement_revision_global_id
                else None
            ),
            "replacementEffectiveDate": (
                lifecycle.replacement_effective_date.isoformat()
                if lifecycle.replacement_effective_date
                else None
            ),
            "terminalEventId": (
                str(lifecycle.terminal_event_global_id)
                if lifecycle.terminal_event_global_id
                else None
            ),
        }

    @staticmethod
    def _cycle_response(
        cycle: DocumentReviewCycle,
        lifecycle: DocumentRevisionLifecycle | None,
        confirmations: Sequence[DocumentConfirmation],
        events: Sequence[DocumentLifecycleEvent],
    ) -> dict[str, Any]:
        cycle_confirmations = tuple(
            value
            for value in confirmations
            if value.cycle_global_id == cycle.global_id
        )
        by_slot = {
            value.authority_slot: value
            for value in cycle_confirmations
            if value.confirmation_type
            in {
                DocumentConfirmationType.REVIEW_APPROVE,
                DocumentConfirmationType.REVIEW_REJECT,
            }
        }
        if any(
            value.cycle_global_id == cycle.global_id
            and value.event_type is DocumentLifecycleEventType.REVIEW_REJECTED
            for value in events
        ):
            state = "rejected"
        elif (
            lifecycle is not None
            and lifecycle.approved_cycle_global_id == cycle.global_id
        ):
            state = "approved"
        elif (
            lifecycle is not None
            and lifecycle.active_cycle_global_id == cycle.global_id
        ):
            state = "active"
        else:
            state = "closed"
        return {
            "globalId": str(cycle.global_id),
            "cycleNumber": cycle.cycle_number,
            "state": state,
            "policy": {
                "globalId": str(cycle.policy_ref.global_id),
                "version": cycle.policy_ref.version,
                "snapshotHash": cycle.policy_ref.snapshot_hash,
            },
            "evidenceSnapshotHash": cycle.evidence.snapshot_hash,
            "fileEvidence": [
                {
                    "fileRevisionId": str(value.file_revision_global_id),
                    "associationId": str(value.association_global_id),
                    "mimeType": value.mime_type,
                    "sizeBytes": value.size_bytes,
                    "sha256": value.sha256,
                    "scanState": value.scan_state,
                    "scanObservedAt": value.scan_observed_at.isoformat(),
                    "uploadedByUserId": value.uploaded_by_user_id,
                    "uploadedAt": value.uploaded_at.isoformat(),
                }
                for value in cycle.evidence.files
            ],
            "reviewerAssignments": [
                {
                    "slotKey": value.slot_key,
                    "userId": value.user_id,
                    "state": (
                        "approved"
                        if (
                            by_slot.get(value.slot_key)
                            and by_slot[value.slot_key].confirmation_type
                            is DocumentConfirmationType.REVIEW_APPROVE
                        )
                        else (
                            "rejected"
                            if by_slot.get(value.slot_key)
                            else "pending"
                        )
                    ),
                    "confirmationId": (
                        str(by_slot[value.slot_key].global_id)
                        if value.slot_key in by_slot
                        else None
                    ),
                }
                for value in cycle.reviewer_assignments
            ],
            "requiredApprovalCount": cycle.required_approval_count,
            "priorRejectedCycleId": (
                str(cycle.prior_rejected_cycle_global_id)
                if cycle.prior_rejected_cycle_global_id
                else None
            ),
            "submittedByUserId": cycle.submitted_by_user_id,
            "submittedAt": cycle.submitted_at.isoformat(),
            "requestId": cycle.request_id,
            "traceId": cycle.trace_id,
            "snapshotHash": cycle.snapshot_hash,
        }

    @staticmethod
    def _confirmation_response(
        value: DocumentConfirmation,
    ) -> dict[str, Any]:
        return {
            "globalId": str(value.global_id),
            "cycleId": str(value.cycle_global_id),
            "type": value.confirmation_type.value,
            "actorUserId": value.actor_user_id,
            "authoritySlot": value.authority_slot,
            "confirmationMethod": value.confirmation_method,
            "confirmationIntent": value.confirmation_intent,
            "reason": value.reason,
            "confirmedAt": value.confirmed_at.isoformat(),
            "requestId": value.request_id,
            "traceId": value.trace_id,
            "evidenceHash": value.evidence_hash,
        }

    @staticmethod
    def _event_response(value: DocumentLifecycleEvent) -> dict[str, Any]:
        return {
            "globalId": str(value.global_id),
            "type": value.event_type.value,
            "fromState": value.from_state.value,
            "toState": value.to_state.value,
            "fromVersion": value.from_version,
            "toVersion": value.to_version,
            "cycleId": str(value.cycle_global_id),
            "confirmationHashes": list(value.confirmation_hashes),
            "replacementRevisionId": (
                str(value.replacement_revision_global_id)
                if value.replacement_revision_global_id
                else None
            ),
            "replacementEffectiveDate": (
                value.replacement_effective_date.isoformat()
                if value.replacement_effective_date
                else None
            ),
            "actorUserId": value.actor_user_id,
            "occurredAt": value.occurred_at.isoformat(),
            "requestId": value.request_id,
            "traceId": value.trace_id,
            "eventHash": value.event_hash,
        }

    def submit_review(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        confirmation_intent: str,
        confirmed: bool,
    ) -> DocumentCommandOutcome | None:
        self._require_confirmation_assertion(
            confirmation_intent,
            confirmed,
            expected="submit_review",
        )
        return self._submit_review(
            project_id,
            document_id,
            revision_id,
            idempotency_key=idempotency_key,
            expected_document_version=expected_document_version,
            expected_lifecycle_version=expected_lifecycle_version,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            policy_snapshot_hash=policy_snapshot_hash,
            confirmation_intent=confirmation_intent,
            confirmed=confirmed,
            prior_rejected_cycle_id=None,
            operation="document.review.submit",
        )

    def resubmit_review(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        prior_rejected_cycle_id: UUID,
        confirmation_intent: str,
        confirmed: bool,
    ) -> DocumentCommandOutcome | None:
        self._require_confirmation_assertion(
            confirmation_intent,
            confirmed,
            expected="resubmit_review",
        )
        return self._submit_review(
            project_id,
            document_id,
            revision_id,
            idempotency_key=idempotency_key,
            expected_document_version=expected_document_version,
            expected_lifecycle_version=expected_lifecycle_version,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            policy_snapshot_hash=policy_snapshot_hash,
            confirmation_intent=confirmation_intent,
            confirmed=confirmed,
            prior_rejected_cycle_id=prior_rejected_cycle_id,
            operation="document.review.resubmit",
        )

    def confirm_review(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        decision: DocumentReviewDecision,
        reason: str | None,
        confirmation_intent: str,
        confirmed: bool,
    ) -> DocumentCommandOutcome | None:
        self._require_confirmation_assertion(
            confirmation_intent,
            confirmed,
            expected="review_decision",
        )
        operation = (
            "document.review.approve"
            if decision is DocumentReviewDecision.APPROVE
            else "document.review.reject"
        )
        context = self._locked_release_context(
            project_id,
            document_id,
            revision_id,
        )
        if context is None:
            return None
        project, document, revision = context
        payload = {
            "revisionId": str(revision_id),
            "expectedDocumentVersion": expected_document_version,
            "expectedLifecycleVersion": expected_lifecycle_version,
            "decision": decision.value,
            "reason": reason,
            "confirmationIntent": confirmation_intent,
            "confirmed": confirmed,
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
        lifecycle_document, lifecycle = self._required_lifecycle(
            revision_id,
            expected_lifecycle_version,
        )
        if lifecycle.active_cycle_global_id is None:
            raise DocumentReviewStateConflict()
        cycle_document = self._locked_cycle(lifecycle.active_cycle_global_id)
        cycle = self._cycle_for_revision(cycle_document, revision_id)
        policy = self._load_exact_release_policy(
            project,
            policy_global_id=cycle.policy_ref.global_id,
            policy_version=cycle.policy_ref.version,
            snapshot_hash=cycle.policy_ref.snapshot_hash,
        )
        confirmations = self._review_confirmations(cycle)
        if any(value.actor_user_id.casefold() == self.actor.casefold()
               for value in confirmations):
            raise DocumentReviewStateConflict()
        approval_hashes = tuple(
            value.evidence_hash
            for value in confirmations
            if value.confirmation_type is DocumentConfirmationType.REVIEW_APPROVE
        )
        now = datetime.now(UTC)
        result = confirm_document_review(
            lifecycle=lifecycle,
            cycle=cycle,
            policy=policy,
            decision=decision,
            existing_approval_hashes=approval_hashes,
            confirmation_global_id=uuid4(),
            event_global_id=uuid4(),
            actor=self.actor,
            reason=reason,
            now=now,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        with _controlled_document_write_scope(), document_release_command_write():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project=project,
                document_id=document_id,
                operation=operation,
            )
            self._insert_confirmation(
                project,
                document,
                revision,
                cycle_document,
                result.confirmation,
            )
            self._insert_lifecycle_event(
                project,
                document,
                revision,
                cycle_document,
                result.event,
            )
            self._save_lifecycle(
                project,
                document,
                revision,
                lifecycle_document,
                result.lifecycle,
                result.event,
                now,
            )
            response = self._transition_response(
                project_id,
                document,
                revision_id,
                result.lifecycle,
                cycle,
                result.event,
                confirmation=result.confirmation,
            )
            self._append_release_audit(
                operation,
                project_id,
                document_id,
                revision_id,
                result.lifecycle,
                result.event,
            )
            self._seal_idempotency(receipt, response)
        return DocumentCommandOutcome(response)

    def release_revision(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        confirmation_intent: str,
        confirmed: bool,
    ) -> DocumentCommandOutcome | None:
        self._require_confirmation_assertion(
            confirmation_intent,
            confirmed,
            expected="release_revision",
        )
        operation = "document.release"
        context = self._locked_release_context(
            project_id,
            document_id,
            revision_id,
        )
        if context is None:
            return None
        project, document, revision = context
        payload = {
            "revisionId": str(revision_id),
            "expectedDocumentVersion": expected_document_version,
            "expectedLifecycleVersion": expected_lifecycle_version,
            "confirmationIntent": confirmation_intent,
            "confirmed": confirmed,
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
        lifecycle_document, lifecycle = self._required_lifecycle(
            revision_id,
            expected_lifecycle_version,
        )
        if lifecycle.approved_cycle_global_id is None:
            raise DocumentReviewStateConflict()
        cycle_document = self._locked_cycle(lifecycle.approved_cycle_global_id)
        cycle = self._cycle_for_revision(cycle_document, revision_id)
        policy = self._load_exact_release_policy(
            project,
            policy_global_id=cycle.policy_ref.global_id,
            policy_version=cycle.policy_ref.version,
            snapshot_hash=cycle.policy_ref.snapshot_hash,
        )
        approvals = tuple(
            value
            for value in self._review_confirmations(cycle)
            if value.confirmation_type is DocumentConfirmationType.REVIEW_APPROVE
        )
        approval_hashes = tuple(value.evidence_hash for value in approvals)
        self._require_exact_approval_event(lifecycle, cycle, approval_hashes)
        live_evidence, file_revisions = self._review_evidence(
            project,
            document,
            revision,
        )
        if live_evidence.canonical_dict() != cycle.evidence.canonical_dict():
            raise DocumentReleaseIntegrityBlocked()
        release_snapshot_hash = self._release_snapshot_hash(
            cycle,
            policy,
            approval_hashes,
            file_revisions,
        )
        now = datetime.now(UTC)
        result = release_document_revision(
            lifecycle=lifecycle,
            cycle=cycle,
            policy=policy,
            release_snapshot_hash=release_snapshot_hash,
            approval_confirmation_hashes=approval_hashes,
            confirmation_global_id=uuid4(),
            event_global_id=uuid4(),
            actor=self.actor,
            now=now,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        with _controlled_document_write_scope(), document_release_command_write():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project=project,
                document_id=document_id,
                operation=operation,
            )
            self._mark_file_revisions_released(file_revisions)
            self._insert_confirmation(
                project,
                document,
                revision,
                cycle_document,
                result.confirmation,
            )
            self._insert_lifecycle_event(
                project,
                document,
                revision,
                cycle_document,
                result.event,
            )
            self._save_lifecycle(
                project,
                document,
                revision,
                lifecycle_document,
                result.lifecycle,
                result.event,
                now,
            )
            response = self._transition_response(
                project_id,
                document,
                revision_id,
                result.lifecycle,
                cycle,
                result.event,
                confirmation=result.confirmation,
            )
            self._append_release_audit(
                operation,
                project_id,
                document_id,
                revision_id,
                result.lifecycle,
                result.event,
            )
            self._seal_idempotency(receipt, response)
        return DocumentCommandOutcome(response)

    def supersede_revision(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        replacement_revision_id: UUID,
        expected_replacement_lifecycle_version: int,
        reason: str,
        confirmation_intent: str,
        confirmed: bool,
    ) -> DocumentCommandOutcome | None:
        self._require_confirmation_assertion(
            confirmation_intent,
            confirmed,
            expected="supersede_revision",
        )
        return self._terminate_revision(
            project_id,
            document_id,
            revision_id,
            idempotency_key=idempotency_key,
            expected_document_version=expected_document_version,
            expected_lifecycle_version=expected_lifecycle_version,
            replacement_revision_id=replacement_revision_id,
            expected_replacement_lifecycle_version=(
                expected_replacement_lifecycle_version
            ),
            reason=reason,
            obsolete=False,
            confirmation_intent=confirmation_intent,
            confirmed=confirmed,
        )

    def obsolete_revision(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        reason: str,
        confirmation_intent: str,
        confirmed: bool,
    ) -> DocumentCommandOutcome | None:
        self._require_confirmation_assertion(
            confirmation_intent,
            confirmed,
            expected="obsolete_revision",
        )
        return self._terminate_revision(
            project_id,
            document_id,
            revision_id,
            idempotency_key=idempotency_key,
            expected_document_version=expected_document_version,
            expected_lifecycle_version=expected_lifecycle_version,
            replacement_revision_id=None,
            expected_replacement_lifecycle_version=None,
            reason=reason,
            obsolete=True,
            confirmation_intent=confirmation_intent,
            confirmed=confirmed,
        )

    def _submit_review(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        confirmation_intent: str,
        confirmed: bool,
        prior_rejected_cycle_id: UUID | None,
        operation: str,
    ) -> DocumentCommandOutcome | None:
        context = self._locked_release_context(
            project_id,
            document_id,
            revision_id,
        )
        if context is None:
            return None
        project, document, revision = context
        payload = {
            "revisionId": str(revision_id),
            "expectedDocumentVersion": expected_document_version,
            "expectedLifecycleVersion": expected_lifecycle_version,
            "policyGlobalId": str(policy_global_id),
            "policyVersion": policy_version,
            "policySnapshotHash": policy_snapshot_hash,
            "priorRejectedCycleId": (
                str(prior_rejected_cycle_id)
                if prior_rejected_cycle_id is not None
                else None
            ),
            "confirmationIntent": confirmation_intent,
            "confirmed": confirmed,
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
        lifecycle_document = self._locked_lifecycle(revision_id)
        lifecycle = (
            self._validated_lifecycle(lifecycle_document)
            if lifecycle_document is not None
            else None
        )
        if lifecycle is None:
            if expected_lifecycle_version != 0 or prior_rejected_cycle_id is not None:
                raise DocumentReviewStateConflict()
        else:
            if lifecycle.version != expected_lifecycle_version:
                raise DocumentReviewStateConflict()
            self._require_rejected_predecessor(
                lifecycle_document,
                lifecycle,
                prior_rejected_cycle_id,
            )
        policy = self._load_exact_release_policy(
            project,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            snapshot_hash=policy_snapshot_hash,
        )
        evidence, _file_revisions = self._review_evidence(
            project,
            document,
            revision,
        )
        cycle_number = self._next_cycle_number(revision_id)
        now = datetime.now(UTC)
        result = submit_document_review(
            lifecycle=lifecycle,
            policy=policy,
            evidence=evidence,
            cycle_global_id=uuid4(),
            event_global_id=uuid4(),
            cycle_number=cycle_number,
            prior_rejected_cycle_global_id=prior_rejected_cycle_id,
            actor=self.actor,
            now=now,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        with _controlled_document_write_scope(), document_release_command_write():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project=project,
                document_id=document_id,
                operation=operation,
            )
            cycle_document = self._insert_review_cycle(
                project,
                document,
                revision,
                result.cycle,
            )
            self._insert_lifecycle_event(
                project,
                document,
                revision,
                cycle_document,
                result.event,
            )
            self._save_lifecycle(
                project,
                document,
                revision,
                lifecycle_document,
                result.lifecycle,
                result.event,
                now,
            )
            response = self._transition_response(
                project_id,
                document,
                revision_id,
                result.lifecycle,
                result.cycle,
                result.event,
            )
            self._append_release_audit(
                operation,
                project_id,
                document_id,
                revision_id,
                result.lifecycle,
                result.event,
            )
            self._seal_idempotency(receipt, response)
        return DocumentCommandOutcome(response)

    def _terminate_revision(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        *,
        idempotency_key: str,
        expected_document_version: int,
        expected_lifecycle_version: int,
        replacement_revision_id: UUID | None,
        expected_replacement_lifecycle_version: int | None,
        reason: str,
        obsolete: bool,
        confirmation_intent: str,
        confirmed: bool,
    ) -> DocumentCommandOutcome | None:
        operation = "document.obsolete" if obsolete else "document.supersede"
        context = self._locked_release_context(
            project_id,
            document_id,
            revision_id,
        )
        if context is None:
            return None
        project, document, revision = context
        payload = {
            "revisionId": str(revision_id),
            "expectedDocumentVersion": expected_document_version,
            "expectedLifecycleVersion": expected_lifecycle_version,
            "replacementRevisionId": (
                str(replacement_revision_id)
                if replacement_revision_id is not None
                else None
            ),
            "expectedReplacementLifecycleVersion": (
                expected_replacement_lifecycle_version
            ),
            "reason": reason,
            "confirmationIntent": confirmation_intent,
            "confirmed": confirmed,
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
        lifecycle_document, lifecycle = self._required_lifecycle(
            revision_id,
            expected_lifecycle_version,
        )
        if lifecycle.approved_cycle_global_id is None:
            raise DocumentReviewStateConflict()
        cycle_document = self._locked_cycle(lifecycle.approved_cycle_global_id)
        cycle = self._cycle_for_revision(cycle_document, revision_id)
        policy = self._load_exact_release_policy(
            project,
            policy_global_id=cycle.policy_ref.global_id,
            policy_version=cycle.policy_ref.version,
            snapshot_hash=cycle.policy_ref.snapshot_hash,
        )
        replacement_effective_date = None
        if not obsolete:
            if (
                replacement_revision_id is None
                or expected_replacement_lifecycle_version is None
                or replacement_revision_id == revision_id
            ):
                raise DocumentReviewStateConflict()
            replacement = self._locked_exact_revision(
                project,
                document,
                replacement_revision_id,
            )
            if replacement is None or (
                int(replacement.major),
                int(replacement.minor),
            ) <= (int(revision.major), int(revision.minor)):
                raise DocumentReviewStateConflict()
            _replacement_document, replacement_lifecycle = (
                self._required_lifecycle(
                    replacement_revision_id,
                    expected_replacement_lifecycle_version,
                )
            )
            if replacement_lifecycle.state is not DocumentLifecycleState.RELEASED:
                raise DocumentReviewStateConflict()
            replacement_effective_date = (
                _date_value(replacement.effective_date)
                if replacement.effective_date
                else None
            )
            if replacement_effective_date is None:
                raise DocumentReviewStateConflict()
        now = datetime.now(UTC)
        result = terminate_released_document_revision(
            lifecycle=lifecycle,
            cycle=cycle,
            policy=policy,
            obsolete=obsolete,
            replacement_revision_global_id=replacement_revision_id,
            replacement_effective_date=replacement_effective_date,
            confirmation_global_id=uuid4(),
            event_global_id=uuid4(),
            actor=self.actor,
            reason=reason,
            now=now,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        with _controlled_document_write_scope(), document_release_command_write():
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                project=project,
                document_id=document_id,
                operation=operation,
            )
            self._insert_confirmation(
                project,
                document,
                revision,
                cycle_document,
                result.confirmation,
            )
            self._insert_lifecycle_event(
                project,
                document,
                revision,
                cycle_document,
                result.event,
            )
            self._save_lifecycle(
                project,
                document,
                revision,
                lifecycle_document,
                result.lifecycle,
                result.event,
                now,
            )
            response = self._transition_response(
                project_id,
                document,
                revision_id,
                result.lifecycle,
                cycle,
                result.event,
                confirmation=result.confirmation,
            )
            self._append_release_audit(
                operation,
                project_id,
                document_id,
                revision_id,
                result.lifecycle,
                result.event,
            )
            self._seal_idempotency(receipt, response)
        return DocumentCommandOutcome(response)

    @staticmethod
    def _require_confirmation_assertion(
        intent: str,
        confirmed: bool,
        *,
        expected: str,
    ) -> None:
        if intent != expected:
            raise RequestValidationFailed(
                [
                    {
                        "path": "confirmationIntent",
                        "message": _(
                            "Select the supported confirmation intent."
                        ),
                    }
                ]
            )
        if confirmed is not True:
            raise RequestValidationFailed(
                [
                    {
                        "path": "confirmed",
                        "message": _("Explicit confirmation is required."),
                    }
                ]
            )

    def _locked_release_context(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
    ) -> tuple[Any, Any, Any] | None:
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        if not self._can_view_project(project, project_id):
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
        revision = self._locked_exact_revision(project, document, revision_id)
        return (
            (project, document, revision)
            if revision is not None
            else None
        )

    @staticmethod
    def _locked_exact_revision(project, document, revision_id: UUID):
        try:
            revision = frappe.get_doc(
                "NPI Document Revision",
                str(revision_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return (
            revision
            if (
                str(revision.global_id) == str(revision_id)
                and str(revision.tenant_id) == str(project.tenant_id)
                and str(revision.project_global_id) == str(project.global_id)
                and str(revision.document_global_id) == str(document.global_id)
            )
            else None
        )

    @staticmethod
    def _locked_lifecycle(revision_id: UUID):
        try:
            return frappe.get_doc(
                "NPI Document Revision Lifecycle",
                str(revision_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None

    def _required_lifecycle(
        self,
        revision_id: UUID,
        expected_version: int,
    ) -> tuple[Any, DocumentRevisionLifecycle]:
        document = self._locked_lifecycle(revision_id)
        if document is None:
            raise DocumentReviewStateConflict()
        value = self._validated_lifecycle(document)
        if value.version != expected_version:
            raise DocumentReviewStateConflict()
        return document, value

    @staticmethod
    def _validated_lifecycle(document) -> DocumentRevisionLifecycle:
        try:
            value = lifecycle_value(document)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReviewStateConflict() from error
        if str(value.revision_global_id) != str(document.name):
            raise DocumentReviewStateConflict()
        return value

    @staticmethod
    def _locked_cycle(cycle_id: UUID):
        try:
            return frappe.get_doc(
                "NPI Document Review Cycle",
                str(cycle_id),
                for_update=True,
            )
        except frappe.DoesNotExistError as error:
            raise DocumentReviewStateConflict() from error

    @staticmethod
    def _cycle_for_revision(
        document,
        revision_id: UUID,
    ) -> DocumentReviewCycle:
        try:
            value = review_cycle_value(document)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReviewStateConflict() from error
        if value.revision_global_id != revision_id:
            raise DocumentReviewStateConflict()
        return value

    def _load_exact_release_policy(
        self,
        project,
        *,
        policy_global_id: UUID,
        policy_version: int,
        snapshot_hash: str,
    ) -> DocumentReleasePolicyVersion:
        root = frappe.db.get_value(
            "NPI Document Release Policy",
            str(policy_global_id),
            [
                "global_id",
                "tenant_id",
                "project_global_id",
                "enabled",
            ],
            as_dict=True,
        )
        row = frappe.db.get_value(
            "NPI Document Release Policy Version",
            {
                "policy_global_id": str(policy_global_id),
                "policy_version": policy_version,
            },
            _POLICY_FIELDS,
            as_dict=True,
        )
        if (
            not root
            or not row
            or str(_record_value(root, "global_id")) != str(policy_global_id)
            or str(_record_value(root, "tenant_id")) != str(project.tenant_id)
            or str(_record_value(root, "project_global_id"))
            != str(project.global_id)
            or int(_record_value(root, "enabled") or 0) != 1
            or str(_record_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_record_value(row, "project_global_id"))
            != str(project.global_id)
            or str(_record_value(row, "publication_state"))
            != DocumentReleasePolicyState.PUBLISHED.value
            or str(_record_value(row, "snapshot_hash")) != snapshot_hash
        ):
            raise DocumentReleasePolicyUnavailable()
        try:
            policy = release_policy_value(row)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReleasePolicyUnavailable() from error
        if (
            policy.policy_global_id != policy_global_id
            or policy.policy_version != policy_version
            or policy.reference
            != DocumentReleasePolicyReference(
                policy_global_id,
                policy_version,
                snapshot_hash,
            )
        ):
            raise DocumentReleasePolicyUnavailable()
        return policy

    def _review_evidence(
        self,
        project,
        document,
        revision,
    ) -> tuple[DocumentReviewEvidence, tuple[Any, ...]]:
        document_policy = self._policy_for_document(project, document)
        associations = _bounded_documents(
            "NPI Document Revision File",
            {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
                "document_revision_global_id": str(revision.global_id),
            },
            order_by="global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        files: list[DocumentReleaseFileEvidence] = []
        file_documents: list[Any] = []
        for association in associations:
            try:
                file_revision = frappe.get_doc(
                    "NPI File Revision",
                    str(association.file_revision_global_id),
                    for_update=True,
                )
            except frappe.DoesNotExistError as error:
                raise DocumentReleaseIntegrityBlocked() from error
            if not _association_matches_live_file(
                project,
                document,
                revision,
                association,
                file_revision,
            ):
                raise DocumentReleaseIntegrityBlocked()
            if (
                str(file_revision.mime_type)
                not in document_policy.allowed_mime_types
                or int(file_revision.size_bytes)
                > document_policy.maximum_file_bytes
            ):
                raise DocumentReleaseIntegrityBlocked()
            files.append(
                self._release_file_evidence(association, file_revision)
            )
            file_documents.append(file_revision)
        try:
            evidence = DocumentReviewEvidence(
                revision_global_id=UUID(str(revision.global_id)),
                revision_snapshot_hash=str(revision.snapshot_hash),
                files=tuple(files),
            )
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReleaseIntegrityBlocked() from error
        return evidence, tuple(file_documents)

    @staticmethod
    def _release_file_evidence(
        association,
        file_revision,
    ) -> DocumentReleaseFileEvidence:
        if (
            str(file_revision.scan_state) != "clean"
            or not file_revision.scan_observed_at
            or not has_live_private_file_identity(file_revision)
        ):
            raise DocumentReleaseIntegrityBlocked()
        try:
            file_document = frappe.get_doc(
                "File",
                str(file_revision.frappe_file_id),
                for_update=True,
            )
            content = file_document.get_content()
        except (
            frappe.DoesNotExistError,
            frappe.PermissionError,
            OSError,
        ) as error:
            raise DocumentReleaseIntegrityBlocked() from error
        if isinstance(content, str):
            content = content.encode("utf-8")
        if (
            not isinstance(content, bytes)
            or len(content) != int(file_revision.size_bytes)
            or hashlib.sha256(content).hexdigest() != str(file_revision.sha256)
            or str(file_document.name) != str(file_revision.frappe_file_id)
            or int(file_document.is_private or 0) != 1
            or int(file_document.is_remote_file or 0) != 0
            or str(file_document.file_url) != str(file_revision.file)
            or not str(file_document.file_url).startswith("/private/files/")
            or str(file_document.file_name) != str(file_revision.file_name)
            or int(file_document.file_size) != int(file_revision.size_bytes)
            or str(file_document.content_hash or "").casefold()
            != str(file_revision.frappe_content_hash)
        ):
            raise DocumentReleaseIntegrityBlocked()
        try:
            return DocumentReleaseFileEvidence(
                association_global_id=UUID(str(association.global_id)),
                association_snapshot_hash=str(association.snapshot_hash),
                file_revision_global_id=UUID(str(file_revision.global_id)),
                file_document_global_id=UUID(
                    str(association.file_document_global_id)
                ),
                file_optimistic_version=int(file_revision.optimistic_version),
                frappe_file_id=str(file_revision.frappe_file_id),
                frappe_content_hash=str(file_revision.frappe_content_hash),
                file_name=str(file_revision.file_name),
                mime_type=str(file_revision.mime_type),
                size_bytes=int(file_revision.size_bytes),
                sha256=str(file_revision.sha256),
                scan_state=str(file_revision.scan_state),
                scan_observed_at=_datetime_value(
                    file_revision.scan_observed_at
                ),
                uploaded_by_user_id=str(association.created_by_user_id),
                uploaded_at=_datetime_value(association.created_at),
            )
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReleaseIntegrityBlocked() from error

    def _review_confirmations(
        self,
        cycle: DocumentReviewCycle,
    ) -> tuple[DocumentConfirmation, ...]:
        rows = _bounded_documents(
            "NPI Document Confirmation",
            {
                "cycle_global_id": str(cycle.global_id),
                "revision_global_id": str(cycle.revision_global_id),
                "confirmation_type": [
                    "in",
                    [
                        DocumentConfirmationType.REVIEW_APPROVE.value,
                        DocumentConfirmationType.REVIEW_REJECT.value,
                    ],
                ],
            },
            order_by="confirmed_at asc, global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        result = []
        slots = set()
        for row in rows:
            try:
                value = confirmation_value(row)
            except (RequestValidationFailed, TypeError, ValueError) as error:
                raise DocumentReviewStateConflict() from error
            if (
                value.cycle_global_id != cycle.global_id
                or value.revision_global_id != cycle.revision_global_id
                or value.policy_ref != cycle.policy_ref
                or value.evidence_snapshot_hash != cycle.evidence.snapshot_hash
                or not any(
                    assignment.slot_key == value.authority_slot
                    and assignment.user_id.casefold()
                    == value.actor_user_id.casefold()
                    for assignment in cycle.reviewer_assignments
                )
                or value.authority_slot in slots
            ):
                raise DocumentReviewStateConflict()
            slots.add(value.authority_slot)
            result.append(value)
        return tuple(result)

    @staticmethod
    def _require_exact_approval_event(
        lifecycle: DocumentRevisionLifecycle,
        cycle: DocumentReviewCycle,
        approval_hashes: Sequence[str],
    ) -> None:
        if lifecycle.approved_event_global_id is None:
            raise DocumentReviewStateConflict()
        try:
            row = frappe.get_doc(
                "NPI Document Lifecycle Event",
                str(lifecycle.approved_event_global_id),
                for_update=True,
            )
            event = lifecycle_event_value(row)
        except (
            frappe.DoesNotExistError,
            RequestValidationFailed,
            TypeError,
            ValueError,
        ) as error:
            raise DocumentReviewStateConflict() from error
        if (
            event.event_type is not DocumentLifecycleEventType.APPROVED
            or event.revision_global_id != lifecycle.revision_global_id
            or event.cycle_global_id != cycle.global_id
            or event.policy_ref != cycle.policy_ref
            or tuple(sorted(event.confirmation_hashes))
            != tuple(sorted(approval_hashes))
            or len(approval_hashes) < cycle.required_approval_count
        ):
            raise DocumentReviewStateConflict()

    @staticmethod
    def _release_snapshot_hash(
        cycle: DocumentReviewCycle,
        policy: DocumentReleasePolicyVersion,
        approval_hashes: Sequence[str],
        file_revisions: Sequence[Any],
    ) -> str:
        return sha256_json(
            {
                "schemaVersion": 1,
                "revisionGlobalId": str(cycle.revision_global_id),
                "reviewEvidenceSnapshotHash": cycle.evidence.snapshot_hash,
                "releasePolicyRef": policy.reference.canonical_dict(),
                "approvalConfirmationHashes": sorted(approval_hashes),
                "files": [
                    {
                        "fileRevisionGlobalId": str(value.global_id),
                        "fromOptimisticVersion": int(value.optimistic_version),
                        "toOptimisticVersion": (
                            int(value.optimistic_version)
                            if int(value.released or 0) == 1
                            else int(value.optimistic_version) + 1
                        ),
                        "sha256": str(value.sha256),
                    }
                    for value in sorted(
                        file_revisions,
                        key=lambda item: str(item.global_id),
                    )
                ],
            }
        )

    @staticmethod
    def _mark_file_revisions_released(file_revisions: Sequence[Any]) -> None:
        for document in file_revisions:
            prior_version = int(document.optimistic_version)
            if int(document.released or 0) == 1:
                continue
            document.released = 1
            document.save()
            if (
                int(document.released or 0) != 1
                or int(document.optimistic_version) != prior_version + 1
            ):
                raise DocumentVersionConflict()

    def _require_rejected_predecessor(
        self,
        lifecycle_document,
        lifecycle: DocumentRevisionLifecycle,
        prior_rejected_cycle_id: UUID | None,
    ) -> None:
        if (
            lifecycle.state is not DocumentLifecycleState.DRAFT
            or prior_rejected_cycle_id is None
            or not lifecycle_document.last_event_global_id
        ):
            raise DocumentReviewStateConflict()
        try:
            event = lifecycle_event_value(
                frappe.get_doc(
                    "NPI Document Lifecycle Event",
                    str(lifecycle_document.last_event_global_id),
                    for_update=True,
                )
            )
        except (
            frappe.DoesNotExistError,
            RequestValidationFailed,
            TypeError,
            ValueError,
        ) as error:
            raise DocumentReviewStateConflict() from error
        if (
            event.event_type is not DocumentLifecycleEventType.REVIEW_REJECTED
            or event.to_version != lifecycle.version
            or event.cycle_global_id != prior_rejected_cycle_id
        ):
            raise DocumentReviewStateConflict()

    @staticmethod
    def _next_cycle_number(revision_id: UUID) -> int:
        rows = _bounded_documents(
            "NPI Document Review Cycle",
            {"revision_global_id": str(revision_id)},
            order_by="cycle_number desc, global_id asc",
            maximum=_MAX_RELEASE_ROWS,
        )
        if not rows:
            return 1
        try:
            values = tuple(review_cycle_value(row) for row in rows)
        except (RequestValidationFailed, TypeError, ValueError) as error:
            raise DocumentReviewStateConflict() from error
        numbers = sorted(value.cycle_number for value in values)
        if numbers != list(range(1, len(numbers) + 1)):
            raise DocumentReviewStateConflict()
        return numbers[-1] + 1

    def _insert_review_cycle(
        self,
        project,
        document,
        revision,
        value: DocumentReviewCycle,
    ):
        return frappe.get_doc(
            {
                "doctype": "NPI Document Review Cycle",
                "global_id": str(value.global_id),
                "cycle_key": (
                    f"{value.revision_global_id}:{value.cycle_number}"
                ),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
                "document_revision": str(revision.global_id),
                "revision_global_id": str(revision.global_id),
                "cycle_number": value.cycle_number,
                "policy_global_id": str(value.policy_ref.global_id),
                "policy_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "review_evidence": value.evidence.canonical_dict(),
                "evidence_snapshot_hash": value.evidence.snapshot_hash,
                "reviewer_assignments": [
                    assignment.canonical_dict()
                    for assignment in value.reviewer_assignments
                ],
                "required_approval_count": value.required_approval_count,
                "prior_rejected_cycle_global_id": (
                    str(value.prior_rejected_cycle_global_id)
                    if value.prior_rejected_cycle_global_id
                    else None
                ),
                "submitted_by_user_id": value.submitted_by_user_id,
                "submitted_at": _database_datetime(value.submitted_at),
                "request_id": value.request_id,
                "trace_id": value.trace_id,
                "cycle_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    def _insert_confirmation(
        self,
        project,
        document,
        revision,
        cycle_document,
        value: DocumentConfirmation,
    ):
        return frappe.get_doc(
            {
                "doctype": "NPI Document Confirmation",
                "global_id": str(value.global_id),
                "confirmation_key": value.confirmation_key,
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
                "document_revision": str(revision.global_id),
                "revision_global_id": str(revision.global_id),
                "review_cycle": str(cycle_document.global_id),
                "cycle_global_id": str(value.cycle_global_id),
                "policy_global_id": str(value.policy_ref.global_id),
                "policy_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "evidence_snapshot_hash": value.evidence_snapshot_hash,
                "confirmation_type": value.confirmation_type.value,
                "actor_user_id": value.actor_user_id,
                "authority_slot": value.authority_slot,
                "confirmation_method": value.confirmation_method,
                "confirmation_intent": value.confirmation_intent,
                "confirmed": 1,
                "reason": value.reason,
                "confirmed_at": _database_datetime(value.confirmed_at),
                "request_id": value.request_id,
                "trace_id": value.trace_id,
                "confirmation_evidence": value.evidence_payload(),
                "evidence_hash": value.evidence_hash,
            }
        ).insert()

    def _insert_lifecycle_event(
        self,
        project,
        document,
        revision,
        cycle_document,
        value: DocumentLifecycleEvent,
    ):
        return frappe.get_doc(
            {
                "doctype": "NPI Document Lifecycle Event",
                "global_id": str(value.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
                "document_revision": str(revision.global_id),
                "revision_global_id": str(revision.global_id),
                "event_type": value.event_type.value,
                "from_state": value.from_state.value,
                "to_state": value.to_state.value,
                "from_version": value.from_version,
                "to_version": value.to_version,
                "review_cycle": str(cycle_document.global_id),
                "cycle_global_id": str(value.cycle_global_id),
                "policy_global_id": str(value.policy_ref.global_id),
                "policy_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "evidence_snapshot_hash": value.evidence_snapshot_hash,
                "confirmation_hashes": list(value.confirmation_hashes),
                "replacement_revision_global_id": (
                    str(value.replacement_revision_global_id)
                    if value.replacement_revision_global_id
                    else None
                ),
                "replacement_effective_date": (
                    value.replacement_effective_date.isoformat()
                    if value.replacement_effective_date
                    else None
                ),
                "actor_user_id": value.actor_user_id,
                "occurred_at": _database_datetime(value.occurred_at),
                "request_id": value.request_id,
                "trace_id": value.trace_id,
                "event_snapshot": value.event_payload(),
                "event_hash": value.event_hash,
            }
        ).insert()

    def _save_lifecycle(
        self,
        project,
        document,
        revision,
        lifecycle_document,
        value: DocumentRevisionLifecycle,
        event: DocumentLifecycleEvent,
        now: datetime,
    ):
        payload: dict[str, object] = {
            "global_id": str(value.revision_global_id),
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
            "document_global_id": str(document.global_id),
            "document_revision": str(revision.global_id),
            "revision_global_id": str(revision.global_id),
            "current_state": value.state.value,
            "lifecycle_version": value.version,
            "active_cycle_global_id": (
                str(value.active_cycle_global_id)
                if value.active_cycle_global_id
                else None
            ),
            "approved_cycle_global_id": (
                str(value.approved_cycle_global_id)
                if value.approved_cycle_global_id
                else None
            ),
            "approved_event_global_id": (
                str(value.approved_event_global_id)
                if value.approved_event_global_id
                else None
            ),
            "release_event_global_id": (
                str(value.release_event_global_id)
                if value.release_event_global_id
                else None
            ),
            "release_snapshot_hash": value.release_snapshot_hash,
            "replacement_revision_global_id": (
                str(value.replacement_revision_global_id)
                if value.replacement_revision_global_id
                else None
            ),
            "replacement_effective_date": (
                value.replacement_effective_date.isoformat()
                if value.replacement_effective_date
                else None
            ),
            "terminal_event_global_id": (
                str(value.terminal_event_global_id)
                if value.terminal_event_global_id
                else None
            ),
            "last_event_global_id": str(event.global_id),
            "updated_by_user_id": self.actor,
            "updated_at": _database_datetime(now),
            "request_id": self.request_id,
            "trace_id": self.trace_id,
        }
        if lifecycle_document is None:
            payload["doctype"] = "NPI Document Revision Lifecycle"
            return frappe.get_doc(payload).insert()
        for fieldname, field_value in payload.items():
            setattr(lifecycle_document, fieldname, field_value)
        lifecycle_document.save()
        return lifecycle_document

    def _append_release_audit(
        self,
        operation: str,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        lifecycle: DocumentRevisionLifecycle,
        event: DocumentLifecycleEvent,
    ) -> None:
        self._append_audit(
            operation=operation,
            global_id=revision_id,
            object_version=lifecycle.version,
            result="created",
            summary={
                "projectId": str(project_id),
                "documentId": str(document_id),
                "revisionId": str(revision_id),
                "lifecycleState": lifecycle.state.value,
                "lifecycleVersion": lifecycle.version,
                "eventId": str(event.global_id),
                "requestId": self.request_id,
            },
        )

    @staticmethod
    def _transition_response(
        project_id: UUID,
        document,
        revision_id: UUID,
        lifecycle: DocumentRevisionLifecycle,
        cycle: DocumentReviewCycle,
        event: DocumentLifecycleEvent,
        *,
        confirmation: DocumentConfirmation | None = None,
    ) -> dict[str, Any]:
        return {
            "projectId": str(project_id),
            "documentId": str(document.global_id),
            "documentOptimisticVersion": int(document.optimistic_version),
            "revisionId": str(revision_id),
            "state": lifecycle.state.value,
            "lifecycleVersion": lifecycle.version,
            "reviewCycleId": str(cycle.global_id),
            "releasePolicy": {
                "globalId": str(cycle.policy_ref.global_id),
                "version": cycle.policy_ref.version,
                "snapshotHash": cycle.policy_ref.snapshot_hash,
            },
            "event": {
                "globalId": str(event.global_id),
                "type": event.event_type.value,
                "snapshotHash": event.event_hash,
            },
            "confirmation": (
                {
                    "globalId": str(confirmation.global_id),
                    "type": confirmation.confirmation_type.value,
                    "evidenceHash": confirmation.evidence_hash,
                }
                if confirmation is not None
                else None
            ),
            "releaseSnapshotHash": lifecycle.release_snapshot_hash,
        }
