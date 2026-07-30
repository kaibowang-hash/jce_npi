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

    def test_launchflow_trace_is_verified_with_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        row = next(item for item in rows if item["requirement_id"] == "FR-BR-001")
        self.assertEqual(row["status"], "TECHNICAL_VERIFIED")
        self.assertIn(
            "implementation/evidence/reconciliation/r1-02-validation.md",
            row["evidence"],
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

    def test_r1_04_trace_is_verified_with_runtime_evidence(self) -> None:
        rows = self.verifier._read_csv(self.verifier.TRACE)
        by_id = {row["requirement_id"]: row for row in rows}
        expected_statuses = {
            "FR-UX-038": "TECHNICAL_VERIFIED",
            "UX-007": "TECHNICAL_VERIFIED_FOUNDATION",
            "UX-027": "TECHNICAL_VERIFIED_FOUNDATION",
            "UX-028": "TECHNICAL_VERIFIED_FOUNDATION_AUTHORITY_HELD",
            "UX-035": "TECHNICAL_VERIFIED_FOUNDATION",
        }
        for requirement_id, expected_status in expected_statuses.items():
            self.assertEqual(by_id[requirement_id]["status"], expected_status)
            self.assertIn(
                "implementation/evidence/reconciliation/r1-04-validation.md",
                by_id[requirement_id]["evidence"],
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
