from __future__ import annotations

import csv
import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/verify_v1_2_reconciliation.py"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)
    )


def _png_document(
    *,
    width: int = 1,
    height: int = 1,
    extra_chunks: tuple[bytes, ...] = (),
    include_iend: bool = True,
) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00\x00")
    payload = (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + b"".join(extra_chunks)
        + _png_chunk(b"IDAT", idat)
    )
    if include_iend:
        payload += _png_chunk(b"IEND", b"")
    return payload


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_v1_2_reconciliation", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load reconciliation verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V12ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = _load_verifier()

    def test_generated_artifacts_are_current(self) -> None:
        self.verifier.verify_generated_artifacts()

    def test_trace_sets_are_complete_and_consistent(self) -> None:
        self.verifier.verify_trace_sets()

    def test_phase9_completed_traces_are_bound_to_final_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id, expected_truth in (
            self.verifier.EXPECTED_P9_COMPLETED_TRACES.items()
        ):
            row = by_id[requirement_id]
            self.assertEqual((row["phase"], row["status"]), expected_truth)
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            expected_evidence = self.verifier.EXPECTED_P9_COMPLETION_EVIDENCE[
                requirement_id
            ]
            self.assertTrue(expected_evidence.issubset(evidence), requirement_id)
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )

    def test_erp_customization_requirements_and_exact_hold_evidence(self) -> None:
        self.verifier.verify_erp_customization_requirements_document()
        self.verifier.verify_p8_07f_fact_documents()
        with self.verifier.TRACE.open(newline="", encoding="utf-8") as handle:
            rows = {
                row["requirement_id"]: row
                for row in csv.DictReader(handle)
            }
        expected = self.verifier.EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_HOLD_STATUSES
        actual = {
            requirement_id
            for requirement_id, row in rows.items()
            if self.verifier.EXPECTED_P8_07F_FACT_EVIDENCE.issubset({
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            })
        }
        self.assertEqual(actual, set(expected))
        self.assertEqual(
            {requirement_id: rows[requirement_id]["status"] for requirement_id in expected},
            expected,
        )

    def test_external_portals_are_deferred_without_rewriting_requirements(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id in ("FR-CO-003", "FR-CO-004"):
            row = by_id[requirement_id]
            self.assertEqual(
                (
                    row["priority"],
                    row["phase"],
                    row["status"],
                    row["source"],
                    row["trace_kind"],
                    row["canonical_ids"],
                ),
                (
                    "P1",
                    "9",
                    "REMAPPED_PHASE_9",
                    "docs/DETAILED_REQUIREMENTS.md",
                    "PACK_CANONICAL",
                    requirement_id,
                ),
            )
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            self.assertTrue(
                self.verifier.EXPECTED_POST_V1_2_DEFERRED_PORTAL_EVIDENCE.issubset(
                    evidence
                )
            )

        requirement_source = (ROOT / "docs/DETAILED_REQUIREMENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "| FR-CO-003 | P1 | 供应商门户支持里程碑更新、文件上传、报价/问题回复和整改证据。 | 供应商只能看到授权模具/项目。 |",
            requirement_source,
        )
        self.assertIn(
            "| FR-CO-004 | P1 | 客户门户支持资料提交、样件/文件审阅、批准/驳回和反馈。 | 客户批准形成时间戳和版本锁定。 |",
            requirement_source,
        )
        self.assertNotIn("USER_APPROVED_POST_V1_2_DEFERRED", requirement_source)

        governed_text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "implementation/phase-4-requirement-anchor.md",
                "implementation/backlog.yaml",
                "implementation/ROADMAP.md",
                "implementation/EXECUTION_PLAN.md",
                "implementation/DECISION_LOG.md",
            )
        )
        self.assertIn("USER_APPROVED_POST_V1_2_DEFERRED", governed_text)
        self.assertIn("internal supplier", governed_text)
        self.assertIn("customer approval evidence", governed_text)

        backlog = (ROOT / "implementation/backlog.yaml").read_text(encoding="utf-8")
        deferred_count = backlog.count(
            "decision_marker: USER_APPROVED_POST_V1_2_DEFERRED"
        )
        self.assertIn(deferred_count, (2, 4))
        self.assertEqual(
            backlog.count("delivery_release: POST_V1_2_FUTURE_RELEASE"),
            deferred_count,
        )
        self.assertEqual(backlog.count("restoration_trigger:"), deferred_count)
        self.assertEqual(backlog.count("- FR-CO-003"), 1)
        self.assertEqual(backlog.count("- FR-CO-004"), 1)

        customer_owned_pilot = backlog.split("  - id: M9-04", 1)[1].split(
            "  - id: M9-05", 1
        )[0]
        new_tool_pilot = backlog.split("  - id: M9-05", 1)[1].split(
            "  - id: M9-06", 1
        )[0]
        for pilot in (customer_owned_pilot, new_tool_pilot):
            if deferred_count == 4:
                self.assertIn(
                    "decision_marker: USER_APPROVED_POST_V1_2_DEFERRED", pilot
                )
                self.assertIn(
                    "delivery_release: POST_V1_2_FUTURE_RELEASE", pilot
                )
                self.assertIn("restoration_trigger:", pilot)
                self.assertIn("representative non-production data", pilot)
                self.assertIn("no real-project pilot claim", pilot)
            else:
                self.assertNotIn("decision_marker:", pilot)
                self.assertNotIn("delivery_release:", pilot)
                self.assertNotIn("restoration_trigger:", pilot)

        execution_plan = (ROOT / "implementation/EXECUTION_PLAN.md").read_text(
            encoding="utf-8"
        )
        normalized_execution_plan = " ".join(execution_plan.split())
        if deferred_count == 4:
            self.assertIn(
                "final V1.2 completion exclude FR-CO-003/004 external",
                normalized_execution_plan,
            )
            self.assertIn("M9-04/M9-05 real", normalized_execution_plan)
            self.assertIn("remain required V1.2 scope", normalized_execution_plan)
            self.assertIn(
                "must not be reported as a real-project pilot or real-user 80-percent usage result",
                normalized_execution_plan,
            )
        else:
            self.assertIn(
                "final V1.2 completion exclude only", normalized_execution_plan
            )
            self.assertIn(
                "cannot claim either portal implemented", normalized_execution_plan
            )

        phase_status = (ROOT / "implementation/PHASE_STATUS.yaml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            phase_status.count("decision_marker: USER_APPROVED_POST_V1_2_DEFERRED"),
            1,
        )
        self.assertIn("product_code_authorized: false", phase_status)
        self.assertIn("SEPARATE_FUTURE_RELEASE_CONTROLLER", phase_status)

    def test_p7_08_mobile_field_trace_is_technically_verified(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        row = next(item for item in rows if item["requirement_id"] == "UX-020")
        self.assertEqual(row["phase"], "7")
        self.assertEqual(row["status"], "TECHNICAL_VERIFIED")
        self.assertEqual(
            {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            },
            self.verifier.EXPECTED_P7_08_EVIDENCE,
        )

    def test_launchflow_trace_is_verified_with_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        row = next(item for item in rows if item["requirement_id"] == "FR-BR-001")
        self.assertEqual(row["status"], "TECHNICAL_VERIFIED")
        self.assertIn(
            "implementation/evidence/reconciliation/r1-02-validation.md",
            row["evidence"],
        )

    def test_p5_06_print_foundation_trace_is_verified_without_form_policy(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id in ("FR-PRN-001", "FR-PRN-002"):
            row = by_id[requirement_id]
            completed_trace = self.verifier.EXPECTED_P7_COMPLETED_TRACES.get(
                requirement_id
            )
            self.assertEqual(
                row["status"],
                completed_trace[1] if completed_trace else "TECHNICAL_VERIFIED",
            )
            expected_evidence = set(
                completed_trace[2]
                if completed_trace
                else self.verifier.EXPECTED_P5_06_TRACE[requirement_id][1]
            )
            if requirement_id in self.verifier.EXPECTED_P7_CARRIED_FOUNDATIONS:
                expected_evidence |= self.verifier.EXPECTED_P7_ANCHOR_EVIDENCE
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                expected_evidence,
            )
        self.assertEqual(
            by_id["FR-PRN-003"]["status"],
            "DECISION_REQUIRED_DR_REC_003_004",
        )

    def test_p6_02_trace_is_verified_with_controlled_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id, expected in self.verifier.EXPECTED_P6_02_TRACE.items():
            row = by_id[requirement_id]
            self.assertEqual(row["status"], expected[1])
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                expected[5],
            )

    def test_p6_03_trace_is_verified_with_controlled_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id, expected in self.verifier.EXPECTED_P6_03_TRACE.items():
            row = by_id[requirement_id]
            self.assertEqual(row["status"], expected[1])
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                expected[5],
            )

    def test_p6_06_trace_is_verified_with_controlled_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id, expected in self.verifier.EXPECTED_P6_06_TRACE.items():
            row = by_id[requirement_id]
            expected_status = self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION.get(
                requirement_id,
                expected[1],
            )
            self.assertEqual(row["status"], expected_status)
            self.assertEqual(
                row["phase"],
                "8"
                if requirement_id
                in self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION
                else "6",
            )
            expected_evidence = set(expected[5])
            if requirement_id in self.verifier.EXPECTED_P8_CARRIED_FOUNDATIONS:
                expected_evidence |= self.verifier.EXPECTED_P8_ANCHOR_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_01_EVIDENCE_REQUIREMENTS:
                expected_evidence |= self.verifier.EXPECTED_P8_01_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_02_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_02_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_03_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_03_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_04_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_04_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_05_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_06_COMPLETED_EVIDENCE
            if (
                requirement_id
                in self.verifier.EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_HOLD_STATUSES
            ):
                expected_evidence |= self.verifier.EXPECTED_P8_07F_FACT_EVIDENCE
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                expected_evidence,
            )

    def test_p6_07_trace_is_verified_with_controlled_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id, expected in self.verifier.EXPECTED_P6_07_TRACE.items():
            row = by_id[requirement_id]
            self.assertEqual(row["phase"], expected[1])
            self.assertEqual(row["status"], expected[2])
            expected_evidence = set(expected[6])
            if requirement_id in self.verifier.EXPECTED_P8_CARRIED_FOUNDATIONS:
                expected_evidence |= self.verifier.EXPECTED_P8_ANCHOR_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_01_EVIDENCE_REQUIREMENTS:
                expected_evidence |= self.verifier.EXPECTED_P8_01_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_02_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_02_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_03_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_03_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_04_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_04_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_05_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION:
                expected_evidence |= self.verifier.EXPECTED_P8_06_COMPLETED_EVIDENCE
            if requirement_id in self.verifier.EXPECTED_P8_07_PLAN_REQUIREMENTS:
                expected_evidence |= self.verifier.EXPECTED_P8_07_PLAN_EVIDENCE
                expected_evidence |= self.verifier.EXPECTED_P8_07_COMPLETED_EVIDENCE
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                expected_evidence,
            )

    def test_r1_03_trace_is_verified_with_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        self.assertEqual(by_id["FR-UX-039"]["status"], "TECHNICAL_VERIFIED")
        self.assertEqual(by_id["UX-011"]["status"], "TECHNICAL_VERIFIED")
        self.assertEqual(
            by_id["UX-018"]["status"],
            "TECHNICAL_VERIFIED_FOUNDATION",
        )
        for requirement_id in ("FR-UX-039", "UX-011", "UX-018"):
            self.assertIn(
                "implementation/evidence/reconciliation/r1-03-validation.md",
                by_id[requirement_id]["evidence"],
            )
        for _, expected_evidence in self.verifier.EXPECTED_R1_03_TRACE.values():
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )

    def test_p7_00_trace_is_anchored_to_exact_atomic_tasks(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for task_id, requirement_ids in (
            self.verifier.EXPECTED_P7_ANCHOR_ALLOCATION.items()
        ):
            anchored_status = f"ANCHORED_{task_id.replace('-', '_')}"
            for requirement_id in requirement_ids:
                row = by_id[requirement_id]
                completed_trace = self.verifier.EXPECTED_P7_COMPLETED_TRACES.get(
                    requirement_id
                )
                p8_06_status = self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION.get(
                    requirement_id
                )
                expected_phase, expected_status = (
                    ("8", p8_06_status)
                    if p8_06_status
                    else completed_trace[:2]
                    if completed_trace
                    else ("7", anchored_status)
                )
                self.assertEqual(row["phase"], expected_phase)
                self.assertEqual(row["status"], expected_status)
                evidence = {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                }
                self.assertTrue(
                    self.verifier.EXPECTED_P7_ANCHOR_EVIDENCE.issubset(
                        evidence
                    )
                )
                if completed_trace:
                    expected_evidence = set(completed_trace[2])
                    if (
                        requirement_id
                        in self.verifier.EXPECTED_P8_CARRIED_FOUNDATIONS
                    ):
                        expected_evidence |= self.verifier.EXPECTED_P8_ANCHOR_EVIDENCE
                    if (
                        requirement_id
                        in self.verifier.EXPECTED_P8_01_EVIDENCE_REQUIREMENTS
                    ):
                        expected_evidence |= self.verifier.EXPECTED_P8_01_COMPLETED_EVIDENCE
                    if requirement_id in self.verifier.EXPECTED_P8_02_COMPLETED_ALLOCATION:
                        expected_evidence |= self.verifier.EXPECTED_P8_02_COMPLETED_EVIDENCE
                    if requirement_id in self.verifier.EXPECTED_P8_03_COMPLETED_ALLOCATION:
                        expected_evidence |= self.verifier.EXPECTED_P8_03_COMPLETED_EVIDENCE
                    if requirement_id in self.verifier.EXPECTED_P8_04_COMPLETED_ALLOCATION:
                        expected_evidence |= self.verifier.EXPECTED_P8_04_COMPLETED_EVIDENCE
                    if requirement_id in self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION:
                        expected_evidence |= self.verifier.EXPECTED_P8_05_COMPLETED_EVIDENCE
                    if requirement_id in self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION:
                        expected_evidence |= self.verifier.EXPECTED_P8_06_COMPLETED_EVIDENCE
                    if (
                        requirement_id
                        in self.verifier.EXPECTED_ERP_CUSTOMIZATION_REQUIREMENTS_HOLD_STATUSES
                    ):
                        expected_evidence |= self.verifier.EXPECTED_P8_07F_FACT_EVIDENCE
                    self.assertEqual(evidence, expected_evidence)
                for evidence_path in evidence:
                    self.assertTrue(
                        (self.verifier.ROOT / evidence_path).is_file(),
                        evidence_path,
                    )
        for requirement_id, expected_trace in (
            self.verifier.EXPECTED_P7_CARRIED_FOUNDATIONS.items()
        ):
            row = by_id[requirement_id]
            self.assertEqual((row["phase"], row["status"]), expected_trace)
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            self.assertTrue(
                self.verifier.EXPECTED_P7_ANCHOR_EVIDENCE.issubset(evidence)
            )

    def test_p8_00_trace_is_anchored_without_overclaiming_holds(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for task_id, requirement_ids in (
            self.verifier.EXPECTED_P8_ANCHOR_ALLOCATION.items()
        ):
            anchored_status = f"ANCHORED_{task_id.replace('-', '_')}"
            for requirement_id in requirement_ids:
                row = by_id[requirement_id]
                completed_status = self.verifier.EXPECTED_P8_07_COMPLETED_ALLOCATION.get(
                    requirement_id,
                    self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION.get(
                        requirement_id,
                        self.verifier.EXPECTED_P8_01_COMPLETED_ALLOCATION.get(
                            requirement_id,
                            self.verifier.EXPECTED_P8_02_COMPLETED_ALLOCATION.get(
                                requirement_id,
                                self.verifier.EXPECTED_P8_03_COMPLETED_ALLOCATION.get(
                                    requirement_id,
                                    self.verifier.EXPECTED_P8_04_COMPLETED_ALLOCATION.get(
                                        requirement_id,
                                        self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION.get(
                                            requirement_id,
                                            anchored_status,
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                )
                expected_trace = (
                    ("8", completed_status)
                    if completed_status != anchored_status
                    else self.verifier.EXPECTED_P8_CARRIED_FOUNDATIONS.get(
                        requirement_id,
                        ("8", anchored_status),
                    )
                )
                self.assertEqual((row["phase"], row["status"]), expected_trace)
                evidence = {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                }
                self.assertTrue(
                    self.verifier.EXPECTED_P8_ANCHOR_EVIDENCE.issubset(evidence)
                )
                if requirement_id in self.verifier.EXPECTED_P8_01_EVIDENCE_REQUIREMENTS:
                    self.assertTrue(
                        self.verifier.EXPECTED_P8_01_COMPLETED_EVIDENCE.issubset(
                            evidence
                        )
                    )
                if requirement_id in self.verifier.EXPECTED_P8_02_COMPLETED_ALLOCATION:
                    self.assertTrue(
                        self.verifier.EXPECTED_P8_02_COMPLETED_EVIDENCE.issubset(
                            evidence
                        )
                    )
                if requirement_id in self.verifier.EXPECTED_P8_03_COMPLETED_ALLOCATION:
                    self.assertTrue(
                        self.verifier.EXPECTED_P8_03_COMPLETED_EVIDENCE.issubset(
                            evidence
                        )
                    )
                if requirement_id in self.verifier.EXPECTED_P8_04_COMPLETED_ALLOCATION:
                    self.assertTrue(
                        self.verifier.EXPECTED_P8_04_COMPLETED_EVIDENCE.issubset(
                            evidence
                        )
                    )
                if requirement_id in self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION:
                    self.assertTrue(
                        self.verifier.EXPECTED_P8_05_COMPLETED_EVIDENCE.issubset(
                            evidence
                        )
                    )
                if requirement_id in self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION:
                    self.assertTrue(
                        self.verifier.EXPECTED_P8_06_COMPLETED_EVIDENCE.issubset(
                            evidence
                        )
                    )

        for requirement_id, expected_trace in {
            **self.verifier.EXPECTED_P8_CARRIED_FOUNDATIONS,
            **self.verifier.EXPECTED_P8_SCOPED_HOLDS,
        }.items():
            row = by_id[requirement_id]
            completed_status = self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION.get(
                requirement_id,
                self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION.get(
                    requirement_id,
                    self.verifier.EXPECTED_P8_04_COMPLETED_ALLOCATION.get(
                        requirement_id,
                        self.verifier.EXPECTED_P8_03_COMPLETED_ALLOCATION.get(
                            requirement_id
                        ),
                    ),
                ),
            )
            effective_trace = (
                ("8", completed_status)
                if completed_status is not None
                else expected_trace
            )
            self.assertEqual((row["phase"], row["status"]), effective_trace)
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            self.assertTrue(
                self.verifier.EXPECTED_P8_ANCHOR_EVIDENCE.issubset(evidence)
            )
            if requirement_id in self.verifier.EXPECTED_P8_01_EVIDENCE_REQUIREMENTS:
                self.assertTrue(
                    self.verifier.EXPECTED_P8_01_COMPLETED_EVIDENCE.issubset(
                        evidence
                    )
                )
            if requirement_id in self.verifier.EXPECTED_P8_02_COMPLETED_ALLOCATION:
                self.assertTrue(
                    self.verifier.EXPECTED_P8_02_COMPLETED_EVIDENCE.issubset(
                        evidence
                    )
                )
            if requirement_id in self.verifier.EXPECTED_P8_03_COMPLETED_ALLOCATION:
                self.assertTrue(
                    self.verifier.EXPECTED_P8_03_COMPLETED_EVIDENCE.issubset(
                        evidence
                    )
                )
            if requirement_id in self.verifier.EXPECTED_P8_04_COMPLETED_ALLOCATION:
                self.assertTrue(
                    self.verifier.EXPECTED_P8_04_COMPLETED_EVIDENCE.issubset(
                        evidence
                    )
                )
            if requirement_id in self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION:
                self.assertTrue(
                    self.verifier.EXPECTED_P8_05_COMPLETED_EVIDENCE.issubset(
                        evidence
                    )
                )
            if requirement_id in self.verifier.EXPECTED_P8_06_COMPLETED_ALLOCATION:
                self.assertTrue(
                    self.verifier.EXPECTED_P8_06_COMPLETED_EVIDENCE.issubset(
                        evidence
                    )
                )

    def test_p8_05_completion_trace_is_frozen_without_overclaiming(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        self.assertEqual(
            by_id["INT-005"]["status"],
            "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_FOUNDATION_PRODUCTION_SANDBOX_MAPPING_HELD",
        )
        for requirement_id in (
            "FR-TL-011",
            "FR-TL-012",
            "FR-TL-013",
            "FR-TL-014",
            "FR-TL-015",
            "FR-TL-016",
        ):
            self.assertEqual(
                by_id[requirement_id]["status"],
                "TECHNICAL_VERIFIED_TOOL_ASSET_EXECUTION_PORTION_PRODUCTION_SANDBOX_BUSINESS_APPROVAL_AND_WHOLE_REQUIREMENT_HELD",
            )
        for requirement_id in self.verifier.EXPECTED_P8_05_COMPLETED_ALLOCATION:
            evidence = {
                value.strip()
                for value in by_id[requirement_id]["evidence"].split(";")
                if value.strip()
            }
            self.assertTrue(
                self.verifier.EXPECTED_P8_05_COMPLETED_EVIDENCE.issubset(evidence)
            )

    def test_completed_p8_tasks_use_non_secret_gitleaks_evidence_keys(self) -> None:
        phase_status = (ROOT / "implementation/PHASE_STATUS.yaml").read_text(
            encoding="utf-8"
        )
        expected_key = "final_gitleaks_artifact_sha256:"
        self.assertEqual(phase_status.count(expected_key), 2)
        self.assertNotIn("final_secret_artifact_sha256:", phase_status)
        digests = [
            line.split(":", 1)[1].strip()
            for line in phase_status.splitlines()
            if line.strip().startswith(expected_key)
        ]
        self.assertEqual(len(set(digests)), 2)
        for digest in digests:
            self.assertEqual(len(digest), 64)
            self.assertTrue(
                all(character in "0123456789abcdef" for character in digest)
            )

    def test_p8_06_completion_verifies_only_bounded_quality_portions(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        expected = {
            "INT-007": (
                "8",
                "TECHNICAL_VERIFIED_FORMAL_QUALITY_LINK_FOUNDATION_PRODUCTION_SANDBOX_POLICY_HELD",
            ),
            "FR-TR-006": (
                "8",
                "TECHNICAL_VERIFIED_FORMAL_QUALITY_REFERENCE_PORTION_PRODUCTION_SANDBOX_POLICY_AND_WHOLE_REQUIREMENT_HELD",
            ),
            "FR-NP-006": (
                "8",
                "TECHNICAL_VERIFIED_FORMAL_QUALITY_LINK_PORTION_PRODUCTION_SANDBOX_POLICY_AND_WHOLE_REQUIREMENT_HELD",
            ),
        }
        for requirement_id, expected_trace in expected.items():
            row = by_id[requirement_id]
            self.assertEqual((row["phase"], row["status"]), expected_trace)
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            self.assertTrue(
                self.verifier.EXPECTED_P8_ANCHOR_EVIDENCE.issubset(evidence)
            )
            self.assertTrue(
                self.verifier.EXPECTED_P8_06_COMPLETED_EVIDENCE.issubset(evidence)
            )

    def test_p8_07_is_technically_verified_with_external_holds(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        expected = {
            "FR-RP-009": "TECHNICAL_VERIFIED_OPERATION_CENTER_FOUNDATION_PRODUCTION_SANDBOX_FACTS_HELD",
            "NFR-INT-001": "TECHNICAL_VERIFIED_INTEGRATION_RELIABILITY_FOUNDATION_PRODUCTION_SANDBOX_FACTS_HELD",
            "UX-016": "TECHNICAL_VERIFIED_FOUNDATION",
        }
        for requirement_id, status in expected.items():
            row = by_id[requirement_id]
            self.assertEqual(row["phase"], "8")
            self.assertEqual(row["status"], status)
            evidence = {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            }
            self.assertTrue(
                self.verifier.EXPECTED_P8_07_PLAN_EVIDENCE.issubset(evidence)
            )
            self.assertTrue(
                self.verifier.EXPECTED_P8_07_COMPLETED_EVIDENCE.issubset(evidence)
            )

        phase_status = (ROOT / "implementation/PHASE_STATUS.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("status: PASS_LEVEL_3_BOUNDED_TECHNICAL_PORTIONS", phase_status)
        self.assertIn(
            "DERIVED_FROM_OWNING_TERMINAL_TRUTH_NOT_A_SECOND_MUTABLE_COPY",
            phase_status,
        )

    def test_p8_07f_governance_is_conditional_read_only_and_minimal(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        plan = (
            ROOT
            / "implementation/evidence/phase-8/p8-07f-production-fact-reconciliation-plan.md"
        ).read_text(encoding="utf-8")
        quality_gate = (ROOT / "implementation/QUALITY_GATE.md").read_text(
            encoding="utf-8"
        )
        current_runtime_transition = (
            ROOT
            / "implementation/evidence/phase-8/p8-07f-current-runtime-governance-transition.md"
        ).read_text(encoding="utf-8")
        phase_status = (ROOT / "implementation/PHASE_STATUS.yaml").read_text(
            encoding="utf-8"
        )

        for required in (
            "P8-07F-GOVERNANCE",
            "P8-07F-FACTS",
            "BatchMode",
            "StrictHostKeyChecking",
            "ClearAllForwardings",
            "DIRECT_MATCH",
            "MINOR_LAUNCHFLOW_ADJUSTMENT",
            "MINOR_ERPNEXT_CUSTOM_APP_ADJUSTMENT",
            "NO_CHANGE",
            "P8-07F-CURRENT-RUNTIME-GOVERNANCE",
            "current tracked production worktree",
            "fixed application-layer read",
        ):
            self.assertIn(required, agents + plan + current_runtime_transition)
        for prohibited in (
            "sudo",
            "console",
            "DocType mutation",
            "replay or reconciliation action",
            "Direct SQL",
        ):
            self.assertIn(prohibited, agents + plan + current_runtime_transition)
        self.assertIn("production_connection_authorized_now: false", phase_status)
        self.assertIn(
            "facts_connection_requires_activation_ordinary_pass: true",
            phase_status,
        )
        self.assertIn("p8_08_blocked_until_facts_gate: false", phase_status)
        self.assertIn("tracked_path_inventory_apps_accepted: 20", phase_status)
        self.assertIn("sensitive_preflight_stops: 2", phase_status)
        self.assertIn("private_state_removed: true", phase_status)
        self.assertIn(
            "runtime_only_metadata_status: ACCEPTED_ALL_FROZEN_FAMILIES_INCLUDING_SYSTEM_LOCALE",
            phase_status,
        )
        self.assertIn("locale_reader_ordinary: 33312664804", phase_status)
        self.assertIn(
            "locale_collection_result: ACCEPTED_COUNTRY_LANGUAGE_TIME_ZONE_CHECKSUM_CC94B21F",
            phase_status,
        )
        self.assertIn(
            "facts_status: PASS_BOUNDED_COMPATIBILITY_RECONCILIATION_LEVEL_3",
            phase_status,
        )
        self.assertIn("current_task: P9-08", phase_status)
        self.assertIn("p9_07:", phase_status)
        self.assertIn("final_level_3: 33730710124_PASS", phase_status)
        self.assertIn("p9_08:", phase_status)
        self.assertIn(
            "evidence_class: CONTROLLED_NON_PRODUCTION_TECHNICAL_UAT",
            phase_status,
        )
        self.assertIn("overall_status: IMPLEMENTATION_COMPLETE", phase_status)
        self.assertIn("final_level_3: 33742476664_PASS", phase_status)
        self.assertIn("final_release_gate: PASS", phase_status)
        self.assertIn("production_ready: false", phase_status)
        self.assertIn("status: PASS_LEVEL_3", phase_status)
        self.assertIn("final_level_3: 33660141866", phase_status)
        self.assertIn("p9_01d_final_result: PASS_ALL_DIAGNOSTICS_OFF_COMPLETE_CUMULATIVE_RUNTIME", phase_status)
        self.assertIn("diagnostics_off_final_level_3: 33330886346", phase_status)
        self.assertIn(
            "technical_result: PASS_INTERNAL_READ_ONLY_PROJECTION_SEAM_EXTERNAL_CONTRACT_HELD",
            phase_status,
        )
        self.assertIn("p8_09:", phase_status)
        self.assertIn("diagnostics_off_final_level_3: 33342817983", phase_status)
        self.assertIn(
            "technical_result: PASS_PRESENTATION_ONLY_IDENTITY_TECHNICAL_CODE_UNCHANGED",
            phase_status,
        )
        self.assertIn("p9_00:", phase_status)
        self.assertIn("repair_ordinary: 33345162833", phase_status)
        self.assertIn("p9_01:", phase_status)
        self.assertIn("product_code_authorized: false", phase_status)
        self.assertIn(
            "diagnostics_off_final_level_3: 33318628754", phase_status
        )
        self.assertIn(
            "current_tracked_worktree_source_status: ACCEPTED_CURRENT_TRACKED_WORKTREE_STRUCTURAL_SUMMARIES_WITH_DIRTY_TREES_AS_CURRENT_SOURCE_TRUTH",
            phase_status,
        )
        self.assertIn(
            "fixed_parent_collector_ordinary: 33307715636",
            phase_status,
        )
        self.assertIn(
            "fixed_site_fact_collector_ordinary: 33309768019",
            phase_status,
        )
        self.assertIn(
            "client_script_paging_contract: PAGE_SIZE_20_MAX_25_PAGES_KEEP_512_KIB_PER_CALL_LIMIT",
            phase_status,
        )
        self.assertIn("bounded_client_paging_ordinary: 33310528823", phase_status)
        self.assertIn("inventory_bound_parent_reader_ordinary: 33311432825", phase_status)
        self.assertIn("accepted_client_script_rows: 98", phase_status)
        self.assertIn("accepted_client_script_pages: 5", phase_status)
        self.assertIn("accepted_required_doctype_rows: 27", phase_status)
        self.assertIn(
            "missing_required_doctypes: [Injection Molding Condition]",
            phase_status,
        )
        self.assertIn(
            "parent_reader_contract: ONLY_ACCEPTED_FIXED_DOCTYPE_INVENTORY_NAMES_NONALLOWLISTED_REJECTED_MISSING_CHECKSUMMED",
            phase_status,
        )
        self.assertIn("accepted_docperms_rows: 120", phase_status)
        self.assertIn("total: 47376", phase_status)
        self.assertIn("local_public: 1632", phase_status)
        self.assertIn("local_private: 45470", phase_status)
        self.assertIn("external_http: 272", phase_status)
        self.assertIn(
            "locale_reader_contract: SYSTEM_SETTINGS_SINGLE_DOCTYPE_FIXED_GET_VALUE_NO_FILTER_EXACT_LANGUAGE_TIME_ZONE_COUNTRY",
            phase_status,
        )
        self.assertIn(
            "runtime_read_implementation: FIXED_FRAPPE_APPLICATION_LAYER_GET_LIST_GET_VALUE_GET_COUNT_NO_SQL_NO_CONSOLE",
            phase_status,
        )
        self.assertIn("direct_sql_and_console_status: PROHIBITED", phase_status)
        self.assertIn("FINAL_FULL_PRODUCTION", (ROOT / "implementation/CURRENT_TASK.json").read_text(encoding="utf-8"))
        self.assertIn("blocks `IMPLEMENTATION_COMPLETE`", quality_gate)

    def test_p8_09_trace_is_verified_with_presentation_only_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        row = {value["requirement_id"]: value for value in rows}["FR-BR-002"]
        self.assertEqual(row["phase"], "8")
        self.assertEqual(
            row["status"], self.verifier.EXPECTED_P8_09_COMPLETED_STATUS
        )
        evidence = {
            value.strip()
            for value in row["evidence"].split(";")
            if value.strip()
        }
        self.assertTrue(
            self.verifier.EXPECTED_P8_09_COMPLETED_EVIDENCE.issubset(evidence)
        )

    def test_r1_04_trace_is_verified_with_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        expected_statuses = {
            "FR-UX-038": "TECHNICAL_VERIFIED",
            "UX-007": "TECHNICAL_VERIFIED_FOUNDATION",
            "UX-027": "TECHNICAL_VERIFIED_FOUNDATION",
            "UX-028": "TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD",
        }
        for requirement_id, expected_status in expected_statuses.items():
            self.assertEqual(by_id[requirement_id]["status"], expected_status)
            self.assertIn(
                "implementation/evidence/reconciliation/r1-04-validation.md",
                by_id[requirement_id]["evidence"],
            )
        self.assertIn(
            "implementation/evidence/phase-6/p6-08-validation.md",
            by_id["UX-007"]["evidence"],
        )
        for _, expected_evidence in self.verifier.EXPECTED_R1_04_TRACE.values():
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )

    def test_all_r1_05_stage_traces_are_verified(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        pane_row = by_id["FR-UX-040"]
        self.assertEqual(
            (
                pane_row["priority"],
                pane_row["phase"],
                pane_row["status"],
                pane_row["source"],
                pane_row["trace_kind"],
                pane_row["canonical_ids"],
            ),
            (
                "P0",
                "5",
                "TECHNICAL_VERIFIED",
                "docs/V1_2_RECONCILIATION_ADDENDUM.md",
                "ADDENDUM_DIRECT",
                "FR-UX-040",
            ),
        )
        self.assertEqual(
            {
                value.strip()
                for value in pane_row["evidence"].split(";")
                if value.strip()
            },
            self.verifier.EXPECTED_R1_05_STAGE_1_TRACE["FR-UX-040"][1],
        )
        field_attachment_row = by_id["FR-UX-041"]
        self.assertEqual(
            (
                field_attachment_row["priority"],
                field_attachment_row["phase"],
                field_attachment_row["status"],
                field_attachment_row["source"],
                field_attachment_row["trace_kind"],
                field_attachment_row["canonical_ids"],
            ),
            (
                "P0",
                "5",
                "TECHNICAL_VERIFIED",
                "docs/V1_2_RECONCILIATION_ADDENDUM.md",
                "ADDENDUM_DIRECT",
                "FR-UX-041",
            ),
        )
        self.assertEqual(
            {
                value.strip()
                for value in field_attachment_row["evidence"].split(";")
                if value.strip()
            },
            self.verifier.EXPECTED_R1_05_STAGE_2_TRACE["FR-UX-041"][1],
        )
        self.assertEqual(
            by_id["FR-UX-043"]["status"],
            "TECHNICAL_VERIFIED",
        )
        self.assertEqual(
            {
                value.strip()
                for value in by_id["FR-UX-043"]["evidence"].split(";")
                if value.strip()
            },
            self.verifier.EXPECTED_R1_05_STAGE_3_TRACE["FR-UX-043"][1],
        )
        for _, expected_evidence in self.verifier.EXPECTED_R1_05_STAGE_1_TRACE.values():
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )
        for _, expected_evidence in self.verifier.EXPECTED_R1_05_STAGE_2_TRACE.values():
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )
        for _, expected_evidence in self.verifier.EXPECTED_R1_05_STAGE_3_TRACE.values():
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )

    def test_fr_ux_043_is_allocated_to_r1_05(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        icon_action_row = by_id["FR-UX-043"]
        self.assertEqual(
            {
                key: icon_action_row[key]
                for key in (
                    "requirement_id",
                    "priority",
                    "phase",
                    "status",
                    "source",
                    "trace_kind",
                    "canonical_ids",
                )
            },
            {
                "requirement_id": "FR-UX-043",
                "priority": "P0",
                "phase": "5",
                "status": "TECHNICAL_VERIFIED",
                "source": "docs/V1_2_RECONCILIATION_ADDENDUM.md",
                "trace_kind": "ADDENDUM_DIRECT",
                "canonical_ids": "FR-UX-043",
            },
        )
        self.assertEqual(
            {
                value.strip()
                for value in icon_action_row["evidence"].split(";")
                if value.strip()
            },
            self.verifier.EXPECTED_R1_05_STAGE_3_TRACE["FR-UX-043"][1],
        )
        addendum = self.verifier.ADDENDUM.read_text(encoding="utf-8")
        self.assertIn("| FR-UX-043 | P0 |", addendum)
        self.assertIn("Append-only amendment: 2026-07-27", addendum)
        self.assertIn("the user-approved 2026-07-26 amended autopilot plan", addendum)
        backlog = (self.verifier.ROOT / "implementation/backlog.yaml").read_text(
            encoding="utf-8"
        )
        r1_05 = backlog.split("  - id: R1-05\n", 1)[1].split("  - id: R1-06\n", 1)[0]
        self.assertIn("    - FR-UX-043\n", r1_05)
        industrial_ux_skill = (
            self.verifier.ROOT / ".agents/skills/industrial-ux/SKILL.md"
        ).read_text(encoding="utf-8")
        for required_guard in (
            "repository-owned\n  local icon adapter",
            "translated accessible name",
            "Retain visible text for primary, high-risk or ambiguous\n  actions",
            "unapproved Primer/Octicons",
        ):
            self.assertIn(required_guard, industrial_ux_skill)
        definition_of_done = (self.verifier.ROOT / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        for required_guard in (
            "icon-first 次级动作仅通过仓库本地图标适配层",
            "名称/tooltip、键盘、焦点、禁用和非 hover 路径",
            "主动作、高风险或含义不明",
            "Primer/Octicons 依赖",
        ):
            self.assertIn(required_guard, definition_of_done)

    def test_r1_06_stage_1_trace_separates_prototype_truth_from_approval(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        expected_statuses = {
            "UX-026": "PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD",
            "UX-030": "TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD",
        }
        for requirement_id, expected_status in expected_statuses.items():
            row = by_id[requirement_id]
            self.assertEqual(row["status"], expected_status)
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                self.verifier.EXPECTED_R1_06_STAGE_1_TRACE[requirement_id][1],
            )
        manifest = (
            self.verifier.ROOT
            / "implementation"
            / "prototype-approvals"
            / "r1-06-my-work-grid-reset.json"
        ).read_text(encoding="utf-8")
        self.assertIn('"status": "PENDING_PRODUCT_OWNER"', manifest)
        self.assertIn('"backendImplementationAuthorized": false', manifest)
        for _, expected_evidence in self.verifier.EXPECTED_R1_06_STAGE_1_TRACE.values():
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )

    def test_r1_06_stage_3_trace_covers_current_p0_visual_scope(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for requirement_id in ("UX-035", "UX-036"):
            row = by_id[requirement_id]
            self.assertEqual(
                row["status"],
                "TECHNICAL_VERIFIED_CURRENT_P0_SCOPE",
            )
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                self.verifier.EXPECTED_R1_06_STAGE_3_TRACE[requirement_id][1],
            )
        self.assertIn(
            "implementation/evidence/reconciliation/r1-04-validation.md",
            by_id["UX-035"]["evidence"],
        )
        self.assertIn(
            "implementation/evidence/phase-3/visual-review.md",
            by_id["UX-036"]["evidence"],
        )
        for _, expected_evidence in self.verifier.EXPECTED_R1_06_STAGE_3_TRACE.values():
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )

    def test_p5_01_trace_records_level_2_scope_without_overclaiming_holds(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for (
            requirement_id,
            (expected_status, expected_evidence),
        ) in self.verifier.EXPECTED_P5_01_COMPLETED_TRACE.items():
            row = by_id[requirement_id]
            self.assertEqual(row["status"], expected_status)
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                expected_evidence,
            )
            self.assertTrue(row["status"].startswith("TECHNICAL_VERIFIED"))
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )
        self.assertEqual(
            by_id["FR-DS-003"]["status"],
            "TECHNICAL_VERIFIED",
        )
        for requirement_id in (
            "FR-DS-001",
            "FR-DS-004",
            "FR-DS-007",
            "FR-DS-008",
            "FR-DS-009",
            "FR-DS-014",
        ):
            self.assertEqual(
                by_id[requirement_id]["status"],
                "TECHNICAL_VERIFIED_FOUNDATION",
            )

    def test_p5_02_trace_records_level_2_scope_without_overclaiming_holds(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        for (
            requirement_id,
            (expected_status, expected_evidence),
        ) in self.verifier.EXPECTED_P5_02_COMPLETED_TRACE.items():
            row = by_id[requirement_id]
            self.assertEqual(row["status"], expected_status)
            self.assertEqual(
                {
                    value.strip()
                    for value in row["evidence"].split(";")
                    if value.strip()
                },
                expected_evidence,
            )
            self.assertTrue(row["status"].startswith("TECHNICAL_VERIFIED"))
            for evidence_path in expected_evidence:
                self.assertTrue(
                    (self.verifier.ROOT / evidence_path).is_file(),
                    evidence_path,
                )
        self.assertEqual(by_id["FR-DS-002"]["status"], "TECHNICAL_VERIFIED")
        for requirement_id in ("FR-DS-005", "FR-DS-010"):
            self.assertEqual(
                by_id[requirement_id]["status"],
                "TECHNICAL_VERIFIED_FOUNDATION",
            )

    def test_p5_03_trace_records_level_2_truth(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        expected_status, expected_evidence = (
            self.verifier.EXPECTED_P5_03_COMPLETED_TRACE["FR-DS-006"]
        )
        row = by_id["FR-DS-006"]
        self.assertEqual(row["status"], expected_status)
        self.assertEqual(
            {
                value.strip()
                for value in row["evidence"].split(";")
                if value.strip()
            },
            expected_evidence,
        )
        self.assertTrue(row["status"].startswith("TECHNICAL_VERIFIED"))
        for evidence_path in expected_evidence:
            self.assertTrue(
                (self.verifier.ROOT / evidence_path).is_file(),
                evidence_path,
            )

    def test_brand_package_is_exact_and_self_contained(self) -> None:
        self.verifier.verify_brand_package()

    def test_csv_reader_rejects_malformed_quoted_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text('name,value\nCore.png,"unterminated\n', encoding="utf-8")
            with self.assertRaises(csv.Error):
                self.verifier._read_csv(path)

    def test_brand_png_rejects_size_dimension_and_pixel_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cases = (
                (
                    "encoded-size",
                    b"x" * (self.verifier.MAX_BRAND_PNG_FILE_BYTES + 1),
                    "file size",
                ),
                (
                    "dimension",
                    _png_document(width=self.verifier.MAX_BRAND_PNG_DIMENSION + 1),
                    "dimensions",
                ),
                (
                    "pixels",
                    _png_document(width=4097, height=4097),
                    "pixel budget",
                ),
            )
            for name, payload, error_pattern in cases:
                with self.subTest(name=name):
                    path = Path(directory) / f"{name}.png"
                    path.write_bytes(payload)
                    with self.assertRaisesRegex(
                        self.verifier.ReconciliationVerificationError,
                        error_pattern,
                    ):
                        self.verifier._verify_png_is_safe(path)

    def test_brand_png_rejects_invalid_structure_crc_and_termination(self) -> None:
        valid = _png_document()
        bad_crc = bytearray(valid)
        bad_crc[32] ^= 1
        cases = (
            ("signature", b"not-png!", "signature"),
            ("truncated", valid[:-1], "truncated chunk"),
            ("crc", bytes(bad_crc), "CRC differs"),
            ("missing-iend", _png_document(include_iend=False), "unique IEND"),
            ("trailing", valid + b"x", "trailing data"),
            (
                "multiple-iend",
                valid + _png_chunk(b"IEND", b""),
                "multiple IEND",
            ),
            (
                "short-ihdr",
                PNG_SIGNATURE + _png_chunk(b"IHDR", b"\x00" * 12),
                "13-byte leading IHDR",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            for name, payload, error_pattern in cases:
                with self.subTest(name=name):
                    path = Path(directory) / f"{name}.png"
                    path.write_bytes(payload)
                    with self.assertRaisesRegex(
                        self.verifier.ReconciliationVerificationError,
                        error_pattern,
                    ):
                        self.verifier._verify_png_is_safe(path)

    def test_brand_png_rejects_animation_and_unknown_critical_chunks(self) -> None:
        cases = (
            (
                "animation",
                _png_document(
                    extra_chunks=(_png_chunk(b"acTL", struct.pack(">II", 1, 0)),)
                ),
                "animated PNG chunks",
            ),
            (
                "unknown-critical",
                _png_document(extra_chunks=(_png_chunk(b"ABCD", b""),)),
                "unsupported critical chunk ABCD",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            for name, payload, error_pattern in cases:
                with self.subTest(name=name):
                    path = Path(directory) / f"{name}.png"
                    path.write_bytes(payload)
                    with self.assertRaisesRegex(
                        self.verifier.ReconciliationVerificationError,
                        error_pattern,
                    ):
                        self.verifier._verify_png_is_safe(path)


if __name__ == "__main__":
    unittest.main()
