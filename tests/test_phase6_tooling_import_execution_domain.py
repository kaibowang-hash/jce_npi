from __future__ import annotations

import unittest
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.tooling.import_domain import (
    ImportFieldResult,
    ImportJobState,
    ImportRowResult,
    ImportRowResultState,
    RollbackDecision,
    RollbackDecisionState,
    ToolingImportJobSnapshot,
)
from npi_core.tooling.import_execution_domain import (
    FIXTURE_MAPPING_VERSION,
    CorrectionEntry,
    ExecutionFieldBinding,
    FixtureMappingActivation,
    ReconciliationItem,
    ReconciliationSnapshot,
    ReconciliationState,
    rollback_item_state,
    validate_correction_entries,
)


NOW = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
HASH = "a" * 64


def _uuid(value: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{value:012d}")


def _field(code: str = "accepted") -> ImportFieldResult:
    return ImportFieldResult(
        source_ordinal=1,
        source_header="Part Name English",
        result_code=code,
        message="The controlled synthetic field was processed.",
        target_field="title" if code == "accepted" else None,
    )


def _row(
    identity: int,
    source_row: int,
    attempt: int,
    state: ImportRowResultState,
) -> ImportRowResult:
    successful = state in {
        ImportRowResultState.CREATED,
        ImportRowResultState.UPDATED,
    }
    return ImportRowResult(
        global_id=_uuid(identity),
        worksheet_name="Tooling List",
        source_row=source_row,
        attempt=attempt,
        state=state,
        target_object_type="engineering_part_revision" if successful else None,
        target_global_id=_uuid(identity + 100) if successful else None,
        target_snapshot_hash=HASH if successful else None,
        field_results=(_field("accepted" if successful else "invalid_value"),),
        trace_id="trace-p6-07-execution-domain",
    )


class Phase6ToolingImportExecutionDomainTests(unittest.TestCase):
    def test_fixture_activation_allows_only_the_exact_synthetic_part_binding(self) -> None:
        activation = FixtureMappingActivation(
            global_id=_uuid(1),
            tenant_id="TENANT-A",
            project_global_id=_uuid(2),
            batch_global_id=_uuid(3),
            source_snapshot_hash=HASH,
            source_sha256="b" * 64,
            customer_scope_id="synthetic-customer",
            fixture_version=FIXTURE_MAPPING_VERSION,
            mapping_revision_global_id=_uuid(4),
            mapping_snapshot_hash="c" * 64,
            source_signature="d" * 64,
            bindings=(
                ExecutionFieldBinding(
                    "Part Name English",
                    "engineering_part_revision",
                    "title",
                ),
            ),
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=_uuid(5),
            trace_id="trace-p6-07-fixture-activation",
        )
        self.assertEqual(activation.snapshot_payload()["state"], "approved_fixture")
        self.assertEqual(len(activation.snapshot_hash), 64)

        with self.assertRaises(RequestValidationFailed):
            replace(
                activation,
                bindings=(
                    ExecutionFieldBinding(
                        "Tooling No.",
                        "tooling_master",
                        "tooling_number",
                    ),
                ),
            )
        with self.assertRaises(RequestValidationFailed):
            replace(activation, fixture_version="customer.production.v1")

    def test_corrections_are_bounded_unique_and_formula_safe(self) -> None:
        entry = CorrectionEntry(
            worksheet_name="Tooling List",
            source_row=7,
            source_header="Part Name English",
            corrected_value="Synthetic corrected part",
        )
        self.assertEqual(validate_correction_entries((entry,)), (entry,))
        with self.assertRaises(RequestValidationFailed):
            validate_correction_entries((entry, entry))
        for value in ("=1+1", " +1", "-1", "@SUM(A1)"):
            with self.subTest(value=value), self.assertRaises(RequestValidationFailed):
                replace(entry, corrected_value=value)

    def test_successful_rows_are_never_replaced_when_retry_is_queued(self) -> None:
        created = _row(10, 7, 1, ImportRowResultState.CREATED)
        retryable = _row(11, 8, 1, ImportRowResultState.FAILED_RETRYABLE)
        initial = ToolingImportJobSnapshot(
            global_id=_uuid(20),
            batch_global_id=_uuid(21),
            preview_global_id=_uuid(22),
            preview_snapshot_hash=HASH,
            attempt=1,
            state=ImportJobState.PARTIALLY_SUCCEEDED,
            row_results=(created, retryable),
            queued_at=NOW,
            updated_at=NOW + timedelta(minutes=1),
        )
        queued_retry = replace(
            initial,
            attempt=2,
            state=ImportJobState.QUEUED,
            updated_at=NOW + timedelta(minutes=2),
            correction_artifact_global_id=_uuid(23),
            correction_artifact_snapshot_hash="b" * 64,
        )
        self.assertEqual(queued_retry.snapshot_payload()["counts"]["created"], 1)
        self.assertEqual(
            queued_retry.snapshot_payload()["counts"]["failed_retryable"],
            1,
        )

        retried = _row(12, 8, 2, ImportRowResultState.CREATED)
        completed = replace(
            queued_retry,
            state=ImportJobState.SUCCEEDED,
            row_results=(created, retryable, retried),
            updated_at=NOW + timedelta(minutes=3),
        )
        self.assertEqual(completed.snapshot_payload()["counts"]["created"], 2)
        self.assertEqual(
            completed.snapshot_payload()["counts"]["failed_retryable"],
            0,
        )
        self.assertEqual(len(completed.snapshot_payload()["rowResults"]), 3)

        with self.assertRaises(RequestValidationFailed):
            replace(
                initial,
                attempt=2,
                state=ImportJobState.QUEUED,
                updated_at=NOW + timedelta(minutes=2),
            )

    def test_reconciliation_is_immutable_and_preserves_rollback_denial_truth(self) -> None:
        item = ReconciliationItem(
            row_result_global_id=_uuid(30),
            target_object_type="engineering_part_revision",
            target_global_id=_uuid(31),
            expected_snapshot_hash=HASH,
            observed_snapshot_hash="b" * 64,
            downstream_reference_count=1,
            state=ReconciliationState.DOWNSTREAM_USED,
        )
        revision = ReconciliationSnapshot(
            global_id=_uuid(32),
            job_global_id=_uuid(33),
            job_snapshot_hash="c" * 64,
            kind="rollback_eligibility",
            items=(item,),
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=_uuid(34),
            trace_id="trace-p6-07-reconciliation",
        )
        self.assertEqual(
            revision.snapshot_payload()["items"][0]["state"],
            "downstream_used",
        )
        self.assertEqual(len(revision.snapshot_hash), 64)
        self.assertEqual(
            rollback_item_state(
                RollbackDecision(
                    RollbackDecisionState.DENIED,
                    "downstream_reference_present",
                )
            ),
            ReconciliationState.DOWNSTREAM_USED,
        )
        self.assertEqual(
            rollback_item_state(
                RollbackDecision(
                    RollbackDecisionState.DENIED,
                    "imported_object_changed",
                )
            ),
            ReconciliationState.CHANGED,
        )

    def test_job_level_reauthorization_failure_retains_completed_row_truth(self) -> None:
        created = _row(40, 7, 1, ImportRowResultState.CREATED)
        failed = ToolingImportJobSnapshot(
            global_id=_uuid(41),
            batch_global_id=_uuid(42),
            preview_global_id=_uuid(43),
            preview_snapshot_hash=HASH,
            attempt=1,
            state=ImportJobState.FAILED_FINAL,
            row_results=(created,),
            queued_at=NOW,
            updated_at=NOW + timedelta(minutes=1),
            failure_code="worker_authorization_revoked",
            failure_message="The worker lost its exact authority.",
            failure_trace_id="trace-p6-07-worker-reauthorization",
        )
        payload = failed.snapshot_payload()
        self.assertEqual(payload["counts"]["created"], 1)
        self.assertEqual(payload["failure"]["code"], "worker_authorization_revoked")
        with self.assertRaises(RequestValidationFailed):
            replace(failed, state=ImportJobState.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
