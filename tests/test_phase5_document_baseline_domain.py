from __future__ import annotations

import unittest
import sys
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.documents.baseline_domain import (  # noqa: E402
    BaselineGateDependency,
    BaselineImpactEvent,
    DocumentBaselineAuthorityUnavailable,
    DocumentBaselineIdempotencyConflict,
    DocumentBaselineInputUnavailable,
    DocumentBaselineMember,
    DocumentBaselineMemberPrecondition,
    DocumentBaselinePolicyReference,
    DocumentBaselinePolicyState,
    DocumentBaselinePolicyUnavailable,
    DocumentBaselinePolicyVersion,
    DocumentBaselineUnavailable,
    create_document_baseline,
    sha256_json,
)
from npi_core.documents.release_domain import (  # noqa: E402
    DocumentReleaseFileEvidence,
    DocumentReviewEvidence,
)
from npi_core.foundation.errors import RequestValidationFailed  # noqa: E402


POLICY_ID = UUID("10000000-0000-4000-8000-000000000001")
POLICY_VERSION_ID = UUID("10000000-0000-4000-8000-000000000002")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000003")
BASELINE_ID = UUID("10000000-0000-4000-8000-000000000004")
MEMBER_ID = UUID("10000000-0000-4000-8000-000000000005")
DOCUMENT_ID = UUID("10000000-0000-4000-8000-000000000006")
REVISION_ID = UUID("10000000-0000-4000-8000-000000000007")
NEW_REVISION_ID = UUID("10000000-0000-4000-8000-000000000008")
RELEASE_EVENT_ID = UUID("10000000-0000-4000-8000-000000000009")
ASSOCIATION_ID = UUID("10000000-0000-4000-8000-000000000010")
FILE_REVISION_ID = UUID("10000000-0000-4000-8000-000000000011")
FILE_DOCUMENT_ID = UUID("10000000-0000-4000-8000-000000000012")
DEPENDENCY_ID = UUID("10000000-0000-4000-8000-000000000013")
GATE_ID = UUID("10000000-0000-4000-8000-000000000014")
REQUIREMENT_ID = UUID("10000000-0000-4000-8000-000000000015")
EVIDENCE_ID = UUID("10000000-0000-4000-8000-000000000016")
IMPACT_ID = UUID("10000000-0000-4000-8000-000000000017")
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
NOW = datetime(2026, 7, 31, 20, 25, 22, tzinfo=UTC)
ACTOR = "baseline.authority@example.com"


def release_evidence() -> DocumentReviewEvidence:
    file_evidence = DocumentReleaseFileEvidence(
        association_global_id=ASSOCIATION_ID,
        association_snapshot_hash=HASH_A,
        file_revision_global_id=FILE_REVISION_ID,
        file_document_global_id=FILE_DOCUMENT_ID,
        file_optimistic_version=1,
        frappe_file_id="private-file-identity",
        frappe_content_hash="d" * 32,
        file_name="released.pdf",
        mime_type="application/pdf",
        size_bytes=128,
        sha256=HASH_B,
        scan_state="clean",
        scan_observed_at=NOW,
        uploaded_by_user_id=ACTOR,
        uploaded_at=NOW,
    )
    return DocumentReviewEvidence(
        revision_global_id=REVISION_ID,
        revision_snapshot_hash=HASH_C,
        files=(file_evidence,),
    )


def policy(
    state: DocumentBaselinePolicyState = DocumentBaselinePolicyState.PUBLISHED,
) -> DocumentBaselinePolicyVersion:
    return DocumentBaselinePolicyVersion(
        global_id=POLICY_VERSION_ID,
        policy_global_id=POLICY_ID,
        tenant_id="site-test",
        project_global_id=PROJECT_ID,
        policy_key="synthetic-baseline",
        policy_version=1,
        title="Synthetic baseline authority",
        state=state,
        baseline_authority_user_ids=(ACTOR,),
    )


def member(sequence: int = 1) -> DocumentBaselineMember:
    evidence = release_evidence()
    return DocumentBaselineMember(
        global_id=MEMBER_ID,
        sequence=sequence,
        document_global_id=DOCUMENT_ID,
        revision_global_id=REVISION_ID,
        major=1,
        minor=0,
        revision_snapshot_hash=HASH_C,
        lifecycle_version=4,
        release_event_global_id=RELEASE_EVENT_ID,
        release_snapshot_hash=HASH_A,
        release_evidence=evidence,
    )


class DocumentBaselineDomainTest(unittest.TestCase):
    def test_policy_is_canonical_publishable_and_exact_actor_bound(self) -> None:
        value = policy()
        self.assertTrue(value.permits_baseline(ACTOR.upper()))
        self.assertFalse(value.permits_baseline("other@example.com"))
        self.assertEqual(value.snapshot_hash, sha256_json(value.snapshot_payload()))
        self.assertEqual(
            value.reference,
            DocumentBaselinePolicyReference(POLICY_ID, 1, value.snapshot_hash),
        )

    def test_policy_rejects_duplicate_authority_and_tampered_hash(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            replace(
                policy(),
                baseline_authority_user_ids=(ACTOR, ACTOR.upper()),
                snapshot_hash="",
            )
        with self.assertRaises(RequestValidationFailed):
            replace(policy(), snapshot_hash=HASH_A)

    def test_member_freezes_exact_revision_release_and_file_evidence(self) -> None:
        value = member()
        self.assertEqual(value.release_evidence.revision_global_id, REVISION_ID)
        self.assertNotEqual(
            value.release_snapshot_hash,
            value.release_evidence.snapshot_hash,
        )
        self.assertEqual(value.member_hash, sha256_json(value.canonical_dict()))
        with self.assertRaises(RequestValidationFailed):
            replace(value, revision_snapshot_hash=HASH_A)

    def test_baseline_requires_published_exact_policy_and_authority(self) -> None:
        value = create_document_baseline(
            global_id=BASELINE_ID,
            tenant_id="site-test",
            project_global_id=PROJECT_ID,
            label="G2 synthetic package",
            policy=policy(),
            members=(member(),),
            actor=ACTOR,
            now=NOW,
            request_id="request-1",
            trace_id="trace-1",
        )
        self.assertEqual(value.version, 1)
        self.assertEqual(value.snapshot_hash, sha256_json(value.snapshot_payload()))
        with self.assertRaises(DocumentBaselinePolicyUnavailable):
            create_document_baseline(
                global_id=BASELINE_ID,
                tenant_id="site-test",
                project_global_id=PROJECT_ID,
                label="G2 synthetic package",
                policy=policy(DocumentBaselinePolicyState.DRAFT),
                members=(member(),),
                actor=ACTOR,
                now=NOW,
                request_id="request-1",
                trace_id="trace-1",
            )
        with self.assertRaises(DocumentBaselineAuthorityUnavailable):
            create_document_baseline(
                global_id=BASELINE_ID,
                tenant_id="site-test",
                project_global_id=PROJECT_ID,
                label="G2 synthetic package",
                policy=policy(),
                members=(member(),),
                actor="other@example.com",
                now=NOW,
                request_id="request-1",
                trace_id="trace-1",
            )

    def test_baseline_rejects_duplicate_revision_and_noncontiguous_sequence(self) -> None:
        first = member()
        duplicate = replace(first, global_id=UUID(int=18), sequence=2)
        with self.assertRaises(RequestValidationFailed):
            create_document_baseline(
                global_id=BASELINE_ID,
                tenant_id="site-test",
                project_global_id=PROJECT_ID,
                label="G2 synthetic package",
                policy=policy(),
                members=(first, duplicate),
                actor=ACTOR,
                now=NOW,
                request_id="request-1",
                trace_id="trace-1",
            )
        with self.assertRaises(RequestValidationFailed):
            create_document_baseline(
                global_id=BASELINE_ID,
                tenant_id="site-test",
                project_global_id=PROJECT_ID,
                label="G2 synthetic package",
                policy=policy(),
                members=(replace(first, sequence=2),),
                actor=ACTOR,
                now=NOW,
                request_id="request-1",
                trace_id="trace-1",
            )

    def test_dependency_key_and_snapshot_are_exact_and_tamper_evident(self) -> None:
        value = self.dependency()
        self.assertEqual(value.snapshot_hash, sha256_json(value.snapshot_payload()))
        self.assertRegex(value.dependency_key, r"^[a-f0-9]{64}$")
        with self.assertRaises(RequestValidationFailed):
            replace(value, dependency_key=HASH_A, snapshot_hash="")

    def test_dependency_accepts_frappe_actor_ids_but_rejects_unsafe_text(self) -> None:
        value = replace(
            self.dependency(),
            registered_by_user_id="Administrator",
            dependency_key="",
            snapshot_hash="",
        )
        self.assertEqual(value.registered_by_user_id, "Administrator")
        for actor in ("", "two words", "unsafe\nactor"):
            with self.subTest(actor=actor):
                with self.assertRaises(RequestValidationFailed):
                    replace(
                        value,
                        registered_by_user_id=actor,
                        dependency_key="",
                        snapshot_hash="",
                    )

    def test_impact_freezes_old_new_lineage_and_rejects_same_revision(self) -> None:
        dependency = self.dependency()
        value = BaselineImpactEvent(
            global_id=IMPACT_ID,
            tenant_id="site-test",
            project_global_id=PROJECT_ID,
            dependency_global_id=DEPENDENCY_ID,
            baseline_global_id=BASELINE_ID,
            baseline_snapshot_hash=HASH_A,
            old_revision_global_id=REVISION_ID,
            old_revision_snapshot_hash=HASH_B,
            new_revision_global_id=NEW_REVISION_ID,
            new_revision_snapshot_hash=HASH_C,
            gate_global_id=GATE_ID,
            requirement_global_id=REQUIREMENT_ID,
            evidence_reference_global_id=EVIDENCE_ID,
            initiated_by_user_id=ACTOR,
            occurred_at=NOW,
            request_id="request-2",
            trace_id="trace-2",
        )
        self.assertEqual(value.event_hash, sha256_json(value.event_payload()))
        self.assertRegex(value.impact_key, r"^[a-f0-9]{64}$")
        with self.assertRaises(RequestValidationFailed):
            replace(value, new_revision_global_id=REVISION_ID, event_hash="")
        with self.assertRaises(RequestValidationFailed):
            replace(value, event_hash=dependency.snapshot_hash)

    def test_input_problem_has_closed_code(self) -> None:
        self.assertEqual(
            DocumentBaselineInputUnavailable().code,
            "DOCUMENT_BASELINE_INPUT_UNAVAILABLE",
        )

    def test_member_precondition_and_repository_problems_are_closed(self) -> None:
        value = DocumentBaselineMemberPrecondition(
            revision_id=REVISION_ID,
            expected_revision_snapshot_hash=HASH_A,
            expected_lifecycle_version=4,
            expected_release_snapshot_hash=HASH_B,
        )
        self.assertEqual(value.expected_lifecycle_version, 4)
        with self.assertRaises(RequestValidationFailed):
            replace(value, expected_lifecycle_version=0)
        with self.assertRaises(RequestValidationFailed):
            replace(value, expected_release_snapshot_hash="not-a-hash")
        self.assertEqual(
            DocumentBaselineUnavailable().code,
            "DOCUMENT_BASELINE_UNAVAILABLE",
        )
        self.assertEqual(
            DocumentBaselineIdempotencyConflict().code,
            "DOCUMENT_BASELINE_IDEMPOTENCY_CONFLICT",
        )

    @staticmethod
    def dependency() -> BaselineGateDependency:
        return BaselineGateDependency(
            global_id=DEPENDENCY_ID,
            tenant_id="site-test",
            project_global_id=PROJECT_ID,
            baseline_global_id=BASELINE_ID,
            baseline_snapshot_hash=HASH_A,
            input_document_global_id=DOCUMENT_ID,
            input_revision_global_id=REVISION_ID,
            input_revision_snapshot_hash=HASH_B,
            gate_global_id=GATE_ID,
            requirement_global_id=REQUIREMENT_ID,
            requirement_key="G2-DESIGN",
            evidence_reference_global_id=EVIDENCE_ID,
            registered_by_user_id=ACTOR,
            registered_at=NOW,
            request_id="request-1",
            trace_id="trace-1",
        )


if __name__ == "__main__":
    unittest.main()
