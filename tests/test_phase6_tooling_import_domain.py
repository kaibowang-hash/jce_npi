from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.tooling.import_domain import (
    ImportJobState,
    ImportFieldResult,
    ImportRowResult,
    ImportRowResultState,
    MappingRevisionState,
    PreviewAction,
    PreviewConfirmation,
    PreviewConfirmationKind,
    RollbackDecisionState,
    RollbackObservation,
    ToolingImportMappingRevision,
    ToolingImportJobSnapshot,
    ToolingImportSource,
    WorkbookRegionKind,
    build_mapping_proposal,
    build_preview,
    confirm_preview,
    derive_job_state,
    detect_tooling_workbook,
    evaluate_rollback,
    inspection_from_snapshot,
    mapping_from_snapshot,
    preview_from_snapshot,
    source_from_snapshot,
)
from npi_core.tooling.xlsx_fixture import (
    SYNTHETIC_HEADERS,
    build_fixture_set,
    build_sanitized_tooling_workbook,
)
from npi_core.tooling.import_mapping_catalog import reviewed_mapping_rows
from npi_core.tooling.xlsx_inspector import (
    inspect,
    read_validated_workbook,
    read_validated_workbook_bytes,
)
from npi_core.foundation.errors import RequestValidationFailed


ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = ROOT / "docs/reference/TOOLING_LIST_FIELD_MAPPING.csv"
NOW = datetime(2026, 8, 9, 4, 0, tzinfo=UTC)


def _source(sha256: str, size_bytes: int, file_name: str) -> ToolingImportSource:
    return ToolingImportSource(
        batch_global_id=UUID("91000000-0000-4000-8000-000000000001"),
        tenant_id="tenant-synthetic",
        project_global_id=UUID("91000000-0000-4000-8000-000000000002"),
        customer_scope_id="customer-synthetic",
        file_revision_global_id=UUID("91000000-0000-4000-8000-000000000003"),
        file_optimistic_version=1,
        frappe_content_hash="f" * 64,
        file_name=file_name,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_bytes=size_bytes,
        sha256=sha256,
        created_by_user_id="synthetic.importer@example.invalid",
        created_at=NOW,
        request_id=UUID("91000000-0000-4000-8000-000000000004"),
        trace_id="trace-p6-07-synthetic",
    )


def _mapping_rows() -> list[dict[str, str]]:
    with MAPPING_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class Phase6ToolingImportDomainTests(unittest.TestCase):
    def test_fixture_is_deterministic_synthetic_and_matches_all_43_columns(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = build_fixture_set(Path(first_dir))
            second = build_fixture_set(Path(second_dir))

        self.assertFalse(first["containsCustomerData"])
        self.assertEqual(first, second)
        expected = json.loads(
            (ROOT / "tests/fixtures/p6-07-tooling-import/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(first, expected)
        self.assertEqual(
            list(SYNTHETIC_HEADERS),
            [row["source_column"] for row in _mapping_rows()],
        )
        self.assertEqual(len(SYNTHETIC_HEADERS), 43)
        self.assertEqual(
            list(reviewed_mapping_rows()),
            [
                {
                    key: row[key]
                    for key in ("source_column", "target_object", "suggested_field")
                }
                for row in _mapping_rows()
            ],
        )
        self.assertEqual(
            [item["titleRowCount"] for item in first["fixtures"]],
            [1, 3],
        )

    def test_passive_report_redacts_cells_while_validated_reader_retains_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "synthetic.xlsx"
            build_sanitized_tooling_workbook(workbook, title_row_count=1)
            input_bytes = workbook.stat().st_size
            passive = inspect(workbook, 1_000, 10_000_000)
            validated = read_validated_workbook(workbook, 1_000, 10_000_000)
            validated_bytes = read_validated_workbook_bytes(
                workbook.read_bytes(),
                file_name=workbook.name,
                max_entries=1_000,
                max_uncompressed_bytes=10_000_000,
            )

        self.assertNotIn("SYN-MOLD-001", str(passive))
        self.assertIn("SYN-MOLD-001", str(validated["worksheets"]))
        self.assertEqual(passive, validated["inspection"])
        self.assertEqual(passive["input_bytes"], input_bytes)
        self.assertEqual(passive["formula_errors"][0]["error"], "#REF!")
        self.assertEqual(len(passive["floating_image_anchors"]), 2)
        self.assertEqual(validated_bytes, validated)

    def test_detection_is_position_independent_and_separates_regions_images(self) -> None:
        detected: list[tuple[int, list[str], list[bool]]] = []
        with tempfile.TemporaryDirectory() as directory:
            for index, title_rows in enumerate((1, 3), start=1):
                workbook = Path(directory) / f"synthetic-{index}.xlsx"
                manifest = build_sanitized_tooling_workbook(
                    workbook, title_row_count=title_rows
                )
                source = _source(
                    str(manifest["sha256"]), workbook.stat().st_size, workbook.name
                )
                validated = read_validated_workbook(workbook, 1_000, 10_000_000)
                if index == 1:
                    with self.assertRaises(RequestValidationFailed):
                        detect_tooling_workbook(
                            global_id=UUID(
                                "91000000-0000-4000-8000-000000000019"
                            ),
                            source=replace(source, size_bytes=source.size_bytes + 1),
                            validated_workbook=validated,
                            expected_headers=SYNTHETIC_HEADERS,
                            created_at=NOW,
                        )
                inspection, rows = detect_tooling_workbook(
                    global_id=UUID(f"91000000-0000-4000-8000-00000000001{index}"),
                    source=source,
                    validated_workbook=validated,
                    expected_headers=SYNTHETIC_HEADERS,
                    created_at=NOW,
                )
                detected.append(
                    (
                        inspection.header_row,
                        [item.kind.value for item in inspection.regions],
                        [item.requires_confirmation for item in inspection.image_anchors],
                    )
                )
                self.assertEqual(len(inspection.columns), 43)
                self.assertEqual(len(rows), 3)
                self.assertEqual(inspection.formula_errors, (("AI3" if title_rows == 1 else "AI5", "#REF!"),))
                self.assertEqual(
                    [item.confidence for item in inspection.image_anchors],
                    ["high", "ambiguous"],
                )

        self.assertEqual([item[0] for item in detected], [2, 4])
        for _header, regions, confirmations in detected:
            self.assertIn(WorkbookRegionKind.DATA.value, regions)
            self.assertIn(WorkbookRegionKind.SHARED_TOOLING_MARKER.value, regions)
            self.assertIn(WorkbookRegionKind.SHARED_TOOLING_DATA.value, regions)
            self.assertIn(WorkbookRegionKind.SUMMARY.value, regions)
            self.assertEqual(confirmations, [False, True])

    def test_mapping_proposal_and_preview_keep_raw_values_and_block_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "synthetic.xlsx"
            manifest = build_sanitized_tooling_workbook(workbook, title_row_count=1)
            source = _source(str(manifest["sha256"]), workbook.stat().st_size, workbook.name)
            inspection, data_rows = detect_tooling_workbook(
                global_id=UUID("91000000-0000-4000-8000-000000000020"),
                source=source,
                validated_workbook=read_validated_workbook(workbook, 1_000, 10_000_000),
                expected_headers=SYNTHETIC_HEADERS,
                created_at=NOW,
            )
            mapping = build_mapping_proposal(
                global_id=UUID("91000000-0000-4000-8000-000000000021"),
                mapping_global_id=UUID("91000000-0000-4000-8000-000000000022"),
                inspection=inspection,
                reviewed_rows=_mapping_rows(),
                customer_scope_id=source.customer_scope_id,
                template_key="synthetic-tooling-list.v1",
                reason="Create a visibly synthetic proposal for controlled verification.",
                actor=source.created_by_user_id,
                created_at=NOW,
            )
            preview = build_preview(
                global_id=UUID("91000000-0000-4000-8000-000000000023"),
                source=source,
                inspection=inspection,
                mapping=mapping,
                data_rows=data_rows,
                created_at=NOW,
            )
            with self.assertRaises(RequestValidationFailed):
                build_preview(
                    global_id=UUID("91000000-0000-4000-8000-000000000024"),
                    source=replace(
                        source,
                        batch_global_id=UUID(
                            "91000000-0000-4000-8000-000000000099"
                        ),
                    ),
                    inspection=inspection,
                    mapping=mapping,
                    data_rows=data_rows,
                    created_at=NOW,
                )
            with self.assertRaises(RequestValidationFailed):
                build_mapping_proposal(
                    global_id=UUID("91000000-0000-4000-8000-000000000025"),
                    mapping_global_id=UUID(
                        "91000000-0000-4000-8000-000000000026"
                    ),
                    inspection=inspection,
                    reviewed_rows=(*_mapping_rows(), _mapping_rows()[0]),
                    customer_scope_id=source.customer_scope_id,
                    template_key="synthetic-tooling-list.v1",
                    reason="Reject duplicate reviewed source columns.",
                    actor=source.created_by_user_id,
                    created_at=NOW,
                )
            unknown_rows = _mapping_rows()
            unknown_rows[0] = {
                **unknown_rows[0],
                "source_column": "Synthetic Unknown Column",
            }
            with self.assertRaises(RequestValidationFailed):
                build_mapping_proposal(
                    global_id=UUID("91000000-0000-4000-8000-000000000027"),
                    mapping_global_id=UUID(
                        "91000000-0000-4000-8000-000000000028"
                    ),
                    inspection=inspection,
                    reviewed_rows=unknown_rows,
                    customer_scope_id=source.customer_scope_id,
                    template_key="synthetic-tooling-list.v1",
                    reason="Reject unknown reviewed source columns.",
                    actor=source.created_by_user_id,
                    created_at=NOW,
                )

        self.assertEqual(mapping.state, MappingRevisionState.PROPOSAL)
        self.assertEqual(len(mapping.entries), 43)
        self.assertTrue(all(row.action is PreviewAction.BLOCKED for row in preview.rows))
        self.assertFalse(preview.execution_eligible)
        self.assertTrue(all("mapping_activation_unavailable" in row.reason_codes for row in preview.rows))
        first_fields = {item.source_header: item for item in preview.rows[0].fields}
        self.assertEqual(first_fields["KW Tooling No."].raw_value, "SYN-TOOL-001\nNew Tooling")
        self.assertEqual(first_fields["KW Tooling No."].normalized_candidates, ("SYN-TOOL-001",))
        self.assertEqual(first_fields["KW Tooling No."].state_candidate, "new_tooling")
        self.assertIn("formula_error", preview.rows[0].reason_codes)
        self.assertIn("required_value_missing", preview.rows[1].reason_codes)
        self.assertIn("relationship_confirmation_required", preview.rows[0].reason_codes)

        controlled_rows = tuple(
            replace(
                row,
                action=(PreviewAction.CREATE if index == 0 else PreviewAction.BLOCKED),
                requires_confirmation=False,
            )
            for index, row in enumerate(preview.rows)
        )
        controlled_preview = replace(
            preview,
            mapping_state=MappingRevisionState.APPROVED_FIXTURE,
            rows=controlled_rows,
        )
        self.assertTrue(controlled_preview.execution_eligible)
        self.assertFalse(
            replace(
                controlled_preview,
                rows=(
                    replace(
                        controlled_rows[0],
                        action=PreviewAction.BLOCKED,
                        requires_confirmation=True,
                    ),
                    *controlled_rows[1:],
                ),
            ).execution_eligible
        )

    def test_snapshot_hydration_and_confirmation_create_an_immutable_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "synthetic.xlsx"
            manifest = build_sanitized_tooling_workbook(workbook, title_row_count=1)
            source = _source(
                str(manifest["sha256"]), workbook.stat().st_size, workbook.name
            )
            inspection, data_rows = detect_tooling_workbook(
                global_id=UUID("91000000-0000-4000-8000-000000000051"),
                source=source,
                validated_workbook=read_validated_workbook_bytes(
                    workbook.read_bytes(),
                    file_name=workbook.name,
                    max_entries=1_000,
                    max_uncompressed_bytes=10_000_000,
                ),
                expected_headers=SYNTHETIC_HEADERS,
                created_at=NOW,
            )
            mapping = build_mapping_proposal(
                global_id=UUID("91000000-0000-4000-8000-000000000052"),
                mapping_global_id=UUID("91000000-0000-4000-8000-000000000053"),
                inspection=inspection,
                reviewed_rows=_mapping_rows(),
                customer_scope_id=source.customer_scope_id,
                template_key="synthetic-tooling-list.v1",
                reason="Create an immutable synthetic preview chain.",
                actor=source.created_by_user_id,
                created_at=NOW,
            )
            predecessor = build_preview(
                global_id=UUID("91000000-0000-4000-8000-000000000054"),
                source=source,
                inspection=inspection,
                mapping=mapping,
                data_rows=data_rows,
                created_at=NOW,
            )

        before_payload = predecessor.snapshot_payload()
        before_hash = predecessor.snapshot_hash
        row = next(item for item in predecessor.rows if item.requires_confirmation)
        confirmations = (
            PreviewConfirmation(
                kind=PreviewConfirmationKind.IMAGE_ANCHOR,
                worksheet_name=row.worksheet_name,
                source_row=row.source_row,
                anchor_key="synthetic.image-0001",
                selected_target_object="tooling_master",
                selected_target_global_id=UUID(
                    "91000000-0000-4000-8000-000000000055"
                ),
                selected_target_snapshot_hash="c" * 64,
                reason="Confirm the exact synthetic image anchor.",
                confirmed_by_user_id=source.created_by_user_id,
                confirmed_at=NOW + timedelta(minutes=1),
            ),
            PreviewConfirmation(
                kind=PreviewConfirmationKind.RELATIONSHIP,
                worksheet_name=row.worksheet_name,
                source_row=row.source_row,
                anchor_key=None,
                selected_target_object="tooling_master",
                selected_target_global_id=UUID(
                    "91000000-0000-4000-8000-000000000055"
                ),
                selected_target_snapshot_hash="c" * 64,
                reason="Confirm the exact synthetic Tooling relationship.",
                confirmed_by_user_id=source.created_by_user_id,
                confirmed_at=NOW + timedelta(minutes=1),
            ),
        )
        successor = confirm_preview(
            global_id=UUID("91000000-0000-4000-8000-000000000056"),
            predecessor=predecessor,
            confirmations=confirmations,
            created_at=NOW + timedelta(minutes=1),
        )

        self.assertEqual(predecessor.snapshot_payload(), before_payload)
        self.assertEqual(predecessor.snapshot_hash, before_hash)
        self.assertEqual(predecessor.preview_version, 1)
        self.assertFalse(predecessor.confirmations)
        self.assertEqual(successor.preview_global_id, predecessor.preview_global_id)
        self.assertEqual(successor.preview_version, 2)
        self.assertEqual(successor.predecessor_global_id, predecessor.global_id)
        self.assertEqual(successor.predecessor_snapshot_hash, predecessor.snapshot_hash)
        self.assertEqual(successor.confirmations, confirmations)
        self.assertEqual(source_from_snapshot(source.snapshot_payload()), source)
        self.assertEqual(
            inspection_from_snapshot(source, inspection.snapshot_payload()), inspection
        )
        self.assertEqual(mapping_from_snapshot(source, mapping.snapshot_payload()), mapping)
        self.assertEqual(
            preview_from_snapshot(source, predecessor.snapshot_payload()), predecessor
        )
        self.assertEqual(
            preview_from_snapshot(source, successor.snapshot_payload()), successor
        )
        tampered = dict(successor.snapshot_payload())
        tampered["sourceSnapshotHash"] = "d" * 64
        with self.assertRaises(RequestValidationFailed):
            preview_from_snapshot(source, tampered)

    def test_production_mapping_state_is_not_constructible(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            ToolingImportMappingRevision(
                global_id=UUID("91000000-0000-4000-8000-000000000031"),
                mapping_global_id=UUID("91000000-0000-4000-8000-000000000032"),
                source=_source("a" * 64, 1, "synthetic.xlsx"),
                inspection_global_id=UUID("91000000-0000-4000-8000-000000000033"),
                inspection_snapshot_hash="b" * 64,
                mapping_version=1,
                state=MappingRevisionState.APPROVED_PRODUCTION,
                customer_scope_id="customer-synthetic",
                template_key="synthetic-tooling-list.v1",
                source_signature="a" * 64,
                entries=(),
                reason="Production approval must remain unavailable.",
                created_by_user_id="synthetic.importer@example.invalid",
                created_at=NOW,
            )

    def test_job_state_never_hides_partial_failure_or_confirmation(self) -> None:
        self.assertEqual(derive_job_state(()), ImportJobState.QUEUED)
        self.assertEqual(
            derive_job_state((ImportRowResultState.CREATED, ImportRowResultState.FAILED_RETRYABLE)),
            ImportJobState.PARTIALLY_SUCCEEDED,
        )
        self.assertEqual(
            derive_job_state((ImportRowResultState.CONFIRMATION_REQUIRED,)),
            ImportJobState.FAILED_FINAL,
        )
        self.assertEqual(
            derive_job_state((ImportRowResultState.CREATED, ImportRowResultState.SKIPPED)),
            ImportJobState.SUCCEEDED,
        )

    def test_job_snapshot_requires_exact_target_truth_and_derived_partial_state(self) -> None:
        created = ImportRowResult(
            global_id=UUID("91000000-0000-4000-8000-000000000041"),
            worksheet_name="Synthetic Tooling List",
            source_row=3,
            attempt=1,
            state=ImportRowResultState.CREATED,
            target_object_type="tooling_master",
            target_global_id=UUID("91000000-0000-4000-8000-000000000042"),
            target_snapshot_hash="a" * 64,
            field_results=(ImportFieldResult(1, "Item", "created", "The field was imported."),),
            trace_id="trace-created",
        )
        failed = ImportRowResult(
            global_id=UUID("91000000-0000-4000-8000-000000000043"),
            worksheet_name="Synthetic Tooling List",
            source_row=4,
            attempt=1,
            state=ImportRowResultState.FAILED_RETRYABLE,
            target_object_type=None,
            target_global_id=None,
            target_snapshot_hash=None,
            field_results=(ImportFieldResult(3, "Part Name English", "required_value_missing", "Enter the required source value."),),
            trace_id="trace-failed",
        )
        job = ToolingImportJobSnapshot(
            global_id=UUID("91000000-0000-4000-8000-000000000044"),
            batch_global_id=UUID("91000000-0000-4000-8000-000000000001"),
            preview_global_id=UUID("91000000-0000-4000-8000-000000000023"),
            preview_snapshot_hash="b" * 64,
            attempt=1,
            state=ImportJobState.PARTIALLY_SUCCEEDED,
            row_results=(created, failed),
            queued_at=NOW,
            updated_at=NOW,
        )
        self.assertEqual(job.snapshot_payload()["counts"]["created"], 1)
        self.assertEqual(job.snapshot_payload()["counts"]["failed_retryable"], 1)
        with self.assertRaises(RequestValidationFailed):
            ImportRowResult(
                global_id=UUID("91000000-0000-4000-8000-000000000045"),
                worksheet_name="Synthetic Tooling List",
                source_row=5,
                attempt=1,
                state=ImportRowResultState.CREATED,
                target_object_type=None,
                target_global_id=None,
                target_snapshot_hash=None,
                field_results=(),
                trace_id="trace-false-success",
            )
        with self.assertRaises(RequestValidationFailed):
            replace(
                created,
                field_results=(
                    ImportFieldResult(1, "Item", "created", "The field was imported."),
                    ImportFieldResult(1, "Item", "created", "The field was imported."),
                ),
            )

    def test_rollback_allows_only_unchanged_unused_batch_created_objects(self) -> None:
        allowed = evaluate_rollback(RollbackObservation("create", True, True, 0))
        changed = evaluate_rollback(RollbackObservation("create", True, False, 0))
        downstream = evaluate_rollback(RollbackObservation("create", True, True, 1))
        updated = evaluate_rollback(RollbackObservation("update", False, True, 0))
        self.assertEqual(allowed.state, RollbackDecisionState.ALLOWED)
        self.assertEqual(changed.reason_code, "imported_object_changed")
        self.assertEqual(downstream.reason_code, "downstream_reference_present")
        self.assertEqual(updated.reason_code, "pre_existing_object_requires_forward_correction")
        for invalid in (
            ("delete", True, True, 0),
            ("create", 1, True, 0),
            ("create", True, True, -1),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(
                RequestValidationFailed
            ):
                evaluate_rollback(RollbackObservation(*invalid))


if __name__ == "__main__":
    unittest.main()
