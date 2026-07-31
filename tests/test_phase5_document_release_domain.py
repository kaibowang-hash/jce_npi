from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.documents.release_domain import (  # noqa: E402
    DocumentLifecycleEvent,
    DocumentLifecycleEventType,
    DocumentLifecycleState,
    DocumentReleaseFileEvidence,
    DocumentReleasePolicyState,
    DocumentReleasePolicyVersion,
    DocumentReviewAssignmentUnavailable,
    DocumentReviewEvidence,
    DocumentReviewerAssignment,
    DocumentReviewStateConflict,
    DocumentRevisionLifecycle,
    RequestValidationFailed,
    advance_document_lifecycle,
    submit_document_review,
)


POLICY_ID = UUID("7590348a-39bb-4a9e-9852-87a199153791")
POLICY_VERSION_ID = UUID("b5b19fc5-3a31-4ed8-a23b-817b1d51fb21")
PROJECT_ID = UUID("8378554b-cb1d-4a09-806d-480a9580055e")
REVISION_ID = UUID("2589495e-797a-4a66-a171-83e7166c92ad")
CYCLE_ID = UUID("8d566c67-fced-4f52-b8d8-01a913f31f10")
EVENT_ID = UUID("dbca8699-13c2-4424-86f7-86e2b7564fda")
ASSOCIATION_ID = UUID("8fa4d6c0-5b7f-4765-a624-62e9999297af")
FILE_REVISION_ID = UUID("f1428481-d120-47c5-ab4c-daad0bc6a57f")
FILE_DOCUMENT_ID = UUID("70e55f2e-dcb4-43fe-a6ea-a0e5950572d6")
NOW = datetime(2026, 7, 31, 7, 30, tzinfo=UTC)


def policy(
    *,
    state: DocumentReleasePolicyState = DocumentReleasePolicyState.PUBLISHED,
    reviewers: tuple[DocumentReviewerAssignment, ...] = (
        DocumentReviewerAssignment("reviewer_one", "reviewer@example.invalid"),
        DocumentReviewerAssignment("reviewer_two", "reviewer2@example.invalid"),
    ),
    release_users: tuple[str, ...] = ("releaser@example.invalid",),
) -> DocumentReleasePolicyVersion:
    return DocumentReleasePolicyVersion(
        global_id=POLICY_VERSION_ID,
        policy_global_id=POLICY_ID,
        tenant_id="TENANT-A",
        project_global_id=PROJECT_ID,
        policy_key="synthetic_release_policy",
        policy_version=1,
        title="Synthetic release policy",
        state=state,
        submitter_user_ids=("submitter@example.invalid",),
        reviewer_assignments=reviewers,
        required_approval_count=2,
        release_authority_user_ids=release_users,
        supersede_authority_user_ids=("superseder@example.invalid",),
        obsolete_authority_user_ids=("obsoleter@example.invalid",),
    )


def evidence() -> DocumentReviewEvidence:
    return DocumentReviewEvidence(
        revision_global_id=REVISION_ID,
        revision_snapshot_hash="a" * 64,
        files=(
            DocumentReleaseFileEvidence(
                association_global_id=ASSOCIATION_ID,
                association_snapshot_hash="b" * 64,
                file_revision_global_id=FILE_REVISION_ID,
                file_document_global_id=FILE_DOCUMENT_ID,
                file_optimistic_version=2,
                frappe_file_id="file-identity",
                frappe_content_hash="c" * 32,
                file_name="drawing.pdf",
                mime_type="application/pdf",
                size_bytes=512,
                sha256="d" * 64,
                scan_state="clean",
                scan_observed_at=NOW,
                uploaded_by_user_id="author@example.invalid",
                uploaded_at=NOW,
            ),
        ),
    )


class DocumentReleasePolicyTests(unittest.TestCase):
    def test_policy_snapshot_is_deterministic_and_exact(self) -> None:
        selected = policy()
        reordered = replace(
            selected,
            submitter_user_ids=tuple(reversed(selected.submitter_user_ids)),
            reviewer_assignments=tuple(reversed(selected.reviewer_assignments)),
            release_authority_user_ids=tuple(
                reversed(selected.release_authority_user_ids)
            ),
        )

        self.assertEqual(selected.snapshot_hash, reordered.snapshot_hash)
        self.assertEqual(selected.reference.snapshot_hash, selected.snapshot_hash)
        self.assertTrue(selected.permits_submit("SUBMITTER@example.invalid"))
        self.assertTrue(selected.permits_release("RELEASER@example.invalid"))
        self.assertEqual(
            selected.reviewer_assignment("reviewer2@example.invalid").slot_key,
            "reviewer_two",
        )

    def test_policy_rejects_reviewer_release_overlap(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            policy(release_users=("reviewer@example.invalid",))

    def test_policy_rejects_weakened_integrity_rules(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(policy(), require_sha256_match=False)
        with self.assertRaises(RequestValidationFailed):
            replace(policy(), required_scan_state="pending")

    def test_evidence_requires_clean_exact_file_metadata(self) -> None:
        selected = evidence()
        self.assertEqual(selected.canonical_dict()["files"][0]["scanState"], "clean")
        self.assertEqual(len(selected.snapshot_hash), 64)
        with self.assertRaises(RequestValidationFailed):
            replace(selected.files[0], scan_state="pending")


class DocumentReleaseTransitionTests(unittest.TestCase):
    def test_first_submission_creates_in_review_version_one(self) -> None:
        result = submit_document_review(
            lifecycle=None,
            policy=policy(),
            evidence=evidence(),
            cycle_global_id=CYCLE_ID,
            event_global_id=EVENT_ID,
            cycle_number=1,
            prior_rejected_cycle_global_id=None,
            actor="submitter@example.invalid",
            now=NOW,
            request_id="request-release-0001",
            trace_id="trace-release-0001",
        )

        self.assertEqual(result.lifecycle.state, DocumentLifecycleState.IN_REVIEW)
        self.assertEqual(result.lifecycle.version, 1)
        self.assertEqual(
            result.event.event_type,
            DocumentLifecycleEventType.SUBMITTED,
        )
        self.assertEqual(result.cycle.evidence.snapshot_hash, evidence().snapshot_hash)

    def test_submission_requires_exact_policy_actor(self) -> None:
        with self.assertRaises(DocumentReviewAssignmentUnavailable):
            submit_document_review(
                lifecycle=None,
                policy=policy(),
                evidence=evidence(),
                cycle_global_id=CYCLE_ID,
                event_global_id=EVENT_ID,
                cycle_number=1,
                prior_rejected_cycle_global_id=None,
                actor="Administrator",
                now=NOW,
                request_id="request-release-0001",
                trace_id="trace-release-0001",
            )

    def test_resubmission_requires_rejected_predecessor_shape(self) -> None:
        with self.assertRaises(DocumentReviewStateConflict):
            submit_document_review(
                lifecycle=DocumentRevisionLifecycle(
                    REVISION_ID,
                    DocumentLifecycleState.DRAFT,
                    2,
                ),
                policy=policy(),
                evidence=evidence(),
                cycle_global_id=CYCLE_ID,
                event_global_id=EVENT_ID,
                cycle_number=2,
                prior_rejected_cycle_global_id=None,
                actor="submitter@example.invalid",
                now=NOW,
                request_id="request-release-0002",
                trace_id="trace-release-0002",
            )

    def test_lifecycle_event_rejects_unapproved_transition(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            DocumentLifecycleEvent(
                global_id=EVENT_ID,
                revision_global_id=REVISION_ID,
                event_type=DocumentLifecycleEventType.RELEASED,
                from_state=DocumentLifecycleState.DRAFT,
                to_state=DocumentLifecycleState.RELEASED,
                from_version=0,
                to_version=1,
                cycle_global_id=CYCLE_ID,
                policy_ref=policy().reference,
                evidence_snapshot_hash=evidence().snapshot_hash,
                confirmation_hashes=("e" * 64,),
                replacement_revision_global_id=None,
                replacement_effective_date=None,
                actor_user_id="releaser@example.invalid",
                occurred_at=NOW,
                request_id="request-release-0003",
                trace_id="trace-release-0003",
            )

    def test_supersede_requires_replacement_and_effectivity(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            DocumentLifecycleEvent(
                global_id=EVENT_ID,
                revision_global_id=REVISION_ID,
                event_type=DocumentLifecycleEventType.SUPERSEDED,
                from_state=DocumentLifecycleState.RELEASED,
                to_state=DocumentLifecycleState.SUPERSEDED,
                from_version=5,
                to_version=6,
                cycle_global_id=CYCLE_ID,
                policy_ref=policy().reference,
                evidence_snapshot_hash=evidence().snapshot_hash,
                confirmation_hashes=("e" * 64,),
                replacement_revision_global_id=None,
                replacement_effective_date=None,
                actor_user_id="superseder@example.invalid",
                occurred_at=NOW,
                request_id="request-release-0004",
                trace_id="trace-release-0004",
            )

    def test_advance_preserves_release_then_terminal_history(self) -> None:
        approved = DocumentRevisionLifecycle(
            revision_global_id=REVISION_ID,
            state=DocumentLifecycleState.APPROVED,
            version=4,
            approved_cycle_global_id=CYCLE_ID,
            approved_event_global_id=UUID("68a10808-cf31-44c5-a27f-e1e76958185e"),
        )
        release_event = DocumentLifecycleEvent(
            global_id=EVENT_ID,
            revision_global_id=REVISION_ID,
            event_type=DocumentLifecycleEventType.RELEASED,
            from_state=DocumentLifecycleState.APPROVED,
            to_state=DocumentLifecycleState.RELEASED,
            from_version=4,
            to_version=5,
            cycle_global_id=CYCLE_ID,
            policy_ref=policy().reference,
            evidence_snapshot_hash=evidence().snapshot_hash,
            confirmation_hashes=("e" * 64,),
            replacement_revision_global_id=None,
            replacement_effective_date=None,
            actor_user_id="releaser@example.invalid",
            occurred_at=NOW,
            request_id="request-release-0005",
            trace_id="trace-release-0005",
        )
        released = advance_document_lifecycle(
            approved,
            release_event,
            release_snapshot_hash="f" * 64,
        )
        replacement_id = UUID("cc39c4b3-4c96-4d04-a2fe-7d5fb714a21f")
        supersede_event = DocumentLifecycleEvent(
            global_id=UUID("6e9107f5-a622-48fb-bcc4-c35507432466"),
            revision_global_id=REVISION_ID,
            event_type=DocumentLifecycleEventType.SUPERSEDED,
            from_state=DocumentLifecycleState.RELEASED,
            to_state=DocumentLifecycleState.SUPERSEDED,
            from_version=5,
            to_version=6,
            cycle_global_id=CYCLE_ID,
            policy_ref=policy().reference,
            evidence_snapshot_hash=evidence().snapshot_hash,
            confirmation_hashes=("1" * 64,),
            replacement_revision_global_id=replacement_id,
            replacement_effective_date=date(2026, 8, 1),
            actor_user_id="superseder@example.invalid",
            occurred_at=NOW,
            request_id="request-release-0006",
            trace_id="trace-release-0006",
        )
        superseded = advance_document_lifecycle(released, supersede_event)

        self.assertEqual(superseded.state, DocumentLifecycleState.SUPERSEDED)
        self.assertEqual(superseded.release_event_global_id, EVENT_ID)
        self.assertEqual(superseded.replacement_revision_global_id, replacement_id)


if __name__ == "__main__":
    unittest.main()
