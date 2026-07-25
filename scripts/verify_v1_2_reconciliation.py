#!/usr/bin/env python3
"""Verify the accepted V1.2 DOCX–Pack reconciliation and brand package."""

from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "implementation/V1_2_DOCX_REQUIREMENTS.csv"
COVERAGE = ROOT / "implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv"
TRACE = ROOT / "implementation/REQUIREMENT_TRACEABILITY.csv"
TOOLING_MAPPING = ROOT / "docs/reference/TOOLING_LIST_FIELD_MAPPING.csv"
ADDENDUM = ROOT / "docs/V1_2_RECONCILIATION_ADDENDUM.md"
BRAND_DIRECTORY = ROOT / "docs/Brand Asset"
BRAND_INSTRUCTIONS = BRAND_DIRECTORY / "Brand Asset Instruction.csv"

EXPECTED_TRACE_KINDS = {
    "PACK_CANONICAL": 173,
    "DOCX_RECONCILED": 95,
    "ADDENDUM_DIRECT": 13,
}
EXPECTED_PACK_ID_SET_SHA256 = (
    "2150b062153317c2b3f06362c3d3b00aff25f10b2bdaebbb452ebda1e5f666fb"
)
PRE_RECONCILIATION_CHECKPOINT = "930b5a28cb995df12f251994a36f7502525ed94a"
EXPECTED_COVERAGE_COUNTS = {
    "EXPLICIT_SAME_ID": 134,
    "EXPLICIT_EQUIVALENT": 23,
    "GOVERNANCE_COVERED_NOT_REQUIREMENT_TRACEABLE": 22,
    "NARRATIVE_EXPLICIT_NOT_TRACEABLE": 12,
    "EXPLICIT_CONSOLIDATED_NO_ALIAS": 7,
    "PARTIAL_EXPLICIT": 9,
    "PARTIAL_NARRATIVE": 5,
    "NARRATIVE_ONLY_HIGH_RISK": 5,
    "MISSING_UNIQUE_REQUIREMENT": 7,
    "OTHER_ISOLATED_CASE": 5,
}
ADDENDUM_IDS = {
    "FR-UX-038",
    "FR-UX-039",
    "FR-UX-040",
    "FR-UX-041",
    "FR-UX-042",
    "FR-PRN-001",
    "FR-PRN-002",
    "FR-PRN-003",
    "FR-INT-015",
    "FR-BR-001",
    "FR-BR-002",
    "FR-TX-019",
    "FR-TX-020",
}
EXPECTED_UX_REMEDIATION_ALLOCATION = {
    "UX-003": ("9", "PLANNED_FULL_PRODUCT_UAT"),
    "UX-004": ("6", "PLANNED_PHASE_6_TOOLING_WORKSPACE"),
    "UX-007": ("5", "PLANNED_R1_04_GRID_PERSONALIZATION"),
    "UX-011": ("5", "PLANNED_R1_03_CONTEXT_QUICK_CREATE"),
    "UX-016": ("8", "PLANNED_PHASE_6_8_ASYNC_JOB_TRUTH"),
    "UX-018": ("5", "PLANNED_R1_03_COMMAND_FOUNDATION"),
    "UX-020": ("7", "PLANNED_PHASE_7_MOBILE_FIELD_ACTIONS"),
    "UX-026": ("5", "PLANNED_R1_06_CONTROLLED_UNDO"),
    "UX-027": ("5", "PLANNED_R1_04_PERSONALIZATION"),
    "UX-028": ("5", "PLANNED_R1_04_PUBLISHED_VIEWS"),
    "UX-030": ("5", "PLANNED_R1_06_PROTOTYPE_GATE"),
    "UX-035": ("5", "PLANNED_R1_04_R1_06_DENSITY"),
    "UX-036": ("5", "PLANNED_R1_06_1440_VISUAL_MATRIX"),
}
EXPECTED_BRAND_INSTRUCTIONS = {
    "Company LOGO.svg": (
        "Website Footer",
        "Use it in the website footer, to indicate that the platform is the "
        "company's asset",
    ),
    "Loading.svg": (
        "Loading Page, Start Page",
        "User see this logo on a blank page when entering the website, or "
        "while loading",
    ),
    "LaunchFlow Icon.svg": (
        "Used as Website Favicon and Place Indicates this Platform",
        "Favicon, also when place mentions the platform (e.g. when the "
        'platform contains information like "Source: NPI One (or '
        "LaunchFlow), use this icon to replace the text instead)",
    ),
    "LaunchFlow-logo_White.svg": (
        "Standard LOGO, used for dark backgraounds",
        "",
    ),
    "LaunchFlow-logo_Standard.svg": (
        "Standard LOGO, used for light backgraounds",
        "",
    ),
}
EXPECTED_BRAND_HASHES = {
    "Brand Asset Instruction.csv": (
        "e790a059d544e709c741845e0a4ee3b078b9c36451bf5a8cd34b5d2171fd372a"
    ),
    "Company LOGO.svg": (
        "856237b6bb2a9fb2d3674c7ede318eb8e3630a0ab12c451d64a25122e272a8ff"
    ),
    "LaunchFlow Icon.svg": (
        "bddf68cb729a1da8378dfdc1136173b6a014706fec6b58e8421d0f4ae8892452"
    ),
    "LaunchFlow-logo_Standard.svg": (
        "d2397fc9a21067a78655e9e84c4645a22cd1e4cc88835f665f7cbb7a29f6e2b6"
    ),
    "LaunchFlow-logo_White.svg": (
        "55b9ab1e7b4ab9330acfc73c2ddb099db38c865d0704781f256c2cf113d4226d"
    ),
    "Loading.svg": ("730e9e621881afbc1d3cb8520792b2ddc75f6b9dc4035311599a105a934cc253"),
}


class ReconciliationVerificationError(RuntimeError):
    """Raised when a reconciled source or generated artifact is inconsistent."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _require_unique(
    rows: list[dict[str, str]], key: str, expected_count: int, label: str
) -> set[str]:
    values = [row[key] for row in rows]
    if len(values) != expected_count or len(set(values)) != expected_count:
        raise ReconciliationVerificationError(
            f"{label} must contain {expected_count} unique {key} values"
        )
    return set(values)


def verify_trace_sets() -> None:
    requirements = _read_csv(REQUIREMENTS)
    coverage = _read_csv(COVERAGE)
    trace = _read_csv(TRACE)
    tooling_mapping = _read_csv(TOOLING_MAPPING)

    docx_ids = _require_unique(requirements, "requirement_id", 229, "DOCX requirements")
    coverage_ids = _require_unique(
        coverage, "docx_requirement_id", 229, "coverage matrix"
    )
    trace_ids = _require_unique(trace, "requirement_id", 281, "traceability")
    _require_unique(tooling_mapping, "source_column", 43, "Tooling List field mapping")

    if coverage_ids != docx_ids:
        raise ReconciliationVerificationError(
            "coverage matrix IDs differ from the authoritative DOCX IDs"
        )
    if not docx_ids.issubset(trace_ids):
        raise ReconciliationVerificationError(
            "traceability does not retain all 229 DOCX requirement IDs"
        )
    if not ADDENDUM_IDS.issubset(trace_ids):
        raise ReconciliationVerificationError(
            "traceability does not retain every addendum requirement ID"
        )

    trace_kind_counts = Counter(row["trace_kind"] for row in trace)
    if dict(trace_kind_counts) != EXPECTED_TRACE_KINDS:
        raise ReconciliationVerificationError(
            f"unexpected trace-kind counts: {dict(trace_kind_counts)}"
        )
    coverage_counts = Counter(
        row["coverage_status_before_reconciliation"] for row in coverage
    )
    if dict(coverage_counts) != EXPECTED_COVERAGE_COUNTS:
        raise ReconciliationVerificationError(
            f"unexpected coverage counts: {dict(coverage_counts)}"
        )

    by_id = {row["requirement_id"]: row for row in trace}
    canonical_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if row["trace_kind"] == "PACK_CANONICAL"
    }
    if len(canonical_ids - docx_ids) != 39:
        raise ReconciliationVerificationError(
            "the trace must retain exactly 39 Pack-only normalized IDs"
        )

    for requirement_id, (
        expected_phase,
        expected_status,
    ) in EXPECTED_UX_REMEDIATION_ALLOCATION.items():
        row = by_id[requirement_id]
        if (row["phase"], row["status"]) != (
            expected_phase,
            expected_status,
        ):
            raise ReconciliationVerificationError(
                f"{requirement_id} has stale remediation allocation"
            )

    linked_alias_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if row["trace_kind"] == "DOCX_RECONCILED"
        and row["status"] == "RECONCILED_ALIAS_LINKED_TO_CANONICAL_IDS"
        and row["phase"] == "3"
    }
    governance_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if row["trace_kind"] == "DOCX_RECONCILED"
        and row["status"] == "RECONCILED_GOVERNANCE_LINKED_NON_PRODUCT"
        and row["phase"] == "0"
    }
    tooling_ids = {
        requirement_id
        for requirement_id, row in by_id.items()
        if row["trace_kind"] == "DOCX_RECONCILED"
        and row["status"] == "PLANNED_PHASE_6_RECONCILED"
        and row["phase"] == "6"
    }
    if len(linked_alias_ids) != 30:
        raise ReconciliationVerificationError(
            "expected 30 non-blocking UX/I18N alias links"
        )
    if len(governance_ids) != 34:
        raise ReconciliationVerificationError(
            "expected 34 non-product ARCH/COD governance links"
        )
    if len(tooling_ids) != 18:
        raise ReconciliationVerificationError(
            "expected 18 Phase 6 Tooling requirements"
        )
    canonical_id_payload = "\n".join(sorted(canonical_ids)) + "\n"
    canonical_id_digest = hashlib.sha256(
        canonical_id_payload.encode("utf-8")
    ).hexdigest()
    if canonical_id_digest != EXPECTED_PACK_ID_SET_SHA256:
        raise ReconciliationVerificationError(
            "the original 173-ID Pack set differs from its accepted baseline"
        )

    for row in coverage:
        if row["pre_reconciliation_checkpoint"] != PRE_RECONCILIATION_CHECKPOINT:
            raise ReconciliationVerificationError(
                "coverage evidence is not fixed to the accepted "
                "pre-reconciliation checkpoint"
            )
        mappings = {
            value.strip()
            for value in row["pack_requirement_ids"].split(";")
            if value.strip()
        }
        unknown = mappings - canonical_ids
        if unknown:
            raise ReconciliationVerificationError(
                f"{row['docx_requirement_id']} maps to non-Pack IDs: "
                f"{sorted(unknown)}"
            )

    addendum_text = ADDENDUM.read_text(encoding="utf-8")
    missing_addendum_ids = sorted(
        requirement_id
        for requirement_id in ADDENDUM_IDS
        if requirement_id not in addendum_text
    )
    if missing_addendum_ids:
        raise ReconciliationVerificationError(
            f"addendum text omits IDs: {missing_addendum_ids}"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_svg_is_self_contained(path: Path) -> None:
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise ReconciliationVerificationError(
            f"brand asset is not valid XML: {path.name}"
        ) from exc

    local_root_name = root.tag.rsplit("}", 1)[-1]
    if local_root_name != "svg":
        raise ReconciliationVerificationError(
            f"brand asset root is not SVG: {path.name}"
        )

    disallowed_elements = {"script", "foreignObject", "image"}
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name in disallowed_elements:
            raise ReconciliationVerificationError(
                f"brand asset contains disallowed {local_name}: {path.name}"
            )
        for attribute_name, value in element.attrib.items():
            local_attribute = attribute_name.rsplit("}", 1)[-1].lower()
            normalized_value = value.strip().lower()
            if local_attribute.startswith("on"):
                raise ReconciliationVerificationError(
                    f"brand asset contains an event handler: {path.name}"
                )
            if local_attribute in {"href", "src"} and normalized_value:
                if not normalized_value.startswith("#"):
                    raise ReconciliationVerificationError(
                        f"brand asset contains an external reference: {path.name}"
                    )
            if "url(" in normalized_value and "url(#" not in normalized_value:
                raise ReconciliationVerificationError(
                    f"brand asset contains an external URL: {path.name}"
                )


def verify_brand_package() -> None:
    actual_files = {path.name for path in BRAND_DIRECTORY.iterdir() if path.is_file()}
    expected_files = set(EXPECTED_BRAND_HASHES)
    if actual_files != expected_files:
        raise ReconciliationVerificationError(
            "brand package file set differs from its accepted sole-source "
            f"baseline: missing={sorted(expected_files - actual_files)}, "
            f"unexpected={sorted(actual_files - expected_files)}"
        )

    instruction_rows = _read_csv(BRAND_INSTRUCTIONS)
    instructions = {
        row["Document Name"]: (row["Usage Scope"], row["Instruction"])
        for row in instruction_rows
    }
    if len(instruction_rows) != 5 or instructions != EXPECTED_BRAND_INSTRUCTIONS:
        raise ReconciliationVerificationError(
            "brand usage instructions differ from the accepted sole-source CSV"
        )

    for filename, expected_hash in EXPECTED_BRAND_HASHES.items():
        path = BRAND_DIRECTORY / filename
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise ReconciliationVerificationError(
                f"brand asset hash differs for {filename}: {actual_hash}"
            )
        if path.suffix.lower() == ".svg":
            _verify_svg_is_self_contained(path)


def verify_generated_artifacts() -> None:
    commands = (
        ("scripts/extract_v1_2_docx_artifacts.py", "--check"),
        ("scripts/generate_v1_2_coverage_matrix.py", "--check"),
        ("scripts/reconcile_v1_2_traceability.py",),
    )
    for command in commands:
        subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            check=True,
        )


def main() -> int:
    verify_generated_artifacts()
    verify_trace_sets()
    verify_brand_package()
    print("V1.2 reconciliation verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
